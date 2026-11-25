"""VALIDATION of the three screenshot strategies on EXPIRY DAYS ONLY (enter at the open, no overnight, exit at the close / 3:15 pm).
Checks: (1) first half vs second half of the 10 years (in/out of sample)  (2) monthly-expiry era vs weekly era  (3) real hourly path (~3y), exit 3:15 and close
(4) trading-cost / stop-slippage stress  (5) is there a real premium edge (premium collected vs what the market actually did)."""
import numpy as np, pandas as pd
src = open("three_strategies.py").read().split("# --- screenshot numbers")[0]; exec(src)
import hedged_straddle as H
EXD = set(exs); SPAN = 6.25 * 3600
def trade2(S0, T0, path, close, Tc, iv, legs, sl, slip=0.0, extra_cost=0.0):
    K = round(S0 / 50) * 50; v0 = V(S0, T0, iv, K, legs); g = G(S0, T0, iv, K, legs); x = None; hit = False
    for S, T in path:
        if sl is not None and V(S, T, iv, K, legs) - v0 >= sl / 100 * g: x = v0 + sl / 100 * g + slip; hit = True; break
    if x is None: x = V(close, Tc, iv, K, legs)
    return dict(pnl=(v0 - x) * Q - (LEG + extra_cost) * len(legs), hit=hit, prem=v0 * Q, move=abs(close - K), K=K, gcr=g)
def daily(legs, sl, slip=0.0, extra=0.0, years=10):
    rows = []
    for d, r in D[D.index >= D.index[-1] - pd.DateOffset(years=years)].iterrows():
        if d not in EXD: continue
        iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        t = trade2(r.Open, 1 / 252, vertices(r, 0), r.Close, 0.0, iv, legs, sl, slip, extra); t["date"] = d; rows.append(t)
    return pd.DataFrame(rows)
def hourly(legs, sl, exit_f=6 / 6.25, slip=0.0, extra=0.0):
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
        t = trade2(g.Open.iloc[0], 1 / 252, path, last, (1 - exit_f) / 252, iv, legs, sl, slip, extra); t["date"] = d; rows.append(t)
    return pd.DataFrame(rows)
def row(r): x = r.pnl; w = x > 0; dd = (x.cumsum() - x.cumsum().cummax()).min(); return f"{len(r):3d} exp | WIN {100*w.mean():3.0f}% | avg Rs{x.mean():>6,.0f}/expiry | TOTAL Rs{x.sum():>9,.0f} | worst Rs{x.min():>7,.0f} | drawdown Rs{dd:>8,.0f}"
A = {nm: daily(legs, sl) for nm, (legs, sl) in ST.items()}
print("=== 1) FIRST HALF vs SECOND HALF (daily model, expiry days) ===")
for nm, r in A.items():
    d = pd.to_datetime(r.date); print(f"  {nm}\n     2016-2021 (in-sample) : {row(r[d < '2022-01-01'])}\n     2022-2026 (out-of-sample): {row(r[d >= '2022-01-01'])}")
print("\n=== 2) MONTHLY-expiry era (to Feb-2019) vs WEEKLY era ===")
for nm, r in A.items():
    d = pd.to_datetime(r.date); print(f"  {nm}\n     monthly era : {row(r[d < '2019-03-01'])}\n     weekly era  : {row(r[d >= '2019-03-01'])}")
print("\n=== 3) REAL HOURLY PATHS (~3 years of expiry days) ===")
for nm, (legs, sl) in ST.items():
    print(f"  {nm}\n     exit 3:15 pm : {row(hourly(legs, sl))}\n     exit 3:30 pm : {row(hourly(legs, sl, exit_f=1.0))}")
print("\n=== 4) STRESS: S3 straddle with worse costs / stop slippage (points paid extra when the stop fires; extra Rs per leg) ===")
for slip, extra in ((0, 0), (2, 0), (5, 0), (10, 0), (5, 200), (10, 300), (20, 300)):
    a = daily(ST["S3 short straddle + 10% stop"][0], 10, slip, extra); h = hourly(ST["S3 short straddle + 10% stop"][0], 10, slip=slip, extra=extra)
    print(f"  slip {slip:2d} pts, extra Rs{extra:3d}/leg:  10y daily model Rs{a.pnl.sum():>10,.0f} (win {100*(a.pnl>0).mean():.0f}%)  |  3y real hourly Rs{h.pnl.sum():>9,.0f} (win {100*(h.pnl>0).mean():.0f}%)")
print("\n=== 5) EDGE CHECK: what the straddle SELLER collects vs what the market actually did on expiry days (10y, no stop) ===")
n = daily(ST["S3 short straddle + 10% stop"][0], None); mv = n.move.mean(); pr = n.prem.mean() / Q
print(f"  avg straddle premium at the open {pr:.0f} pts | avg value at the close (|close-strike|) {mv:.0f} pts | premium kept on average {pr-mv:.0f} pts = {100*(pr-mv)/pr:.0f}% of the premium")
print(f"  with NO stop-loss: total Rs{n.pnl.sum():,.0f}, win {100*(n.pnl>0).mean():.0f}%, worst day Rs{n.pnl.min():,.0f} ; WITH the 10% stop: total Rs{A['S3 short straddle + 10% stop'].pnl.sum():,.0f}, worst Rs{A['S3 short straddle + 10% stop'].pnl.min():,.0f}")
