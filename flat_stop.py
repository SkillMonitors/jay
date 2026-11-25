"""Flat TOP of the cloud (Senkou A or B, whichever forms the top edge, level for >=10 plotted bars) as a target. Price enters the cloud from BELOW.
Entry = close of the entry candle (prev close below the cloud, close inside it). Target = first touch of the flat top (High >= level).
Stop = low of the last candle that was below the cloud (candle before entry). Daily 10y; 2H/3H/4H ~2y (Yahoo intraday limit). Nifty 50, Bank Nifty, Sensex."""
import numpy as np, pandas as pd
IDX = {"Nifty 50": "nifty_50", "Bank Nifty": "bank_nifty", "Sensex": "sensex"}; FLATN = 10; COST = 0.05
def rd(p, intr=False): d = pd.read_csv(p, index_col=0); d.index = pd.to_datetime(d.index.astype(str).str[:19 if intr else 10]); return d[~d.index.duplicated()]
def rs(d, rule): return d.resample(rule, offset="9h15min").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
def events(df, years, maxb, stopmode="prev"):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    N = len(df); a = ((m(9) + m(26)) / 2).values; b = m(52).values
    Ap = np.full(N + 26, np.nan); Bp = Ap.copy(); Ap[26:] = a; Bp[26:] = b            # plotted 26 bars ahead
    top = np.fmax(Ap, Bp); bot = np.fmin(Ap, Bp)
    top = np.where(np.isnan(Ap) | np.isnan(Bp), np.nan, top); bot = np.where(np.isnan(Ap) | np.isnan(Bp), np.nan, bot)
    O, H, L, C = (df[c].values for c in ("Open","High","Low","Close"))
    i = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=years)).to_datetime64()) if years else 60; out = []
    while i < N - 2:
        i += 1
        if np.isnan(bot[i]) or np.isnan(bot[i-1]) or not (C[i-1] < bot[i-1] and bot[i] <= C[i] <= top[i]): continue
        win = top[i:i + FLATN]
        if np.isnan(win).any() or not np.all(win == win[0]): continue                   # flat top edge ahead
        lvl = top[i]; e = C[i]; stop = L[i-1] if stopmode == "prev" else L[i]
        if not (stop < e < lvl): continue
        res, k_end, px = "timeout", min(N - 1, i + maxb), C[min(N - 1, i + maxb)]; anyt = None
        for k in range(i + 1, min(N, i + maxb + 1)):
            if anyt is None and H[k] >= lvl: anyt = k - i
            if O[k] <= stop: res, k_end, px = "stop", k, O[k]; break
            if L[k] <= stop: res, k_end, px = "stop", k, stop; break
            if O[k] >= lvl: res, k_end, px = "target", k, O[k]; break
            if H[k] >= lvl: res, k_end, px = "target", k, lvl; break
        out.append(dict(date=df.index[i], res=res, bars=k_end - i, ret=(px/e - 1) * 100 - COST, reward=(lvl/e - 1) * 100, risk=(e/stop - 1) * 100, any_touch=anyt)); i = k_end
    return pd.DataFrame(out)
def line(label, ev, per_day):
    if ev.empty: print(f"  {label:28s}: 0 events"); return
    t = ev[ev.res == "target"]; s = ev[ev.res == "stop"]; o = ev[ev.res == "timeout"]
    print(f"  {label:28s}: {len(ev):3d} setups | TOUCHED flat line first {len(t):3d} ({100*len(t)/len(ev):3.0f}%) | STOPPED first {len(s):3d} ({100*len(s)/len(ev):3.0f}%) | timeout {len(o):2d} | "
          f"avg to touch {t.bars.mean() if len(t) else float('nan'):4.1f} bars (~{(t.bars.mean()/per_day if len(t) else float('nan')):.1f} trading days) | reward {ev.reward.mean():.2f}% vs risk {ev.risk.mean():.2f}% | avg per trade {ev.ret.mean():+.2f}% | sum {ev.ret.sum():+.0f}%")
TF = [("Daily (10y)", None, 60, 1), ("4-hour (~2y)", "4h", 120, 1.6), ("3-hour (~2y)", "3h", 120, 2.1), ("2-hour (~2y)", "2h", 150, 3.2)]
allr = []
for lab, rule, maxb, pd_ in TF:
    print(f"\n=== {lab} ===")
    tot = []
    for n, f in IDX.items():
        df = rd(f"mk_{f}.csv") if rule is None else rs(rd(f"ix1h_{f}.csv", True), rule)
        ev = events(df, 10 if rule is None else None, maxb); ev["idx"] = n; ev["tf"] = lab; tot.append(ev); line(n, ev, pd_)
    T = pd.concat(tot); line("ALL THREE", T, pd_); allr.append(T)
pd.concat(allr).to_csv("flat_stop_events.csv", index=False)
print("\n--- sensitivity: stop = low of the ENTRY candle instead ---")
for lab, rule, maxb, pd_ in TF:
    tot = []
    for n, f in IDX.items():
        df = rd(f"mk_{f}.csv") if rule is None else rs(rd(f"ix1h_{f}.csv", True), rule); tot.append(events(df, 10 if rule is None else None, maxb, "entry"))
    line(lab, pd.concat(tot), pd_)
