"""Offline tests against a simulated market. Nothing here can reach Zerodha.  Run:  python -m unittest discover -s tests -v"""
import csv, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import Bot
from broker import PaperBroker, make_broker
from config import Config
from simulator import Sim, calm, spike, gap, crawl, DAY
from squareoff import square_off_all
from datetime import timedelta
from broker import OptionPair


class RejectShortPE(PaperBroker):
    def place(self, symbol, side, qty, price=None, order_type="LIMIT"):
        if symbol.endswith("PE") and side == "SELL" and symbol.startswith("NIFTY21000"):
            oid = f"REJ{len(self.orders)+1}"; self.orders[oid] = dict(status="REJECTED", filled=0, avg=0.0); return oid
        return super().place(symbol, side, qty, price, order_type)


class RejectWingCE(PaperBroker):
    def place(self, symbol, side, qty, price=None, order_type="LIMIT"):
        if side == "BUY" and symbol.endswith("CE") and not symbol.startswith("NIFTY21000") and not self.pos.get(symbol):
            oid = f"REJ{len(self.orders)+1}"; self.orders[oid] = dict(status="REJECTED", filled=0, avg=0.0); return oid
        return super().place(symbol, side, qty, price, order_type)


class FlakyPaper(PaperBroker):
    """LIMIT orders sit unfilled for the first two attempts; MARKET always fills. Proves retry/escalation."""
    def __init__(self, *a, **k): super().__init__(*a, **k); self.limit_calls = 0
    def place(self, symbol, side, qty, price=None, order_type="LIMIT"):
        if order_type == "LIMIT" and self.limit_calls < 2:
            self.limit_calls += 1; oid = f"OPEN{len(self.orders)+1}"; self.orders[oid] = dict(status="OPEN", filled=0, avg=0.0); self.placed_log.append((symbol, side, qty, price, order_type, "OPEN")); return oid
        return super().place(symbol, side, qty, price, order_type)


class T(unittest.TestCase):
    def setUp(self): self.d = tempfile.TemporaryDirectory(); self.old = os.getcwd(); os.chdir(self.d.name)
    def tearDown(self): os.chdir(self.old); self.d.cleanup()

    def mk(self, scenario, cls=PaperBroker, **cfg):
        sim = Sim(scenario); c = Config(**cfg); b = cls(sim); logs = []
        return sim, b, Bot(b, c, now_fn=sim.now, sleep_fn=sim.sleep, log=logs.append), logs

    def flat(self, b): return all(p["quantity"] == 0 for p in b.positions())
    def pnl(self, b): return sum(p["pnl"] for p in b.positions())

    def test_calm_day_time_exit_flat_and_journal(self):
        sim, b, bot, logs = self.mk(calm); r = bot.run()
        self.assertEqual(r["reason"], "time_exit"); self.assertTrue(self.flat(b)); self.assertEqual(b.live_orders_sent, 0)
        self.assertGreaterEqual(sim.now().hour * 60 + sim.now().minute, 15 * 60 + 15)
        with open("logs/paper_journal.csv") as f: rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1); self.assertEqual(rows[0]["reason"], "time_exit"); self.assertEqual(rows[0]["qty_per_leg"], "130")

    def test_wings_bought_before_shorts_sold(self):
        sim, b, bot, logs = self.mk(calm); bot.run(); entry = b.placed_log[:4]
        self.assertEqual([x[1] for x in entry], ["BUY", "BUY", "SELL", "SELL"], "risk must be capped by the wings before any short is sold")
        self.assertEqual({x[0] for x in entry[:2]}, {"NIFTY21200CE", "NIFTY20800PE"})

    def test_itm_wing_style(self):
        sim, b, bot, logs = self.mk(calm, wing_style="itm"); bot.run(); self.assertEqual({x[0] for x in b.placed_log[:2]}, {"NIFTY20800CE", "NIFTY21200PE"})

    def test_stop_loss_triggers_and_loss_is_bounded(self):
        sim, b, bot, logs = self.mk(spike); r = bot.run()
        self.assertEqual(r["reason"], "stop_loss"); self.assertTrue(self.flat(b)); self.assertGreater(self.pnl(b), -4000)      # ~10% of ~Rs198*130 plus slippage

    def test_gap_through_stop_is_honest_about_gap_risk(self):
        sim, b, bot, logs = self.mk(gap); r = bot.run()
        self.assertEqual(r["reason"], "stop_loss"); self.assertTrue(self.flat(b)); self.assertLess(self.pnl(b), -4500, "a jump past the stop costs MORE than the stop - gaps cannot be avoided")

    def test_panic_closes_shorts_before_wings(self):
        sim, b, bot, logs = self.mk(calm); orig = sim.sleep
        def sleeper(s):
            orig(s)
            if sim.now().hour == 11 and sim.now().minute >= 30: bot.panic.set()
        bot.sleep = sleeper; r = bot.run()
        self.assertEqual(r["reason"], "panic"); self.assertTrue(self.flat(b)); self.assertLess(sim.now().hour, 12)
        after = b.placed_log[4:]; kinds = [x[1] for x in after if x[5] == "COMPLETE"]; self.assertEqual(kinds, ["BUY", "BUY", "SELL", "SELL"], "buy back both shorts BEFORE selling the wings")

    def test_panic_file(self):
        sim, b, bot, logs = self.mk(calm); orig = sim.sleep
        def sleeper(s):
            orig(s)
            if sim.now().hour == 10 and not os.path.exists("created"): open("PANIC", "w").close(); open("created", "w").close()
        bot.sleep = sleeper; r = bot.run(); self.assertEqual(r["reason"], "panic"); self.assertTrue(self.flat(b)); self.assertFalse(os.path.exists("PANIC"))

    def test_short_leg_rejected_unwinds_everything(self):
        sim, b, bot, logs = self.mk(calm, cls=RejectShortPE); r = bot.run(); self.assertEqual(r["reason"], "entry_failed"); self.assertTrue(self.flat(b), "wings and the CE short must all be closed")

    def test_wing_rejected_means_no_short_is_ever_sold(self):
        sim, b, bot, logs = self.mk(calm, cls=RejectWingCE); r = bot.run(); self.assertEqual(r["reason"], "entry_failed"); self.assertTrue(self.flat(b))
        self.assertFalse(any(x[1] == "SELL" and x[0].startswith("NIFTY21000") for x in b.placed_log), "no short may be sold if a wing could not be bought")

    def test_max_daily_loss(self):
        sim, b, bot, logs = self.mk(crawl, stop_loss_pct=500.0, max_daily_loss=1500.0); r = bot.run(); self.assertEqual(r["reason"], "max_daily_loss"); self.assertTrue(self.flat(b))

    def test_refuses_too_many_sets(self):
        sim, b, bot, logs = self.mk(calm, sets=10)
        with self.assertRaises(SystemExit): bot.run()

    def test_no_second_entry_same_day(self):
        sim, b, bot, logs = self.mk(calm); bot.run(); sim2, b2, bot2, _ = self.mk(calm)
        with self.assertRaises(SystemExit): bot2.run()

    def test_not_expiry_day_does_nothing(self):
        sim, b, bot, logs = self.mk(calm); sim.find_option_pair = lambda u, k, t: OptionPair(f"NIFTY{k}CE", f"NIFTY{k}PE", 65, DAY + timedelta(days=3), k)
        r = bot.run(); self.assertEqual(r["reason"], "not_expiry_day"); self.assertEqual(len(b.placed_log), 0)

    def test_data_failure_failsafe(self):
        sim, b, bot, logs = self.mk(calm); n = {"calls": 0}; real = bot._quotes
        def flaky(syms):
            n["calls"] += 1
            if n["calls"] > 12: raise RuntimeError("feed down")
            return real(syms)
        bot._quotes = flaky; r = bot.run(); self.assertEqual(r["reason"], "data_failsafe"); self.assertTrue(self.flat(b))

    def test_square_off_all_retries_and_shorts_first(self):
        sim = Sim(calm); b = FlakyPaper(sim); b.place("NIFTY21000CE", "SELL", 75, order_type="MARKET"); b.place("NIFTY21200CE", "BUY", 75, order_type="MARKET"); b.place("NIFTY21000PE", "SELL", 75, order_type="MARKET")
        n0 = len(b.placed_log); ok = square_off_all(b, lambda m: None, sleep=sim.sleep, retries=5); self.assertTrue(ok); self.assertTrue(self.flat(b))
        done = [x for x in b.placed_log[n0:] if x[5] == "COMPLETE"]; first_sell = next(i for i, x in enumerate(done) if x[1] == "SELL"); last_buy = max(i for i, x in enumerate(done) if x[1] == "BUY")
        self.assertLess(last_buy, first_sell, "every short must be bought back before any long/wing is sold")

    def test_live_mode_refused_without_confirmation(self):
        os.environ["KITE_API_KEY"] = "x"; os.environ["KITE_ACCESS_TOKEN"] = "y"; os.environ.pop("LIVE_TRADING", None)
        with self.assertRaises(SystemExit): make_broker(paper=False, product="MIS", tag="t")


if __name__ == "__main__": unittest.main()
