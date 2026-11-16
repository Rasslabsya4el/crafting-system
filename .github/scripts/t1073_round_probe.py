"""#1073 probe: one fossil round of a route, profiled. python round_probe.py TREE ROUTE UPPER [NET seconds=40] [kinds=essence,chaos-orb]"""
import sys, time, cProfile, pstats, os, threading
from pathlib import Path
TREE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TREE / "src"))
ROUTE, UPPER = sys.argv[2], float(sys.argv[3])
NET = float(sys.argv[4]) if len(sys.argv) > 4 else 40.0
KINDS = set((sys.argv[5] if len(sys.argv) > 5 else "essence,chaos-orb").split(",")) | {"fossil-set"}
threading.Timer(NET + 40, lambda: (print("CAP", flush=True), os._exit(3))).start()
from crafting_system.abstraction import Goal
from crafting_system.cli import _benchmark
from crafting_system.data import load_game_data
from crafting_system.budget import Budget, running
from crafting_system.planner import _plan as pp
from crafting_system.planner._rounds import RoundCall
from crafting_system.planner._offers import offers_for
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
data = load_game_data()
prices = load_price_file(TREE / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json")
bench = next(b for b in _benchmark.BENCHMARKS if b.id == ROUTE)
t = load_target(TREE / bench.target, data)
o = offers_for(data, Goal.from_target(t), t.base_id, t.start_item, None)
chosen = tuple(x for x in o.offers if (x.kind or x.label) in KINDS and not (x.kind == "fossil-set" and os.environ.get("NOFOSSIL")))
print(ROUTE, "offers", len(chosen), flush=True)
from crafting_system.planner import _pattern_bound as pb, _envelope_plan as ep
_real = pb.pattern_lower_bound
def _plb(*a, **k):
    k["progress"] = lambda t: print("  [%6.1f] %s" % (time.perf_counter() - T0, t[:300]), flush=True)
    b = _real(*a, **k)
    f = b.floors
    if f is not None:
        print("  floors: rho", f.rho, "chosen", f.chosen, "start class", f.klass(a[1].flags, a[1].fractured, a[1].status), flush=True)
        from collections import Counter
        print("  kinds", Counter((e.kind, e.level) for e in f.entries), flush=True)
        low = sorted((e.ratio, e.cost, float(e.pbar), e.kind, e.priced.label) for e in f.entries)[:8]
        for x in low: print("   ratio", x, flush=True)
    return b
ep.pattern_lower_bound = _plb
pr = cProfile.Profile()
T0 = time.perf_counter()
with running(Budget(None, NET, None, None, 0.01).start()) as clock:
    pr.enable()
    try:
        plan = pp._make_plan(data, t, prices, start_price=None, offers=chosen, aim=None, rates=None, strands=False, solve_it=True, start_price_of=None,
            price_source="ninja", solver="auto", with_risk=False, incumbent=None, clock=clock, foresee=False, round_call=RoundCall(1, UPPER, False))
        s = plan.search
        print("PLAN", plan.mean_remaining, "exact", s.exact, "stopped", s.stopped, "lower", s.lower, "expanded", getattr(s, "expanded", None), flush=True)
        print({k: getattr(s, k) for k in ("bound_offers", "tightened", "bound_rounds") if hasattr(s, k)})
    except BaseException as e:
        print("ERR", type(e).__name__, str(e)[:400], flush=True)
    pr.disable()
print("seconds %.1f" % (time.perf_counter() - T0), flush=True)
pstats.Stats(pr).sort_stats("cumulative").print_stats(int(os.environ.get("NPROF","25")))
sys.stdout.flush(); os._exit(0)
