"""R08 for ticket #829 on one runner: the envelope search's first plan and its plan under the 60-second budget of tests/test_cli_r08_r09_real.py
(1% gap, stopped by the net otherwise), on the test's own inputs: the R08 target and the prices of 2026-10-31 that the test plans at. Solver
`envelope` on both sides (main walks a judged route, so `judges_route` would not compare searches). research/881/profile_plan.py's inputs
(the prices of 2026-07-31) passed the hour on either side, exact, under a 50-minute budget and under this 60 s one (heavy runs 43677436859,
43682164228, 43687702275). `CRAFTING_SOURCE=<main's src>` plans with main. Started only through heavy_dispatch.py (research/829/pair.sh
pattern). Prints one JSON line."""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if os.environ.get("CRAFTING_SOURCE"):
    sys.path.insert(0, os.environ["CRAFTING_SOURCE"])

import crafting_system.cli  # noqa: E402,F401  (names the page that presents a plan, #882)
from crafting_system.data import load_game_data  # noqa: E402
from crafting_system.planner import make_plan  # noqa: E402
from crafting_system.prices import load_price_file  # noqa: E402
from crafting_system.targets import load_target  # noqa: E402

data = load_game_data()
target = load_target(ROOT / "examples" / "targets" / "r08-energy-shield-boots.yaml", data)
prices = load_price_file(ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json")
began = time.perf_counter()
plan = make_plan(data, target, prices, budget=60.0, solver="envelope", with_risk=False)
info = plan.search
print(json.dumps({
    "side": sys.argv[1] if len(sys.argv) > 1 else "", "seconds": round(time.perf_counter() - began, 2), "mean_remaining": plan.mean_remaining,
    "first_upper": info.first_upper, "lower": info.lower, "upper": info.upper, "within": info.within, "stopped": info.stopped,
    "expanded": info.expanded,
}))
