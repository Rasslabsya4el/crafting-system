"""Fixture data and items for the Eldritch actions (ticket #151, ADR-0025): boots, gloves, helmets and body armours with a small
hand-made pool, so that every result can be written down by hand.

The data is the contract suite's fixture (`contract_support.CONTRACT_DATA`) plus:

* four bases, `BOOTS` (with a base implicit), `GLOVES`, `HELMET` and `BODY`, each of its own item class and tag;
* boots mods that spawn on boots: prefixes Life 1000, Armour 500, Evasion 300 and Attack 200 (tagged `attack`), suffixes
  Fire 1000, Cold 600, Speed 400 and Caster 100 (tagged `caster`), one tier each, every family its own;
* Eldritch implicits in the shape of the real records (grades 1 to 6 of a base mod, a Unique-Presence variant that weighs half
  and is off at grade 1, a Pinnacle-Presence variant that weighs a fifth and is off at grades 1 and 2):

  ====================  =======  ======  ======  =======
  family (side)         boots    gloves  helmet  body
  ====================  =======  ======  ======  =======
  AvoidShock (Exarch)   700      500     0       0
  FireMax (Exarch)      600      0       400     0
  Aggro (Exarch)        100      0       0       0
  Pierce (Exarch)       0        500     0       0
  Armour (Exarch)       0        0       0       1000
  ChanceToShock (Eater) 400      300     0       0
  Flask (Eater)         300      0       0       0
  Leech (Eater)         200      200     0       0
  ====================  =======  ======  ======  =======

The expected pools in the tests are written by hand from this table, not computed from the fixture.
"""

import dataclasses

from contract_support import CONTRACT_DATA

from crafting_system.data import BaseItem, Mod, StatRange, Weight
from crafting_system.items import (
    EldritchSide,
    ExplicitMod,
    ImplicitMod,
    Influence,
    Item,
    Metamod,
    Rarity,
    eldritch_grade,
)

EXARCH, EATER = "searing_exarch_implicit", "eater_of_worlds_implicit"
BOOTS = "Fixture/Boots"
GLOVES = "Fixture/Gloves"
HELMET = "Fixture/Helmet"
BODY = "Fixture/BodyArmour"
BASE_IMPLICIT = "FixtureBootsBaseImplicit1"
LEVEL = 84

LIFE, ARMOUR, EVASION, ATTACK = "FxPrefixLife1", "FxPrefixArmour1", "FxPrefixEvasion1", "FxPrefixAttack1"
FIRE, COLD, SPEED, CASTER = "FxSuffixFire1", "FxSuffixCold1", "FxSuffixSpeed1", "FxSuffixCaster1"
PREFIX_WEIGHTS = {LIFE: 1000, ARMOUR: 500, EVASION: 300, ATTACK: 200}
SUFFIX_WEIGHTS = {FIRE: 1000, COLD: 600, SPEED: 400, CASTER: 100}

# the metamods of the contract fixture (crafted mods, any base takes them)
LOCK_PREFIXES = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix; locks the prefixes
LOCK_SUFFIXES = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix; locks the suffixes
NO_ATTACK = "FxMetaNoAttack"  # a crafted suffix of the family of Cannot roll Attack Modifiers (the contract fixture has none)
NO_CASTER = "FxMetaNoCaster"  # a crafted suffix of the family of Cannot roll Caster Modifiers

# family -> (side, {item class tag: base weight})
ELDRITCH_FAMILIES = {
    "AvoidShock": (EXARCH, {"boots": 700, "gloves": 500}),
    "FireMax": (EXARCH, {"boots": 600, "helmet": 400}),
    "Aggro": (EXARCH, {"boots": 100}),
    "Pierce": (EXARCH, {"gloves": 500}),
    "Armour": (EXARCH, {"body_armour": 1000}),
    "ChanceToShock": (EATER, {"boots": 400, "gloves": 300}),
    "Flask": (EATER, {"boots": 300}),
    "Leech": (EATER, {"boots": 200, "gloves": 200}),
}
UNIQUE_PRESENCE = "local_influence_mod_requires_unique_monster_presence"
PINNACLE_PRESENCE = "local_influence_mod_requires_celestial_boss_presence"


def eldritch_id(family: str, grade: int, variant: str = "") -> str:
    return f"{family}EldritchImplicit{variant}{grade}"


def _mod(mod_id: str, generation_type: str, family: str, weights: dict[str, int], stats, tags: tuple[str, ...] = (), level: int = 1) -> Mod:
    return Mod(
        id=mod_id,
        name="",
        text="x",
        type=family,
        families=(family,),
        domain="item",
        generation_type=generation_type,
        required_level=level,
        spawn_weights=(*(Weight(tag, weight) for tag, weight in weights.items()), Weight("default", 0)),
        generation_weights=(),
        adds_tags=(),
        implicit_tags=tags,
        stats=tuple(StatRange(*stat) for stat in stats),
        is_essence_only=False,
    )


def _eldritch_mods() -> dict[str, Mod]:
    mods = {}
    for family, (side, weights) in ELDRITCH_FAMILIES.items():
        for grade in range(1, 7):
            low = 10 * grade
            for variant, factor, off_below, extra in (
                ("", 10, 0, ()),
                ("UniquePresence", 5, 2, ((UNIQUE_PRESENCE, 1, 1),)),
                ("PinnaclePresence", 2, 3, ((PINNACLE_PRESENCE, 1, 1),)),
            ):
                mod_id = eldritch_id(family, grade, variant)
                scaled = {tag: (weight // 10) * factor if grade >= off_below else 0 for tag, weight in weights.items()}
                stats = [(f"{family.lower()}_stat", low, low + 2), *extra]
                mod = _mod(mod_id, side, family + variant, scaled, stats, level=75)
                mods[mod_id] = dataclasses.replace(mod, families=(family,), type=family + variant)
    return mods


def _explicit_mods() -> dict[str, Mod]:
    mods = {}
    for table, side in ((PREFIX_WEIGHTS, "prefix"), (SUFFIX_WEIGHTS, "suffix")):
        for mod_id, weight in table.items():
            tags = ("attack",) if mod_id == ATTACK else ("caster",) if mod_id == CASTER else ()
            mods[mod_id] = _mod(mod_id, side, mod_id[:-1], {"boots": weight}, [(f"{mod_id}_stat", 5, 9)], tags)
    mods[BASE_IMPLICIT] = _mod(BASE_IMPLICIT, "unique", "FixtureBaseImplicit", {}, [("fixture_implicit_stat", 3, 4)])
    for mod_id, side, metamod in ((NO_ATTACK, "suffix", Metamod.NO_ATTACK_MODS), (NO_CASTER, "suffix", Metamod.NO_CASTER_MODS)):
        mods[mod_id] = dataclasses.replace(_mod(mod_id, side, metamod.value, {}, []), domain="crafted")
    return mods


def _base(base_id: str, item_class: str, tag: str, implicits: tuple[str, ...] = ()) -> BaseItem:
    return BaseItem(
        id=base_id,
        name=base_id.rsplit("/", 1)[-1],
        item_class=item_class,
        domain="item",
        drop_level=1,
        tags=(tag,),  # not "default" and not "armour": mods of the contract fixture spawn on those, and would join every pool
        implicits=implicits,
        release_state="released",
    )


DATA = dataclasses.replace(
    CONTRACT_DATA,
    mods={**CONTRACT_DATA.mods, **_explicit_mods(), **_eldritch_mods()},
    base_items={
        **CONTRACT_DATA.base_items,
        BOOTS: _base(BOOTS, "Boots", "boots", (BASE_IMPLICIT,)),
        GLOVES: _base(GLOVES, "Gloves", "gloves"),
        HELMET: _base(HELMET, "Helmet", "helmet"),
        BODY: _base(BODY, "Body Armour", "body_armour"),
    },
)


def low(mod_id: str, data=DATA) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)


def roll(mod_id: str, *, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    return ExplicitMod(mod_id, 1, low(mod_id), fractured=fractured, crafted=crafted)


def implicit(mod_id: str) -> ImplicitMod:
    return ImplicitMod(mod_id, eldritch_grade(DATA.mods[mod_id]), low(mod_id))


def exarch(grade: int, family: str = "AvoidShock", variant: str = "") -> ImplicitMod:
    return implicit(eldritch_id(family, grade, variant))


def eater(grade: int, family: str = "ChanceToShock", variant: str = "") -> ImplicitMod:
    return implicit(eldritch_id(family, grade, variant))


def build(
    base: str = BOOTS,
    *mods: ExplicitMod,
    implicits: tuple[ImplicitMod, ...] = (),
    rarity: Rarity = Rarity.RARE,
    level: int = LEVEL,
    **fields,
) -> Item:
    return Item.build(DATA, base_id=base, item_level=level, rarity=rarity, mods=mods, implicits=implicits, **fields)


def boots(*mods: ExplicitMod, implicits: tuple[ImplicitMod, ...] = (), **fields) -> Item:
    return build(BOOTS, *mods, implicits=implicits, **fields)


def amulet() -> Item:
    from items_support import AMULET

    return Item.build(DATA, base_id=AMULET, item_level=LEVEL, rarity=Rarity.RARE)


SHAPER = frozenset({Influence.SHAPER})
SIDES = {EldritchSide.EXARCH: EXARCH, EldritchSide.EATER: EATER}
