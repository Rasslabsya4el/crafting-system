"""The planner's one entry: a target, prices and settings in, a `Plan` out (ticket #880).

`plan_target` is what a caller of the planner calls: the command line, the benchmark command and, later, the website. It loads no
file and reads no date: the caller loads the game data, the target and the prices, and says in `PlanSettings` what a
run may do (the day prices are judged on is `PlanSettings.today`). It times its own stages (the run's budget, `crafting_system.budget`) and takes the number of worker processes from `crafting_system.parallel`. Today it is `_starts.plan_with_starts` under one name, so the plan is the one the command printed before the planner
left `cli` (with `recipe_starts` off it is `_plan.make_plan`).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from crafting_system.budget import Budget
from crafting_system.data import GameData
from crafting_system.prices import PriceFile
from crafting_system.prices.price_source import DEFAULT_GAP_PERCENT, DEFAULT_PRICE_SOURCE
from crafting_system.targets import Target

from . import _packed
from ._plan import Plan
from ._starts import plan_with_starts


@dataclass(frozen=True)
class PlanSettings:
    """What one run of the planner may do; every default is the planner's own (`plan_with_starts`, `make_plan`).

    * `recipe_starts`: also compare the start items a vendor recipe can make (ADR-0059); off, the plan starts from the target's own item.
    * `start_price`: what the target's own start item costs in Chaos for this run; None reads the price file.
    * `price_source`, `price_gap_percent`, `today`: how a bought start item is priced (`ninja`, `trade` or `both`; ticket #357).
    * `budget`: the run's aim and its net of time and memory (`crafting_system.budget`, OR-33); None is no aim and no net.
    * `strands`: consider Memory Strands.
    * `solver`: the search, one of `SOLVERS` (`auto` by default).
    * `judges_route`: the caller will judge a given route against the plan, so `auto` keeps the walk of the whole graph (#535, #732).
    """

    recipe_starts: bool = True
    start_price: float | None = None
    price_source: str = DEFAULT_PRICE_SOURCE
    price_gap_percent: float = DEFAULT_GAP_PERCENT
    today: date | None = None
    budget: Budget | None = None
    strands: bool = False
    solver: str = "auto"
    judges_route: bool = False


def plan_target(data: GameData, target: Target, prices: PriceFile, settings: PlanSettings = PlanSettings()) -> Plan:
    """The cheapest plan for `target` at `prices` under `settings`; raises `PlanError` where no plan can be made (`plan_with_starts`)."""
    return plan_with_starts(
        data, target, prices, recipe_starts=settings.recipe_starts, start_price=settings.start_price, price_source=settings.price_source,
        price_gap_percent=settings.price_gap_percent, today=settings.today, budget=settings.budget, strands=settings.strands,
        solver=settings.solver, judges_route=settings.judges_route,
    )  # fmt: skip


def progress() -> Callable[[str], None] | None:
    """Where the phases of a long plan are said (`_packed.PROGRESS`), or None when nobody listens."""
    return _packed.PROGRESS


def say_progress_to(sink: Callable[[str], None] | None) -> Callable[[str], None] | None:
    """Say the phases of a long plan to `sink` from now on (None: to nobody); returns the sink before, for the caller to put back."""
    previous = _packed.PROGRESS
    _packed.PROGRESS = sink
    return previous
