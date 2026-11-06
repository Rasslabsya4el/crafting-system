"""The envelope search against the full walk on a route (ticket #377, ADR-0063 point 4); run by the `Run a command` workflow.

    python .github/scripts/envelope_routes.py --route r05|r13|r04|r14 [--phase both|envelope|full] [--out DIR] [--incumbent] [--net-seconds N]
    python .github/scripts/envelope_routes.py compare ENVELOPE.json FULL.json

`--phase both` (the default) plans the route with `make_plan(solver="envelope")` and then with `make_plan(solver="packed")` (the full walk) in
one process and compares them: the mean, the plan (the label of the action at every state the envelope's plan reaches, against the full plan's
at the same state), the states expanded, the time and the peak memory of each. `--phase envelope` and `--phase full` run one of them, for a route
whose two runs do not fit in one runner's hour (R14): each writes `<route>.<phase>.json` with a digest of its policy, and `compare` joins two such
files. States are compared by a digest of their `repr`, so set `PYTHONHASHSEED=0` in the command when the two phases run in two processes.

`--incumbent` gives the search the route `examples/routes/<route>-restart.yaml` (the guide's route completed with a restart) as the incumbent whose
policy is the first upper bound; R04 and R14 have one. The risk (percentiles) is not computed: it is not what is compared.

Never run on a PC for R04 and R14: they walk for minutes to half an hour. Run by `.github/scripts/heavy_dispatch.py` (docs/ci.md).
"""

import argparse
import faulthandler
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packed_routes as P  # noqa: E402  (the inputs of a route, the memory watch)

from crafting_system.cli import _packed, make_plan  # noqa: E402
from crafting_system.cli._envelope import Net  # noqa: E402
from crafting_system.cli._envelope_plan import route_incumbent  # noqa: E402
from crafting_system.cli._route import load_route  # noqa: E402

ROOT = P.ROOT
TOLERANCE = 1e-9


def digest(state) -> str:
    return hashlib.blake2b(repr(state).encode(), digest_size=8).hexdigest()


def incumbent_of(route: str, data, target, prices, start_price):
    """The guide's route completed with a restart, read against an unsolved plan of the target."""
    path = ROOT / "examples" / "routes" / f"{P.TARGETS[route]}-restart.yaml"
    plan = make_plan(data, target, prices, start_price=start_price, solve_it=False)
    return route_incumbent(load_route(path, plan, data), data)


def run_phase(phase: str, route: str, say, use_incumbent: bool, net_seconds: float | None = None) -> dict:
    data, target, prices, start_price = P.inputs(route)
    options = {}
    if phase == "envelope" and use_incumbent:
        options["incumbent"] = incumbent_of(route, data, target, prices, start_price)
    if phase == "envelope" and net_seconds is not None:
        options["net"] = Net(seconds=net_seconds)  # a stop-and-say-so net (OR-12): the plan then says it is not shown to be the best
    began = time.perf_counter()
    plan = make_plan(
        data, target, prices, start_price=start_price, budget=None, solver="envelope" if phase == "envelope" else "packed", with_risk=False, **options
    )
    seconds = time.perf_counter() - began
    policy = {digest(state): priced.label for state, priced in plan.policy.offers()}  # the offer, not the built action: R04's kernels hold thousands of outcomes
    row = {
        "phase": phase, "route": route, "seconds": round(seconds, 1), "solve_seconds": round(plan.solve_seconds, 1), "peak_mb": P.peak_mb(),
        "mean": plan.mean_remaining, "error_bound": plan.solution.error_bound, "states_known": len(plan.solution.values),
        "policy_states": len(plan.policy), "offers": len(plan.offers), "start_label": plan.policy.offer(plan.start).label,
    }
    if phase == "envelope":
        info = plan.packed.info["envelope"]
        row.update(
            exact=info.exact, stopped=info.stopped, lower=info.lower, upper=info.upper, rounds=info.rounds, touched=info.touched,
            expanded=info.expanded, realized=info.realized, candidates=info.candidates, keys_missing=info.keys_missing,
            bound_keys=info.bound_keys, bound_seconds=round(info.bound_seconds, 1), first_upper=info.first_upper, incumbent=info.incumbent,
            search_peak_mb=info.peak_mb,
        )
    say(f"{phase}: mean {row['mean']!r}, {row['states_known']:,} states known, {row['policy_states']:,} in the plan, {seconds:.0f} s, {row['peak_mb']} MB")
    return {"row": row, "policy": policy}


def compare(envelope: dict, full: dict) -> dict:
    """The envelope's plan against the full plan: the mean, and the label of the action at each state the envelope's plan reaches."""
    a, b = envelope["row"], full["row"]
    same = other = missing = 0
    for key, label in envelope["policy"].items():
        found = full["policy"].get(key)
        if found is None:
            missing += 1
        elif found == label:
            same += 1
        else:
            other += 1
    relative = abs(a["mean"] - b["mean"]) / abs(b["mean"])
    out = {
        "route": a["route"], "mean_envelope": a["mean"], "mean_full": b["mean"], "mean_relative_difference": relative,
        "mean_equal": relative <= TOLERANCE, "start_action_equal": a["start_label"] == b["start_label"],
        "envelope_policy_states": len(envelope["policy"]), "full_policy_states": len(full["policy"]),
        "same_action": same, "other_action": other, "not_in_full_plan": missing,
        "states_full": b["states_known"], "states_known_envelope": a["states_known"], "states_expanded_envelope": a.get("expanded"),
        "expanded_share_of_full": None if a.get("expanded") is None else a["expanded"] / b["states_known"],
        "touched_share_of_full": a["states_known"] / b["states_known"],
        "seconds_envelope": a["seconds"], "seconds_full": b["seconds"], "peak_mb_envelope": a["peak_mb"], "peak_mb_full": b["peak_mb"],
        "exact": a.get("exact"), "lower": a.get("lower"), "upper": a.get("upper"),
    }
    return out


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "compare":
        loaded = [json.loads(Path(name).read_text(encoding="utf-8")) for name in sys.argv[2:4]]
        print(json.dumps(compare(*loaded), indent=2))
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--phase", default="both", choices=("both", "envelope", "full"))
    parser.add_argument("--incumbent", action="store_true")
    parser.add_argument("--net-seconds", type=float, help="stop the envelope search after this many seconds (the plan then states [LB, U])")
    parser.add_argument("--out")
    parser.add_argument("--profile", action="store_true", help="print the 40 most expensive functions (cumulative) after the run")
    arguments = parser.parse_args()
    faulthandler.dump_traceback_later(600, repeat=True, file=sys.stderr)
    threading.Thread(target=P.watch_memory, daemon=True).start()
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {P.peak_mb()} MB] {line}", flush=True)

    _packed.PROGRESS = say
    out = Path(arguments.out) if arguments.out else None
    phases = ("envelope", "full") if arguments.phase == "both" else (arguments.phase,)
    results = {}
    profiler = None
    if arguments.profile:
        import cProfile

        profiler = cProfile.Profile()
        profiler.enable()
    for phase in phases:
        results[phase] = run_phase(phase, arguments.route, say, arguments.incumbent, arguments.net_seconds)
        if out is not None:
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{arguments.route}.{phase}.json").write_text(json.dumps(results[phase]), encoding="utf-8")
        print("ROW " + json.dumps(results[phase]["row"]), flush=True)
    if profiler is not None:
        import pstats

        profiler.disable()
        pstats.Stats(profiler).sort_stats("cumulative").print_stats(40)
    if len(results) == 2:
        report = compare(results["envelope"], results["full"])
        print("COMPARE " + json.dumps(report), flush=True)
        if out is not None:
            (out / f"{arguments.route}.compare.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
