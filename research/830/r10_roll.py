"""R10 with a Life roll limit (ticket #830, #743): the plan `tests/test_cli_roll_real.py` makes, timed, with the search's own figures.

    python research/830/r10_roll.py ROLL [--seconds S] [--budget]

ROLL is the Life roll the target asks (70: `examples/targets/r10-fractured-boots-70-life.yaml`; 75 cuts a tier in the middle, as the test does).
The plan is `make_plan(solver="auto", with_risk=False)` at the test's prices (2026-10-31): with no budget (the test's exact plan), or with
`--budget` the planner's default (`Budget.default()`, the aim of a minute and the stop at a proved 1%). `--seconds` is a net for the
measurement only, so that one side of a pair fits a runner; a stop is printed, not hidden. Prints one JSON line.
"""

import argparse
import dataclasses
import json
import sys
import tempfile
import time
from pathlib import Path

from crafting_system.budget import Budget
from crafting_system.cli import make_plan
from crafting_system.data import load_game_data
from crafting_system.planner._envelope import Net
from crafting_system.planner._plan import PlanError
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "examples" / "targets" / "r10-fractured-boots-70-life.yaml"
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roll", type=int)
    parser.add_argument("--seconds", type=float, default=None)
    parser.add_argument("--budget", action="store_true")
    args = parser.parse_args()
    text = TARGET.read_text(encoding="utf-8")
    assert "min_roll: [70]" in text
    path = Path(tempfile.mkdtemp()) / f"r10-{args.roll}.yaml"
    path.write_text(text.replace("min_roll: [70]", f"min_roll: [{args.roll}]"), encoding="utf-8")
    data = load_game_data()
    target = load_target(path, data)
    prices = load_price_file(PRICES)
    if args.budget:
        budget = Budget.default()
        if args.seconds is not None:
            budget = dataclasses.replace(budget, seconds=args.seconds)
        options = {"budget": budget}
    else:
        options = {"net": Net(seconds=args.seconds)} if args.seconds is not None else {}
    began = time.perf_counter()
    row: dict = {"roll": args.roll, "budget": args.budget}
    try:
        plan = make_plan(data, target, prices, with_risk=False, **options)
    except PlanError as error:
        row.update(seconds=round(time.perf_counter() - began, 1), error=str(error)[:600])
        print(json.dumps(row), flush=True)
        return 0
    row["seconds"] = round(time.perf_counter() - began, 1)
    row["mean_remaining"] = plan.mean_remaining
    row["states"] = len(plan.solution.values)
    row["reach"] = len(plan.policy)
    info = plan.packed.info.get("envelope") if plan.packed is not None else None
    row["path"] = "envelope search" if info is not None else "walk"
    if info is not None:
        row["envelope"] = {key: value for key, value in dataclasses.asdict(info).items() if not isinstance(value, (list, dict))}
    row["limits"] = [limit.what for limit in plan.limits]
    print(json.dumps(row, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
