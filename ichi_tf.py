"""Best Ichimoku trend strategy (long: close breaks above cloud; exit on Tenkan/Kijun cross down) across 2H / 4H / Daily (same ~2-year window)."""
import numpy as np, pandas as pd, yfinance as yf, os
from ichi_strats import ind, run, stats
from fx_tf import FX, hourly, rs
IDX = {"Nifty 50":"^NSEI","Sensex":"^BSESN","Bank Nifty":"^NSEBANK"}
def idx_hourly(n, s):
    f = "ix1h_" + n.replace(" ","_").lower() + ".csv"
    if not os.path.exists(f):
        d = yf.download(s, period="730d", interval="1h", auto_adjust=False, progress=False); d.columns = d.columns.get_level_values(0)
        d[["Open","High","Low","Close"]].dropna().to_csv(f)
    d = pd.read_csv(f, index_col=0); d.index = pd.to_datetime(d.index.astype(str).str[:19]); return d[~d.index.duplicated()]
def resample(d, rule, india):
    if rule == "1D": return d.resample("1D").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
    kw = dict(offset="9h15min") if india else {}
    return d.resample(rule, **kw).agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
hrs = {"2h": 2, "4h": 4, "1D": 24}
for grp, mk in (("INDIA", {n: idx_hourly(n, s) for n, s in IDX.items()}), ("FOREX", {n: hourly(n, s) for n, s in FX.items()})):
    print(f"\n=== {grp} (last ~2 years, long, cloud breakout, exit on TK cross down, cost 0.05%) ===")
    for rule in ("2h", "4h", "1D"):
        tot = []; res = []
        for n, h in mk.items():
            df = resample(h, rule, grp == "INDIA"); d = ind(df); N = len(df)
            tr = run(d, ("long",), "cloud breakout", "TK cross down", years=(N - 80) / 252)
            tot += tr
        r = np.array([t[2] for t in tot]); hold = np.mean([t[1]-t[0] for t in tot])
        per = {"2h": (12 if grp == "INDIA" else 12), "4h": 6, "1D": 1}[rule]
        # bars -> real time: India 2h bars ~3.5/day, 4h ~1.75/day; FX 2h 12/day, 4h 6/day
        bpd = {"INDIA": {"2h": 3.4, "4h": 1.8, "1D": 1}, "FOREX": {"2h": 12, "4h": 6, "1D": 1}}[grp][rule]
        eq = np.mean([np.prod(1 + np.array([t[2] for t in run(ind(resample(h, rule, grp == "INDIA")), ("long",), "cloud breakout", "TK cross down", years=(len(resample(h, rule, grp == "INDIA")) - 80) / 252)]) / 100) for h in mk.values()])
        print(f"{rule:3s} trades {len(r):4d} | win {100*(r>0).mean():3.0f}% | avg {r.mean():+.2f}%/trade | avg hold {hold:5.1f} bars = {hold/bpd:5.1f} trading days | avg per-market growth of Rs1L: Rs{100000*eq:,.0f}")
