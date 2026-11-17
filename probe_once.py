"""#1086 probe: the Exalted round's pattern bound, staircase (MODE=grow) or all offers at once (MODE=once). python probe_once.py TREE ROUTE KIND"""
import dataclasses, os, sys, threading, time
from pathlib import Path
TREE = Path(sys.argv[1]).resolve(); ROUTE = sys.argv[2]; KEEP = set(sys.argv[3].split("+")) - {"none"}
MODE = os.environ.get("MODE", "grow")
sys.path.insert(0, str(TREE / "src"))
threading.Timer(float(os.environ.get("CAP", "58")), lambda: (print("CAP", flush=True), os._exit(3))).start()
T0 = time.perf_counter()
import crafting_system.actions; cat = sys.modules["crafting_system.actions.catalog"]
for name, entry in list(cat._KINDS.items()):
    if name in KEEP:
        cat._KINDS[name] = dataclasses.replace(entry, opt_in=False)
from crafting_system.cli import _benchmark
from crafting_system.data import load_game_data
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner import _envelope_plan as ep
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
real = ep.pattern_lower_bound
import collections, functools
from crafting_system.abstraction import _pattern as P, _kernel as K
CNT = collections.Counter(); TM = collections.Counter()
def wrap(owner, name):
    f = getattr(owner, name)
    @functools.wraps(f)
    def g(*a, **k):
        t = time.perf_counter()
        try: return f(*a, **k)
        finally: CNT[name] += 1; TM[name] += time.perf_counter() - t
    setattr(owner, name, g)
for owner, name in [(P.Pattern, "members"), (P.PatternBuilder, "_reset"), (P.PatternBuilder, "_prime"), (K.Abstraction if hasattr(K, "Abstraction") else None, "kernel_key"), (K.Abstraction if hasattr(K, "Abstraction") else None, "kernel"), (K.Abstraction if hasattr(K, "Abstraction") else None, "_item_of")]:
    if owner is not None and hasattr(owner, name): wrap(owner, name)
def traced(ab, start, offers, **k):
    if not any("exalt" in o.label.lower() for o in offers):
        return real(ab, start, offers, **k)
    t = time.perf_counter()
    if MODE == "once":
        k = dict(k); k["item"] = None; k["approximate"] = True
    b = real(ab, start, offers, **k)
    m = b.model
    print(f"MODE {MODE}: {time.perf_counter()-t:.1f} s, start value {b.start_value!r} lower {b.lower!r}, rounds {b.rounds}, keys {len(m.keys)}, kernels {m.stats.kernels}, "
          f"members {m.stats.members}, restarts {m.stats.universe_growth}, pairs {m.stats.pairs}, offers {len(b.positions)} of {len(offers)}, phases { {a: round(v, 2) for a, v in b.seconds_by_phase.items()} }", flush=True)
    print("COUNTS", {n: (CNT[n], round(TM[n], 2)) for n in CNT}, flush=True)
    os._exit(0)
ep.pattern_lower_bound = traced
data = load_game_data(cache_dir=Path(os.environ.get('CRAFTING_CACHE_DIR') or r'C:\Coding\Crafting system\local\cache'))
bench = next(b for b in _benchmark.BENCHMARKS if b.id == ROUTE)
prices = load_price_file(TREE / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json")
plan_target(data, load_target(TREE / bench.target, data), prices, PlanSettings(recipe_starts=False))
