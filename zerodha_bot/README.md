# Zerodha Nifty expiry-day iron butterfly bot - PAPER TRADING first

**Paper mode is the default: nothing real is traded.** Written and tested only against a *simulated* market (`tests/`, `demo.py`), never against the real Zerodha API. Not financial advice.

## The trade (what we backtested)
On every Nifty **expiry day** (Tuesday weekly expiry from Sep 2025), at ~09:16:
1. **BUY the two wings first**: call at K+200 and put at K-200 (K = nearest 50 strike to spot). `--style itm` gives your screenshot's version (call K-200, put K+200) - same payoff, more cash, less margin.
2. **SELL the at-the-money call and put at K.**
Size = `sets` x 2 lots on every leg (1 set = 2 lots = 130 qty at lot 65). **Start with 1 set.**
Exit everything (shorts bought back first, then wings sold) on the first of: **stop-loss** (cost to close rises 10% of the premium collected on the short legs) - **max daily loss** (Rs15,000 default) - **time exit 15:15** - **PANIC** - **data failure** (10 missed price updates, uses a market order). If an entry order fails part-way, everything already filled is closed and the bot stops.

## Plain at-the-money SELL straddle with a 10% stop (no wings)
`python bot.py --wing 0 --lots-per-set 1 --sets 1 --sl 10` sells the ATM call and put at 09:16 and buys both back if the combined premium rises 10% above what you collected, at 15:15, on PANIC, or on the 2% account limit. **No wings = unlimited loss on a gap and a large margin requirement**; the stop-loss can fill worse than 10%. Paper trade it first (`python demo.py straddle` shows it on a simulated day).

## Try it right now with NO Zerodha account
```
python -m unittest discover -s tests -v     # 22 offline safety tests
python demo.py            # simulated calm expiry day, exits 3:15
python demo.py stop       # stop-loss firing
python demo.py panic      # you press PANIC at 11:30 - shorts bought back before wings are sold
python demo.py gap        # market jumps through the stop: the loss is bigger than 10% (gap risk)
python demo.py account    # account loses 2% of capital elsewhere -> everything closed, no more trades that day
```

## Real paper trading (real quotes, fake orders)
Needs the paid Kite Connect plan with market data. On YOUR machine (never paste keys into a chat):
```
pip install -r requirements.txt
export KITE_API_KEY=...  KITE_API_SECRET=...          # see .env.example
python login.py                                       # each morning; paste the request_token only into this terminal
export KITE_ACCESS_TOKEN=$(cat .access_token)
python bot.py                                         # start before 09:15 on an expiry day; paper mode
python summary.py                                     # after several expiries: win rate, avg per set, drawdown vs the backtest
```
Every trade is appended to `logs/paper_journal.csv` (centre strike, net credit, reason, gross P&L, estimated costs, est. net).
**Go/no-go rule:** after at least 20-30 expiries compare `python summary.py` with the backtest (~Rs2,700 net per set per expiry, 53-58% wins). If your paper average is far below that, real spreads/slippage are eating the edge - do NOT go live.

## 2% daily account loss limit (kill switch)
If your **whole account's** loss for the day (all positions, realised + unrealised) reaches **2% of `capital`** (default Rs10,00,000 -> Rs20,000), the bot **cancels all orders and closes ALL positions**, refuses to trade again that day, and exits. Change `capital` and `max_daily_loss_pct` in `config.py` (set `capital` to your real trading capital).
There is also a separate **guard** you can run in a second terminal so it protects even your *manual* trades: `python guard.py` (add `--capital 1000000 --pct 2`). After the limit trips it keeps watching until 15:30 and closes anything you open afterwards (`--no-lockout` to disable).
Two limits work together: the bot's own `max_daily_loss` (Rs15,000 for its own position) and this account-wide 2%. Whichever hits first closes everything. Test it: `python demo.py account`.

## Four ways to PANIC (cancel orders, buy back shorts first, then sell wings, retry until verified flat)
1. Browser: http://127.0.0.1:8765 (local only) - big red button + live status.  2. `touch PANIC` in the bot folder.
3. `python panic.py` (type PANIC) or `--yes` - works even if the bot crashed.  4. Ctrl+C in the bot terminal.   Last resort: Zerodha's kill switch / Kite app.
The panic button closes **everything in the account**, not only this bot's trades.

## Live mode (only after paper trading proves itself)
`export LIVE_TRADING=YES_I_UNDERSTAND_THIS_USES_REAL_MONEY`, then `python bot.py --live` (also asks you to type YES). Keep `sets` small; `max_sets` (default 3) is a hard cap.

## Honest limits
* The 2% limit is checked every ~5 seconds from Zerodha's P&L; a sudden gap can take you past 2% before it trips, and it uses the P&L figure Zerodha reports (it excludes brokerage and taxes).
* The backtest used **modelled** option prices; real spreads, slippage and expiry-day price swings can wipe out the small per-trade profit (about 3 points per leg of extra cost would erase it).
* A stop-loss is not a guarantee: a jump past the stop fills at the next price (see `demo.py gap`).
* Zerodha auto-squares MIS positions around 15:20; 15:15 leaves almost no time if a fill is slow - consider `--exit 15:00`.
* Check broker/SEBI rules for API orders (e.g. static IP, algo registration). Keep the bot machine online; if the process dies, positions stay open - use `panic.py` or the Kite app.
* Never put your API key/secret/token in a chat or in git (`.gitignore` already excludes `.env`, `.access_token`, `logs/`, `state/`).
