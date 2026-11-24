"""All settings in one place. Defaults match the strategy we tested: expiry-day 2-lot iron butterfly, 200-pt wings, 10% stop, exit 3:15 pm."""
from dataclasses import dataclass


@dataclass
class Config:
    # --- what to trade ---
    underlying: str = "NIFTY"
    spot_symbol: str = "NSE:NIFTY 50"
    strike_step: int = 50
    wing_points: int = 200         # distance of the protective wings; 0 = plain short straddle (NOT recommended: unlimited loss)
    wing_style: str = "otm"        # "otm": buy call K+200 & put K-200 (standard iron fly)   "itm": buy call K-200 & put K+200 (your screenshot) - same payoff, more cash, less margin
    sets: int = 1                  # a SET = lots_per_set lots of every leg. Start with 1 and paper trade.
    lots_per_set: int = 2          # your structure: 2 lots on each of the 4 legs
    max_sets: int = 3              # hard cap - the bot refuses more (raise it deliberately)
    expiry_only: bool = True
    product: str = "MIS"

    # --- when (IST) ---
    entry_time: str = "09:16"
    exit_time: str = "15:15"       # square-off. Zerodha auto-squares MIS ~15:20, so leave a margin or use an earlier time such as 15:00

    # --- risk ---
    stop_loss_pct: float = 10.0    # exit all legs when the cost to close rises by this % of the premium collected on the short ATM legs
    max_daily_loss: float = 15000.0  # rupees, for the WHOLE position; exit everything if the mark-to-market loss reaches this
    max_order_qty: int = 1800

    # --- execution ---
    poll_seconds: float = 2.0
    order_buffer_pct: float = 1.0
    fill_timeout_s: float = 20.0
    exit_retries: int = 5

    # --- ops ---
    paper: bool = True             # DEFAULT: nothing is sent to the exchange
    dashboard_port: int = 8765
    state_dir: str = "state"
    tag: str = "flybot"
    est_cost_per_set: float = 800.0  # rupees per set per expiry, used in the paper journal so results compare with the backtest
