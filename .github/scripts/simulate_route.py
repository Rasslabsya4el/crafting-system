"""Play a given route on concrete items and report its cost (ticket #70; run by the `Run a command` workflow).

    python .github/scripts/simulate_route.py TARGET.yaml ROUTE.yaml [--runs N] [--seed S] [--skip-refused] [--out DIR]

For a route whose graph is too large to evaluate exactly (R04, R14): a plan with nothing solved (`make_plan(solve_it=False)`),
the route read against it, then `runs` simulated crafts (`cli._route_sim`). Prints and writes `<route>.sim.json`: success
rate, mean, p50, p90 and CVaR with their intervals, the runs a gap of the guide stopped, the runs cut at the step limit.
"""

import argparse
import json
import math
import time
from pathlib import Path

from crafting_system.cli import load_route, make_plan
from crafting_system.cli._route_sim import simulate_route
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("route")
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--chunk", type=int, default=50, help="runs per simulator call; the summary is printed and written after each")
    parser.add_argument("--seconds", type=float, default=10_800, help="stop starting new chunks after this many seconds")
    parser.add_argument("--max-steps", type=int, default=200_000)
    parser.add_argument("--skip-refused", action="store_true", help="a rule whose action the game refuses is skipped (for the completed routes)")
    parser.add_argument("--out")
    args = parser.parse_args()

    data = load_game_data()
    target = load_target(Path(args.target), data)
    plan = make_plan(data, target, load_price_file(PRICES), solve_it=False)
    route = load_route(Path(args.route), plan, data)
    began = time.perf_counter()
    costs: list[float] = []
    successes = stopped = unfinished = 0
    steps = 0.0
    chunk = 0
    while len(costs) < args.runs and time.perf_counter() - began < args.seconds:
        report = simulate_route(
            data, plan, route, runs=min(args.chunk, args.runs - len(costs)), seed=args.seed + chunk,
            max_steps=args.max_steps, skip_refused=args.skip_refused,
        )  # fmt: skip
        chunk += 1
        costs += report.costs
        successes += report.successes
        stopped += report.stopped
        unfinished += report.unfinished
        steps += report.mean_steps * report.runs
        summary = summarize(costs, successes, stopped, unfinished, steps, args, time.perf_counter() - began)
        print(json.dumps(summary), flush=True)
        write(args, summary)


def summarize(costs, successes, stopped, unfinished, steps, args, seconds) -> dict:
    """Mean with a 95% interval, quantiles and the counts of all the runs finished so far (normal approximation, good for hundreds of runs)."""
    runs = len(costs)
    mean = sum(costs) / runs
    spread = math.sqrt(sum((cost - mean) ** 2 for cost in costs) / (runs - 1)) if runs > 1 else float("nan")
    half = 1.96 * spread / math.sqrt(runs) if runs > 1 else float("nan")
    ordered = sorted(costs)
    return {
        "route": Path(args.route).name, "runs": runs, "seed": args.seed, "seconds": seconds,
        "successes": successes, "stopped_at_a_gap": stopped, "cut_at_step_limit": unfinished, "mean_steps": steps / runs,
        "success_rate": successes / runs, "mean_cost": {"value": mean, "low": mean - half, "high": mean + half},
        "p50": ordered[int(0.5 * (runs - 1))], "p90": ordered[int(0.9 * (runs - 1))],
        "note": "costs of every run, finished or not; a run that stopped at a gap or hit the step limit counts what it paid",
    }  # fmt: skip


def write(args, summary: dict) -> None:
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{Path(args.route).stem}.sim.json").write_text(json.dumps(summary, indent=2) + chr(10), encoding="utf-8")


if __name__ == "__main__":
    main()
