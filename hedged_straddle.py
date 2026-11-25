"""Hedged straddle study. Open ~21,000: SELL 2 lots ATM call+put (21,000) and BUY 1 lot of the 200-pt-away call (21,200) and put (20,800).
Variants: V1 = that (2 short ATM straddles, 1 long wing pair)   V3 = classic iron fly (1 short straddle + 1 wing pair)   V0 = plain short straddle   V2 = mirror (BUY 2 straddles, SELL 1 wing pair).
MODELLED prices (Black-Scholes, India VIX), lot 75, cost Rs600 per trade (8 orders). Stop-loss = 10% of the GROSS premium of the short ATM legs. Expiry days = nearest expiry day."""
import numpy as np, pandas as pd
from intraday_straddle import D, VX, nxt, exs, bs
LOT, COST, W = 75, 600, 200
EXD = set(exs)
VAR = {"V1: sell 2 straddles + buy 1 wing pair": (2, 1, +1), "V3: iron fly (1 straddle + 1 wing pair)": (1, 1, +1), "V0: plain short straddle (no hedge)": (1, 0, +1), "V2: BUY 2 straddles + sell 1 wing pair": (2, 1, -1)}
def val(S, K, T, iv, a, b):                          # cost to CLOSE the short-straddle book (positive = you owe)
    atm = bs(S, K, T, iv, True) + bs(S, K, T, iv, False); wing = bs(S, K + W, T, iv, True) + bs(S, K - W, T, iv, False)
    return a * atm - b * wing, atm
def trade(open_, path, close, d, n, iv, var, sl, T_close_n):
    a, b, sd = var; K = round(open_ / 50) * 50; T0 = (n + 1) / 252
    v0, atm0 = val(open_, K, T0, iv, a, b); gross = a * atm0; hit = False; x = None
    for S, T in path:
        v, _ = val(S, K, T, iv, a, b)
        if sl is not None and sd * (v - v0) >= sl / 100 * gross: hit = True; x = v0 + sd * sl / 100 * gross; break      # sd*(v-v0) = loss (short) / gain flipped for long
    if not hit: x, _ = val(close, K, T_close_n, iv, a, b)
    pts = sd * (v0 - x); return dict(date=d, hit=hit, pnl=pts * LOT - COST, credit=v0 * LOT, maxloss_pts=None)
def run_daily(var, sl, years=10):                                    # 10y, path approximated from daily OHLC, hold to the close
    rows = []; start = D.index[-1] - pd.DateOffset(years=years)
    for d, r in D[D.index >= start].iterrows():
        if d not in EXD: continue
        e = nxt(d); iv = VX.loc[d] / 100
        if np.isnan(iv): continue
        n = 0                                                        # expiry day
        path_pts = [(r.Low, .33), (r.High, .66)] if r.Close >= r.Open else [(r.High, .33), (r.Low, .66)]
        path = [(S, (n + 1 - f) / 252) for S, f in path_pts]; rows.append(trade(r.Open, path, r.Close, d, n, iv, var, sl, n / 252))
    return pd.DataFrame(rows)
H1 = pd.read_csv("ix1h_nifty_50.csv", index_col=0); H1.index = pd.to_datetime(H1.index.astype(str).str[:19]); H1 = H1[~H1.index.duplicated()]
def run_hourly(var, sl, expiry_only=True):                           # real hourly paths, ~2y, exit ~14:15
    rows = []; span = 6.25 * 3600; EXIT_F = 5 / 6.25
    for d, g in H1.groupby(H1.index.normalize()):
        if d not in D.index or len(g) < 5 or g.index[0].hour != 9 or (expiry_only and d not in EXD): continue
        e = nxt(d); iv = VX.loc[d] / 100
        if e is None or np.isnan(iv): continue
        n = int(((D.index > d) & (D.index <= e)).sum()) if e <= D.index[-1] else max(1, int(np.busday_count(d.date(), e.date())))
        t0 = g.index[0]; path = []
        for ts, b in g.iterrows():
            f0 = (ts - t0).total_seconds() / span
            if f0 >= EXIT_F: break
            ln = 3600 / span; pts = [(b.Low, f0 + .33 * ln), (b.High, f0 + .66 * ln)] if b.Close >= b.Open else [(b.High, f0 + .33 * ln), (b.Low, f0 + .66 * ln)]
            path += [(S, (n + 1 - min(f, EXIT_F)) / 252) for S, f in pts]; last = b.Close
        rows.append(trade(g.Open.iloc[0], path, last, d, n, iv, var, sl, (n + 1 - EXIT_F) / 252))
    return pd.DataFrame(rows)
def show(r, name):
    x = r.pnl; w = x > 0; eq = x.cumsum(); dd = (eq - eq.cummax()).min()
    print(f"  {name:42s} {len(x):3d} days | WIN {100*w.mean():3.0f}% | SL hit {100*r.hit.mean():3.0f}% | avg win Rs{x[w].mean() if w.any() else 0:>6,.0f} avg loss Rs{x[~w].mean() if (~w).any() else 0:>7,.0f} | TOTAL Rs{x.sum():>9,.0f} | worst Rs{x.min():>8,.0f} | max drawdown Rs{dd:>9,.0f}")
if __name__ == "__main__":
    for title, fn, sl in (("A) 10 YEARS, expiry days only, daily-range approximation, hold to the close, stop 10%", lambda v, s: run_daily(v, s), 10),
                          ("B) ~2 YEARS, expiry days only, REAL hourly path, exit ~2:15 pm, stop 10%", lambda v, s: run_hourly(v, s), 10),
                          ("C) ~2 YEARS, ALL trading days, REAL hourly path, exit ~2:15 pm, stop 10%", lambda v, s: run_hourly(v, s, expiry_only=False), 10)):
        print(f"\n=== {title} ==="); 
        for nm, var in VAR.items(): show(fn(var, sl), nm)
    print("\n=== NO STOP-LOSS (A: 10y expiry days) - shows the tail risk of each ===")
    for nm, var in VAR.items(): show(run_daily(var, None), nm)
    r = run_daily(VAR["V1: sell 2 straddles + buy 1 wing pair"], 10); r.to_csv("hedged_straddle_v1_trades.csv", index=False)
    r["yr"] = r.date.dt.year; print("\nV1 by year (A):"); print(r.groupby("yr").agg(n=("pnl", "size"), win=("pnl", lambda x: round(100*(x>0).mean())), total=("pnl", lambda x: round(x.sum())), worst=("pnl", lambda x: round(x.min()))).T.to_string())
