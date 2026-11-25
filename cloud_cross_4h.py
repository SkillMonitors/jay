"""4-hour chart. LONG when a 4H candle closes ABOVE the cloud (prev close was not), SHORT when it closes BELOW the cloud. STOP = the red line (Kijun-sen).
Variants: (1) trailing: exit when a 4H candle closes back through the Kijun (red line moves with price); (2) fixed: stop at the Kijun level at entry (touch), exit when price closes back inside the cloud.
Last 12 months of ~2 years of 4H data. Rs1,00,000 per index, all-in, compounded, cost 0.05%/trade, no leverage."""
import numpy as np, pandas as pd
IDX = {"Nifty 50": "nifty_50", "Bank Nifty": "bank_nifty", "Sensex": "sensex"}
def rd(p): d = pd.read_csv(p, index_col=0); d.index = pd.to_datetime(d.index.astype(str).str[:19]); return d[~d.index.duplicated()]
def prep(df):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    A = ((m(9) + m(26)) / 2).shift(26).values; B = m(52).shift(26).values
    return dict(K=m(26).values, T=m(9).values, top=np.fmax(A, B), bot=np.fmin(A, B), O=df.Open.values, H=df.High.values, L=df.Low.values, C=df.Close.values)
def run(df, variant, months=12, cost=0.05, sides=("long", "short")):
    d = prep(df); N = len(df); start = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(months=months)).to_datetime64())
    C, K, top, bot, O, H, L = d["C"], d["K"], d["top"], d["bot"], d["O"], d["H"], d["L"]; tr = []; pos = None
    for i in range(max(start, 80), N):
        if pos is not None:
            s, e, j, stp = pos; x = None
            if variant == "trail":
                if (s == 1 and C[i] < K[i]) or (s == -1 and C[i] > K[i]): x = C[i]
            else:
                if (s == 1 and L[i] <= stp) or (s == -1 and H[i] >= stp): x = min(O[i], stp) if s == 1 else max(O[i], stp)
                elif (s == 1 and C[i] < top[i]) or (s == -1 and C[i] > bot[i]): x = C[i]
            if x is None and i == N - 1: x = C[i]; why = "open"
            else: why = "exit"
            if x is not None: tr.append((df.index[j], df.index[i], s, (x/e - 1) * s * 100 - cost, why)); pos = None
        if pos is None and i < N - 1 and not np.isnan(top[i]) and not np.isnan(top[i-1]):
            if "long" in sides and C[i] > top[i] and C[i-1] <= top[i-1] and K[i] < C[i]: pos = (1, C[i], i, K[i])
            elif "short" in sides and C[i] < bot[i] and C[i-1] >= bot[i-1] and K[i] > C[i]: pos = (-1, C[i], i, K[i])
    return pd.DataFrame(tr, columns=["entry", "exit", "side", "ret", "why"]), df.index[start], df.index[-1], C[start], C[-1]
def report(name, t, d0, d1, c0, c1, cap=100000):
    c = t[t.why != "open"]; o = t[t.why == "open"]; allr = t
    eq = cap * np.cumprod(1 + allr.ret.values / 100); curve = np.r_[cap, eq]; dd = (curve / np.maximum.accumulate(curve) - 1).min() * 100
    w = allr[allr.ret > 0]; l = allr[allr.ret <= 0]
    print(f"  {name:11s} {len(allr):3d} trades ({(allr.side==1).sum()}L/{(allr.side==-1).sum()}S) | win {100*(allr.ret>0).mean():3.0f}% | avg win {w.ret.mean() if len(w) else 0:+.2f}% avg loss {l.ret.mean() if len(l) else 0:+.2f}% | "
          f"avg hold {np.mean([(b-a).total_seconds()/86400 for a, b in zip(allr.entry, allr.exit)]):.1f}d | Rs1L -> Rs{eq[-1]:,.0f} ({(eq[-1]/cap-1)*100:+.1f}%) | max drop {dd:.1f}% | buy&hold {(c1/c0-1)*100:+.1f}%" + (f" | last trade still open" if len(o) else ""))
    return allr
for variant, lab in (("trail", "(1) STOP = red line (Kijun), trailing - exit when a 4H candle closes back through it"), ("fixed", "(2) STOP = red line level at entry, exit if price closes back inside the cloud")):
    print(f"\n{lab}")
    for sides, sl in ((("long", "short"), "long+short"), (("long",), "long only"), (("short",), "short only")):
        print(f" -- {sl} --")
        for n, f in IDX.items():
            t, d0, d1, c0, c1 = run(rd(f"ix1h_{f}.csv").resample("4h", offset="9h15min").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna(), variant, sides=sides)
            if len(t): a = report(n, t, d0, d1, c0, c1)
            if variant == "trail" and sl == "long+short" and n == "Nifty 50": print(a.assign(entry=a.entry.dt.strftime("%d-%b %H:%M"), exit=a.exit.dt.strftime("%d-%b %H:%M")).round(2).to_string(index=False))
