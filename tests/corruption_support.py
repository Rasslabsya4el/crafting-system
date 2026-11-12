"""A small world for the Vaal Orb (ticket #259, ADR-0037): the contract suite's data plus a corrupted implicit pool on four bases and the jewels.

`DATA` is `item_state_support.ITEM_DATA` (the contract suite's fixture, hand-made Eldritch implicits, boots) plus

* five corrupted implicits, in `POOL`: weights 1000, 500, 250 and 200 (the last of required level 75, which an item of level 60 leaves out), the
  first with one stat and the second with two, so that the roll of each stat is told apart; the pool is the same on an amulet, boots and a belt;
* the Heavy Belt (one base implicit) and four jewels: a Cobalt, a Crimson, a Viridian and a Prismatic Jewel, each with a pool of two mods (one
  of required level 40), and an abyss jewel with a pool of one mod of its own domain;
* `NO_POOL_BASE`: a base whose class (a flask) no corrupted mod spawns on.

`oracle(item)` is the independent oracle of the Orb: it writes ADR-0037's rules again as plain fractions (four equal outcomes, the weights of the
pool, one implicit of the item replaced uniformly) and returns the chance of every kind of end, never calling `actions.corruption` or the pool.
"""

import dataclasses
from fractions import Fraction

from abstraction_pool import LIFE_1, MANA_1, RESIST_2
from contract_support import CONTRACT_DATA, _roll
from implicits_support import BELT, BOOTS, HEAVY_BELT
from item_state_support import ITEM_DATA, implicit
from items_support import AMULET

from crafting_system.data import BaseItem, StatRange, Weight
from crafting_system.items import ImplicitMod, Item, Rarity

ALL_RES, SECOND, THIRD, LATE = "VaalAllRes", "VaalTwoStats", "VaalThird", "VaalLate"
JEWEL_A, JEWEL_LATE, ABYSS_A = "VaalJewelA", "VaalJewelLate", "VaalAbyssA"
BASE_IMPLICIT = "StrengthImplicitBelt1"  # the Heavy Belt's own implicit (implicits_support)
EXARCH, EXARCH_2 = "AvoidShockEldritchImplicit1", "AvoidShockEldritchImplicit2"
EATER = "ChanceToShockEldritchImplicit2"
LEVEL = 84

# mod id: (weight, required level, family, stats)
POOL = {
    ALL_RES: (1000, 1, "VaalAllResFamily", [(10, 12)]),
    SECOND: (500, 1, "VaalTwoStatsFamily", [(3, 5), (8, 9)]),
    THIRD: (250, 1, "VaalThirdFamily", [(7, 7)]),
    LATE: (200, 75, "VaalLateFamily", [(1, 2)]),
}
JEWEL_POOL = {JEWEL_A: (1000, 1, "VaalJewelFamily", [(4, 6)]), JEWEL_LATE: (1000, 40, "VaalJewelLateFamily", [(1, 3)])}
ABYSS_POOL = {ABYSS_A: (1000, 1, "VaalAbyssFamily", [(2, 4)])}

COBALT = "Metadata/Items/Jewels/VaalTestCobalt"
CRIMSON = "Metadata/Items/Jewels/VaalTestCrimson"
VIRIDIAN = "Metadata/Items/Jewels/VaalTestViridian"
PRISMATIC = "Metadata/Items/Jewels/VaalTestPrismatic"
ABYSS = "Metadata/Items/Jewels/VaalTestAbyss"
FLASK = "Metadata/Items/Flasks/VaalTestFlask"
JEWELS = {"Cobalt Jewel": COBALT, "Crimson Jewel": CRIMSON, "Viridian Jewel": VIRIDIAN, "Prismatic Jewel": PRISMATIC}
NO_POOL_BASE = FLASK


def _mod(template, mod_id, family, domain, level, weights, stats):
    return dataclasses.replace(
        template,
        id=mod_id,
        name=mod_id,
        text=mod_id,
        type=family,
        families=(family,),
        generation_type="corrupted",
        domain=domain,
        required_level=level,
        spawn_weights=tuple(Weight(tag, weight) for tag, weight in weights),
        generation_weights=(),
        implicit_tags=(),
        stats=tuple(StatRange(f"{mod_id}_stat{index}", low, high) for index, (low, high) in enumerate(stats)),
    )


def _world():
    template = CONTRACT_DATA.mods[LIFE_1]
    mods = dict(ITEM_DATA.mods)
    for mod_id, (weight, level, family, stats) in POOL.items():
        mods[mod_id] = _mod(template, mod_id, family, "item", level, [("amulet", weight), ("boots", weight), ("belt", weight), ("default", 0)], stats)
    for mod_id, (weight, level, family, stats) in JEWEL_POOL.items():
        mods[mod_id] = _mod(template, mod_id, family, "misc", level, [("jewel", weight), ("default", 0)], stats)
    for mod_id, (weight, level, family, stats) in ABYSS_POOL.items():
        mods[mod_id] = _mod(template, mod_id, family, "abyss_jewel", level, [("default", weight)], stats)
    bases = dict(ITEM_DATA.base_items)
    bases[BELT] = HEAVY_BELT
    for name, base_id in JEWELS.items():
        bases[base_id] = BaseItem(base_id, name, "Jewel", "misc", 1, ("jewel", "default"), (), "released")
    bases[ABYSS] = BaseItem(ABYSS, "Murderous Eye Jewel", "AbyssJewel", "abyss_jewel", 1, ("abyss_jewel", "default"), (), "released")
    bases[FLASK] = BaseItem(FLASK, "Test Life Flask", "LifeFlask", "flask", 1, ("flask", "default"), (), "released")
    return dataclasses.replace(ITEM_DATA, mods=mods, base_items=bases)


DATA = _world()


def amulet(*mods, implicits=(), rarity=Rarity.RARE, **fields) -> Item:
    return Item.build(DATA, base_id=AMULET, item_level=fields.pop("item_level", LEVEL), rarity=rarity, mods=mods, implicits=implicits, **fields)


def on(base_id: str, *mods, implicits=(), rarity=Rarity.RARE, **fields) -> Item:
    return Item.build(DATA, base_id=base_id, item_level=fields.pop("item_level", LEVEL), rarity=rarity, mods=mods, implicits=implicits, **fields)


def exarch() -> ImplicitMod:
    return implicit(EXARCH)


def eater() -> ImplicitMod:
    return implicit(EATER)


def base_implicit() -> ImplicitMod:
    mod = DATA.mods[BASE_IMPLICIT]
    return ImplicitMod(BASE_IMPLICIT, 0, tuple(min(stat.min, stat.max) for stat in mod.stats))


def starts() -> dict[str, Item]:
    """Rare items with no implicit listed, one, two, a base implicit or an Eater one in its place (no item holds both, ticket #528), a fractured mod, a normal and a magic item."""
    junk = (_roll(RESIST_2), _roll(LIFE_1))
    return {
        "none": amulet(*junk),
        "one": on(BOOTS, *junk, implicits=(exarch(),)),
        "two": on(BOOTS, *junk, implicits=(exarch(), eater())),
        "belt-stored": on(BELT, *junk, implicits=(base_implicit(),)),  # a belt as it is bought: its base implicit
        "belt-replaced": on(BELT, *junk, implicits=(eater(),)),  # the base implicit went to an Ember (#484): the item lists the Eater one alone
        "fractured": amulet(_roll(RESIST_2, fractured=True), _roll(LIFE_1), _roll(MANA_1)),
        "normal": amulet(rarity=Rarity.NORMAL),
        "magic": amulet(_roll(LIFE_1), rarity=Rarity.MAGIC),
    }


def pool_weights(level: int = LEVEL, pool: dict = POOL) -> dict[str, int]:
    """The corrupted pool at `level`, written out: the oracle's own copy of ADR-0037's rule (weight of the first matching tag, required level)."""
    return {mod_id: weight for mod_id, (weight, required, *_) in pool.items() if required <= level}


def oracle(held: list[str], pool: dict[str, int], *, dead_chance: Fraction, nothing_chance: Fraction):
    """Every end of one Vaal Orb by hand: a dict from the end to its chance.

    An end is `("implicit", frozenset of the implicit ids the item holds)`, `"nothing"` or `"dead"`. The item has the `held` implicits it
    lists, the base's own included (#484); one of them, chosen uniformly, is replaced by the drawn mod, and an item with none gains it.
    The four outcomes are equal; the caller gives the chances of the dead end and of nothing (they differ by base).
    """
    kept = [(Fraction(1), list(held))] if not held else [(Fraction(1, len(held)), [i for i in held if i != gone]) for gone in held]
    whole = sum(pool.values())
    ends: dict = {}
    for stay, left in kept:
        for mod_id, weight in pool.items():
            key = ("implicit", frozenset([*left, mod_id]))
            ends[key] = ends.get(key, Fraction(0)) + Fraction(1, 4) * stay * Fraction(weight, whole)
    ends["dead"] = dead_chance
    ends["nothing"] = nothing_chance
    assert sum(ends.values()) == 1
    return ends
