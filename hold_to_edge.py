"""Enter when price closes inside the cloud (from below -> LONG, from above -> SHORT). NO stop-loss, NO time limit:
hold until price touches the far cloud edge. Daily, last 10y, Nifty 50 / Sensex / Bank Nifty. Cost 0.05%/trade, no leverage, Rs1L per index (compounded)."""
import numpy as np, pandas as pd
from cloud_both import load, IDX
CAP = 100000
def sim(df, modes, years=10, redonly=False):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    A = ((m(9)+m(26))/2).shift(26).values; B = m(52).shift(26).values; top, bot = np.fmax(A, B), np.fmin(A, B)
    O, H, L, C = (df[c].values for c in ("Open","High","Low","Close")); N = len(df)
    start = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=years)).to_datetime64())
    eq = CAP; curve = []; trades = []; pos = None; days_in = 0
    for i in range(start, N):
        if pos is not None:
            s, e, j, eq0, mae = pos
            if i > j:
                tgt = top[i] if s == 1 else bot[i]
                hit = (H[i] >= tgt) if s == 1 else (L[i] <= tgt)
                mae = min(mae, (L[i]/e - 1) * 100 if s == 1 else -(H[i]/e - 1) * 100)
                pos = (s, e, j, eq0, mae)
                if hit:
                    px = max(tgt, O[i]) if s == 1 else min(tgt, O[i]); r = s * (px/e - 1) * 100 - 0.05
                    eq = eq0 * (1 + r/100); trades.append(dict(entry=df.index[j], exit=df.index[i], side=s, days=i-j, ret=r, mae=mae, open=False)); pos = None
                else: days_in += 1
            curve.append(eq if pos is None else pos[3] * (1 + pos[0] * (C[i]/pos[1] - 1)))
        else: curve.append(eq)
        if pos is None and i < N - 1 and not (np.isnan(top[i]) or np.isnan(top[i-1])) and bot[i] <= C[i] <= top[i]:
            if C[i-1] < bot[i-1] and "long" in modes and (not redonly or A[i] < B[i]): pos = (1, C[i], i, eq, 0.0)
            elif C[i-1] > top[i-1] and "short" in modes: pos = (-1, C[i], i, eq, 0.0)
    if pos is not None:
        s, e, j, eq0, mae = pos; r = s * (C[-1]/e - 1) * 100
        trades.append(dict(entry=df.index[j], exit=df.index[-1], side=s, days=N-1-j, ret=r, mae=mae, open=True))
    t = pd.DataFrame(trades); cv = pd.Series(curve); yrs = (N - start) / 252
    return t, cv, yrs, days_in / (N - start)
def line(name, t, cv, yrs, tim):
    d = t[~t.open]; o = t[t.open]; dd = (cv / cv.cummax() - 1).min() * 100
    print(f"{name:34s} trades {len(d):3d} closed (+{len(o)} open) | avg {d.days.mean():5.1f}d  median {d.days.median():4.0f}d  p90 {d.days.quantile(.9):4.0f}d  max {d.days.max():4.0f}d | avg gain {d.ret.mean():+.2f}% | "
          f"avg worst dip {d.mae.mean():+.1f}%  deepest {d.mae.min():+.1f}% | in market {100*tim:.0f}% | Rs1L -> Rs{cv.iloc[-1]:,.0f} (CAGR {((cv.iloc[-1]/CAP)**(1/yrs)-1)*100:.1f}%, max drawdown {dd:.0f}%)"
          + (f" | OPEN now: {o.ret.iloc[0]:+.1f}% since {o.entry.iloc[0].date()}" if len(o) else ""))
res = {}
for n, f in IDX.items():
    df = load(f"mk_{n.replace(' ','_').lower()}.csv"); print(f"\n=== {n} ===")
    for name, modes, red in (("LONG from below (any cloud)", ("long",), False), ("LONG from below (RED cloud only)", ("long",), True), ("SHORT from above", ("short",), False), ("BOTH directions", ("long","short"), False)):
        t, cv, yrs, tim = sim(df, modes, redonly=red); line(name, t, cv, yrs, tim); res[(n, name)] = t
allt = pd.concat([t.assign(k=k[1], idx=k[0]) for k, t in res.items()]); allt.to_csv("hold_to_edge_trades.csv", index=False)
for k in ("LONG from below (any cloud)", "LONG from below (RED cloud only)", "SHORT from above"):
    d = allt[(allt.k == k) & (~allt.open)]; print(f"\nCOMBINED {k}: {len(d)} closed trades, all reached the edge; days avg {d.days.mean():.1f} median {d.days.median():.0f} p90 {d.days.quantile(.9):.0f} max {d.days.max()}; "
          f"within 5d {100*(d.days<=5).mean():.0f}% 10d {100*(d.days<=10).mean():.0f}% 30d {100*(d.days<=30).mean():.0f}%; avg dip {d.mae.mean():+.1f}%, dips worse than -5%: {(d.mae<-5).sum()}, worse than -10%: {(d.mae<-10).sum()}; open now: {int(allt[(allt.k==k)].open.sum())}")
