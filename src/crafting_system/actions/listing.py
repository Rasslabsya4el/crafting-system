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

A listing whose price is a **Normal base's** (the stored trade search asks for rarity normal: R08 and R09) is not drawn for free: the player buys
the Normal base and uses the orb that makes it the rarity, an Orb of Alchemy (Rare) or an Orb of Transmutation (Magic, the same 1 or 2 mods as an
Alteration). The draw is then that orb, `paid`: it is named by the orb and costs one of it (OR-16, OR-43, #1522).

A listing whose price buys an item of **another rarity** than the start's, or of any rarity (R14: the stored search asks `nonunique`), is not
drawn for free either: the item bought may hold mods of another rarity, so the player first uses an Orb of Scouring (its influences stay,
claim `scouring.keeps_influence`) and then the orb that makes the Normal base the rarity. The draw is then both orbs, `paid` and `scoured_from`
the bought item's rarity in words ("any rarity", "Rare"): the most a player pays, since a Normal one he buys needs no Scouring and one of the
start's rarity neither orb (#1537).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity

from .alchemy import AlchemyOrb
from .contract import Action, Adds, Reads
from .errors import NotApplicableError
from .magic import AlterationOrb, TransmutationOrb
from .outcomes import Outcomes
from .scour import ScouringOrb

__all__ = [
    "DRAW_LABEL",
    "OpenListing",
    "open_listing",
    "scoured_from",
    "unopened_listing",
]

DRAW_LABEL = "The bought item's own mods"

DRAWN_BY = {Rarity.MAGIC: AlterationOrb(), Rarity.RARE: AlchemyOrb()}
MADE_BY = {Rarity.MAGIC: TransmutationOrb(), Rarity.RARE: AlchemyOrb()}  # the orb a player uses on a Normal base to make it that rarity (#1522)


def unopened_listing(data: GameData, start: Item) -> Item | None:
    """The unopened listing the start item `start` of a bought start stands for, or None when `start` is not one.

    The rule (ADR-0064, one for every target): a bought start item that is Magic or Rare and holds no mod, nothing corrupted, no imprint and no offer is
    the item the market sells, whose mods the target does not name. Its base, item level, influences, implicits and quality are the start item's own.
    """
    if start.rarity not in DRAWN_BY or start.mods or start.corrupted or start.imprints or start.veil_offer:
        return None
    return start.changed(data, rarity=Rarity.NORMAL, unopened=True)


SCOURED_CLAIMS = frozenset({"scouring.removes_all_unprotected_mods", "scouring.keeps_influence"})


def open_listing(rarity: Rarity, paid: bool = False, scoured_from: str | None = None) -> "OpenListing":
    """The draw that opens a listing of `rarity` (Magic or Rare); `paid` when the item bought is a Normal base, so the draw is the orb that makes
    it that rarity, used and paid (#1522); `scoured_from` (with `paid`) when the item bought is of another rarity or any, in words, so an Orb of
    Scouring comes first (#1537). The planner asks for it here and names no concrete class."""
    return OpenListing(rarity, paid, scoured_from if paid else None)


def scoured_from(action: Action) -> str | None:
    """The bought item's rarity in words ("any rarity", "Rare") when `action` is an opening that scours the bought item first (#1537), else None."""
    return action.scoured_from if isinstance(action, OpenListing) else None


@dataclass(frozen=True)
class OpenListing(Action):
    """Open an unopened listing of `rarity` (Magic or Rare): the draw of the mods the market item holds."""

    rarity: Rarity
    paid: bool = False  # the item bought is a Normal base: the draw is the orb that makes it `rarity`, named and paid (#1522)
    scoured_from: str | None = None  # with `paid`, the item bought is of this other rarity (or "any rarity"): an Orb of Scouring comes first (#1537)
    opens_listing = True

    def __post_init__(self) -> None:
        if self.rarity not in DRAWN_BY:
            raise ValueError(f"a listing is opened as a Magic or a Rare item, not {self.rarity}")

    @property
    def variant(self) -> str:
        if self.scoured_from is not None:
            return f"{self.rarity.value}-scoured"
        return f"{self.rarity.value}-paid" if self.paid else self.rarity.value

    def label(self, data: GameData | None = None) -> str:
        if self.scoured_from is not None:
            return f"Orb of Scouring and {MADE_BY[self.rarity].label(data)} on the bought item ({self.scoured_from})"
        return f"{MADE_BY[self.rarity].label(data)} on the bought Normal base" if self.paid else DRAW_LABEL

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        if self.paid:  # the player uses the orb on the Normal base he bought (#1522), after an Orb of Scouring on an item of another rarity (#1537)
            made = dict(MADE_BY[self.rarity].resources(data))
            if self.scoured_from is not None:
                for name, count in ScouringOrb().resources(data).items():
                    made[name] = made.get(name, 0) + count
            return made
        return {}  # the price of the listing is the start price

    def reads(self, data: GameData) -> Reads:
        return DRAWN_BY[self.rarity].reads(data)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return DRAWN_BY[self.rarity].adds(data, item)

    def strand_use(self, data: GameData | None = None):
        return DRAWN_BY[self.rarity].strand_use(data)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        drawn = DRAWN_BY[self.rarity].claims(data)
        return drawn | SCOURED_CLAIMS if self.scoured_from is not None else drawn

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The draw of the orb that makes this rarity, on the listing opened: raises `NotApplicableError` for an item that is not an unopened listing."""
        if not item.unopened:
            raise NotApplicableError("the draw of a bought item's mods works only on a listing that is not opened yet")
        opened = item.changed(data, unopened=False, rarity=self.rarity if self.rarity is Rarity.MAGIC else Rarity.NORMAL)
        return DRAWN_BY[self.rarity].outcomes(data, opened)
