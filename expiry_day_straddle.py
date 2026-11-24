"""Sell ATM straddle at the OPEN on EXPIRY DAY ONLY, exit at the close (expiry), stop-loss = X% of the combined premium. Last 10 years. Modelled prices (see intraday_straddle.py)."""
import numpy as np, pandas as pd, itertools
from intraday_straddle import *
rs = {}
for sl in (10, 20, 30, None):
    r = run(sl, "short"); r = r[r.dte == 0].copy(); r["yr"] = r.date.dt.year; rs[sl] = r
def show2(r, name):
    x = r.pnl; w = (x > 0).sum(); eq = x.cumsum(); dd = (eq - eq.cummax()).min()
    print(f"  {name:16s} {len(x):3d} expiry days | WIN {w:3d} ({100*w/len(x):.0f}%) LOSE {len(x)-w:3d} ({100*(len(x)-w)/len(x):.0f}%) | SL hit {100*r.hit.mean():.0f}% | avg win Rs{x[x>0].mean():,.0f} avg loss Rs{x[x<=0].mean():,.0f} | TOTAL Rs{x.sum():>9,.0f} | best Rs{x.max():,.0f} worst Rs{x.min():,.0f} | max drawdown Rs{dd:,.0f}")
r10 = rs[10]; print(f"{r10.date.min().date()} -> {r10.date.max().date()}: {len(r10)} expiry days ({(r10.date < '2019-02-25').sum()} monthly-only expiries before Feb-2019, then weekly)\n")
for sl, r in rs.items(): show2(r, f"stop {sl}%" if sl else "no stop")
print("\n=== 10% stop-loss, by year ==="); g = r10.groupby("yr").agg(expiries=("pnl", "size"), win=("pnl", "sum"), wins=("pnl", lambda x: (x > 0).sum()), sl_hit=("hit", lambda x: round(100*x.mean())), total=("pnl", lambda x: round(x.sum())), worst=("pnl", lambda x: round(x.min()))).drop(columns="win"); print(g.to_string())
print(f"\navg premium at the open: {r10.prem_pct.mean():.2f}% of spot = Rs{(r10.prem*75).mean():,.0f} per lot | a 10% stop = Rs{(r10.prem*0.1*75).mean():,.0f} | costs assumed Rs400/day")
print("longest losing streak:", max((len(list(g_)) for k, g_ in itertools.groupby(r10.pnl <= 0) if k), default=0), "expiries | worst 3:", r10.nsmallest(3, "pnl")[["date", "pnl"]].assign(date=lambda x: x.date.dt.date).round(0).values.tolist())
for c in (0, 200, 400, 800):
    x = r10.pts * 75 - c; print(f"  with cost Rs{c:>3}/expiry: total Rs{x.sum():>9,.0f}  win {100*(x>0).mean():.0f}%")
h = hourly_check(10); ex = {d for d in exs}; h = h[h.date.isin(ex)]; dd = r10[r10.date >= h.date.min()]
print(f"\nCheck on real hourly paths ({h.date.min().date()} -> {h.date.max().date()}, {len(h)} expiry days): hourly win {100*(h.pnl>0).mean():.0f}%, total Rs{h.pnl.sum():,.0f} | daily-approx same period win {100*(dd.pnl>0).mean():.0f}%, total Rs{dd.pnl.sum():,.0f}")
r10.to_csv("expiry_day_straddle_10pct.csv", index=False)
