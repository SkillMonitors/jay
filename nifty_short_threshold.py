"""At what % above the MONTHLY average line should Nifty 50 be shorted? Last 10 years (entries from Nov-2016), daily execution.
Line = (a) monthly Kijun-sen (26-month high/low midpoint) or (b) 12-month simple average of monthly closes. Value used = last COMPLETED month.
Short when price trades X% above the line (fill at max(open, line*(1+X))), cover when price falls back to the line. Cost 0.05%."""
import numpy as np, pandas as pd
df = pd.read_csv("data_nifty_50.csv", index_col=0); df.index = pd.to_datetime(df.index.astype(str).str[:10]); df = df[~df.index.duplicated()]
m = df.resample("ME").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
lines = {"Monthly Kijun (26m)": (m.High.rolling(26).max() + m.Low.rolling(26).min()) / 2, "12-month average": m.Close.rolling(12).mean()}
O, H, L, C = (df[c].values for c in ("Open","High","Low","Close")); N = len(df)
mon = m.index.searchsorted(df.index)                                  # month index of each day
START = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=10)).to_datetime64())
def sim(line, thr, stop=None, cost=0.05):
    ln = line.shift(1).values[mon]                                   # last completed month's value, per day
    tr = []; pos = None
    for i in range(START, N):
        if np.isnan(ln[i]): continue
        if pos is None:
            trig = ln[i] * (1 + thr/100)
            if H[i] >= trig: pos = dict(i=i, e=max(O[i], trig), mae=(H[i]/max(O[i], trig) - 1) * 100)
            continue
        e = pos["e"]; pos["mae"] = max(pos["mae"], (H[i]/e - 1) * 100)
        if stop and H[i] >= e * (1 + stop/100): x, w = e * (1 + stop/100), "stop"
        elif L[i] <= ln[i]: x, w = (O[i] if O[i] <= ln[i] else ln[i]), "line"
        else: continue
        tr.append((df.index[pos["i"]], df.index[i], (e/x - 1) * 100 - cost, pos["mae"], w, (i - pos["i"]) / 21)); pos = None
    if pos is not None: tr.append((df.index[pos["i"]], df.index[-1], (pos["e"]/C[-1] - 1) * 100 - cost, pos["mae"], "OPEN", (N - 1 - pos["i"]) / 21))
    return pd.DataFrame(tr, columns=["entry","exit","ret","mae","why","months"])
rows = []
for nm, ln in lines.items():
    for thr in (3, 5, 7, 10, 12, 15, 18, 20, 25, 30):
        for stop in (None, 10, 20):
            t = sim(ln, thr, stop); c = t[t.why != "OPEN"]; o = t[t.why == "OPEN"]
            if len(c) == 0: rows.append(dict(line=nm, thr=thr, stop=stop, done=0, open=len(o), open_ret=round(o.ret.iloc[0], 1) if len(o) else None)); continue
            eq = np.cumprod(1 + c.ret.values / 100)
            rows.append(dict(line=nm, thr=thr, stop=stop, done=len(c), win=round(100*(c.ret>0).mean()), avg=round(c.ret.mean(), 1), comp=round(100*(eq[-1]-1)), months=round(c.months.mean(), 1),
                             worst_against=round(c.mae.max()), open=len(o), open_ret=round(o.ret.iloc[0], 1) if len(o) else None))
R = pd.DataFrame(rows); R.to_csv("nifty_short_threshold.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(f"{df.index[START].date()} -> {df.index[-1].date()}; Nifty {C[START]:.0f} -> {C[-1]:.0f} ({(C[-1]/C[START]-1)*100:.0f}% buy&hold)")
for nm in lines: print("\n==", nm, "=="); print(R[R.line == nm].drop(columns="line").to_string(index=False))
d = sim(lines["Monthly Kijun (26m)"], 10); print("\nKijun, 10% (no stop) trades:"); print(d.assign(entry=d.entry.dt.date, exit=d.exit.dt.date).round(1).to_string(index=False))
