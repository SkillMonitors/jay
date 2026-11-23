"""FX: how often does price enter the RED cloud from below and then touch the cloud top? Daily vs 4H vs 2H."""
import numpy as np, pandas as pd, yfinance as yf, os
FX = {"EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X","AUD/USD":"AUDUSD=X","USD/CAD":"USDCAD=X","USD/CHF":"USDCHF=X",
      "NZD/USD":"NZDUSD=X","EUR/JPY":"EURJPY=X","GBP/JPY":"GBPJPY=X","USD/INR":"USDINR=X","EUR/INR":"EURINR=X","GBP/INR":"GBPINR=X","JPY/INR":"JPYINR=X"}
def hourly(n, s):
    f = "fx1h_" + n.replace("/","").lower() + ".csv"
    if not os.path.exists(f):
        d = yf.download(s, period="730d", interval="1h", auto_adjust=False, progress=False); d.columns = d.columns.get_level_values(0)
        d[["Open","High","Low","Close"]].dropna().to_csv(f)
    d = pd.read_csv(f, index_col=0); d.index = pd.to_datetime(d.index.astype(str).str[:19]); return d[~d.index.duplicated()]
def daily(n):
    d = pd.read_csv("mk_" + n.replace("/","").lower() + ".csv", index_col=0); d.index = pd.to_datetime(d.index.astype(str).str[:10]); return d[~d.index.duplicated()]
def rs(d, rule):
    return d.resample(rule).agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
def events(df, maxb):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    A = ((m(9)+m(26))/2).shift(26).values; B = m(52).shift(26).values
    top, bot = np.fmax(A, B), np.fmin(A, B); C, H = df.Close.values, df.High.values; N = len(df); out = []; i = 0
    while i < N - 2:
        i += 1
        if np.isnan(top[i]) or np.isnan(top[i-1]): continue
        if C[i-1] < bot[i-1] and bot[i] <= C[i] <= top[i] and A[i] < B[i]:
            touch = None; closed_below = False
            for k in range(i+1, min(N, i+maxb+1)):
                if C[k] < bot[k]: closed_below = True
                if H[k] >= top[k]: touch = k - i; break
            out.append((touch, closed_below)); i += touch if touch else 1
    return out
if __name__ == "__main__":
    cfg = {"Daily": (None, 60, 24), "4-hour": ("4h", 90, 4), "2-hour": ("2h", 120, 2)}
    tot = {k: [] for k in cfg}; rows = []
    for n, s in FX.items():
        h = hourly(n, s); r = {"pair": n}
        for tf, (rule, maxb, hrs) in cfg.items():
            df = daily(n) if rule is None else rs(h, rule)
            if rule is None: df = df[df.index >= df.index.max() - pd.DateOffset(years=10) - pd.DateOffset(years=1)]
            ev = events(df, maxb); tot[tf] += ev
            t = [e[0] for e in ev if e[0]]; clean = [e for e in ev if e[0] and not e[1]]
            r[tf] = f"{len(ev)} ev | touch {len(t)} ({100*len(t)/max(len(ev),1):.0f}%) | clean {len(clean)} ({100*len(clean)/max(len(ev),1):.0f}%)"
        rows.append(r)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nALL FX PAIRS COMBINED")
    for tf, (rule, maxb, hrs) in cfg.items():
        ev = tot[tf]; t = [e[0] for e in ev if e[0]]; clean = sum(1 for e in ev if e[0] and not e[1])
        print(f"{tf:7s} events {len(ev):4d} | touch top red line {len(t):4d} ({100*len(t)/len(ev):.0f}%) | without any close below cloud {clean:4d} ({100*clean/len(ev):.0f}%) | "
              f"avg {np.mean(t):.1f} bars = {np.mean(t)*hrs:.0f} hrs ({np.mean(t)*hrs/24:.1f} days) | median {np.median(t):.0f} bars = {np.median(t)*hrs:.0f} hrs | within 5 bars {100*sum(x<=5 for x in t)/len(ev):.0f}%")
