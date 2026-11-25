"""What would Rs1,05,000 be worth today if run through the daily BTC ATM short straddle (10% stop) over the last ~2 years? MODELLED (see crypto_daily_straddle.py): real BTC hourly paths,
option price = markup x trailing realised vol, stop slippage as % of premium, cost 5% of premium. Daily compounding, trade size = notional equal to current equity (no leverage)."""
import numpy as np, pandas as pd
src = open("crypto_daily_straddle.py").read().split("if __name__")[0]; exec(src)
fx = pd.read_csv("mk_usdinr.csv", index_col=0); fx.index = pd.to_datetime(fx.index.astype(str).str[:10]); fx = fx[~fx.index.duplicated()]
d = load("cx_btc_1h.csv"); P = paths(d); days = sorted({t.normalize() for _, _, t in P}); start, end = days[0], days[-1]
fx0 = fx.Close[fx.index <= start.tz_localize(None)].iloc[-1]; fx1 = fx.Close.iloc[-1]; cap_inr = 105000.0; cap_usd = cap_inr / fx0
btc0 = d.Close[d.index >= start].iloc[0]; btc1 = d.Close.iloc[-1]
print(f"Period {start.date()} -> {end.date()} ({len(days)} daily trades) | USD/INR {fx0:.2f} -> {fx1:.2f} | Rs1,05,000 = ${cap_usd:,.0f} at the start | BTC ${btc0:,.0f} -> ${btc1:,.0f} ({(btc1/btc0-1)*100:+.0f}%)")
bh_usd = cap_usd * btc1 / btc0; print(f"Just HOLDING BTC instead: ${bh_usd:,.0f} = Rs{bh_usd*fx1:,.0f} today ({(bh_usd*fx1/cap_inr-1)*100:+.0f}%)\n")
def equity(mk, slip, lev=1.0, cost=5.0, use_stop=True):
    x, _ = run(P, mk, cost, use_stop=use_stop); h = run.hits if use_stop else np.zeros(len(P), bool)
    p0 = np.array([straddle(S[0], S[0], 1 / 365, rv * mk) / S[0] * 100 for S, rv, t in P]); x = x - h * slip / 100 * p0               # stop fills worse by slip% of premium
    df = pd.DataFrame(dict(day=[t.normalize() for _, _, t in P], x=x)).groupby("day").x.mean()                                      # average of the 10 bridges per real day
    eq = [cap_usd]
    for v in df.values: eq.append(max(eq[-1] * (1 + lev * v / 100), 0.0))
    eq = np.array(eq); dd = (eq / np.maximum.accumulate(eq) - 1).min() * 100; fixed = cap_usd + (lev * cap_usd * df.values / 100).sum()
    return eq[-1], dd, fixed, df.min()
print(f"{'scenario (BTC daily straddle, 10% stop, size = 1x equity)':62s} {'$ now':>9s} {'= Rs today':>12s} {'vs Rs1.05L':>11s} {'worst fall':>11s} {'no-compound Rs':>15s}")
for nm, mk, sl in (("option priced AT recent real vol, stop fills perfectly", 1.0, 0), ("... stop fills 10% of premium worse", 1.0, 10), ("... stop fills 25% worse", 1.0, 25), ("option priced 10% above real vol, 10% worse fills", 1.1, 10), ("option priced 20% above real vol, 25% worse fills", 1.2, 25), ("option priced 10% BELOW real vol, 10% worse fills", 0.9, 10)):
    e, dd, fixed, w = equity(mk, sl); print(f"{nm:62s} ${e:>8,.0f} Rs{e*fx1:>10,.0f} {(e*fx1/cap_inr-1)*100:+9.0f}% {dd:10.0f}% Rs{fixed*fx1:>12,.0f}")
e, dd, fixed, w = equity(1.0, 0, use_stop=False); print(f"{'NO stop at all, priced at real vol':62s} ${e:>8,.0f} Rs{e*fx1:>10,.0f} {(e*fx1/cap_inr-1)*100:+9.0f}% {dd:10.0f}% Rs{fixed*fx1:>12,.0f}   (worst single day {w:.1f}% of notional)")
