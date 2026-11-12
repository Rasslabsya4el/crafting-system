"""The socket finish of a plan (ticket #231, B6 S5; ADR-0045, ADR-0049): its actions, their prices, its solve, and what the answer says of it.

A target that names sockets is planned in two parts. The mods are planned as before: the compressed state holds no socket, so the plan of the
mods is the plan of a target without sockets. The finish is solved on its own (`abstraction.solve_finish`) from the sockets the goal item holds,
which are the start item's (no mod action changes sockets, ADR-0045; one that does is refused below), and its value is added to every goal state.
With one finish value for every goal state (the case until Orb of Binding gives a goal a second one, ticket #232), adding it changes no choice of
the mods: every plan that reaches the goal pays it once, so the plan of the mods stays the cheapest and its mean grows by the finish
(`Plan.total_mean`).

The finish actions are the socket kinds of the catalog (`FINISH_KINDS`, kinds the mods never offer) and, below 20% quality, the Whetstone or the Scrap
(`QUALITY_KIND`, ADR-0049). A target's `actions:` names them like any kind: when it is given, only the finish kinds it names (by kind or by label) are
offered. Each is priced by `price_offers`; one without a price is left out and said, as a mod action is.

Refused here, with the reason (`FinishRefused`, which `make_plan` turns into its `PlanError`): a start item that does not state its sockets
(`sockets: any`), a target that takes a corrupted item (the finish of a corrupted item is ticket #267's), a mod action that changes sockets (the
goal item's sockets would not be the start item's), and a finish that no offered action completes.

Until the finish is its own sub-route on the answer (ticket #233), the answer says it in one line (`finish_limit`): the finish's mean, the total,
and the actions the finish takes; the figures of the mods (mean, percentiles, steps) stay those of the mods.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, replace

from crafting_system.abstraction import Finish, FinishStep, SocketWanted, solve_finish
from crafting_system.actions.catalog import catalog_kinds
from crafting_system.data import GameData
from crafting_system.items import PlainQuality
from crafting_system.prices import PriceFile
from crafting_system.prices.price_source import DEFAULT_PRICE_SOURCE

from . import _limits
from ._limits import Limit, kind_title, unpriced_limits
from ._offers import DroppedOffer, PricedOffer, offer_of, price_offers

FINISH_KINDS = ("jewellers-orb", "orb-of-fusing", "bench-socket-count", "bench-socket-links", "chromatic-orb", "bench-socket-colours")
QUALITY_KIND = "quality-currency"
ALL_FINISH_KINDS = (*FINISH_KINDS, QUALITY_KIND)


class FinishRefused(ValueError):
    """The finish of a target cannot be planned; the text says why in a player's words."""


@dataclass(frozen=True)
class PlanFinish:
    """The finish of a plan: the solved finish, the priced actions it was offered (the quality currency apart) and those left out for lack of a price."""

    finish: Finish
    offers: tuple[PricedOffer, ...]
    quality: PricedOffer | None
    dropped: tuple[DroppedOffer, ...]

    @property
    def value(self) -> float:
        return self.finish.value


def split_names(data: GameData, start_item, names: Collection[str] | None) -> tuple[list[str] | None, frozenset[str] | None]:
    """A target's `actions:` split into the names the mods read and the names of the finish (a finish kind, or the label of one finish action).

    None stays None for both: every kind is offered."""
    if names is None:
        return None, None
    labels = {action.label(data) for action in catalog_kinds(data, start_item, names=ALL_FINISH_KINDS)}
    finish = frozenset(name for name in names if name in ALL_FINISH_KINDS or name in labels)
    return [name for name in names if name not in finish], finish


def finish_offers(data: GameData, start_item, names: frozenset[str] | None) -> tuple[list, list]:
    """The offers of the finish actions for the start item (`names`: only those kinds or labels; None: all), and of the quality currency."""
    listed = catalog_kinds(data, start_item, names=ALL_FINISH_KINDS)
    socket_offers, quality_offers = [], []
    for action, kind in listed.items():
        label = action.label(data)
        if names is not None and kind not in names and label not in names:
            continue
        offer = offer_of(action, label, data, start_item, kind, shares=False)
        (quality_offers if kind == QUALITY_KIND else socket_offers).append(offer)
    return socket_offers, quality_offers


def plan_finish(
    data: GameData,
    target,
    prices: PriceFile,
    price_source: str = DEFAULT_PRICE_SOURCE,
    *,
    names: frozenset[str] | None = None,
    goal_takes_corrupted: bool = False,
    mod_actions: Iterable = (),
) -> PlanFinish:
    """Solve the finish of `target` from its start item's sockets with the finish actions `names` allows, at today's prices (module text)."""
    start = target.start_item
    if start.sockets is None:
        raise FinishRefused(
            "the target asks for sockets and its start item does not say which it has (`sockets: any`); the sockets are finished from the ones the "
            "item has, so write its sockets in the target's start item"
        )
    if goal_takes_corrupted:
        raise FinishRefused("the target asks for sockets and takes a corrupted item, which the planner cannot plan yet: a corrupted item takes no socket orb")
    changing = sorted({action.label(data) for action in mod_actions if action.adds(data, start).sockets})
    if changing:
        raise FinishRefused(
            f"the target asks for sockets and {', '.join(changing)} can change them while the mods are made, which the planner cannot plan yet; "
            "leave it out with the target's `actions:`"
        )
    socket_offers, quality_offers = finish_offers(data, start, names)
    priced, dropped = price_offers(socket_offers, prices, price_source)
    quality_priced, quality_dropped = price_offers(quality_offers, prices, price_source)
    quality = min(quality_priced, key=lambda entry: entry.cost, default=None)
    steps = [FinishStep(entry.label, entry.offer.action, entry.cost) for entry in priced]
    quality_step = None if quality is None else FinishStep(quality.label, quality.offer.action, quality.cost)
    percent = start.quality.percent if isinstance(start.quality, PlainQuality) else 0
    finish = solve_finish(
        data, target.base_id, target.item_level, SocketWanted.of(target.sockets), start.sockets, steps, quality=percent, quality_step=quality_step
    )
    if not math.isfinite(finish.value):
        offered = ", ".join(entry.label for entry in priced) or "none"
        missing = sorted({name for drop in (*dropped, *quality_dropped) for name in drop.missing})
        unpriced = f"; without a price: {', '.join(missing)}" if missing else ""
        raise FinishRefused(
            f"no way of finishing the sockets the target asks for from the start item's sockets with the socket methods offered ({offered}{unpriced})"
        )
    return PlanFinish(finish, tuple(priced), quality, (*dropped, *quality_dropped))


def finish_limits(plan_finish: PlanFinish, mods_mean: float) -> tuple[Limit, ...]:
    """What the answer says of the finish until it is a sub-route of its own (ticket #233): its mean beside the mods' and the total, the methods
    it uses, and the finish actions left out for lack of a price."""
    finish = plan_finish.finish
    total = mods_mean + finish.value
    if finish.met:
        why = "the start item already has the sockets the target asks for, so nothing is added to the cost of the mods"
        labels: tuple[str, ...] = ()
    else:
        taken = set(finish.policy.values())
        labels = tuple(entry.label for entry in plan_finish.offers if entry.label in taken)
        if finish.quality_bought and plan_finish.quality is not None:
            labels = (plan_finish.quality.label, *labels)
        bought = (
            f", of which {finish.quality_cost:,.2f} Chaos is the quality raised to 20% first" if finish.quality_bought else ""
        )
        why = (
            f"the sockets are finished on their own once the mods are made: {finish.value:,.2f} Chaos on average{bought}, "
            f"so the whole craft costs {total:,.2f} Chaos on average after the start item; the mean and the percentiles shown here are of the mods alone"
        )
    found = (
        Limit(
            _limits.FINISH,
            "Sockets finished after the mods",
            why,
            "The finish is the cheapest way to the sockets with the socket methods offered, and adding it changes no step of the mods.",
            labels,
            approximate="The finish is worked out exactly, the cheapest way to the sockets with the socket methods offered; it changes no step of the mods.",
        ),
    )
    return found + unpriced_limits((drop.label, drop.missing, drop.kind) for drop in plan_finish.dropped)


def without_finish_kinds(limits: Sequence[Limit]) -> tuple[Limit, ...]:
    """The limits with the finish kinds taken out of "methods the planner cannot use yet": for a target that names sockets the finish uses them."""
    titles = {kind_title(name) for name in ALL_FINISH_KINDS}
    kept: list[Limit] = []
    for limit in limits:
        if limit.kind == _limits.NOT_BUILT:
            labels = tuple(label for label in limit.labels if label not in titles)
            if not labels:
                continue
            limit = replace(limit, labels=labels)
        kept.append(limit)
    return tuple(kept)
