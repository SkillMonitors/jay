"""Grid-search Ichimoku mean-reversion strategies on Nifty 50 daily data (last 10y).
Enter at signal-day close, one position at a time. No costs."""
import itertools, sys, numpy as np, pandas as pd
full = pd.read_csv("nifty50_daily.csv", parse_dates=["Date"]).set_index("Date")
H, L, C = full.High, full.Low, full.Close
mid = lambda n: (H.rolling(n).max() + L.rolling(n).min()) / 2
ten, kij = mid(9), mid(26)
sa = ((ten + kij) / 2).shift(26); sb = mid(52).shift(26)
lines = {"tenkan": ten, "kijun": kij, "cloud": None}
top, bot = pd.concat([sa, sb], axis=1).max(axis=1, skipna=False), pd.concat([sa, sb], axis=1).min(axis=1, skipna=False)
start = full.index.max() - pd.DateOffset(years=10)
idx = full.index[full.index >= start]
c = C.values; dates = full.index
first = dates.get_loc(idx[0])

def ref_line(side, ref):
    if ref == "cloud": return (top if side == "short" else bot).values
    return lines[ref].values

def run(side, ref, thr, exitk, stop, maxhold, lo, hi):
    r = ref_line(side, ref); ex = {"kijun": kij.values, "ref": r, "tenkan": ten.values}
    trades = []; pos = None
    for i in range(max(first, lo), hi):
        if np.isnan(r[i]): continue
        if pos is None:
            dev = (c[i] / r[i] - 1) * 100
            if (side == "short" and dev > thr) or (side == "long" and dev < -thr):
                pos = (i, c[i])
            continue
        j, e = pos; s = 1 if side == "long" else -1
        ret = s * (c[i] / e - 1) * 100
        done = False
        if isinstance(exitk, float):
            done = ret >= exitk
        else:
            tgt = ex[exitk][i]
            done = (c[i] >= tgt) if side == "long" else (c[i] <= tgt)
        if stop and ret <= -stop: done = True
        if maxhold and i - j >= maxhold: done = True
        if done: trades.append((j, i, ret)); pos = None
    return trades, pos

def stats(tr):
    if not tr: return None
    r = np.array([t[2] for t in tr]); w = r > 0
    return dict(n=len(r), win=w.mean(), tot=r.sum(), avg=r.mean(), aw=r[w].mean() if w.any() else 0,
                al=r[~w].mean() if (~w).any() else 0, worst=r.min(), days=np.mean([t[1]-t[0] for t in tr]))

grid = itertools.product(["long", "short"], ["tenkan", "kijun", "cloud"], [2,3,4,5,6,8,10],
                         ["ref", "kijun", 1.0, 2.0, 3.0, 5.0], [None, 5, 8, 12], [None, 20, 40])
N = len(full); mid_i = first + (N - first) // 2
rows = []
for side, ref, thr, ex, stop, mh in grid:
    tr, op = run(side, ref, thr, ex, stop, mh, 0, N)
    s = stats(tr)
    if not s or s["n"] < 8: continue
    a = stats(run(side, ref, thr, ex, stop, mh, 0, mid_i)[0]); b = stats(run(side, ref, thr, ex, stop, mh, mid_i, N)[0])
    rows.append(dict(side=side, ref=ref, thr=thr, exit=ex, stop=stop, maxhold=mh, **s,
                     n1=a["n"] if a else 0, w1=a["win"] if a else np.nan,
                     n2=b["n"] if b else 0, w2=b["win"] if b else np.nan, open=op is not None))
d = pd.DataFrame(rows)
d.to_csv("search_results.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
good = d[(d.win >= 0.88) & (d.n >= 10)].sort_values("tot", ascending=False)
print(len(d), "strategies with >=8 trades;", len(good), "with win>=88% & n>=10")
print(good.head(15).round(2).to_string(index=False))
