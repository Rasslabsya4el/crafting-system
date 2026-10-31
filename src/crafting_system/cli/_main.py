"""The command line: `python -m crafting_system.cli TARGET.yaml [--verify] [--json PATH]`.

This is the one place of the planner that reads the clock and the environment. It loads the game
data from the cache, the target, and the price file with its hand overrides, makes the plan, prints
the text tree, writes the JSON policy and, with `--verify`, runs the simulator against the computed
mean. Exit code 0 is a plan (and, with `--verify`, an agreeing simulation), 1 an error, 2 a
simulation that does not agree.
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from crafting_system.actions import ActionError
from crafting_system.config import Config, load_config
from crafting_system.data import DataError, GameData, load_game_data
from crafting_system.prices import (
    PriceFile,
    PriceFileNotFound,
    default_price_file_path,
    load_prices,
    stale_warning,
)
from crafting_system.prices.price_file import OVERRIDES_FILE_NAME
from crafting_system.solver import ConvergenceError
from crafting_system.targets import TargetError, load_target

from ._plan import PlanError, make_plan
from ._report import build_report, policy_document, render_text
from ._verify import DEFAULT_RUNS, DEFAULT_SEED, verify

COMMAND = "python -m crafting_system.cli"


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
    clock, the cached game data and the price files.
    """
    parser = argparse.ArgumentParser(
        prog=COMMAND, description="Find the cheapest crafting policy for a target item (YAML in, text and JSON out)."
    )
    parser.add_argument("target", help="the target YAML file (see examples/targets/)")
    parser.add_argument("--json", metavar="PATH", help="where to write the JSON policy (default: <output dir>/<target>.policy.json)")
    parser.add_argument("--start-price", type=float, metavar="CHAOS", help="what the start item costs, in Chaos; wins over the price file")
    parser.add_argument("--verify", action="store_true", help="also run the policy on concrete items and compare with the computed mean")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"simulated crafts for --verify (default {DEFAULT_RUNS})")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"random seed for --verify (default {DEFAULT_SEED})")
    args = parser.parse_args(argv)

    try:
        config = load_config(env)
        game = data if data is not None else load_game_data(cache_dir=config.cache_dir)
        target_path = Path(args.target)
        target = load_target(target_path, game)
        price_file = prices if prices is not None else _load_prices(target.price_file, config)
        stale = stale_warning(price_file, today if today is not None else datetime.now(UTC).date())
        if stale:
            print(f"Warning: {stale}", file=sys.stderr)

        plan = make_plan(game, target, price_file, start_price=args.start_price)
        report = build_report(plan, game)
        check = verify(game, plan, runs=args.runs, seed=args.seed) if args.verify else None

        name = target_path.name
        print(render_text(report, check, target_name=name), end="")
        out = Path(args.json) if args.json else config.output_dir / f"{target_path.stem}.policy.json"
        _write_json(out, policy_document(report, check, target_name=name))
        print(f"JSON policy written to {out}")
    except (TargetError, DataError, PriceFileNotFound, PlanError, ActionError, ConvergenceError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if check is not None and not check.agrees:
        return 2
    return 0


def _load_prices(price_file: Path | None, config: Config) -> PriceFile:
    """The price file the target names, else the configured one, with `price_overrides.toml` beside it."""
    path = price_file if price_file is not None else default_price_file_path(config)
    return load_prices(path, path.parent / OVERRIDES_FILE_NAME)


def _write_json(path: Path, document: dict) -> None:
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
