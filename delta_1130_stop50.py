"""Same study (sell BTC daily ATM straddle 11:30 am IST, square off 5:00 pm IST, 2 yrs real hourly paths, modelled prices) with a 50% stop: sold at 200 -> stop when it costs 300 to buy back (loss 100)."""
import numpy as np, pandas as pd
src = open("delta_1130_2y.py").read().split("CAP = 105000.0;")[0]; exec(src)
CAP = 105000.0; fx0 = fx.Close[fx.index <= P[0][2].tz_localize(None).normalize()].iloc[-1]; fx1 = fx.Close.iloc[-1]
def compound(r):
    e = CAP / fx0
    for v in r.pnl.values: e *= (1 + v / 100)
    return e * fx1
r = simulate(stop=50); s = stats(r); nw = int(round(s['win'] * s['days'] / 100))
print(f"=== 50% STOP, base case (IV 1.0x real vol, cost 5% of premium, exact stop fills): {s['days']} trades | WIN {s['win']:.0f}% ({nw}W/{s['days']-nw}L) | stop hit {s['stop']:.0f}% of days | avg premium Rs{r.prem.mean()/100*CAP:,.0f} -> stop distance Rs{r.prem.mean()/100*CAP*.5:,.0f}")
print(f"  avg win Rs{s['avg_win']/100*CAP:,.0f} | avg loss Rs{s['avg_loss']/100*CAP:,.0f} (win/loss {abs(s['avg_win']/s['avg_loss']):.1f}x) | profit factor {s['pf']:.2f} | per trade Rs{s['avg']/100*CAP:,.0f} | best Rs{s['best']/100*CAP:,.0f} | worst Rs{s['worst']/100*CAP:,.0f} | longest losing streak {s['streak']} | worst fall Rs{s['rs_dd']:,.0f}")
print(f"  TOTAL 2 yrs (fixed Rs1.05L/day): Rs{s['rs']:,.0f} | compounded: Rs1,05,000 -> Rs{compound(r):,.0f}")
q = r.copy(); q["q"] = q.index.to_period("Q"); g = q.groupby("q"); print("\n  by quarter:"); print(pd.DataFrame(dict(days=g.size(), win_pct=g.pnl.apply(lambda x: 100 * (x > 0).mean()).round(0), stop_pct=g.hit.apply(lambda x: 100 * x.mean()).round(0), Rs=(g.pnl.sum() / 100 * CAP).round(0), worst_day_Rs=(g.pnl.min() / 100 * CAP).round(0))).to_string())
print("\n=== STRESS: total Rs on fixed Rs1.05L for 10% / 30% / 50% / no stop ===")
print(f"{'scenario':44s} {'10%':>10s} {'30%':>10s} {'50%':>10s} {'no stop':>10s}")
for mk, sl, c in ((1.0, 0, 5), (1.0, 10, 5), (1.0, 25, 5), (1.0, 50, 5), (1.1, 10, 5), (0.9, 10, 5), (1.0, 10, 10), (1.0, 10, 20), (0.9, 25, 10)):
    v = [stats(simulate(mk, c, sl, stop=st))["rs"] for st in (10, 30, 50)]; n = stats(simulate(mk, c, 0, use_stop=False))["rs"]
    print(f"IV {mk:.1f}x | stop slip {sl:2d}% | cost {c:2d}%:".ljust(44) + "".join(f" Rs{x:>8,.0f}" for x in v) + f" Rs{n:>8,.0f}")
print("\n10 worst days (50% stop):"); print(r.nsmallest(10, "pnl")[["pnl", "move", "hit"]].assign(Rs=lambda x: (x.pnl / 100 * CAP).round(0)).round(2).to_string())
r.to_csv("delta_1130_stop50_trades.csv")
