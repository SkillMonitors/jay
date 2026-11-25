"""Sell a straddle at strikes open+0/50/100/150/200 (e.g. open 21,000 -> 21,000 ... 21,200) at 9:15, stop-loss 10% of the combined premium, exit ~14:15 (close of the 13:15 hourly bar, nearest to 2 pm).
Real hourly price paths (~2 years, Yahoo limit); MODELLED option prices (Black-Scholes, India VIX prior close as IV). Lot 75, cost Rs400 per straddle."""
import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from intraday_straddle import D, VX, nxt, V2, exs
OFFS = [0, 50, 100, 150, 200]; SPAN = 6.25 * 3600; EXIT_F = 5 / 6.25; SL = 10; COST = 400
H1 = pd.read_csv("ix1h_nifty_50.csv", index_col=0); H1.index = pd.to_datetime(H1.index.astype(str).str[:19]); H1 = H1[~H1.index.duplicated()]
EXD = set(exs)
rows = []
for d, g in H1.groupby(H1.index.normalize()):
    if d not in D.index or d not in VX.index or len(g) < 5 or g.index[0].hour != 9: continue
    e = nxt(d); iv = VX.loc[d] / 100
    if e is None or np.isnan(iv): continue
    n = int(((D.index > d) & (D.index <= e)).sum()) if e <= D.index[-1] else max(1, int(np.busday_count(d.date(), e.date())))
    t0 = g.index[0]; S0 = g.Open.iloc[0]; base = round(S0 / 50) * 50
    bars = [(ts, b) for ts, b in g.iterrows() if (ts - t0).total_seconds() < EXIT_F * SPAN]            # bars starting before ~14:15
    exit_bar = bars[-1][1]
    for off in OFFS:
        K = base + off; p0 = V2(S0, K, (n + 1) / 252, iv); hit = False
        for ts, b in bars:
            f0 = (ts - t0).total_seconds() / SPAN; ln = 3600 / SPAN
            for S, ff in ([(b.Low, f0 + .33 * ln), (b.High, f0 + .66 * ln)] if b.Close >= b.Open else [(b.High, f0 + .33 * ln), (b.Low, f0 + .66 * ln)]):
                if V2(S, K, (n + 1 - min(ff, EXIT_F)) / 252, iv) >= p0 * (1 + SL / 100): hit = True; break
            if hit: break
        x = p0 * (1 + SL / 100) if hit else V2(exit_bar.Close, K, (n + 1 - EXIT_F) / 252, iv)
        rows.append(dict(date=d, off=off, expiry_day=(d in EXD), hit=hit, prem=p0, pnl=(p0 - x) * 75 - COST, rng=g.High.max() - g.Low.min(), op_hi=g.High.max() - S0, op_lo=S0 - g.Low.min()))
R = pd.DataFrame(rows); R.to_csv("strike_straddle_results.csv", index=False)
def table(r, title):
    print(f"\n=== {title} ({r.date.nunique()} days, {r.date.min().date()} -> {r.date.max().date()}) ===")
    out = []
    for off, g in r.groupby("off"):
        x = g.pnl; eq = x.cumsum(); out.append(dict(strike=f"open+{off}", win=f"{(x>0).sum()}/{len(x)} ({100*(x>0).mean():.0f}%)", lose=f"{(x<=0).sum()} ({100*(x<=0).mean():.0f}%)", sl_hit=f"{100*g.hit.mean():.0f}%", avg_win=round(x[x>0].mean()) if (x>0).any() else 0, avg_loss=round(x[x<=0].mean()) if (x<=0).any() else 0,
                    total=round(x.sum()), per_day=round(x.mean()), worst=round(x.min()), max_dd=round((eq - eq.cummax()).min())))
    print(pd.DataFrame(out).to_string(index=False)); return pd.DataFrame(out)
T_all = table(R, "ALL trading days"); T_exp = table(R[R.expiry_day], "EXPIRY DAYS only")
sc = R[(R.rng <= 200) & (R.op_lo <= 50)]; T_sc = table(sc, "SCENARIO days: whole-day range <= 200 pts and price never fell >50 below the open (like your 21,000-21,200 example)")
# ---------- graph
fig, ax = plt.subplots(2, 2, figsize=(15, 10)); cols = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e"]
lab = [f"+{o}" for o in OFFS]; w = .38; xs = np.arange(len(OFFS))
wr = lambda r: [100 * (r[r.off == o].pnl > 0).mean() for o in OFFS]; tot = lambda r: [r[r.off == o].pnl.sum() / 1000 for o in OFFS]
a = ax[0, 0]; a.bar(xs - w/2, wr(R), w, label=f"All days ({R.date.nunique()})", color="#4c78a8"); a.bar(xs + w/2, wr(R[R.expiry_day]), w, label=f"Expiry days ({R[R.expiry_day].date.nunique()})", color="#f58518")
a.set_xticks(xs, [f"open{l}" for l in lab]); a.set_ylabel("Winning days, %"); a.set_title("Win rate by strike (stop-loss 10%, exit ~2:15 pm)", loc="left"); a.legend(); a.axhline(50, color="grey", lw=.7, ls="--"); a.set_ylim(0, 100)
for i, v in enumerate(wr(R)): a.text(i - w/2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8)
for i, v in enumerate(wr(R[R.expiry_day])): a.text(i + w/2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8)
a = ax[0, 1]; b1 = a.bar(xs - w/2, tot(R), w, color="#4c78a8", label="All days"); b2 = a.bar(xs + w/2, tot(R[R.expiry_day]), w, color="#f58518", label="Expiry days")
a.set_xticks(xs, [f"open{l}" for l in lab]); a.set_ylabel("Total profit per lot, ₹ thousand"); a.set_title("Total profit by strike (per 75-lot, after ₹400/trade)", loc="left"); a.axhline(0, color="k", lw=.8); a.legend()
for bars_ in (b1, b2):
    for bar in bars_: a.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (3 if bar.get_height() >= 0 else -12), f"{bar.get_height():.0f}", ha="center", fontsize=8)
a = ax[1, 0]
for o, c in zip(OFFS, cols):
    g = R[(R.off == o) & R.expiry_day].sort_values("date"); a.plot(g.date, g.pnl.cumsum() / 1000, color=c, lw=1.6, label=f"open+{o}")
a.set_title("Cumulative profit, expiry days only (₹ thousand per lot)", loc="left"); a.axhline(0, color="k", lw=.8); a.legend(ncol=2, fontsize=8); a.grid(alpha=.25)
a = ax[1, 1]
for o, c in zip(OFFS, cols):
    g = R[R.off == o].sort_values("date"); a.plot(g.date, g.pnl.cumsum() / 1000, color=c, lw=1.4, label=f"open+{o}")
a.set_title("Cumulative profit, all trading days (₹ thousand per lot)", loc="left"); a.axhline(0, color="k", lw=.8); a.legend(ncol=2, fontsize=8); a.grid(alpha=.25)
fig.suptitle("Nifty 50 short straddle at open + 0/50/100/150/200 pts - 9:15 entry, 10% stop-loss, exit ~2:15 pm (modelled option prices, ~2 years)", fontsize=12, x=.01, ha="left")
fig.tight_layout(rect=(0, 0, 1, .96)); fig.savefig("strike_straddle_chart.png", dpi=130); print("\nsaved strike_straddle_chart.png")
