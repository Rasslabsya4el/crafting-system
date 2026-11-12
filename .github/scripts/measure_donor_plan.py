"""Plan a benchmark route whose offers take donors and judge its given route, with the sizes and the seconds (ticket #225; run by the `Run a command` workflow).

    python .github/scripts/measure_donor_plan.py TARGET.yaml [ROUTE.yaml] [--prices FILE] [--out DIR]

Prints one line of JSON and writes it to `<out>/donor_plan.json`: the seconds of the plan and of the route, the product states of the plan
reading's solve, the processes (the target and each second item it makes), the plan's mean and its cost at every reading of alpha, the best
route without recombinators, and the given route's mean, gaps and first divergence. It asserts nothing; the tests of R25 and R28 hold the
numbers. Never run it on a PC: the product is solved once per reading of alpha (docs/ci.md).
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from crafting_system.cli import make_plan  # noqa: E402
from crafting_system.cli._route import evaluate_route, load_route  # noqa: E402
from crafting_system.data import load_game_data  # noqa: E402
from crafting_system.prices import load_price_file  # noqa: E402
from crafting_system.targets import load_target  # noqa: E402

PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-11-10.json"


def number(value: float) -> float | None:
    return None if math.isinf(value) or math.isnan(value) else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("route", nargs="?")
    parser.add_argument("--prices", default=str(PRICES))
    parser.add_argument("--out")
    args = parser.parse_args()
    data = load_game_data()
    target = load_target(Path(args.target), data)
    began = time.perf_counter()
    plan = make_plan(data, target, load_price_file(Path(args.prices)), judges_route=args.route is not None)
    found: dict = {
        "target": args.target,
        "plan_seconds": time.perf_counter() - began,
        "mean": number(plan.mean_remaining),
        "risk_mean": None if plan.risk is None else number(plan.risk.mean.value),
        "product_states": None if plan.donors is None else len(plan.donors.solution.values),
        "processes": None if plan.donors is None else 1 + len(plan.donors.processes),
        "main_states": len(plan.solution.values),
        "readings": {str(reading): number(cost.value) for reading, cost in plan.readings.plan.costs.items()} if plan.readings else None,
        "without_recombinators": None if plan.readings is None or plan.readings.baseline is None else number(plan.readings.baseline.value.value),
        "first_action": plan.policy[plan.start].label if plan.start in plan.policy else None,
    }
    print(json.dumps(found), flush=True)
    if args.route:
        began = time.perf_counter()
        result = evaluate_route(plan, load_route(Path(args.route), plan, data), data)
        found["route_seconds"] = time.perf_counter() - began
        found["route_mean"] = number(result.risk.mean.value)
        found["route_gaps"] = len(result.gaps)
        found["route_gap_reasons"] = sorted({gap.reason for gap in result.gaps})[:10]
        found["first_divergence"] = None if result.divergence is None else [result.divergence.solver_action, result.divergence.route_action]
    line = json.dumps(found)
    print(line)
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / "donor_plan.json").write_text(line + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
