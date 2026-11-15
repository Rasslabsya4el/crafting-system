"""R08 for ticket #829 on one runner: the envelope search's first plan and its plan under the 60-second budget of tests/test_cli_r08_r09_real.py
(1% gap, stopped by the net otherwise), as research/881/profile_plan.py builds the route's inputs. The exact run without a budget, and a
50-minute budget, pass the hour on either side (heavy runs 43677436859, 43682164228). `CRAFTING_SOURCE=<main's src>` plans with main. Started only through heavy_dispatch.py (research/829/pair.sh
pattern). Prints one JSON line."""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if os.environ.get("CRAFTING_SOURCE"):
    sys.path.insert(0, os.environ["CRAFTING_SOURCE"])
sys.path[:0] = [str(ROOT / "research" / "881"), str(ROOT / ".github" / "scripts"), str(ROOT / "tests")]

import profile_plan  # noqa: E402
from crafting_system.planner import make_plan  # noqa: E402


class Args:
    route = "r08"
    case = None


data, target, prices, start_price, solver = profile_plan.inputs(Args)
began = time.perf_counter()
plan = make_plan(data, target, prices, start_price=start_price, budget=60.0, solver=solver, with_risk=False)
info = plan.search
print(json.dumps({
    "side": sys.argv[1] if len(sys.argv) > 1 else "", "seconds": round(time.perf_counter() - began, 2), "mean_remaining": plan.mean_remaining,
    "first_upper": info.first_upper, "lower": info.lower, "upper": info.upper, "within": info.within, "stopped": info.stopped,
    "expanded": info.expanded,
}))
