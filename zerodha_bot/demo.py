"""Run a SIMULATED expiry day - no Zerodha, no network, no real money. Shows the whole flow, the stop-loss and the panic button.
   python demo.py            calm day -> exits at 3:15 pm
   python demo.py stop       premiums climb -> stop-loss fires
   python demo.py panic      you hit PANIC at 11:30 -> everything closed, shorts first
   python demo.py gap        market jumps through the stop (shows gap risk)
   python demo.py account    a loss elsewhere pushes the whole account past -2% of capital -> everything is closed"""
import os, sys, tempfile
from bot import Bot
from broker import PaperBroker
from config import Config
from simulator import Sim, LossyPaper, calm, spike, gap, crawl

which = sys.argv[1] if len(sys.argv) > 1 else "calm"
os.chdir(tempfile.mkdtemp()); sim = Sim({"calm": calm, "stop": spike, "panic": calm, "gap": gap, "account": calm}[which]); b = LossyPaper(sim) if which == "account" else PaperBroker(sim)
bot = Bot(b, Config(), now_fn=sim.now, sleep_fn=sim.sleep, log=lambda m: print(m) if not m.endswith("quote error") else None)
if which == "panic":
    orig = sim.sleep
    def sleeper(s):
        orig(s)
        if sim.now().hour == 11 and sim.now().minute >= 30 and not bot.panic.is_set(): print(">>> you press the PANIC button <<<"); bot.panic.set()
    bot.sleep = sleeper
if which == "account":
    orig2 = sim.sleep
    def sleeper2(s):
        orig2(s)
        if sim.now().hour == 11 and b.extra == 0: b.extra = -21000.0; print(">>> a separate manual trade loses Rs21,000 (> 2% of Rs10 lakh) <<<")
    bot.sleep = sleeper2
r = bot.run(); print("\nresult:", r["reason"], "| open positions:", r["open_positions"] or "none", "| simulated gross P&L Rs", r["gross_pnl"])
