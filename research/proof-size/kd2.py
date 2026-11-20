"""#1310: the FIRST bound's build of a route with round 1 set by LEAD (as research/rounds-design/tb.py), dumped whole to OUT.pkl, then exit.
env LEAD=names:label|label ; NET (seconds, the run's limit) ; SPB (SEARCH_PER_BUILD; 0.02 lets the build take nearly the whole limit).
Usage: kd.py benchmark_routes.py ROUTE OUTDIR --net        (env DUMP=path of the pickle)"""
import os, pickle, runpy, sys, time
from crafting_system.planner import _rounds, _envelope_plan as _ep
if os.environ.get("SPB"):
    _ep.SEARCH_PER_BUILD = float(os.environ["SPB"])
if os.environ.get("NET"):
    from crafting_system import config as _config
    _config.TIME_LIMIT_SECONDS = float(os.environ["NET"])
LEAD = os.environ.get("LEAD")
real_groups = _rounds.round_groups
def groups(offers, named, added):
    extra = tuple(LEAD.split(":", 1)[1].split("|"))
    gs = real_groups(offers, (*(named or ()), *extra), added)
    print(f"LEAD first group {len(gs[0].positions)} offers", flush=True)
    return gs
if LEAD: _rounds.round_groups = groups
orig = _ep.pattern_lower_bound
def wrapped(*a, **k):
    load0 = f'{os.getloadavg()[0]:.2f}'
    t = time.perf_counter()
    b = orig(*a, **k)
    s = time.perf_counter() - t
    m = b.model; x = m.stats; priced = a[2]
    exp = m.expanded or [True] * len(m.keys)
    print(f"BUILD took {s:.1f}s offers {len(b.positions)} keys {len(m.keys)} expanded {sum(exp)} kernels {x.kernels} pairs {x.pairs} start value {b.start_value!r} error {b.error_bound!r} stopped {str(b.stopped)[:120]} phase {b.phase} load {load0}->{f'{os.getloadavg()[0]:.2f}'}", flush=True)
    out = {"keys": m.keys, "goal": m.goal, "actions": m.actions, "kernels": m.kernels, "expanded": exp, "value": [float(v) for v in b.value],
           "start_value": b.start_value, "stopped": b.stopped, "seconds": s, "labels": [priced[p].label for p in b.positions], "costs": [float(priced[p].cost) for p in b.positions],
           "cheapest": min(float(p.cost) for p in priced), "modes": dict(x.modes), "narrow": {k: sorted(v) for k, v in getattr(m, "narrow", {}).items()}}
    if len(m.keys) < int(os.environ.get("MINKEYS", "0")) or not all(exp) or not (b.start_value < float("inf")):
        return b
    with open(os.environ["DUMP"], "wb") as f:
        pickle.dump(out, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("DUMPED", os.environ["DUMP"], flush=True)
    sys.stdout.flush(); os._exit(0)
_ep.pattern_lower_bound = wrapped
script = sys.argv[1]; sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
