"""All settings in one place. Defaults are deliberately conservative. Change them with command-line flags or by editing here."""
from dataclasses import dataclass


@dataclass
class Config:
    # --- what to trade ---
    underlying: str = "NIFTY"
    spot_symbol: str = "NSE:NIFTY 50"
    strike_step: int = 50          # Nifty strikes are 50 apart
    strike_offset: int = 0         # 0 = at-the-money; +50 = one strike above the open, etc.
    lots: int = 1
    max_lots: int = 2              # hard cap - the bot refuses to trade more than this
    expiry_only: bool = True       # only trade on the nearest expiry day
    product: str = "MIS"           # MIS = intraday (auto square-off by broker), NRML = carry

    # --- when ---
    entry_time: str = "09:16"      # IST (09:15 is the opening auction; the first minute has wide spreads)
    exit_time: str = "14:15"       # IST, forced time exit

    # --- risk ---
    stop_loss_pct: float = 10.0    # exit both legs if the COMBINED premium rises this % above entry
    max_daily_loss: float = 5000.0 # rupees; exit everything if mark-to-market loss reaches this
    max_order_qty: int = 1800      # slice larger orders (Nifty exchange freeze limit is 1800 qty)

    # --- execution ---
    poll_seconds: float = 2.0
    order_buffer_pct: float = 1.0  # how far through the spread a "marketable" limit order is placed
    fill_timeout_s: float = 20.0
    exit_retries: int = 5

    # --- safety / ops ---
    paper: bool = True             # DEFAULT: nothing is sent to the exchange
    dashboard_port: int = 8765     # local-only web page with the panic button (127.0.0.1)
    state_dir: str = "state"
    tag: str = "straddlebot"
