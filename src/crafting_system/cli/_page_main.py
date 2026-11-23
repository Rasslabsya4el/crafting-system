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
from crafting_system.targets import StartKind, buy_spec_of

from ._plan_file import PlanFileError, load_plan
from ._report import build_report
from ._route_view import write_route_page

COMMAND = "python -m crafting_system.cli page"


def page_main(argv: Sequence[str], *, env: Mapping[str, str] | None = None, data: GameData | None = None) -> int:
    """Run `page` and return the exit code; `env` and `data` are for tests."""
    parser = argparse.ArgumentParser(prog=COMMAND, description="Write the route view of a plan saved with --save-plan, without planning again.")
    parser.add_argument("plan", help="the file --save-plan wrote")
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
        page = write_route_page(out, report, game, buy_spec=spec, cache_dir=config.cache_dir, target_name=saved.target_name)
    except (DataError, PlanFileError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Route view written to {page}")
    return 0
