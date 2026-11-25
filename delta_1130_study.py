"""STUDY: Delta-Exchange-style BTC daily option. SELL the at-the-money straddle at 11:30 IST (06:00 UTC), SQUARE OFF at ~5:00 pm IST (11:30 UTC; the option expires 5:30 pm IST = 12:00 UTC).
~5 years of REAL 5-minute BTC prices (Binance public data). MODELLED option prices: Black-Scholes, r=0, IV = markup x trailing-30-day realised vol (no historical option quotes are available).
Stop-loss = 10% above the premium collected (checked on every 5-minute candle). Cost = % of premium (fees+spread). Results in % of notional, then Rs for Rs1,05,000."""
import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.special import ndtr
Y = 24 * 365
def strad(S, K, T, v):
    T = np.maximum(T, 1e-12); sq = v * np.sqrt(T); d1 = (np.log(S / K) + .5 * sq ** 2) / sq; d2 = d1 - sq
    return S * ndtr(d1) - K * ndtr(d2) + K * ndtr(-d2) - S * ndtr(-d1)
h = pd.read_csv("btc_1h_5y.csv.gz", index_col=0); h.index = pd.to_datetime(h.index, utc=True); h["rv"] = np.log(h.Close).diff().rolling(720, min_periods=500).std().shift(1) * np.sqrt(Y)
w = pd.read_csv("btc5m_window_5y.csv.gz", index_col=0); w.index = pd.to_datetime(w.index, utc=True)
days = []
for day, g in w.groupby(w.index.normalize()):
    g = g[(g.index >= day + pd.Timedelta(hours=6)) & (g.index < day + pd.Timedelta(hours=11, minutes=30))]
    t0 = day + pd.Timedelta(hours=6)
    if len(g) < 60 or t0 not in h.index or np.isnan(h.rv.loc[t0]): continue
    days.append((day, g, h.rv.loc[t0]))
START, END = days[0][0], days[-1][0]
def simulate(markup=1.0, cost_pct=5.0, slip_pct=0.0, stop=10.0, use_stop=True):
    out = []
    for day, g, rv in days:
        iv = rv * markup; S0 = g.Open.iloc[0]; K = S0; tstart = g.index[0]; Tend = pd.Timestamp(day + pd.Timedelta(hours=12))
        p0 = strad(S0, K, 6 / Y, iv); trig = p0 * (1 + stop / 100); hit = False; x = None; when = None
        if use_stop:
            op, hi, lo, cl = g.Open.values, g.High.values, g.Low.values, g.Close.values; ts = g.index
            for j in range(len(g)):
                vs = [(lo[j], .33), (hi[j], .66)] if cl[j] >= op[j] else [(hi[j], .33), (lo[j], .66)]
                for S, f in vs:
                    t = ts[j] + pd.Timedelta(minutes=5 * f); T = (Tend - t).total_seconds() / 3600 / Y
                    if strad(S, K, T, iv) >= trig: hit = True; x = trig + slip_pct / 100 * p0; when = t; break
                if hit: break
        if not hit: x = strad(g.Close.iloc[-1], K, 0.5 / Y, iv)
        pnl = ((p0 - x) - cost_pct / 100 * p0) / S0 * 100
        out.append(dict(day=day, pnl=pnl, hit=hit, prem=p0 / S0 * 100, move=(g.Close.iloc[-1] / S0 - 1) * 100, rng=(g.High.max() - g.Low.min()) / S0 * 100, S0=S0, exit_ist=(when + pd.Timedelta(minutes=330)).strftime("%H:%M") if hit else "17:00"))
    return pd.DataFrame(out).set_index("day")
def stats(r, cap=105000.0):
    x = r.pnl; wn = x > 0; eq = x.cumsum(); dd = (eq - eq.cummax()).min(); streak = max((len(list(g)) for k, g in __import__("itertools").groupby(wn) if not k), default=0)
    return dict(days=len(r), win=100 * wn.mean(), stop=100 * r.hit.mean(), avg_win=x[wn].mean(), avg_loss=x[~wn].mean(), avg=x.mean(), total=x.sum(), pf=x[wn].sum() / -x[~wn].sum(), best=x.max(), worst=x.min(), dd=dd, streak=streak, rs_total=x.sum() / 100 * cap)
if __name__ == "__main__":
    print(f"{len(days)} daily trades {START.date()} -> {END.date()}")
    base = simulate(); s = stats(base); print("\n=== BASE CASE: IV = 1.0 x realised, cost 5% of premium, stop 10%, exact stop fills ===")
    for k, v in s.items(): print(f"  {k:9s} {v:,.2f}")
    print("\n=== BY YEAR (fixed Rs1,05,000 notional per day, no compounding) ===")
    base["yr"] = base.index.year; g = base.groupby("yr")
    print(pd.DataFrame(dict(days=g.size(), win_pct=g.pnl.apply(lambda x: 100 * (x > 0).mean()).round(0), stop_pct=g.hit.apply(lambda x: 100 * x.mean()).round(0), pnl_pct=g.pnl.sum().round(1), Rs=(g.pnl.sum() / 100 * 105000).round(0), worst_day_pct=g.pnl.min().round(2), btc_move_pct=g.apply(lambda d: (d.S0.iloc[-1] / d.S0.iloc[0] - 1) * 100).round(0))).to_string())
    print("\n=== STRESS (stop fill worse by slip% of premium / IV vs real vol) -> total % of notional over the period, and Rs on Rs1,05,000 fixed ===")
    for mk, sl, c in ((1.0, 0, 5), (1.0, 10, 5), (1.0, 25, 5), (1.1, 10, 5), (0.9, 10, 5), (1.0, 10, 10), (1.0, 10, 20), (1.2, 25, 10)):
        r = simulate(mk, c, sl); s2 = stats(r); print(f"  IV {mk:.1f}x, stop slip {sl:2d}%, cost {c:2d}%: win {s2['win']:3.0f}% | total {s2['total']:7.0f}% | Rs{s2['rs_total']:>12,.0f} | worst day {s2['worst']:.2f}% | drawdown {s2['dd']:.0f}%")
    ns = simulate(use_stop=False); s3 = stats(ns); print(f"  NO STOP, IV 1.0x:   win {s3['win']:3.0f}% | total {s3['total']:7.0f}% | Rs{s3['rs_total']:>12,.0f} | worst day {s3['worst']:.2f}% | drawdown {s3['dd']:.0f}%")
    print("\n=== 10 WORST DAYS (base case) ===")
    print(base.nsmallest(10, "pnl")[["pnl", "move", "rng", "prem", "hit", "exit_ist"]].round(2).to_string())
    print("\n=== BY WEEKDAY (base) ===")
    base["wd"] = base.index.day_name(); print(base.groupby("wd").pnl.agg(["count", "mean", lambda x: 100 * (x > 0).mean()]).rename(columns={"<lambda_0>": "win_pct"}).round(3).to_string())
    base.drop(columns=["yr", "wd"]).to_csv("delta_1130_trades.csv")
    fig, ax = plt.subplots(2, 1, figsize=(13, 8), gridspec_kw=dict(height_ratios=[2, 1])); eq = base.pnl.cumsum() / 100 * 105000
    ax[0].plot(eq.index, eq.values / 1000, color="#1b9e77", lw=1.6, label="Base case (stop fills perfectly)")
    for sl, c, col in ((10, 5, "#d95f02"), (25, 5, "#7570b3")): r = simulate(1.0, c, sl); ax[0].plot(r.index, (r.pnl.cumsum() / 100 * 105000).values / 1000, color=col, lw=1.2, label=f"stop fills {sl}% of premium worse")
    ax[0].axhline(0, color="k", lw=.8); ax[0].set_title("BTC daily straddle: sell 11:30 am IST, square off 5:00 pm IST - cumulative profit (₹ thousand, fixed ₹1,05,000 notional)", loc="left", fontsize=11); ax[0].legend(); ax[0].grid(alpha=.25)
    dd = eq - eq.cummax(); ax[1].fill_between(dd.index, dd.values / 1000, 0, color="#c62828", alpha=.4); ax[1].set_title("Drawdown from peak (₹ thousand), base case", loc="left", fontsize=10); ax[1].grid(alpha=.25)
    fig.tight_layout(); fig.savefig("delta_1130_chart.png", dpi=130); print("\nsaved chart + delta_1130_trades.csv")
