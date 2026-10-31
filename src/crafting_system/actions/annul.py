"""The Orb of Annulment: removes one explicit mod, uniformly among the mods it can remove; the rarity stays."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import refuse_metamods
from .errors import NotApplicableError
from .finite import Finite

ACCEPTS_MAGIC_OR_RARE = get_rule("annulment_orb.accepts_magic_or_rare")
REMOVES_ONE_MOD_UNIFORMLY = get_rule("annulment_orb.removes_one_mod_uniformly")
NEVER_DOWNGRADES_RARITY = get_rule("annulment_orb.never_downgrades_rarity")
FRACTURED_MODS_STAY = get_rule("annulment_orb.fractured_mods_stay")
REFUSED_WITHOUT_REMOVABLE_MOD = get_rule("annulment_orb.refused_without_removable_mod")
REFUSED_ON_CORRUPTED = get_rule("annulment_orb.refused_on_corrupted")
COST = get_rule("annulment_orb.cost")


@dataclass(frozen=True)
class AnnulmentOrb(Action):
    """One Orb of Annulment."""

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Annulment"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        # What stays depends on which mods are on the item, so every family of the junk is told apart.
        # `block_invariant` stays False: ADR-0023 calls Annulment "probably" invariant and no test proves it.
        return Reads()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # `keeps_crafted` stays True: a crafted mod is one of the mods it may remove, but it is not erased.
        return Adds.removal()

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of using the orb on `item`: one result per removable mod, each with chance 1/n.

        Raises `NotApplicableError` for a normal or a corrupted item and for an item with no mod to
        remove (none, or every one fractured), and `OutOfScopeError` for one with a crafted metamod.
        The rarity stays: a magic item left with no mod is magic.
        """
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("an Orb of Annulment works on a magic or rare item only, and this item is normal")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Orb of Annulment")
        refuse_metamods(data, item)
        removable = [entry for entry in item.mods if not entry.fractured]
        if not removable:
            raise NotApplicableError("an Orb of Annulment cannot be used here: the item has no mod that is not fractured to remove")
        share = Fraction(1, len(removable))
        return Finite(
            data,
            item,
            tuple((share, item.remove_mod(data, entry.mod_id)) for entry in removable),
        )


@kind(
    "annulment-orb",
    order=81,
    planner=False,
    why_not="no compressed-state kernel for a removal that keeps the rest of the item yet (#69)",
)
def _annulment_orb(data: GameData, item: Item):
    if item.rarity is not Rarity.NORMAL:
        yield AnnulmentOrb()
