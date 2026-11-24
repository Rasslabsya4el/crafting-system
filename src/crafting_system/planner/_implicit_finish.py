"""The implicit finish of a plan (ticket #1231, #159 part 2): the roll of a base implicit a target asks for, made by Blessed Orbs after the mods.

A Blessed Orb rerolls the values of the item's ranged implicits and nothing else (`actions/blessed.py`, `Adds.implicits` with
`Adds.needs_roll_limit`), each value uniform over its range whatever it was before (`blessed_orb.previous_value_can_repeat`). No other method of
the beta changes or reads a base implicit (the Orb of Scouring, the essences, the fossils, the bench, the Harvest crafts, the Awakener's Orb, the
imprints and the influenced Exalted Orbs all keep it; the Embers, Ichors and Orbs of Conflict put an Eldritch implicit in its place, the Vaal Orb
and the Locus corrupt the item, and the recombinator, a deferred method, picks implicits). So where none of those is offered every state the
mods pass through holds the start item's implicit as it was, a restart gives it back, and once the mods are made the cheapest way on is the
Blessed Orbs alone: each use meets every implicit wish with one chance `p`, the same at every use, so the mean number of uses is `1 / p` from a
start that fails a wish (0 from one that meets them all). The plan of a target with such a wish is then exactly the plan of the same target
without it plus `b / p` at `b` Chaos per Blessed Orb: the same split as the quality finish (`_quality_finish.py`) and the socket finish
(`_finish.py`), and the search of the mods holds no implicit at all.

The finish is exact only under those conditions, so `applies` and `holds` check them: every implicit wish of the target is met by a base implicit
the start item holds (no Eldritch and no corrupted implicit: those are planned in the search), the start item is neither corrupted nor holds an
Eldritch implicit (a Blessed Orb is not offered on one), the run does not name Hinekora's Lock (a Blessed Orb is a burn of the Lock, ADR-0056,
which would reroll the implicit inside the mods), and no offered action changes or reads the implicits or corrupts the item. Where they fail
the implicit is planned inside the one search, the Blessed Orb an offer of it (the key of the bound's model holds the implicit's roll status,
ticket #158); `FINISH` off sends every target there (the tests of that search).

The page and the text draw the finish as the last step of the route (#1234, `ImplicitFinish.step`, `_finish_steps`), and the plan's risk is
that of the whole craft (`_plan.add_risk`); the answer also says it in one line (`implicit_finish_limits`): the Blessed Orb, its mean number of
uses and cost, and the total with the mods and the other finishes.
"""

from __future__ import annotations

import itertools
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.actions import NotApplicableError, OutOfScopeError, catalog_kinds
from crafting_system.data import GameData
from crafting_system.items import ImplicitMod, Item, eldritch_side
from crafting_system.prices import PriceFile
from crafting_system.prices.price_source import DEFAULT_PRICE_SOURCE
from crafting_system.targets import ImplicitRequirement, Target

from . import _limits
from ._finish_steps import IMPLICIT, FinishStep
from ._foresight import lock_wanted
from ._limits import Limit, unpriced_limits
from ._offers import DroppedOffer, PricedOffer, offer_of, price_offers

BLESSED_KIND = "blessed-orb"
FINISH = True  # off: the implicit is searched with the mods even where the finish is exact (the tests of that search)
MAX_CASES = 100_000  # the joint classes of the rolls a chance is summed over; an implicit of the game has at most a few


class ImplicitFinishRefused(ValueError):
    """The implicit finish of a target cannot be planned; the text says why in a player's words."""


@dataclass(frozen=True)
class ImplicitFinish:
    """The implicit finish of a plan: the wishes it meets, the Blessed Orb it takes (None when the start item already meets them), the chance
    one use meets them all, its mean number of uses, and the orbs left out for lack of a price."""

    wanted: tuple[ImplicitRequirement, ...]
    words: str  # the wishes in a player's words
    orb: PricedOffer | None
    chance: Fraction
    uses: Fraction
    dropped: tuple[DroppedOffer, ...]

    @property
    def value(self) -> float:
        """The mean cost of the finish in Chaos: the mean number of Blessed Orbs times the price of one."""
        return 0.0 if self.orb is None else float(self.uses) * self.orb.cost

    def step(self) -> FinishStep | None:
        """The finish as the last step of the route (#1234): one state that each use leaves with the chance of meeting every wish; None when
        the start item already meets them."""
        if self.orb is None:
            return None
        law = ((0, ((self.chance, None), (1 - self.chance, 0))),) if self.chance < 1 else ((0, ((self.chance, None),)),)
        return FinishStep(IMPLICIT, self.orb, f"the implicit {self.words}", self.uses, self.chance, law, ROLL_APPROXIMATE)


def _base_implicits(data: GameData, item: Item) -> frozenset[str]:
    return frozenset(entry.mod_id for entry in item.implicits if entry.mod_id in data.mods and eldritch_side(data.mods[entry.mod_id]) is None)


def applies(data: GameData, target: Target, offers: Iterable | None = None, *, judged: bool = False) -> bool:
    """Whether the implicit wishes of `target` are planned as a finish (module text); `offers` are a caller's own offers, None for the planner's.

    The guide's own plan of its actions (`judged`, `_entry.guide_plan`) keeps the implicit in its model: its route may name a Blessed Orb as
    one of its steps. A solved plan a route is judged against finishes it, and reads the route's Blessed Orb rule as the finish (#1234)."""
    if not FINISH or judged or offers is not None or not target.implicits or lock_wanted(target.actions):
        return False
    start = target.start_item
    if start.corrupted or start.eldritch_implicits(data):
        return False
    held = _base_implicits(data, start)
    return all(not wish.corrupted and wish.mod_ids & held for wish in target.implicits)


def holds(data: GameData, actions: Iterable) -> bool:
    """Whether no action of `actions` (the plan's offered actions, the restart apart) changes or reads the implicits, or corrupts the item."""
    for action in actions:
        adds = action.adds(data)
        if adds.implicits or adds.corrupts or action.reads(data).implicits:
            return False
    return True


def _classes(law: dict[int, Fraction], thresholds: Collection[int]) -> list[tuple[int, Fraction]]:
    """The values of one stat a requirement can tell apart, each with its chance: the lowest value and every threshold inside the range, each
    standing for the values from it up to the next one (a requirement only compares a value with its thresholds)."""
    values = sorted(law)
    points = sorted({values[0], *(limit for limit in thresholds if values[0] < limit <= values[-1])})
    found = []
    for at, point in enumerate(points):
        upto = points[at + 1] if at + 1 < len(points) else values[-1] + 1
        found.append((point, sum((chance for value, chance in law.items() if point <= value < upto), Fraction(0))))
    return found


def chance_of_meeting(data: GameData, action, item: Item, wanted: Iterable[ImplicitRequirement]) -> Fraction:
    """The exact chance that one use of `action` (an action that rerolls implicit values, its outcomes giving `value_law`) on `item` leaves an
    item that meets every wish of `wanted`, from the action's own outcomes (its contract)."""
    wanted = tuple(wanted)
    try:
        outcomes = action.outcomes(data, item)
    except NotApplicableError as error:
        raise ImplicitFinishRefused(f"{action.label(data)} cannot finish the implicit: {error}") from None
    ((share, made),) = outcomes.results  # one result of probability 1 whose rerolled values stand at their lowest; `value_law` gives each
    rerolled = getattr(outcomes, "rerolled", ())
    thresholds: dict[tuple[str, int], set[int]] = {}
    for wish in wanted:
        for mod_id in wish.mod_ids & set(rerolled):
            for index, limit in enumerate(wish.min_roll or ()):
                if limit is not None:
                    thresholds.setdefault((mod_id, index), set()).add(limit)
    stats = sorted(thresholds)
    classes = [_classes(outcomes.value_law(mod_id, index), thresholds[(mod_id, index)]) for mod_id, index in stats]
    cases = 1
    for each in classes:
        cases *= len(each)
    if cases > MAX_CASES:
        raise ImplicitFinishRefused(f"{action.label(data)} rerolls more values than the finish can sum over")
    met = Fraction(0)
    for picked in itertools.product(*classes):
        chosen = dict(zip(stats, (value for value, _ in picked)))
        implicits = tuple(
            ImplicitMod(entry.mod_id, entry.grade, tuple(chosen.get((entry.mod_id, index), value) for index, value in enumerate(entry.values)))
            for entry in made.implicits
        )
        rolled = made.changed(data, implicits=implicits)
        if all(wish.is_met_by(rolled) for wish in wanted):
            chance = Fraction(share)
            for _, part in picked:
                chance *= part
            met += chance
    return met


def _words(data: GameData, start: Item, wanted: Iterable[ImplicitRequirement]) -> str:
    """The wishes as a player reads them: the implicit's text and the roll asked."""
    parts = []
    for wish in wanted:
        held = [entry for entry in start.implicits if entry.mod_id in wish.mod_ids]
        text = (data.mods[held[0].mod_id].text or held[0].mod_id) if held else "the implicit"
        stats = data.mods[held[0].mod_id].stats if held else ()
        # a limit at the top of its stat's range is that value exactly: "rolls 35", not "35 or more" (crafter, #1231)
        rolls = [
            str(limit) if index < len(stats) and limit >= stats[index].max else f"{limit} or more"
            for index, limit in enumerate(wish.min_roll or ())
            if limit is not None
        ]
        parts.append(f"{text} rolls {' and '.join(rolls)}" if rolls else f"{text} is held")
    return "; ".join(parts)


def plan_implicit_finish(
    data: GameData, target: Target, prices: PriceFile, price_source: str = DEFAULT_PRICE_SOURCE, *, names: Collection[str] | None = None
) -> ImplicitFinish:
    """The implicit finish of `target` from its start item's implicits, with the Blessed Orbs `names` allows (None: every one), at today's prices."""
    wanted = tuple(target.implicits)
    start = target.start_item
    words = _words(data, start, wanted)
    if all(wish.is_met_by(start) for wish in wanted):
        return ImplicitFinish(wanted, words, None, Fraction(1), Fraction(0), ())
    listed = catalog_kinds(data, start, names=(BLESSED_KIND,))
    giving = [
        offer_of(action, action.label(data), data, start, kind, shares=False)
        for action, kind in listed.items()
        if names is None or kind in names or action.label(data) in names
    ]
    if not giving:
        raise ImplicitFinishRefused(f"the target asks that the implicit {words}, and no Blessed Orb is among the methods offered")
    priced, dropped = price_offers(giving, prices, price_source)
    if not priced:
        missing = sorted({name for drop in dropped for name in drop.missing})
        unpriced = f" (without a price: {', '.join(missing)})" if missing else ""
        raise ImplicitFinishRefused(f"the target asks that the implicit {words}, and no Blessed Orb has a price{unpriced}")
    worked = []
    for entry in priced:
        try:
            chance = chance_of_meeting(data, entry.offer.action, start, wanted)
        except OutOfScopeError as error:
            raise ImplicitFinishRefused(f"{entry.label} cannot finish the implicit: {error}") from None
        if chance == 0:
            raise ImplicitFinishRefused(f"the target asks that the implicit {words}, which no roll of its range reaches")
        worked.append((chance, entry))
    chance, best = min(worked, key=lambda pair: pair[1].cost / float(pair[0]))  # the cheapest mean: the price over the chance
    return ImplicitFinish(wanted, words, best, chance, 1 / chance, dropped)


ROLL_APPROXIMATE = (
    "the chance per use is read from the roll law of the Blessed Orb (an approximate input: each value uniform over its range, the value it "
    "had able to come again)"
)


def implicit_finish_limits(finish: ImplicitFinish, total: float, *, at_most: bool = False) -> tuple[Limit, ...]:
    """What the answer says of the implicit finish, which the page and the text also draw as the last step (#1234): the last step, its mean and the total of the craft
    (`total`: the mods and every finish, after the start item); the Blessed Orbs left out for lack of a price. `at_most`: the total is an upper end."""
    if finish.orb is None:
        why = f"the start item's implicit {finish.words} already, which no step of the mods changes, so nothing is added to the cost of the mods"
        labels: tuple[str, ...] = ()
    else:
        costs = "costs at most" if at_most else "costs"
        why = (
            f"a last step, once the mods are made: {finish.orb.label} until the implicit {finish.words} (a chance of "
            f"{float(finish.chance):.2%} each), {float(finish.uses):,.2f} on average at {finish.orb.cost:,.2f} Chaos each, {finish.value:,.2f} "
            f"Chaos on average; so the whole craft {costs} {total:,.2f} Chaos on average after the start item, the mean the result "
            "gives"
        )
        labels = (finish.orb.label,)
    found = Limit(
        _limits.IMPLICIT_FINISH,
        "Implicit finished after the mods",
        why,
        "No step of the mods changes the implicit, so rolling it last changes no step of the mods; the mean number of Blessed Orbs is exact at "
        "the roll law read for the Blessed Orb (an approximate input: each value uniform over its range, the value it had able to come again).",
        labels,
    )
    return (found, *unpriced_limits((drop.label, drop.missing, drop.kind) for drop in finish.dropped))
