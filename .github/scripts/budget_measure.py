"""Measure one plan's time and memory with and without the run's budget (ticket #825), for a heavy run.

    uv run --no-sync python .github/scripts/budget_measure.py r08-energy-shield-boots tests/fixtures/prices/routes-allflame-2026-07-31.json default $OUT_DIR/r08.json

`solver` (optional, default `auto`) is `make_plan`'s. `mode` is `none` (no budget: every stage to its end, as `make_plan` always ran before #825) or `default` (`budget.Budget.default()`: OR-33's
10-minute net and 80% of the machine's memory, what the command uses). The memory of this process and of its live children is sampled every
`SAMPLE_SECONDS` from /proc (Linux runners). The result is one JSON object: the seconds, the peak memory, the mean or the refusal, and the
limits that bound. It runs on any branch: `none` needs nothing of #825.
"""

import json
import os
import multiprocessing
import sys
import threading
import time
from pathlib import Path

SAMPLE_SECONDS = 2.0


def held_mb() -> float:
    def rss(pid) -> float:
        try:
            with open(os.path.join(os.sep, "proc", str(pid), "status"), encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024
        except OSError:
            pass
        return 0.0

    return rss("self") + sum(rss(child.pid) for child in multiprocessing.active_children())


def main(stem: str, prices_path: str, mode: str, out: str, solver: str = "auto") -> None:
    from crafting_system.cli import make_plan
    from crafting_system.planner._plan import PlanError
    from crafting_system.config import load_config
    from crafting_system.data import load_game_data
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    root = Path(__file__).resolve().parents[2]
    data = load_game_data(cache_dir=load_config().cache_dir)
    target = load_target(root / "examples" / "targets" / f"{stem}.yaml", data)
    prices = load_price_file(root / prices_path)
    kwargs: dict = {"solver": solver}
    if mode == "default":
        from crafting_system.budget import Budget

        kwargs["budget"] = Budget.default()
    peak = [0.0]
    done = threading.Event()

    def sample() -> None:
        while not done.wait(SAMPLE_SECONDS):
            peak[0] = max(peak[0], held_mb())

    threading.Thread(target=sample, daemon=True).start()
    began = time.perf_counter()
    result: dict = {"route": stem, "prices": prices_path, "mode": mode, "solver": solver, "budget": repr(kwargs.get("budget"))}
    try:
        plan = make_plan(data, target, prices, **kwargs)
        result["mean"] = plan.mean_remaining
        result["states"] = len(plan.solution.values)
        result["p50"] = None if plan.risk is None else [plan.risk.p50.low, plan.risk.p50.high]
        result["bound"] = [list(limit.names) for limit in plan.limits if limit.kind == "time-and-memory"]
        info = plan.packed.info.get("envelope") if plan.packed is not None else None
        if info is not None:
            result["envelope"] = {"exact": info.exact, "stopped": info.stopped, "lower": info.lower, "upper": info.upper, "bound_stopped": info.bound_stopped,
                                  "bound_seconds": info.bound_seconds, "seconds": info.seconds, "expanded": info.expanded}
    except PlanError as error:
        result["refused"] = str(error)
    result["seconds"] = time.perf_counter() - began
    done.set()
    result["peak_mb"] = max(peak[0], held_mb())
    print(json.dumps(result, indent=1))
    Path(out).write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:6])
