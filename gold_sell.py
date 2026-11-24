"""Gold: buy Rs10,000 on each first fall to the monthly red line (Kijun), then SELL each lot with a rule. Profit shown for COMPLETED trades only (+ open lots listed)."""
import numpy as np, pandas as pd
exec(open("gold_monthly.py").read().split("for df, nm in")[0])
def buys_of(df):
    m = df.resample("ME").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
    K = (m.High.rolling(26).max() + m.Low.rolling(26).min()) / 2; out = []
    for j in range(27, len(m)):
        prevK = K.iloc[j-1]
        if m.Close.iloc[j-1] > prevK:
            days = df[(df.index > m.index[j-1]) & (df.index <= m.index[j])]; hit = days[days.Low <= prevK]
            if len(hit): r = hit.iloc[0]; out.append((hit.index[0], r.Open if r.Open <= prevK else prevK))
    return out, m, K
def run(df, name, rule, val, stop=None, amt=10000):
    buys, m, K = buys_of(df); done = []; open_ = []
    for d, px in buys:
        fut = df[df.index > d]; sold = None
        for t, r in fut.iterrows():
            if stop and r.Low <= px * (1 - stop/100): sold = (t, px * (1 - stop/100)); break
            if rule == "tp" and r.High >= px * (1 + val/100): sold = (t, max(px * (1 + val/100), r.Open if r.Open > px*(1+val/100) else 0)); break
            if rule == "stretch":   # sell when price is val% above the monthly red line (Kijun as of last completed month)
                mm = m[m.index < t]; 
                if len(mm) >= 26:
                    kk = (mm.High.iloc[-26:].max() + mm.Low.iloc[-26:].min()) / 2
                    if r.High >= kk * (1 + val/100): sold = (t, max(kk * (1 + val/100), r.Open) if r.Open > kk*(1+val/100) else kk*(1+val/100)); break
        if sold: done.append((d, px, sold[0], sold[1]))
        else: open_.append((d, px))
    D = pd.DataFrame(done, columns=["buy","bpx","sell","spx"]); 
    if D.empty: print(f"{name} | {rule} {val}% stop {stop}: no completed trades"); return
    D["ret"] = (D.spx / D.bpx - 1) * 100; D["yrs"] = (D.sell - D.buy).dt.days / 365.25; profit = (amt * D.ret / 100).sum()
    cfs = sorted([(b, -amt) for b in D.buy] + [(s, amt * (1 + r/100)) for s, r in zip(D.sell, D.ret)], key=lambda x: x[0])
    ou = sum(amt * (df.Close.iloc[-1] / p - 1) for _, p in open_)
    print(f"{name:22s} sell={rule}{'+' if rule=='tp' else ''}{val}%{' stop '+str(stop)+'%' if stop else '':>10s} | completed {len(D):2d}/{len(buys)} win {100*(D.ret>0).mean():3.0f}% | avg {D.ret.mean():+5.1f}% in {D.yrs.mean():.1f}y | profit on completed Rs{profit:>8,.0f} | XIRR {xirr(cfs):5.1f}% | still open {len(open_)} lots (unrealised Rs{ou:,.0f})")
    return D
for df, nm in ((inr, "Gold INR (20y proxy)"), (gb, "GOLDBEES (actual)")):
    for rule, val, stop in (("tp", 10, None), ("tp", 15, None), ("tp", 20, None), ("tp", 30, None), ("tp", 50, None), ("stretch", 10, None), ("stretch", 15, None), ("tp", 20, 15)):
        D = run(df, nm, rule, val, stop)
    print()
D = run(gb, "GOLDBEES (actual)", "tp", 20)
print(D.assign(buy=D.buy.dt.date, sell=D.sell.dt.date).round(1).to_string(index=False))
