"""Portfolio simulation of the two best stock configs (max 10 concurrent positions, equal weight, compounded, Rs1L) + check on indices."""
import numpy as np, pandas as pd, sys
src = open("stock_search.py").read().split("DATA = ")[0]; exec(src)
DATA = {t: ind(g) for t, g in A.groupby("Ticker")}
CFG = {"A: Dip 6% below Kijun | stop 8% | exit <=20d": ("dip_below_kijun", 6.0, None, 8, 20),
       "B: Dip 6% below Kijun | stop 2xATR | exit <=5d (fastest)": ("dip_below_kijun", 6.0, None, "atr", 5),
       "C: Red-cloud entry (your chart) | stop 2xATR | exit <=5d": ("red_cloud_entry", None, None, "atr", 5),
       "D: Red-cloud entry | stop 8% | exit <=20d": ("red_cloud_entry", None, None, 8, 20)}
def port(name, params, maxpos=10):
    nm, p, tp, stop, hold = params; ev = []
    for t, d in DATA.items():
        s, tg = sig(d, nm, p); nxt = 0
        for i in s:
            if i < nxt or d["idx"][i] < START or i + 1 >= len(d["C"]): continue
            k, r, w = trade(d, i, tg, tp, stop, hold); ev.append((d["idx"][i], d["idx"][k], r*100 - COST, t)); nxt = k + 1
    ev.sort(); eq = 100000.0; open_ = []; taken = 0; curve = []; peak = eq; dd = 0; days = pd.bdate_range(START, A.index.max())
    # process chronologically: realise on exit date
    exits = sorted([(e[1], e) for e in ev], key=lambda x: x[0]); alloc = {}
    import heapq; hp = []; k = 0; capital = eq; eqs = []
    for e in ev:
        while hp and hp[0][0] <= e[0]:
            ex, rr, size = heapq.heappop(hp); capital += size * (1 + rr/100); 
        if len(hp) < maxpos:
            size = (capital + sum(x[2] for x in hp)) / maxpos if False else None
            tot = capital + sum(x[2] for x in hp); size = min(capital, tot / maxpos)
            if size <= 0: continue
            capital -= size; heapq.heappush(hp, (e[1], e[2], size)); taken += 1
        tot = capital + sum(x[2] for x in hp); peak = max(peak, tot); dd = min(dd, tot/peak - 1)
    while hp: ex, rr, size = heapq.heappop(hp); capital += size * (1 + rr/100)
    yrs = 15; cg = ((capital/100000) ** (1/yrs) - 1) * 100
    return len(ev), taken, capital, cg, dd * 100
for nme, prm in CFG.items():
    n, tk, fin, cg, dd = port(nme, prm); print(f"{nme}\n    signals {n} | trades taken (max 10 at once) {tk} | Rs1,00,000 -> Rs{fin:,.0f} in 15y | {cg:.1f}%/yr | max drop (at cost, approx) {dd:.0f}%")
# Nifty-50 equal-weight buy&hold benchmark
bh = np.mean([(d["C"][-1] / d["C"][np.searchsorted(d["idx"].values, START.to_datetime64())]) ** (1/15) - 1 for d in DATA.values()]) * 100
print(f"\nBenchmark: equal-weight buy&hold of the same 48 stocks ~ {bh:.1f}%/yr (survivorship-biased: today's index members)")
