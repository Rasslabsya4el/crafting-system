"""The orbs of magic items: Transmutation and Alteration (1 or 2 mods), Augmentation and Regal (one more mod)."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .add import add_one_mod, draw_onto
from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import refuse_unmodelled
from .errors import NotApplicableError
from .metamods import kept_by_reroll
from .outcomes import Outcomes

TRANSMUTATION_ACCEPTS_NORMAL_ONLY = get_rule("magic_orbs.transmutation_accepts_normal_only")
ALTERATION_ACCEPTS_MAGIC_ONLY = get_rule("magic_orbs.alteration_accepts_magic_only")
ALTERATION_REROLLS_ALL_MODS = get_rule("magic_orbs.alteration_rerolls_all_mods")
FRACTURED_MODS_KEPT = get_rule("magic_orbs.fractured_mods_kept")
MAGIC_MOD_COUNT = get_rule("magic_orbs.magic_mod_count")
KEPT_MODS_COUNT_IN_TOTAL = get_rule("magic_orbs.kept_mods_count_in_total")
DRY_POOL_LEAVES_FEWER_MODS = get_rule("magic_orbs.dry_pool_leaves_fewer_mods")
AUGMENTATION_ACCEPTS_MAGIC_WITH_FREE_SLOT = get_rule("magic_orbs.augmentation_accepts_magic_with_free_slot")
REGAL_ACCEPTS_MAGIC_ONLY = get_rule("magic_orbs.regal_accepts_magic_only")
REGAL_KEEPS_MODS_AND_ADDS_ONE = get_rule("magic_orbs.regal_keeps_mods_and_adds_one")
REFUSED_ON_CORRUPTED = get_rule("magic_orbs.refused_on_corrupted")
COST = get_rule("magic_orbs.cost")

JEWEL_REASON = (
    "the magic and rare capacities and mod counts are admitted for regular items only, "
    "so this orb on a jewel is not modelled yet"
)


def magic_totals() -> dict[int, Fraction]:
    """The probability of each number of mods of a magic item that a Transmutation or Alteration leaves: 1 or 2."""
    weights = MAGIC_MOD_COUNT.value
    whole = sum(weights.values())
    return {total: Fraction(share, whole) for total, share in weights.items()}


def _refuse(data: GameData, item: Item, wanted: Rarity, name: str) -> None:
    """Refuse the item when it is not of rarity `wanted` or is corrupted; then the states no rule covers yet."""
    if item.rarity is not wanted:
        raise NotApplicableError(f"{name} works on a {wanted} item only, and this item is {item.rarity}")
    if item.corrupted:
        raise NotApplicableError(f"the item is corrupted, and a corrupted item takes no {name}")
    refuse_unmodelled(data, item, JEWEL_REASON)


@dataclass(frozen=True)
class TransmutationOrb(Action):
    """One Orb of Transmutation: a normal item becomes magic with 1 or 2 mods, 1/2 each."""

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Transmutation"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value["transmutation"])

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing(block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not normal or is corrupted, and
        `OutOfScopeError` for a jewel or an influenced item of a class with no influence class key.
        """
        _refuse(data, item, Rarity.NORMAL, "an Orb of Transmutation")
        return draw_onto(data, item.changed(data, rarity=Rarity.MAGIC), magic_totals())


@dataclass(frozen=True)
class AlterationOrb(Action):
    """One Orb of Alteration: rerolls a magic item to 1 or 2 mods, 1/2 each; the fractured mods and a locked side stay and count inside."""

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Alteration"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value["alteration"])

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing(block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not magic or is corrupted, and
        `OutOfScopeError` for a jewel or an influenced item of a class with no influence class key.
        Ordinary crafted mods are removed by the reroll like every mod that is not fractured, and the
        mods of a side that `Prefixes` / `Suffixes Cannot Be Changed` locks stay and count inside the total.
        """
        _refuse(data, item, Rarity.MAGIC, "an Orb of Alteration")
        retained = item.changed(data, mods=kept_by_reroll(data, item))
        # a metamod the reroll keeps (it sits on a locked side) filters the draw, as for a Chaos Orb
        return draw_onto(data, retained, magic_totals())


@dataclass(frozen=True)
class AugmentationOrb(Action):
    """One Orb of Augmentation: adds one mod to a magic item that has a free slot."""

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Augmentation"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value["augmentation"])

    def reads(self, data: GameData) -> Reads:
        return Reads.adding(variants=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not magic, is corrupted, is full, or for which
        no mod is legal, and `OutOfScopeError` for a jewel or an influenced item of a class with no influence class key.
        The Attack and Caster metamods on the item keep the mods with their tag out of the pool.
        """
        _refuse(data, item, Rarity.MAGIC, "an Orb of Augmentation")
        return add_one_mod(data, item, "an Orb of Augmentation")


@dataclass(frozen=True)
class RegalOrb(Action):
    """One Regal Orb: a magic item becomes rare and gains one mod; the mods it has stay."""

    def label(self, data: GameData | None = None) -> str:
        return "Regal Orb"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value["regal"])

    def reads(self, data: GameData) -> Reads:
        return Reads.adding(variants=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the orb on `item`.

        Raises `NotApplicableError` for an item that is not magic, is corrupted, or for which no mod is
        legal on the rare item, and `OutOfScopeError` for a jewel or an influenced item of a class with no influence class key.
        The Attack and Caster metamods on the item keep the mods with their tag out of the pool.
        """
        _refuse(data, item, Rarity.MAGIC, "a Regal Orb")
        return add_one_mod(data, item, "a Regal Orb", rarity=Rarity.RARE)


@kind("transmutation-orb", order=71)
def _transmutation_orb(data: GameData, item: Item):
    if item.rarity is Rarity.NORMAL:
        yield TransmutationOrb()


@kind("alteration-orb", order=72)
def _alteration_orb(data: GameData, item: Item):
    if item.rarity in (Rarity.NORMAL, Rarity.MAGIC):
        yield AlterationOrb()


@kind("augmentation-orb", order=73)
def _augmentation_orb(data: GameData, item: Item):
    if item.rarity in (Rarity.NORMAL, Rarity.MAGIC):
        yield AugmentationOrb()


@kind("regal-orb", order=74)
def _regal_orb(data: GameData, item: Item):
    if item.rarity in (Rarity.NORMAL, Rarity.MAGIC):
        yield RegalOrb()
