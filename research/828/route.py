"""R07 or R24 through `make_plan` at the planner's default settings (the aim and the net of OR-33, OR-40), as ticket #828 measures them.

    uv run --no-sync python -u research/828/route.py r24-avoid-shock-boots

Prints one JSON line: the path taken, the mean, the search's figures (status, gap, lower, upper, seconds, keys of the bound, states, reach), or
the refusal. Started only through the dispatcher (`research/828/routes.sh`).
"""

import dataclasses
import json
import sys
import time
from pathlib import Path

from crafting_system.data import load_game_data
from crafting_system.planner import _packed
from crafting_system.planner._plan import PlanError, make_plan
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    stem = sys.argv[1]
    _packed.PROGRESS = lambda line: print(f"[{time.perf_counter() - began:8.1f}s] {line[:400]}", flush=True)
    data = load_game_data()
    target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
    prices = load_price_file(target.price_file)
    began = time.perf_counter()
    record: dict = {"route": stem}
    try:
        plan = make_plan(data, target, prices, with_risk=False)
    except PlanError as error:
        record.update(status="refused", reason=str(error)[:2000])
    else:
        info = plan.packed.info.get("envelope") if plan.packed is not None else None
        record.update(status="planned", mean_remaining=float(plan.mean_remaining), start_price=plan.start_price.chaos, reach=len(plan.policy))
        record["path"] = "envelope" if info is not None else "walk"
        if info is not None:
            record["envelope"] = {k: v for k, v in dataclasses.asdict(info).items() if not isinstance(v, (list, dict, tuple))}
        record["limits"] = [limit.what for limit in plan.limits]
    record["seconds"] = round(time.perf_counter() - began, 1)
    print("RESULT " + json.dumps(record, default=str), flush=True)


began = time.perf_counter()
if __name__ == "__main__":
    main()
