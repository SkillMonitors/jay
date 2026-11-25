"""Two SHORT straddles at open-100 and open+100 (e.g. 20,900 and 21,100 when Nifty opens ~21,000), expiry days only, entry 9:16, each with ITS OWN stop-loss (% of ITS premium), exit 3:15 pm (hourly) / close (daily model).
130 qty (2 lots) per leg. Optional wings (call at upper+200, put at lower-200, 260 qty). Cost Rs200 per leg. 'slip' = extra points paid per straddle when its stop fires (real spreads).
MODELLED prices (Black-Scholes, India VIX)."""
import numpy as np, pandas as pd
import hedged_straddle as H
from intraday_straddle import D, VX, exs, bs
EXD = set(e for e in exs if e in D.index); Q, LEG, SPAN = 130, 200, 6.25 * 3600
def trade(S0, path, close, T_close, iv, stops, hedge, slip):
    K = round(S0 / 50) * 50; Ks = [K - 100, K + 100]; T0 = 1 / 252
    st = lambda S, T, k: bs(S, k, T, iv, True) + bs(S, k, T, iv, False)
    v0 = [st(S0, T0, k) for k in Ks]; out = [None, None]; stopped = [False, False]
    w0 = (bs(S0, Ks[1] + 200, T0, iv, True) + bs(S0, Ks[0] - 200, T0, iv, False)) if hedge else 0.0
    for S, T in path:
        for i in (0, 1):
            if out[i] is None and st(S, T, Ks[i]) - v0[i] >= stops[i] / 100 * v0[i]: out[i] = v0[i] * (1 + stops[i] / 100) + slip; stopped[i] = True
    for i in (0, 1):
        if out[i] is None: out[i] = st(close, T_close, Ks[i])
    pnl = sum((v0[i] - out[i]) * Q for i in (0, 1)) - 4 * LEG
    if hedge: pnl += (bs(close, Ks[1] + 200, T_close, iv, True) + bs(close, Ks[0] - 200, T_close, iv, False) - w0) * 2 * Q - 2 * LEG
    return dict(pnl=pnl, n_stops=sum(stopped), prem=sum(v0) * Q)
def daily(stops, hedge, slip, years=5):
    rows = []
    for d, r in D[D.index >= D.index[-1] - pd.DateOffset(years=years)].iterrows():
        if d not in EXD: continue
        iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        pts = [(r.Low, .33), (r.High, .66)] if r.Close >= r.Open else [(r.High, .33), (r.Low, .66)]
        t = trade(r.Open, [(S, (1 - f) / 252) for S, f in pts], r.Close, 0.0, iv, stops, hedge, slip); t["date"] = d; rows.append(t)
    return pd.DataFrame(rows)
def hourly(stops, hedge, slip, exit_f=6 / 6.25):
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
        t = trade(g.Open.iloc[0], path, last, (1 - exit_f) / 252, iv, stops, hedge, slip); t["date"] = d; rows.append(t)
    return pd.DataFrame(rows)
def show(r, name):
    x = r.pnl; w = x > 0; dd = (x.cumsum() - x.cumsum().cummax()).min()
    print(f"  {name:44s} {len(r):3d} exp | WIN {100*w.mean():3.0f}% | both stops {100*(r.n_stops==2).mean():3.0f}% one {100*(r.n_stops==1).mean():3.0f}% none {100*(r.n_stops==0).mean():3.0f}% | avg win Rs{x[w].mean():>6,.0f} avg loss Rs{x[~w].mean():>7,.0f} | TOTAL Rs{x.sum():>9,.0f} | worst Rs{x.min():>8,.0f} | drawdown Rs{dd:>9,.0f}")
CASES = [("lower strike 2% / upper strike 3%", (2, 3)), ("lower strike 3% / upper strike 2%", (3, 2)), ("both 10% (earlier setting)", (10, 10))]
for title, fn in (("A) LAST 5 YEARS - daily-range model, expiry days, exit at close", daily), ("B) ~3 YEARS - REAL hourly path, expiry days, exit 3:15 pm", hourly)):
    print(f"\n=== {title} ===")
    for hedge in (False, True):
        print(f" -- {'WITH wings (full hedge)' if hedge else 'NO wings (two naked straddles)'} --")
        for nm, s in CASES:
            show(fn(s, hedge, 0.0), nm + "  [exact stop fills]")
        show(fn((2, 3), hedge, 2.0), "2%/3%  [stop fills 2 pts worse - realistic]")
