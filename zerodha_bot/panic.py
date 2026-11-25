"""STANDALONE PANIC BUTTON.  python panic.py        -> asks you to type PANIC, then cancels all orders and closes ALL positions in your account.
                           python panic.py --yes  -> no question asked (use from a shortcut / second terminal).
Works even if the bot has crashed. Reads KITE_API_KEY / KITE_ACCESS_TOKEN from the environment (see .env.example)."""
import os, sys, time
from broker import KiteBroker
from squareoff import square_off_all


def main():
    key, tok = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_ACCESS_TOKEN")
    if not key or not tok: sys.exit("Set KITE_API_KEY and KITE_ACCESS_TOKEN first (run login.py).")
    broker = KiteBroker(key, tok)
    pos = [p for p in broker.positions() if p["quantity"] != 0]
    print("Open positions:", *([f"\n  {p['symbol']}: {p['quantity']} ({p['product']}) P&L {p['pnl']:.0f}" for p in pos] or ["none"]))
    if "--yes" not in sys.argv and input("\nType PANIC to cancel all orders and close everything: ").strip() != "PANIC": sys.exit("Cancelled - nothing done.")
    ok = square_off_all(broker, log=lambda m: print(time.strftime("%H:%M:%S"), m))
    sys.exit(0 if ok else 2)


if __name__ == "__main__": main()
