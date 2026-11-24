"""Nifty 50: SHORT when price is >5% above the MONTHLY average line (Kijun-sen, 26 months); stay short until price comes DOWN to that line. No stop-loss (as asked) + stop variants.
Entry variants: (A) intramonth - short as soon as price trades 5% above last month's Kijun (tradeable); (B) at the month's CLOSE if the month closes >5% above its Kijun; (C) at the month's HIGH ("top of the candle", needs hindsight - best-case)."""
import numpy as np, pandas as pd
df = pd.read_csv("data_nifty_50.csv", index_col=0); df.index = pd.to_datetime(df.index.astype(str).str[:10]); df = df[~df.index.duplicated()]
m = df.resample("ME").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
Kc = (m.High.rolling(26).max() + m.Low.rolling(26).min()) / 2      # Kijun incl. month j
mi = {t: j for j, t in enumerate(m.index)}
def month_of(t): return m.index.searchsorted(t)                     # index of month containing day t
def sim(variant, thr=5.0, stop=None, cost=0.05):
    trades = []; pos = None
    for t, r in df.iterrows():
        j = month_of(t)
        if j < 27: continue
        Kprev = Kc.iloc[j-1]                                         # line known at the start of this month (last completed month)
        if pos is None:
            if variant == "A" and r.High >= Kprev * (1 + thr/100):
                pos = dict(t=t, e=max(r.Open, Kprev * (1 + thr/100)), mae=0.0)
        if pos is not None:
            pos["mae"] = max(pos["mae"], (r.High / pos["e"] - 1) * 100)
            lvl = Kprev
            if stop and r.High >= pos["e"] * (1 + stop/100): x, why = pos["e"] * (1 + stop/100), "stop"
            elif r.Low <= lvl and t != pos["t"]: x, why = (r.Open if r.Open <= lvl else lvl), "line"
            else: x = None
            if x is not None:
                trades.append(dict(entry=pos["t"], exit=t, e=pos["e"], x=x, ret=(pos["e"]/x - 1) * 100 - cost, mae=pos["mae"], why=why, months=(t - pos["t"]).days / 30.4)); pos = None
    if pos is not None: trades.append(dict(entry=pos["t"], exit=df.index[-1], e=pos["e"], x=df.Close.iloc[-1], ret=(pos["e"]/df.Close.iloc[-1] - 1) * 100 - cost, mae=pos["mae"], why="OPEN", months=(df.index[-1] - pos["t"]).days / 30.4))
    return pd.DataFrame(trades)
def simMC(variant, stop=None, cost=0.05, thr=5.0):                  # B / C: decide at month end, enter at that month's close/high, then manage from next day
    trades = []; pos = None; days = df.index
    for j in range(27, len(m)):
        mo = m.index[j]
        if pos is None and m.Close.iloc[j] > Kc.iloc[j] * (1 + thr/100) and j + 1 < len(m):
            pos = dict(t=mo, e=m.Close.iloc[j] if variant == "B" else m.High.iloc[j], mae=0.0, start=j + 1)
        if pos is not None and j + 1 >= pos["start"] and j + 1 < len(m):
            for t, r in df[(df.index > mo) & (df.index <= m.index[j+1])].iterrows():
                Kp = Kc.iloc[j]; pos["mae"] = max(pos["mae"], (r.High / pos["e"] - 1) * 100)
                if stop and r.High >= pos["e"] * (1 + stop/100): x, why = pos["e"] * (1 + stop/100), "stop"
                elif r.Low <= Kp: x, why = (r.Open if r.Open <= Kp else Kp), "line"
                else: continue
                trades.append(dict(entry=pos["t"], exit=t, e=pos["e"], x=x, ret=(pos["e"]/x - 1) * 100 - cost, mae=pos["mae"], why=why, months=(t - pos["t"]).days / 30.4)); pos = None; break
    if pos is not None: trades.append(dict(entry=pos["t"], exit=df.index[-1], e=pos["e"], x=df.Close.iloc[-1], ret=(pos["e"]/df.Close.iloc[-1] - 1) * 100 - cost, mae=pos["mae"], why="OPEN", months=(df.index[-1] - pos["t"]).days / 30.4))
    return pd.DataFrame(trades)
def show(name, t):
    if t.empty: print(f"{name}: no trades"); return
    c = t[t.why != "OPEN"]; o = t[t.why == "OPEN"]; eq = np.cumprod(1 + c.ret.values / 100)
    print(f"\n{name}: {len(c)} completed trades" + (f" (+{len(o)} open: {o.ret.iloc[0]:+.1f}% so far since {o.entry.iloc[0].date()}, worst adverse {o.mae.iloc[0]:.0f}%)" if len(o) else ""))
    if len(c): print(f"   win {100*(c.ret>0).mean():.0f}% ({(c.ret>0).sum()}W/{(c.ret<=0).sum()}L) | avg {c.ret.mean():+.1f}% | sum {c.ret.sum():+.1f}% | compounded {100*(eq[-1]-1):+.0f}% | avg hold {c.months.mean():.1f} months (max {c.months.max():.0f}) | stopped out {int((c.why=='stop').sum())} | avg worst move against you {c.mae.mean():.1f}% (worst {c.mae.max():.1f}%)")
    return c
A = sim("A"); B = simMC("B"); C = simMC("C")
for nm, t in (("A) intramonth: short when 5% above the monthly line - NO stop", A), ("B) short at the month CLOSE when >5% above the line - NO stop", B), ("C) short at the month HIGH (top of candle, hindsight) - NO stop", C)):
    c = show(nm, t)
    if nm[0] == "A": print(t.assign(entry=t.entry.dt.date, exit=t.exit.dt.date).round(1).to_string(index=False))
for s in (8, 10, 15):
    show(f"A) intramonth with {s}% stop-loss", sim("A", stop=s))
