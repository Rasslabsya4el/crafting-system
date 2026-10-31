"""The Orb of Alchemy: a normal item becomes rare with 4, 5 or 6 mods (8:3:1)."""

from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .draw import refuse_unmodelled
from .errors import NotApplicableError
from .outcomes import Outcomes

ACCEPTS_NORMAL_ONLY = get_rule("alchemy.accepts_normal_only")
COUNT_LIKE_CHAOS = get_rule("alchemy.count_like_chaos")
REFUSED_ON_CORRUPTED = get_rule("magic_orbs.refused_on_corrupted")


@dataclass(frozen=True)
class AlchemyOrb:
    """One Orb of Alchemy."""

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not normal or is corrupted, and `OutOfScopeError` for a jewel or an influenced item. The draw is the one of a Chaos
        Orb on a rare item with no mod.
        """
        if item.rarity is not Rarity.NORMAL:
            raise NotApplicableError(f"an Orb of Alchemy works on a normal item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Orb of Alchemy")
        refuse_unmodelled(data, item)
        return Outcomes.reroll(data, item, tag=None)
