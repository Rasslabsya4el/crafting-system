"""Plan routes on the packed solver and cross-check it against the object solver (ticket #374, ADR-0063); run by the `Run a command` workflow.

    python .github/scripts/packed_routes.py plan  --route r04|r14|s02 [--out DIR]
    python .github/scripts/packed_routes.py check --route r05|r08|r10|r12|r13 [--out DIR]

`plan` makes the plan of the route the way the planner does (`make_plan(solver="auto")`, exact) and writes `<route>.json`:
the mean cost from the start, the certified error bound, the numbers of the packed solve (states, classes, kernels, rounds,
seconds of each phase), the risk (odds, p50, p90) and the peak memory.

`check` makes the production plan with the object solver (`solver="object"`), then solves the same offers on packed arrays and
prints the relative difference of the mean cost, p50 and p90; for R08 the packed solve takes the offers the bound pruning
ended on (`plan.pruned.used`), for the others every offer after the twins are merged (`solver="packed"`). Writes `<route>.check.json`.

Never run on a PC for the heavy routes: R04, R14 and S02 walk for minutes to half an hour. Run by `.github/scripts/heavy_dispatch.py`.
"""

import argparse
import datetime
import faulthandler
import json
import re
import sys
import threading
import time
from pathlib import Path

from crafting_system.cli import _packed, make_plan
from crafting_system.data import load_game_data
from crafting_system.prices import PriceEntry, PriceFile, load_price_file
from crafting_system.targets import load_target, parse_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGETS = {
    "r04": "r04-penetrating-quiver",
    "r05": "r05-strength-ring",
    "r08": "r08-energy-shield-boots",
    "r10": "r10-fractured-boots",
    "r12": "r12-lightning-amulet",
    "r13": "r13-life-resist-belt",
    "r14": "r14-hunter-bow",
}
STRAND_TARGET = ROOT / "docs" / "research" / "2026-11-01-strand-routes-files" / "targets" / "s02-fire-res-ring-showcase.yaml"
STRAND_KINDS = ("remembrance-orb", "unravelling-orb")


class FlatPrices(dict):
    """Every currency costs 1 chaos (the setting of tests/test_strand_routes_load.py, where the strand targets are planned)."""

    def __contains__(self, name):
        return True

    def __getitem__(self, name):
        return PriceEntry(1.0, "test")

    def get(self, name, default=None):
        return PriceEntry(1.0, "test")


def peak_mb() -> int:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    except ImportError:
        return 0


def watch_memory() -> None:
    """Print the resident memory every 20 seconds (a runner that is shut down leaves no other trace of what it held)."""
    while True:
        time.sleep(20)
        try:
            with open("/proc/self/status", encoding="utf-8") as handle:
                rss = next(line for line in handle if line.startswith("VmRSS")).split()[1]
            print(f"  memory: {int(rss) // 1024} MB resident", flush=True)
        except OSError:
            return


def inputs(route: str):
    """`(data, target, prices, start_price)` of a route: R-routes at the committed prices, S02 as today's loaders read it."""
    data = load_game_data()
    if route == "s02":
        text = STRAND_TARGET.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^\s*memory_strands:.*\n", "", text)
        text = re.sub(r"\b(?:%s)\b,? ?" % "|".join(STRAND_KINDS), "", text)
        prices = PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, FlatPrices())
        return data, parse_target(text, data, source="s02"), prices, 10.0
    return data, load_target(ROOT / "examples" / "targets" / f"{TARGETS[route]}.yaml", data), load_price_file(PRICES), None


def risk_row(plan) -> dict | None:
    risk = plan.risk
    if risk is None:
        return None
    return {
        "success": risk.success_probability.value, "p50": risk.p50.value, "p90": risk.p90.value,
        "p50_low": risk.p50.low, "p50_high": risk.p50.high, "p90_low": risk.p90.low, "p90_high": risk.p90.high,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("plan", "check"))
    parser.add_argument("--route", required=True)
    parser.add_argument("--out")
    parser.add_argument("--solver", default="auto", choices=_packed.SOLVERS, help="plan: the solver (default auto)")
    arguments = parser.parse_args()
    faulthandler.dump_traceback_later(300, repeat=True, file=sys.stderr)
    threading.Thread(target=watch_memory, daemon=True).start()
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {peak_mb()} MB] {line}", flush=True)

    _packed.PROGRESS = say
    data, target, prices, start_price = inputs(arguments.route)
    say(f"{arguments.route}: target loaded")
    out = Path(arguments.out) if arguments.out else None
    result: dict = {"route": arguments.route, "mode": arguments.mode}
    if arguments.mode == "plan":
        plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver=arguments.solver)
        result.update(
            solver=arguments.solver, seconds=round(time.perf_counter() - began, 1), solve_seconds=round(plan.solve_seconds, 1),
            risk_seconds=round(plan.risk_seconds, 1), mean_remaining=plan.mean_remaining, error_bound=plan.solution.error_bound,
            states=len(plan.solution.values), policy_states=len(plan.policy), offers=len(plan.offers),
            start_price=plan.start_price.chaos, risk=risk_row(plan), peak_mb=peak_mb(),
        )
    else:
        reference = make_plan(data, target, prices, start_price=start_price, budget=None, solver="object")
        say(f"object solver: mean {reference.mean_remaining!r} ({reference.solve_seconds:.0f} s)")
        if reference.pruned is not None and arguments.route == "r08":
            began_packed = time.perf_counter()
            packed = _packed.packed_result(
                reference.abstraction, reference.start, reference.pruned.used, solver="packed"
            )
            mean, bound = packed.solution.values[reference.start], packed.solution.error_bound
            packed_info = packed.info
            packed_seconds = time.perf_counter() - began_packed
            candidate_risk = None
        else:
            began_packed = time.perf_counter()
            candidate = make_plan(data, target, prices, start_price=start_price, budget=None, solver="packed")
            mean, bound = candidate.mean_remaining, candidate.solution.error_bound
            packed_info, packed_seconds, candidate_risk = {}, time.perf_counter() - began_packed, risk_row(candidate)
        difference = abs(mean - reference.mean_remaining) / max(abs(reference.mean_remaining), 1e-300)
        result.update(
            object_mean=reference.mean_remaining, packed_mean=mean, relative_difference=difference,
            object_bound=reference.solution.error_bound, packed_bound=bound, object_seconds=round(reference.solve_seconds, 1),
            packed_seconds=round(packed_seconds, 1), packed_info=packed_info, object_risk=risk_row(reference), packed_risk=candidate_risk,
            peak_mb=peak_mb(),
        )
        say(f"packed: mean {mean!r}, relative difference {difference:.3g}")
        if candidate_risk and result["object_risk"]:
            for key in ("p50", "p90"):
                say(f"{key}: object {result['object_risk'][key]!r}, packed {candidate_risk[key]!r}")
    text = json.dumps(result, indent=1)
    print(text, flush=True)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        suffix = "" if arguments.mode == "plan" else ".check"
        (out / f"{arguments.route}{suffix}.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
