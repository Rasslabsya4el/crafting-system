"""The price of Hinekora's Lock and of its burns (batch B8, ticket #295, ADR-0056).

The Lock is a priced, used-up resource: one use consumes one `Hinekora's Lock` of the price file (`HinekoraLock.resources`, claim
`hinekora_lock.cost`), and a relock pays it again. The file dates it (poe.ninja's Currency overview lists the Lock). With **no price for the Lock it is
dropped**, as any action whose price is missing (ADR-0007): `lock_missing` names what is missing, and the planner gives the Lock to
`planner._offers.price_offers` as an `Offer`, which drops it and lists it among the actions "dropped for lack of a price".

A **burn** is priced like any action, by its resources. `cheapest_burn` picks, among the legal burns of a state (`actions.burns_at`), the one that costs
least at the prices of the file, which is the burn the Peek of a Lock takes as its fallback; a burn whose currency has no price is not a candidate. Ties
are broken by label, so the choice never depends on the order of the catalog. A hand override of a price counts as for any line (`load_prices`).

A Chaos Orb is worth 1 Chaos whether or not the file lists it, and a Divine Orb the file's `chaos_per_divine` when it lists no price for it, as in
`price_offers`.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from crafting_system.actions import Action, HinekoraLock

from .price_file import CHAOS_ORB, DIVINE_ORB, PriceFile
from .trade_market import planned_price

__all__ = [
    "PricedBurn",
    "cheapest_burn",
    "lock_missing",
    "lock_price",
    "price_burns",
    "resource_cost",
]


@dataclass(frozen=True)
class PricedBurn:
    """A burn with the price of one use, in Chaos Orbs."""

    burn: Action
    cost: float


def resource_cost(resources: Mapping[str, int], prices: PriceFile, price_source: str = "both") -> tuple[float, tuple[str, ...]]:
    """What `resources` cost at `prices` in Chaos Orbs, and the names that have no price (sorted); the cost is meaningful only when none is missing.

    `price_source` is the profile setting `planned_price` reads the prices under, as the plan's offers are (`planner._offers.price_offers`).
    """
    total, missing = 0.0, []
    for name, count in resources.items():
        if name == CHAOS_ORB:
            total += float(count)
        elif (planned := planned_price(prices, name, price_source)) is not None and planned.mark is None:
            total += count * planned.chaos  # a marked price is a thin trade market's: a currency line has none, so it would count as missing
        elif name == DIVINE_ORB:
            total += count * prices.chaos_per_divine
        else:
            missing.append(name)
    return total, tuple(sorted(missing))


def lock_missing(prices: PriceFile, price_source: str = "both") -> tuple[str, ...]:
    """The price names of the Lock that `prices` lacks; empty when the Lock is priced."""
    return resource_cost(HinekoraLock().resources(), prices, price_source)[1]


def lock_price(prices: PriceFile, price_source: str = "both") -> float | None:
    """The price of one Hinekora's Lock in Chaos Orbs, or None when the file has none (the Lock is then dropped and the report lists it)."""
    cost, missing = resource_cost(HinekoraLock().resources(), prices, price_source)
    return None if missing else cost


def price_burns(burns: Iterable[Action], data, prices: PriceFile, price_source: str = "both") -> tuple[PricedBurn, ...]:
    """The burns whose currency has a price, with their cost, cheapest first (ties by label)."""
    found = []
    for burn in burns:
        cost, missing = resource_cost(burn.resources(data), prices, price_source)
        if not missing:
            found.append(PricedBurn(burn, cost))
    return tuple(sorted(found, key=lambda entry: (entry.cost, entry.burn.label(data))))


def cheapest_burn(burns: Iterable[Action], data, prices: PriceFile, price_source: str = "both") -> PricedBurn | None:
    """The legal burn that costs least at the prices of the file, or None when none is priced."""
    priced = price_burns(burns, data, prices, price_source)
    return priced[0] if priced else None
