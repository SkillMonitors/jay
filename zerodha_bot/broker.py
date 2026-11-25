"""Broker layer. KiteBroker talks to Zerodha. PaperBroker NEVER sends orders - it simulates fills from a quote source.
Both expose the same small interface so the strategy and the panic button don't care which one they use."""
import itertools, math, os
from datetime import date, datetime

TICK = 0.05


def round_tick(p: float, side: str) -> float:
    """Round to the 0.05 tick (up for BUY, down for SELL so the limit stays marketable); never below one tick."""
    n = p / TICK
    n = math.ceil(n - 1e-9) if side == "BUY" else math.floor(n + 1e-9)
    return max(round(n * TICK, 2), TICK)


class OptionPair:
    def __init__(self, ce, pe, lot_size, expiry, strike):
        self.ce, self.pe, self.lot_size, self.expiry, self.strike = ce, pe, lot_size, expiry, strike


class KiteBroker:
    """Real Zerodha Kite Connect. Needs: pip install kiteconnect, KITE_API_KEY and a fresh access token (run login.py each morning)."""

    def __init__(self, api_key: str, access_token: str, tag: str = "straddlebot", product: str = "MIS"):
        from kiteconnect import KiteConnect          # imported lazily so paper/mock mode needs no install
        self.kite = KiteConnect(api_key=api_key); self.kite.set_access_token(access_token)
        self.tag, self.product = tag, product
        self._inst = None

    # ---- market data
    def spot(self, symbol: str) -> float:
        return float(self.kite.ltp([symbol])[symbol]["last_price"])

    def _instruments(self):
        if self._inst is None: self._inst = self.kite.instruments("NFO")
        return self._inst

    def find_option_pair(self, underlying: str, strike: int, today: date) -> OptionPair:
        rows = [r for r in self._instruments() if r["name"] == underlying and r["instrument_type"] in ("CE", "PE") and r["expiry"] >= today and r["strike"] == strike]
        if not rows: raise RuntimeError(f"no {underlying} options found for strike {strike}")
        expiry = min(r["expiry"] for r in rows)
        ce = next(r for r in rows if r["expiry"] == expiry and r["instrument_type"] == "CE")
        pe = next(r for r in rows if r["expiry"] == expiry and r["instrument_type"] == "PE")
        return OptionPair(ce["tradingsymbol"], pe["tradingsymbol"], int(ce["lot_size"]), expiry, strike)

    def nearest_expiry(self, underlying: str, today: date) -> date:
        return min(r["expiry"] for r in self._instruments() if r["name"] == underlying and r["expiry"] >= today)

    def quotes(self, symbols):
        raw = self.kite.quote([f"NFO:{s}" for s in symbols]); out = {}
        for s in symbols:
            q = raw[f"NFO:{s}"]; d = q.get("depth", {}); bid = d.get("buy", [{}])[0].get("price") or 0; ask = d.get("sell", [{}])[0].get("price") or 0
            out[s] = dict(ltp=q["last_price"], bid=bid, ask=ask)
        return out

    # ---- orders
    def place(self, symbol, side, qty, price=None, order_type="LIMIT"):
        kw = dict(variety="regular", exchange="NFO", tradingsymbol=symbol, transaction_type=side, quantity=int(qty), product=self.product,
                  order_type=order_type, validity="DAY", tag=self.tag)
        if order_type == "LIMIT": kw["price"] = price
        if order_type == "MARKET": kw["market_protection"] = -1           # Zerodha now requires market protection on API market orders (-1 = automatic)
        return self.kite.place_order(**kw)

    def order_info(self, order_id):
        hist = self.kite.order_history(order_id)[-1]
        return dict(status=hist["status"], filled=int(hist.get("filled_quantity", 0)), avg=float(hist.get("average_price") or 0))

    def cancel(self, order_id):
        self.kite.cancel_order(variety="regular", order_id=order_id)

    def open_orders(self):
        return [o["order_id"] for o in self.kite.orders() if o["status"] in ("OPEN", "TRIGGER PENDING", "VALIDATION PENDING", "PUT ORDER REQ RECEIVED")]

    def positions(self):
        return [dict(symbol=p["tradingsymbol"], exchange=p["exchange"], quantity=int(p["quantity"]), product=p["product"], pnl=float(p.get("pnl", 0)))
                for p in self.kite.positions()["net"]]

    def day_pnl(self):
        """Today's profit/loss across ALL positions in the account (realised + unrealised). Uses Kite's m2m (day mark-to-market) when present, else pnl."""
        return float(sum(float(p.get("m2m", p.get("pnl", 0)) or 0) for p in self.kite.positions()["net"]))


class PaperBroker:
    """Simulated broker: fills instantly at the touch (BUY at ask, SELL at bid - conservative). Quote data comes from `source`
    (a KiteBroker for live quotes with fake orders, or a simulator in tests). It has NO connection to order placement."""

    def __init__(self, source, product="MIS"):
        self.src, self.product = source, product
        self._ids = itertools.count(1); self.orders = {}; self.pos = {}; self.placed_log = []
        self.live_orders_sent = 0                                         # must always stay 0

    def spot(self, symbol): return self.src.spot(symbol)
    def find_option_pair(self, *a, **k): return self.src.find_option_pair(*a, **k)
    def nearest_expiry(self, *a, **k): return self.src.nearest_expiry(*a, **k)
    def quotes(self, symbols): return self.src.quotes(symbols)

    def place(self, symbol, side, qty, price=None, order_type="LIMIT"):
        q = self.src.quotes([symbol])[symbol]; ask = q["ask"] or q["ltp"]; bid = q["bid"] or q["ltp"]
        fill = ask if side == "BUY" else bid
        ok = order_type == "MARKET" or (side == "BUY" and price >= fill) or (side == "SELL" and price <= fill)
        oid = f"PAPER{next(self._ids)}"
        if ok:
            sign = 1 if side == "BUY" else -1; p = self.pos.setdefault(symbol, dict(qty=0, cash=0.0)); p["qty"] += sign * int(qty); p["cash"] -= sign * int(qty) * fill
            self.orders[oid] = dict(status="COMPLETE", filled=int(qty), avg=fill)
        else: self.orders[oid] = dict(status="OPEN", filled=0, avg=0.0)
        self.placed_log.append((symbol, side, int(qty), price, order_type, self.orders[oid]["status"])); return oid

    def order_info(self, oid): return dict(self.orders[oid])
    def cancel(self, oid):
        if self.orders[oid]["status"] == "OPEN": self.orders[oid]["status"] = "CANCELLED"
    def open_orders(self): return [o for o, d in self.orders.items() if d["status"] == "OPEN"]
    def day_pnl(self): return float(sum(p["pnl"] for p in self.positions()))
    def positions(self):
        try: qs = self.src.quotes([s for s in self.pos]) if self.pos else {}
        except Exception: qs = {}                                         # real Kite positions() does not depend on the quote feed either
        return [dict(symbol=s, exchange="NFO", quantity=p["qty"], product=self.product, pnl=p["cash"] + p["qty"] * (qs[s]["ltp"] if s in qs else 0.0)) for s, p in self.pos.items()]


def make_broker(paper: bool, product: str, tag: str):
    """Paper mode: real quotes if Kite credentials exist (data plan required), else refuses (use the simulator in tests)."""
    key, tok = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_ACCESS_TOKEN")
    if not key or not tok: raise SystemExit("Set KITE_API_KEY and KITE_ACCESS_TOKEN (run login.py first). Never paste them into a chat.")
    if not paper and os.environ.get("LIVE_TRADING") != "YES_I_UNDERSTAND_THIS_USES_REAL_MONEY":
        raise SystemExit("Live mode refused: set LIVE_TRADING=YES_I_UNDERSTAND_THIS_USES_REAL_MONEY to confirm.")
    real = KiteBroker(key, tok, tag, product)
    return PaperBroker(real, product) if paper else real
