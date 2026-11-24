import yfinance as yf, pandas as pd, time
T = "RELIANCE TCS HDFCBANK ICICIBANK INFY HINDUNILVR ITC SBIN BHARTIARTL KOTAKBANK LT AXISBANK ASIANPAINT MARUTI SUNPHARMA TITAN ULTRACEMCO BAJFINANCE NESTLEIND WIPRO HCLTECH M&M NTPC POWERGRID TATAMOTORS TATASTEEL JSWSTEEL ADANIENT ADANIPORTS COALINDIA ONGC BAJAJFINSV TECHM INDUSINDBK DRREDDY CIPLA EICHERMOT HEROMOTOCO BRITANNIA GRASIM HINDALCO BPCL APOLLOHOSP DIVISLAB TATACONSUM SBILIFE HDFCLIFE BAJAJ-AUTO SHRIRAMFIN".split()
frames = []
for i in range(0, len(T), 10):
    b = [t + ".NS" for t in T[i:i+10]]
    d = yf.download(b, period="16y", auto_adjust=True, progress=False, group_by="ticker", threads=False)
    for t in b:
        try:
            x = d[t][["Open","High","Low","Close"]].dropna(); x["Ticker"] = t[:-3]; frames.append(x)
        except Exception as e: print("fail", t, e)
    time.sleep(2)
A = pd.concat(frames); A.index.name = "Date"; A.to_csv("stocks_daily.csv.gz")
print(A.Ticker.nunique(), "stocks", A.index.min().date(), A.index.max().date(), len(A), "rows"); print(A.groupby("Ticker").size().describe())
