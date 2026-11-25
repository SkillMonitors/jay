"""2-LOT iron butterfly: SELL 2 lots ATM call + 2 lots ATM put, BUY 2 lots call (K+W) + 2 lots put (K-W). Weekly Nifty expiries 2019-2026, buy at previous expiry close, hold to expiry.
MODELLED prices (Black-Scholes, India VIX). Lot 65, 2 lots = 130 qty, cost Rs500 per trade (8 orders + settlement)."""
import numpy as np, pandas as pd
from intraday_straddle import D, exs, bs
VX = pd.read_csv("indiavix.csv", index_col=0); VX.index = pd.to_datetime(VX.index.astype(str).str[:10]); VX = VX.Close[~VX.index.duplicated()].reindex(D.index).ffill()
LOT, LOTS, COST = 65, 2, 500; Q = LOT * LOTS
ex = [e for e in exs if pd.Timestamp("2019-03-01") <= e <= D.index[-1]]
def run(W):
    rows = []
    for a, b in zip(ex[:-1], ex[1:]):
        S0, ST, iv = D.Close.loc[a], D.Close.loc[b], VX.loc[a] / 100
        if np.isnan(iv): continue
        T = ((b - a).days + 0.25) / 365; K = round(S0 / 50) * 50
        credit = bs(S0, K, T, iv, True) + bs(S0, K, T, iv, False) - bs(S0, K + W, T, iv, True) - bs(S0, K - W, T, iv, False)
        owed = min(abs(ST - K), W)                                    # what the position costs to close at expiry (capped by the wings)
        rows.append(dict(date=a, credit=credit, pts=credit - owed, pnl=(credit - owed) * Q - COST, move=abs(ST - K)))
    return pd.DataFrame(rows)
print(f"{len(ex)-1} weekly expiries {ex[0].date()} -> {ex[-1].date()} | 2 lots = {Q} qty | cost Rs{COST}/trade\n")
print(f"{'wing width':>10s} {'trades':>6s} {'WIN':>5s} {'LOSE':>5s} {'avg credit':>11s} {'max profit':>11s} {'max loss':>9s} {'avg win':>9s} {'avg loss':>9s} {'TOTAL':>11s} {'worst':>9s} {'drawdown':>10s}")
for W in (50, 100, 150, 200):
    r = run(W); w = r.pnl > 0; dd = (r.pnl.cumsum() - r.pnl.cumsum().cummax()).min(); c = r.credit.mean()
    print(f"{W:>10d} {len(r):6d} {100*w.mean():4.0f}% {100*(~w).mean():4.0f}% Rs{c*Q:>9,.0f} Rs{c*Q-COST:>9,.0f} Rs{(W-c)*Q+COST:>7,.0f} Rs{r.pnl[w].mean():>7,.0f} Rs{r.pnl[~w].mean():>7,.0f} Rs{r.pnl.sum():>9,.0f} Rs{r.pnl.min():>7,.0f} Rs{dd:>9,.0f}")
r = run(100); r["yr"] = r.date.dt.year; print("\nWing 100 by year:"); print(r.groupby("yr").agg(n=("pnl", "size"), win=("pnl", lambda x: round(100*(x>0).mean())), total=("pnl", lambda x: round(x.sum()))).T.to_string())
gross = (r.pts * Q).sum(); print(f"\nWing 100: gross before costs Rs{gross:,.0f}; costs Rs{COST*len(r):,.0f}; after costs Rs{r.pnl.sum():,.0f}")
r.to_csv("iron_fly_2lot_w100.csv", index=False)
