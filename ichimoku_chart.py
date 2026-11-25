"""Full Ichimoku chart (Tenkan, Kijun, Senkou A/B cloud, Chikou) for Sensex, with 1%+ sudden drops below the Kijun marked."""
import sys, numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
NAME, TITLE = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("sensex", "Sensex")
df = pd.read_csv(f"mk_{NAME}.csv", index_col=0); df.index = pd.to_datetime(df.index.astype(str).str[:10]); df = df[~df.index.duplicated()]
mid = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
T, K = mid(9), mid(26); SA, SB = ((T + K) / 2), mid(52)
fut = pd.bdate_range(df.index[-1] + pd.Timedelta(days=1), periods=26)
idx_all = df.index.append(fut)
SAp = pd.Series(np.r_[SA.values, np.full(26, np.nan)], idx_all).shift(26); SBp = pd.Series(np.r_[SB.values, np.full(26, np.nan)], idx_all).shift(26)
SAp = pd.Series(np.r_[SA.values], df.index).reindex(idx_all); SBp = pd.Series(np.r_[SB.values], df.index).reindex(idx_all)
SAp = pd.Series(SAp.values, idx_all).shift(26); SBp = pd.Series(SBp.values, idx_all).shift(26)
chikou = df.Close.shift(-26)
# sudden-drop events (>=1% single day, crosses from above Kijun to below), as in kijun_drop.py
drop = (df.Close / df.Close.shift() - 1) * 100; ev = df.index[(drop <= -1) & (df.Close.shift() >= K.shift()) & (df.Close < K.shift())]
def draw(ax, d0, d1, candles):
    s = slice(d0, d1); x = idx_all[(idx_all >= d0) & (idx_all <= d1)]
    a, b = SAp.reindex(x), SBp.reindex(x)
    ax.fill_between(x, a, b, where=(a >= b), color="#2ca02c", alpha=.18, lw=0, label="Cloud (bullish)")
    ax.fill_between(x, a, b, where=(a < b), color="#d62728", alpha=.18, lw=0, label="Cloud (bearish)")
    ax.plot(x, a, color="#2ca02c", lw=.8, label="Senkou Span A"); ax.plot(x, b, color="#d62728", lw=.8, label="Senkou Span B")
    ax.plot(T[s], color="#1f77b4", lw=1.2, label="Tenkan-sen (9)"); ax.plot(K[s], color="#ff7f0e", lw=1.4, label="Kijun-sen (26) = 50% line")
    ax.plot(chikou[s], color="#7f3fbf", lw=.9, ls="--", label="Chikou span (close, shifted -26)")
    d = df[s]
    if candles:
        up = d.Close >= d.Open
        ax.vlines(d.index, d.Low, d.High, color=np.where(up, "#2e7d32", "#c62828"), lw=.8)
        ax.bar(d.index, (d.Close - d.Open).abs().clip(lower=d.Close.mean()*0.0003), bottom=np.minimum(d.Open, d.Close), width=.7, color=np.where(up, "#2e7d32", "#c62828"))
    else: ax.plot(d.Close, color="black", lw=.8, label="Close")
    e = [t for t in ev if d0 <= t <= d1]; ax.scatter(e, df.Close.reindex(e) * .985, marker="^", s=70 if candles else 28, color="#d4a000", zorder=5, edgecolor="k", lw=.5, label="Sudden drop (>=1%) below Kijun")
    ax.grid(alpha=.25); ax.margins(x=.01)
fig, axs = plt.subplots(2, 1, figsize=(15, 11), gridspec_kw=dict(height_ratios=[1.3, 1]))
draw(axs[0], df.index[-170], idx_all[-1], True); axs[0].set_title(f"{TITLE} - daily Ichimoku Cloud, last ~8 months (cloud projected 26 days ahead)", loc="left", fontsize=13)
draw(axs[1], df.index[-2520], idx_all[-1], False); axs[1].set_title(f"{TITLE} - 10 years", loc="left", fontsize=13)
h, l = axs[0].get_legend_handles_labels(); axs[0].legend(h, l, loc="upper left", fontsize=8.5, ncol=2, framealpha=.9)
for a in axs: a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"{v:,.0f}")); a.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
fig.tight_layout(); fig.savefig(f"{NAME}_ichimoku_chart.png", dpi=130); print("saved", df.index[-1].date(), "close", round(df.Close.iloc[-1]), "T", round(T.iloc[-1]), "K", round(K.iloc[-1]), "cloud now", round(min(SAp.loc[df.index[-1]], SBp.loc[df.index[-1]])), round(max(SAp.loc[df.index[-1]], SBp.loc[df.index[-1]])))
