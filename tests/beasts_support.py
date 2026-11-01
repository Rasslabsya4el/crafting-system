"""Shared helpers for the beast tests (ticket #147): the fixture data with a Talisman base and the eight aspect suffixes.

The fixture excerpt holds neither, so `BEAST_DATA` copies the fixture amulet base under a new id with the tag
`talisman` and adds four-plus-four synthetic suffixes, copies of a fixture suffix with the ids, family, domain
and levels of the real aspect mods (`beastcraft.aspect_mods`). Nothing here imports a concrete action.
"""

import dataclasses

from items_support import AMULET, DATA
from repoe_support import no_network  # noqa: F401

from crafting_system.data import GameData, StatRange, Weight
from crafting_system.items import ExplicitMod, Item, Rarity

TALISMAN = "Metadata/Items/Amulets/Talismans/TestTalisman"
SUFFIX_TEMPLATE = "LightningResist1"
LEVEL = 86

LIFE, SHIELD, DAMAGE = "IncreasedLife1", "IncreasedEnergyShield1", "AddedLightningDamage1"  # three prefixes
FIRE, COLD, MANA = "FireResist1", "ColdResist1", "ManaLeechPermyriadSuffix1"  # three suffixes
SIX_MODS = (LIFE, SHIELD, DAMAGE, FIRE, COLD, MANA)
CRAFTED = "JunMaster2AllDamage2_"  # an ordinary bench craft (a prefix)
METAMOD = "DexMasterItemGenerationCannotChangeSuffixes"  # the metamod Suffixes Cannot Be Changed (a prefix)

ASPECT_WORDS = {"avian": "Bird", "cat": "Cat", "crab": "Crab", "spider": "Spider"}
ASPECT_IDS = {
    (aspect, level): f"Grants{word}AspectCrafted" + ("30" if level == 30 else "")
    for aspect, word in ASPECT_WORDS.items()
    for level in (20, 30)
}


def _aspect_mod(aspect: str, level: int):
    word = ASPECT_WORDS[aspect]
    template = DATA.mods[SUFFIX_TEMPLATE]
    return dataclasses.replace(
        template,
        id=ASPECT_IDS[aspect, level],
        name=f"of {aspect}",
        text=f"Grants Level {level} Aspect of the {word} Skill",
        type=f"Grants{word}Aspect",
        families=("GrantedSkill",),
        domain="item",
        generation_type="suffix",
        required_level=20,
        spawn_weights=(Weight("default", 0),),
        stats=(StatRange(f"local_display_grants_skill_{word.lower()}_aspect_level", level, level),),
    )


def beast_data(*, talisman: bool = True, aspects: bool = True, data: GameData = DATA) -> GameData:
    """`data` (the fixture data) with the test Talisman base and/or the eight aspect suffixes added."""
    if talisman:
        amulet = data.base_items[AMULET]
        base = dataclasses.replace(amulet, id=TALISMAN, name="Test Talisman", tags=(*amulet.tags, "talisman"))
        data = dataclasses.replace(data, base_items={**data.base_items, TALISMAN: base})
    if aspects:
        mods = {mod_id: _aspect_mod(aspect, level) for (aspect, level), mod_id in ASPECT_IDS.items()}
        data = dataclasses.replace(data, mods={**data.mods, **mods})
    return data


BEAST_DATA = beast_data()


def roll(mod_id: str, *, tier: int = 1, fractured: bool = False, crafted: bool = False, data: GameData = BEAST_DATA) -> ExplicitMod:
    """The mod `mod_id` with every stat rolled at the low end of its range."""
    mod = data.mods[mod_id]
    return ExplicitMod(mod_id, tier, tuple(min(stat.min, stat.max) for stat in mod.stats), fractured=fractured, crafted=crafted)


def contract_beast_data() -> GameData:
    """The data of the contract suite with the test Talisman base and the aspect suffixes added."""
    from contract_support import CONTRACT_DATA  # imported here: the module builds the whole abstraction fixture

    return beast_data(data=CONTRACT_DATA)


def contract_item(base_id: str, mod_ids=(), *, data: GameData, rarity: Rarity = Rarity.RARE) -> Item:
    """An item for the contract suite (`contract_support.check_action`): its mods carry the tiers of its fixture pool."""
    from contract_support import TIERS  # imported here: the module builds the whole abstraction fixture

    mods = tuple(
        ExplicitMod(mod_id, TIERS.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats))
        for mod_id in mod_ids
    )
    return Item.build(data, base_id=base_id, item_level=84, rarity=rarity, mods=mods)


def rare(base_id: str, mod_ids=(), *, data: GameData = BEAST_DATA, rarity: Rarity = Rarity.RARE, extra=(), **fields) -> Item:
    """A validated item on `base_id` holding `mod_ids` at their lowest values, and the `extra` explicit mods."""
    mods = (*(roll(mod_id, data=data) for mod_id in mod_ids), *extra)
    return Item.build(data, base_id=base_id, item_level=fields.pop("item_level", LEVEL), rarity=rarity, mods=mods, **fields)
