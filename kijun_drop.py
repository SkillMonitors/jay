"""Nifty 50 daily, last 10y. Kijun-sen = 50% (midpoint) of the last-26-day high/low range.
Event: a single candle closes at least X% below the previous close AND crosses from above the Kijun to below it.
Question: does price later recover (High) back up to that 50% level, and how fast?"""
import numpy as np, pandas as pd, sys
NAME = sys.argv[1] if len(sys.argv) > 1 else "nifty_50"
df = pd.read_csv(f"mk_{NAME}.csv", index_col=0); df.index = pd.to_datetime(df.index.astype(str).str[:10]); df = df[~df.index.duplicated()]
K = ((df.High.rolling(26).max() + df.Low.rolling(26).min()) / 2).values
O, H, L, C = (df[c].values for c in ("Open","High","Low","Close")); N = len(df)
start = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=10)).to_datetime64())
def run(th, maxd=60, show=False):
    rows = []; i = start
    while i < N - 1:
        i += 1
        if np.isnan(K[i-1]): continue
        drop = (C[i]/C[i-1] - 1) * 100
        if drop <= -th and C[i-1] >= K[i-1] and C[i] < K[i-1]:
            lvl = K[i-1]; touch = None; touch_dyn = None; worst = 0
            for k in range(i+1, min(N, i+maxd+1)):
                worst = min(worst, (L[k]/C[i]-1)*100)
                if touch is None and H[k] >= lvl: touch = k - i
                if touch_dyn is None and H[k] >= K[k]: touch_dyn = k - i
                if touch is not None and touch_dyn is not None: break
            rows.append(dict(date=df.index[i].date(), drop=round(drop,2), close=round(C[i]), level=round(lvl), to_level=round((lvl/C[i]-1)*100,2), touch=touch, touch_dyn=touch_dyn, worst_before=round(worst,1)))
            if touch: i += touch
    return pd.DataFrame(rows)
print(f"{df.index[start].date()} -> {df.index[-1].date()}")
for th in (1.0, 1.5, 2.0, 3.0):
    r = run(th); t = r.touch.dropna(); td = r.touch_dyn.dropna()
    print(f"\n### single-day drop >= {th}% that breaks below Kijun (50% line): {len(r)} events")
    print(f"  recovered to the SAME 50% level (within 60 days): {len(t)} ({100*len(t)/len(r):.0f}%) | not recovered: {len(r)-len(t)}")
    print(f"  recovered to the (moving) Kijun: {len(td)} ({100*len(td)/len(r):.0f}%)")
    if len(t): print(f"  days to recover: avg {t.mean():.1f}, median {t.median():.0f}, p90 {t.quantile(.9):.0f}, max {t.max():.0f} | within 5d {100*(t<=5).sum()/len(r):.0f}%, 10d {100*(t<=10).sum()/len(r):.0f}%, 20d {100*(t<=20).sum()/len(r):.0f}%")
    print(f"  distance from drop close up to the 50% level: avg {r.to_level.mean():.2f}% | further fall after the drop before recovery/60d: avg {r.worst_before.mean():.1f}%, worst {r.worst_before.min():.1f}%")
    if th in (2.0,): print(r.to_string(index=False)); r.to_csv(f"kijun_drop_events_2pct_{NAME}.csv", index=False)
