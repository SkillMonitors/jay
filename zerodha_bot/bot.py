"""Nifty short-straddle bot for Zerodha with a hard stop-loss and a panic button.

  python bot.py                 PAPER mode (default): real quotes, FAKE orders. Run this for weeks first.
  python bot.py --live          real orders. Refused unless LIVE_TRADING=YES_I_UNDERSTAND_THIS_USES_REAL_MONEY is set.

Rules: at entry_time sell the at-the-money (+offset) CALL and PUT. Exit BOTH legs when ANY of these happens:
  * combined premium to buy back >= entry combined premium x (1 + stop_loss_pct)      -> STOP LOSS
  * mark-to-market loss >= max_daily_loss rupees                                       -> MAX LOSS
  * clock reaches exit_time                                                             -> TIME EXIT
  * you press PANIC (dashboard button / `touch PANIC` file / panic.py / Ctrl+C)         -> PANIC: cancel all orders, close ALL positions
  * quotes stop arriving (data fault)                                                   -> FAIL-SAFE exit
If only one leg gets filled at entry, it is closed immediately and the bot stops."""
import argparse, json, os, signal, sys, threading, time
from datetime import datetime, time as dtime
from http.server import BaseHTTPRequestHandler, HTTPServer
from zoneinfo import ZoneInfo
from broker import make_broker, round_tick
from config import Config
from squareoff import square_off_all, _marketable

IST = ZoneInfo("Asia/Kolkata")
PAGE = """<!doctype html><meta charset=utf-8><title>Straddle bot</title><body style="font-family:system-ui;max-width:560px;margin:40px auto;text-align:center">
<h2>Straddle bot</h2><pre id=s style="text-align:left;background:#f4f4f4;padding:12px;border-radius:8px">loading...</pre>
<button onclick="fetch('/panic',{method:'POST'}).then(()=>document.getElementById('m').innerText='PANIC SENT - cancelling orders and closing all positions')"
 style="font-size:32px;padding:24px 48px;background:#c62828;color:#fff;border:0;border-radius:12px;cursor:pointer">PANIC - EXIT ALL</button><p id=m></p>
<script>setInterval(()=>fetch('/status').then(r=>r.text()).then(t=>document.getElementById('s').innerText=t),1500)</script></body>"""


class Bot:
    def __init__(self, broker, cfg: Config, now_fn=None, sleep_fn=time.sleep, log=None):
        self.b, self.cfg, self.sleep = broker, cfg, sleep_fn
        self.now = now_fn or (lambda: datetime.now(IST)); self.panic = threading.Event(); self.status = dict(state="idle")
        os.makedirs(cfg.state_dir, exist_ok=True); os.makedirs("logs", exist_ok=True)
        self._log = log or (lambda m: print(m, flush=True))
        self.result = None

    # ------------------------------------------------------------------ utilities
    def log(self, msg):
        line = f"{self.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"; self._log(line)
        try:
            with open(os.path.join("logs", f"{self.now().date()}.log"), "a") as f: f.write(line + "\n")
        except OSError: pass

    def _t(self, hhmm): h, m = map(int, hhmm.split(":")); return self.now().replace(hour=h, minute=m, second=0, microsecond=0)

    def _panic_requested(self):
        if os.path.exists("PANIC"):
            try: os.remove("PANIC")
            except OSError: pass
            self.panic.set()
        return self.panic.is_set()

    @staticmethod
    def _write(path, obj):
        with open(path, "w") as f: json.dump(obj, f)

    def _guard_once_per_day(self):
        f = os.path.join(self.cfg.state_dir, f"traded_{self.now().date()}.json")
        if os.path.exists(f): raise SystemExit(f"Already traded today ({f}). Delete it only if you are sure no position is open.")
        return f

    # ------------------------------------------------------------------ order helpers
    def _fill(self, symbol, side, qty):
        """Place a marketable LIMIT order, wait for it, widen the price on retries. Returns (filled_qty, avg_price)."""
        got, cost = 0, 0.0
        for k in range(1, self.cfg.exit_retries + 1):
            need = qty - got
            if need <= 0: break
            try: q = self.b.quotes([symbol])[symbol]
            except Exception: q = None                                               # data feed down: still get out, using a MARKET order
            last = (k == self.cfg.exit_retries or q is None) and side == "BUY"        # closing a short must not fail: final try (or no quote) is a MARKET order
            oid = self.b.place(symbol, side, need, order_type="MARKET") if last else self.b.place(symbol, side, need, price=_marketable(side, q, self.cfg.order_buffer_pct * k), order_type="LIMIT")
            deadline = self.now().timestamp() + self.cfg.fill_timeout_s
            while True:
                info = self.b.order_info(oid)
                if info["status"] in ("COMPLETE", "REJECTED", "CANCELLED") or self.now().timestamp() > deadline: break
                self.sleep(0.5)
            if info["status"] == "OPEN":
                try: self.b.cancel(oid)
                except Exception: pass
                info = self.b.order_info(oid)
            if info["filled"]: got += info["filled"]; cost += info["filled"] * info["avg"]
            if info["status"] == "REJECTED": self.log(f"order rejected: {symbol} {side}")
        return got, (cost / got if got else 0.0)

    def _quotes(self, syms):
        q = self.b.quotes(syms)
        return {s: dict(ltp=q[s]["ltp"], cover=(q[s]["ask"] or q[s]["ltp"])) for s in syms}

    def _close_legs(self, legs, qty, reason):
        self.log(f"EXITING both legs - reason: {reason}")
        ok = True
        for sym in legs:
            pos = next((p for p in self.b.positions() if p["symbol"] == sym), None)
            n = -pos["quantity"] if pos and pos["quantity"] < 0 else 0
            if n:
                g, avg = self._fill(sym, "BUY", n); self.log(f"bought back {g}/{n} {sym} @ {avg:.2f}"); ok &= g == n
        if not ok: self.log("!!! could not close everything - calling full square-off"); square_off_all(self.b, self.log, self.cfg.max_order_qty, self.cfg.order_buffer_pct, sleep=self.sleep)

    # ------------------------------------------------------------------ main flow
    def run(self):
        c = self.cfg
        if c.lots > c.max_lots: raise SystemExit(f"lots={c.lots} exceeds max_lots={c.max_lots} (raise max_lots deliberately if you mean it)")
        guard = self._guard_once_per_day()
        self.log(f"start | {'PAPER' if c.paper else '*** LIVE ***'} | lots={c.lots} SL={c.stop_loss_pct}% maxloss=Rs{c.max_daily_loss:.0f} entry={c.entry_time} exit={c.exit_time}")
        while self.now() < self._t(c.entry_time):
            if self._panic_requested(): self.log("PANIC before entry - nothing to close"); return self._finish("panic_before_entry")
            self.status = dict(state="waiting for entry"); self.sleep(1)
        if self.now() >= self._t(c.exit_time): return self._finish("too_late")
        spot = self.b.spot(c.spot_symbol); strike = int(round(spot / c.strike_step) * c.strike_step + c.strike_offset)
        pair = self.b.find_option_pair(c.underlying, strike, self.now().date())
        if c.expiry_only and pair.expiry != self.now().date(): self.log(f"not an expiry day (nearest expiry {pair.expiry}) - doing nothing"); return self._finish("not_expiry_day")
        qty = c.lots * pair.lot_size; legs = [pair.ce, pair.pe]
        self.log(f"spot {spot:.2f} -> strike {strike} | {pair.ce} / {pair.pe} | qty {qty} ({c.lots} lot x {pair.lot_size})")
        try:
            filled = {}
            for sym in legs:
                if self._panic_requested(): raise KeyboardInterrupt
                g, avg = self._fill(sym, "SELL", qty); filled[sym] = (g, avg); self.log(f"sold {g}/{qty} {sym} @ {avg:.2f}")
                if g != qty:
                    self.log("entry incomplete - unwinding and stopping"); self._close_legs([s for s in filled if filled[s][0]], qty, "entry incomplete")
                    self._write(guard, dict(result="entry_failed")); return self._finish("entry_failed")
            entry = sum(a for _, a in filled.values()); self._write(guard, dict(entry=entry, strike=strike, legs=legs, qty=qty))
            stop_level = entry * (1 + c.stop_loss_pct / 100); self.log(f"ENTRY combined premium {entry:.2f} | STOP-LOSS when buy-back >= {stop_level:.2f} | max loss Rs{c.max_daily_loss:.0f}")
            bad_polls = 0
            while True:
                if self._panic_requested():
                    self.log("!!! PANIC !!! cancelling all orders and closing ALL positions"); ok = square_off_all(self.b, self.log, c.max_order_qty, c.order_buffer_pct, sleep=self.sleep)
                    return self._finish("panic" if ok else "panic_NOT_FLAT")
                if self.now() >= self._t(c.exit_time): self._close_legs(legs, qty, "time exit"); return self._finish("time_exit")
                try: q = self._quotes(legs); bad_polls = 0
                except Exception as e:
                    bad_polls += 1; self.log(f"quote error ({bad_polls}): {e}")
                    if bad_polls >= 10: self._close_legs(legs, qty, "no market data (fail-safe)"); return self._finish("data_failsafe")
                    self.sleep(c.poll_seconds); continue
                cover = sum(v["cover"] for v in q.values()); mtm = (entry - cover) * qty
                self.status = dict(state="in trade", strike=strike, entry=round(entry, 2), buy_back_now=round(cover, 2), stop_at=round(stop_level, 2), mtm=round(mtm, 2), time=self.now().strftime("%H:%M:%S"))
                if cover >= stop_level: self._close_legs(legs, qty, f"STOP-LOSS hit ({cover:.2f} >= {stop_level:.2f})"); return self._finish("stop_loss")
                if mtm <= -c.max_daily_loss: self._close_legs(legs, qty, f"MAX DAILY LOSS (Rs{mtm:.0f})"); return self._finish("max_daily_loss")
                self.sleep(c.poll_seconds)
        except BaseException as e:                                       # ANY crash / Ctrl+C -> try to leave the account flat
            self.log(f"!!! {type(e).__name__}: {e} - emergency square-off"); square_off_all(self.b, self.log, c.max_order_qty, c.order_buffer_pct, sleep=self.sleep)
            self._finish("emergency_squareoff"); raise

    def _finish(self, why):
        pos = [p for p in self.b.positions() if p["quantity"] != 0]; self.result = dict(reason=why, open_positions=pos)
        self.log(f"DONE: {why} | open positions: {'NONE' if not pos else pos}"); self.status = dict(state="finished", reason=why); return self.result


def start_dashboard(bot: Bot, port: int):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            body = (PAGE if self.path == "/" else json.dumps(bot.status, indent=1)).encode(); self.send_response(200); self.send_header("Content-Type", "text/html" if self.path == "/" else "text/plain"); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            if self.path == "/panic": bot.panic.set(); self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    srv = HTTPServer(("127.0.0.1", port), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true"); ap.add_argument("--lots", type=int); ap.add_argument("--offset", type=int)
    ap.add_argument("--sl", type=float); ap.add_argument("--max-loss", type=float); ap.add_argument("--entry"); ap.add_argument("--exit"); ap.add_argument("--any-day", action="store_true"); ap.add_argument("--product")
    a = ap.parse_args(); cfg = Config(paper=not a.live)
    for k, v in (("lots", a.lots), ("strike_offset", a.offset), ("stop_loss_pct", a.sl), ("max_daily_loss", a.max_loss), ("entry_time", a.entry), ("exit_time", a.exit), ("product", a.product)):
        if v is not None: setattr(cfg, k, v)
    if a.any_day: cfg.expiry_only = False
    if not cfg.paper and input(f"LIVE MODE with REAL MONEY: {cfg.lots} lot(s), stop {cfg.stop_loss_pct}%. Type YES to continue: ") != "YES": sys.exit("aborted")
    bot = Bot(make_broker(cfg.paper, cfg.product, cfg.tag), cfg)
    signal.signal(signal.SIGINT, lambda *_: bot.panic.set())          # Ctrl+C = PANIC (square off), never "just die with positions open"
    start_dashboard(bot, cfg.dashboard_port); print(f"panic button: http://127.0.0.1:{cfg.dashboard_port}   |   or: touch PANIC   |   or: python panic.py   |   or Ctrl+C")
    r = bot.run(); sys.exit(0 if not r["open_positions"] else 2)


if __name__ == "__main__": main()
