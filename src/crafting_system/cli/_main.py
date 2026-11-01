"""The command line: `python -m crafting_system.cli TARGET.yaml [--route ROUTE.yaml] [--buy-spec PATH] [--strands] [--no-recipe-starts] [--verify] [--json PATH]`, and `benchmark`.

This is the one place of the planner that reads the clock and the environment. It loads the game
data from the cache, the target, and the price file with its hand overrides, makes the plan, prints
the text tree, writes the JSON policy and, with `--verify`, runs the simulator against the computed
mean. Exit code 0 is a plan (and, with `--verify`, an agreeing simulation), 1 an error, 2 a
simulation that does not agree. With `--route` the given route (a YAML file of rules, see `_route`)
is evaluated as a fixed policy at the same prices and printed next to the policy's numbers.
`python -m crafting_system.cli benchmark [--out DIR]` runs the benchmark routes (see `_benchmark`).

A query whose exact run is forecast to take longer than `--budget` seconds (about a minute by default) is
answered approximately, within a certified 1% of the exact mean, and marked so (ADR-0023, `_decide`);
`--exact` solves it exactly however long it takes. An approximate answer gives no certified p90; its `--verify`
runs the policy on concrete items and reports a simulated mean, p90 and CVaR labelled "simulated, not certified"
(ADR-0023, `_lift`); it gives no `--route` and no route page yet.

The plan compares the target's own start item with the start items a vendor recipe can make and keeps the cheapest total of start
price and expected crafting cost (ADR-0059, `_starts`). The setting `recipe_starts` of `crafting.toml` (default on), or
`--no-recipe-starts` for one run, turns that off; the plan is then the one `make_plan` gives.
"""

import argparse
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from crafting_system.actions import ActionError
from crafting_system.config import load_config
from crafting_system.data import DataError, GameData, load_game_data
from crafting_system.prices import PriceFile, PriceFileNotFound, load_buy_spec, stale_warning
from crafting_system.solver import ConvergenceError
from crafting_system.targets import TargetError, load_target

from ._benchmark import benchmark_main
from ._decide import BUDGET_SECONDS
from ._inputs import load_target_prices, write_json
from ._plan import PlanError
from ._report import build_report, policy_document, render_text
from ._route import evaluate_route, load_route
from ._route_report import render_route_text, route_document
from ._route_view import write_route_page
from ._starts import plan_with_starts
from ._verify import DEFAULT_RUNS, DEFAULT_SEED, verify

COMMAND = "python -m crafting_system.cli"


def _seconds(text: str) -> float:
    """A `--budget` value: a number of seconds, zero or more."""
    value = float(text)
    if not value >= 0 or value == float("inf"):
        raise argparse.ArgumentTypeError(f"the budget must be a number of seconds, zero or more, got {text!r}")
    return value


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    today: date | None = None,
    data: GameData | None = None,
    prices: PriceFile | None = None,
) -> int:
    """Run one command and return the exit code.

    `env`, `today`, `data` and `prices` are for tests: they stand in for the environment, the
    clock, the cached game data and the price files. `benchmark` as the first argument runs the
    benchmark command instead (same hooks).
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["benchmark"]:
        return benchmark_main(arguments[1:], command=COMMAND, env=env, today=today, data=data, prices=prices)

    parser = argparse.ArgumentParser(
        prog=COMMAND, description="Find the cheapest crafting policy for a target item (YAML in, text and JSON out)."
    )
    parser.add_argument("target", help="the target YAML file (see examples/targets/)")
    parser.add_argument("--json", metavar="PATH", help="where to write the JSON policy (default: <output dir>/<target>.policy.json)")
    parser.add_argument("--start-price", type=float, metavar="CHAOS", help="what the start item costs, in Chaos; wins over the price file")
    parser.add_argument("--route", metavar="ROUTE.yaml", help="also evaluate this given route (rules in YAML, see examples/routes/) as a fixed policy and compare it with the policy")
    parser.add_argument("--buy-spec", metavar="PATH", help="a buy spec YAML: the route view's buy step gets a trade-site search link built from it")
    parser.add_argument("--strands", action="store_true", help="consider Memory Strands (the setting memory_strands of crafting.toml); a start item with strands turns it on by itself")
    parser.add_argument("--no-recipe-starts", action="store_true", help="plan only from the target's own start item; do not compare the start items a vendor recipe can make (the setting recipe_starts of crafting.toml)")
    parser.add_argument("--exact", action="store_true", help="solve exactly however long it takes, never approximately")
    parser.add_argument("--budget", type=_seconds, default=BUDGET_SECONDS, metavar="SECONDS", help=f"the time the exact run may take before the answer is approximate (default {BUDGET_SECONDS:g})")
    parser.add_argument("--verify", action="store_true", help="also run the policy on concrete items and compare with the computed mean (an approximate answer: with its certified interval)")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"simulated crafts for --verify (default {DEFAULT_RUNS})")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"random seed for --verify (default {DEFAULT_SEED})")
    args = parser.parse_args(arguments)

    try:
        config = load_config(env)
        game = data if data is not None else load_game_data(cache_dir=config.cache_dir)
        target_path = Path(args.target)
        target = load_target(target_path, game)
        price_file = prices if prices is not None else load_target_prices(target.price_file, config)
        stale = stale_warning(price_file, today if today is not None else datetime.now(UTC).date())
        if stale:
            print(f"Warning: {stale}", file=sys.stderr)

        plan = plan_with_starts(
            game, target, price_file, recipe_starts=config.recipe_starts and not args.no_recipe_starts,
            start_price=args.start_price, budget=None if args.exact else args.budget, strands=args.strands or config.memory_strands,
        )  # fmt: skip
        if plan.approximation is not None and args.route:
            raise PlanError("--route is not available for an approximate answer yet; run again with --exact")
        report = build_report(plan, game)
        route_path = Path(args.route) if args.route else None
        route = load_route(route_path, plan, game) if route_path is not None else None
        given = evaluate_route(plan, route, game) if route is not None else None
        check = verify(game, plan, runs=args.runs, seed=args.seed) if args.verify else None

        name = target_path.name
        print(render_text(report, check, target_name=name), end="")
        document = policy_document(report, check, target_name=name)
        if route_path is not None and route is not None and given is not None:
            print()
            print(render_route_text(report, route, given, game, file_name=route_path.name), end="")
            document["given_route"] = route_document(report, route, given, game, file_name=route_path.name)
        out = Path(args.json) if args.json else config.output_dir / f"{target_path.stem}.policy.json"
        write_json(out, document)
        print(f"JSON policy written to {out}")
        if plan.approximation is not None:
            print("Route view not written: it is not built for an approximate answer yet.")
        else:
            spec = load_buy_spec(Path(args.buy_spec)) if args.buy_spec else None
            page = write_route_page(
                out.parent / f"{target_path.stem}.route.html", report, game, route=route, given=given,
                buy_spec=spec, cache_dir=config.cache_dir, target_name=name,
            )  # fmt: skip
            print(f"Route view written to {page}")
    except (TargetError, DataError, PriceFileNotFound, PlanError, ActionError, ConvergenceError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if check is not None and not check.agrees:
        return 2
    return 0
