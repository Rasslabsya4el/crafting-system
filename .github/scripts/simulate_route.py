"""Play a given route on concrete items and report its cost (ticket #70; run by the `Run a command` workflow).

    python .github/scripts/simulate_route.py TARGET.yaml ROUTE.yaml [--runs N] [--seed S] [--skip-refused] [--out DIR]

For a route whose graph is too large to evaluate exactly (R04, R14): a plan with nothing solved (`make_plan(solve_it=False)`),
the route read against it, then `runs` simulated crafts (`cli._route_sim`). Prints and writes `<route>.sim.json`: success
rate, mean, p50, p90 and CVaR with their intervals, the runs a gap of the guide stopped, the runs cut at the step limit.
"""

import argparse
import json
import time
from pathlib import Path

from crafting_system.cli import load_route, make_plan
from crafting_system.cli._route_sim import simulate_route
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"


def estimate(value) -> dict:
    return {"value": value.value, "low": value.low, "high": value.high}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("route")
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=200_000)
    parser.add_argument("--skip-refused", action="store_true", help="a rule whose action the game refuses is skipped (for the completed routes)")
    parser.add_argument("--out")
    args = parser.parse_args()

    data = load_game_data()
    target = load_target(Path(args.target), data)
    plan = make_plan(data, target, load_price_file(PRICES), solve_it=False)
    route = load_route(Path(args.route), plan, data)
    began = time.perf_counter()
    report = simulate_route(data, plan, route, runs=args.runs, seed=args.seed, max_steps=args.max_steps, skip_refused=args.skip_refused)
    summary = {
        "route": Path(args.route).name, "runs": report.runs, "seed": args.seed, "seconds": time.perf_counter() - began,
        "successes": report.successes, "stopped_at_a_gap": report.stopped, "cut_at_step_limit": report.unfinished,
        "mean_steps": report.mean_steps, "success_rate": estimate(report.success_rate), "mean_cost": estimate(report.cost),
        "p50": estimate(report.quantile(0.5)), "p90": estimate(report.quantile(0.9)),
    }
    print(json.dumps(summary, indent=2), flush=True)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{Path(args.route).stem}.sim.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
