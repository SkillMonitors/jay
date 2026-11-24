"""Intraday Nifty ATM straddle: enter at the OPEN (ATM strike), exit at the CLOSE, stop-loss = X% of the combined premium. 10 years daily (path approximated from daily OHLC),
checked against real hourly paths for the last ~2 years. MODELLED option prices (Black-Scholes, India VIX prior close as IV, r 6.5%). Nearest expiry (monthly until Feb-2019, weekly Thu, weekly Tue from Sep-2025).
Points are per unit of Nifty; Rs shown for a 75-qty lot (older years had other lot sizes). Cost Rs400/day per straddle."""
import numpy as np, pandas as pd, math
ncdf = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs(S, K, T, v, call, r=0.065):
    if T <= 1e-9: return max(S - K, 0.0) if call else max(K - S, 0.0)
    d1 = (math.log(S/K) + (r + v*v/2)*T) / (v*math.sqrt(T)); d2 = d1 - v*math.sqrt(T)
    return S*ncdf(d1) - K*math.exp(-r*T)*ncdf(d2) if call else K*math.exp(-r*T)*ncdf(-d2) - S*ncdf(-d1)
V2 = lambda S, K, T, v: bs(S, K, T, v, True) + bs(S, K, T, v, False)
D = pd.read_csv("data_nifty_50.csv", index_col=0); D.index = pd.to_datetime(D.index.astype(str).str[:10]); D = D[~D.index.duplicated()]
VX = pd.read_csv("indiavix.csv", index_col=0); VX.index = pd.to_datetime(VX.index.astype(str).str[:10]); VX = VX.Close[~VX.index.duplicated()].reindex(D.index).ffill().shift(1)   # prior close
# expiry calendar (snapped to trading days)
cand = []
for y in range(2016, 2027):
    for mth in range(1, 13):
        last = pd.Timestamp(y, mth, 1) + pd.offsets.MonthEnd(0); cand.append(("M", last - pd.Timedelta(days=(last.weekday() - 3) % 7)))
wk = pd.Timestamp("2019-02-25")
while wk < pd.Timestamp("2026-12-31"):
    wd = 3 if wk < pd.Timestamp("2025-09-01") else 1; cand.append(("W", wk + pd.Timedelta(days=wd))); wk += pd.Timedelta(days=7)
ex = sorted({(d if k == "W" else d) for k, d in cand if (k == "W" or d < pd.Timestamp("2019-02-25") or True)})
def snap(e): p = D.index[D.index <= e]; return p[-1] if len(p) else e
exs = sorted({snap(e) for e in ex if e <= D.index[-1] + pd.Timedelta(days=10)})
def nxt(d): 
    i = np.searchsorted(np.array(exs, dtype="datetime64[ns]"), np.datetime64(d)); return exs[i] if i < len(exs) else None
SESS = 0.26
def day(row, d, sl, side, cost=400):
    e = nxt(d); iv = VX.loc[d] / 100
    if e is None or np.isnan(iv): return None
    n = int(((D.index > d) & (D.index <= e)).sum()) if e <= D.index[-1] else max(1, int(np.busday_count(d.date(), e.date())))   # trading days after today up to expiry (0 on expiry day)
    days = n; K = round(row.Open / 50) * 50; T0 = (n + 1) / 252                   # TRADING-day time: today is a full trading day of variance
    p0 = V2(row.Open, K, T0, iv)
    path = [(row.Low, .33), (row.High, .66)] if row.Close >= row.Open else [(row.High, .33), (row.Low, .66)]
    hit = False; x = None
    for S, f in path:
        v = V2(S, K, (n + 1 - f) / 252, iv)
        if sl is not None and ((side == "short" and v >= p0 * (1 + sl/100)) or (side == "long" and v <= p0 * (1 - sl/100))): hit = True; x = p0 * (1 + sl/100) if side == "short" else p0 * (1 - sl/100); break
    if not hit: x = V2(row.Close, K, n / 252, iv)
    pts = (p0 - x) if side == "short" else (x - p0)
    return dict(date=d, prem=p0, prem_pct=p0 / row.Open * 100, pts=pts, hit=hit, dte=days, pnl=pts * 75 - cost)
def run(sl, side, start=None):
    rows = [r for r in (day(row, d, sl, side) for d, row in D.iterrows() if d >= (start or D.index[-1] - pd.DateOffset(years=10))) if r]; return pd.DataFrame(rows)
def show(r, name):
    x = r.pnl; w = (x > 0).sum(); eq = x.cumsum(); dd = (eq - eq.cummax()).min(); yrs = (r.date.iloc[-1] - r.date.iloc[0]).days / 365.25
    print(f"  {name:26s} {len(x):4d} days | WIN {100*w/len(x):3.0f}% LOSE {100*(len(x)-w)/len(x):3.0f}% | SL hit {100*r.hit.mean():3.0f}% | avg/day Rs{x.mean():>6,.0f} | TOTAL Rs{x.sum():>10,.0f} (Rs{x.sum()/yrs:>8,.0f}/yr) | worst day Rs{x.min():>8,.0f} | max drawdown Rs{dd:>10,.0f}")
if __name__ == "__main__":
    print(f"{D.index[-1] - pd.DateOffset(years=10):%Y-%m-%d} -> {D.index[-1]:%Y-%m-%d}")
    print("\n=== SELL ATM straddle at the open, exit at close, 10-year ===")
    for sl in (10, 20, 30, None): r = run(sl, "short"); show(r, f"stop-loss {sl}%" if sl else "no stop-loss")
    print("\n=== BUY ATM straddle at the open, exit at close ===")
    for sl in (10, None): r = run(sl, "long"); show(r, f"stop-loss {sl}%" if sl else "no stop-loss")
    r = run(10, "short"); r["yr"] = r.date.dt.year; r["pnl_k"] = r.pnl
    print("\n=== SELL straddle, 10% stop-loss, by year ==="); print(r.groupby("yr").agg(days=("pnl", "size"), win=("pnl", lambda x: round(100*(x>0).mean())), sl_hit=("hit", lambda x: round(100*x.mean())), total=("pnl", lambda x: round(x.sum())), worst=("pnl", lambda x: round(x.min()))).to_string())
    r.to_csv("intraday_straddle_short10.csv", index=False)
    print("\navg premium %.2f%% of spot | avg stop-loss size if hit: Rs%.0f per lot | avg premium Rs%.0f per lot" % (r.prem_pct.mean(), (r.prem * 0.10 * 75).mean(), (r.prem * 75).mean()))
    print("longest losing streak (days):", max((len(list(g)) for k, g in __import__("itertools").groupby(r.pnl <= 0) if k), default=0))

def hourly_check(sl=10, cost=400):
    H1 = pd.read_csv("ix1h_nifty_50.csv", index_col=0); H1.index = pd.to_datetime(H1.index.astype(str).str[:19]); H1 = H1[~H1.index.duplicated()]
    out = []
    for d, g in H1.groupby(H1.index.normalize()):
        if d not in D.index or d not in VX.index or len(g) < 5: continue
        e = nxt(d); iv = VX.loc[d] / 100
        if e is None or np.isnan(iv): continue
        n = int(((D.index > d) & (D.index <= e)).sum()) if e <= D.index[-1] else max(1, int(np.busday_count(d.date(), e.date())))
        S0 = g.Open.iloc[0]; K = round(S0 / 50) * 50; p0 = V2(S0, K, (n + 1) / 252, iv); hit = False; x = None
        t0 = g.index[0]; span = 6.25 * 3600
        for ts, b in g.iterrows():
            f0 = (ts - t0).total_seconds() / span; ln = min(3600, span - (ts - t0).total_seconds()) / span
            for S, ff in ([(b.Low, f0 + .33 * ln), (b.High, f0 + .66 * ln)] if b.Close >= b.Open else [(b.High, f0 + .33 * ln), (b.Low, f0 + .66 * ln)]):
                if V2(S, K, (n + 1 - min(ff, 1)) / 252, iv) >= p0 * (1 + sl / 100): hit = True; break
            if hit: break
        x = p0 * (1 + sl / 100) if hit else V2(g.Close.iloc[-1], K, n / 252, iv)
        out.append(dict(date=d, hit=hit, pnl=(p0 - x) * 75 - cost))
    return pd.DataFrame(out)
if __name__ == "__main__":
    h = hourly_check(); st = h.date.min(); dd = run(10, "short", start=st)
    print(f"\n=== CHECK on real hourly paths ({st.date()} -> {h.date.max().date()}, {len(h)} days) vs the daily-OHLC approximation ===")
    print(f"  hourly path : win {100*(h.pnl>0).mean():.0f}% | SL hit {100*h.hit.mean():.0f}% | total Rs{h.pnl.sum():,.0f} | avg/day Rs{h.pnl.mean():,.0f}")
    print(f"  daily approx: win {100*(dd.pnl>0).mean():.0f}% | SL hit {100*dd.hit.mean():.0f}% | total Rs{dd.pnl.sum():,.0f} | avg/day Rs{dd.pnl.mean():,.0f}")
