"""Tests for the 2% account daily-loss kill switch (bot-integrated and standalone guard)."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import Bot
from config import Config
from guard import watch
from simulator import Sim, LossyPaper, calm


class T(unittest.TestCase):
    def setUp(self): self.d = tempfile.TemporaryDirectory(); self.old = os.getcwd(); os.chdir(self.d.name)
    def tearDown(self): os.chdir(self.old); self.d.cleanup()
    def mk(self, **cfg):
        sim = Sim(calm); b = LossyPaper(sim); logs = []; return sim, b, Bot(b, Config(**cfg), now_fn=sim.now, sleep_fn=sim.sleep, log=logs.append), logs
    def flat(self, b): return all(p["quantity"] == 0 for p in b.positions())

    def test_limit_is_2_percent_of_capital(self):
        sim, b, bot, logs = self.mk(capital=1_000_000); self.assertEqual(bot._account_limit(), 20000)

    def test_bot_closes_everything_when_account_loses_2_percent(self):
        sim, b, bot, logs = self.mk(); orig = sim.sleep
        def sleeper(s):
            orig(s)
            if sim.now().hour == 11 and sim.now().minute >= 0: b.extra = -21000.0           # a loss elsewhere in the account pushes the DAY past -2% of Rs10 lakh
        bot.sleep = sleeper; r = bot.run()
        self.assertEqual(r["reason"], "account_loss_limit"); self.assertTrue(self.flat(b)); self.assertLess(sim.now().hour, 12)
        self.assertTrue(any("ACCOUNT DAILY LOSS LIMIT HIT" in l for l in logs)); self.assertTrue(os.path.exists(f"state/locked_{sim.now().date()}"))

    def test_loss_below_limit_does_not_trigger(self):
        sim, b, bot, logs = self.mk(); b.extra = -15000.0; r = bot.run(); self.assertEqual(r["reason"], "time_exit")

    def test_no_new_trade_after_limit_already_hit(self):
        sim, b, bot, logs = self.mk(); b.extra = -25000.0; r = bot.run()
        self.assertEqual(r["reason"], "account_loss_limit_already_hit"); self.assertEqual(len(b.placed_log), 0)

    def test_guard_closes_manual_positions_and_locks_out(self):
        sim = Sim(calm); b = LossyPaper(sim); b.place("NIFTY21000CE", "SELL", 650, order_type="MARKET"); logs = []; state = {"n": 0}
        orig = sim.sleep
        def sleeper(s):
            orig(s); state["n"] += 1
            if state["n"] == 3: b.extra = -22000.0                                           # day loss crosses -Rs20,000
            if state["n"] == 8: b.place("NIFTY21200CE", "BUY", 65, order_type="MARKET")      # you open something new later (lockout must close it)
        sim.t = sim.t.replace(hour=11, minute=0); tripped = watch(b, 20000, now_fn=sim.now, sleep_fn=sleeper, end_hhmm="11:10", poll=5.0, log=logs.append)
        self.assertTrue(tripped); self.assertTrue(self.flat(b)); self.assertTrue(any("LOCKOUT" in l for l in logs))

    def test_guard_stays_quiet_inside_limit(self):
        sim = Sim(calm); b = LossyPaper(sim); b.place("NIFTY21000CE", "SELL", 130, order_type="MARKET"); sim.t = sim.t.replace(hour=11, minute=0)
        self.assertFalse(watch(b, 20000, now_fn=sim.now, sleep_fn=sim.sleep, end_hhmm="11:05", log=lambda m: None)); self.assertFalse(self.flat(b))


if __name__ == "__main__": unittest.main()
