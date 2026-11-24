"""Monthly Ichimoku RED line (Kijun-sen, 26 months) on gold. Buy Rs10,000 each time price comes DOWN to it (first touch after being above). Hold to today.
Series: (1) GOLDBEES.NS actual (since 2009), (2) gold in INR = COMEX gold x USDINR (20y proxy, spot-like)."""
import numpy as np, pandas as pd
def rd(f): d = pd.read_csv(f, index_col=0); d.index = pd.to_datetime(d.index); return d
gb = rd("gold_goldbees.csv"); gb = gb[gb.Close > 5].copy(); gb.loc[gb.Open <= 0, "Open"] = gb.Close.shift(1).fillna(gb.Close)  # clean bad Yahoo rows (zero opens in 2009-10, 0.3 tick in Dec-2019)
gc = rd("gold_gcf.csv"); fx = rd("gold_usdinr.csv")
inr = gc.join(fx.Close.rename("fx"), how="inner"); fxr = inr.fx
inr = pd.DataFrame({c: gc[c].reindex(fx.index.union(gc.index)).ffill() * fx.Close.reindex(fx.index.union(gc.index)).ffill() / 31.1035 * 10 for c in ("Open","High","Low","Close")}).dropna()
inr = inr[inr.index >= "2003-12-01"]   # INR price per 10g, no import duty/GST
def xirr(cfs):
    t0 = cfs[0][0]; f = lambda r: sum(c / (1 + r) ** ((t - t0).days / 365.25) for t, c in cfs)
    lo, hi = -0.9, 5.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0: lo = mid
        else: hi = mid
    return mid * 100
def study(df, name, mode="touch", amt=10000, tag=""):
    m = df.resample("ME").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
    K = (m.High.rolling(26).max() + m.Low.rolling(26).min()) / 2
    buys = []; armed = False
    for j in range(27, len(m)):
        mo = m.index[j]; prevK = K.iloc[j-1]; above = m.Close.iloc[j-1] > prevK
        if mode == "touch":
            if above: armed = True
            if armed or above:
                days = df[(df.index > m.index[j-1]) & (df.index <= mo)]
                hit = days[days.Low <= prevK]
                if len(hit) and above:
                    r = hit.iloc[0]; px = r.Open if r.Open <= prevK else prevK; buys.append((hit.index[0], px)); 
        else:   # every month that closes below the red line
            if m.Close.iloc[j] < K.iloc[j]: buys.append((mo, m.Close.iloc[j]))
    if not buys: return
    last = df.Close.iloc[-1]; b = pd.DataFrame(buys, columns=["date","px"]); b["ret"] = (last / b.px - 1) * 100; b["yrs"] = (df.index[-1] - b.date).dt.days / 365.25
    units = amt / b.px; invested = amt * len(b); value = (units * last).sum()
    cfs = [(d, -amt) for d in b.date] + [(df.index[-1], value)]
    # fwd 12m
    fw = []
    for d, p in zip(b.date, b.px):
        t = d + pd.DateOffset(years=1)
        if t <= df.index[-1]: fw.append((df.Close[df.index <= t].iloc[-1] / p - 1) * 100)
    # SIP same total money, spread monthly over same span
    ms = m[m.index >= b.date.iloc[0]]; sip = amt * len(b) / len(ms); sip_val = (sip / ms.Close * last).sum()
    lump = invested / df.Close[df.index >= b.date.iloc[0]].iloc[0] * last
    mdd = []
    for d, p in zip(b.date, b.px): mdd.append((df.Low[df.index >= d].min() / p - 1) * 100)
    print(f"\n{name} | {tag} | first buy {b.date.iloc[0].date()} -> last {b.date.iloc[-1].date()} | prices to {df.index[-1].date()}")
    print(f"  buys: {len(b)} (Rs{amt:,} each) | invested Rs{invested:,.0f} -> value today Rs{value:,.0f} | profit Rs{value-invested:,.0f} ({(value/invested-1)*100:.0f}%) | annualised (XIRR) {xirr(cfs):.1f}%/yr")
    print(f"  buys in profit today: {(b.ret>0).sum()}/{len(b)} | median per-buy return {b.ret.median():.0f}% | worst {b.ret.min():.0f}% | avg deepest dip after buying {np.mean(mdd):.0f}% (worst {min(mdd):.0f}%)")
    if fw: print(f"  1 year after each buy: {len(fw)} buys with 12m data | profitable {100*np.mean(np.array(fw)>0):.0f}% | avg +{np.mean(fw):.0f}% | median {np.median(fw):.0f}% | worst {min(fw):.0f}%")
    print(f"  same money as monthly SIP over same period: Rs{sip_val:,.0f} | same money lump-sum on the first buy date: Rs{lump:,.0f}")
    print("  buy dates:", ", ".join(f"{d.strftime('%b-%y')}" for d in b.date))
    return b
for df, nm in ((inr, "Gold in INR (10g, COMEX x USDINR) 20y"), (gb, "GOLDBEES.NS (actual ETF, since 2009)")):
    study(df, nm, "touch", tag="buy on first fall to the monthly red line (Kijun)")
    study(df, nm, "close_below", tag="buy EVERY month that closes below the red line")
