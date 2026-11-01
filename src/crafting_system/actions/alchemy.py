"""The Orb of Alchemy: a normal item becomes rare with 4, 5 or 6 mods (8:3:1)."""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import refuse_unmodelled
from .errors import NotApplicableError
from .outcomes import Outcomes

__all__ = [
    "AlchemyOrb",
]

ACCEPTS_NORMAL_ONLY = get_rule("alchemy.accepts_normal_only")
COUNT_LIKE_CHAOS = get_rule("alchemy.count_like_chaos")
REFUSED_ON_CORRUPTED = get_rule("magic_orbs.refused_on_corrupted")
COST = get_rule("alchemy.cost")
JEWELS_TAKE_THE_ORBS = get_rule("jewel.ordinary_orbs_work_on_jewels")
JEWEL_REROLL_COUNT = get_rule("jewel.reroll_mod_count")


@dataclass(frozen=True)
class AlchemyOrb(Action):
    """One Orb of Alchemy."""

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Alchemy"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not normal or is corrupted, and `OutOfScopeError` for a cluster jewel or an influenced item of a class with no influence class key (a normal item holds no metamod). The draw is the one of a Chaos
        Orb on a rare item with no mod.
        """
        if item.rarity is not Rarity.NORMAL:
            raise NotApplicableError(f"an Orb of Alchemy works on a normal item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Orb of Alchemy")
        refuse_unmodelled(data, item, jewels=True)
        return Outcomes.reroll(data, item, tag=None)


@kind("alchemy-orb", order=70, planner=False, why_not="not in the B1 offer set; which actions a target needs is pruning (#118)")
def _alchemy_orb(data: GameData, item: Item):
    if item.rarity is Rarity.NORMAL:
        yield AlchemyOrb()
