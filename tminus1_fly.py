"""2-lot iron butterfly (200-pt wings, 130 qty) opened on T-1 (day before expiry) at ~12:15-12:30 and squared off on expiry day at 3:15 pm; compared with opening on expiry morning.
Real hourly paths, last 12 months and ~3 years. MODELLED prices (Black-Scholes, India VIX). Stop = 10% of the premium of the short ATM legs. Cost Rs800 (plus overnight needs NRML margin)."""
import numpy as np, pandas as pd
import hedged_straddle as H
from intraday_straddle import D, VX, exs
Q, COST, SPAN = 130, 800, 6.25 * 3600; EXD = [e for e in exs if e in D.index]
def bar_path(g, t0, iv, base_days, upto_f=None, from_f=0.0):
    """vertices (price, T_years, iv, session_label) for each hourly bar of one day. base_days = full extra trading days after this one."""
    out = []; last = None
    for ts, b in g.iterrows():
        f0 = (ts - t0).total_seconds() / SPAN
        if f0 < from_f - 1e-9: continue
        if upto_f is not None and f0 >= upto_f: break
        ln = 3600 / SPAN; pts = [(b.Low, f0 + .33 * ln), (b.High, f0 + .66 * ln)] if b.Close >= b.Open else [(b.High, f0 + .33 * ln), (b.Low, f0 + .66 * ln)]
        for S, f in pts:
            if upto_f is not None: f = min(f, upto_f)
            out.append((S, (1 - f + base_days) / 252, iv)); 
        last = (b.Close, (1 - min(f0 + ln, upto_f if upto_f else 9) + base_days) / 252)
    return out, last
def run(sl, tminus1=True, exit_f=6 / 6.25):
    rows = []
    for d in EXD:
        if d < pd.Timestamp("2023-12-01"): continue
        gd = H.H1[H.H1.index.normalize() == d]
        if len(gd) < 5 or gd.index[0].hour != 9: continue
        iv_d = VX.loc[d] / 100
        if tminus1:
            p = D.index[D.index < d][-1]; gp = H.H1[H.H1.index.normalize() == p]
            if len(gp) < 5 or gp.index[0].hour != 9: continue
            iv_p = VX.loc[p] / 100; ent = gp[gp.index.hour == 12]
            if ent.empty or np.isnan(iv_p) or np.isnan(iv_d): continue
            t0p = gp.index[0]; f_ent = (ent.index[0] - t0p).total_seconds() / SPAN; S0 = ent.Open.iloc[0]; T0 = (1 - f_ent + 1) / 252; iv0 = iv_p
            path, _ = bar_path(gp, t0p, iv_p, 1, from_f=f_ent)
        else:
            if np.isnan(iv_d): continue
            S0 = gd.Open.iloc[0]; T0 = 1 / 252; iv0 = iv_d; path = []
        pd_, last = bar_path(gd, gd.index[0], iv_d, 0, upto_f=exit_f); path += pd_
        K = round(S0 / 50) * 50; v0, atm0 = H.val(S0, K, T0, iv0, 1, 1); hit = None; x = None
        for S, T, iv in path:
            v, _ = H.val(S, K, T, iv, 1, 1)
            if sl is not None and (v - v0) >= sl / 100 * atm0: x = v0 + sl / 100 * atm0; hit = "T-1 session" if (tminus1 and T > 1.0 / 252 + 1e-9 and False) else "stop"; break
        if x is None: x, _ = H.val(last[0], K, last[1], iv_d, 1, 1)
        rows.append(dict(date=d, hit=hit is not None, pnl=(v0 - x) * Q - COST, credit=v0 * Q, spot=S0))
    return pd.DataFrame(rows)
def show(r, name):
    x = r.pnl; w = x > 0; dd = (x.cumsum() - x.cumsum().cummax()).min()
    print(f"  {name:44s} {len(r):3d} exp | WIN {w.sum():3d} ({100*w.mean():3.0f}%) | stop hit {100*r.hit.mean():3.0f}% | avg win Rs{x[w].mean():>6,.0f} avg loss Rs{x[~w].mean():>7,.0f} | TOTAL Rs{x.sum():>9,.0f} | best Rs{x.max():>7,.0f} worst Rs{x.min():>8,.0f} | drawdown Rs{dd:>8,.0f} | avg credit Rs{r.credit.mean():,.0f}")
end = D.index[-1]
for lab, start in (("LAST 12 MONTHS", end - pd.DateOffset(years=1)), ("ALL HOURLY DATA (~3 yrs)", pd.Timestamp("2000-01-01"))):
    print(f"\n=== {lab} ===")
    for nm, tm1, sl in (("SAME DAY: open ~9:16 -> 3:15 pm, stop 10%", False, 10), ("T-1: open ~12:15 -> expiry 3:15 pm, stop 10%", True, 10), ("T-1: open ~12:15 -> expiry 3:15 pm, NO stop", True, None)):
        r = run(sl, tm1); r = r[r.date > start]; show(r, nm)
r = run(10, True); r = r[r.date > end - pd.DateOffset(years=1)].copy(); r["month"] = r.date.dt.to_period("M"); r.to_csv("tminus1_fly_last_year.csv", index=False)
print("\nT-1 version by month (last 12m):"); print(r.groupby("month").agg(n=("pnl", "size"), wins=("pnl", lambda x: int((x > 0).sum())), total=("pnl", lambda x: round(x.sum()))).T.to_string())
