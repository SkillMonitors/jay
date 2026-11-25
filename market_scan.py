"""Run the daily Ichimoku red-cloud plan on FX / INR currency pairs / Indian indices, last 10y.
LONG : prev close below cloud, close inside a RED cloud, close > Tenkan & Kijun. Target cloud top.
SHORT: mirror (prev close above cloud, close inside GREEN cloud, close < Tenkan & Kijun). Target cloud bottom.
Entry at signal close; stop (fixed % or 2xATR14); time exit after 5 days; cost 0.05% round trip; no leverage."""
import numpy as np, pandas as pd, yfinance as yf, os, sys
MK = {"Nifty 50":"^NSEI","Sensex":"^BSESN","Bank Nifty":"^NSEBANK",
      "USD/INR":"USDINR=X","EUR/INR":"EURINR=X","GBP/INR":"GBPINR=X","JPY/INR":"JPYINR=X",
      "EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X","AUD/USD":"AUDUSD=X",
      "USD/CAD":"USDCAD=X","USD/CHF":"USDCHF=X","NZD/USD":"NZDUSD=X","EUR/JPY":"EURJPY=X","GBP/JPY":"GBPJPY=X"}
def get(name, sym):
    f = "mk_" + name.replace("/","").replace(" ","_").lower() + ".csv"
    if not os.path.exists(f):
        d = yf.download(sym, period="12y", auto_adjust=False, progress=False)
        d.columns = d.columns.get_level_values(0); d[["Open","High","Low","Close"]].dropna().to_csv(f)
    d = pd.read_csv(f, index_col=0); d.index = pd.to_datetime(d.index.astype(str).str[:10]); return d[~d.index.duplicated()]
def backtest(df, stopmode, sides, hold=5, cost=0.05, years=10, confirm=True):
    m = lambda n: (df.High.rolling(n).max() + df.Low.rolling(n).min()) / 2
    T, K = m(9).values, m(26).values; A = ((m(9)+m(26))/2).shift(26).values; B = m(52).shift(26).values
    top, bot = np.fmax(A, B), np.fmin(A, B)
    tr_ = pd.concat([df.High-df.Low, (df.High-df.Close.shift()).abs(), (df.Low-df.Close.shift()).abs()], axis=1).max(axis=1)
    atr = tr_.rolling(14).mean().values
    O, H, L, C = (df[c].values for c in ("Open","High","Low","Close"))
    start = np.searchsorted(df.index.values, (df.index.max() - pd.DateOffset(years=years)).to_datetime64())
    trades = []; i = start
    while i < len(df) - 1:
        i += 1
        if np.isnan(top[i]) or np.isnan(top[i-1]): continue
        side = None
        if "long" in sides and C[i-1] < bot[i-1] and bot[i] <= C[i] <= top[i] and A[i] < B[i] and (not confirm or (C[i] > T[i] and C[i] > K[i])): side = 1
        elif "short" in sides and C[i-1] > top[i-1] and bot[i] <= C[i] <= top[i] and A[i] > B[i] and C[i] < T[i] and C[i] < K[i]: side = -1
        if side is None: continue
        ent = C[i]; sd = (stopmode * ent / 100) if stopmode != "atr" else 2 * atr[i]
        stp = ent - side * sd; ret = None
        for k in range(i+1, min(len(df), i+hold+1)):
            tgt = top[k] if side == 1 else bot[k]
            if (side == 1 and O[k] >= tgt) or (side == -1 and O[k] <= tgt): px = O[k]
            elif (side == 1 and O[k] <= stp) or (side == -1 and O[k] >= stp): px = O[k]
            elif (side == 1 and L[k] <= stp) or (side == -1 and H[k] >= stp): px = stp
            elif (side == 1 and H[k] >= tgt) or (side == -1 and L[k] <= tgt): px = tgt
            else: continue
            ret = side * (px/ent - 1) * 100; break
        else:
            k = min(len(df)-1, i+hold); ret = side * (C[k]/ent - 1) * 100
        trades.append((df.index[i], df.index[k], ret - cost, side)); i = k
    return pd.DataFrame(trades, columns=["entry","exit","ret","side"]), df.index[start], df.index[-1]
def summarize(t, d0, d1, cap=100000):
    if t.empty: return None
    eq = pd.Series(cap * np.cumprod(1 + t.ret.values/100), index=t.exit.values); eq.loc[d0] = cap; eq = eq.sort_index()
    daily = eq.reindex(pd.date_range(d0, d1)).ffill()
    six = (daily.shift(-182) / daily - 1).dropna() * 100
    yrs = (d1 - d0).days / 365.25; dd = (daily / daily.cummax() - 1).min() * 100
    return dict(trades=len(t), per_yr=round(len(t)/yrs,1), win=round(100*(t.ret>0).mean()), avg=round(t.ret.mean(),2), final=round(daily.iloc[-1]),
                cagr=round(((daily.iloc[-1]/cap)**(1/yrs)-1)*100,1), maxdd=round(dd,1), six_med=round(six.median(),1), six_mean=round(six.mean(),1),
                six_p10=round(six.quantile(.1),1), six_worst=round(six.min(),1), six_pos=round(100*(six>0).mean()))
if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    data = {n: get(n, s) for n, s in MK.items()}
    for sides in (("long",), ("long","short")):
        for sm in (1.5, "atr"):
            rows = []
            for n, df in data.items():
                t, a, b = backtest(df, sm, sides); s = summarize(t, a, b)
                if s: rows.append(dict(market=n, **s))
            r = pd.DataFrame(rows).sort_values("cagr", ascending=False)
            print(f"\n##### sides={'+'.join(sides)}  stop={sm}"); print(r.to_string(index=False))
            r.to_csv(f"market_scan_{'_'.join(sides)}_{sm}.csv", index=False)
