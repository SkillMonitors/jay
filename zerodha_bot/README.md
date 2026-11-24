# Zerodha Nifty straddle bot - with stop-loss and PANIC button

**Paper mode is the default. Nothing real is traded until you deliberately switch to live.**
Not financial advice. Written and tested only against a simulated market (`tests/`), never against the real Zerodha API - read, run in paper mode for weeks, and check every number yourself before using real money.

## What it does
At `entry_time` it sells the at-the-money Nifty call and put (same strike) and exits both legs on the **first** of:
| Trigger | What happens |
|---|---|
| Combined premium to buy back >= entry x (1 + `stop_loss_pct`) (default 10%) | STOP-LOSS: buy back both legs |
| Mark-to-market loss >= `max_daily_loss` rupees | MAX-LOSS exit |
| Clock hits `exit_time` (default 14:15) | TIME exit |
| You press PANIC | cancel all orders, close ALL positions in the account |
| Quote feed fails 10 polls in a row | FAIL-SAFE exit (uses a market order) |
| Only one leg fills at entry | other leg is closed at once, bot stops |
| Any crash / Ctrl+C | emergency square-off, then exits |

## Four ways to panic (all do the same thing: cancel orders, buy back shorts first, then sell any longs, retry until the account is verified flat)
1. **Browser button**: `http://127.0.0.1:8765` (local only) - big red button + live status.
2. **File**: `touch PANIC` in the bot folder.
3. **Second terminal / works even if the bot crashed**: `python panic.py` (type PANIC) or `python panic.py --yes`.
4. **Ctrl+C** in the bot terminal.
Last resort: Zerodha's own kill switch / the Kite app.

## Setup (on YOUR computer or server, not in any chat)
```
pip install -r requirements.txt
export KITE_API_KEY=...  KITE_API_SECRET=...        # from your Kite Connect app; see .env.example
python login.py                                      # every morning; paste the request_token ONLY into this terminal
export KITE_ACCESS_TOKEN=$(cat .access_token)
python bot.py                                        # PAPER: real quotes, fake orders (quotes need the paid Kite Connect data plan)
python -m unittest discover -s tests -v              # offline tests, 13 scenarios
```
Live (only after weeks of paper trading): `export LIVE_TRADING=YES_I_UNDERSTAND_THIS_USES_REAL_MONEY` then `python bot.py --live` (also asks you to type YES).
Useful flags: `--lots 1  --offset 0  --sl 10  --max-loss 5000  --entry 09:16  --exit 14:15  --any-day` (default trades expiry days only).

## Honest limits you must know
* **A stop-loss is not a guarantee.** If the market jumps past the stop between two price checks, you exit at the first available price - the loss can be bigger than 10% (there is a test showing this).
* Stop uses the **ask** price (what you would pay to buy back). Illiquid/wide quotes can trigger it early.
* The backtests behind this strategy used *modelled* option prices. Real fills, spreads and margin will differ. A naked short straddle needs large margin and can lose a lot in one fast move.
* `MIS` positions are auto-squared-off by Zerodha late in the day (extra charges apply if it happens); keep `exit_time` well before that.
* SEBI/broker rules for API order placement (e.g. static IP, algo registration) may apply to you - check Zerodha's current terms.
* The panic button closes **everything** in the account, not just this bot's trades.
* Run it on a machine that stays on and online. If the bot process dies, positions stay open - use `panic.py` or the Kite app.
