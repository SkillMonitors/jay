"""FLAT cloud (flat Senkou Span B) as a target. Nifty 50 / Sensex, last 10y daily & weekly, ~2y 4H/2H.
FLAT = the plotted Senkou B stays exactly constant for >= FLATN consecutive bars (known in advance: the cloud is drawn 26 bars ahead).
UP event  : price is >=1% BELOW the flat level and turns up: close crosses above Tenkan-sen after >=5 closes below it.
            success = High reaches the flat level BEFORE a close below the recent swing low (lowest low of the 10 bars up to the signal);
            failure = swing low breaks first; timeout = neither within MAXB bars.
DOWN event: mirror (price >=1% ABOVE a flat level, turns down: close crosses below Tenkan after >=5 closes above it)."""
import numpy as np, pandas as pd
from cloud_both import load, rs
FLATN = 10
def prep(df):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    N = len(df); B = m(52).values; T = m(9).values
    Bp = np.full(N + 26, np.nan); Bp[26:26 + N] = B          # plotted Senkou B: value at bar k comes from bar k-26 (known ahead up to N+25)
    return T, Bp
def events(df, years, maxb):
    T, Bp = prep(df); C, H, L = df.Close.values, df.High.values, df.Low.values; N = len(df)
    i = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=years)).to_datetime64()) if years else 60
    out = []
    while i < N - 2:
        i += 1
        if np.isnan(T[i]) or np.isnan(T[i-1]): continue
        win = Bp[i:i + FLATN]; lvl = Bp[i]
        if np.isnan(win).any() or not np.all(win == lvl): continue      # next FLATN plotted values flat
        below5 = np.all(C[i-5:i] < T[i-5:i]); above5 = np.all(C[i-5:i] > T[i-5:i])
        d = None
        if lvl > C[i] * 1.01 and below5 and C[i] > T[i] and C[i-1] <= T[i-1]: d = "up"
        elif lvl < C[i] / 1.01 and above5 and C[i] < T[i] and C[i-1] >= T[i-1]: d = "down"
        if d is None: continue
        sw = L[i-10:i+1].min() if d == "up" else H[i-10:i+1].max()
        res, k_end, anyt = "timeout", min(N - 1, i + maxb), None
        for k in range(i + 1, min(N, i + maxb + 1)):
            hit = (H[k] >= lvl) if d == "up" else (L[k] <= lvl)
            inv = (C[k] < sw) if d == "up" else (C[k] > sw)
            if anyt is None and hit: anyt = k - i
            if hit and res == "timeout": res, k_end = "success", k; break
            if inv: res, k_end = "failure", k; break
        if res == "failure":      # does it still reach the level later anyway?
            for k in range(k_end + 1, min(N, i + maxb + 1)):
                if (H[k] >= lvl) if d == "up" else (L[k] <= lvl): anyt = k - i; break
        out.append(dict(date=df.index[i], dir=d, res=res, bars=k_end - i, any_touch=anyt, dist=abs(lvl / C[i] - 1) * 100,
                        dip=((L[i+1:k_end+1].min() / C[i] - 1) * 100 if d == "up" else -(H[i+1:k_end+1].max() / C[i] - 1) * 100) if k_end > i else 0))
        i = k_end if res != "timeout" else i + 5
    return pd.DataFrame(out)
def show(ev, label, unit, per_day):
    print(f"\n{label}")
    for d, nm in (("up", "price turns UP toward a flat cloud ABOVE"), ("down", "price turns DOWN toward a flat cloud BELOW")):
        g = ev[ev.dir == d]
        if not len(g): print(f"  {nm}: 0 events"); continue
        s = g[g.res == "success"]; f = g[g.res == "failure"]; t = g[g.res == "timeout"]; a = g.any_touch.dropna()
        print(f"  {nm}: {len(g)} events | SUCCESS {len(s)} ({100*len(s)/len(g):.0f}%) | FAILURE {len(f)} ({100*len(f)/len(g):.0f}%) | timeout {len(t)} | "
              f"touches the flat line at some point anyway: {len(a)} ({100*len(a)/len(g):.0f}%)")
        if len(s): print(f"      time to touch (successes): avg {s.bars.mean():.1f} {unit} (~{s.bars.mean()/per_day:.1f} trading days), median {s.bars.median():.0f}, max {s.bars.max()} | avg distance to line {g.dist.mean():.1f}% | avg deepest dip {g.dip.mean():+.1f}%")
IDX = {"Nifty 50": "nifty_50", "Sensex": "sensex"}
rows = []
for n, f in IDX.items():
    D = load(f"mk_{f}.csv"); Wk = load(f"data_{f}_1wk.csv")
    show(events(D, 10, 60), f"=== {n} | DAILY | 10 years ===", "days", 1)
    show(events(Wk, 10, 26), f"=== {n} | WEEKLY | 10 years ===", "weeks", 0.2)
    H1 = load(f"ix1h_{f}.csv", True)
    for rule, per_day, lab in (("4h", 1.6, "4-HOUR"), ("2h", 3.2, "2-HOUR")):
        show(events(rs(H1, rule), None, 120), f"=== {n} | {lab} | last ~2 years ===", "bars", per_day)
