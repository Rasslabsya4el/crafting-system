"""The Chaos Orb: rerolls every mod of a rare item, and the number of mods, except the fractured ones.

Random rerolls: `ChaosOrb()`, `HarvestReforge("lightning")` (sixteen tagged crafts, one per tag of the claim
`harvest_reforge.tagged_rare_reforge_exists`), `HarvestReforgeInfluence()` (an influenced item, one influence mod
guaranteed), `HarvestReforgeLikelihood(more=True)` (the mods the item holds are 10 times more, or with `more=False`
10 times less, likely to return; the item keeps at least as many mods) and `ApplyEssence("Shrieking Essence of
Spite")` (an essence is named as in the game data or by its record id). Each has one method,
`outcomes(data, item) -> Outcomes`, and `Outcomes` is the whole result.
"""

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
    "ChaosOrb",
]

ACCEPTS_RARE_ONLY = get_rule("chaos_orb.accepts_rare_only")
REROLLS_ALL_MODS = get_rule("chaos_orb.rerolls_all_mods")
REFUSED_ON_CORRUPTED = get_rule("chaos_orb.refused_on_corrupted")
COST = get_rule("chaos_orb.cost")
JEWELS_TAKE_THE_ORBS = get_rule("jewel.ordinary_orbs_work_on_jewels")
JEWEL_REROLL_COUNT = get_rule("jewel.reroll_mod_count")


@dataclass(frozen=True)
class ChaosOrb(Action):
    """One Orb of Chaos."""

    def label(self, data: GameData | None = None) -> str:
        return "Chaos Orb"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing(block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing(named=frozenset(), single_draw=True)

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not rare or is corrupted, and
        `OutOfScopeError` for a cluster jewel or an influenced item of a class with no influence class key. Ordinary
        crafted mods are removed by the reroll like every mod that is not fractured. The mods of a side that
        `Prefixes` or `Suffixes Cannot Be Changed` locks stay and count inside the total, and an Attack or
        Caster metamod that stays (on a locked side) keeps the mods with its tag out of the draw.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(
                f"a Chaos Orb works on a rare item only, and this item is {item.rarity}"
            )
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Chaos Orb")
        refuse_unmodelled(data, item, jewels=True)
        return Outcomes.reroll(data, item, tag=None)


@kind("chaos-orb", order=10)
def _chaos_orb(data: GameData, item: Item):
    yield ChaosOrb()
