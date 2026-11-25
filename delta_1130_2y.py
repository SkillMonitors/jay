"""STUDY (2 years of real BTC hourly prices): SELL the at-the-money BTC straddle at 11:30 am IST (06:00 UTC), SQUARE OFF at ~5:00 pm IST (11:30 UTC). The daily option expires 5:30 pm IST (12:00 UTC).
Each real hour is filled in with a Brownian bridge (12 five-minute steps, 10 random draws per day, averaged) so the 10% stop is checked on a fine path. MODELLED option price: Black-Scholes, r=0, IV = markup x trailing-30-day realised vol.
Stop = 10% above the premium. Cost = % of premium. Results in % of notional, then Rs for Rs1,05,000."""
import numpy as np, pandas as pd, matplotlib, itertools; matplotlib.use("Agg"); import matplotlib.pyplot as plt
src = open("crypto_daily_straddle.py").read().split("def run(")[0]; exec(src)          # straddle, load, paths
d = load("cx_btc_1h.csv"); P = paths(d, entry_hour=6, hours=6, draws=10, m=12); M = 12; EXIT_STEP = int(5.5 * M)                  # 06:00 -> 11:30 UTC = 66 five-minute steps
Y = 24 * 365; fx = pd.read_csv("mk_usdinr.csv", index_col=0); fx.index = pd.to_datetime(fx.index.astype(str).str[:10])
def simulate(markup=1.0, cost_pct=5.0, slip_pct=0.0, stop=10.0, use_stop=True):
    rows = []
    for S, rv, t0 in P:
        iv = rv * markup; K = S[0]; Tleft = (6 - np.arange(len(S)) / M) / Y; p0 = straddle(S[0], K, Tleft[0], iv); trig = p0 * (1 + stop / 100)
        val = straddle(S[1:EXIT_STEP], K, Tleft[1:EXIT_STEP], iv); hit = bool(use_stop and (val >= trig).any())
        x = trig + slip_pct / 100 * p0 if hit else straddle(S[EXIT_STEP], K, Tleft[EXIT_STEP], iv)
        rows.append((t0.normalize(), ((p0 - x) - cost_pct / 100 * p0) / K * 100, hit, p0 / K * 100, (S[EXIT_STEP] / S[0] - 1) * 100, K))
    df = pd.DataFrame(rows, columns=["day", "pnl", "hit", "prem", "move", "S0"]).groupby("day").agg(pnl=("pnl", "mean"), hit=("hit", "mean"), prem=("prem", "mean"), move=("move", "mean"), S0=("S0", "mean")); df.index = df.index.tz_localize(None); return df
def stats(r, cap=105000.0):
    x = r.pnl; w = x > 0; eq = x.cumsum(); dd = (eq - eq.cummax()).min(); streak = max((len(list(g)) for k, g in itertools.groupby(w) if not k), default=0)
    return dict(days=len(r), win=100 * w.mean(), stop=100 * r.hit.mean(), avg_win=x[w].mean(), avg_loss=x[~w].mean(), avg=x.mean(), total=x.sum(), pf=x[w].sum() / -x[~w].sum(), best=x.max(), worst=x.min(), dd=dd, streak=streak, rs=x.sum() / 100 * cap, rs_dd=dd / 100 * cap)
CAP = 105000.0; fx0 = fx.Close[fx.index <= P[0][2].tz_localize(None).normalize()].iloc[-1]; fx1 = fx.Close.iloc[-1]
base = simulate(); s = stats(base); first, last = base.index[0], base.index[-1]
print(f"{len(base)} daily trades, {first.date()} -> {last.date()} (entry 06:00 UTC = 11:30 IST, square-off 11:30 UTC = 5:00 pm IST)\n=== BASE CASE: IV = 1.0 x realised vol, cost 5% of premium, stop 10% (fills exactly), no leverage ===")
print(f"  trades {s['days']} | WIN {s['win']:.0f}% ({int(round(s['win']*s['days']/100))}W / {s['days']-int(round(s['win']*s['days']/100))}L) | stop-loss hit {s['stop']:.0f}% of days | avg premium collected {base.prem.mean():.2f}% of notional (Rs{base.prem.mean()/100*CAP:,.0f} on Rs1.05L)")
print(f"  avg win {s['avg_win']:+.3f}% (Rs{s['avg_win']/100*CAP:,.0f}) | avg loss {s['avg_loss']:+.3f}% (Rs{s['avg_loss']/100*CAP:,.0f}) | win/loss {abs(s['avg_win']/s['avg_loss']):.1f}x | profit factor {s['pf']:.2f} | expectancy {s['avg']:+.3f}% per trade (Rs{s['avg']/100*CAP:,.0f})")
print(f"  best day {s['best']:+.2f}% (Rs{s['best']/100*CAP:,.0f}) | worst day {s['worst']:+.2f}% (Rs{s['worst']/100*CAP:,.0f}) | longest losing streak {s['streak']} days | worst fall from a peak {s['dd']:.1f}% (Rs{s['rs_dd']:,.0f})")
print(f"  TOTAL over 2 years: {s['total']:+.1f}% of notional = Rs{s['rs']:,.0f} on a FIXED Rs1,05,000 per day (no compounding)")
eq = 105000 / fx0; usd_c = eq
for v in base.pnl.values: usd_c *= (1 + v / 100)
print(f"  COMPOUNDED (trade size = whole balance): ${105000/fx0:,.0f} -> ${usd_c:,.0f} = Rs{usd_c*fx1:,.0f} today (USD/INR {fx0:.1f} -> {fx1:.1f}); BTC itself {base.S0.iloc[0]:,.0f} -> {base.S0.iloc[-1]:,.0f}")
q = base.copy(); q["q"] = q.index.to_period("Q"); g = q.groupby("q")
print("\n=== BY QUARTER (fixed Rs1,05,000) ===")
print(pd.DataFrame(dict(days=g.size(), win_pct=g.pnl.apply(lambda x: 100 * (x > 0).mean()).round(0), stop_pct=g.hit.apply(lambda x: 100 * x.mean()).round(0), pnl_pct=g.pnl.sum().round(1), Rs=(g.pnl.sum() / 100 * CAP).round(0), worst_day_pct=g.pnl.min().round(2))).to_string())
print("\n=== STRESS: stop fills worse (% of premium) / option price vs real vol / trading cost -> total Rs on fixed Rs1.05L, win %, worst fall ===")
for mk, sl, c in ((1.0, 0, 5), (1.0, 10, 5), (1.0, 25, 5), (1.1, 10, 5), (0.9, 10, 5), (1.0, 10, 10), (1.0, 10, 20), (1.2, 25, 10), (0.9, 25, 10)):
    r = simulate(mk, c, sl); t = stats(r); print(f"  IV {mk:.1f}x | stop slip {sl:2d}% | cost {c:2d}%:  Rs{t['rs']:>10,.0f} | win {t['win']:3.0f}% | worst day {t['worst']:+.2f}% | worst fall Rs{t['rs_dd']:,.0f}")
ns = simulate(use_stop=False); t = stats(ns); print(f"  NO STOP at all (IV 1.0x):  Rs{t['rs']:>10,.0f} | win {t['win']:3.0f}% | worst day {t['worst']:+.2f}% (Rs{t['worst']/100*CAP:,.0f}) | worst fall Rs{t['rs_dd']:,.0f}")
print("\n=== 10 WORST DAYS (base) ==="); print(base.nsmallest(10, "pnl")[["pnl", "move", "prem", "hit"]].assign(Rs=lambda x: (x.pnl / 100 * CAP).round(0)).round(2).to_string())
print("\n=== 10 BEST DAYS (base) ==="); print(base.nlargest(10, "pnl")[["pnl", "move", "prem", "hit"]].assign(Rs=lambda x: (x.pnl / 100 * CAP).round(0)).round(2).to_string())
wd = base.copy(); wd["wd"] = wd.index.day_name(); print("\n=== BY WEEKDAY ==="); print(wd.groupby("wd").pnl.agg(count="count", avg_pct="mean", win_pct=lambda x: 100 * (x > 0).mean()).round(3).to_string())
base.to_csv("delta_1130_2y_trades.csv")
fig, ax = plt.subplots(2, 1, figsize=(13, 8), gridspec_kw=dict(height_ratios=[2, 1])); cum = base.pnl.cumsum() / 100 * CAP
ax[0].plot(cum.index, cum.values / 1000, color="#1b9e77", lw=1.8, label="Base case (stop fills perfectly)")
for sl, col in ((10, "#d95f02"), (25, "#7570b3")): r = simulate(1.0, 5, sl); ax[0].plot(r.index, (r.pnl.cumsum() / 100 * CAP).values / 1000, color=col, lw=1.2, label=f"stop fills {sl}% of premium worse")
ax[0].plot(ns.index, (ns.pnl.cumsum() / 100 * CAP).values / 1000, color="#999", lw=1, ls="--", label="no stop-loss")
ax[0].axhline(0, color="k", lw=.8); ax[0].set_title("BTC daily straddle: sell 11:30 am IST, square off 5:00 pm IST - cumulative profit (₹ thousand, fixed ₹1,05,000 notional, modelled)", loc="left", fontsize=11); ax[0].legend(); ax[0].grid(alpha=.25)
dd = cum - cum.cummax(); ax[1].fill_between(dd.index, dd.values / 1000, 0, color="#c62828", alpha=.4); ax[1].set_title("Drawdown from peak (₹ thousand), base case", loc="left", fontsize=10); ax[1].grid(alpha=.25)
fig.tight_layout(); fig.savefig("delta_1130_2y_chart.png", dpi=130)
