"""Monte-Carlo check of the 1-day ATM short straddle with a 10% premium stop, using FINE intraday paths (5-minute steps of a 24h FX day) - no vertex shortcut.
Spot follows a driftless GBM with REALISED vol sigma_r; the option is SOLD at implied vol = markup x sigma_r. markup = 1.0 is a fair price. Stop fills exactly at +10% (optimistic). Cost = % of premium."""
import numpy as np
from scipy.special import ndtr
rng = np.random.default_rng(7)
def straddle(S, K, T, v):
    sq = v * np.sqrt(T); d1 = (np.log(S / K) + 0.5 * sq ** 2) / sq; d2 = d1 - sq
    return S * ndtr(d1) - K * ndtr(d2) + K * ndtr(-d2) - S * ndtr(-d1)
def sim(sig_r=0.07, markup=1.0, cost_pct=5.0, stop=10.0, n=20000, steps=288, T0=1 / 365, use_stop=True):
    iv = sig_r * markup; dt = T0 / steps; z = rng.standard_normal((n, steps)); logS = np.cumsum(-0.5 * sig_r ** 2 * dt + sig_r * np.sqrt(dt) * z, axis=1); S = np.exp(logS)    # S0 = K = 1
    p0 = straddle(1.0, 1.0, T0, iv); Ts = T0 - dt * np.arange(1, steps + 1); val = straddle(S[:, :-1], 1.0, Ts[:-1][None, :], iv)
    hit = (val >= p0 * (1 + stop / 100)).any(axis=1) if use_stop else np.zeros(n, bool)
    final = np.abs(S[:, -1] - 1.0); x = np.where(hit, p0 * (1 + stop / 100), final)
    pnl = (p0 - x) - cost_pct / 100 * p0; return pnl * 100, hit, p0 * 100
print("EUR/USD-like (realised vol 7%), 1-day ATM short straddle. Expected P&L per trade in % of notional (+ = seller wins):")
print(f"{'IV / realised':>14s} {'stop hit':>9s} {'win rate':>9s} {'avg P&L/trade':>14s} {'per year (252 trades)':>22s} {'with NO stop: per trade':>24s}")
for m in (0.9, 1.0, 1.1, 1.2, 1.3, 1.5):
    p, h, prem = sim(markup=m); pn, _, _ = sim(markup=m, use_stop=False)
    print(f"{m:14.1f} {100*h.mean():8.0f}% {100*(p>0).mean():8.0f}% {p.mean():13.4f}% {p.mean()*252:20.1f}% {pn.mean():22.4f}%")
print(f"\npremium at the open = {prem:.3f}% of notional (1-day, 7% vol)")
print("\nBreak-even option-price markup over realised vol (EUR/USD-like), by cost of trading (as % of premium):")
for c in (0, 5, 10, 20):
    be = next((m for m in np.arange(0.9, 1.6, 0.02) if sim(markup=m, cost_pct=c, n=8000)[0].mean() >= 0), None); print(f"  cost {c:2d}% of premium -> need IV >= {be:.2f} x realised")
print("\nSlippage on the stop (extra fill in % of premium), markup 1.2, cost 5%:")
for sl in (0, 5, 10, 25):
    p, h, _ = sim(markup=1.2); p2 = p - h * sl / 100 * prem; print(f"  stop fills {sl:2d}% of premium worse: avg {p2.mean():+.4f}% per trade = {p2.mean()*252:+.1f}% a year")
