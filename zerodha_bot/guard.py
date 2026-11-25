"""ACCOUNT LOSS GUARD (kill switch). Run it in a second terminal next to the bot - or on its own to protect manual trades too.
If your TOTAL loss for the day (all positions, realised + unrealised) reaches max_daily_loss_pct (default 2%) of `capital`, it cancels all orders and closes ALL positions,
then (lockout) keeps watching until 15:30 and closes anything you open afterwards.
    python guard.py                         # uses capital / pct from config.py
    python guard.py --capital 1000000 --pct 2 --no-lockout"""
import argparse, os, sys, time
from datetime import datetime
from zoneinfo import ZoneInfo
from config import Config
from squareoff import square_off_all

IST = ZoneInfo("Asia/Kolkata")


def watch(broker, limit, now_fn=lambda: datetime.now(IST), sleep_fn=time.sleep, end_hhmm="15:30", poll=5.0, lockout=True, log=print, max_qty=1800):
    h, m = map(int, end_hhmm.split(":")); tripped = False; fails = 0
    while now_fn() < now_fn().replace(hour=h, minute=m, second=0, microsecond=0):
        try: d = broker.day_pnl(); fails = 0
        except Exception as e:
            fails += 1; log(f"[guard] day P&L check failed ({fails}): {e}")
            if fails in (3, 10): log("[guard] !!! cannot read P&L - you are NOT protected; watch your positions manually")
            sleep_fn(poll); continue
        if not tripped and d <= -limit:
            log(f"[guard] !!! DAY LOSS Rs{d:,.0f} reached the limit -Rs{limit:,.0f} - CLOSING ALL POSITIONS"); square_off_all(broker, log, max_qty, sleep=sleep_fn); tripped = True
        elif tripped and lockout and any(p["quantity"] != 0 for p in broker.positions()):
            log("[guard] LOCKOUT: new position opened after the limit was hit - closing it"); square_off_all(broker, log, max_qty, sleep=sleep_fn)
        sleep_fn(poll)
    return tripped


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--capital", type=float); ap.add_argument("--pct", type=float); ap.add_argument("--no-lockout", action="store_true"); a = ap.parse_args()
    cfg = Config(); cap = a.capital or cfg.capital; pct = a.pct or cfg.max_daily_loss_pct
    key, tok = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_ACCESS_TOKEN")
    if not key or not tok: sys.exit("Set KITE_API_KEY and KITE_ACCESS_TOKEN first (run login.py).")
    from broker import KiteBroker
    broker = KiteBroker(key, tok); limit = cap * pct / 100
    print(f"guard running: will close ALL positions if the day's loss reaches Rs{limit:,.0f} ({pct}% of Rs{cap:,.0f}). Ctrl+C stops the guard (it does not close positions).")
    watch(broker, limit, lockout=not a.no_lockout)
