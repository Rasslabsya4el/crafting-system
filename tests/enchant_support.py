"""Shared helpers for the enchantment tests (ticket #236): the fixture game data plus a small, real-shaped slice of the enchant pools.

The shared fixture excerpts hold no enchantment, and adding to them would change counts other tests read, so the slice is added here, in
memory, with the ids, texts and stats of the 3.29.3.3 dump. `tests/test_enchantment_real.py` checks the same rules on the whole dump.
"""

from dataclasses import replace

from items_support import AMULET, BODY, DATA as FIXTURE

from crafting_system.data import Mod, StatRange

SWORD = "Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"
BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
ARMOUR_POOL = "EnchantmentHeistArmour"
WEAPON_POOL = "EnchantmentHeistWeapon"
ARMOUR_QUALITY = "AlternateArmourQuality"
WEAPON_QUALITY = "AlternateWeaponQuality"

LIFE = "ArmourEnchantmentHeistLifeEffect1"
LIFE_ATTRIBUTE = "ArmourEnchantmentHeistLifeEffectAttributeEffect1_"
LIFE_REQUIREMENTS = "ArmourEnchantmentHeistLifeEffectAttributeRequirements1"
LIFE_RESISTANCE = "ArmourEnchantmentHeistLifeEffectResistanceEffect1__"
LIFE_RESISTANCE_PENALTY = "ArmourEnchantmentHeistLifeEffectResistanceEffectPenalty1"
LIFE_REQUIREMENTS_PENALTY = "ArmourEnchantmentHeistLifeEffectAttributeRequirementsPenalty1_"
LIFE_SOCKET_PENALTY = "ArmourEnchantmentHeistLifeEffectSocketPenalty1"
LIFE_LINKED = "ArmourEnchantmentHeistLifeEffectSocketsAreLinked1_"
LIFE_NO_RED = "ArmourEnchantmentHeistLifeEffectNoRedSockets1"
RESISTANCE_LIFE_PENALTY = "ArmourEnchantmentHeistResistanceEffectLifeEffectPenalty1"
ARMOUR_REQUIREMENTS = "ArmourEnchantmentHeistAttributeRequirements1"
ARMOUR_LINKED = "ArmourEnchantmentHeistSocketsAreLinked1"
ARMOUR_EXTRA_SLOT = "ArmourEnchantmentHeistAdditionalCraftingModifier1"
ARMOUR_WHITE_SOCKETS = "ArmourEnchantmentHeistWhiteSockets1"
WEAPON_CRITICAL = "WeaponEnchantmentHeistCriticalEffect1"
WEAPON_EXTRA_SLOT = "WeaponEnchantmentHeistAdditionalCraftingModifier1_"
QUALITY_LIFE = "HarvestAlternateArmourQualityIncreasedLife"
QUALITY_ACCURACY = "HarvestAlternateWeaponQualityAccuracyRatingIncrease_"

LIFE_TEXT = "8% increased Explicit Life Modifier magnitudes"
LIFE_ATTRIBUTE_TEXT = "6% increased Explicit Life Modifier magnitudes\n6% increased Explicit Attribute Modifier magnitudes"
EXTRA_SLOT_TEXT = "Can have 1 additional Crafted Modifier"

# The clean Life enchants of body armour in the slice, and in the 3.29 dump (the research counted 4).
CLEAN_LIFE = frozenset({LIFE, LIFE_ATTRIBUTE, LIFE_REQUIREMENTS, LIFE_RESISTANCE})


def _enchant(mod_id: str, family: str, level: int, text: str, *stats: tuple[str, int]) -> Mod:
    return Mod(
        id=mod_id,
        name="",
        text=text,
        type=mod_id.rstrip("_0123456789"),
        families=(family,),
        domain="item",
        generation_type="unique",
        required_level=level,
        spawn_weights=(),
        generation_weights=(),
        adds_tags=(),
        implicit_tags=(),
        stats=tuple(StatRange(stat, value, value) for stat, value in stats),
        is_essence_only=False,
    )


def _armour(mod_id: str, level: int, text: str, *stats: tuple[str, int]) -> Mod:
    return _enchant(mod_id, ARMOUR_POOL, level, text, *stats)


LIFE_STAT = "heist_enchantment_life_mod_effect_+%"
ATTRIBUTE_STAT = "heist_enchantment_attribute_mod_effect_+%"
RESISTANCE_STAT = "heist_enchantment_resistance_mod_effect_+%"
REQUIREMENTS_STAT = "local_attribute_requirements_+%"

SLICE = (
    _armour(LIFE, 1, LIFE_TEXT, (LIFE_STAT, 8)),
    _armour(LIFE_ATTRIBUTE, 20, LIFE_ATTRIBUTE_TEXT, (LIFE_STAT, 6), (ATTRIBUTE_STAT, 6)),
    _armour(
        LIFE_REQUIREMENTS, 20,
        "6% increased Explicit Life Modifier magnitudes\n25% reduced Attribute Requirements",
        (LIFE_STAT, 6), (REQUIREMENTS_STAT, -25),
    ),
    _armour(
        LIFE_RESISTANCE, 20,
        "6% increased Explicit Life Modifier magnitudes\n6% increased Explicit Resistance Modifier magnitudes",
        (LIFE_STAT, 6), (RESISTANCE_STAT, 6),
    ),
    _armour(
        LIFE_RESISTANCE_PENALTY, 69,
        "12% increased Explicit Life Modifier magnitudes\n50% reduced Explicit Resistance Modifier magnitudes",
        (LIFE_STAT, 12), (RESISTANCE_STAT, -50),
    ),
    _armour(
        LIFE_REQUIREMENTS_PENALTY, 69,
        "15% increased Explicit Life Modifier magnitudes\n200% increased Attribute Requirements",
        (LIFE_STAT, 15), (REQUIREMENTS_STAT, 200),
    ),
    _armour(
        LIFE_SOCKET_PENALTY, 69,
        "15% increased Explicit Life Modifier magnitudes\n-3 to maximum Sockets",
        (LIFE_STAT, 15), ("local_maximum_sockets_+", -3),
    ),
    _armour(
        LIFE_LINKED, 30,
        "6% increased Explicit Life Modifier magnitudes\nAll Sockets Linked",
        (LIFE_STAT, 6), ("local_all_sockets_linked", 1),
    ),
    _armour(
        LIFE_NO_RED, 30,
        "8% increased Explicit Life Modifier magnitudes\nHas no Red Sockets",
        (LIFE_STAT, 8), ("local_cannot_have_red_sockets", 1),
    ),
    _armour(
        RESISTANCE_LIFE_PENALTY, 69,
        "12% increased Explicit Resistance Modifier magnitudes\n50% reduced Explicit Life Modifier magnitudes",
        (RESISTANCE_STAT, 12), (LIFE_STAT, -50),
    ),
    _armour(ARMOUR_REQUIREMENTS, 1, "40% reduced Attribute Requirements", (REQUIREMENTS_STAT, -40)),
    _armour(ARMOUR_LINKED, 1, "All Sockets Linked", ("local_all_sockets_linked", 1)),
    _armour(ARMOUR_EXTRA_SLOT, 80, EXTRA_SLOT_TEXT, ("local_can_have_additional_crafted_mods", 1)),
    _armour(ARMOUR_WHITE_SOCKETS, 30, "Has 1 White Socket", ("local_has_X_white_sockets", 1)),
    _enchant(
        WEAPON_CRITICAL, WEAPON_POOL, 1, "8% increased Explicit Critical Modifier magnitudes",
        ("heist_enchantment_critical_mod_effect_+%", 8),
    ),
    _enchant(WEAPON_EXTRA_SLOT, WEAPON_POOL, 80, EXTRA_SLOT_TEXT, ("local_can_have_additional_crafted_mods", 1)),
    _enchant(
        QUALITY_LIFE, ARMOUR_QUALITY, 1,
        "Quality does not increase Defences\nGrants +1 to Maximum Life per 2% Quality",
        ("local_quality_does_not_increase_defences", 1), ("local_maximum_life_per_2%_quality", 1),
    ),
    _enchant(
        QUALITY_ACCURACY, WEAPON_QUALITY, 1,
        "Quality does not increase Physical Damage\nGrants 1% increased Accuracy per 2% Quality",
        ("local_quality_does_not_increase_physical_damage", 1), ("local_accuracy_rating_+%_per_2%_quality", 1),
    ),
)

DATA = replace(FIXTURE, mods={**FIXTURE.mods, **{mod.id: mod for mod in SLICE}})

__all__ = ["AMULET", "BODY", "DATA", "SWORD", "BOW", "SLICE"]
