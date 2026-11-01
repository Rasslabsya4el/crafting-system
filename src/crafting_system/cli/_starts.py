"""The choice of a start: plan each start option with the existing planner and keep the cheapest total (ADR-0059, ticket #330).

`plan_with_starts` is `make_plan` for a target whose start item may also be made by a vendor recipe. The start options are a list of
priced candidates with a source (`_start_options`): the target's own start item (`plain`), then the recipe-made items that can
help. The choice is made here, **outside the solver**: one plan per candidate, each by `make_plan` on the target with that
candidate as its start item and its price as the start price, and the answer is the candidate with the smallest **total**, the start
price plus the plan's expected cost still to pay. Nothing in `solver` learns what a candidate is, so the choice works with today's
solver and with the one of #312.

* **Order and ties.** The plain start item is planned first, then the recipe starts from the cheapest to the dearest. A tie goes to
  the earlier one, so a recipe start must be strictly cheaper to win.
* **A sound shortcut.** A candidate whose start price alone is not below the best total found so far cannot win (the cost still
  to pay is never negative), so it is not planned; the report says so. This changes no answer.
* **The rule axis.** A recipe may read a rule axis (the elemental cap: `wiki` T3 is the plan, `coe` T2). The cheapest start is found
  at every reading; the plan is the one at the plan reading (the first value of every axis) and the answer carries the cheapest
  total at each reading and their range (ADR-0022, ADR-0059). A candidate planned for one reading is not planned again for another.
* **Off means untouched.** With `recipe_starts` false, or when no recipe takes the target's base kind, the result is exactly what
  `make_plan` returns, with no `starts`: the report and the JSON then read as they did before this ticket.
"""

import dataclasses
import itertools
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from crafting_system.data import GameData
from crafting_system.prices import PriceFile
from crafting_system.prices.price_source import DEFAULT_GAP_PERCENT, DEFAULT_PRICE_SOURCE
from crafting_system.targets import Target

from ._offers import Offer
from ._plan import Plan, PlanError, StartPrice, make_plan, resolve_start_price
from ._start_options import StartContext, StartList, StartSource, combine, vendor_recipe_starts
from ._start_types import (
    SOURCE_PLAIN,
    ConsideredStart,
    Reading,
    ReadingChoice,
    StartCandidate,
    StartChoice,
)

PLAIN_KEY = "plain"
PLAIN_LABEL = "the target's own start item"
SOURCES: tuple[StartSource, ...] = (vendor_recipe_starts,)  # a bought-item source (research #337) is one more entry


def plain_candidate(target: Target, prices: PriceFile, override: float | None) -> StartCandidate:
    """The target's own start item with its price (`resolve_start_price`); an unpriced one has an infinite price and fails when planned."""
    try:
        price = resolve_start_price(target, prices, override)
        chaos, name, source = price.chaos, price.name, price.source
    except PlanError as error:
        chaos, name, source = math.inf, target.start_price, str(error)
    return StartCandidate(PLAIN_KEY, SOURCE_PLAIN, PLAIN_LABEL, target.start_item, chaos, name, source)


def readings_of(axes: tuple[tuple[str, tuple[str, ...]], ...]) -> list[Reading]:
    """Every reading of the rule axes, the plan reading (the first value of each axis) first; `[()]` when there is no axis."""
    if not axes:
        return [()]
    names = [name for name, _ in axes]
    return [tuple(zip(names, values, strict=True)) for values in itertools.product(*(values for _, values in axes))]


@dataclass
class _Outcome:
    """What planning one candidate gave: a plan, or an error; `plan` is dropped once it is not the plan of the answer."""

    plan: Plan | None
    mean_remaining: float
    total: float
    error: str | None
    approximate: bool


def _plan_candidate(
    data: GameData, target: Target, prices: PriceFile, candidate: StartCandidate, override: float | None, **kwargs: Any
) -> _Outcome:
    """Plan `target` from `candidate` with the existing planner; a `PlanError` is an outcome, not a crash."""
    try:
        if candidate.key == PLAIN_KEY:
            plan = make_plan(data, target, prices, start_price=override, **kwargs)
        else:
            moved = dataclasses.replace(target, start_item=candidate.item, start_price=None)
            price = StartPrice(candidate.price_name, candidate.price, candidate.price_source)
            plan = make_plan(data, moved, prices, start_price_of=price, **kwargs)
    except PlanError as error:
        return _Outcome(None, math.inf, math.inf, str(error), False)
    return _Outcome(plan, plan.mean_remaining, plan.start_price.chaos + plan.mean_remaining, None, plan.approximation is not None)


def plan_with_starts(
    data: GameData,
    target: Target,
    prices: PriceFile,
    *,
    recipe_starts: bool = True,
    start_price: float | None = None,
    sources: tuple[StartSource, ...] = SOURCES,
    offers: Iterable[Offer] | None = None,
    price_source: str = DEFAULT_PRICE_SOURCE,
    price_gap_percent: float = DEFAULT_GAP_PERCENT,
    today: date | None = None,
    **kwargs: Any,
) -> Plan:
    """Plan `target` from every start option and return the plan of the cheapest total, with the comparison in `Plan.starts`.

    `recipe_starts` is the user setting: false makes this exactly `make_plan`. `start_price` is the plain start item's price for
    this run (it does not apply to a recipe start, whose price is its goods). `kwargs` go to `make_plan` unchanged (`budget`,
    `rates`, `strands`). `sources` are the start sources after the plain one. `price_source` (`ninja`, `trade`, `both`), `price_gap_percent`
    and `today` are the profile setting of ticket #357; they go to every source in its `StartContext` and change nothing for the plain
    start item or for a recipe start, which are priced from the price file as before. Raises `PlanError` as `make_plan` does when no
    start option reaches the goal (the message is the plain start item's).
    """
    offers = tuple(offers) if offers is not None else None  # several plans read them
    if not recipe_starts:
        return make_plan(data, target, prices, start_price=start_price, offers=offers, **kwargs)
    listing = combine([source(StartContext(data, target, prices, price_source, price_gap_percent, today)) for source in sources])
    if not listing.candidates and not listing.refused:
        return make_plan(data, target, prices, start_price=start_price, offers=offers, **kwargs)

    plain = plain_candidate(target, prices, start_price)
    order = [plain, *sorted(listing.candidates, key=lambda candidate: (candidate.price, candidate.key))]
    outcomes: dict[str, _Outcome] = {}
    skipped: dict[str, str] = {}
    by_reading: list[ReadingChoice] = []
    chosen_key: str | None = None
    for index, reading in enumerate(readings_of(listing.axes)):
        best_key, best_total = None, math.inf
        for candidate in order:
            if not candidate.exists_in(reading):
                continue
            if candidate.key not in outcomes:
                if candidate.key != PLAIN_KEY and candidate.price >= best_total:
                    skipped.setdefault(candidate.key, f"its start price {candidate.price:,.2f} Chaos is not below the best total found, {best_total:,.2f}")
                    continue
                outcomes[candidate.key] = _plan_candidate(data, target, prices, candidate, start_price, offers=offers, **kwargs)
            total = outcomes[candidate.key].total
            if total < best_total:
                best_key, best_total = candidate.key, total
        by_reading.append(ReadingChoice(reading, best_key, best_total))
        if index == 0:
            chosen_key = best_key
        for key, outcome in outcomes.items():
            if key != chosen_key:
                outcome.plan = None  # only the plan of the answer is kept
    if chosen_key is None:
        raise PlanError(outcomes[PLAIN_KEY].error or "no start option reaches the goal")
    chosen = next(candidate for candidate in order if candidate.key == chosen_key)
    plan = outcomes[chosen_key].plan
    assert plan is not None
    considered = []
    for candidate in order:
        outcome = outcomes.get(candidate.key)
        if outcome is None:
            considered.append(ConsideredStart(candidate, "not planned", None, None, False, skipped.get(candidate.key, "")))
        elif outcome.error is not None:
            considered.append(ConsideredStart(candidate, "failed", None, None, False, outcome.error))
        else:
            state = "chosen" if candidate.key == chosen_key else "planned"
            considered.append(ConsideredStart(candidate, state, outcome.mean_remaining, outcome.total, outcome.approximate))
    choice = StartChoice(
        chosen, tuple(considered), listing.refused, listing.axes, tuple(by_reading), _claims(chosen, order, tuple(by_reading))
    )
    return dataclasses.replace(plan, starts=choice)


def _claims(chosen: StartCandidate, order: list[StartCandidate], by_reading: tuple[ReadingChoice, ...]) -> tuple[str, ...]:
    """The `approximate` claims the answer rests on: those of the chosen start, and of every start that depends on a rule axis
    when the axis changes the cheapest total (then the range needs its reason)."""
    totals = [entry.total for entry in by_reading]
    found = set(chosen.claims)
    if max(totals) - min(totals) > 1e-9 * max(1.0, abs(max(totals))):
        found |= {claim for candidate in order if candidate.axis is not None for claim in candidate.claims}
    return tuple(sorted(found))
