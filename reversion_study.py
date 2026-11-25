"""How many days does price take to fall back to its average after being >X% above it?

Usage:  python reversion_study.py prices.csv [--threshold 5] [--years 10]
CSV needs columns: Date, Close  (High, Low optional; needed for Ichimoku Kijun-sen).

"Average" is tested three ways: SMA20, SMA50, Ichimoku Kijun-sen (26-period high/low midpoint).
A signal EPISODE starts on the first day close is > threshold% above the average
(consecutive stretched days are one episode, so results aren't double counted).
Reversion = first later day when close <= the average (that day's value).
"""
import argparse
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument("csv"); p.add_argument("--threshold", type=float, default=5.0)
p.add_argument("--years", type=float, default=10)
a = p.parse_args()

df = pd.read_csv(a.csv, parse_dates=["Date"]).sort_values("Date").set_index("Date")
df = df[df.index >= df.index.max() - pd.DateOffset(years=a.years)] if a.years else df
hi = df["High"] if "High" in df else df["Close"]
lo = df["Low"] if "Low" in df else df["Close"]
avgs = {
    "SMA20": df["Close"].rolling(20).mean(),
    "SMA50": df["Close"].rolling(50).mean(),
    "Kijun26": (hi.rolling(26).max() + lo.rolling(26).min()) / 2,
}
print(f"{len(df)} bars  {df.index[0].date()} -> {df.index[-1].date()}  threshold {a.threshold}%\n")

for name, avg in avgs.items():
    dev = (df["Close"] / avg - 1) * 100
    stretched = dev > a.threshold
    starts = stretched & ~stretched.shift(1, fill_value=False)
    rows = []
    for t in df.index[starts]:
        i = df.index.get_loc(t)
        fut = df["Close"].iloc[i + 1:] <= avg.iloc[i + 1:]
        hit = fut.values.argmax() + 1 if fut.any() else None
        peak = dev.iloc[i: i + (hit or len(df))].max()
        rows.append((t, hit, peak))
    r = pd.DataFrame(rows, columns=["start", "days", "peak_dev"])
    done = r.dropna(subset=["days"])
    print(f"== {name} ==")
    print(f"days stretched >{a.threshold}%: {int(stretched.sum())}   episodes: {len(r)}")
    if len(done):
        d = done["days"]
        print(f"reverted: {len(done)}/{len(r)} ({len(done)/len(r):.0%}); not yet: {len(r)-len(done)}")
        print(f"days to revert  mean {d.mean():.1f}  median {d.median():.0f}  "
              f"p75 {d.quantile(.75):.0f}  p90 {d.quantile(.9):.0f}  max {d.max():.0f}")
        for n in (5, 10, 20):
            print(f"  within {n:>2} days: {(d<=n).mean():.0%}")
        print(f"avg peak stretch before reverting: {done['peak_dev'].mean():.1f}%")
    print()
