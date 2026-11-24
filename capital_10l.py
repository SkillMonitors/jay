"""Rs10 lakh capital: 2-lot iron butterfly (200-pt wings, 130 qty = 1 'set'), EVERY expiry day, 10% stop, exit by ~3:15 pm. N sets per expiry. MODELLED prices, cost Rs800/set/expiry, lot 65 held constant."""
import numpy as np, pandas as pd
import hedged_straddle as H
src = open("expiry_fly_last_year.py").read().split("end = D.index[-1]")[0]; exec(src)       # day_run (real hourly path), uses H.LOT=130, H.COST=800
from intraday_straddle import D
CAP = 1_000_000; end = D.index[-1]; v3 = H.VAR["V3: iron fly (1 straddle + 1 wing pair)"]
daily = H.run_daily(v3, 10, years=10); daily["date"] = pd.to_datetime(daily["date"])
real = day_run(10, 6 / 6.25)
def block(r, years, label):
    r = r[r.date > end - pd.DateOffset(years=years)]; x = r.pnl; eq = x.cumsum(); dd = (eq - eq.cummax()).min(); yr = (r.date.iloc[-1] - r.date.iloc[0]).days / 365.25
    print(f"\n{label}: {len(r)} expiries over {yr:.1f} yrs | win {100*(x>0).mean():.0f}% | per SET: total Rs{x.sum():,.0f} (Rs{x.sum()/yr:,.0f}/yr) | worst day Rs{x.min():,.0f} | worst fall from a peak Rs{dd:,.0f}")
    print(f"   {'sets':>5s} {'lots':>5s} {'profit':>12s} {'= % of 10L':>11s} {'per year':>11s} {'worst day':>10s} {'worst fall':>11s} {'= % of 10L':>11s}")
    for n in (5, 10, 15):
        print(f"   {n:5d} {2*n:5d} Rs{x.sum()*n:>10,.0f} {100*x.sum()*n/CAP:9.0f}% Rs{x.sum()*n/yr:>9,.0f} Rs{x.min()*n:>8,.0f} Rs{dd*n:>9,.0f} {100*dd*n/CAP:9.0f}%")
    return r
print("A) DAILY-RANGE MODEL, hold to close (3:30), expiry days only"); r6 = block(daily, 6, "last 6 years"); r5 = block(daily, 5, "last 5 years")
r = r6.copy(); r["yr"] = r.date.dt.year; print("\n   10 sets by calendar year (A):"); print((r.groupby("yr").pnl.sum() * 10).round().astype(int).to_string())
print("\nB) REAL HOURLY PATH (about 3 years, exit 3:15 pm)"); b3 = block(real, 3, "last ~3 years")
# rolling worst/best 12 months (A), per set
s = daily.set_index("date").pnl; roll = s.rolling("365D").sum(); print(f"\nRolling 12-month profit per set (A, 2016+): min Rs{roll.min():,.0f} | median Rs{roll.median():,.0f} | max Rs{roll.max():,.0f}  -> with 10 sets: Rs{roll.min()*10:,.0f} / Rs{roll.median()*10:,.0f} / Rs{roll.max()*10:,.0f}")
# 6-year projection for 10 sets: scenarios
pa = r6.pnl.sum() / 6 * 10; pb = b3.pnl.sum() / ((b3.date.iloc[-1] - b3.date.iloc[0]).days / 365.25) * 10
print("\n6-YEAR PROJECTION, 10 sets, fixed size (no compounding), IF the past pattern simply repeated:")
for nm, yearly in (("optimistic: daily-range model", pa), ("base: real hourly-path rate", pb), ("conservative: half of base", pb / 2), ("pessimistic: zero edge after costs", 0.0)):
    print(f"  {nm:38s} Rs{yearly:>9,.0f}/yr -> after 6 yrs Rs{CAP + 6*yearly:>11,.0f}  (profit Rs{6*yearly:,.0f}, {100*6*yearly/CAP:.0f}% of 10L)")
