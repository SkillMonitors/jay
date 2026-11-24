"""Nifty 50 option spreads on the 4H cloud-cross signals (Kijun stop rule's ENTRY signals).
LONG signal  (4H close above the cloud) -> BULL CALL SPREAD : buy ATM call, sell call +W points (debit).
SHORT signal (4H close below the cloud) -> BEAR CALL SPREAD : sell ATM call, buy call +W points (credit).
Held to expiry (weekly = Tuesday, or monthly = last Tuesday). Option prices MODELLED (Black-Scholes, India VIX as IV, r=6.5%) - no real quotes. Lot 75 assumed. Before brokerage/taxes."""
import numpy as np, pandas as pd, math
exec(open("cloud_cross_4h.py").read().split("for variant, lab in")[0])
LOT = 75
ncdf = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs(S, K, T, v, r=0.065):
    if T <= 0: return max(S - K, 0.0)
    d1 = (math.log(S/K) + (r + v*v/2)*T) / (v*math.sqrt(T)); return S*ncdf(d1) - K*math.exp(-r*T)*ncdf(d1 - v*math.sqrt(T))
D = pd.read_csv("mk_nifty_50.csv", index_col=0); D.index = pd.to_datetime(D.index.astype(str).str[:10]); D = D[~D.index.duplicated()]
V = pd.read_csv("indiavix.csv", index_col=0); V.index = pd.to_datetime(V.index.astype(str).str[:10]); V = V.Close[~V.index.duplicated()]
df4 = rd("ix1h_nifty_50.csv").resample("4h", offset="9h15min").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
sig, d0, d1, _, _ = run(df4, "trail", months=23)
sig = sig[["entry", "side"]].copy(); sig["spot"] = [df4.Close.loc[t] for t in sig.entry]
def expiry(day, kind):
    d = day.normalize()
    if kind == "weekly":
        e = d + pd.Timedelta(days=2)                                   # at least 2 days out
        while e.weekday() != 1: e += pd.Timedelta(days=1)             # Tuesday
    else:
        e = d + pd.Timedelta(days=5)
        while True:
            last = (e + pd.offsets.MonthEnd(0)); last = last - pd.Timedelta(days=(last.weekday() - 1) % 7)   # last Tuesday of that month
            if last >= d + pd.Timedelta(days=5): e = last; break
            e = (e + pd.offsets.MonthEnd(0)) + pd.Timedelta(days=1)
    prev = D.index[D.index <= e]; return prev[-1] if len(prev) else e   # holiday -> previous trading day
def trade(row, kind, W):
    S0, side = row.spot, row.side; ex = expiry(row.entry, kind)
    if ex > D.index[-1]: return None
    iv = (V.reindex([row.entry.normalize()], method="ffill").iloc[0] / 100) if len(V) else 0.14
    T = (ex - row.entry.normalize()).days / 365 + 0.25/365
    K1 = round(S0 / 50) * 50; K2 = K1 + W; ST = D.Close.loc[ex]
    spread0 = bs(S0, K1, T, iv) - bs(S0, K2, T, iv); payoff = max(ST - K1, 0) - max(ST - K2, 0)
    pnl = (payoff - spread0) if side == 1 else (spread0 - payoff)                 # bull call debit / bear call credit
    return dict(entry=row.entry, expiry=ex, side="BULL call spr" if side == 1 else "BEAR call spr", spot=S0, K1=K1, K2=K2, iv=round(iv*100,1), net_premium=round(spread0, 1), ST=round(ST), pnl_pts=round(pnl, 1), pnl_rs=round(pnl * LOT), max_loss_rs=round((spread0 if side == 1 else W - spread0) * LOT))
def summarize(res, label):
    r = pd.DataFrame(res); 
    if r.empty: print(label, "no trades"); return r
    w = r[r.pnl_rs > 0]; l = r[r.pnl_rs <= 0]
    print(f"{label:36s} {len(r):3d} trades | WIN {len(w):3d} ({100*len(w)/len(r):3.0f}%)  LOSE {len(l):3d} | avg win Rs{w.pnl_rs.mean() if len(w) else 0:>7,.0f} avg loss Rs{l.pnl_rs.mean() if len(l) else 0:>8,.0f} | total Rs{r.pnl_rs.sum():>9,.0f} | worst Rs{r.pnl_rs.min():,.0f}")
    return r
print(f"Signals: {len(sig)} four-hour cloud-cross entries {sig.entry.min().date()} -> {sig.entry.max().date()} ({(sig.side==1).sum()} long, {(sig.side==-1).sum()} short)\n")
for kind in ("weekly", "monthly"):
    print(f"=== hold to {kind.upper()} expiry (last ~2 years) ===")
    for W in (100, 200, 300):
        res = [t for t in (trade(r, kind, W) for r in sig.itertuples()) if t]
        r = summarize(res, f"width {W} pts (all)")
        if W == 200:
            for sd in ("BULL call spr", "BEAR call spr"): summarize([x for x in res if x["side"] == sd], f"   {sd}")
            cut = D.index[-1] - pd.DateOffset(months=12); summarize([x for x in res if x["entry"] >= cut], "   last 12 months only")
            pd.DataFrame(res).to_csv(f"nifty_spreads_{kind}.csv", index=False)
            if kind == "weekly": print(pd.DataFrame(res).assign(entry=lambda x: x.entry.dt.strftime("%d-%b-%y %H:%M"), expiry=lambda x: x.expiry.dt.strftime("%d-%b")).tail(14).to_string(index=False))
    print()
