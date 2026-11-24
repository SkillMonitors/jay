"""Weekly Nifty 50 expiry option strategies filtered by the daily Ichimoku state. Enter at the close of the previous expiry, hold to expiry. MODELLED prices (Black-Scholes, India VIX as IV, r 6.5%, no skew).
Weekly expiry: Thursday until 31-Aug-2025, Tuesday after (holiday -> previous trading day). Lot 75 assumed. Cost per spread Rs400 (brokerage+charges+slippage).
Window: 2019-03 onward (weekly Nifty expiries exist) -> 2026-11."""
import numpy as np, pandas as pd, math, itertools
ncdf = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs(S, K, T, v, call=True, r=0.065):
    if T <= 0: return max(S - K, 0.0) if call else max(K - S, 0.0)
    d1 = (math.log(S/K) + (r + v*v/2)*T) / (v*math.sqrt(T)); d2 = d1 - v*math.sqrt(T)
    return S*ncdf(d1) - K*math.exp(-r*T)*ncdf(d2) if call else K*math.exp(-r*T)*ncdf(-d2) - S*ncdf(-d1)
D = pd.read_csv("data_nifty_50.csv", index_col=0); D.index = pd.to_datetime(D.index.astype(str).str[:10]); D = D[~D.index.duplicated()]
V = pd.read_csv("indiavix.csv", index_col=0); V.index = pd.to_datetime(V.index.astype(str).str[:10]); V = V.Close[~V.index.duplicated()].reindex(D.index).ffill()
m = lambda n: (D.High.rolling(n).max() + D.Low.rolling(n).min()) / 2
T9, K26 = m(9), m(26); A = ((T9 + K26) / 2).shift(26); B = m(52).shift(26); top, bot = np.fmax(A, B), np.fmin(A, B)
# expiry calendar
exp = []; d = pd.Timestamp("2019-02-25")
while d < D.index[-1]:
    tgt = d + pd.Timedelta(days=(3 if d < pd.Timestamp("2025-09-01") else 1) - d.weekday() + (0 if (3 if d < pd.Timestamp("2025-09-01") else 1) >= d.weekday() else 0))
    wk = d - pd.Timedelta(days=d.weekday()); wd = 3 if wk < pd.Timestamp("2025-09-01") else 1; e = wk + pd.Timedelta(days=wd)
    prev = D.index[D.index <= e]
    if len(prev) and (not exp or prev[-1] > exp[-1]): exp.append(prev[-1])
    d += pd.Timedelta(days=7)
exp = [e for e in exp if e <= D.index[-1]]; COST = 400; LOT = 75
def rnd(x): return round(x / 50) * 50
def leg_pnl(S0, ST, iv, T, kind, d_pct, W):
    """returns spread P&L in points for a CREDIT spread: kind 'put' (bull put) or 'call' (bear call)"""
    if kind == "put":
        ks = rnd(S0 * (1 - d_pct/100)); kl = ks - W; cr = bs(S0, ks, T, iv, False) - bs(S0, kl, T, iv, False); pay = max(ks - ST, 0) - max(kl - ST, 0)
    else:
        ks = rnd(S0 * (1 + d_pct/100)); kl = ks + W; cr = bs(S0, ks, T, iv, True) - bs(S0, kl, T, iv, True); pay = max(ST - ks, 0) - max(ST - kl, 0)
    return cr - pay, cr
def run(strategy, d_pct, W):
    out = []
    for a, b in zip(exp[:-1], exp[1:]):
        S0, ST, iv = D.Close.loc[a], D.Close.loc[b], V.loc[a] / 100; T = ((b - a).days + 0.25) / 365
        if np.isnan(iv) or np.isnan(top.loc[a]): continue
        bull = S0 > top.loc[a] and T9.loc[a] > K26.loc[a]; bear = S0 < bot.loc[a] and T9.loc[a] < K26.loc[a]
        legs = []
        if strategy == "trend": legs = ["put"] if bull else (["call"] if bear else [])
        elif strategy == "trend+condor": legs = ["put"] if bull else (["call"] if bear else ["put", "call"])
        elif strategy == "condor": legs = ["put", "call"]
        elif strategy == "bull_put_always": legs = ["put"]
        if not legs: continue
        pts = 0; cr = 0
        for k in legs: p, c = leg_pnl(S0, ST, iv, T, k, d_pct, W); pts += p; cr += c
        out.append(dict(date=a, expiry=b, pnl=pts * LOT - COST * len(legs), credit=cr * LOT, maxloss=(W - cr / len(legs)) * LOT * (1 if len(legs) == 1 else 1), legs="+".join(legs)))
    return pd.DataFrame(out)
def stats(r):
    if r.empty: return None
    eq = r.pnl.cumsum(); dd = (eq - eq.cummax()).min(); w = r[r.pnl > 0]; l = r[r.pnl <= 0]; yrs = (r.expiry.iloc[-1] - r.date.iloc[0]).days / 365.25
    margin = (W_ := r.maxloss.mean())
    return dict(n=len(r), win=round(100*len(w)/len(r)), avg=round(r.pnl.mean()), total=round(r.pnl.sum()), per_yr=round(r.pnl.sum()/yrs), worst=round(r.pnl.min()), maxdd=round(dd), pf=round(w.pnl.sum()/max(-l.pnl.sum(), 1), 2),
                h1=round(r[r.date < "2023-01-01"].pnl.mean()), h2=round(r[r.date >= "2023-01-01"].pnl.mean()), roi_per_yr=round(100 * r.pnl.sum() / yrs / max(margin, 1)))
rows = []
for s, dp, W in itertools.product(["trend", "trend+condor", "condor", "bull_put_always"], [0.5, 1.0, 1.5, 2.0], [100, 200, 300]):
    st = stats(run(s, dp, W))
    if st: rows.append(dict(strategy=s, otm_pct=dp, width=W, **st))
R = pd.DataFrame(rows); R.to_csv("nifty_weekly_options_grid.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(f"{len(exp)} weekly expiries {exp[0].date()} -> {exp[-1].date()}")
print(R.sort_values("total", ascending=False).head(14).to_string(index=False)); print("\nbest by strategy:")
print(R.sort_values("total", ascending=False).groupby("strategy").head(1).to_string(index=False))
R.to_pickle("/tmp/R.pkl")
