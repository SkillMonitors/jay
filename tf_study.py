"""(1) Same 'enter red cloud from below -> touch cloud top' study on 15m/1h/daily/weekly/monthly bars.
   (2) Daily trade simulation with stop-loss and a time stop (<= 1 week)."""
import numpy as np, pandas as pd, yfinance as yf, os, itertools
SYMS = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
def get(sym, name, tf):
    f = f"data_{name.replace(' ','_').lower()}_{tf}.csv"
    if tf == "1d": f = f"data_{name.replace(' ','_').lower()}.csv"
    if not os.path.exists(f):
        kw = {"15m": dict(period="60d", interval="15m"), "1h": dict(period="730d", interval="1h"),
              "1wk": dict(period="max", interval="1wk"), "1mo": dict(period="max", interval="1mo")}[tf]
        d = yf.download(sym, auto_adjust=False, progress=False, **kw); d.columns = d.columns.get_level_values(0)
        d[["Open","High","Low","Close"]].dropna().to_csv(f)
    d = pd.read_csv(f, index_col=0, parse_dates=True)
    return d
def prep(df):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    A = ((m(9) + m(26)) / 2).shift(26).values; B = m(52).shift(26).values
    ok = ~(np.isnan(A) | np.isnan(B))
    return dict(T=m(9).values, K=m(26).values, A=A, B=B, top=np.where(ok, np.fmax(A, B), np.nan), bot=np.where(ok, np.fmin(A, B), np.nan))
def events(df, years=15, maxb=60):
    p = prep(df); C, H = df.Close.values, df.High.values; top, bot = p["top"], p["bot"]
    N = len(df); i = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=years)).to_datetime64()) if years else 0
    ev = []
    while i < N - 2:
        i += 1
        if np.isnan(top[i]) or np.isnan(top[i-1]): continue
        if C[i-1] < bot[i-1] and bot[i] <= C[i] <= top[i] and p["A"][i] < p["B"][i]:
            strict = free = None
            for k in range(i+1, min(N, i+maxb+1)):
                if free is None and H[k] >= top[k]: free = k - i
                if strict is None and free is not None and not any(C[j] < bot[j] for j in range(i+1, k+1)): strict = free
                if C[k] < bot[k] and free is None and strict is None: strict = -1  # invalidated first
                if free is not None: break
            ev.append(dict(i=i, date=df.index[i], free=free, strict=free if (free and strict != -1) else None))
            if free: i += free
    return ev, p
print("=== (1) Time-frame comparison: enter red cloud from below, target cloud top ===")
rows = []
for tf in ["15m", "1h", "1d", "1wk", "1mo"]:
    tot = hit = fh = 0; days = []
    for n, s in SYMS.items():
        df = get(s, n, tf)
        ev, p = events(df, years=None if tf in ("15m","1h") else 15, maxb={"15m":200,"1h":120,"1d":60,"1wk":26,"1mo":12}[tf])
        for e in ev:
            tot += 1; fh += e["free"] is not None; hit += e["strict"] is not None
            if e["free"]: days.append(e["free"])
    rows.append(dict(timeframe=tf, events=tot, touch_anytime=f"{fh}/{tot} ({100*fh/max(tot,1):.0f}%)", touch_without_closing_below_cloud=f"{hit}/{tot} ({100*hit/max(tot,1):.0f}%)",
                     avg_bars_to_touch=round(np.mean(days), 1) if days else None, span=f"{df.index[0].date()}..{df.index[-1].date()}"))
print(pd.DataFrame(rows).to_string(index=False))

print("\n=== (2) Daily trade plan simulation (enter at signal-day close, long) ===")
def sim_events():
    out = []
    for n, s in SYMS.items():
        df = get(s, n, "1d"); ev, p = events(df, 15)
        O, H, L, C = (df[c].values for c in ("Open","High","Low","Close"))
        for e in ev:
            out.append(dict(idx=n, i=e["i"], df=df, p=p, O=O, H=H, L=L, C=C, date=e["date"]))
    return out
EV = sim_events()
def trade(e, stop, hold):
    i = e["i"]; ent = e["C"][i]; top = e["p"]["top"]; st = ent * (1 - stop / 100) if stop else -1
    for k in range(i+1, min(len(e["C"]), i+hold+1)):
        if e["O"][k] >= top[k]: return (e["O"][k]/ent-1)*100, "target"
        if e["O"][k] <= st: return (e["O"][k]/ent-1)*100, "stop"
        if e["L"][k] <= st: return -stop, "stop"
        if e["H"][k] >= top[k]: return (top[k]/ent-1)*100, "target"
    j = min(len(e["C"])-1, i+hold); return (e["C"][j]/ent-1)*100, "time"
def filt(e, f):
    i = e["i"]; p = e["p"]
    if f == "none": return True
    if f == "tk_kj": return e["C"][i] > p["T"][i] and e["C"][i] > p["K"][i]
res = []
for f, stop, hold in itertools.product(["none", "tk_kj"], [None, 1, 1.5, 2, 3, 4], [3, 5, 10]):
    r = [trade(e, stop, hold) for e in EV if filt(e, f)]; x = np.array([a for a, _ in r])
    w = x[x > 0]; l = x[x <= 0]
    half = len(x) // 2
    res.append(dict(filter=f, stop=stop, hold=hold, n=len(x), win=round(100*(x>0).mean(),1), avg=round(x.mean(),2), avg_win=round(w.mean(),2), avg_loss=round(l.mean(),2) if len(l) else 0,
                    pf=round(w.sum()/-l.sum(),2) if len(l) and l.sum() else np.inf, worst=round(x.min(),2), tot=round(x.sum(),1),
                    avg1=round(x[:half].mean(),2), avg2=round(x[half:].mean(),2)))
R = pd.DataFrame(res); R.to_csv("trade_plan_grid.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(R[R.hold == 5].to_string(index=False)); print("\nTop by avg per trade (all holds):")
print(R.sort_values("avg", ascending=False).head(8).to_string(index=False))
