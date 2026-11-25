"""Nifty EXPIRY-DAY iron-butterfly bot for Zerodha, with a hard stop-loss and a panic button. PAPER MODE IS THE DEFAULT.

  python bot.py                 paper: real quotes (needs Kite data plan), FAKE orders, results in logs/paper_journal.csv
  python demo.py                no Zerodha needed: runs a simulated expiry day so you can see the logic and the panic button work
  python bot.py --live          real orders (refused unless LIVE_TRADING=YES_I_UNDERSTAND_THIS_USES_REAL_MONEY is set)

Trade (per set = lots_per_set lots of EVERY leg):  BUY the two wings first (call K+W, put K-W), then SELL the at-the-money call and put at K.
Exit ALL legs (shorts bought back first, then wings sold) on the FIRST of:
  * cost-to-close rises by stop_loss_pct of the premium collected on the short legs      -> STOP-LOSS
  * mark-to-market loss >= max_daily_loss                                               -> MAX-LOSS
  * clock reaches exit_time (default 15:15)                                              -> TIME EXIT
  * PANIC: dashboard button / `touch PANIC` / panic.py / Ctrl+C                          -> cancel all orders, close ALL positions
  * quotes stop arriving                                                                -> FAIL-SAFE exit
If an entry order fails part-way, everything already bought/sold is closed at once and the bot stops."""
import argparse, csv, json, os, signal, sys, threading, time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from zoneinfo import ZoneInfo
from broker import make_broker
from config import Config
from squareoff import square_off_all, _marketable

IST = ZoneInfo("Asia/Kolkata")
PAGE = """<!doctype html><meta charset=utf-8><title>Iron fly bot</title><body style="font-family:system-ui;max-width:560px;margin:40px auto;text-align:center">
<h2>Iron fly bot</h2><pre id=s style="text-align:left;background:#f4f4f4;padding:12px;border-radius:8px">loading...</pre>
<button onclick="fetch('/panic',{method:'POST'}).then(()=>document.getElementById('m').innerText='PANIC SENT - cancelling orders and closing all positions')"
 style="font-size:32px;padding:24px 48px;background:#c62828;color:#fff;border:0;border-radius:12px;cursor:pointer">PANIC - EXIT ALL</button><p id=m></p>
<script>setInterval(()=>fetch('/status').then(r=>r.text()).then(t=>document.getElementById('s').innerText=t),1500)</script></body>"""


class Bot:
    def __init__(self, broker, cfg: Config, now_fn=None, sleep_fn=time.sleep, log=None, journal="logs/paper_journal.csv"):
        self.b, self.cfg, self.sleep, self.journal = broker, cfg, sleep_fn, journal
        self.now = now_fn or (lambda: datetime.now(IST)); self.panic = threading.Event(); self.status = dict(state="idle")
        os.makedirs(cfg.state_dir, exist_ok=True); os.makedirs(os.path.dirname(journal) or ".", exist_ok=True)
        self._log = log or (lambda m: print(m, flush=True)); self.result = None

    # ------------------------------------------------------------------ utilities
    def log(self, msg):
        line = f"{self.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"; self._log(line)
        try:
            with open(os.path.join(os.path.dirname(self.journal) or ".", f"{self.now().date()}.log"), "a") as f: f.write(line + "\n")
        except OSError: pass

    @staticmethod
    def _write(path, obj):
        with open(path, "w") as f: json.dump(obj, f)

    def _t(self, hhmm): h, m = map(int, hhmm.split(":")); return self.now().replace(hour=h, minute=m, second=0, microsecond=0)

    def _panic_requested(self):
        if os.path.exists("PANIC"):
            try: os.remove("PANIC")
            except OSError: pass
            self.panic.set()
        return self.panic.is_set()

    def _account_limit(self): return self.cfg.capital * self.cfg.max_daily_loss_pct / 100

    def _account_breached(self):
        """True if the WHOLE account's loss today has reached max_daily_loss_pct of capital."""
        try: d = self.b.day_pnl()
        except Exception as e: self.log(f"day P&L check failed: {e}"); return False
        self.status["account_day_pnl"] = round(d)
        if d <= -self._account_limit():
            self.log(f"!!! ACCOUNT DAILY LOSS LIMIT HIT: day P&L Rs{d:,.0f} <= -Rs{self._account_limit():,.0f} ({self.cfg.max_daily_loss_pct}% of Rs{self.cfg.capital:,.0f}) - CLOSING ALL POSITIONS")
            return True
        return False

    def _lockfile(self): return os.path.join(self.cfg.state_dir, f"locked_{self.now().date()}")

    def _guard_once_per_day(self):
        f = os.path.join(self.cfg.state_dir, f"traded_{self.now().date()}.json")
        if os.path.exists(f): raise SystemExit(f"Already traded today ({f}). Delete it only if you are sure no position is open.")
        return f

    # ------------------------------------------------------------------ orders
    def _fill(self, symbol, side, qty, closing=False):
        """Marketable LIMIT orders with widening price; closing orders end with a MARKET order. Returns (filled_qty, avg_price)."""
        got, cost = 0, 0.0
        for k in range(1, self.cfg.exit_retries + 1):
            need = qty - got
            if need <= 0: break
            try: q = self.b.quotes([symbol])[symbol]
            except Exception: q = None                                               # feed down: still get out with a MARKET order
            market = closing and (k == self.cfg.exit_retries or q is None)
            oid = self.b.place(symbol, side, need, order_type="MARKET") if market else self.b.place(symbol, side, need, price=_marketable(side, q, self.cfg.order_buffer_pct * k), order_type="LIMIT")
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
            if info["status"] == "REJECTED": self.log(f"order rejected: {symbol} {side}"); break
        return got, (cost / got if got else 0.0)

    def _quotes(self, syms):
        q = self.b.quotes(syms)
        return {s: dict(ltp=q[s]["ltp"], ask=(q[s]["ask"] or q[s]["ltp"]), bid=(q[s]["bid"] or q[s]["ltp"])) for s in syms}

    def _close_all(self, shorts, longs, reason):
        """Buy back the SHORT legs first, only then sell the wings (never leave a naked short in the middle of an exit)."""
        self.log(f"EXITING all legs - reason: {reason}"); ok = True
        for sym in shorts:
            pos = next((p for p in self.b.positions() if p["symbol"] == sym), None); n = -pos["quantity"] if pos and pos["quantity"] < 0 else 0
            if n: g, a = self._fill(sym, "BUY", n, closing=True); self.log(f"bought back {g}/{n} {sym} @ {a:.2f}"); ok &= g == n
        for sym in longs:
            pos = next((p for p in self.b.positions() if p["symbol"] == sym), None); n = pos["quantity"] if pos and pos["quantity"] > 0 else 0
            if n: g, a = self._fill(sym, "SELL", n, closing=True); self.log(f"sold wing {g}/{n} {sym} @ {a:.2f}"); ok &= g == n
        if not ok: self.log("!!! could not close everything - calling full square-off"); square_off_all(self.b, self.log, self.cfg.max_order_qty, self.cfg.order_buffer_pct, sleep=self.sleep)

    # ------------------------------------------------------------------ main flow
    def run(self):
        c = self.cfg
        if c.sets > c.max_sets: raise SystemExit(f"sets={c.sets} exceeds max_sets={c.max_sets} (raise max_sets deliberately if you mean it)")
        guard = self._guard_once_per_day()
        if os.path.exists(self._lockfile()) or self._account_breached(): return self._finish("account_loss_limit_already_hit", [], [], 0)    # no new trades after the limit was hit today
        self.log(f"start | account daily-loss limit Rs{self._account_limit():,.0f} ({c.max_daily_loss_pct}% of Rs{c.capital:,.0f}) | {'PAPER' if c.paper else '*** LIVE ***'} | {c.sets} set(s) x {c.lots_per_set} lots | wings {c.wing_style} {c.wing_points} | stop {c.stop_loss_pct}% | max loss Rs{c.max_daily_loss:.0f} | entry {c.entry_time} exit {c.exit_time}")
        while self.now() < self._t(c.entry_time):
            if self._panic_requested(): self.log("PANIC before entry - nothing to close"); return self._finish("panic_before_entry", [], [], 0)
            self.status = dict(state="waiting for entry"); self.sleep(1)
        if self.now() >= self._t(c.exit_time): return self._finish("too_late", [], [], 0)
        spot = self.b.spot(c.spot_symbol); K = int(round(spot / c.strike_step) * c.strike_step); W = c.wing_points
        atm = self.b.find_option_pair(c.underlying, K, self.now().date())
        if c.expiry_only and atm.expiry != self.now().date(): self.log(f"not an expiry day (nearest expiry {atm.expiry}) - doing nothing"); return self._finish("not_expiry_day", [], [], 0)
        shorts = [atm.ce, atm.pe]; longs = []
        if W > 0:
            up, dn = self.b.find_option_pair(c.underlying, K + W, self.now().date()), self.b.find_option_pair(c.underlying, K - W, self.now().date())
            longs = [up.ce, dn.pe] if c.wing_style == "otm" else [dn.ce, up.pe]
        qty = c.sets * c.lots_per_set * atm.lot_size
        self.log(f"spot {spot:.2f} -> centre {K} | SELL {shorts} | BUY {longs} | qty {qty} per leg ({c.sets} set x {c.lots_per_set} lots x {atm.lot_size})")
        try:
            sold, bought = {}, {}
            for sym in longs:                                                       # wings FIRST: risk is capped before any short is sold
                if self._panic_requested(): raise KeyboardInterrupt
                g, a = self._fill(sym, "BUY", qty); bought[sym] = (g, a); self.log(f"bought wing {g}/{qty} {sym} @ {a:.2f}")
                if g != qty: return self._abort_entry(guard, shorts, longs, qty)
            for sym in shorts:
                if self._panic_requested(): raise KeyboardInterrupt
                g, a = self._fill(sym, "SELL", qty); sold[sym] = (g, a); self.log(f"sold {g}/{qty} {sym} @ {a:.2f}")
                if g != qty: return self._abort_entry(guard, shorts, longs, qty)
            gross = sum(a for _, a in sold.values()); v0 = gross - sum(a for _, a in bought.values())       # v0 = net credit = what closing would cost right now (points)
            stop_level = v0 + c.stop_loss_pct / 100 * gross; entry_time = self.now()
            self._write(guard, dict(v0=v0, gross=gross, K=K, shorts=shorts, longs=longs, qty=qty))
            self.log(f"ENTRY net credit {v0:.2f} pts (Rs{v0*qty:,.0f}) | gross short premium {gross:.2f} | STOP when cost-to-close >= {stop_level:.2f} | max loss Rs{c.max_daily_loss:.0f}")
            bad = 0; syms = shorts + longs; last_acct = self.now().timestamp()
            while True:
                if self.now().timestamp() - last_acct >= c.account_check_seconds:
                    last_acct = self.now().timestamp()
                    if self._account_breached():
                        open(self._lockfile(), "w").close(); ok = square_off_all(self.b, self.log, c.max_order_qty, c.order_buffer_pct, sleep=self.sleep)
                        return self._finish("account_loss_limit" if ok else "account_loss_limit_NOT_FLAT", shorts, longs, qty, K, v0, entry_time)
                if self._panic_requested():
                    self.log("!!! PANIC !!! cancelling all orders and closing ALL positions"); ok = square_off_all(self.b, self.log, c.max_order_qty, c.order_buffer_pct, sleep=self.sleep)
                    return self._finish("panic" if ok else "panic_NOT_FLAT", shorts, longs, qty, K, v0, entry_time)
                if self.now() >= self._t(c.exit_time): self._close_all(shorts, longs, "time exit"); return self._finish("time_exit", shorts, longs, qty, K, v0, entry_time)
                try: q = self._quotes(syms); bad = 0
                except Exception as e:
                    bad += 1; self.log(f"quote error ({bad}): {e}")
                    if bad >= 10: self._close_all(shorts, longs, "no market data (fail-safe)"); return self._finish("data_failsafe", shorts, longs, qty, K, v0, entry_time)
                    self.sleep(c.poll_seconds); continue
                value = sum(q[s]["ask"] for s in shorts) - sum(q[s]["bid"] for s in longs); mtm = (v0 - value) * qty
                self.status = dict(state="in trade", centre=K, net_credit=round(v0, 2), cost_to_close=round(value, 2), stop_at=round(stop_level, 2), mtm_rs=round(mtm), time=self.now().strftime("%H:%M:%S"))
                if value >= stop_level: self._close_all(shorts, longs, f"STOP-LOSS hit ({value:.2f} >= {stop_level:.2f})"); return self._finish("stop_loss", shorts, longs, qty, K, v0, entry_time)
                if mtm <= -c.max_daily_loss: self._close_all(shorts, longs, f"MAX DAILY LOSS (Rs{mtm:.0f})"); return self._finish("max_daily_loss", shorts, longs, qty, K, v0, entry_time)
                self.sleep(c.poll_seconds)
        except BaseException as e:                                       # ANY crash / Ctrl+C -> try to leave the account flat
            self.log(f"!!! {type(e).__name__}: {e} - emergency square-off"); square_off_all(self.b, self.log, c.max_order_qty, c.order_buffer_pct, sleep=self.sleep)
            self._finish("emergency_squareoff", shorts, longs, qty, K); raise

    def _abort_entry(self, guard, shorts, longs, qty):
        self.log("entry incomplete - closing whatever was filled and stopping"); self._close_all(shorts, longs, "entry incomplete")
        self._write(guard, dict(result="entry_failed")); return self._finish("entry_failed", shorts, longs, qty)

    def _finish(self, why, shorts, longs, qty, K=None, v0=None, entry_time=None):
        pos = [p for p in self.b.positions() if p["quantity"] != 0]; mine = [p for p in self.b.positions() if p["symbol"] in shorts + longs]
        gross = sum(p["pnl"] for p in mine) if mine else 0.0; sets = self.cfg.sets if v0 is not None else 0; cost = self.cfg.est_cost_per_set * sets
        self.result = dict(reason=why, open_positions=pos, gross_pnl=round(gross, 2), est_net_pnl=round(gross - cost, 2))
        self.log(f"DONE: {why} | gross P&L Rs{gross:,.0f} | est. net after Rs{cost:,.0f} costs Rs{gross - cost:,.0f} | open positions: {'NONE' if not pos else pos}")
        if v0 is not None:
            new = not os.path.exists(self.journal)
            with open(self.journal, "a", newline="") as f:
                w = csv.writer(f)
                if new: w.writerow(["date", "mode", "centre", "sets", "qty_per_leg", "net_credit_pts", "reason", "entry_time", "exit_time", "gross_pnl", "est_cost", "est_net_pnl"])
                w.writerow([self.now().date(), "PAPER" if self.cfg.paper else "LIVE", K, sets, qty, round(v0, 2), why, entry_time.strftime("%H:%M:%S") if entry_time else "", self.now().strftime("%H:%M:%S"), round(gross, 2), cost, round(gross - cost, 2)])
        self.status = dict(state="finished", reason=why, gross_pnl=round(gross)); return self.result


def start_dashboard(bot: Bot, port: int):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            body = (PAGE if self.path == "/" else json.dumps(bot.status, indent=1)).encode(); self.send_response(200); self.send_header("Content-Type", "text/html" if self.path == "/" else "text/plain"); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            if self.path == "/panic": bot.panic.set(); self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    srv = HTTPServer(("127.0.0.1", port), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true"); ap.add_argument("--sets", type=int); ap.add_argument("--wing", type=int); ap.add_argument("--style", choices=["otm", "itm"])
    ap.add_argument("--sl", type=float); ap.add_argument("--max-loss", type=float); ap.add_argument("--entry"); ap.add_argument("--exit"); ap.add_argument("--any-day", action="store_true"); ap.add_argument("--product")
    a = ap.parse_args(); cfg = Config(paper=not a.live)
    for k, v in (("sets", a.sets), ("wing_points", a.wing), ("wing_style", a.style), ("stop_loss_pct", a.sl), ("max_daily_loss", a.max_loss), ("entry_time", a.entry), ("exit_time", a.exit), ("product", a.product)):
        if v is not None: setattr(cfg, k, v)
    if a.any_day: cfg.expiry_only = False
    if not cfg.paper and input(f"LIVE MODE with REAL MONEY: {cfg.sets} set(s), stop {cfg.stop_loss_pct}%. Type YES to continue: ") != "YES": sys.exit("aborted")
    bot = Bot(make_broker(cfg.paper, cfg.product, cfg.tag), cfg)
    signal.signal(signal.SIGINT, lambda *_: bot.panic.set())          # Ctrl+C = PANIC (square off), never "just die with positions open"
    start_dashboard(bot, cfg.dashboard_port); print(f"panic button: http://127.0.0.1:{cfg.dashboard_port}   |   or: touch PANIC   |   or: python panic.py   |   or Ctrl+C")
    r = bot.run(); sys.exit(0 if not r["open_positions"] else 2)


if __name__ == "__main__": main()
