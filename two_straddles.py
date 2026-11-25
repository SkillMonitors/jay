"""TWO short straddles 100 pts apart (K and K+100, e.g. 21,000 and 21,100), expiry days only, 9:16 entry, stop = 10% of the premium of the short legs. 130 qty per leg (2 lots).
S1 = single iron fly (reference: straddle at K + wings K+/-200)   S2 = two straddles, NO hedge   S3 = two straddles + wings (call K+300, put K-200, 260 qty = full hedge).
MODELLED prices (Black-Scholes, India VIX). Cost Rs200 per leg (entry+exit). Daily-range model 5 years (hold to close) and real hourly path ~3 years (exit 3:15 pm)."""
import numpy as np, pandas as pd
import hedged_straddle as H
from intraday_straddle import D, VX, exs, bs
EXD = set(e for e in exs if e in D.index); Q = 130; PER_LEG = 200; SPAN = 6.25 * 3600
STRUCT = {
 "S1 iron fly (1 straddle + wings +-200)": [("C", 0, 1, 1), ("P", 0, 1, 1), ("C", 200, 1, -1), ("P", -200, 1, -1)],
 "S2 two straddles K & K+100, NO hedge":   [("C", 0, 1, 1), ("P", 0, 1, 1), ("C", 100, 1, 1), ("P", 100, 1, 1)],
 "S3 two straddles + full wings":          [("C", 0, 1, 1), ("P", 0, 1, 1), ("C", 100, 1, 1), ("P", 100, 1, 1), ("C", 300, 2, -1), ("P", -200, 2, -1)]}
def V(S, T, iv, K, legs): return sum(sg * m * bs(S, K + off, T, iv, kind == "C") for kind, off, m, sg in legs)
def gross(S, T, iv, K, legs): return sum(m * bs(S, K + off, T, iv, kind == "C") for kind, off, m, sg in legs if sg > 0)
def trade(S0, path, close, T_close, iv, legs, sl):
    K = round(S0 / 50) * 50; T0 = path[0][1] if path else 0; v0 = V(S0, T0 if False else 1 / 252, iv, K, legs); g = gross(S0, 1 / 252, iv, K, legs); x = None; hit = False
    for S, T in path:
        v = V(S, T, iv, K, legs)
        if sl is not None and v - v0 >= sl / 100 * g: x = v0 + sl / 100 * g; hit = True; break
    if x is None: x = V(close, T_close, iv, K, legs)
    return dict(pnl=(v0 - x) * Q - PER_LEG * len(legs), hit=hit, credit=v0 * Q, K=K)
def run_daily(legs, sl, years=5):
    rows = []
    for d, r in D[D.index >= D.index[-1] - pd.DateOffset(years=years)].iterrows():
        if d not in EXD: continue
        iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        pts = [(r.Low, .33), (r.High, .66)] if r.Close >= r.Open else [(r.High, .33), (r.Low, .66)]
        t = trade(r.Open, [(S, (1 - f) / 252) for S, f in pts], r.Close, 0.0, iv, legs, sl); t["date"] = d; rows.append(t)
    return pd.DataFrame(rows)
def run_hourly(legs, sl, exit_f=6 / 6.25):
    rows = []
    for d, g in H.H1.groupby(H.H1.index.normalize()):
        if d not in EXD or d not in D.index or len(g) < 5 or g.index[0].hour != 9: continue
        iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        t0 = g.index[0]; path = []; last = g.Close.iloc[0]
        for ts, b in g.iterrows():
            f0 = (ts - t0).total_seconds() / SPAN
            if f0 >= exit_f: break
            ln = 3600 / SPAN; pts = [(b.Low, f0 + .33 * ln), (b.High, f0 + .66 * ln)] if b.Close >= b.Open else [(b.High, f0 + .33 * ln), (b.Low, f0 + .66 * ln)]
            path += [(S, (1 - min(f, exit_f)) / 252) for S, f in pts]; last = b.Close
        t = trade(g.Open.iloc[0], path, last, (1 - exit_f) / 252, iv, legs, sl); t["date"] = d; rows.append(t)
    return pd.DataFrame(rows)
def show(r, name):
    x = r.pnl; w = x > 0; dd = (x.cumsum() - x.cumsum().cummax()).min()
    print(f"  {name:40s} {len(r):3d} exp | WIN {100*w.mean():3.0f}% ({w.sum()}W/{(~w).sum()}L) | stop hit {100*r.hit.mean():3.0f}% | avg win Rs{x[w].mean():>6,.0f} avg loss Rs{x[~w].mean():>7,.0f} | TOTAL Rs{x.sum():>9,.0f} | best Rs{x.max():>7,.0f} worst Rs{x.min():>8,.0f} | drawdown Rs{dd:>9,.0f} | avg credit Rs{r.credit.mean():>6,.0f}")
if __name__ == "__main__":
    print("A) LAST 5 YEARS, daily-range model, hold to the close, expiry days, stop 10%")
    A = {nm: run_daily(l, 10) for nm, l in STRUCT.items()}
    for nm, r in A.items(): show(r, nm)
    print("\nB) ~3 YEARS, REAL hourly path, exit 3:15 pm, stop 10%")
    for nm, l in STRUCT.items(): show(run_hourly(l, 10), nm)
    print("\nC) NO stop-loss (A: 5y daily model) - tail risk")
    for nm, l in STRUCT.items(): show(run_daily(l, None), nm)
    print("\nS2 and S3 by year (A):")
    for nm in list(STRUCT)[1:]:
        r = A[nm].copy(); r["yr"] = pd.to_datetime(r.date).dt.year; print(f"  {nm}:", (r.groupby("yr").pnl.sum().round().astype(int)).to_dict())
    # worst-case payoff at expiry per structure (centre 21,000, avg credit)
    S = np.arange(19500, 22501, 10)
    for nm, l in STRUCT.items():
        cr = A[nm].credit.mean() / Q; pay = [cr - sum(sg * m * (max(s - (21000 + off), 0) if k == "C" else max((21000 + off) - s, 0)) for k, off, m, sg in l) for s in S]
        print(f"  {nm}: best Rs{max(pay)*Q:,.0f} | at Nifty 19,500: Rs{pay[0]*Q:,.0f} | at 22,500: Rs{pay[-1]*Q:,.0f} | worst in 19,500-22,500: Rs{min(pay)*Q:,.0f}")
    A["S3 two straddles + full wings"].to_csv("two_straddles_S3_trades.csv", index=False)
