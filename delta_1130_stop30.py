"""Same study as delta_1130_2y.py (sell BTC daily ATM straddle 11:30 am IST, square off 5:00 pm IST, 2 years real hourly paths, modelled prices) but with a 30% stop-loss, compared with other stops."""
import numpy as np, pandas as pd
src = open("delta_1130_2y.py").read().split("CAP = 105000.0;")[0]; exec(src)
CAP = 105000.0; fx0 = fx.Close[fx.index <= P[0][2].tz_localize(None).normalize()].iloc[-1]; fx1 = fx.Close.iloc[-1]
def compound(r):
    e = CAP / fx0
    for v in r.pnl.values: e *= (1 + v / 100)
    return e * fx1
print("=== STOP-LOSS COMPARISON (IV 1.0x real vol, cost 5% of premium, stop fills exactly) - fixed Rs1,05,000 per day ===")
print(f"{'stop':>8s} {'wins':>6s} {'stop hit':>9s} {'avg win':>9s} {'avg loss':>10s} {'total Rs':>11s} {'compounded Rs':>14s} {'worst day Rs':>13s} {'worst fall Rs':>14s} {'streak':>7s}")
for nm, st, us in (("10%", 10, True), ("20%", 20, True), ("30%", 30, True), ("50%", 50, True), ("no stop", 0, False)):
    r = simulate(stop=st, use_stop=us); s = stats(r)
    print(f"{nm:>8s} {s['win']:5.0f}% {s['stop']:8.0f}% Rs{s['avg_win']/100*CAP:>6,.0f} Rs{s['avg_loss']/100*CAP:>7,.0f} Rs{s['rs']:>9,.0f} Rs{compound(r):>11,.0f} Rs{s['worst']/100*CAP:>10,.0f} Rs{s['rs_dd']:>11,.0f} {s['streak']:>7d}")
r30 = simulate(stop=30); s = stats(r30)
print(f"\n=== 30% STOP, base case: {s['days']} trades | WIN {s['win']:.0f}% ({int(round(s['win']*s['days']/100))}W/{s['days']-int(round(s['win']*s['days']/100))}L) | stop hit {s['stop']:.0f}% | avg premium Rs{r30.prem.mean()/100*CAP:,.0f}")
print(f"  avg win Rs{s['avg_win']/100*CAP:,.0f} | avg loss Rs{s['avg_loss']/100*CAP:,.0f} (win/loss {abs(s['avg_win']/s['avg_loss']):.1f}x) | profit factor {s['pf']:.2f} | per trade Rs{s['avg']/100*CAP:,.0f} | best Rs{s['best']/100*CAP:,.0f} | worst Rs{s['worst']/100*CAP:,.0f} | longest losing streak {s['streak']} | worst fall Rs{s['rs_dd']:,.0f}")
print(f"  TOTAL 2 years (fixed Rs1.05L/day): Rs{s['rs']:,.0f} | compounded: Rs1,05,000 -> Rs{compound(r30):,.0f}")
q = r30.copy(); q["q"] = q.index.to_period("Q"); g = q.groupby("q"); print("\n  by quarter:"); print(pd.DataFrame(dict(days=g.size(), win_pct=g.pnl.apply(lambda x: 100 * (x > 0).mean()).round(0), stop_pct=g.hit.apply(lambda x: 100 * x.mean()).round(0), Rs=(g.pnl.sum() / 100 * CAP).round(0), worst_day_Rs=(g.pnl.min() / 100 * CAP).round(0))).to_string())
print("\n=== STRESS for the 30% stop vs the 10% stop: total Rs on fixed Rs1.05L (stop fills worse by slip% of premium; IV vs real vol; cost % of premium) ===")
print(f"{'scenario':46s} {'10% stop':>11s} {'30% stop':>11s}")
for mk, sl, c in ((1.0, 0, 5), (1.0, 10, 5), (1.0, 25, 5), (1.1, 10, 5), (0.9, 10, 5), (1.0, 10, 10), (1.0, 10, 20), (0.9, 25, 10)):
    a = stats(simulate(mk, c, sl, stop=10))["rs"]; b = stats(simulate(mk, c, sl, stop=30))["rs"]; print(f"IV {mk:.1f}x | stop slip {sl:2d}% | cost {c:2d}%:".ljust(46) + f" Rs{a:>9,.0f} Rs{b:>9,.0f}")
print("\n10 worst days (30% stop):"); print(r30.nsmallest(10, "pnl")[["pnl", "move", "hit"]].assign(Rs=lambda x: (x.pnl / 100 * CAP).round(0)).round(2).to_string())
r30.to_csv("delta_1130_stop30_trades.csv")
