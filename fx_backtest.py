"""5-year (daily) / ~2-year (4H, 2H: Yahoo limit) backtest of the red-cloud plan on FX pairs. Rs 1 lakh split equally across pairs."""
import numpy as np, pandas as pd
from market_scan import backtest, get, MK
from fx_tf import FX, hourly, daily, rs
CAP = 100000
cfg = {"Daily (5 yrs)": (None, 5, 5), "4-hour (~2 yrs)": ("4h", 30, 2), "2-hour (~2 yrs)": ("2h", 60, 2)}
def run(confirm, label):
    print(f"\n######## {label} | stop = 2xATR14, exit after 1 trading week, cost 0.05%/trade, long only ########")
    for tf, (rule, hold, yrs) in cfg.items():
        rows = []; fin = 0; allr = []
        for n, s in FX.items():
            df = daily(n) if rule is None else rs(hourly(n, s), rule)
            t, d0, d1 = backtest(df, "atr", ("long",), hold=hold, cost=0.05, years=yrs, confirm=confirm)
            per = CAP / len(FX); end = per * np.prod(1 + t.ret.values / 100) if len(t) else per
            fin += end; allr += list(t.ret.values)
            rows.append((n, len(t), int((t.ret > 0).sum()), end))
        x = np.array(allr); w = (x > 0).sum(); n_ = len(x)
        print(f"{tf:16s} trades {n_:4d} | made money {w:4d} ({100*w/n_:.0f}%) | lost {n_-w:4d} | avg/trade {x.mean():+.3f}% | avg win {x[x>0].mean():+.2f}% avg loss {x[x<=0].mean():+.2f}% "
              f"| Rs1,00,000 -> Rs{fin:,.0f} ({(fin/CAP-1)*100:+.1f}%)")
        best = max(rows, key=lambda r: r[3]); worst = min(rows, key=lambda r: r[3])
        print(f"{'':16s} best pair {best[0]} ({best[1]} trades, {best[2]} wins, Rs1L-equivalent {best[3]*len(FX):,.0f}); worst {worst[0]} ({worst[3]*len(FX):,.0f}); pairs profitable {sum(r[3] > CAP/len(FX) for r in rows)}/{len(FX)}")
run(True, "WITH Tenkan/Kijun confirmation (my plan)")
run(False, "WITHOUT confirmation (pure cloud-entry)")
print("\nReference - Indian indices, daily, 5 years, same plan, equal split:")
ix = ["Nifty 50", "Sensex", "Bank Nifty"]; fin = 0; allr = []
for n in ix:
    t, d0, d1 = backtest(get(n, MK[n]), "atr", ("long",), hold=5, cost=0.05, years=5); fin += CAP/3*np.prod(1+t.ret.values/100); allr += list(t.ret.values)
    print(f"  {n}: {len(t)} trades, {int((t.ret>0).sum())} wins")
print(f"  total {len(allr)} trades, {sum(r>0 for r in allr)} wins -> Rs1,00,000 -> Rs{fin:,.0f}")
