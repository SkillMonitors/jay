"""Nifty 50 ATM straddle (same strike for call+put) every expiry, last 5 years. LONG straddle (buy) and SHORT straddle (sell), held from the previous expiry close to expiry.
MODELLED prices (Black-Scholes, India VIX as IV, r 6.5%), lot 75, cost Rs250 per straddle (2 legs, brokerage+charges+slippage). Weekly expiry Thu->Tue from Sep-2025; monthly = last weekly expiry of each month."""
import numpy as np, pandas as pd
exec(open("nifty_weekly_options.py").read().split("rows = []\nfor s, dp, W")[0])
COST_S = 250
start = D.index[-1] - pd.DateOffset(years=5)
def straddle(ex_list, label):
    out = []
    for a, b in zip(ex_list[:-1], ex_list[1:]):
        if a < start: continue
        S0, ST, iv = D.Close.loc[a], D.Close.loc[b], V.loc[a] / 100; T = ((b - a).days + 0.25) / 365
        K = round(S0 / 50) * 50; prem = bs(S0, K, T, iv, True) + bs(S0, K, T, iv, False); pay = abs(ST - K)
        out.append(dict(date=a, expiry=b, spot=S0, ST=ST, prem=prem, prem_pct=prem / S0 * 100, move=abs(ST - S0), move_pct=abs(ST / S0 - 1) * 100, long_pnl=(pay - prem) * LOT - COST_S, short_pnl=(prem - pay) * LOT - COST_S, vix=iv * 100))
    r = pd.DataFrame(out); r["yr"] = r.date.dt.year; return r
def show(r, col, name):
    x = r[col]; w = (x > 0).sum(); eq = x.cumsum(); dd = (eq - eq.cummax()).min()
    print(f"  {name:14s} trades {len(x):3d} | WIN {w:3d} ({100*w/len(x):.0f}%) LOSE {len(x)-w:3d} | avg win Rs{x[x>0].mean():>7,.0f} avg loss Rs{x[x<=0].mean():>8,.0f} | TOTAL Rs{x.sum():>9,.0f} | avg/trade Rs{x.mean():>6,.0f} | best Rs{x.max():,.0f} worst Rs{x.min():,.0f} | max drawdown Rs{dd:,.0f}")
weekly = straddle(exp, "weekly")
mon = [max(g) for _, g in pd.Series(exp).groupby([e.year * 100 + e.month for e in exp])]; monthly = straddle(mon, "monthly")
print(f"Window: {start.date()} -> {D.index[-1].date()}")
for lab, r in (("WEEKLY expiry (enter at previous expiry close, ~1 week)", weekly), ("MONTHLY expiry (~1 month)", monthly)):
    print(f"\n=== {lab}: {len(r)} expiries | avg premium {r.prem_pct.mean():.2f}% of spot vs avg actual move {r.move_pct.mean():.2f}% | moved more than premium in {100*(r.move > r.prem).mean():.0f}% of expiries ===")
    show(r, "long_pnl", "BUY straddle"); show(r, "short_pnl", "SELL straddle")
    g = r.groupby("yr").agg(n=("long_pnl", "size"), buy_win=("long_pnl", lambda x: round(100*(x>0).mean())), buy_total=("long_pnl", lambda x: round(x.sum())), sell_win=("short_pnl", lambda x: round(100*(x>0).mean())), sell_total=("short_pnl", lambda x: round(x.sum())))
    print(g.to_string())
weekly.to_csv("nifty_straddle_weekly.csv", index=False); monthly.to_csv("nifty_straddle_monthly.csv", index=False)
print("\nworst 4 weeks for the SELLER:", weekly.nsmallest(4, "short_pnl")[["date", "move_pct", "short_pnl"]].assign(date=lambda x: x.date.dt.date).round(1).values.tolist())
