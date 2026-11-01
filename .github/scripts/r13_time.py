import sys, time
sys.path.insert(0, "tests")
from pathlib import Path
from abstraction_support import real_game_data
from crafting_system.cli import make_plan, verify, evaluate_route, load_route
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
data = real_game_data()
t = load_target(Path("examples/targets/r13-life-resist-belt.yaml"), data)
t0 = time.time()
plan = make_plan(data, t, load_price_file(Path("tests/fixtures/prices/routes-allflame-2026-10-31.json")))
print("plan secs", time.time() - t0, "solve", plan.solve_seconds, "risk", plan.risk_seconds, "states", len(plan.policy), "solved", len(plan.solution.values), "mean", plan.risk.mean.value, "mean_remaining", plan.mean_remaining, flush=True)
t0 = time.time()
route = load_route(Path("examples/routes/r13-life-resist-belt.yaml"), plan, data)
r = evaluate_route(plan, route, data)
print("route secs", time.time() - t0, "gaps", len(r.gaps), "mean", r.risk.mean.value, "succ", r.risk.success_probability.value, flush=True)
for runs in (20, 100):
    t0 = time.time()
    v = verify(data, plan, runs=runs, seed=11)
    print("verify", runs, "secs", time.time() - t0, v.agrees, v.reason, v.report.cost.value, v.report.mean_steps, v.p90.value, flush=True)
