"""The command line: `python -m crafting_system.cli TARGET.yaml [--route ROUTE.yaml] [--strands] [--no-recipe-starts] [--price-source ninja|trade|both] [--solver auto|object|packed|envelope] [--verify] [--json PATH]`, `benchmark`, and `trade TARGET.yaml` (price the target's bought start item on the trade site, by hand).

This is the one place that reads the day and the settings of the environment for a plan (the planner is given both; it only times its own stages). It loads the game
data from the cache, the target, and the price file with its hand overrides, asks the planner for the plan (`planner.plan_target`), prints
the text tree, writes the JSON policy and, with `--verify`, runs the simulator against the computed
mean. Exit code 0 is a plan (and, with `--verify`, an agreeing simulation), 1 an error, 2 a
simulation that does not agree. With `--route` the given route (a YAML file of rules, see `_route`)
is evaluated as a fixed policy at the same prices and printed next to the policy's numbers.
`python -m crafting_system.cli benchmark [--out DIR]` runs the benchmark routes (see `_benchmark`).

`--solver` picks the search (ticket #535): `auto` (the default) is the envelope search wherever its bound can be built and the older
walk-and-solve path where the target is outside it (`make_plan` says which); `envelope`, `packed` and `object` name one. The envelope
search stops by itself as soon as its plan is proved to cost at most `--gap` percent (1 by default) more than the cheapest, whatever the time,
and says so beside the plan's exact mean (OR-32, OR-39, ticket #826); a proof that closes is the exact answer. `--exact`, or `--gap 0`, keeps
the exact proof however long it takes.

A walk asked for by name (`--solver packed`, `object`) that would run longer than `--budget` seconds is
answered approximately, within a certified 1% of the exact mean, and marked so (ADR-0023, `_decide`: retired, and never
reached by the default `--solver auto`, #926, #928);
`--exact` solves it exactly however long it takes. An approximate answer gives no certified p90; its `--verify`
runs the policy on concrete items and reports a simulated mean, p90 and CVaR labelled "simulated, not certified"
(ADR-0023, `_lift`); it gives no `--route` and no route page yet.

The plan compares the target's own start item with the start items a vendor recipe can make and keeps the cheapest total of start
price and expected crafting cost (ADR-0059, `_starts`). The setting `recipe_starts` of `crafting.toml` (default on), or
`--no-recipe-starts` for one run, turns that off; the plan is then the one `make_plan` gives. `--route` turns it off too, because a
given route is written for the target's own start item. With a `--budget`, each start option gets the whole budget.
The price source of a bought start item (`ninja`, `trade` or `both`, ticket #357) is the setting `price_source` of `crafting.toml`
(default `both`, with `price_gap_percent`, default 20) or `--price-source` for one run; it reaches the start sources, and a start
option the source prices shows both prices side by side with the gap flag. The plain start item and recipe starts do not read it.
"""

import argparse
import math
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from datetime import UTC, date, datetime
from pathlib import Path

from crafting_system.actions import NotApplicableError, OutOfScopeError, imprints_held_at_most
from crafting_system.budget import PROOF_GAP, Budget, default_memory_mb
from crafting_system.config import MEMORY_SHARE_SETTING, NO_LIMIT, PRICE_SOURCES, Config, load_config
from crafting_system.data import DataError, GameData, load_game_data
from crafting_system.prices import PriceFile, PriceFileNotFound, stale_warning
from crafting_system.solver import ConvergenceError
from crafting_system.targets import StartKind, TargetError, buy_spec_of, load_target
from crafting_system.planner import BUDGET_SECONDS, SOLVERS, PlanError, PlanSettings, plan_target, progress, say_progress_to

from ._benchmark import benchmark_main
from ._inputs import load_target_prices, write_json
from ._report import build_report, policy_document, render_text
from ._route import evaluate_route, load_route
from ._route_report import render_route_text, route_document
from ._route_view import write_route_page
from ._trade import trade_main
from ._verify import DEFAULT_RUNS, DEFAULT_SEED, verify

COMMAND = "python -m crafting_system.cli"


def _peak_megabytes() -> int:
    """The most memory this process has held, in MB (0 where the system does not say)."""
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    except ImportError:
        return 0


def _seconds(text: str) -> float:
    """A `--budget` value: a number of seconds, zero or more."""
    value = float(text)
    if not value >= 0 or value == float("inf"):
        raise argparse.ArgumentTypeError(f"the budget must be a number of seconds, zero or more, got {text!r}")
    return value


def _limit(text: str) -> float | None:
    """A `--time-limit` or `--memory-limit` value: a number above zero, or `none` for no limit (None)."""
    if text.strip().lower() == NO_LIMIT:
        return None
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not (value > 0 and math.isfinite(value)):
        raise argparse.ArgumentTypeError(f"a limit is a number above zero, or {NO_LIMIT}; got {text!r}")
    return value


def _percent(text: str) -> float:
    """A `--gap` value: a percent, zero or more."""
    value = float(text)
    if not (value >= 0 and math.isfinite(value)):
        raise argparse.ArgumentTypeError(f"the gap is a percent, zero or more (0 keeps the exact proof); got {text!r}")
    return value


_FROM_SETTINGS = object()  # a limit not given on the command line: the planner settings' value


def run_budget(
    config: Config, aim: float | None, time_limit: object = _FROM_SETTINGS, memory_limit: object = _FROM_SETTINGS, gap: float = PROOF_GAP
) -> Budget:
    """The run's budget (#825, OR-33): the aim (`--budget`, None with `--exact`), the net from the command line, else the planner settings, and
    the proof the search owes (`--gap` as a share, 0 with `--exact`; OR-32, OR-39)."""
    seconds = config.time_limit_seconds if time_limit is _FROM_SETTINGS else time_limit
    memory = config.memory_limit_mb if memory_limit is _FROM_SETTINGS else memory_limit
    if memory == MEMORY_SHARE_SETTING:
        memory = default_memory_mb()
    return Budget(aim_seconds=aim, seconds=seconds, memory_mb=memory, gap=gap)  # type: ignore[arg-type]


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

    if arguments[:1] == ["trade"]:
        return trade_main(arguments[1:], env=env, data=data)

    parser = argparse.ArgumentParser(
        prog=COMMAND, description="Find the cheapest crafting policy for a target item (YAML in, text and JSON out)."
    )
    parser.add_argument("target", help="the target YAML file (see examples/targets/)")
    parser.add_argument("--json", metavar="PATH", help="where to write the JSON policy (default: the output folder, named after the target)")
    parser.add_argument("--start-price", type=float, metavar="CHAOS", help="what the start item costs, in Chaos; wins over the price file")
    parser.add_argument("--route", metavar="ROUTE.yaml", help="also evaluate this given route (rules in YAML, see examples/routes/) as a fixed policy and compare it with the policy")
    parser.add_argument("--strands", action="store_true", help="consider Memory Strands (or turn them on in the planner settings); a start item with strands turns it on by itself")
    parser.add_argument("--no-recipe-starts", action="store_true", help="plan only from the target's own start item; do not compare the start items a vendor recipe can make (or turn recipe starts off in the planner settings)")
    parser.add_argument("--price-source", choices=PRICE_SOURCES, help="which price a bought start item is priced with: ninja, trade or both (or set it in the planner settings; default both)")
    parser.add_argument(
        "--solver", choices=SOLVERS, default="auto",
        help="how the cheapest route is searched. auto (default): the search that looks only at the states that could matter, whenever it can be "
        "built for the target; the walk of the whole graph where it cannot, and with --route (judging your route needs the planner's choice at every "
        "state your route reaches); for now, with 40 or more priced actions (the fossil sets), the walk that first proves most of them not needed. envelope: that search by name, and an error where it cannot be built. "
        "packed: walk the whole graph, then solve it exactly; slower on a big target and it can need many GB of memory, but it names every state. "
        "object: the same walk of the whole graph in plain objects; fine for a small target, it runs out of memory on a big one. "
        "With --exact the answer is the same exact mean whichever is chosen",
    )  # fmt: skip
    parser.add_argument("--exact", action="store_true", help="prove the plan the cheapest however long it takes: no approximate answer and no stop at --gap; the time and memory limits still stop it and say so, unless --time-limit none and --memory-limit none")
    parser.add_argument("--budget", type=_seconds, default=BUDGET_SECONDS, metavar="SECONDS", help=f"the time the plan aims at (default {BUDGET_SECONDS:g}): a walk of the whole graph asked for by name (packed, object) that would take longer is answered approximately; the search of auto and envelope does not read it (it stops at --gap), and auto walks exactly, to the time limit, where that search cannot be built")
    parser.add_argument("--gap", type=_percent, default=PROOF_GAP * 100.0, metavar="PERCENT", help=f"stop the search once the plan is proved to cost at most this many percent more than the cheapest, and say so beside its exact mean (default {PROOF_GAP * 100.0:g}); 0 keeps the exact proof")
    parser.add_argument(
        "--time-limit", type=_limit, default=_FROM_SETTINGS, metavar="SECONDS",
        help="stop the plan after this many seconds and say what it found and where it stopped, or none for no limit (default: the planner settings, 600)",
    )  # fmt: skip
    parser.add_argument(
        "--memory-limit", type=_limit, default=_FROM_SETTINGS, metavar="MB",
        help="stop the plan when it holds this many MB of memory and say so, or none for no limit (default: the planner settings, 80%% of the machine's memory)",
    )  # fmt: skip
    parser.add_argument("--progress", action="store_true", help="print the phases of a long plan (the walk, the merge, the solve, the risk, the report) with their seconds to stderr")
    parser.add_argument("--verify", action="store_true", help="also run the policy on concrete items and compare with the computed mean (an approximate answer: with its certified interval)")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"simulated crafts for --verify (default {DEFAULT_RUNS})")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"random seed for --verify (default {DEFAULT_SEED})")
    args = parser.parse_args(arguments)
    previous_progress = progress()
    setting = ExitStack()

    try:
        config = load_config(env)
        setting.enter_context(imprints_held_at_most(config.max_imprints))  # the setting `max_imprints` for the length of the plan (#223)
        game = data if data is not None else load_game_data(cache_dir=config.cache_dir)
        target_path = Path(args.target)
        target = load_target(target_path, game)
        price_file = prices if prices is not None else load_target_prices(target.price_file, config)
        run_day = today if today is not None else datetime.now(UTC).date()
        stale = stale_warning(price_file, run_day)
        if stale:
            print(f"Warning: {stale}", file=sys.stderr)

        began = time.perf_counter()

        def stage(text: str) -> None:
            if args.progress:
                memory = _peak_megabytes()
                print(f"[{time.perf_counter() - began:8.1f} s{f', {memory:,} MB' if memory else ''}] {text}", file=sys.stderr, flush=True)

        if args.progress:
            say_progress_to(stage)
        # a given route is written for the target's own start item, so `--route` plans from that item alone
        settings = PlanSettings(
            recipe_starts=config.recipe_starts and not args.no_recipe_starts and not args.route,
            start_price=args.start_price, price_source=args.price_source or config.price_source,
            price_gap_percent=config.price_gap_percent, today=run_day, budget=run_budget(config, None if args.exact else args.budget, args.time_limit, args.memory_limit, 0.0 if args.exact else args.gap / 100.0),
            strands=args.strands or config.memory_strands, solver=args.solver, judges_route=bool(args.route),
        )  # fmt: skip
        plan = plan_target(game, target, price_file, settings)
        if plan.approximation is not None and args.route:
            raise PlanError("--route is not available for an approximate answer yet; run again with --exact to get an exact one")
        stage(f"plan made: mean {plan.mean_remaining:,.4f} Chaos, {len(plan.solution.values):,} states solved")
        report = build_report(plan, game)
        stage(f"report built: {len(report.states):,} states")
        route_path = Path(args.route) if args.route else None
        route = load_route(route_path, plan, game) if route_path is not None else None
        given = evaluate_route(plan, route, game) if route is not None else None
        if given is not None:
            stage(f"given route evaluated: {len(given.gaps):,} gaps, mean {given.risk.mean.value:,.4f}")
        check = verify(game, plan, runs=args.runs, seed=args.seed) if args.verify else None
        if check is not None:
            stage(f"verified by {check.runs:,} simulated crafts: {'agrees' if check.agrees else 'DOES NOT AGREE'}")

        name = target_path.name
        print(render_text(report, check, target_name=name), end="")
        stage("text written")
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
            spec = buy_spec_of(game, target) if target.start is StartKind.BOUGHT else None  # computed from the target: the buy step's link and filter
            page = write_route_page(
                out.parent / f"{target_path.stem}.route.html", report, game, route=route, given=given,
                buy_spec=spec, cache_dir=config.cache_dir, target_name=name,
            )  # fmt: skip
            print(f"Route view written to {page}")
    except (TargetError, DataError, PriceFileNotFound, PlanError, NotApplicableError, OutOfScopeError, ConvergenceError, ValueError, OSError) as error:  # the refusals are ValueErrors: named so that the Error: line is known to carry their text
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        say_progress_to(previous_progress)
        setting.close()
    if check is not None and not check.agrees:
        return 2
    return 0
