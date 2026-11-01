"""Where a plan spends its time, on the heavy cases, with a chosen number of workers (ticket #250; run by the `Run a command` workflow).

    python .github/scripts/profile_plans.py --case r05 [--budget SECONDS] [--workers N] [--cprofile] --out $OUT_DIR

Cases: the example targets by their short name (r05, r13, r08, r09, r10, r11, r12) and r04 (the quiver of the reference
route, a copy of the target of #70). `--budget` goes to `make_plan` (0 forces the approximate answer, 60 is the CLI default);
without it the plan is exact; `--rates` injects the seconds per kernel outcome and per solved edge, as the real-route tests
do, so that the exact-or-approximate decision does not depend on the machine. Prices are the fixture's, plus a MADE-UP
price for every resource it lacks (none for the routes the fixture covers).

It wraps the stages of the pipeline in timers (inclusive time of the outermost call, and the number of calls) and
writes `<case>.json` with them, the answer's hash (so a run with 1 and with N workers can be compared) and the
seconds of the whole `make_plan`. `--cprofile` also writes the 40 functions with the most own time.
"""

import argparse
import cProfile
import hashlib
import json
import os
import platform
import pstats
import signal
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
CASES = Path(__file__).resolve().parent / "profile_cases"
EXAMPLES = {
    "r05": "r05-strength-ring", "r08": "r08-energy-shield-boots", "r09": "r09-life-boots", "r10": "r10-fractured-boots",
    "r11": "r11-reservation-helmet", "r12": "r12-lightning-amulet", "r13": "r13-life-resist-belt",
}
TIMERS: dict[str, list[float]] = {}  # stage -> [seconds, calls]


def timed(owner, name: str, stage: str | None = None) -> None:
    """Replace `owner.name` by a wrapper that adds the time of its outermost calls to `TIMERS[stage]`."""
    original = getattr(owner, name)
    stage = stage or f"{getattr(owner, '__name__', type(owner).__name__)}.{name}"
    active = [0]

    def wrapper(*args, **kwargs):
        if active[0]:
            return original(*args, **kwargs)
        active[0] += 1
        began = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            spent = time.perf_counter() - began
            active[0] -= 1
            entry = TIMERS.setdefault(stage, [0.0, 0])
            entry[0] += spent
            entry[1] += 1

    setattr(owner, name, wrapper)


def install_timers() -> None:
    from crafting_system.abstraction import Abstraction, Coarsening
    from crafting_system.cli import _approx, _bound_prune, _decide, _plan
    from crafting_system.solver import _bounds, _solve, _tail

    for name in ("kernel", "kernel_key"):
        timed(Abstraction, name, f"abstraction.{name}")
    for name in ("variants", "coarsen"):
        if hasattr(Coarsening, name):
            timed(Coarsening, name, f"coarsening.{name}")
    timed(_solve, "build_graph", "solver.build_graph (explore states, kernels inside)")
    timed(_solve, "proper_states", "solver.proper_states")
    timed(_solve, "solve_cyclic", "solver.solve_cyclic (components)")
    timed(_bounds, "solve_bounds", "solver.solve_bounds")
    timed(_tail, "solve_tail_cut", "solver.solve_tail_cut")
    timed(_approx, "solve_level", "approx.solve_level")
    timed(_plan, "decide", "decide (pilot walk and rates)")
    timed(_plan, "solve", "plan.solve (exact, whole)")
    timed(_plan, "solve_pruned", "plan.solve_pruned (bound pruning, solves inside)")
    timed(_plan, "evaluate_risk", "plan.evaluate_risk (risk run)")
    timed(_plan, "climb", "plan.climb (approximate ladder)")
    timed(_bound_prune, "reach_bound", "prune.reach_bound")
    timed(_plan._Model, "prefetch", "model.prefetch (keys here + the pool's distributions)")
    timed(Abstraction, "prime", "abstraction.prime (distributions in the pool)")


def filled_prices(data, target, offers):
    """The fixture's prices plus a made-up price for each resource the offers (and the start item) need and it lacks."""
    from crafting_system.cli._offers import price_offers
    from crafting_system.prices import load_price_file
    from crafting_system.prices.price_names import canonical_price_name

    document = json.loads(PRICES.read_text(encoding="utf-8"))
    base = load_price_file(PRICES)
    _, dropped = price_offers(offers, base)
    missing = {name for drop in dropped for name in drop.missing}
    if target.start_price is not None and canonical_price_name(target.start_price) not in base.prices:
        missing.add(target.start_price)
    for name in sorted(missing):
        share = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        document["prices"][name] = {"chaos": round(0.6 + 11.4 * share, 2), "source": "made-up (timing only)"}
    path = Path(os.environ["OUT_DIR"]) / "prices-filled.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return load_price_file(path), sorted(missing)


def build_case(case: str, data):
    """The target of a case."""
    from crafting_system.targets import load_target

    if case == "r04":
        return load_target(CASES / "r04-penetrating-quiver.yaml", data)
    return load_target(ROOT / "examples" / "targets" / f"{EXAMPLES[case]}.yaml", data)


def answer_hash(plan) -> str:
    """A hash of what the answer says: the start value and, per state in a fixed order, the chosen label and the value."""
    rows = [repr(plan.mean_remaining)]
    rows += sorted(f"{state!r}|{action.label}|{plan.solution.values[state]!r}" for state, action in plan.solution.policy.items())
    approx = plan.approximation
    if approx is not None:
        rows.append(f"approx {approx.lower!r} {approx.upper!r} {approx.gap!r} {approx.level}")
    if plan.risk is not None:
        rows.append(repr(plan.risk))
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=[*EXAMPLES, "r04"])
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--rates", default=None, help="KERNEL,SOLVE seconds per unit to inject (e.g. 4e-5,7e-6)")
    parser.add_argument("--workers", type=int, default=None, help="sets CRAFTING_WORKERS (the product reads it; before #250 it is ignored)")
    parser.add_argument("--cprofile", action="store_true")
    parser.add_argument("--limit", type=float, default=None, help="stop the plan after this many seconds (Linux) and write what the timers saw so far")
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    os.environ["OUT_DIR"] = str(out)
    if arguments.workers is not None:
        os.environ["CRAFTING_WORKERS"] = str(arguments.workers)

    from crafting_system.abstraction import Goal
    from crafting_system.cli import make_plan
    from crafting_system.cli._offers import offers_for
    from crafting_system.data import load_game_data

    data = load_game_data()
    target = build_case(arguments.case, data)
    offers = None
    chosen = offers_for(data, Goal.from_target(target), target.base_id, target.start_item, target.actions).offers
    prices, missing = filled_prices(data, target, chosen)
    install_timers()
    profiler = cProfile.Profile() if arguments.cprofile else None
    began = time.perf_counter()
    if profiler:
        profiler.enable()
    from crafting_system.cli._decide import Rates

    rates = Rates(*(float(x) for x in arguments.rates.split(","))) if arguments.rates else None
    plan = None
    if arguments.limit is not None:

        def stop(*_):
            raise TimeoutError(f"stopped after {arguments.limit:g} s")

        signal.signal(signal.SIGALRM, stop)
        signal.setitimer(signal.ITIMER_REAL, arguments.limit)
    try:
        plan = make_plan(data, target, prices, offers=offers, budget=arguments.budget, rates=rates)
    except TimeoutError as stopped:
        print(stopped, flush=True)
    finally:
        if arguments.limit is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
    if profiler:
        profiler.disable()
    seconds = time.perf_counter() - began
    stages = {name: {"seconds": round(spent, 2), "calls": calls} for name, (spent, calls) in sorted(TIMERS.items(), key=lambda kv: -kv[1][0])}
    result = {
        "case": arguments.case,
        "budget": arguments.budget,
        "workers_env": os.environ.get("CRAFTING_WORKERS"),
        "seconds": round(seconds, 2),
        "interrupted": plan is None,
        "stages": stages,
        "made_up_prices": missing,
        "machine": {"system": platform.platform(), "cpus": os.cpu_count(), "python": platform.python_version()},
    }
    if plan is not None:
        result.update(
            solve_seconds=round(plan.solve_seconds, 2),
            risk_seconds=round(plan.risk_seconds, 2),
            approximate=plan.approximation is not None,
            level=plan.approximation.level if plan.approximation else None,
            mean_remaining=plan.mean_remaining,
            states=len(plan.solution.values),
            offers=len(plan.offers),
            answer_sha256=answer_hash(plan),
        )
    tag = f"{arguments.case}-w{arguments.workers}" if arguments.workers is not None else arguments.case
    (out / f"{tag}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result), flush=True)
    if profiler:
        with (out / f"{tag}.cprofile.txt").open("w", encoding="utf-8") as handle:
            stats = pstats.Stats(profiler, stream=handle)
            stats.sort_stats("tottime").print_stats(40)
            stats.sort_stats("cumulative").print_stats(40)


if __name__ == "__main__":
    main()
