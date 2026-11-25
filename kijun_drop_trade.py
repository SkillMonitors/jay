"""Trade: BUY at the close of a >=X% single-day drop that breaks below the Kijun-sen (50% line). TARGET = that 50% level. STOP = fixed % below entry. TIME EXIT after N days.
Sensex & Nifty 50 daily, last 10y, cost 0.05%/trade, no leverage."""
import numpy as np, pandas as pd, itertools
def load(n):
    d = pd.read_csv(f"mk_{n}.csv", index_col=0); d.index = pd.to_datetime(d.index.astype(str).str[:10]); return d[~d.index.duplicated()]
def trades(df, th, stop, hold, cost=0.05):
    K = ((df.High.rolling(26).max() + df.Low.rolling(26).min()) / 2).values
    O, H, L, C = (df[c].values for c in ("Open","High","Low","Close")); N = len(df)
    i = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=10)).to_datetime64()); out = []
    while i < N - 1:
        i += 1
        if np.isnan(K[i-1]): continue
        if (C[i]/C[i-1] - 1) * 100 <= -th and C[i-1] >= K[i-1] and C[i] < K[i-1]:
            e, tgt = C[i], K[i-1]; stp = e * (1 - stop/100) if stop else -1; k_end = min(N-1, i+hold); why = "time"; px = C[k_end]
            for k in range(i+1, min(N, i+hold+1)):
                if O[k] >= tgt: px, why, k_end = O[k], "target", k; break
                if O[k] <= stp: px, why, k_end = O[k], "stop", k; break
                if L[k] <= stp: px, why, k_end = stp, "stop", k; break
                if H[k] >= tgt: px, why, k_end = tgt, "target", k; break
            out.append(dict(date=df.index[i], exit=df.index[k_end], days=k_end-i, ret=(px/e-1)*100-cost, why=why)); i = k_end
    return pd.DataFrame(out)
def summ(t, years=10, cap=100000):
    eq = cap * np.cumprod(1 + t.ret.values/100); dd = (eq/np.maximum.accumulate(eq) - 1).min() * 100; w = t[t.ret > 0]; l = t[t.ret <= 0]; h = len(t)//2
    return dict(n=len(t), win=round(100*len(w)/len(t)), tgt=int((t.why=="target").sum()), stp=int((t.why=="stop").sum()), tim=int((t.why=="time").sum()), avg=round(t.ret.mean(),2),
                avgw=round(w.ret.mean(),2) if len(w) else 0, avgl=round(l.ret.mean(),2) if len(l) else 0, pf=round(w.ret.sum()/-l.ret.sum(),2) if len(l) else np.inf,
                days=round(t.days.mean(),1), final=round(eq[-1]), dd=round(dd,1), h1=round(t.ret[:h].mean(),2), h2=round(t.ret[h:].mean(),2), worst=round(t.ret.min(),2))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
D = {"Sensex": load("sensex"), "Nifty 50": load("nifty_50")}
rows = []
for (n, df), th, stop, hold in itertools.product(D.items(), (1.0, 1.5, 2.0), (None, 1, 1.5, 2, 3, 5), (10, 20, 60)):
    t = trades(df, th, stop, hold)
    if len(t) >= 10: rows.append(dict(idx=n, drop=th, stop=stop, hold=hold, **summ(t)))
R = pd.DataFrame(rows); R.to_csv("kijun_drop_trade_grid.csv", index=False)
print("--- Sensex, drop>=1%, hold<=20d ---"); print(R[(R.idx=="Sensex")&(R["drop"]==1.0)&(R.hold==20)].to_string(index=False))
print("--- Nifty 50, drop>=1%, hold<=20d ---"); print(R[(R.idx=="Nifty 50")&(R["drop"]==1.0)&(R.hold==20)].to_string(index=False))
# consistency: configs positive on BOTH indices and both halves
g = R.pivot_table(index=["drop","stop","hold"], columns="idx", values=["avg","h1","h2","win","final"], dropna=True)
ok = g[(g[("avg","Sensex")]>0)&(g[("avg","Nifty 50")]>0)&(g[("h1","Sensex")]>0)&(g[("h2","Sensex")]>0)&(g[("h1","Nifty 50")]>0)&(g[("h2","Nifty 50")]>0)]
print("\n--- configs positive on both indices AND in both halves of the 10 years ---"); print(ok.sort_values(("avg","Sensex"), ascending=False).round(2).head(10).to_string())
