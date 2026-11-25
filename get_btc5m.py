"""Download ~5 years of BTCUSDT 5-minute candles from Binance's public market-data host (data-api.binance.vision). Saves
   btc_1h_5y.csv.gz      hourly OHLC (for trailing volatility)
   btc5m_window_5y.csv.gz  5-minute candles between 05:00 and 12:30 UTC only (the trading window we study)"""
import requests, pandas as pd, time, sys
URL = "https://data-api.binance.vision/api/v3/klines"; start = int(pd.Timestamp("2021-10-20", tz="UTC").timestamp() * 1000); end = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
rows = []; t = start; n = 0
while t < end:
    for attempt in range(6):
        try:
            r = requests.get(URL, params=dict(symbol="BTCUSDT", interval="5m", startTime=t, limit=1000), timeout=30); r.raise_for_status(); k = r.json(); break
        except Exception as e: print("retry", attempt, e, file=sys.stderr); time.sleep(2 + attempt * 3)
    else: raise SystemExit("giving up")
    if not k: break
    rows += [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4])) for x in k]; t = k[-1][0] + 300000; n += 1
    if n % 50 == 0: print(n, pd.to_datetime(t, unit="ms"), len(rows), flush=True)
    time.sleep(0.12)
d = pd.DataFrame(rows, columns=["t", "Open", "High", "Low", "Close"]); d["t"] = pd.to_datetime(d.t, unit="ms", utc=True); d = d.drop_duplicates("t").set_index("t")
h = d.resample("1h").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna(); h.to_csv("btc_1h_5y.csv.gz")
w = d[(d.index.hour >= 5) & ((d.index.hour < 12) | ((d.index.hour == 12) & (d.index.minute < 30)))]; w.to_csv("btc5m_window_5y.csv.gz")
print("DONE", len(d), "5m candles", d.index[0], "->", d.index[-1], "| window rows", len(w), "| hourly rows", len(h))
