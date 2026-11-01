"""Shared helpers for the Wild Bristle Matron and side-swap tests (ticket #147): a small pool whose odds a person can work out by hand.

`SMALL` is the fixture data cut down to the mods below (and the five metamods and one ordinary crafted mod), with the
Caster tag put on the Lightning Damage % family (the fixture has no caster mod). The prefix pool, with the required
level and weight of each mod (the fixture amulet has the tag `amulet`, whose weights all of these use):

    Life        IncreasedLife1 (5, 1000)  IncreasedLife2 (11, 1000)           one family, weight 2000
    Energy Sh.  IncreasedEnergyShield1 (3, 1000)
    Lightning   AddedLightningDamage1 (3, 500)  AddedLightningDamage9 (76, 250)    attack tag, one family
    Gem level   GlobalSkillGemLevel1 (75, 50)

and the suffix pool:

    FireResist1 (1, 1000)   ColdResist1 (1, 1000)   LifeLeechPermyriadSuffix1 (50, 1000, attack tag)
    ChaosResist1 (16, 250)  ChaosResist6 (81, 250)  LightningDamagePercent1 (10, 500, caster tag)

Nothing here imports a concrete action.
"""

import dataclasses

from items_support import AMULET, DATA
from repoe_support import no_network  # noqa: F401

from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Item, Rarity

LIFE1, LIFE2, ES1 = "IncreasedLife1", "IncreasedLife2", "IncreasedEnergyShield1"
LIGHTNING1, LIGHTNING9, GEM1 = "AddedLightningDamage1", "AddedLightningDamage9", "GlobalSkillGemLevel1"
FIRE, COLD, LEECH = "FireResist1", "ColdResist1", "LifeLeechPermyriadSuffix1"
CHAOS1, CHAOS6, LPCT = "ChaosResist1", "ChaosResist6", "LightningDamagePercent1"
PREFIXES = (LIFE1, LIFE2, ES1, LIGHTNING1, LIGHTNING9, GEM1)
SUFFIXES = (FIRE, COLD, LEECH, CHAOS1, CHAOS6, LPCT)

PCBC = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix; locks the prefixes
SCBC = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix; locks the suffixes
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"  # a suffix
NO_CASTER = "StrDexMasterItemGenerationCannotRollCasterAffixes"  # a suffix
MULTI = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # a suffix
METAMODS = (PCBC, SCBC, NO_ATTACK, NO_CASTER, MULTI)
CRAFTED = "JunMaster2AllDamage2_"  # an ordinary bench craft (a prefix)
ITEM_LEVEL = 86


def _small() -> GameData:
    keep = {*PREFIXES, *SUFFIXES, *METAMODS, CRAFTED}
    mods = {}
    for mod_id, mod in DATA.mods.items():
        if mod_id not in keep:
            continue
        if mod.families == ("LightningDamagePercentage",):
            mod = dataclasses.replace(mod, implicit_tags=(*mod.implicit_tags, "caster"))
        mods[mod_id] = mod
    return dataclasses.replace(DATA, mods=mods)


SMALL = _small()


def roll(mod_id: str, *, fractured: bool = False, crafted: bool = False, tier: int = 1) -> ExplicitMod:
    """The mod `mod_id` at the low end of its ranges."""
    mod = SMALL.mods[mod_id]
    return ExplicitMod(mod_id, tier, tuple(min(stat.min, stat.max) for stat in mod.stats), fractured=fractured, crafted=crafted)


def item_of(
    *mod_ids: str,
    fractured: tuple[str, ...] = (),
    crafted: tuple[str, ...] = (),
    item_level: int = ITEM_LEVEL,
    rarity: Rarity = Rarity.RARE,
    **fields,
) -> Item:
    """A validated fixture amulet holding `mod_ids`; the metamods and the bench craft are crafted mods automatically."""
    auto = {*METAMODS, CRAFTED}
    mods = tuple(roll(m, fractured=m in fractured, crafted=m in crafted or m in auto) for m in mod_ids)
    return Item.build(SMALL, base_id=AMULET, item_level=item_level, rarity=rarity, mods=mods, **fields)


def outcome_table(outcomes) -> dict[frozenset[str], object]:
    """The listed results as `{set of mod ids of the finished item: its chance}` (two results never hold the same mods here)."""
    table: dict[frozenset[str], object] = {}
    for chance, result in outcomes.results:
        key = frozenset(entry.mod_id for entry in result.mods)
        assert key not in table, "two results hold the same mods"
        table[key] = chance
    return table
