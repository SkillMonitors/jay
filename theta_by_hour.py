"""When does a BTC DAILY at-the-money straddle (expiry 12:00 UTC = 5:30 pm IST) decay fastest, and when is its delta calm? (1) analytic Black-Scholes table (2) real-data test by ENTRY hour.
Option price = BS with IV = trailing-30d realised vol (markup 1.0), r = 0. No stop here: pure 'sell at hour X, hold to expiry' so the decay-vs-risk trade-off is visible."""
import numpy as np, pandas as pd
from scipy.special import ndtr
def strad(S, K, T, v):
    T = np.maximum(T, 1e-12); sq = v * np.sqrt(T); d1 = (np.log(S / K) + .5 * sq ** 2) / sq; d2 = d1 - sq
    return S * ndtr(d1) - K * ndtr(d2) + K * ndtr(-d2) - S * ndtr(-d1)
sigma = 0.50; Y = 24 * 365
print(f"(1) ANALYTIC: ATM straddle, BTC vol {int(sigma*100)}% a year, hours left to the 12:00 UTC (5:30 pm IST) expiry")
print(f"{'hrs left':>8s} {'IST clock':>10s} {'premium % spot':>15s} {'% of day-start premium left':>28s} {'decay in the NEXT hour (% of day-start premium)':>48s} {'straddle delta if BTC +0.2%':>29s}")
p24 = strad(1, 1, 24 / Y, sigma)
for h in (24, 18, 12, 8, 6, 4, 3, 2, 1, 0.5, 0.25):
    p = strad(1, 1, h / Y, sigma); nxt = strad(1, 1, max(h - 1, 1e-6) / Y, sigma) if h >= 1 else 0.0; sq = sigma * np.sqrt(h / Y); d1 = np.log(1.002) / sq + sq / 2
    clock = (pd.Timestamp("2026-01-01 17:30") - pd.Timedelta(hours=h)).strftime("%H:%M"); dl = 2 * ndtr(d1) - 1
    print(f"{h:8.2f} {clock:>10s} {100*p:14.2f}% {100*p/p24:27.0f}% {100*(p-nxt)/p24 if h>=1 else 100*p/p24:47.1f}% {dl:+28.2f}")
print("  (delta of the straddle = 2*N(d1)-1: it is ~0 when BTC sits exactly at the strike, but it swings toward +-1 faster and faster as expiry nears = gamma risk)\n")
# real data
d = pd.read_csv("cx_btc_1h.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()]
r = np.log(d.Close).diff(); d["rv"] = r.rolling(720, min_periods=400).std().shift(1) * np.sqrt(Y)
print("(2) REAL BTC (~2 yrs): sell the ATM straddle at each hour, hold to the next 12:00 UTC expiry, fair price (IV = trailing real vol), cost 5% of premium, NO stop")
rows = []
for h in range(24):
    hrs = (12 - h) % 24 or 24; pn = []
    for t0 in d.index[d.index.hour == h]:
        t1 = t0 + pd.Timedelta(hours=hrs - 1)
        if t1 not in d.index or np.isnan(d.rv.loc[t0]): continue
        S0 = d.Open.loc[t0]; ST = d.Close.loc[t1]; prem = strad(S0, S0, hrs / Y, d.rv.loc[t0]); pn.append(((prem - abs(ST - S0)) - 0.05 * prem) / S0 * 100 / (prem / S0 * 100) * 100)       # P&L as % of premium
    x = np.array(pn); rows.append((h, hrs, len(x), x.mean(), (x > 0).mean() * 100, x.std(), x.mean() / x.std(), np.percentile(x, 5)))
print(f"{'entry UTC':>9s} {'IST':>6s} {'hrs left':>8s} {'n':>4s} {'avg P&L % of premium':>22s} {'win %':>6s} {'std (risk)':>11s} {'edge/risk':>10s} {'5th pct (bad day)':>18s}")
for h, hrs, n, m, w, s, sr, p5 in rows:
    ist = (pd.Timestamp("2026-01-01") + pd.Timedelta(hours=h, minutes=330)).strftime("%H:%M")
    print(f"{h:02d}:00     {ist:>6s} {hrs:8d} {n:4d} {m:21.1f}% {w:5.0f}% {s:10.0f}% {sr:10.3f} {p5:17.0f}%")
vol = r.groupby(d.index.hour).std() * np.sqrt(Y) * 100
print("\n(3) Realised BTC volatility by hour of day (annualised %, UTC):")
print("  " + "  ".join(f"{h:02d}h:{v:.0f}" for h, v in vol.items()))
