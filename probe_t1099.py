"""One reference route under the default net (600 s) with an explicit memory net; prints each round and the answer.

python probe.py TREE ROUTE MEMORY_MB
"""
import os
import sys
import threading
import time
from pathlib import Path

TREE, ROUTE, MEMORY = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
threading.Timer(1500.0, lambda: (print("CAP", flush=True), os._exit(3))).start()
from crafting_system.budget import Budget, process_mb  # noqa: E402
from crafting_system.cli import _benchmark  # noqa: E402
from crafting_system.data import load_game_data  # noqa: E402
from crafting_system.planner import PlanSettings, plan_target  # noqa: E402
from crafting_system.planner import _plan as pp  # noqa: E402
from crafting_system.planner import _rounds  # noqa: E402
from crafting_system.prices import load_price_file  # noqa: E402
from crafting_system.targets import load_target  # noqa: E402

from crafting_system.config import load_config  # noqa: E402

data = load_game_data(cache_dir=load_config().cache_dir)
import crafting_system  # noqa: E402

print("TREE", crafting_system.__file__, flush=True)
prices = load_price_file(TREE / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json")
bench = next(b for b in _benchmark.BENCHMARKS if b.id == ROUTE)
PEAK = [0.0]


def sample():
    while True:
        PEAK[0] = max(PEAK[0], process_mb() or 0.0)
        time.sleep(0.5)


threading.Thread(target=sample, daemon=True).start()
T0 = time.perf_counter()
real = pp._make_plan


def traced(*a, round_call=None, **k):
    if round_call is None:
        return real(*a, round_call=round_call, **k)
    head = f"[{time.perf_counter() - T0:6.1f} s] round of {len(k['offers'])} offers, searches {round_call.searches}, in hand {round_call.upper}, held {getattr(round_call, 'held', '-')}"
    try:
        plan = real(*a, round_call=round_call, **k)
        s = plan.search
        print(f"{head}\n    -> plan {plan.mean_remaining:.4f} lower {getattr(s, 'lower', None)} stopped {getattr(s, 'stopped', None)} bound {getattr(s, 'bound_seconds', 0):.1f} s keys {getattr(s, 'bound_keys', None)} bound_stopped {getattr(s, 'bound_stopped', None)} [{time.perf_counter() - T0:.1f} s]", flush=True)
        return plan
    except BaseException as e:
        print(f"{head}\n    -> {type(e).__name__}: {str(e)[:300]} [{time.perf_counter() - T0:.1f} s]", flush=True)
        raise


pp._make_plan = traced
budget = Budget(seconds=600.0, memory_mb=MEMORY)
plan = plan_target(data, load_target(TREE / bench.target, data), prices, PlanSettings(recipe_starts=False, budget=budget))
print(f"[{time.perf_counter() - T0:6.1f} s] ANSWER {ROUTE} {plan.mean_remaining + plan.start_price.chaos:.2f} c, peak {PEAK[0]:.0f} MB", flush=True)
for n, r in enumerate(plan.search.widening if plan.search else (), start=1):
    print("  ", _rounds.round_line(n, r))
os._exit(0)
