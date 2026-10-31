"""The Chaos Orb: rerolls every mod of a rare item, and the number of mods, except the fractured ones."""

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

ACCEPTS_RARE_ONLY = get_rule("chaos_orb.accepts_rare_only")
REROLLS_ALL_MODS = get_rule("chaos_orb.rerolls_all_mods")
REFUSED_ON_CORRUPTED = get_rule("chaos_orb.refused_on_corrupted")
COST = get_rule("chaos_orb.cost")


@dataclass(frozen=True)
class ChaosOrb(Action):
    """One Orb of Chaos."""

    def label(self, data: GameData | None = None) -> str:
        return "Chaos Orb"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), single_draw=True)

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not rare or is corrupted, and
        `OutOfScopeError` for a jewel, an influenced item or one with a crafted metamod. Ordinary
        crafted mods are removed by the reroll like every mod that is not fractured.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(
                f"a Chaos Orb works on a rare item only, and this item is {item.rarity}"
            )
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Chaos Orb")
        refuse_unmodelled(data, item)
        return Outcomes.reroll(data, item, tag=None)


@kind("chaos-orb", order=10)
def _chaos_orb(data: GameData, item: Item):
    yield ChaosOrb()
