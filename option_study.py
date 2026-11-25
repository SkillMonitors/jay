"""How often does a 1-month ATM CALL bought on an Ichimoku signal double (+100%)? Black-Scholes repricing with India VIX as IV (fallback 14%).
Signals (daily, Nifty/Bank Nifty, last 10y): (A) close breaks above cloud top; (B) enters red cloud from below with close>Tenkan&Kijun. Base rate = every day."""
import numpy as np, pandas as pd, yfinance as yf, os, math
from market_scan import get, MK
from ichi_strats import ind
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs(S, K, T, v, r=0.065):
    if T <= 0: return max(S - K, 0.0)
    d1 = (math.log(S/K) + (r + v*v/2)*T) / (v*math.sqrt(T)); d2 = d1 - v*math.sqrt(T)
    return S*ncdf(d1) - K*math.exp(-r*T)*ncdf(d2)
if not os.path.exists("indiavix.csv"):
    d = yf.download("^INDIAVIX", period="12y", auto_adjust=False, progress=False); d.columns = d.columns.get_level_values(0); d[["Close"]].to_csv("indiavix.csv")
vix = pd.read_csv("indiavix.csv", index_col=0); vix.index = pd.to_datetime(vix.index.astype(str).str[:10]); vix = vix.Close[~vix.index.duplicated()]
print("VIX rows:", len(vix), vix.index.min().date() if len(vix) else None)
HOLD = 21
def study(name):
    df = get(name, MK[name]); d = ind(df); C = d["C"]; N = len(C); idx = df.index
    v = (vix.reindex(idx).ffill().bfill() / 100).fillna(0.14).values if len(vix) else np.full(N, .14)
    top, T_, K_ , A, B = d["top"], d["T"], d["K"], d["A"], d["B"]
    prevC = np.r_[np.nan, C[:-1]]; prevtop = np.r_[np.nan, top[:-1]]; prevbot = np.r_[np.nan, np.fmin(A,B)[:-1]]
    sigA = (C > top) & (prevC <= prevtop)
    sigB = (prevC < prevbot) & (np.fmin(A,B) <= C) & (C <= top) & (A < B) & (C > T_) & (C > K_)
    start = N - 2520; out = {}
    for lab, sig in (("A: breaks above cloud", sigA), ("B: enters red cloud + Tenkan/Kijun", sigB), ("Any day (base rate)", np.ones(N, bool))):
        res = []
        for i in range(max(start, 80), N - HOLD):
            if not sig[i] or np.isnan(top[i]): continue
            S0 = C[i]; Kx = round(S0 / 50) * 50; p0 = bs(S0, Kx, 30/365, v[i]); best = 0; 
            for j in range(1, HOLD + 1):
                pj = bs(C[i+j], Kx, max(30 - j*365/252, 0)/365, v[i+j]); best = max(best, pj / p0)
            pend = bs(C[i+HOLD], Kx, 0, v[i]) / p0
            res.append((best, pend, C[i+HOLD]/S0 - 1))
        r = np.array(res)
        out[lab] = (len(r), (r[:,0] >= 2).mean()*100, (r[:,1] >= 2).mean()*100, (r[:,1] > 1).mean()*100, (r[:,1] < 0.5).mean()*100, np.mean(r[:,1]) - 1, np.median(r[:,1]) - 1, (r[:,1] <= 0.01).mean()*100)
    return out
for n in ("Nifty 50", "Bank Nifty"):
    o = study(n); print(f"\n=== {n}: buy ATM call at signal-day close, ~30 days to expiry, hold {HOLD} trading days ===")
    print(f"{'signal':38s}{'n':>5s}{'touched 2x':>12s}{'ended >=2x':>12s}{'ended profit':>14s}{'lost >50%':>11s}{'lost ~all':>11s}{'avg ret':>9s}{'median':>8s}")
    for k, (n_, t2, e2, pr, l50, avg, med, l100) in o.items():
        print(f"{k:38s}{n_:5d}{t2:11.0f}%{e2:11.0f}%{pr:13.0f}%{l50:10.0f}%{l100:10.0f}%{avg*100:+8.0f}%{med*100:+7.0f}%")
