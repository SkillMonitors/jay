"""Ichimoku cloud entry study on daily data: Nifty 50, Sensex, Bank Nifty (last ~15y).
UP event  : previous close below cloud, today's close inside cloud (price enters from below).
            Target = far edge (cloud top). Invalidated if close falls back below cloud bottom.
DOWN event: mirror image (enters from above, target = cloud bottom, invalid if close back above top).
Split by cloud colour: red/bearish (SenkouA < SenkouB) vs green/bullish."""
import numpy as np, pandas as pd, yfinance as yf, os
SYMS = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
MAXD = 120
def load(sym, name):
    f = f"data_{name.replace(' ','_').lower()}.csv"
    if not os.path.exists(f):
        d = yf.download(sym, period="max", auto_adjust=False, progress=False)
        d.columns = d.columns.get_level_values(0)
        d[["Open","High","Low","Close"]].dropna().to_csv(f)
    return pd.read_csv(f, parse_dates=["Date"]).set_index("Date")
def events(df):
    H, L, C = df.High.values, df.Low.values, df.Close.values
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    A = ((m(9) + m(26)) / 2).shift(26).values; B = m(52).shift(26).values
    T9, K26 = m(9).values, m(26).values
    top, bot = np.fmax(A, B), np.fmin(A, B); top = np.where(np.isnan(A)|np.isnan(B), np.nan, top); bot = np.where(np.isnan(A)|np.isnan(B), np.nan, bot)
    start = df.index.max() - pd.DateOffset(years=15)
    out = []; i = np.searchsorted(df.index.values, start.to_datetime64()); N = len(df)
    while i < N - 1:
        i += 1
        if np.isnan(top[i]) or np.isnan(top[i-1]): continue
        for d in ("up", "down"):
            if d == "up": cond = C[i-1] < bot[i-1] and bot[i] <= C[i] <= top[i]
            else:         cond = C[i-1] > top[i-1] and bot[i] <= C[i] <= top[i]
            if not cond: continue
            col = "red" if A[i] < B[i] else "green"
            res, days = "open", None
            for k in range(i + 1, min(N, i + MAXD + 1)):
                if np.isnan(top[k]): break
                hit = (H[k] >= top[k]) if d == "up" else (L[k] <= bot[k])
                bad = (C[k] < bot[k]) if d == "up" else (C[k] > top[k])
                if hit and not (bad and False): res, days = "hit", k - i; break
                if bad: res, days = "fail", k - i; break
            else: days = None
            if res == "open" and i + MAXD < N: res = "timeout"
            cal = (df.index[i + days] - df.index[i]).days if res == "hit" else None
            free = next((k - i for k in range(i + 1, min(N, i + 61)) if not np.isnan(top[k]) and ((H[k] >= top[k]) if d == "up" else (L[k] <= bot[k]))), None)
            out.append(dict(date=df.index[i], dir=d, cloud=col, res=res, days=days, cal=cal, free60=free,
                            above_tk=C[i] > T9[i], above_kj=C[i] > K26[i], thick=(top[i]-bot[i])/C[i]*100))
            if days: i += days  # no overlapping events
            break
    return pd.DataFrame(out)
rows, allev = [], []
for name, sym in SYMS.items():
    df = load(sym, name); ev = events(df); ev["index"] = name; allev.append(ev)
    print(f"{name}: {df.index[0].date()} -> {df.index[-1].date()}")
ev = pd.concat(allev); ev.to_csv("cloud_events.csv", index=False)
def summ(g):
    done = g[g.res.isin(["hit","fail","timeout"])]; h = g[g.res=="hit"]
    return pd.Series(dict(events=len(g), hit=len(h), fail=(g.res=="fail").sum(), timeout=(g.res=="timeout").sum(), open=(g.res=="open").sum(),
        hit_pct=round(100*len(h)/max(len(done),1),1), avg_td=round(h.days.mean(),1), med_td=h.days.median(), max_td=h.days.max(), avg_cal=round(h.cal.mean(),1),
        w10=round(100*(h.days<=10).sum()/max(len(done),1),1), w20=round(100*(h.days<=20).sum()/max(len(done),1),1), w40=round(100*(h.days<=40).sum()/max(len(done),1),1)))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(ev.groupby(["dir","cloud","index"]).apply(summ, include_groups=False).to_string())
print(); print(ev.groupby(["dir","cloud"]).apply(summ, include_groups=False).to_string())

print("\n--- UP + red cloud: extra views ---")
u = ev[(ev.dir=="up")&(ev.cloud=="red")]
f = u.free60.notna()
print("touch top within 60d regardless of closes below cloud:", f.sum(), "/", len(u), f"= {100*f.mean():.1f}%",
      "| avg days", round(u.free60.mean(),1), "median", u.free60.median())
for nm, m_ in [("close>Tenkan", u.above_tk), ("close>Kijun", u.above_kj), ("both", u.above_tk&u.above_kj), ("thick>=1.5%", u.thick>=1.5), ("thick>=3%", u.thick>=3)]:
    g = u[m_]; h = g[g.res=="hit"]
    print(f"{nm:14s} n={len(g):3d} hit {100*len(h)/max(len(g),1):5.1f}%  avg days {h.days.mean():.1f}")
print(u[u.res=="hit"].days.describe().round(1).to_dict())
for name, g in u.groupby("index"): print(name, "last events:", g.tail(3)[["date","res","days"]].astype(str).values.tolist())
