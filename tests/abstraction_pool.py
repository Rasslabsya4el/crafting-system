"""The small amulet pool of the `abstraction` tests: a subset of the fixture mods and the items built on it.

The pool keeps three prefix families (the gem-level family with its Lightning, Fire and Cold mods,
Lightning damage added, life) and four suffix families (Lightning, Cold and Fire resistance, mana
leech), one to three mods each, so that every finished item of a reroll can be listed one by one.
`SMALL` is the fixture data with only these mods (in the order of the fixture) plus one crafted
mod that is never in a pool. Tiers are counted inside this subset: Lightning Resistance has the
tiers 3, 2 and 1 for `LightningResist1` to `LightningResist3`. Nothing here imports `abstraction`.
"""

import dataclasses

from items_support import AMULET, DATA

from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table

GEM = "GlobalLightningGemLevel1"
FIRE_GEM = "GlobalFireGemLevel1_"
COLD_GEM = "GlobalColdGemLevel1__"
LIFE_1, LIFE_2 = "IncreasedLife1", "IncreasedLife2"
DAMAGE_1, DAMAGE_2 = "AddedLightningDamage1", "AddedLightningDamage2"
RESIST_1, RESIST_2, RESIST_3 = "LightningResist1", "LightningResist2", "LightningResist3"
COLD_RESIST, FIRE_RESIST = "ColdResist1", "FireResist1"
MANA_1, MANA_2 = "ManaLeechPermyriadSuffix1", "ManaLeechPermyriadSuffix2"
CRAFTED = "DexMasterItemGenerationCannotChangeSuffixes"

RESISTS = frozenset({RESIST_1, RESIST_2, RESIST_3})
DAMAGES = frozenset({DAMAGE_1, DAMAGE_2})
LIVES = frozenset({LIFE_1, LIFE_2})
MANAS = frozenset({MANA_1, MANA_2})
POOL_IDS = frozenset(
    {GEM, FIRE_GEM, COLD_GEM, COLD_RESIST, FIRE_RESIST, CRAFTED} | RESISTS | DAMAGES | LIVES | MANAS
)
FAMILIES = 7  # every one of them can be drawn at item level 84

LEVEL = 84

SMALL: GameData = dataclasses.replace(
    DATA, mods={mod_id: mod for mod_id, mod in DATA.mods.items() if mod_id in POOL_IDS}
)
TIERS = tier_table(SMALL, AMULET)


def roll(mod_id: str, *, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    """The mod at its tier in `SMALL` (1 for a mod that cannot spawn) with every stat at the low end."""
    mod = SMALL.mods[mod_id]
    values = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return ExplicitMod(mod_id, TIERS.get(mod_id, 1), values, fractured=fractured, crafted=crafted)


def small_item(*mods: ExplicitMod, level: int = LEVEL, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    """A validated amulet of `SMALL` holding `mods`."""
    return Item.build(SMALL, base_id=AMULET, item_level=level, rarity=rarity, mods=mods, **fields)


def fractured_item(*mod_ids: str, level: int = LEVEL, **fields) -> Item:
    """A rare amulet whose every mod in `mod_ids` is fractured."""
    return small_item(*(roll(mod_id, fractured=True) for mod_id in mod_ids), level=level, **fields)
