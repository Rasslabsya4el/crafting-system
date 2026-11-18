"""The quality finish of a plan (ticket #159): the catalyst quality a target asks for, applied after the mods.

A catalyst only sets the quality (`Adds.only_quality`): it adds no mod, draws none and changes no odds (ADR-0029), and no other method of the
beta changes or reads the quality (the Orb of Scouring, the essences, the fossils, the bench, the Harvest crafts, the Awakener's Orb, the
imprints and the influenced Exalted Orbs all keep it; only the recombinator, a deferred method, reads and sets it). So every state the mods
pass through holds the start item's quality, a restart gives that quality back, and once the mods are made the cheapest way on is the
catalysts alone. The plan of a target with quality is then exactly the plan of the same target without it, plus the mean cost `Q(q0)` of
taking the start item's quality `q0` of the type asked to the percent asked (the chain of `mean_uses`, at most 20 states): the same split as
the socket finish (`_finish.py`, ADR-0045), and the search of the mods holds no quality at all.

The finish is exact only under those conditions, so `applies` and `holds` check them: the target asks for a catalyst quality, the run does
not name Hinekora's Lock (a burn keeps no quality yet: the Lock is not offered on a quality target, `LockStatus.WITH_QUALITY`), and no offered
action other than one that only sets the quality changes or reads it, nor corrupts the item (a corrupted item takes no catalyst, so the quality
would have to come before the corruption). Where they fail, the quality is planned inside the one search, as before (the bound's key holds the
quality and a catalyst is offered last, `Abstraction.quality_offer_pruned`); `FINISH` off sends every target there (the tests of that search).

Until the page draws the finish as a step of its own (#1234), the answer says it in one line (`quality_finish_limits`): the catalyst, its
mean number of uses and cost, and the total with the mods; the figures of the mods (mean, percentiles, steps) stay those of the mods.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.abstraction import Goal
from crafting_system.actions import NotApplicableError, catalog_kinds
from crafting_system.data import GameData
from crafting_system.prices import PriceFile
from crafting_system.prices.price_source import DEFAULT_PRICE_SOURCE
from crafting_system.targets import QualityRequirement, Target

from . import _limits
from ._foresight import lock_wanted
from ._limits import Limit, unpriced_limits
from ._offers import DroppedOffer, PricedOffer, _gives_quality_wanted, offer_of, price_offers

CATALYST_KIND = "catalyst"
FINISH = True  # off: the quality is searched with the mods even where the finish is exact (the tests of that search)


class QualityFinishRefused(ValueError):
    """The quality finish of a target cannot be planned; the text says why in a player's words."""


@dataclass(frozen=True)
class QualityFinish:
    """The quality finish of a plan: the catalyst it takes, its mean number of uses from the start item's quality, the catalysts of another type
    left out, and the catalysts left out for lack of a price."""

    wanted: QualityRequirement
    start_percent: int  # the start item's quality of the type asked (0 when it holds none or another type)
    catalyst: PricedOffer | None  # None when the start item already holds the quality asked
    uses: Fraction
    other_types: tuple[str, ...]
    dropped: tuple[DroppedOffer, ...]

    @property
    def value(self) -> float:
        """The mean cost of the finish in Chaos: the mean number of catalysts times the price of one."""
        return 0.0 if self.catalyst is None else float(self.uses) * self.catalyst.cost


def applies(target: Target, offers: Iterable | None = None) -> bool:
    """Whether the quality of `target` is planned as a finish (module text); `offers` are a caller's own offers, None for the planner's."""
    if not FINISH or not isinstance(target.quality, QualityRequirement) or lock_wanted(target.actions):
        return False
    return offers is None


def holds(data: GameData, actions: Iterable) -> bool:
    """Whether no action of `actions` (the plan's offered actions, the restart apart) changes or reads the quality without only setting it, or
    corrupts the item."""
    for action in actions:
        adds = action.adds(data)
        if adds.only_quality:
            continue
        if adds.quality or adds.corrupts or action.reads(data).quality:
            return False
    return True


def mean_uses(data: GameData, action, item, wanted: QualityRequirement) -> Fraction:
    """The exact mean number of uses of `action` that take `item` to the quality `wanted`, from the action's own outcomes (its contract).

    The quality only rises under a catalyst of the type asked, so the chain is walked down from the states it reaches, at most 20; an
    outcome that keeps the quality as it is is a repeat of the use and enters the mean by the usual `1 / (1 - p)`."""
    memo: dict = {}

    def mean(current, depth: int = 0) -> Fraction:
        if wanted.is_met_by(current):
            return Fraction(0)
        key = current.quality
        if key in memo:
            return memo[key]
        if depth > 100:
            raise QualityFinishRefused(f"{action.label(data)} does not raise the quality towards the percent asked")
        try:
            results = action.outcomes(data, current).results
        except NotApplicableError as error:
            raise QualityFinishRefused(f"{action.label(data)} cannot finish the quality: {error}") from None
        stay, onward = Fraction(0), Fraction(1)
        for chance, made in results:
            if made.quality == key:
                stay += Fraction(chance)
            else:
                onward += Fraction(chance) * mean(made, depth + 1)
        if stay >= 1:
            raise QualityFinishRefused(f"{action.label(data)} never changes the quality of the item")
        memo[key] = onward / (1 - stay)
        return memo[key]

    return mean(item)


def plan_quality_finish(
    data: GameData, target: Target, prices: PriceFile, price_source: str = DEFAULT_PRICE_SOURCE, *, names: Collection[str] | None = None
) -> QualityFinish:
    """The quality finish of `target` from its start item's quality, with the catalysts `names` allows (None: every one), at today's prices."""
    wanted = target.quality
    if not isinstance(wanted, QualityRequirement):
        raise ValueError("the quality finish is of a catalyst quality")
    start = target.start_item
    held = start.quality
    percent = held.percent if held is not None and getattr(held, "type", None) is wanted.type else 0
    goal = Goal.from_target(target)
    listed = catalog_kinds(data, start, names=(CATALYST_KIND,))
    giving, other = [], []
    for action, kind in listed.items():
        label = action.label(data)
        if names is not None and kind not in names and label not in names:
            continue
        if _gives_quality_wanted(data, goal, start, action):
            giving.append(offer_of(action, label, data, start, kind, shares=False))
        else:
            other.append(label)
    what = f"{wanted.min_percent}% {wanted.type.value.capitalize()} quality"
    if wanted.is_met_by(start):
        return QualityFinish(wanted, percent, None, Fraction(0), tuple(other), ())
    priced, dropped = price_offers(giving, prices, price_source)
    if not priced:
        missing = sorted({name for drop in dropped for name in drop.missing})
        unpriced = f" (without a price: {', '.join(missing)})" if missing else ""
        raise QualityFinishRefused(f"the target asks for {what}, and no catalyst of that type is among the methods offered{unpriced}")
    worked = [(mean_uses(data, entry.offer.action, start, wanted), entry) for entry in priced]
    uses, best = min(worked, key=lambda pair: float(pair[0]) * pair[1].cost)
    return QualityFinish(wanted, percent, best, uses, tuple(other), dropped)


def quality_finish_limits(finish: QualityFinish, mods_mean: float, *, mods_at_most: bool = False) -> tuple[Limit, ...]:
    """What the answer says of the quality finish until the page draws it as a step (#1234): the last step, its mean beside the mods' and the
    total; the catalysts of another type left out; the catalysts left out for lack of a price. `mods_at_most`: the mods' mean is an upper end."""
    wanted = finish.wanted
    what = f"{wanted.min_percent}% {wanted.type.value.capitalize()} quality"
    if finish.catalyst is None:
        why = f"the start item already has {what}, which no step of the mods changes, so nothing is added to the cost of the mods"
        labels: tuple[str, ...] = ()
    else:
        total = mods_mean + finish.value
        costs = "costs at most" if mods_at_most else "costs"
        held = f" from the start item's {finish.start_percent}%" if finish.start_percent else ""
        why = (
            f"the last step, once the mods are made: {finish.catalyst.label} until the item has {what}{held}, {float(finish.uses):,.2f} on "
            f"average at {finish.catalyst.cost:,.2f} Chaos each, {finish.value:,.2f} Chaos on average; so the whole craft {costs} "
            f"{total:,.2f} Chaos on average after the start item; every other figure of this answer is of the mods alone"
        )
        labels = (finish.catalyst.label,)
    found = [
        Limit(
            _limits.QUALITY_FINISH,
            "Quality finished after the mods",
            why,
            "No step of the mods changes the quality, so finishing it last changes no step of the mods; the mean number of catalysts is exact at "
            "the gain law of the catalysts.",
            labels,
        )
    ]
    if finish.other_types:
        found.append(
            Limit(
                _limits.QUALITY,
                "Not offered",
                "it only sets the quality, and never to the type the target asks for: a catalyst of another type restarts the quality from 0%",
                "The plan is unaffected: such a catalyst only costs currency and undoes the quality asked.",
                finish.other_types,
            )
        )
    return (*found, *unpriced_limits((drop.label, drop.missing, drop.kind) for drop in finish.dropped))
