"""Rounds of one route, printed as they go: python rounds_probe.py TREE ROUTE [CAP seconds, default 55]"""
import sys, os, threading, time
from pathlib import Path
CAP = float(sys.argv[3]) if len(sys.argv) > 3 else 55.0
threading.Timer(CAP, lambda: (print("CAP", flush=True), os._exit(3))).start()
TREE = Path(sys.argv[1])
from crafting_system.cli import _benchmark
from crafting_system.data import load_game_data
from crafting_system.budget import Budget
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner import _plan as pp
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
cache = os.environ.get("CRAFTING_CACHE_DIR") or r'C:\Coding\Crafting system\local\cache'
data = load_game_data(cache_dir=Path(cache))
from crafting_system.budget import process_mb
PEAK = [0.0]
def sample():
    while True:
        PEAK[0] = max(PEAK[0], process_mb() or 0.0); time.sleep(0.5)
threading.Thread(target=sample, daemon=True).start()
prices = load_price_file(TREE / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json")
bench = next(b for b in _benchmark.BENCHMARKS if b.id == sys.argv[2])
T0 = time.perf_counter()
real = pp._make_plan
def traced(*a, round_call=None, **k):
    if round_call is None:
        return real(*a, round_call=round_call, **k)
    n = len(k["offers"])
    print(f"[{time.perf_counter()-T0:6.1f} s] round: {n} offers, searches {round_call.searches}, upper in hand {round_call.upper}", flush=True)
    try:
        plan = real(*a, round_call=round_call, **k)
        s = plan.search
        print(f"[{time.perf_counter()-T0:6.1f} s]   plan {plan.mean_remaining:.4f} exact {s and s.exact} within {s and s.within} stopped {s and s.stopped}", flush=True)
        return plan
    except BaseException as e:
        print(f"[{time.perf_counter()-T0:6.1f} s]   {type(e).__name__}: {str(e)[:200]}", flush=True)
        raise
pp._make_plan = traced
plan = plan_target(data, load_target(TREE / bench.target, data), prices, PlanSettings(recipe_starts=False, budget=Budget.default()))
print(f"[{time.perf_counter()-T0:6.1f} s] ANSWER {sys.argv[2]} {plan.mean_remaining + plan.start_price.chaos:.2f} c, peak {PEAK[0]:.0f} MB, memory setting {Budget.default().memory_mb}, exact {plan.search and plan.search.exact}", flush=True)
for l in plan.limits:
    if l.kind in ("rounds", "kinds-not-tried", "time-and-memory"):
        print(" ", l.what, "|", l.guarantee); [print("    ", n) for n in l.names]
os._exit(0)
