"""TEMPORARY timing for #66. Not part of the PR."""
import sys, time
sys.path.insert(0, "tests")
from pathlib import Path
from abstraction_support import real_game_data
from crafting_system.cli import make_plan, evaluate_route, load_route
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
data = real_game_data()
variant = sys.argv[1]
path = Path("examples/targets/r13-life-resist-belt.yaml")
if variant == "noactions":
    text = "\n".join(l for l in path.read_text().splitlines() if not l.startswith("actions:"))
    path = Path("r13-noactions.yaml"); path.write_text(text)
t = load_target(path, data)
t0 = time.time()
plan = make_plan(data, t, load_price_file(Path("tests/fixtures/prices/routes-allflame-2026-10-31.json")))
print(variant, "plan secs", time.time() - t0, "solve", plan.solve_seconds, "risk", plan.risk_seconds, "states", len(plan.policy), "solved", len(plan.solution.values), "mean", plan.risk.mean.value, "offers", len(plan.offers), flush=True)
route = load_route(Path("examples/routes/r13-life-resist-belt.yaml"), plan, data)
r = evaluate_route(plan, route, data)
print(variant, "route mean", r.risk.mean.value, "gaps", len(r.gaps), flush=True)
