"""The Chaos Orb: rerolls every mod of a rare item, and the number of mods, except the fractured ones."""

from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .draw import refuse_unmodelled
from .errors import NotApplicableError
from .outcomes import Outcomes

ACCEPTS_RARE_ONLY = get_rule("chaos_orb.accepts_rare_only")
REROLLS_ALL_MODS = get_rule("chaos_orb.rerolls_all_mods")
REFUSED_ON_CORRUPTED = get_rule("chaos_orb.refused_on_corrupted")


@dataclass(frozen=True)
class ChaosOrb:
    """One Orb of Chaos."""

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not rare or is corrupted, and
        `OutOfScopeError` for a jewel, an influenced item or one with a crafted mod.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(
                f"a Chaos Orb works on a rare item only, and this item is {item.rarity}"
            )
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Chaos Orb")
        refuse_unmodelled(data, item)
        return Outcomes.reroll(data, item, tag=None)
