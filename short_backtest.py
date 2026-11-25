"""Short Nifty when close > X% above Ichimoku Kijun-sen; cover when close <= Kijun-sen.
Usage: python short_backtest.py nifty50_daily.csv [threshold_pct ...]"""
import sys, pandas as pd
df = pd.read_csv(sys.argv[1], parse_dates=["Date"]).set_index("Date")
df = df[df.index >= df.index.max() - pd.DateOffset(years=10)]
full = pd.read_csv(sys.argv[1], parse_dates=["Date"]).set_index("Date")
kij = ((full.High.rolling(26).max() + full.Low.rolling(26).min()) / 2).reindex(df.index)
c = df.Close
ths = [float(x) for x in sys.argv[2:]] or [10]
print(f"{df.index[0].date()} -> {df.index[-1].date()}  ({len(df)} days)")
for th in ths:
    dev = (c / kij - 1) * 100
    trades, pos = [], None
    for i, t in enumerate(df.index):
        if pd.isna(kij.iloc[i]): continue
        if pos is None and dev.iloc[i] > th:
            pos = dict(entry_date=t, entry=c.iloc[i], i=i)
        elif pos is not None and c.iloc[i] <= kij.iloc[i]:
            pos.update(exit_date=t, exit=c.iloc[i], open=False); trades.append(pos); pos = None
    if pos: pos.update(exit_date=df.index[-1], exit=c.iloc[-1], open=True); trades.append(pos)
    r = pd.DataFrame(trades)
    print(f"\n=== threshold {th}% above Kijun-sen ===")
    if r.empty: print("no trades"); continue
    r["ret%"] = (r.entry / r.exit - 1) * 100  # short return
    r["days"] = [(df.index.get_loc(e) - x) for e, x in zip(r.exit_date, r.i)]
    r["worst%"] = [-(c.iloc[x:df.index.get_loc(e)+1].max() / en - 1) * 100 for x, e, en in zip(r.i, r.exit_date, r.entry)]
    w = r[r["ret%"] > 0]; l = r[r["ret%"] <= 0]
    print(r[["entry_date","exit_date","entry","exit","days","ret%","worst%","open"]].round(2).to_string(index=False))
    print(f"trades {len(r)}  wins {len(w)}  losses {len(l)}  win rate {len(w)/len(r):.0%}")
    print(f"total return (sum) {r['ret%'].sum():.2f}%  avg/trade {r['ret%'].mean():.2f}%  "
          f"avg win {w['ret%'].mean() if len(w) else 0:.2f}%  avg loss {l['ret%'].mean() if len(l) else 0:.2f}%")
