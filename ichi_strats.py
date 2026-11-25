"""Systematic test of classic Ichimoku trend strategies. Daily, last 10y, Indian indices + 13 FX pairs.
Entry/exit at bar close, one position at a time, cost 0.05% per round trip."""
import numpy as np, pandas as pd, itertools
from market_scan import get, MK
from fx_tf import FX
IDX = ["Nifty 50", "Sensex", "Bank Nifty"]
def ind(df):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    T, K = m(9).values, m(26).values; A = ((m(9)+m(26))/2).shift(26).values; B = m(52).shift(26).values
    return dict(C=df.Close.values, T=T, K=K, A=A, B=B, top=np.fmax(A,B), bot=np.fmin(A,B), chikou=(df.Close.values > df.Close.shift(26).values))
def signals(d, side, entry, exit_):
    C, T, K, top, bot, A, B = (d[k] for k in ("C","T","K","top","bot","A","B"))
    s = 1 if side == "long" else -1
    prevC = np.r_[np.nan, C[:-1]]; prevtop = np.r_[np.nan, top[:-1]]; prevbot = np.r_[np.nan, bot[:-1]]
    prevT = np.r_[np.nan, T[:-1]]; prevK = np.r_[np.nan, K[:-1]]
    if side == "long":
        above = C > top; tk = T > K; tkx = (T > K) & (prevT <= prevK); cross = above & (prevC <= prevtop)
        full = above & tk & d["chikou"] & (A > B); fullprev = np.r_[False, full[:-1]]
        ex = {"close<Kijun": C < K, "close<cloud": C < top, "TK cross down": (T < K) & (prevT >= prevK), "close<Tenkan": C < T}
    else:
        above = C < bot; tkx = (T < K) & (prevT >= prevK); cross = above & (prevC >= prevbot)
        full = above & (T < K) & (~d["chikou"]) & (A < B); fullprev = np.r_[False, full[:-1]]
        ex = {"close<Kijun": C > K, "close<cloud": C > bot, "TK cross down": (T > K) & (prevT <= prevK), "close<Tenkan": C > T}
    en = {"cloud breakout": cross, "TK cross above cloud": tkx & above, "full alignment": full & ~fullprev}[entry]
    return s, en, ex[exit_]
def run(d, sides, entry, exit_, years=10, cost=0.05, idx=None):
    C = d["C"]; N = len(C); start = N - int(years * 252)
    sig = {sd: signals(d, sd, entry, exit_) for sd in sides}
    trades = []; pos = None; i = start
    for i in range(start, N):
        if pos is not None:
            s, e, j = pos; _, _, ex = sig["long" if s == 1 else "short"]
            if ex[i] or i == N - 1:
                trades.append((j, i, s * (C[i]/e - 1) * 100 - cost)); pos = None
        if pos is None and i < N - 1:
            for sd in sides:
                s, en, _ = sig[sd]
                if en[i] and not np.isnan(d["top"][i]): pos = (s, C[i], i); break
    return trades
def stats(tr, years):
    if not tr: return None
    r = np.array([t[2] for t in tr]); eq = np.cumprod(1 + r/100); dd = (eq / np.maximum.accumulate(eq) - 1).min() * 100
    return dict(n=len(r), win=100*(r>0).mean(), avg=r.mean(), tot=(eq[-1]-1)*100, cagr=(eq[-1]**(1/years)-1)*100, dd=dd,
                hold=np.mean([t[1]-t[0] for t in tr]), pf=r[r>0].sum()/max(-r[r<=0].sum(), 1e-9))
if __name__ == "__main__":
    data = {n: ind(get(n, MK[n])) for n in IDX}
    for n in FX: data[n] = ind(get(n, MK[n]))
    rows = []
    for sides, entry, ex in itertools.product([("long",), ("long","short")], ["cloud breakout","TK cross above cloud","full alignment"], ["close<Kijun","close<cloud","TK cross down","close<Tenkan"]):
        res = {}; 
        for grp, names in (("India", IDX), ("FX", list(FX))):
            cg = []; wins = []; ns = []; holds = []; pos_mk = 0; dds = []
            for n in names:
                tr = run(data[n], sides, entry, ex); s = stats(tr, 10)
                if s: cg.append(s["cagr"]); ns.append(s["n"]); wins.append(s["win"]); holds.append(s["hold"]); dds.append(s["dd"]); pos_mk += s["cagr"] > 0
            res[grp] = (np.mean(cg), np.mean(wins), np.sum(ns), np.mean(holds), pos_mk, len(names), np.mean(dds))
        rows.append(dict(sides="+".join(sides), entry=entry, exit=ex, **{f"{g}_cagr": round(v[0],2) for g, v in res.items()},
            **{f"{g}_win": round(v[1]) for g, v in res.items()}, **{f"{g}_trades": v[2] for g, v in res.items()}, **{f"{g}_hold_d": round(v[3],1) for g, v in res.items()},
            **{f"{g}_mk_pos": f"{v[4]}/{v[5]}" for g, v in res.items()}, **{f"{g}_dd": round(v[6]) for g, v in res.items()}))
    R = pd.DataFrame(rows); R.to_csv("ichi_strats.csv", index=False)
    pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
    print(R.sort_values("India_cagr", ascending=False).to_string(index=False))
    bh = [((data[n]["C"][-1]/data[n]["C"][-2520])**(1/10)-1)*100 for n in IDX]; print("\nBuy&hold CAGR India idx:", [round(x,1) for x in bh])
