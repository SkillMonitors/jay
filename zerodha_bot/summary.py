"""Summarise your PAPER trading journal: python summary.py   (reads logs/paper_journal.csv). Compare with the backtest (~Rs2,700 net per set per expiry, 53-58% wins)."""
import csv, sys
path = sys.argv[1] if len(sys.argv) > 1 else "logs/paper_journal.csv"
try:
    with open(path) as f: rows = list(csv.DictReader(f))
except FileNotFoundError: sys.exit("No journal yet - run `python bot.py` on an expiry day first.")
net = [float(r["est_net_pnl"]) for r in rows]; sets = [int(r["sets"]) for r in rows]; per_set = [n / s for n, s in zip(net, sets)]
w = sum(1 for n in net if n > 0); eq = 0; peak = 0; dd = 0
for n in net: eq += n; peak = max(peak, eq); dd = min(dd, eq - peak)
print(f"{len(rows)} expiry days | wins {w} ({100*w/len(rows):.0f}%) | stop-loss {sum(r['reason']=='stop_loss' for r in rows)} | panic {sum(r['reason'].startswith('panic') for r in rows)} | total est. net Rs{sum(net):,.0f} | avg per set per expiry Rs{sum(per_set)/len(rows):,.0f} | worst day Rs{min(net):,.0f} | worst fall from a peak Rs{dd:,.0f}")
print("Backtest said ~Rs2,700 per set per expiry. If your paper average is much lower, real spreads/slippage are eating the edge - do NOT go live.")
