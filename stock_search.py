"""Ichimoku strategy search across 48 Nifty-50 stocks, 15 years daily. Long only, entry at signal close, cost 0.15% round trip.
Ranks by average % per trade, % per day held, with a train (2011-2018) / test (2019-2026) split."""
import numpy as np, pandas as pd, itertools, sys
A = pd.read_csv("stocks_daily.csv.gz", index_col=0, parse_dates=True)
COST = 0.15; CUT = pd.Timestamp("2019-01-01"); START = A.index.max() - pd.DateOffset(years=15)
def ind(df):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    T, K = m(9).values, m(26).values; a = ((m(9)+m(26))/2).shift(26).values; b = m(52).shift(26).values
    tr = pd.concat([df.High-df.Low, (df.High-df.Close.shift()).abs(), (df.Low-df.Close.shift()).abs()], axis=1).max(axis=1)
    return dict(O=df.Open.values, H=df.High.values, L=df.Low.values, C=df.Close.values, T=T, K=K, A=a, B=b, top=np.fmax(a,b), bot=np.fmin(a,b), atr=tr.rolling(14).mean().values, idx=df.index)
def sig(d, name, p):
    C, K, T, top, bot, a, b = d["C"], d["K"], d["T"], d["top"], d["bot"], d["A"], d["B"]
    sh = lambda x: np.r_[np.nan, x[:-1]]; pC, pK, pT, ptop, pbot = sh(C), sh(K), sh(T), sh(top), sh(bot)
    with np.errstate(invalid="ignore"):
        inside = (C >= bot) & (C <= top)
        if name == "red_cloud_entry": s = (pC < pbot) & inside & (a < b) & (C > T) & (C > K); tg = "edge"
        elif name == "cloud_entry_any": s = (pC < pbot) & inside; tg = "edge"
        elif name == "kijun_drop": s = ((C/pC - 1)*100 <= -p) & (pC >= pK) & (C < pK); tg = "level"
        elif name == "dip_below_kijun": s = (C <= K*(1-p/100)) & (pC > pK*(1-p/100)); tg = "level"
        elif name == "cloud_breakout": s = (C > top) & (pC <= ptop); tg = "tp"
        elif name == "tk_cross_above_cloud": s = (T > K) & (pT <= pK) & (C > top); tg = "tp"
        elif name == "kijun_pullback": s = (C > top) & (T > K) & (d["L"] <= K) & (C > K) & (pC > pK); tg = "tp"
    return np.where(s & ~np.isnan(top) & ~np.isnan(K))[0], tg
def trade(d, i, tg, tp, stop, hold):
    O, H, L, C = d["O"], d["H"], d["L"], d["C"]; N = len(C); e = C[i]
    stp = e - 2*d["atr"][i] if stop == "atr" else (e*(1-stop/100) if stop else -1)
    lvl = d["K"][i-1] if tg == "level" else None
    for k in range(i+1, min(N, i+hold+1)):
        t = d["top"][k] if tg == "edge" else (lvl if tg == "level" else e*(1+tp/100))
        if O[k] >= t: return k, O[k]/e-1, "T"
        if O[k] <= stp: return k, O[k]/e-1, "S"
        if L[k] <= stp: return k, stp/e-1, "S"
        if H[k] >= t: return k, t/e-1, "T"
    k = min(N-1, i+hold); return k, C[k]/e-1, "X"
DATA = {t: ind(g) for t, g in A.groupby("Ticker")}
SIGS = {"red_cloud_entry": [None], "cloud_entry_any": [None], "kijun_drop": [2.0, 3.0], "dip_below_kijun": [4.0, 6.0], "cloud_breakout": [None], "tk_cross_above_cloud": [None], "kijun_pullback": [None]}
rows = []; allt = {}
for name, params in SIGS.items():
    for p in params:
        pre = {t: sig(d, name, p) for t, d in DATA.items()}; tg = next(iter(pre.values()))[1]
        for tp, stop, hold in itertools.product([3, 5, 8] if tg == "tp" else [None], ["atr", 5, 8], [5, 10, 20]):
            tr = []
            for t, d in DATA.items():
                nxt = 0
                for i in pre[t][0]:
                    if i < nxt or d["idx"][i] < START or i + 1 >= len(d["C"]): continue
                    k, r, w = trade(d, i, tg, tp, stop, hold); tr.append((t, d["idx"][i], k - i, (r*100 - COST), w)); nxt = k + 1
            if len(tr) < 150: continue
            x = pd.DataFrame(tr, columns=["t","date","days","ret","why"]); tr_, te = x[x.date < CUT], x[x.date >= CUT]
            pf = x.ret[x.ret > 0].sum() / max(-x.ret[x.ret <= 0].sum(), 1e-9); byst = x.groupby("t").ret.mean()
            rows.append(dict(strategy=name, param=p, tp=tp, stop=stop, hold=hold, n=len(x), per_yr=round(len(x)/15), win=round(100*(x.ret>0).mean()), avg=round(x.ret.mean(),2), days=round(x.days.mean(),1),
                             per_day=round(x.ret.sum()/x.days.sum(),3), pf=round(pf,2), avg_train=round(tr_.ret.mean(),2), avg_test=round(te.ret.mean(),2), n_test=len(te), stocks_pos=f"{(byst>0).sum()}/{len(byst)}", worst=round(x.ret.min(),1)))
            allt[(name, p, tp, stop, hold)] = x
R = pd.DataFrame(rows); R.to_csv("stock_search.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 30)
print(len(R), "configs with >=150 trades")
ok = R[(R.avg_train > 0) & (R.avg_test > 0)]
print("\n=== TOP by avg % per trade (positive in BOTH train 2011-18 and test 2019-26) ==="); print(ok.sort_values("avg", ascending=False).head(12).to_string(index=False))
print("\n=== TOP by % return per day held (positive in both halves) ==="); print(ok.sort_values("per_day", ascending=False).head(12).to_string(index=False))
