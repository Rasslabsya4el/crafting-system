"""Fixture data for the influence crafts (ticket #154): a helmet base and synthetic influence mods, typed so that every number is by hand.

The fixture excerpt holds no helmet and no influence mod of a helmet, so `influence_data` adds a `Contract Helmet` (item class
Helmet, whose class key is `helmet`) and these mods, copies of two fixture mods with their own ids, families, levels and weights:

    id                         side    family                 level  weight   on tag           tier
    ContractHelmetPlain1       prefix  ContractHelmetPlain       1    1000    helmet           1   (no influence: never in an influence pool)
    ContractHelmetShaperP1     prefix  ContractHelmetShaperP    68     300    helmet_shaper    3
    ContractHelmetShaperP2     prefix  ContractHelmetShaperP    75     300    helmet_shaper    2
    ContractHelmetShaperP3     prefix  ContractHelmetShaperP    80     200    helmet_shaper    1
    ContractHelmetShaperS1     suffix  ContractHelmetShaperS    68     500    helmet_shaper    2
    ContractHelmetShaperS2     suffix  ContractHelmetShaperS    75     500    helmet_shaper    1
    ContractHelmetShaperHigh1  suffix  ContractHelmetShaperH    90     700    helmet_shaper    1   (above the item levels of the tests)
    ContractHelmetShaperOld1   prefix  ContractHelmetShaperO    68       0    helmet_shaper    -   (a legacy mod: weight 0)
    ContractHelmetElderS1      suffix  ContractHelmetElderS     70     400    helmet_elder     1
    ContractHelmetElderP1      prefix  ContractHelmetElderP     70     100    helmet_elder     1
    ContractHelmetHunterS1     suffix  ContractHelmetHunterS    68     100    helmet_basilisk  1

and four Elevated mods (weight 0, level 90, the family of the mod they come from): `ContractHelmetShaperP3Maven`,
`ContractHelmetShaperS2Maven`, `ContractHelmetElderS1Maven` and `ContractHelmetElderP1Maven`. `ELEVATED` pairs each top-tier mod with its Elevated mod.
Nothing here imports a concrete action.
"""

import dataclasses

from items_support import DATA

from crafting_system.data import BaseItem, GameData, Mod, Weight
from crafting_system.items import ExplicitMod, Item, Rarity

HELMET = "Metadata/Items/Armours/Helmets/ContractHelmet"
PREFIX_TEMPLATE, SUFFIX_TEMPLATE = "AddedLightningDamage1", "ColdResist1"

PLAIN = "ContractHelmetPlain1"
P1, P2, P3 = "ContractHelmetShaperP1", "ContractHelmetShaperP2", "ContractHelmetShaperP3"
S1, S2 = "ContractHelmetShaperS1", "ContractHelmetShaperS2"
HIGH, OLD = "ContractHelmetShaperHigh1", "ContractHelmetShaperOld1"
ELDER_S, ELDER_P, HUNTER_S = "ContractHelmetElderS1", "ContractHelmetElderP1", "ContractHelmetHunterS1"
P3_MAVEN, S2_MAVEN, ELDER_S_MAVEN = "ContractHelmetShaperP3Maven", "ContractHelmetShaperS2Maven", "ContractHelmetElderS1Maven"
ELDER_P_MAVEN = "ContractHelmetElderP1Maven"
ELEVATED = ((P3, P3_MAVEN), (S2, S2_MAVEN), (ELDER_S, ELDER_S_MAVEN), (ELDER_P, ELDER_P_MAVEN))

# id: (side, family, required level, weight, tag, template, name)
ORDINARY = {
    PLAIN: ("prefix", "ContractHelmetPlain", 1, 1000, "helmet", PREFIX_TEMPLATE, "Plain"),
    P1: ("prefix", "ContractHelmetShaperP", 68, 300, "helmet_shaper", PREFIX_TEMPLATE, "Shaper's"),
    P2: ("prefix", "ContractHelmetShaperP", 75, 300, "helmet_shaper", PREFIX_TEMPLATE, "Shaper's"),
    P3: ("prefix", "ContractHelmetShaperP", 80, 200, "helmet_shaper", PREFIX_TEMPLATE, "Shaper's"),
    S1: ("suffix", "ContractHelmetShaperS", 68, 500, "helmet_shaper", SUFFIX_TEMPLATE, "of Shaping"),
    S2: ("suffix", "ContractHelmetShaperS", 75, 500, "helmet_shaper", SUFFIX_TEMPLATE, "of Shaping"),
    HIGH: ("suffix", "ContractHelmetShaperH", 90, 700, "helmet_shaper", SUFFIX_TEMPLATE, "of Shaping"),
    OLD: ("prefix", "ContractHelmetShaperO", 68, 0, "helmet_shaper", PREFIX_TEMPLATE, "Shaper's"),
    ELDER_S: ("suffix", "ContractHelmetElderS", 70, 400, "helmet_elder", SUFFIX_TEMPLATE, "of the Elder"),
    ELDER_P: ("prefix", "ContractHelmetElderP", 70, 100, "helmet_elder", PREFIX_TEMPLATE, "Elder's"),
    HUNTER_S: ("suffix", "ContractHelmetHunterS", 68, 100, "helmet_basilisk", SUFFIX_TEMPLATE, "of the Hunt"),
}
# elevated id: (the mod it comes from, tag)
ELEVATED_FROM = {P3_MAVEN: (P3, "helmet_shaper"), S2_MAVEN: (S2, "helmet_shaper"), ELDER_S_MAVEN: (ELDER_S, "helmet_elder"), ELDER_P_MAVEN: (ELDER_P, "helmet_elder")}


def influence_mods(data: GameData) -> dict[str, Mod]:
    """The synthetic mods above, built from two mods of `data`."""
    mods: dict[str, Mod] = {}
    for mod_id, (side, family, level, weight, tag, template, name) in ORDINARY.items():
        mods[mod_id] = dataclasses.replace(
            data.mods[template],
            id=mod_id,
            name=name,
            type=family,
            families=(family,),
            generation_type=side,
            required_level=level,
            spawn_weights=(Weight(tag, weight), Weight("default", 0)),
            generation_weights=(),
        )
    for mod_id, (origin, tag) in ELEVATED_FROM.items():
        source = mods[origin]
        mods[mod_id] = dataclasses.replace(
            source,
            id=mod_id,
            name="Elevated " + source.name,
            type=source.type + "Maven",
            required_level=90,
            spawn_weights=(Weight(tag, 0), Weight("default", 0)),
        )
    return mods


def influence_data(data: GameData = DATA) -> GameData:
    """`data` with the Contract Helmet and the synthetic influence mods added."""
    helmet = BaseItem(HELMET, "Contract Helmet", "Helmet", "item", 1, ("helmet", "armour", "default"), (), "released")
    return dataclasses.replace(
        data, mods={**data.mods, **influence_mods(data)}, base_items={**data.base_items, HELMET: helmet}
    )


INFLUENCE_DATA = influence_data()


def roll(mod_id: str, tier: int, data: GameData = INFLUENCE_DATA, **flags) -> ExplicitMod:
    """The mod `mod_id` at tier `tier` with every stat rolled at the low end of its range."""
    mod = data.mods[mod_id]
    return ExplicitMod(mod_id, tier, tuple(min(stat.min, stat.max) for stat in mod.stats), **flags)


def helmet(*mods: ExplicitMod, level: int = 84, rarity: Rarity = Rarity.RARE, data: GameData = INFLUENCE_DATA, **fields) -> Item:
    """A validated Contract Helmet."""
    return Item.build(data, base_id=HELMET, item_level=level, rarity=rarity, mods=mods, **fields)
