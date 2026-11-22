"""#1276 probe: benchmark_routes.py with every round traced and the groups regrouped by env LEAD (no planner code changed).
LEAD=one            every offer in one group (one search, no rounds)
LEAD=allbut:K1,K2   one first group of every kind but K1,K2; those kinds keep their own rounds after it
LEAD=kinds:K1,K2:F  first group = the groups of kinds K1,K2 (a kind as kind or kind@feat+feat for one of two groups of a kind); rest in main's order
LEAD=tier0          first group = every group whose features are within {junk}; rest in main's order
LEAD=names:L1|L2    the labels (or kinds) lead the first group, as a target's named actions do
ONLY=L1|L2          the planner's own offers are cut to these labels before any search (#1192): the probe of a route that is not searched
                    in rounds (R14: an Awakener's Orb among its offers), and with LEAD=one a single search of exactly those offers
"""
import os, runpy, sys, time
T0 = time.perf_counter()
from crafting_system.planner import _plan as pp, _rounds
real = pp._make_plan
def traced(*a, round_call=None, **k):
    if round_call is None:
        return real(*a, round_call=round_call, **k)
    head = f"TRACE [{time.perf_counter()-T0:6.1f} s] round offers {len(k.get('offers', ()))} searches {round_call.searches} upper {round_call.upper} floors {round_call.floors}"
    t = time.perf_counter()
    try:
        plan = real(*a, round_call=round_call, **k)
        s = plan.search
        print(f"{head}\nTRACE    -> plan {plan.mean_remaining:.4f} lower {getattr(s,'lower',None)} states {getattr(s,'touched',None)} stopped {str(getattr(s,'stopped',None))[:160]} took {time.perf_counter()-t:.1f} s", flush=True)
        return plan
    except BaseException as e:
        print(f"{head}\nTRACE    -> {type(e).__name__}: {str(e)[:300]} took {time.perf_counter()-t:.1f} s", flush=True)
        raise
pp._make_plan = traced
if os.environ.get("SPB"):  # the build's room before a first plan: it stops when the time left is at most SPB times the time it took (main: 3.0, a quarter)
    from crafting_system.planner import _envelope_plan as _ep
    _ep.SEARCH_PER_BUILD = float(os.environ["SPB"])
    print(f"TRACE SPB {_ep.SEARCH_PER_BUILD}", flush=True)
if os.environ.get("ONLY"):
    import dataclasses
    only = set(os.environ["ONLY"].split("|"))
    real_offers_for = pp.offers_for
    def offers_for(*a, **k):
        chosen = real_offers_for(*a, **k)
        kept = tuple(o for o in chosen.offers if o.label in only)
        print(f"TRACE ONLY: {len(kept)} of {len(chosen.offers)} offers kept; labels not found: {sorted(only - {o.label for o in kept})}", flush=True)
        return dataclasses.replace(chosen, offers=kept)
    pp.offers_for = offers_for
LEAD = os.environ.get("LEAD")
real_groups = _rounds.round_groups
def name(g): return g.kinds[0] + "@" + "+".join(sorted(g.features)) if len(g.kinds) == 1 else ",".join(g.kinds)
def groups(offers, named, added):
    if LEAD and LEAD.startswith("names:"):  # the labels or kinds (|-separated) lead the first group, as a target's named actions do
        extra = tuple(LEAD.split(":", 1)[1].split("|"))
        gs = real_groups(offers, (*(named or ()), *extra), added)
        got = sorted({o.label for i in gs[0].positions for o in [offers[i]]})
        print(f"TRACE LEAD names: first group {len(gs[0].positions)} offers, features {sorted(gs[0].features)}, {len(gs)} groups; labels {got}", flush=True)
        return gs
    gs = list(real_groups(offers, named, added))
    if not LEAD or len(gs) < 2:
        return tuple(gs)
    if LEAD == "one":
        lead = gs
    elif LEAD == "tier0":
        lead = [g for g in gs if set(g.features) <= {"junk"}]
    elif LEAD.startswith("allbut:"):
        out = set(LEAD.split(":", 1)[1].split(","))
        lead = [g for g in gs if not (set(g.kinds) & out)]
    else:
        want = set(LEAD.split(":", 1)[1].split(","))
        lead = [g for g in gs if (set(g.kinds) & want) or name(g) in want]
    rest = [g for g in gs if g not in lead]
    first = _rounds.Group(tuple(sorted(i for g in lead for i in g.positions)), tuple(sorted({x for g in lead for x in g.kinds})), frozenset().union(*(g.features for g in lead)))
    print(f"TRACE LEAD {LEAD}: first group {len(first.positions)} offers of {len(lead)} groups, features {sorted(first.features)}; {len(rest)} groups after: {[name(g) for g in rest]}", flush=True)
    return (first, *rest)
_rounds.round_groups = groups

# t1276c: the final plan's text report and its steps by cost (the plan-led rule reads the costliest step)
from pathlib import Path as _P
from crafting_system.cli import _benchmark as _B
from crafting_system.cli._report import build_report as _br, render_text as _rt
_OUT = _P(sys.argv[3]) if len(sys.argv) > 3 else None
_plan_t = _B.plan_target
def _pt(data, target, prices, settings):
    t0 = time.perf_counter()
    plan = _plan_t(data, target, prices, settings)
    print(f"TRACE PLAN made in {time.perf_counter()-t0:.1f} s: mean_remaining {plan.mean_remaining:,.4f}", flush=True)
    try:
        rep = _br(plan, data)
        if _OUT is not None:
            _OUT.mkdir(parents=True, exist_ok=True); (_OUT / "plan.txt").write_text(_rt(rep))
        steps = sorted((s for s in rep.steps if s.acts and s.step_cost), key=lambda s: -(s.step_cost or 0))
        for s in steps[:12]:
            print(f"TRACE STEP {s.number}: {s.title} | uses {s.uses:,.2f} | {s.step_cost:,.2f} c | items {s.items} | {s.item[:200]}", flush=True)
    except Exception as e:
        print("TRACE report failed:", type(e).__name__, str(e)[:300], flush=True)
    return plan
_B.plan_target = _pt
script = sys.argv[1]; sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
