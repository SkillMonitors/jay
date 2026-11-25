"""THE PANIC BUTTON LOGIC. Cancels every open order, then closes every open position (shorts bought back first so margin is released),
retries until the account is flat, and reports what it did. Used by panic.py, the dashboard button, the PANIC file and Ctrl+C."""
import time


def _chunks(qty, size):
    while qty > 0: yield min(qty, size); qty -= size


def _marketable(side, q, buf):
    p = (q["ask"] or q["ltp"]) * (1 + buf / 100) if side == "BUY" else (q["bid"] or q["ltp"]) * (1 - buf / 100)
    from broker import round_tick
    return round_tick(p, side)


def square_off_all(broker, log=print, max_qty=1800, buffer_pct=1.0, retries=5, wait=2.0, sleep=time.sleep):
    """Returns True only if the account is verified flat (no open orders, no open positions)."""
    for attempt in range(1, retries + 1):
        # 1) cancel working orders so they cannot fill after we flatten
        for oid in broker.open_orders():
            try: broker.cancel(oid); log(f"[panic] cancelled order {oid}")
            except Exception as e: log(f"[panic] cancel failed {oid}: {e}")
        # 2) close SHORTS first. Longs (e.g. hedge legs) are sold only once every short is confirmed closed,
        #    otherwise a hedged position would be left naked in the middle of a panic.
        pos = [p for p in broker.positions() if p["quantity"] != 0]
        if not pos: log("[panic] verified FLAT - no open positions"); return True
        shorts = [p for p in pos if p["quantity"] < 0]; longs = [p for p in pos if p["quantity"] > 0]; last = attempt == retries
        def send(p):
            side = "BUY" if p["quantity"] < 0 else "SELL"; qty = abs(p["quantity"])
            try: q = broker.quotes([p["symbol"]])[p["symbol"]]
            except Exception: q = dict(ltp=0, bid=0, ask=0)
            for c in _chunks(qty, max_qty):
                try:
                    if last or not q["ltp"]: oid = broker.place(p["symbol"], side, c, order_type="MARKET")      # final attempt: market order, price is no object
                    else: oid = broker.place(p["symbol"], side, c, price=_marketable(side, q, buffer_pct * attempt), order_type="LIMIT")
                    log(f"[panic] {side} {c} {p['symbol']} (attempt {attempt}) -> {oid}")
                except Exception as e: log(f"[panic] order FAILED {p['symbol']} {side} {c}: {e}")
        for p in shorts: send(p)
        if shorts:
            sleep(wait / 2)
            if any(p["quantity"] < 0 for p in broker.positions()) and not last: log("[panic] shorts not all closed yet - holding hedge legs, retrying"); sleep(wait / 2); continue
        for p in longs: send(p)
        sleep(wait)
    remaining = [p for p in broker.positions() if p["quantity"] != 0]
    if remaining: log(f"[panic] !!! STILL OPEN after {retries} attempts: {remaining} - CLOSE MANUALLY in the Kite app NOW")
    else: log("[panic] verified FLAT")
    return not remaining
