"""2-lot iron butterfly (200-pt wings; same payoff as the ITM-wing version in the screenshot) on EVERY expiry day, last 12 months, real hourly paths.
Enter at 9:16-ish open at the ATM strike. Stop-loss = 10% of the premium of the short ATM legs. MODELLED prices (BS + India VIX). 130 qty, cost Rs800/expiry."""
import numpy as np, pandas as pd
import hedged_straddle as H
from intraday_straddle import D, VX, nxt, exs
H.LOT, H.COST = 130, 800; v3 = H.VAR["V3: iron fly (1 straddle + 1 wing pair)"]; EXD = set(exs)
def day_run(sl, exit_f):
    rows = []; span = 6.25 * 3600
    for d, g in H.H1.groupby(H.H1.index.normalize()):
        if d not in D.index or len(g) < 5 or g.index[0].hour != 9 or d not in EXD: continue
        iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        n = 0; t0 = g.index[0]; path = []; last = g.Close.iloc[0]
        for ts, b in g.iterrows():
            f0 = (ts - t0).total_seconds() / span
            if f0 >= exit_f: break
            ln = 3600 / span; pts = [(b.Low, f0 + .33 * ln), (b.High, f0 + .66 * ln)] if b.Close >= b.Open else [(b.High, f0 + .33 * ln), (b.Low, f0 + .66 * ln)]
            path += [(S, (n + 1 - min(f, exit_f)) / 252) for S, f in pts]; last = b.Close
        r = H.trade(g.Open.iloc[0], path, last, d, n, iv, v3, sl, (n + 1 - exit_f) / 252); r["open"] = g.Open.iloc[0]; r["close"] = last; rows.append(r)
    return pd.DataFrame(rows)
end = D.index[-1]; start = end - pd.DateOffset(years=1)
print(f"Window {start.date()} -> {end.date()}\n")
res = {}
for nm, sl, ef in (("A) stop 10%, exit ~2:15 pm", 10, 5 / 6.25), ("B) stop 10%, hold to the close/expiry", 10, 1.0), ("C) NO stop, hold to the close/expiry", None, 1.0)):
    r = day_run(sl, ef); r = r[r.date > start].copy(); res[nm] = r; x = r.pnl; w = x > 0; dd = (x.cumsum() - x.cumsum().cummax()).min()
    print(f"{nm:42s} {len(r)} expiries | WIN {w.sum()} ({100*w.mean():.0f}%) LOSE {(~w).sum()} | stop hit {100*r.hit.mean():.0f}% | avg win Rs{x[w].mean():,.0f} avg loss Rs{x[~w].mean():,.0f} | TOTAL Rs{x.sum():,.0f} | best Rs{x.max():,.0f} worst Rs{x.min():,.0f} | max drawdown Rs{dd:,.0f}")
r = res["A) stop 10%, exit ~2:15 pm"]; r["month"] = r.date.dt.to_period("M")
print("\nA) by month:"); print(r.groupby("month").agg(expiries=("pnl", "size"), wins=("pnl", lambda x: int((x > 0).sum())), total=("pnl", lambda x: round(x.sum()))).T.to_string())
r.drop(columns=["maxloss_pts"]).to_csv("expiry_fly_last_year_A.csv", index=False)
print("\nlast 8 expiries (A):"); print(r.tail(8).assign(date=lambda x: x.date.dt.date)[["date", "open", "close", "pnl", "hit"]].round(0).to_string(index=False))
