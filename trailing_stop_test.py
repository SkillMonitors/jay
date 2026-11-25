"""ATM short straddle on EXPIRY DAYS: fixed 10% stop vs TRAILING 10% stop.
Fixed   : stop = entry premium x 1.10  (never moves).
Trailing: stop = (LOWEST combined premium seen so far) x 1.10 - e.g. sold at 200 -> stop 220; premium falls to 180 -> stop 198 (distance 18, not 20); keeps ratcheting down, never up.
Enter at the open, exit at the close (daily model, 10y) or 3:15 pm (real hourly path, ~3y). MODELLED prices; cost Rs200/leg; 65 qty."""
import numpy as np, pandas as pd
src = open("validate_expiry.py").read().split("A = {nm: daily(")[0]; exec(src)
LEGS = ST["S3 short straddle + 10% stop"][0]
def trade3(S0, T0, path, close, Tc, iv, pct, trail, slip=0.0):
    K = round(S0 / 50) * 50; v0 = V(S0, T0, iv, K, LEGS); low = v0; x = None; hit = False
    for S, T in path:
        v = V(S, T, iv, K, LEGS)
        if v >= low * (1 + pct / 100) if trail else v >= v0 * (1 + pct / 100):
            x = (low if trail else v0) * (1 + pct / 100) + slip; hit = True; break
        low = min(low, v)
    if x is None: x = V(close, Tc, iv, K, LEGS)
    return dict(pnl=(v0 - x) * Q - LEG * 2, hit=hit)
def daily3(pct, trail, slip=0.0):
    rows = []
    for d, r in D[D.index >= D.index[-1] - pd.DateOffset(years=10)].iterrows():
        if d not in EXD: continue
        iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        rows.append(trade3(r.Open, 1 / 252, vertices(r, 0), r.Close, 0.0, iv, pct, trail, slip) | dict(date=d))
    return pd.DataFrame(rows)
def hourly3(pct, trail, slip=0.0, exit_f=6 / 6.25):
    rows = []
    for d, g in H.H1.groupby(H.H1.index.normalize()):
        if d not in EXD or d not in D.index or len(g) < 5 or g.index[0].hour != 9: continue
        iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        t0 = g.index[0]; path = []; last = g.Close.iloc[0]
        for ts, b in g.iterrows():
            f0 = (ts - t0).total_seconds() / SPAN
            if f0 >= exit_f - 1e-9: break
            ln = 3600 / SPAN; pts = [(b.Low, f0 + .33 * ln), (b.High, f0 + .66 * ln)] if b.Close >= b.Open else [(b.High, f0 + .33 * ln), (b.Low, f0 + .66 * ln)]
            path += [(S, (1 - min(f, exit_f)) / 252) for S, f in pts]; last = b.Close
        rows.append(trade3(g.Open.iloc[0], 1 / 252, path, last, (1 - exit_f) / 252, iv, pct, trail, slip) | dict(date=d))
    return pd.DataFrame(rows)
def row(r): x = r.pnl; w = x > 0; dd = (x.cumsum() - x.cumsum().cummax()).min(); return f"{len(r):3d} exp | WIN {100*w.mean():3.0f}% | stop hit {100*r.hit.mean():3.0f}% | avg win Rs{x[w].mean():>6,.0f} avg loss Rs{x[~w].mean():>7,.0f} | avg/expiry Rs{x.mean():>6,.0f} | TOTAL Rs{x.sum():>9,.0f} | worst Rs{x.min():>7,.0f} | drawdown Rs{dd:>8,.0f}"
print("=== 10 YEARS, expiry days, daily-range model, exit at close ===")
for nm, pct, tr in (("FIXED 10%", 10, False), ("TRAILING 10%", 10, True), ("TRAILING 15%", 15, True), ("TRAILING 20%", 20, True), ("FIXED 20%", 20, False)): print(f"  {nm:14s} {row(daily3(pct, tr))}")
print("\n=== ~3 YEARS, REAL hourly path, exit 3:15 pm ===")
for nm, pct, tr in (("FIXED 10%", 10, False), ("TRAILING 10%", 10, True), ("TRAILING 15%", 15, True), ("TRAILING 20%", 20, True), ("FIXED 20%", 20, False)): print(f"  {nm:14s} {row(hourly3(pct, tr))}")
print("\n=== stress: 5 points worse fill whenever the stop fires ===")
for nm, pct, tr in (("FIXED 10%", 10, False), ("TRAILING 10%", 10, True)): print(f"  {nm:14s} 10y Rs{daily3(pct, tr, 5).pnl.sum():>9,.0f} | 3y real Rs{hourly3(pct, tr, 5).pnl.sum():>9,.0f}")
