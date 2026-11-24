"""Long CALL (and PUT) butterfly, 1:2:1, e.g. screenshot: BUY 25,300 / SELL 2x 25,400 / BUY 25,500, 65 qty per lot, ~8 days to expiry.
Part 1: check the screenshot prices against Black-Scholes. Part 2: backtest weekly Nifty expiries 2019-2026 (modelled prices: BS + India VIX, no skew). Hold to expiry (cash settled)."""
import numpy as np, pandas as pd, math
from intraday_straddle import D, VX, exs, bs
LOT, COST = 65, 300
# ---- Part 1: screenshot check
S, T, iv = 25349.65, 8 / 365, 0.165
mk = {25300: (297.00, 205.10), 25400: (244.95, 254.95), 25500: (199.30, 309.20)}
print("SCREENSHOT CHECK (spot 25349.65, 8 days, IV 16.5%):  strike | market call vs model call | market put vs model put")
for k, (c, p) in mk.items(): print(f"   {k}: call {c:7.2f} vs {bs(S, k, T, iv, True):7.2f} | put {p:7.2f} vs {bs(S, k, T, iv, False):7.2f}")
deb_c = mk[25300][0] + mk[25500][0] - 2 * mk[25400][0]; deb_p = mk[25300][1] + mk[25500][1] - 2 * mk[25400][1]
print(f"   call butterfly debit (market) = {deb_c:.2f} pts = Rs{deb_c*LOT:,.0f} per set | put butterfly = {deb_p:.2f} pts | max profit (call) = {100-deb_c:.1f} pts = Rs{(100-deb_c)*LOT:,.0f}")
print(f"   break-evens {25300+deb_c:.1f} to {25500-deb_c:.1f}  (a {(25500-deb_c)-(25300+deb_c):.0f}-point window around 25,400)  | net delta = {0.56-2*0.49+0.43:+.2f} (almost zero: it is NOT a directional bet)\n")
# ---- Part 2: backtest
ex = [e for e in exs if e >= pd.Timestamp("2019-03-01") and e <= D.index[-1]]
def fly(S0, ST, iv, T, K0, W, kind):
    f = (lambda K: bs(S0, K, T, iv, kind == "call")); pay = (lambda K: max(ST - K, 0) if kind == "call" else max(K - ST, 0))
    debit = f(K0 - W) + f(K0 + W) - 2 * f(K0); payoff = pay(K0 - W) + pay(K0 + W) - 2 * pay(K0)
    return debit, payoff
def run(W, off, kind="call"):
    rows = []
    for a, b in zip(ex[:-1], ex[1:]):
        S0, ST, iv = D.Close.loc[a], D.Close.loc[b], VX.reindex(D.index).ffill().loc[a] / 100
        if np.isnan(iv): continue
        T = ((b - a).days + 0.25) / 365; K0 = round(S0 / 50) * 50 + off; deb, pay = fly(S0, ST, iv, T, K0, W, kind)
        rows.append(dict(date=a, debit=deb, payoff=pay, pnl=(pay - deb) * LOT - COST, move=abs(ST - K0)))
    return pd.DataFrame(rows)
VX = pd.read_csv("indiavix.csv", index_col=0); VX.index = pd.to_datetime(VX.index.astype(str).str[:10]); VX = VX.Close[~VX.index.duplicated()]
print(f"BACKTEST: {len(ex)-1} weekly expiries {ex[0].date()} -> {ex[-1].date()}, buy at previous expiry close, hold to expiry, cost Rs{COST}/trade, lot {LOT}")
print(f"{'structure':32s} {'trades':>6s} {'WIN':>6s} {'avg debit':>10s} {'avg win':>9s} {'avg loss':>9s} {'TOTAL':>10s} {'best':>8s} {'return on debit':>16s}")
for kind in ("call", "put"):
    for W in (50, 100, 150, 200):
        for off in (0, 50):
            if kind == "put" and off: continue
            r = run(W, off, kind); w = r.pnl > 0; d = r.debit.mean() * LOT
            print(f"{kind+' fly W'+str(W)+(' centre+50' if off else ' centre ATM'):32s} {len(r):6d} {100*w.mean():5.0f}% Rs{d:>8,.0f} Rs{r.pnl[w].mean():>7,.0f} Rs{r.pnl[~w].mean():>7,.0f} Rs{r.pnl.sum():>9,.0f} Rs{r.pnl.max():>6,.0f} {100*r.pnl.sum()/(r.debit.sum()*LOT):>14.0f}%")
r = run(100, 0); r["yr"] = r.date.dt.year; print("\ncall fly W100 ATM by year:"); print(r.groupby("yr").agg(n=("pnl", "size"), win=("pnl", lambda x: round(100*(x>0).mean())), total=("pnl", lambda x: round(x.sum()))).T.to_string())
print("\nhow often Nifty ended within 100 pts / within the 187-pt break-even window of the centre strike:", f"{100*(r.move<=100).mean():.0f}% / {100*(r.move<=93.6).mean():.0f}%")
r.to_csv("butterfly_w100_trades.csv", index=False)
