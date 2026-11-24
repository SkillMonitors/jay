"""Offline tests against a simulated market. Nothing here can reach Zerodha. Run:  python -m unittest discover -s tests -v"""
import os, sys, tempfile, unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import Bot
from broker import OptionPair, PaperBroker, make_broker
from config import Config
from squareoff import square_off_all

IST = ZoneInfo("Asia/Kolkata"); DAY = date(2026, 11, 24)


class Sim:
    """Fake market + fake clock. `scenario(minutes_since_915, symbol) -> premium`."""
    def __init__(self, scenario, start_hhmm=(9, 10)):
        self.t = datetime(2026, 11, 24, *start_hhmm, tzinfo=IST); self.scenario = scenario
    def now(self): return self.t
    def sleep(self, s): self.t += timedelta(seconds=s)
    def spot(self, sym): return 21012.0
    def find_option_pair(self, u, strike, today): return OptionPair(f"NIFTY{strike}CE", f"NIFTY{strike}PE", 75, DAY, strike)
    def nearest_expiry(self, u, today): return DAY
    def quotes(self, syms):
        m = (self.t - self.t.replace(hour=9, minute=15, second=0)).total_seconds() / 60
        return {s: dict(ltp=self.scenario(m, s), bid=self.scenario(m, s) - 0.25, ask=self.scenario(m, s) + 0.25) for s in syms}


calm = lambda m, s: 100 - 0.01 * m                                   # slow theta decay, stays far from the stop
spike = lambda m, s: 100 - 0.01 * m if m < 120 else 98.8 + 1.0 * (m - 120)   # from 11:15 each leg rises 1 pt/min -> stop (~+10%) is crossed gradually
gap = lambda m, s: 100 - 0.01 * m if m < 120 else 140                        # instant jump: stop cannot fill at 10% (gap risk)
crawl = lambda m, s: 100 + 0.05 * m                                  # steady loss -> max-daily-loss path


class RejectPE(PaperBroker):
    def place(self, symbol, side, qty, price=None, order_type="LIMIT"):
        if symbol.endswith("PE") and side == "SELL":
            oid = f"REJ{len(self.orders)+1}"; self.orders[oid] = dict(status="REJECTED", filled=0, avg=0.0); return oid
        return super().place(symbol, side, qty, price, order_type)


class FlakyPaper(PaperBroker):
    """LIMIT buy-backs sit unfilled for the first two attempts; MARKET always fills. Proves the retry/escalation path."""
    def __init__(self, *a, **k): super().__init__(*a, **k); self.limit_calls = 0
    def place(self, symbol, side, qty, price=None, order_type="LIMIT"):
        if order_type == "LIMIT" and self.limit_calls < 2:
            self.limit_calls += 1; oid = f"OPEN{len(self.orders)+1}"; self.orders[oid] = dict(status="OPEN", filled=0, avg=0.0); self.placed_log.append((symbol, side, qty, price, order_type, "OPEN")); return oid
        return super().place(symbol, side, qty, price, order_type)


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(); self.old = os.getcwd(); os.chdir(self.d.name)
    def tearDown(self): os.chdir(self.old); self.d.cleanup()

    def mk(self, scenario, cls=PaperBroker, **cfg):
        sim = Sim(scenario); cfg.setdefault("stop_loss_pct", 10.0); c = Config(**cfg); b = cls(sim); logs = []
        bot = Bot(b, c, now_fn=sim.now, sleep_fn=sim.sleep, log=logs.append); return sim, b, bot, logs

    def flat(self, b): return all(p["quantity"] == 0 for p in b.positions())

    def test_calm_day_time_exit_and_flat(self):
        sim, b, bot, logs = self.mk(calm); r = bot.run()
        self.assertEqual(r["reason"], "time_exit"); self.assertTrue(self.flat(b)); self.assertEqual(b.live_orders_sent, 0)
        self.assertTrue(any("sold 75/75 NIFTY21000CE" in l for l in logs)); self.assertGreaterEqual(sim.now().hour * 60 + sim.now().minute, 14 * 60 + 15)

    def test_stop_loss_hits_and_limits_loss(self):
        sim, b, bot, logs = self.mk(spike); r = bot.run()
        self.assertEqual(r["reason"], "stop_loss"); self.assertTrue(self.flat(b))
        pnl = sum(p["pnl"] for p in b.positions()); entry = 2 * (100 - 0.01 * 1 - 0.25)                 # sold ~ at bid
        self.assertGreater(pnl, -0.20 * entry * 75, "loss must stay near the 10% stop, not run away")  # 10% stop + a little slippage

    def test_gap_through_stop_is_honest_about_gap_risk(self):
        sim, b, bot, logs = self.mk(gap); r = bot.run()
        self.assertEqual(r["reason"], "stop_loss"); self.assertTrue(self.flat(b))
        self.assertLess(sum(p["pnl"] for p in b.positions()), -0.25 * 2 * 99 * 75)   # a jump past the stop costs MORE than 10% - the bot exits at the first chance, it cannot avoid gaps

    def test_panic_mid_day_flattens_account(self):
        sim, b, bot, logs = self.mk(calm)
        orig = sim.sleep
        def sleeper(s):
            orig(s)
            if sim.now().hour == 11 and sim.now().minute >= 30: bot.panic.set()
        bot.sleep = sleeper; r = bot.run()
        self.assertEqual(r["reason"], "panic"); self.assertTrue(self.flat(b)); self.assertLess(sim.now().hour, 12)

    def test_panic_file(self):
        sim, b, bot, logs = self.mk(calm); orig = sim.sleep
        def sleeper(s):
            orig(s)
            if sim.now().hour == 10 and not os.path.exists("created"): open("PANIC", "w").close(); open("created", "w").close()
        bot.sleep = sleeper; r = bot.run()
        self.assertEqual(r["reason"], "panic"); self.assertTrue(self.flat(b)); self.assertFalse(os.path.exists("PANIC"))

    def test_one_leg_rejected_unwinds(self):
        sim, b, bot, logs = self.mk(calm, cls=RejectPE); r = bot.run()
        self.assertEqual(r["reason"], "entry_failed"); self.assertTrue(self.flat(b), "the filled CE leg must be bought back")

    def test_max_daily_loss(self):
        sim, b, bot, logs = self.mk(crawl, stop_loss_pct=500.0, max_daily_loss=1500.0); r = bot.run()
        self.assertEqual(r["reason"], "max_daily_loss"); self.assertTrue(self.flat(b))

    def test_refuses_too_many_lots(self):
        sim, b, bot, logs = self.mk(calm, lots=10)
        with self.assertRaises(SystemExit): bot.run()

    def test_no_second_entry_same_day(self):
        sim, b, bot, logs = self.mk(calm); bot.run()
        sim2, b2, bot2, _ = self.mk(calm)
        with self.assertRaises(SystemExit): bot2.run()

    def test_not_expiry_day_does_nothing(self):
        sim, b, bot, logs = self.mk(calm)
        sim.nearest_expiry = lambda u, t: DAY + timedelta(days=3)
        sim.find_option_pair = lambda u, k, t: OptionPair("A", "B", 75, DAY + timedelta(days=3), k)
        r = bot.run(); self.assertEqual(r["reason"], "not_expiry_day"); self.assertEqual(len(b.placed_log), 0)

    def test_data_failure_failsafe(self):
        sim, b, bot, logs = self.mk(calm); n = {"calls": 0}; real = bot._quotes
        def flaky(syms):                                              # the bot's price feed dies mid-trade; the order path still works
            n["calls"] += 1
            if n["calls"] > 12: raise RuntimeError("feed down")
            return real(syms)
        bot._quotes = flaky; r = bot.run()
        self.assertEqual(r["reason"], "data_failsafe"); self.assertTrue(self.flat(b))

    def test_square_off_all_retries_and_shorts_first(self):
        sim = Sim(calm); b = FlakyPaper(sim); b.place("NIFTYAAA", "SELL", 75, order_type="MARKET"); b.place("NIFTYBBB", "BUY", 75, order_type="MARKET"); b.place("NIFTYCCC", "SELL", 75, order_type="MARKET")
        n0 = len(b.placed_log); logs = []
        ok = square_off_all(b, logs.append, sleep=sim.sleep, retries=5); self.assertTrue(ok); self.assertTrue(self.flat(b))
        done = [x for x in b.placed_log[n0:] if x[5] == "COMPLETE"]; first_sell = next(i for i, x in enumerate(done) if x[1] == "SELL"); last_buy = max(i for i, x in enumerate(done) if x[1] == "BUY")
        self.assertLess(last_buy, first_sell, "every short must be bought back before any long/hedge leg is sold")

    def test_live_mode_refused_without_confirmation(self):
        os.environ["KITE_API_KEY"] = "x"; os.environ["KITE_ACCESS_TOKEN"] = "y"; os.environ.pop("LIVE_TRADING", None)
        with self.assertRaises(SystemExit): make_broker(paper=False, product="MIS", tag="t")


if __name__ == "__main__": unittest.main()
