"""`page`: write the route view of a plan saved with `--save-plan` again, with the page code of this tree, without planning (#1442).

A change to the route page is then checked on a heavy craft's plan in minutes instead of the hour the plan takes. The plan is
read against the game data of the settings (`_plan_file`); the page is the one the plain command writes, the given route left out.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from crafting_system.config import load_config
from crafting_system.data import DataError, GameData, load_game_data
from crafting_system.planner import PlanError, guide_plan
from crafting_system.targets import StartKind, buy_spec_of

from ._plan_file import PlanFileError, load_plan
from ._report import build_report
from ._route import RouteError, evaluate_route, load_route, route_actions
from ._route_view import write_route_page

COMMAND = "python -m crafting_system.cli page"


def page_main(argv: Sequence[str], *, env: Mapping[str, str] | None = None, data: GameData | None = None) -> int:
    """Run `page` and return the exit code; `env` and `data` are for tests."""
    parser = argparse.ArgumentParser(prog=COMMAND, description="Write the route view of a plan saved with --save-plan, without planning again.")
    parser.add_argument("plan", help="the file --save-plan wrote")
    parser.add_argument("--route", metavar="ROUTE.yaml", help="also draw this given route (the guide's) below the plan, as the plain command's --route does; the proof sentence then gives the plan's cost against it, and the goal card where the two costs differ. A route that names actions the saved plan was not offered is priced on the guide's own plan of them, as the benchmark judges it")
    parser.add_argument("--out", metavar="PAGE.html", help="where to write the page (default: beside the plan, named after the target)")
    args = parser.parse_args(list(argv))
    try:
        config = load_config(env)
        game = data if data is not None else load_game_data(cache_dir=config.cache_dir)
        saved = load_plan(Path(args.plan), game)
        if saved.plan.approximation is not None:
            print("Route view not written: it is not built for an approximate answer yet.")
            return 0
        stem = Path(saved.target_name).stem or Path(args.plan).stem
        out = Path(args.out) if args.out else Path(args.plan).with_name(f"{stem}.route.html")
        spec = buy_spec_of(game, saved.target) if saved.target.start is StartKind.BOUGHT else None
        report = build_report(saved.plan, game)
        judged = None if not args.route else judged_on(saved.plan, Path(args.route), game)
        route = load_route(Path(args.route), judged, game) if judged is not None else None
        given = evaluate_route(judged, route, game) if route is not None else None
        page = write_route_page(out, report, game, route=route, given=given, given_on=judged, buy_spec=spec, cache_dir=config.cache_dir)
    except (DataError, PlanFileError, RouteError, PlanError, OSError) as error:  # RouteError: a --route file that cannot be read; PlanError: the guide's own plan
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Route view written to {page}")
    return 0


def judged_on(plan, route: Path, data: GameData):
    """The plan a given route is evaluated on: `plan` itself when it offers every action the route names, else the guide's own plan of
    those actions (`guide_plan`, as the benchmark judges the guide of a site plan, #1442), so that a site plan's page can be drawn beside its
    guide (#1305). Raises `PlanError` (`NotModelled`) when the route names an action the model does not hold."""
    labels = route_actions(route)
    plain = plan.starts is None or plan.starts.chosen.key == "plain"  # the guide starts from the target's own item, not a vendor recipe's
    if plain and set(labels) <= {priced.label for priced in plan.offers}:
        return plan
    return guide_plan(data, plan.target, plan.prices, labels)
