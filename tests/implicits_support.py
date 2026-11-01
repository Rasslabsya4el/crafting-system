"""Shared helpers for the implicit, quality and unveil-offer tests of `items` (ADR-0027).

The committed fixture data has no Eldritch, veiled or unveiled mods and no boots, so `EXTENDED` adds a few
hand-written records in the shape of the real repoe records (checked against 3.29.3.3): the ids, families,
stat ranges and generation types are the real ones where a real record exists, the rest is marked below.
"""

import dataclasses

from items_support import BODY, DATA

from crafting_system.data import BaseItem, Mod, StatRange, Weight
from crafting_system.items import ExplicitMod, ImplicitMod, Item, Rarity

BELT = "Metadata/Items/Belts/Belt4"  # Heavy Belt, a real base: one ranged implicit, item class Belt
LEATHER_BELT = "Metadata/Items/Belts/Belt3"  # in the fixture data: IncreasedLifeImplicitBelt1
BOOTS = "Metadata/Items/Armours/Boots/BootsStr1"  # invented id: only the item class Boots matters

PRESENCE_UNIQUE = "local_influence_mod_requires_unique_monster_presence"
PRESENCE_PINNACLE = "local_influence_mod_requires_celestial_boss_presence"


def _mod(mod_id, generation_type, domain, family, stats, *, level=1, text="x", mod_type=None) -> Mod:
    return Mod(
        id=mod_id,
        name="",
        text=text,
        type=mod_type or family,
        families=(family,),
        domain=domain,
        generation_type=generation_type,
        required_level=level,
        spawn_weights=(),
        generation_weights=(),
        adds_tags=(),
        implicit_tags=(),
        stats=tuple(StatRange(*stat) for stat in stats),
        is_essence_only=False,
    )


def _eldritch(mod_id, generation_type, family, stats) -> Mod:
    return _mod(mod_id, generation_type, "item", family, stats, level=75)


def _unveiled(mod_id, generation_type, family, stats) -> Mod:
    mod = _mod(mod_id, generation_type, "unveiled", family, stats)
    return dataclasses.replace(mod, spawn_weights=(Weight("default", 0),), implicit_tags=("unveiled_mod",))


EXARCH = "searing_exarch_implicit"
EATER = "eater_of_worlds_implicit"
HAND_MADE = (
    # a base implicit: generation type "unique", domain item, a range
    _mod("StrengthImplicitBelt1", "unique", "item", "Strength", [("additional_strength", 25, 35)]),
    # Searing Exarch: AvoidShock grades 1 to 3, a Unique Enemy variant (two stats) and a Pinnacle variant
    _eldritch("AvoidShockEldritchImplicit1", EXARCH, "AvoidShock", [("base_avoid_shock_%", 33, 35)]),
    _eldritch("AvoidShockEldritchImplicit2", EXARCH, "AvoidShock", [("base_avoid_shock_%", 36, 38)]),
    _eldritch("AvoidShockEldritchImplicit3", EXARCH, "AvoidShock", [("base_avoid_shock_%", 39, 41)]),
    _eldritch(
        "AvoidShockEldritchImplicitUniquePresence4",
        EXARCH,
        "AvoidShock",
        [("base_avoid_shock_%", 51, 53), (PRESENCE_UNIQUE, 1, 1)],
    ),
    _eldritch(
        "AvoidShockEldritchImplicitPinnaclePresence2",
        EXARCH,
        "AvoidShock",
        [("base_avoid_shock_%", 54, 56), (PRESENCE_PINNACLE, 1, 1)],
    ),
    _eldritch("ShockProliferationEldritchImplicit1", EXARCH, "ShockProliferation", [("gloves_shock_proliferation_radius", 12, 12)]),
    # Eater of Worlds
    _eldritch("ChanceToShockEldritchImplicit2", EATER, "ChanceToShock", [("base_chance_to_shock_%", 10, 10)]),
    # a malformed id the data does not have, to see the helper refuse it
    _eldritch("ChanceToShockEldritchImplicitX", EATER, "ChanceToShock", [("base_chance_to_shock_%", 10, 10)]),
    # the veiled placeholders (real stats; the value of veiled_mod_type is invented)
    _mod(
        "VeiledPrefix", "prefix", "veiled", "VeiledPrefix", [("veiled_mod_type", 1, 1), ("veiled_mod_seed", 1, 30000)], text=None
    ),
    _mod(
        "VeiledSuffix", "suffix", "veiled", "VeiledSuffix", [("veiled_mod_type", 2, 2), ("veiled_mod_seed", 1, 30000)], text=None
    ),
    # the unveiled pool: three prefixes (two in one family) and two suffixes
    _unveiled("UnveiledPrefixAilments1", "prefix", "AvoidAilments", [("avoid_all_elemental_status_%", 20, 25)]),
    _unveiled("UnveiledPrefixAilments2", "prefix", "AvoidAilments", [("avoid_all_elemental_status_%", 26, 30)]),
    _unveiled("UnveiledPrefixLife1", "prefix", "IncreasedLife", [("base_maximum_life", 30, 40)]),
    _unveiled("UnveiledPrefixMana1", "prefix", "IncreasedMana", [("base_maximum_mana", 30, 40)]),
    _unveiled("UnveiledSuffixSpeed1", "suffix", "MovementVelocity", [("base_movement_velocity_+%", 10, 12)]),
    _unveiled("UnveiledSuffixCrit1", "suffix", "CriticalStrikeChance", [("critical_strike_chance_+%", 20, 30)]),
)

HEAVY_BELT = BaseItem(
    id=BELT,
    name="Heavy Belt",
    item_class="Belt",
    domain="item",
    drop_level=10,
    tags=("belt", "default"),
    implicits=("StrengthImplicitBelt1",),
    release_state="released",
)
SOME_BOOTS = BaseItem(
    id=BOOTS,
    name="Iron Greaves",
    item_class="Boots",
    domain="item",
    drop_level=1,
    tags=("boots", "str_armour", "armour", "default"),
    implicits=(),
    release_state="released",
)

EXTENDED = dataclasses.replace(
    DATA,
    mods={**DATA.mods, **{mod.id: mod for mod in HAND_MADE}},
    base_items={**DATA.base_items, BELT: HEAVY_BELT, BOOTS: SOME_BOOTS},
)


def implicit(mod_id: str, grade: int = 0) -> ImplicitMod:
    """The implicit `mod_id` of `grade`, every stat rolled at the low end of its range."""
    mod = EXTENDED.mods[mod_id]
    return ImplicitMod(mod_id, grade, tuple(min(stat.min, stat.max) for stat in mod.stats))


def placeholder(mod_id: str = "VeiledPrefix", *, seed: int = 1) -> ExplicitMod:
    """A veiled placeholder with the given (possibly non-canonical) seed."""
    mod = EXTENDED.mods[mod_id]
    values = tuple(seed if stat.id == "veiled_mod_seed" else stat.min for stat in mod.stats)
    return ExplicitMod(mod_id, 1, values)


def make(*mods: ExplicitMod, base_id: str = BELT, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    """A validated item on the extended data (default: a Heavy Belt) at item level 84."""
    fields.setdefault("item_level", 84)
    return Item.build(EXTENDED, base_id=base_id, rarity=rarity, mods=mods, **fields)


def on_body(*mods: ExplicitMod, **fields) -> Item:
    """The same on the fixture body armour."""
    return make(*mods, base_id=BODY, **fields)
