"""Fixture data for the Harvest quality enchants (ticket #240): the 14 mods of the 3.29.3.3 dump, typed by hand, and the items they sit on.

The shared fixture excerpts hold no quality enchant, so `quality_data` adds the 14 to a game data in memory, with the ids, texts and
stats of the dump (`tests/test_actions_harvest_quality_real.py` checks the same facts on the whole dump). `COSTS` is the wiki
table "List of harvest crafting options" as the research (ticket #100) read it, written here and not read from the registry:
body armour 3,250 each, weapon 5,000 each, by lifeforce; no Sacred or Rancour cost.
"""

from dataclasses import replace

from enchant_support import ARMOUR_QUALITY, BODY, SWORD, WEAPON_QUALITY, _enchant

from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Rarity

WILD, VIVID, PRIMAL = (f"{name} Crystallised Lifeforce" for name in ("Wild", "Vivid", "Primal"))
ARMOUR_STAT, WEAPON_STAT = "local_quality_does_not_increase_defences", "local_quality_does_not_increase_physical_damage"
ARMOUR_HEAD, WEAPON_HEAD = "Quality does not increase Defences\n", "Quality does not increase Physical Damage\n"
ARMOUR_PREFIX, WEAPON_PREFIX = "HarvestAlternateArmourQuality", "HarvestAlternateWeaponQuality"

# mod id -> (lifeforce, count, the line of its text, its own stat)
ARMOUR = {
    ARMOUR_PREFIX + "IncreasedLife": (WILD, 3250, "Grants +1 to Maximum Life per 2% Quality", "local_maximum_life_per_2%_quality"),
    ARMOUR_PREFIX + "Strength": (WILD, 3250, "Grants +1 to Strength per 2% Quality", "local_strength_per_2%_quality"),
    ARMOUR_PREFIX + "FireResistance": (WILD, 3250, "Grants +1% to Fire Resistance per 2% Quality", "local_fire_resistance_%_per_2%_quality"),
    ARMOUR_PREFIX + "Dexterity": (VIVID, 3250, "Grants +1 to Dexterity per 2% Quality", "local_dexterity_per_2%_quality"),
    ARMOUR_PREFIX + "ColdResistance": (VIVID, 3250, "Grants +1% to Cold Resistance per 2% Quality", "local_cold_resistance_%_per_2%_quality"),
    ARMOUR_PREFIX + "IncreasedMana": (PRIMAL, 3250, "Grants +1 to Maximum Mana per 2% Quality", "local_maximum_mana_per_2%_quality"),
    ARMOUR_PREFIX + "Intelligence_": (PRIMAL, 3250, "Grants +1 to Intelligence per 2% Quality", "local_intelligence_per_2%_quality"),
    ARMOUR_PREFIX + "LightningResistance": (
        PRIMAL, 3250, "Grants +1% to Lightning Resistance per 2% Quality", "local_lightning_resistance_%_per_2%_quality"
    ),
}
WEAPON = {
    WEAPON_PREFIX + "LocalMeleeWeaponRange_": (WILD, 5000, "+0.1 metres to Weapon Range per 10% Quality", "local_weapon_range_+_per_10%_quality"),
    WEAPON_PREFIX + "AreaOfEffect_": (WILD, 5000, "Grants 1% increased Area of Effect per 4% Quality", "local_area_of_effect_+%_per_4%_quality"),
    WEAPON_PREFIX + "AccuracyRatingIncrease_": (VIVID, 5000, "Grants 1% increased Accuracy per 2% Quality", "local_accuracy_rating_+%_per_2%_quality"),
    WEAPON_PREFIX + "LocalIncreasedAttackSpeed": (VIVID, 5000, "1% increased Attack Speed per 8% Quality", "local_attack_speed_+%_per_8%_quality"),
    WEAPON_PREFIX + "LocalCriticalStrikeChance__": (
        PRIMAL, 5000, "1% increased Critical Strike Chance per 4% Quality", "local_critical_strike_chance_+%_per_4%_quality"
    ),
    WEAPON_PREFIX + "ElementalDamagePercent": (PRIMAL, 5000, "Grants 1% increased Elemental Damage per 2% Quality", "local_elemental_damage_+%_per_2%_quality"),
}
LIFE, MANA = ARMOUR_PREFIX + "IncreasedLife", ARMOUR_PREFIX + "IncreasedMana"
DEXTERITY = ARMOUR_PREFIX + "Dexterity"
RANGE, CRITICAL = WEAPON_PREFIX + "LocalMeleeWeaponRange_", WEAPON_PREFIX + "LocalCriticalStrikeChance__"
ACCURACY = WEAPON_PREFIX + "AccuracyRatingIncrease_"
COSTS = {mod_id: {lifeforce: count} for mod_id, (lifeforce, count, _, _) in {**ARMOUR, **WEAPON}.items()}


def quality_mods() -> dict[str, Mod]:
    """The 14 quality enchants as mods, built the way `enchant_support` builds its slice."""
    mods = {}
    for table, family, head, own in ((ARMOUR, ARMOUR_QUALITY, ARMOUR_HEAD, ARMOUR_STAT), (WEAPON, WEAPON_QUALITY, WEAPON_HEAD, WEAPON_STAT)):
        for mod_id, (_, _, line, stat) in table.items():
            mods[mod_id] = _enchant(mod_id, family, 1, head + line, (own, 1), (stat, 1))
    return mods


def quality_data(data: GameData) -> GameData:
    """`data` with the 14 quality enchants added."""
    return replace(data, mods={**data.mods, **quality_mods()})


def body_armour(data: GameData, *, enchantment: str | None = None, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    """A body armour of item level 84 with no explicit mod."""
    return Item.build(data, base_id=BODY, item_level=84, rarity=rarity, mods=(), enchantment=enchantment, **fields)


def sword(data: GameData, *, enchantment: str | None = None, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    """A sword of item level 84 with no explicit mod."""
    return Item.build(data, base_id=SWORD, item_level=84, rarity=rarity, mods=(), enchantment=enchantment, **fields)
