"""Three structures from the screenshots (Nifty ~25,819, 1 lot = 65 qty, wings 150 pts):
 S1  4-leg iron fly with in-the-money wings: BUY call K-150, SELL call K, SELL put K, BUY put K+150      (hedged -> NO stop)
 S2  3-leg butterfly 1:2:1 (65/130/65): BUY K-150, SELL 2x K, BUY K+150 (calls; puts give ~the same)    (hedged -> NO stop)
 S3  2-leg naked short straddle at K with a 10% STOP on the combined premium.
Timing A: EXPIRY DAY ONLY, enter at the open, hold to the close (daily-range model, 10 years).   Timing B: enter at the previous expiry close, hold to expiry (all expiries, 10 years).
MODELLED prices (Black-Scholes, India VIX). Cost Rs200 per leg (entry+exit). Constant 65-qty lot."""
import numpy as np, pandas as pd
from intraday_straddle import D, VX, exs, nxt, bs
Q = 65; LEG = 200
ST = {"S1 iron fly, ITM wings (4 legs)": ([("C", 0, 1, 1), ("P", 0, 1, 1), ("C", -150, 1, -1), ("P", 150, 1, -1)], None),
      "S2 butterfly 1:2:1 (3 legs)":      ([("C", 0, 2, 1), ("C", -150, 1, -1), ("C", 150, 1, -1)], None),
      "S3 short straddle + 10% stop":     ([("C", 0, 1, 1), ("P", 0, 1, 1)], 10)}
V = lambda S, T, iv, K, legs: sum(sg * m * bs(S, K + off, T, iv, kind == "C") for kind, off, m, sg in legs)
G = lambda S, T, iv, K, legs: sum(m * bs(S, K + off, T, iv, kind == "C") for kind, off, m, sg in legs if sg > 0)
def trade(S0, T0, path, close, Tc, iv, legs, sl):
    K = round(S0 / 50) * 50; v0 = V(S0, T0, iv, K, legs); g = G(S0, T0, iv, K, legs); x = None; hit = False
    for S, T in path:
        if sl is not None and V(S, T, iv, K, legs) - v0 >= sl / 100 * g: x = v0 + sl / 100 * g; hit = True; break
    if x is None: x = V(close, Tc, iv, K, legs)
    return dict(pnl=(v0 - x) * Q - LEG * len(legs), hit=hit, debit_credit=v0 * Q)
def vertices(r, n_after, f_scale=1.0):          # daily-range path inside one session; n_after = trading days remaining after this session
    pts = [(r.Low, .33), (r.High, .66)] if r.Close >= r.Open else [(r.High, .33), (r.Low, .66)]
    return [(S, (n_after + 1 - f) / 252) for S, f in pts]
def timing_A(legs, sl, years=10):
    rows = []; 
    for d, r in D[D.index >= D.index[-1] - pd.DateOffset(years=years)].iterrows():
        if d not in set(exs): continue
        iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        t = trade(r.Open, 1 / 252, vertices(r, 0), r.Close, 0.0, iv, legs, sl); t["date"] = d; rows.append(t)
    return pd.DataFrame(rows)
ex_all = [e for e in exs if e >= D.index[-1] - pd.DateOffset(years=10) and e <= D.index[-1]]
def timing_B(legs, sl):
    rows = []
    for a, b in zip(ex_all[:-1], ex_all[1:]):
        iv = VX.loc[a] / 100
        if np.isnan(iv): continue
        days = D[(D.index > a) & (D.index <= b)]; n = len(days); path = []
        for i, (d, r) in enumerate(days.iterrows()): path += vertices(r, n - 1 - i)
        t = trade(D.Close.loc[a], (n + 0.0) / 252 + 0 / 252, path, D.Close.loc[b], 0.0, iv, legs, sl); t["date"] = a; rows.append(t)
    return pd.DataFrame(rows)
def show(r, name):
    x = r.pnl; w = x > 0; dd = (x.cumsum() - x.cumsum().cummax()).min()
    print(f"  {name:36s} {len(r):3d} trades | WIN {100*w.mean():3.0f}% ({w.sum()}W/{(~w).sum()}L) | stop hit {100*r.hit.mean():3.0f}% | avg win Rs{x[w].mean():>6,.0f} avg loss Rs{x[~w].mean():>7,.0f} | TOTAL Rs{x.sum():>9,.0f} | best Rs{x.max():>7,.0f} worst Rs{x.min():>8,.0f} | drawdown Rs{dd:>9,.0f}")
# --- screenshot numbers
c, p = {25650: 313.65, 25800: 230.90, 25950: 160.55}, {25650: None, 25800: 205.10, 25950: 287.20}
d1 = c[25650] + p[25950] - c[25800] - p[25800]; d2 = c[25650] + c[25950] - 2 * c[25800]; cr3 = c[25800] + p[25800]
print(f"SCREENSHOTS (spot 25,819, 65 qty): S1 debit {d1:.1f} pts = Rs{d1*Q:,.0f} | max profit Rs{(300-d1)*Q:,.0f} | max loss Rs{(d1-150)*Q:,.0f} | break-evens 25,800 +/-{300-d1-150+150-150:.0f}"
      .replace("+/-0", f"+/-{150-(d1-150):.0f}"))
print(f"             S2 debit {d2:.1f} pts = Rs{d2*Q:,.0f} | max profit Rs{(150-d2)*Q:,.0f} | max loss Rs{d2*Q:,.0f} | break-evens 25,800 +/-{150-d2:.0f}   (Sensibull POP 19%)")
print(f"             S3 credit {cr3:.1f} pts = Rs{cr3*Q:,.0f} max profit | break-evens 25,800 +/-{cr3:.0f}   (Sensibull POP 58%) | needs stop: loss unlimited\n")
for title, fn in (("A) EXPIRY DAY ONLY, enter at the open, hold to the close - last 10 years", timing_A), ("B) enter at the PREVIOUS EXPIRY close, hold to expiry (like the screenshots, ~1 week) - last 10 years", timing_B)):
    print(f"=== {title} ==="); R = {}
    for nm, (legs, sl) in ST.items(): R[nm] = fn(legs, sl); show(R[nm], nm)
    print("  by year (Rs):")
    for nm, r in R.items(): r = r.copy(); r["yr"] = pd.to_datetime(r.date).dt.year; print(f"    {nm:36s}", r.groupby("yr").pnl.sum().round().astype(int).to_dict())
    print()
    pd.concat({k: v for k, v in R.items()}).reset_index(level=0).rename(columns={"level_0": "strategy"}).to_csv(f"three_strategies_{'A' if fn is timing_A else 'B'}.csv", index=False)
