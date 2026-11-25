"""The structure in the latest screenshot (all legs qty 130 = 2 lots of 65): BUY 25,200 call, SELL 25,400 call, SELL 25,400 put, (4th leg hidden -> BUY 25,600 put).
= 2-lot iron butterfly, 200-pt wings, built with in-the-money wings. Part 1: payoff from the screenshot prices. Part 2: backtests (modelled prices)."""
import numpy as np, pandas as pd
import hedged_straddle as H
from intraday_straddle import D, exs, bs
# ---- Part 1: payoff from screenshot prices (put 25,600 not visible: extrapolated from 25,500 -> 309.20, 25,550 -> 338.60, i.e. ~ +29.4 per 50)
c25200, c25400, p25400 = 353.55, 244.95, 254.95; p25600 = 338.60 + 29.4; Q = 130
debit = (c25200 - c25400) + (p25600 - p25400)
print(f"SCREENSHOT: debit = {debit:.1f} pts = Rs{debit*Q:,.0f} | payoff at expiry = 200 (anywhere outside 25,200-25,600) up to 400 (exactly 25,400)")
print(f"  max profit {400-debit:.1f} pts = Rs{(400-debit)*Q:,.0f} | max loss {debit-200:.1f} pts = Rs{(debit-200)*Q:,.0f} | break-evens {25400-(400-debit):.0f} to {25400+(400-debit):.0f} (+/-{400-debit:.0f} pts)\n")
# ---- Part 2a: weekly hold-to-expiry, 2 lots, W=200, centre ATM or ATM+50 (the screenshot centres 50 above spot)
VX = pd.read_csv("indiavix.csv", index_col=0); VX.index = pd.to_datetime(VX.index.astype(str).str[:10]); VX = VX.Close[~VX.index.duplicated()].reindex(D.index).ffill()
ex = [e for e in exs if pd.Timestamp("2019-03-01") <= e <= D.index[-1]]
def weekly(off, W=200, Q=130, cost=500):
    rows = []
    for a, b in zip(ex[:-1], ex[1:]):
        S0, ST, iv = D.Close.loc[a], D.Close.loc[b], VX.loc[a] / 100
        if np.isnan(iv): continue
        T = ((b - a).days + .25) / 365; K = round(S0 / 50) * 50 + off
        D_ = (bs(S0, K - W, T, iv, True) - bs(S0, K, T, iv, True)) + (bs(S0, K + W, T, iv, False) - bs(S0, K, T, iv, False))      # buy ITM call + ITM put, sell ATM call+put
        pay = (min(max(ST - (K - W), 0), W) - 0) + min(max((K + W) - ST, 0), W)                                                      # the two debit spreads at expiry
        rows.append(dict(date=a, pnl=(pay - D_) * Q - cost, debit=D_))
    return pd.DataFrame(rows)
print("WEEKLY (buy at previous expiry close, hold to expiry, 403 weeks, 130 qty, Rs500 cost):")
for off, nm in ((0, "centre = nearest strike"), (50, "centre = 50 above (like your screen)")):
    r = weekly(off); w = r.pnl > 0; dd = (r.pnl.cumsum() - r.pnl.cumsum().cummax()).min()
    print(f"  {nm:38s} WIN {100*w.mean():3.0f}% ({w.sum()}/{len(r)}) | avg debit Rs{r.debit.mean()*130:,.0f} | avg win Rs{r.pnl[w].mean():,.0f} avg loss Rs{r.pnl[~w].mean():,.0f} | TOTAL Rs{r.pnl.sum():,.0f} | worst Rs{r.pnl.min():,.0f} | drawdown Rs{dd:,.0f}")
# ---- Part 2b: expiry-day open->close / open->2:15pm with the stop (2 lots, same V3 maths, 130 qty, Rs800 cost)
H.LOT, H.COST = 130, 800; v3 = H.VAR["V3: iron fly (1 straddle + 1 wing pair)"]
print("\nEXPIRY DAYS ONLY, 2 lots, 200-pt wings, 10% stop (modelled):")
H.show(H.run_daily(v3, 10), "10 yrs, hold to close (daily approx)"); H.show(H.run_hourly(v3, 10), "~2 yrs, real hourly path, exit ~2:15pm")
H.show(H.run_daily(v3, None), "10 yrs, hold to close, NO stop")
