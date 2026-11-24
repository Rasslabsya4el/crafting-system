"""The planner's one entry: a target, prices and settings in, a `Plan` out (ticket #880).

`plan_target` is what a caller of the planner calls: the command line, the benchmark command and, later, the website. It loads no
file and reads no date: the caller loads the game data, the target and the prices, and says in `PlanSettings` what a
run may do (the day prices are judged on is `PlanSettings.today`). It times its own stages (the run's budget, `crafting_system.budget`) and takes the number of worker processes from `crafting_system.parallel`. Today it is `_starts.plan_with_starts` under one name, so the plan is the one the command printed before the planner
left `cli` (with `recipe_starts` off it is `_plan.make_plan`).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

from crafting_system.budget import Budget
from crafting_system.data import GameData
from crafting_system.prices import PriceFile
from crafting_system.prices.price_source import DEFAULT_GAP_PERCENT, DEFAULT_PRICE_SOURCE
from crafting_system.targets import Target

from . import _implicit_finish, _packed, _quality_finish
from ._envelope import Standing
from ._offers import unmodelled_labels
from ._plan import Plan, PlanError, StartPrice, make_plan
from ._starts import plan_with_starts


@dataclass(frozen=True)
class PlanSettings:
    """What one run of the planner may do; every default is the planner's own (`plan_with_starts`, `make_plan`).

    * `recipe_starts`: also compare the start items a vendor recipe can make (ADR-0059); off, the plan starts from the target's own item.
    * `start_price`: what the target's own start item costs in Chaos for this run; None reads the price file.
    * `price_source`, `price_gap_percent`, `today`: how a bought start item is priced (`ninja`, `trade` or `both`; ticket #357).
    * `budget`: the run's aim and its net of time and memory (`crafting_system.budget`, OR-33), and the proof it owes (`Budget.gap`,
      OR-32, OR-39: the search stops once its plan is proved at most 1% above the cheapest); None is no aim and no net, and the proof is exact.
    * `watch`: told where the search stands, from its first executable plan on (`Standing`: the best plan's cost so far and the figure no plan
      can cost less than, both after the start item), so a caller can show a plan while the proof goes on; with start options, once per option.
    * `strands`: consider Memory Strands.
    * `solver`: the search, one of `SOLVERS` (`auto` by default).
    * `judges_route`: the caller will judge a given route against the plan. It changes nothing since #986: the route is evaluated on its own
      reach (as objects, or on packed arrays when that reach is big), so `auto` takes the envelope search for it as for any plan, and nothing
      walks the whole graph for it.
    * `route_actions`: the labels the judged route names (`cli._route.route_actions`, read without a plan), or None when they are not known.
      Known, they lead the first round of the offers, so a target whose offers are searched in rounds is searched so for a judged route too, and
      the plan holds every action the route takes (#1110); not known, a judged route may name any offer and the offers are searched at once.
    * `time_limit_seconds`: the time limit one request asks for (#1577, OR-40): the run stops at it and says so, as at the budget's own net.
      It is a request's limit within the machine's: `budget.seconds` is the machine's maximum, and a request may ask for less or as much,
      never more (`PlanError`); None is the budget's own net. A request that asks for more time asks for a run of its own: it starts over.
    * `methods`: the methods the run may use (the user's setting, #405, OR-5, OR-13, OR-41): kinds of the catalog (`chaos-orb`, `essence`)
      or labels of single actions ("Essence of Insanity"), as `kinds()` and the offers name them; None is every beta method the planner
      offers by default (OR-37). A target never names them (its file's `actions:` key is refused); a run with fewer says so in its answer
      ("Methods this run's setting leaves out").
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
    watch: Callable[[Standing], None] | None = None
    route_actions: tuple[str, ...] | None = None
    methods: tuple[str, ...] | None = None
    time_limit_seconds: float | None = None


def request_budget(budget: Budget | None, seconds: float | None) -> Budget | None:
    """The budget one request runs under (#1577, OR-40): `budget` (the machine's) with its time net set to the request's `seconds`, which may
    not pass the machine's own net; None for `seconds` keeps `budget` as it is. With no budget, the request's limit is the only net: no aim,
    no memory net and the exact proof, as no budget means. Raises `PlanError` for a limit that is not a number above zero, past the
    machine's maximum, or asked of a run counted in states (its work is counted in states, never in seconds: `Budget.in_states`)."""
    if seconds is None:
        return budget
    try:  # a JSON integer too large for a float is no number of seconds either (it would overflow, not be refused)
        number = float(seconds) if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else math.nan
    except OverflowError:
        number = math.nan
    if not (math.isfinite(number) and number > 0):
        raise PlanError(f"a request's time limit is a number of seconds above zero; got {str(seconds)[:40]!r}")
    seconds = number
    if budget is None:
        return Budget(aim_seconds=None, seconds=float(seconds), memory_mb=None, gap=0.0)
    if budget.counted:
        raise PlanError("a run counted in states takes no time limit: its work is counted in states, never in seconds")
    if budget.seconds is not None and seconds > budget.seconds:
        raise PlanError(f"the time limit asked, {seconds:,.0f} s, is past this machine's own limit of {budget.seconds:,.0f} s")
    return replace(budget, seconds=float(seconds))


def plan_target(data: GameData, target: Target, prices: PriceFile, settings: PlanSettings = PlanSettings()) -> Plan:
    """The cheapest plan for `target` at `prices` under `settings`; raises `PlanError` where no plan can be made (`plan_with_starts`), or
    where the request's time limit cannot be had (`request_budget`)."""
    budget = request_budget(settings.budget, settings.time_limit_seconds)
    return plan_with_starts(
        data, target, prices, recipe_starts=settings.recipe_starts, start_price=settings.start_price, price_source=settings.price_source,
        price_gap_percent=settings.price_gap_percent, today=settings.today, budget=budget, strands=settings.strands,
        solver=settings.solver, judges_route=settings.judges_route, watch=settings.watch,
        route_actions=settings.route_actions, methods=settings.methods,
    )  # fmt: skip


class NotModelled(PlanError):
    """A given route names an action the model does not hold for its target's item (a deferred method, OR-37, or a label no action bears):
    its route cannot be priced, and `labels` are the actions, by name (#1442)."""

    def __init__(self, labels: tuple[str, ...]) -> None:
        self.labels = labels
        super().__init__(f"{', '.join(labels)} {'is' if len(labels) == 1 else 'are'} not modelled")


def guide_plan(data: GameData, target: Target, prices: PriceFile, labels: tuple[str, ...], settings: PlanSettings = PlanSettings()) -> Plan:
    """The plan a given route (a guide's) is priced on with its OWN actions (#1442): the target's own start item, and the actions of the
    catalog that bear the route's `labels` (`cli._route.route_actions`) as the offers, priced at `prices`, with nothing solved.

    The route is a fixed policy, evaluated exactly on its own reach (`cli._route.evaluate_route`), so its cost needs no search and no plan of
    the planner's: only its actions, the model of the item they act on and the start. It is therefore the same whichever offers the
    planner's own search happened to run (the groups of `_rounds`). The plan is made as one a route is judged against (`judges_route`): the
    quality and the implicit stay in the model, since a guide may name the catalyst or the orb that sets them. A catalyst quality or a base
    implicit that NO action of the route changes is left out of the model instead, as the planner's own plan leaves it to a finish after
    the mods (`_quality_finish`, `_implicit_finish`): the route could never reach it, and the plan's cost it is compared with holds the mods
    alone; a finish the route keeps in its model is in its cost, and the caller compares it with the plan's mods and that finish
    (`Plan.quality_finish_value`, `Plan.implicit_finish_value`). Raises `NotModelled` naming each label no action of the catalog bears on this item, and `PlanError` as `make_plan` does (a label
    the catalog bears but the item never takes, no price for the start item)."""
    if not labels:
        raise PlanError("the guide's route names no action (only `restart`, or a file that cannot be read): there is nothing to price")
    missing = unmodelled_labels(data, target.start_item, labels)
    if missing:
        raise NotModelled(missing)

    def made(asked: Target, start: StartPrice | None = None) -> Plan:
        return make_plan(
            data, asked, prices, start_price=settings.start_price, start_price_of=start, price_source=settings.price_source, solve_it=False,
            with_risk=False, judges_route=True, route_actions=labels, methods=labels, strands=settings.strands,
        )  # fmt: skip

    plan = made(target)
    named = [priced.offer.action for priced in plan.offers if priced.label in labels]
    # an action that sets, changes or reads the quality (or the implicits), or corrupts the item, keeps it in the model, as `holds` keeps it for the planner
    quality_left = _quality_finish.applies(target) and not any(
        (adds := action.adds(data)).quality or adds.only_quality or adds.corrupts or action.reads(data).quality for action in named
    )
    implicit_left = _implicit_finish.applies(data, target) and not any(
        (adds := action.adds(data)).implicits or adds.corrupts or action.reads(data).implicits for action in named
    )
    if not (quality_left or implicit_left):
        return plan
    # the start item is the one the target describes, priced as it (OR-3): its key is computed from the whole target (`make_plan`'s `priced_as`)
    mods = replace(target, quality=None if quality_left else target.quality, implicits=() if implicit_left else target.implicits)
    return made(mods, plan.start_price)


def progress() -> Callable[[str], None] | None:
    """Where the phases of a long plan are said (`_packed.PROGRESS`), or None when nobody listens."""
    return _packed.PROGRESS


def say_progress_to(sink: Callable[[str], None] | None) -> Callable[[str], None] | None:
    """Say the phases of a long plan to `sink` from now on (None: to nobody); returns the sink before, for the caller to put back."""
    previous = _packed.PROGRESS
    _packed.PROGRESS = sink
    return previous
