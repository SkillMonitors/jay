"""Delta-Exchange-style DAILY options (expiry every day 12:00 UTC = 5:30 pm IST): SELL the ATM straddle right after expiry (entry 12:00 UTC, 24h to expiry), stop = 10% above the premium, exit at expiry.
Real BTC/ETH hourly price paths (~2 years). Each hour is filled in with a Brownian bridge (12 five-minute steps) so the stop is checked on a fine path. 10 random bridges per real day.
Option price = Black-Scholes (r=0) with IV = markup x trailing-30-day REALISED vol (no free implied-vol history exists, so markup is an assumption; 1.0 = fair price). P&L in % of notional (spot).
cost = round-trip trading cost as % of the premium (fees+spread)."""
import numpy as np, pandas as pd
from scipy.special import ndtr
rng = np.random.default_rng(11)
def straddle(S, K, T, v):
    T = np.maximum(T, 1e-12); sq = v * np.sqrt(T); d1 = (np.log(S / K) + 0.5 * sq ** 2) / sq; d2 = d1 - sq
    return S * ndtr(d1) - K * ndtr(d2) + K * ndtr(-d2) - S * ndtr(-d1)
def load(f):
    d = pd.read_csv(f, index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()]; r = np.log(d.Close).diff(); d["rv"] = r.rolling(720, min_periods=400).std().shift(1) * np.sqrt(24 * 365); return d
def paths(d, entry_hour=12, hours=24, draws=10, m=12):
    """yield (S_path[0..n], sigma_hour, rv, date) real hourly boundaries filled with bridges"""
    out = []
    for t0 in d.index[d.index.hour == entry_hour]:
        w = d.loc[t0: t0 + pd.Timedelta(hours=hours - 1)]
        if len(w) < hours or np.isnan(w.rv.iloc[0]): continue
        b = np.r_[w.Open.iloc[0], w.Close.values]; lb = np.log(b); sig_h = w.rv.iloc[0] / np.sqrt(24 * 365)
        for _ in range(draws):
            z = rng.standard_normal((hours, m)) ; seg = []
            for k in range(hours):
                steps = z[k] * sig_h / np.sqrt(m); W = np.cumsum(steps); tt = np.arange(1, m + 1) / m; br = W - tt * W[-1]              # Brownian bridge (zero at both ends)
                seg.append(lb[k] + (lb[k + 1] - lb[k]) * tt + br)
            out.append((np.exp(np.r_[lb[0], np.concatenate(seg)]), w.rv.iloc[0], t0))
    return out
def run(P, markup, cost_pct, stop=10.0, hours=24, m=12, use_stop=True):
    res = []; hits = []
    for S, rv, t0 in P:
        iv = rv * markup; K = S[0]; n = len(S) - 1; Tleft = (hours - np.arange(n + 1) / m) / (24 * 365); p0 = straddle(S[0], K, Tleft[0], iv)
        val = straddle(S[1:-1], K, Tleft[1:-1], iv); hit = use_stop and (val >= p0 * (1 + stop / 100)).any()
        x = p0 * (1 + stop / 100) if hit else abs(S[-1] - K)
        res.append(((p0 - x) - cost_pct / 100 * p0) / K * 100); hits.append(bool(hit))
    run.hits = np.array(hits); return np.array(res), p0
def go(name, f, **kw):
    d = load(f); P = paths(d, **kw); print(f"\n=== {name}: {len(P)//10} real days x 10 bridges, entry {kw.get('entry_hour',12):02d}:00 UTC, {kw.get('hours',24)}h to expiry ===")
    print(f"{'IV / realised':>14s} {'wins':>6s} {'stop hit':>9s} {'avg win':>9s} {'avg loss':>9s} {'avg P&L':>9s} {'per year (365 trades)':>22s} {'NO-stop avg':>12s}")
    for mk in (0.9, 1.0, 1.1, 1.2, 1.3, 1.5):
        xn, _ = run(P, mk, 5, use_stop=False, hours=kw.get('hours', 24)); x, p0 = run(P, mk, 5, hours=kw.get('hours', 24)); w = x > 0
        print(f"{mk:14.1f} {100*w.mean():5.0f}% {100*run.hits.mean():8.0f}% {x[w].mean() if w.any() else 0:8.3f}% {x[~w].mean():8.3f}% {x.mean():8.4f}% {x.mean()*365:20.1f}% {xn.mean():11.4f}%")
    print("  premium (1.0x) = %.2f%% of notional | 10%% stop = %.3f%% of notional | latest spot $%.0f" % (straddle(1.0, 1.0, 1 / 365, P[-1][1]) * 100, straddle(1.0, 1.0, 1 / 365, P[-1][1]) * 10, d.Close.iloc[-1]))
    for c in (5, 10, 20):
        be = next((mk for mk in np.arange(0.9, 1.8, 0.05) if run(P[::3], mk, c, hours=kw.get('hours', 24))[0].mean() >= 0), None); print(f"  break-even IV vs realised at cost {c}% of premium: {'>1.75' if be is None else f'{be:.2f}x'}")
if __name__ == "__main__":
    go("BTC daily option, sell at 12:00 UTC", "cx_btc_1h.csv"); go("ETH daily option, sell at 12:00 UTC", "cx_eth_1h.csv"); go("BTC, sell at 00:00 UTC (12h left, faster decay)", "cx_btc_1h.csv", entry_hour=0, hours=12)
