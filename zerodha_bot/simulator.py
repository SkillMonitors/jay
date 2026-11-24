"""Fake market + fake clock for tests and `demo.py`. No network, no Zerodha."""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from broker import OptionPair

IST = ZoneInfo("Asia/Kolkata"); DAY = date(2026, 11, 24)


class Sim:
    """`scenario(minutes_since_915, base) -> ATM premium`. Wing prices are derived from the ATM premium by strike distance."""
    def __init__(self, scenario, start_hhmm=(9, 10), centre=21000):
        self.t = datetime(2026, 11, 24, *start_hhmm, tzinfo=IST); self.scenario = scenario; self.centre = centre
    def now(self): return self.t
    def sleep(self, s): self.t += timedelta(seconds=s)
    def spot(self, sym): return self.centre + 12.0
    def find_option_pair(self, u, strike, today): return OptionPair(f"NIFTY{strike}CE", f"NIFTY{strike}PE", 65, DAY, strike)
    def nearest_expiry(self, u, today): return DAY
    def _price(self, sym):
        m = (self.t - self.t.replace(hour=9, minute=15, second=0)).total_seconds() / 60; base = self.scenario(m)
        k = int(re.findall(r"\d+", sym)[0]); typ = sym[-2:]
        if k == self.centre: f = 1.0
        elif (typ == "CE" and k < self.centre) or (typ == "PE" and k > self.centre): f = 2.2        # in-the-money wing: intrinsic + time value
        else: f = 0.45                                                                               # out-of-the-money wing
        return max(base * f, 0.05)
    def quotes(self, syms): return {s: dict(ltp=self._price(s), bid=self._price(s) - 0.25, ask=self._price(s) + 0.25) for s in syms}


calm = lambda m: 100 - 0.01 * m                                      # slow theta decay
spike = lambda m: 100 - 0.01 * m if m < 120 else 98.8 + 1.0 * (m - 120)   # from 11:15 premiums climb 1 pt/min -> stop is crossed gradually
gap = lambda m: 100 - 0.01 * m if m < 120 else 140                    # instant jump: shows gap risk
crawl = lambda m: 100 + 0.05 * m                                     # steady loss -> max-daily-loss path
