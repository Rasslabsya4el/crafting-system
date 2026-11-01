"""The Harvest quality enchants: 14 exact actions that put one enchantment on a body armour or a weapon (ticket #240, ADR-0052).

Eight enchants are for body armour (+1 Maximum Life, Maximum Mana, Strength, Dexterity or Intelligence per 2% quality, or +1% to a
Fire, Cold or Lightning resistance) and six for weapons (range, area, accuracy, attack speed, critical strike chance, elemental
damage); each stops quality adding Defences or physical damage (`enchantment.harvest_quality_enchants_14`). One action is one
enchant, `HarvestQualityEnchant(mod_id)`, and its outcome is a `Finite` with one result of chance 1: no draw, the item holds that
enchant afterwards. It changes the enchantment and nothing else, sockets and links included
(`enchantment.quality_enchant_changes_only_its_stat`).

* **Cost**: Lifeforce, by the enchant, from the claim `enchantment.harvest_quality_enchant_costs`, priced from the price file like any
  Harvest craft: 3,250 for a body armour enchant (Life, Strength and Fire resistance Wild; Dexterity and Cold resistance Vivid; Mana,
  Intelligence and Lightning resistance Primal) and 5,000 for a weapon enchant (Range and Area Wild; Accuracy and Attack Speed Vivid;
  Critical and Elemental Primal). No Sacred or Rancour.
* **Replaces and is replaced** (`enchantment.one_slot_new_replaces_old`, `enchantment.quality_enchant_replaces_heist_enchant`,
  approximate, ADR-0028): the item has one enchantment slot, so the action replaces a Tempering or Tailoring enchant or another quality
  enchant, and a later Tempering or Tailoring Orb replaces this one. Using the enchant the item already holds is allowed and changes
  nothing; a planner has no reason to.
* **Refusals** (`NotApplicableError`): a corrupted item (`enchantment.mirrored_and_corruption`: the item model has no mirrored item,
  so only the corrupted one can arise), and an item of the wrong class: the eight for body armour are refused on a weapon, the six for
  weapons on a body armour, and either on any other base (a base is a weapon by the tag `weapon`, a body armour by `body_armour`).
  The rarity does not matter. A cluster jewel or a base of no enchantment is of no class, so the action is never listed for it.
* **Not modelled**: replacing the "Can have 1 additional Crafted Modifier" enchant of an item that holds a second crafted mod; no
  source says what the game does, and the compressed state does not hold the enchantment (ADR-0050), so the action does not look.

The enchantment is a finish step of the plan (ADR-0050), priced by the finish cost, and the search over mods does not choose it: the
kind is not a planner kind. The quality line that gives the enchant its worth (ADR-0052) and the Harvest route of the finish cost are
other tickets. The kind works on two item classes and none of the amulets of the contract fixture, so it declares `applies_only_to`,
and the contract suite meets it on the body armour and the sword of `tests/contract_fixtures_harvest_quality.py`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import BaseItem, GameData
from crafting_system.items import EnchantKind, Item, enchant_class, enchant_info
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError
from .finite import Finite
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, NOT_SPENT_BY, StrandUse

__all__ = [
    "HarvestQualityEnchant",
]

QUALITY_ENCHANTS_14 = get_rule("enchantment.harvest_quality_enchants_14")
ENCHANT_COSTS = get_rule("enchantment.harvest_quality_enchant_costs")
CHANGES_ONLY_ITS_STAT = get_rule("enchantment.quality_enchant_changes_only_its_stat")
ONE_SLOT_NEW_REPLACES_OLD = get_rule("enchantment.one_slot_new_replaces_old")
REPLACES_HEIST_ENCHANT = get_rule("enchantment.quality_enchant_replaces_heist_enchant")  # approximate (ADR-0028)
REFUSED_ON_MIRRORED_AND_CORRUPTED = get_rule("enchantment.mirrored_and_corruption")

PREFIXES = ("HarvestAlternateArmourQuality", "HarvestAlternateWeaponQuality")
NOISE_WORDS = frozenset({"Local", "Percent"})  # parts of the dump's ids that tell a player nothing


def _words(mod_id: str) -> str:
    """The name of the enchant read off its mod id: `HarvestAlternateArmourQualityIncreasedLife` is "Increased Life", `...LocalMeleeWeaponRange_` is "Melee Weapon Range"."""
    name = mod_id
    for prefix in PREFIXES:
        name = name.removeprefix(prefix)
    name = name.rstrip("_")
    spaced = "".join(f" {char}" if char.isupper() and index else char for index, char in enumerate(name))
    return " ".join(word for word in spaced.split() if word not in NOISE_WORDS)


@dataclass(frozen=True)
class HarvestQualityEnchant(Action):
    """One Harvest quality enchant, named by the id of its mod in the dump (a key of `enchantment.harvest_quality_enchant_costs`)."""

    mod_id: str = "HarvestAlternateArmourQualityIncreasedLife"

    def __post_init__(self) -> None:
        if not isinstance(self.mod_id, str) or self.mod_id not in ENCHANT_COSTS.value:
            known = ", ".join(sorted(ENCHANT_COSTS.value))
            raise ValueError(f"there is no Harvest quality enchant {self.mod_id!r}; known: {known}")

    @property
    def variant(self) -> str:
        return self.mod_id

    def label(self, data: GameData | None = None) -> str:
        return f"Harvest Quality Enchant {_words(self.mod_id)}"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(NOT_SPENT_BY, CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: a Harvest craft draws no mod and spends nothing

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(ENCHANT_COSTS.value[self.mod_id])

    def reads(self, data: GameData) -> Reads:
        # It looks at neither the mods nor the enchantment it replaces: only the class of the base and the corruption decide.
        return Reads(junk=True, families=frozenset(), block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, enchantment=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The item with this enchant in the enchantment slot, with chance 1.

        Raises `NotApplicableError` for a corrupted item and for an item whose class does not take this enchant.
        """
        mod = data.mods.get(self.mod_id)
        info = enchant_info(mod) if mod is not None else None
        if info is None or info.kind is not EnchantKind.QUALITY:
            raise ValueError(f"the enchant {self.mod_id} is not a Harvest quality enchant of the game data")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no enchantment")
        held = enchant_class(data.base_items[item.base_id])
        if held is not info.item_class:
            found = held.value if held else "neither a weapon nor a body armour"
            raise NotApplicableError(f"this enchant is for a {info.item_class.value}, and the item is {found}")
        return Finite(data, item, ((Fraction(1), item.changed(data, enchantment=self.mod_id)),))


def _fits(data: GameData, base: BaseItem, mod_id: str) -> bool:
    mod = data.mods.get(mod_id)
    info = enchant_info(mod) if mod is not None else None
    return info is not None and info.kind is EnchantKind.QUALITY and info.item_class is enchant_class(base)


@kind(
    "harvest-quality-enchant",
    order=26,
    planner=False,
    why_not="a finish step, priced by the finish cost of ADR-0050, never searched over",
    applies_only_to="weapon and body armour",
)
def _harvest_quality_enchants(data: GameData, item: Item):
    base = data.base_items[item.base_id]
    for mod_id in sorted(ENCHANT_COSTS.value):
        if _fits(data, base, mod_id):
            yield HarvestQualityEnchant(mod_id)
