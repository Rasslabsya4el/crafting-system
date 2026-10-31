"""The actions the planner may use, what one use of each takes, and what that costs at today's prices.

An `Offer` pairs an action of `actions` with the resources one use consumes, by their price-file
names. R12 offers a Chaos Orb and the Harvest reforge of Lightning; the rest of B1 widens the list.
Prices come from the price file (hand overrides on top); an offer with a missing price is dropped
and reported (ADR-0007), never guessed.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from crafting_system.actions import ChaosOrb, HarvestReforge
from crafting_system.prices import CHAOS_ORB, PriceFile
from crafting_system.rules import get_rule

TAGGED_RARE_REFORGE_EXISTS = get_rule("harvest_reforge.tagged_rare_reforge_exists")
LIFEFORCE_COST = get_rule("harvest_reforge.lifeforce_cost")


@dataclass(frozen=True)
class Offer:
    """One action and what a use of it consumes.

    `resources` maps a price-file name to how many of it one use takes. `tag` is the guaranteed mod
    tag of a Harvest reforge and None for any other action.
    """

    label: str
    action: object
    resources: Mapping[str, int]
    tag: str | None = None


@dataclass(frozen=True)
class PricedOffer:
    """An offer with the price of one use, in Chaos Orbs, and where each resource price came from."""

    offer: Offer
    cost: float
    parts: tuple[tuple[str, int, float, str], ...]  # (resource, count, chaos for all of them, source)

    @property
    def label(self) -> str:
        return self.offer.label


@dataclass(frozen=True)
class DroppedOffer:
    """An offer left out because some resource has no price."""

    label: str
    missing: tuple[str, ...]


def default_offers() -> tuple[Offer, ...]:
    """The actions of the R12 slice: a Chaos Orb and the Harvest reforge of Lightning."""
    return (
        Offer("Chaos Orb", ChaosOrb(), {CHAOS_ORB: 1}),
        Offer(
            "Harvest Reforge Lightning",
            HarvestReforge("lightning"),
            dict(LIFEFORCE_COST.value["lightning"]),
            tag=TAGGED_RARE_REFORGE_EXISTS.value["lightning"],
        ),
    )


def price_offers(
    offers: Iterable[Offer], prices: PriceFile
) -> tuple[tuple[PricedOffer, ...], tuple[DroppedOffer, ...]]:
    """The offers whose resources all have a price, and those that do not (with the names missing).

    A Chaos Orb is worth 1 Chaos whether or not the file lists it.
    """
    priced: list[PricedOffer] = []
    dropped: list[DroppedOffer] = []
    for offer in offers:
        parts = []
        missing = []
        for name, count in offer.resources.items():
            if name == CHAOS_ORB:
                parts.append((name, count, float(count), "fixed"))
            elif name in prices.prices:
                entry = prices.prices[name]
                parts.append((name, count, count * entry.chaos, entry.source))
            else:
                missing.append(name)
        if missing:
            dropped.append(DroppedOffer(offer.label, tuple(sorted(missing))))
        else:
            priced.append(PricedOffer(offer, sum(part[2] for part in parts), tuple(parts)))
    return tuple(priced), tuple(dropped)
