"""Single-draw weight shares: the guide's way of quoting odds (ADR-0020).

A share is the weight of the wanted mods in the pool over the weight of the candidates of one draw:
all of the pool for a Chaos Orb, the tagged mods of the pool for a Harvest reforge. The pool is the
one `actions.build_pool` gives for the item with only its fractured mods, so a fractured family is
already out of it. A share is not the chance that the finished item holds the mod (that is the
kernel's per-click chance, which later draws also feed); the report prints both next to each other.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.actions import build_pool
from crafting_system.data import GameData
from crafting_system.items import Item

from ._offers import Offer


@dataclass(frozen=True)
class WeightShare:
    """`wanted` out of `total` weight when `action` draws on the item, for the leaf named `leaf`."""

    action: str
    leaf: str
    wanted: Fraction
    total: Fraction

    @property
    def share(self) -> Fraction:
        return self.wanted / self.total if self.total else Fraction(0)


def weight_share(data: GameData, item: Item, mod_ids: Iterable[str], tag: str | None) -> tuple[Fraction, Fraction]:
    """`(wanted weight, total weight)` of one draw on `item` with only its fractured mods kept.

    `tag` restricts the candidates to the mods carrying that implicit tag (a Harvest reforge), None
    leaves the whole pool (a Chaos Orb). A wanted mod outside the candidates counts as weight 0.
    """
    wanted_ids = frozenset(mod_ids)
    retained = item.changed(data, mods=item.fractured_mods)
    wanted = Fraction(0)
    total = Fraction(0)
    for family in build_pool(data, retained):
        for entry in family.mods:
            if tag is not None and tag not in entry.mod.implicit_tags:
                continue
            total += entry.weight
            if entry.mod.id in wanted_ids:
                wanted += entry.weight
    return wanted, total


def start_shares(
    data: GameData, item: Item, offers: Iterable[Offer], leaves: Iterable[tuple[str, frozenset[str]]]
) -> list[WeightShare]:
    """The share of each leaf's mods under each offer, on `item`.

    `leaves` pairs a leaf label with its mod ids. A leaf that no candidate of the offer can satisfy
    is left out (its share would be 0 for no reason the reader cares about), and so is an offer the
    item cannot take at all.
    """
    found = []
    for offer in offers:
        for label, mod_ids in leaves:
            wanted, total = weight_share(data, item, mod_ids, offer.tag)
            if wanted:
                found.append(WeightShare(offer.label, label, wanted, total))
    return found
