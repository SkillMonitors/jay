"""Price enters the Ichimoku cloud from BELOW or from ABOVE -> does it touch the far edge? How fast? Nifty 50, Sensex, Bank Nifty."""
import numpy as np, pandas as pd
IDX = {"Nifty 50": "nifty_50", "Sensex": "sensex", "Bank Nifty": "bank_nifty"}
def load(path, intraday=False):
    d = pd.read_csv(path, index_col=0); d.index = pd.to_datetime(d.index.astype(str).str[:19 if intraday else 10]); return d[~d.index.duplicated()]
def rs(d, rule): return d.resample(rule, offset="9h15min").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
def events(df, years, maxb):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    A = ((m(9)+m(26))/2).shift(26).values; B = m(52).shift(26).values
    top, bot = np.fmax(A, B), np.fmin(A, B); C, H, L = df.Close.values, df.High.values, df.Low.values; N = len(df)
    i = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=years)).to_datetime64()) if years else 0
    out = []
    while i < N - 2:
        i += 1
        if np.isnan(top[i]) or np.isnan(top[i-1]) or not (bot[i] <= C[i] <= top[i]): continue
        if C[i-1] < bot[i-1]: d = "from below"
        elif C[i-1] > top[i-1]: d = "from above"
        else: continue
        res = "none"; k_end = i
        for k in range(i+1, min(N, i+maxb+1)):
            hit = (H[k] >= top[k]) if d == "from below" else (L[k] <= bot[k])
            back = (C[k] < bot[k]) if d == "from below" else (C[k] > top[k])   # closed back out the way it came in
            if hit: res = "touch"; k_end = k; break
            if back: res = "back"; k_end = k; break
        clean = res == "touch" and not any((C[j] < bot[j]) if d == "from below" else (C[j] > top[j]) for j in range(i+1, k_end+1))
        out.append(dict(date=df.index[i], dir=d, color="red" if A[i] < B[i] else "green", res=res, bars=k_end - i, clean=clean)); i = k_end
    return pd.DataFrame(out)
def report(ev, label, unit, per_day):
    print(f"\n{label}")
    for d in ("from below", "from above"):
        g = ev[ev.dir == d]; t = g[g.res == "touch"]
        if not len(g): continue
        print(f"  {d}: {len(g):3d} entries | touched far edge {len(t):3d} ({100*len(t)/len(g):3.0f}%) | touched before closing back out {len(t):3d}->"
              f"{(g.res=='touch').sum() and 100*(g.res=='touch').mean():.0f}% (rest closed back out first: {(g.res=='back').sum()}, still open {(g.res=='none').sum()}) | "
              f"avg {t.bars.mean():.1f} {unit} (~{t.bars.mean()/per_day:.1f} trading days) | median {t.bars.median():.0f} | within 5 {100*(t.bars<=5).sum()/len(g):.0f}% / 10 {100*(t.bars<=10).sum()/len(g):.0f}% / 20 {100*(t.bars<=20).sum()/len(g):.0f}%")
pd.set_option("display.width", 250)
# ---- Daily, 10y, per index + combined, with cloud colour split
allev = []
for n, f in IDX.items():
    ev = events(load(f"mk_{n.replace(' ','_').lower()}.csv"), 10, 60); ev["idx"] = n; allev.append(ev); report(ev, f"=== {n} | DAILY | last 10 years ===", "days", 1)
E = pd.concat(allev); report(E, "=== ALL THREE | DAILY | 10 years ===", "days", 1)
for c in ("red", "green"): report(E[E.color == c], f"   ... only when cloud is {c.upper()} (entry day)", "days", 1)
# ---- Weekly 10y
W = pd.concat([events(load(f"data_{f}_1wk.csv"), 10, 26).assign(idx=n) for n, f in IDX.items()]); report(W, "=== ALL THREE | WEEKLY | 10 years ===", "weeks", 0.2)
# ---- Intraday ~2y
for rule, per_day, lab in (("4h", 1.6, "4-HOUR"), ("2h", 3.2, "2-HOUR")):
    X = pd.concat([events(rs(load(f"ix1h_{n.replace(' ','_').lower()}.csv", True), rule), None, 120).assign(idx=n) for n in IDX]); report(X, f"=== ALL THREE | {lab} | last ~2 years (Yahoo limit) ===", "bars", per_day)
E.to_csv("cloud_both_daily_events.csv", index=False)
