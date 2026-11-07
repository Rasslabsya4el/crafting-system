"""The draw that opens a bought listing: the mods of the item the market sells (ticket #640, ADR-0064).

A bought start item whose mods the target does not name is not an item with no mods: a Magic item in the game holds 1 or 2 mods and a Rare item
4 to 6. It is the item the market sells, a draw of the orb that makes its rarity. The planner holds the listing as an **unopened** item
(`Item.unopened`: a normal item with no mod, bought and not looked at yet), and this action opens it:

* a **Magic** listing is what an Orb of Alteration leaves on that base: 1 or 2 mods, 1/2 each, from the base's pool at its game weights, the
  mods of the item's influences included;
* a **Rare** listing is what an Orb of Alchemy leaves on that base: 4, 5 or 6 mods (8:3:1).

The draw is one chance step before the first decision, free beyond the price of the listing (that price is the start price, and a restart pays it
again). It is offered at no other state, and no other action works on the unopened item, so the planner decides on each outcome of the draw: an
Augmentation only where the item holds 1 mod, and an Alteration (or whatever is cheapest) where it holds 2. It is not an orb the player uses:
the cost is the listing's, and the orb it copies is only the law of the draw. The result is exactly that orb's result on the opened item, so no
solver or abstraction learns a new kind of step.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity

from .alchemy import AlchemyOrb
from .contract import Action, Adds, Reads
from .errors import NotApplicableError
from .magic import AlterationOrb
from .outcomes import Outcomes

__all__ = [
    "DRAW_LABEL",
    "OpenListing",
    "unopened_listing",
]

DRAW_LABEL = "The bought item's own mods"

DRAWN_BY = {Rarity.MAGIC: AlterationOrb(), Rarity.RARE: AlchemyOrb()}


def unopened_listing(data: GameData, start: Item) -> Item | None:
    """The unopened listing the start item `start` of a bought start stands for, or None when `start` is not one.

    The rule (ADR-0064, one for every target): a bought start item that is Magic or Rare and holds no mod, nothing corrupted, no imprint and no offer is
    the item the market sells, whose mods the target does not name. Its base, item level, influences, implicits and quality are the start item's own.
    """
    if start.rarity not in DRAWN_BY or start.mods or start.corrupted or start.imprints or start.veil_offer:
        return None
    return start.changed(data, rarity=Rarity.NORMAL, unopened=True)


@dataclass(frozen=True)
class OpenListing(Action):
    """Open an unopened listing of `rarity` (Magic or Rare): the draw of the mods the market item holds."""

    rarity: Rarity
    opens_listing = True

    def __post_init__(self) -> None:
        if self.rarity not in DRAWN_BY:
            raise ValueError(f"a listing is opened as a Magic or a Rare item, not {self.rarity}")

    @property
    def variant(self) -> str:
        return self.rarity.value

    def label(self, data: GameData | None = None) -> str:
        return DRAW_LABEL

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {}  # the price of the listing is the start price

    def reads(self, data: GameData) -> Reads:
        return DRAWN_BY[self.rarity].reads(data)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return DRAWN_BY[self.rarity].adds(data, item)

    def strand_use(self, data: GameData | None = None):
        return DRAWN_BY[self.rarity].strand_use(data)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return DRAWN_BY[self.rarity].claims(data)

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The draw of the orb that makes this rarity, on the listing opened: raises `NotApplicableError` for an item that is not an unopened listing."""
        if not item.unopened:
            raise NotApplicableError("the draw of a bought item's mods works only on a listing that is not opened yet")
        opened = item.changed(data, unopened=False, rarity=self.rarity if self.rarity is Rarity.MAGIC else Rarity.NORMAL)
        return DRAWN_BY[self.rarity].outcomes(data, opened)
