"""Plan R08 / R09 (ticket #63) with progress and stack dumps, one route per runner; run by the `Run a command` workflow.

    python .github/scripts/time_routes.py --route r08 [--exact | --budget 60] --out $OUT_DIR

Prints where the time goes (the bound pruning's progress, a stack dump every 3 minutes) and writes `<route>.json`.
"""

import argparse
import faulthandler
import json
import sys
import time
from pathlib import Path

from crafting_system.cli import _bound_prune, make_plan
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-fossils-2026-11-01.json"
TARGETS = {"r08": "r08-energy-shield-boots", "r09": "r09-life-boots"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True, choices=sorted(TARGETS))
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--budget", type=float, default=60.0)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    faulthandler.dump_traceback_later(180, repeat=True, file=sys.stderr)
    began = time.perf_counter()

    def progress(line: str) -> None:
        try:
            import resource

            line += f" (peak memory {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} MB)"
        except ImportError:
            pass
        print(f"[{time.perf_counter() - began:7.1f}s] {line}", flush=True)

    _bound_prune.PROGRESS = progress
    data = load_game_data()
    target = load_target(ROOT / "examples" / "targets" / f"{TARGETS[arguments.route]}.yaml", data)
    progress("target loaded")
    plan = make_plan(data, target, load_price_file(PRICES), budget=None if arguments.exact else arguments.budget)
    approximation = plan.approximation
    result = {
        "route": arguments.route,
        "seconds": round(time.perf_counter() - began, 1),
        "solve_seconds": round(plan.solve_seconds, 1),
        "states": len(plan.solution.values),
        "offers": len(plan.offers),
        "mean_remaining": plan.mean_remaining,
        "note": plan.note,
        "approximation": None
        if approximation is None
        else {"lower": approximation.lower, "upper": approximation.upper, "gap": approximation.gap, "level": str(approximation.level)},
    }
    (out / f"{arguments.route}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    progress(json.dumps(result))


if __name__ == "__main__":
    main()
