import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from hedged_straddle import *
v = {k: VAR[k] for k in list(VAR)[:3]}; short = {"V1: sell 2 straddles + buy 1 wing pair": "V1  Sell 2 lots ATM straddle + buy 1 lot wings (your idea)", "V3: iron fly (1 straddle + 1 wing pair)": "V3  Classic iron fly (1 : 1)", "V0: plain short straddle (no hedge)": "V0  Plain short straddle (1 lot)"}
col = {"V1": "#d95f02", "V3": "#1b9e77", "V0": "#7570b3"}; fig, ax = plt.subplots(1, 2, figsize=(15, 6)); K = 21000
S = np.arange(20300, 21701, 10); cred = {}
runs = {nm: run_daily(var, 10) for nm, var in v.items()}
for nm, var in v.items():
    a, b, sd = var; c0 = runs[nm].credit.mean() / LOT; cred[nm] = c0
    pts = c0 - (a * np.abs(S - K) - b * (np.maximum(S - K - W, 0) + np.maximum(K - W - S, 0))); ax[0].plot(S, pts * LOT / 1000, color=col[nm[:2]], lw=2.2, label=f"{short[nm]}  (avg premium collected ≈ ₹{c0*LOT/1000:.1f}k)")
ax[0].axhline(0, color="k", lw=.8); ax[0].axvline(K, color="grey", ls=":", lw=1); [ax[0].axvline(K + x, color="grey", ls="--", lw=.6) for x in (-W, W)]
ax[0].set_title("Profit/loss AT EXPIRY if Nifty ends at X (opened 21,000) - no stop-loss", loc="left", fontsize=11); ax[0].set_xlabel("Nifty at expiry"); ax[0].set_ylabel("₹ thousand (per 75-qty lot set)"); ax[0].legend(fontsize=8.5, loc="lower center"); ax[0].grid(alpha=.25)
ax[0].annotate("V1 beyond the wings: still loses\n₹75 per point (1 lot naked on each side)", (21420, ax[0].get_ylim()[0] * .55), fontsize=8.5, color=col["V1"])
for nm, r in runs.items(): ax[1].plot(r.date, r.pnl.cumsum() / 1000, color=col[nm[:2]], lw=1.8, label=short[nm])
ax[1].set_title("Cumulative profit, 10 yrs, expiry days only, 10% stop (modelled)", loc="left", fontsize=11); ax[1].set_ylabel("₹ thousand"); ax[1].legend(fontsize=8.5); ax[1].grid(alpha=.25); ax[1].axhline(0, color="k", lw=.8)
fig.tight_layout(); fig.savefig("hedged_straddle_chart.png", dpi=130); print({k[:2]: round(c * LOT) for k, c in cred.items()})
