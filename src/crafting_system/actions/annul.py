"""The Orb of Annulment: removes one explicit mod, uniformly among the mods it can remove; the rarity stays.

The mods it can remove are the explicit mods that are not fractured, not on a side that `Prefixes` or
`Suffixes Cannot Be Changed` locks, and without the tag that `Cannot roll Attack` or `Caster Modifiers`
protects. A metamod on the other side is one of them (D5 of issue #28).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError
from .finite import Finite
from .metamods import allowed_by_tags, blocked_tags, locked_sides, on_locked_side

ACCEPTS_MAGIC_OR_RARE = get_rule("annulment_orb.accepts_magic_or_rare")
REMOVES_ONE_MOD_UNIFORMLY = get_rule("annulment_orb.removes_one_mod_uniformly")
NEVER_DOWNGRADES_RARITY = get_rule("annulment_orb.never_downgrades_rarity")
FRACTURED_MODS_STAY = get_rule("annulment_orb.fractured_mods_stay")
REFUSED_WITHOUT_REMOVABLE_MOD = get_rule("annulment_orb.refused_without_removable_mod")
REFUSED_ON_CORRUPTED = get_rule("annulment_orb.refused_on_corrupted")
RESPECTS_LOCKS_AND_TAGS = get_rule("metamods.annulment_respects_locks_and_tags")
OTHER_SIDE_METAMOD_IS_A_CANDIDATE = get_rule("metamods.annulment_may_remove_other_side_metamod")
COST = get_rule("annulment_orb.cost")


@dataclass(frozen=True)
class AnnulmentOrb(Action):
    """One Orb of Annulment."""

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Annulment"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        # It reads how many mods there are per side and, through the locks and tags of the item, which of
        # them it may remove: no family by name and no pool weight (a removal draws nothing). The successor
        # depends on the slots (their number and kinds), so a family freed by the removal matters only to an
        # action that reads families (a craft, an addition), and that action says so itself.
        # Block-invariant (ADR-0023, #130): a pool of `n` slots out of `N` removable ones loses one with probability `n / N`.
        return Reads(junk=True, families=frozenset(), block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # `keeps_crafted` stays True: a crafted mod is one of the mods it may remove, but it is not erased.
        return Adds.removal()

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of using the orb on `item`: one result per removable mod, each with chance 1/n.

        Raises `NotApplicableError` for a normal or a corrupted item and for an item with no mod to
        remove (none, or every one fractured, locked or protected by a tag metamod).
        The rarity stays: a magic item left with no mod is magic.
        """
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("an Orb of Annulment works on a magic or rare item only, and this item is normal")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Orb of Annulment")
        locked, blocked = locked_sides(data, item), blocked_tags(data, item)
        removable = [
            entry
            for entry in item.mods
            if not entry.fractured
            and not on_locked_side(data, entry, locked)
            and allowed_by_tags(data.mods[entry.mod_id], blocked)
        ]
        if not removable:
            raise NotApplicableError(
                "an Orb of Annulment cannot be used here: the item has no mod that is not fractured, "
                "not on a locked side and not protected by a tag metamod to remove"
            )
        share = Fraction(1, len(removable))
        return Finite(
            data,
            item,
            tuple((share, item.remove_mod(data, entry.mod_id)) for entry in removable),
        )


@kind(
    "annulment-orb",
    order=81,
    opt_in=True,
)
def _annulment_orb(data: GameData, item: Item):
    # a normal item gets mods on the way (an essence, an Orb of Transmutation), so the kind is listed for it too
    yield AnnulmentOrb()
