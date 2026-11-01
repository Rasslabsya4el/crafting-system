"""A small world for the Bloodstained Fossil (ticket #261, ADR-0038): the boots of `test_actions_fossil.py` with a corrupted implicit pool.

`DATA` is the world of the fossil tests plus

* four corrupted implicits that boots can get, weights 1000, 250, 500 and 200 (W = 1,950 at item level 86): "all resistances", chaos
  resistance, an added cold damage and a mod of required level 75 that item level 60 leaves out (W = 1,750 there);
* two Eldritch implicits (one per side, grade 1 and 2) and the base implicit of `IMPLICIT_BOOTS` (a made-up base with one), which the
  implicit a resonator draws can replace;
* a jewel with a pool of one corrupted mod of required level 40, so that a jewel of item level 30 has an empty pool;
* `NO_POOL_GLOVES`: gloves, which no corrupted mod spawns on (the class has no pool).

`bloodstained(*others)` is the resonator, `starts` the boots it is used on, and the independent oracle of the implicit draw
(`implicit_cases`) is written here with plain fractions, from the rules of ADR-0037 and ADR-0038 and not from `actions.bloodstained`.
"""

import dataclasses
from fractions import Fraction

from test_actions_fossil import BOOTS, DATA as FOSSIL_DATA, GLOVES, JEWEL, fossil_id, roll

from crafting_system.actions import ApplyFossils
from crafting_system.data import Weight
from crafting_system.items import ImplicitMod, Item, Rarity

BLOODSTAINED = "Bloodstained Fossil"
GILDED = "Gilded Fossil"
IMPLICIT_BOOTS = "Metadata/Items/Armours/Boots/TestBootsWithImplicit"

ALL_RES = "CorruptedAllRes"
CHAOS_RES = "CorruptedChaosRes"
COLD_DAMAGE = "CorruptedColdDamage"
LATE = "CorruptedLate"  # required level 75
JEWEL_LATE = "CorruptedJewelLate"  # the only corrupted mod of a jewel, required level 40
EXARCH = "EldritchExarchImplicit1"  # grade 1, the Searing Exarch side
EATER = "EldritchEaterImplicit2"  # grade 2, the Eater of Worlds side
BASE_IMPLICIT = "BootsBaseImplicit"

# mod id: (weight on boots, required level, family, low, high)
POOL = {
    ALL_RES: (1000, 1, "AllResCorrupted", 14, 16),
    CHAOS_RES: (250, 1, "ChaosResCorrupted", 10, 14),
    COLD_DAMAGE: (500, 1, "ColdDamageCorrupted", 3, 4),
    LATE: (200, 75, "LateCorrupted", 1, 1),
}


def _extend(data):
    template = data.mods["FireResA"]

    def mod(mod_id, family, generation_type, level, weights, low, high):
        return dataclasses.replace(
            template,
            id=mod_id,
            name=mod_id,
            text=mod_id,
            type=family,
            families=(family,),
            generation_type=generation_type,
            domain="item",
            required_level=level,
            spawn_weights=tuple(Weight(tag, weight) for tag, weight in weights),
            generation_weights=(),
            implicit_tags=(),
            stats=(dataclasses.replace(template.stats[0], id=f"{mod_id}_stat", min=low, max=high),),
        )

    mods = dict(data.mods)
    for mod_id, (weight, level, family, low, high) in POOL.items():
        mods[mod_id] = mod(mod_id, family, "corrupted", level, [("boots", weight), ("default", 0)], low, high)
    mods[JEWEL_LATE] = mod(JEWEL_LATE, "JewelLateCorrupted", "corrupted", 40, [("jewel", 1000), ("default", 0)], 5, 6)
    mods[EXARCH] = mod(EXARCH, "ExarchFamily", "searing_exarch_implicit", 1, [("boots", 700), ("default", 0)], 20, 22)
    mods[EATER] = mod(EATER, "EaterFamily", "eater_of_worlds_implicit", 1, [("boots", 700), ("default", 0)], 30, 33)
    mods[BASE_IMPLICIT] = mod(BASE_IMPLICIT, "BootsBaseImplicitFamily", "unique", 1, [], 8, 10)
    bases = dict(data.base_items)
    bases[IMPLICIT_BOOTS] = dataclasses.replace(bases[BOOTS], id=IMPLICIT_BOOTS, name="Test Boots With Implicit", implicits=(BASE_IMPLICIT,))
    gilded = dataclasses.replace(data.fossils[fossil_id(BLOODSTAINED)], id=fossil_id(GILDED), name=GILDED)  # no weight, no forced mod: it only holds a socket
    return dataclasses.replace(data, mods=mods, base_items=bases, fossils={**data.fossils, gilded.id: gilded}, bench_options=())  # no bench craft: the fixture's name mods this world lacks


DATA = _extend(FOSSIL_DATA)
NO_POOL_GLOVES = GLOVES
LEVEL = 86


def boots(*mods, rarity=Rarity.RARE, base=BOOTS, **fields) -> Item:
    """Boots of the extended world (the `boots` of the fossil tests validates against its own data)."""
    fields.setdefault("item_level", LEVEL)
    return Item.build(DATA, base_id=base, rarity=rarity, mods=mods, **fields)


def bloodstained(*others: str) -> ApplyFossils:
    """The resonator with the Bloodstained Fossil and the fossils `others` (named without the word Fossil: "Scorched")."""
    return ApplyFossils((BLOODSTAINED, *(f"{name} Fossil" for name in others)))


def plain(*others: str) -> ApplyFossils | None:
    """The same resonator without the Bloodstained Fossil, None when it holds no other fossil."""
    return ApplyFossils(tuple(f"{name} Fossil" for name in others)) if others else None


def exarch(grade_values=(20,)) -> ImplicitMod:
    return ImplicitMod(EXARCH, 1, grade_values)


def eater(values=(30,)) -> ImplicitMod:
    return ImplicitMod(EATER, 2, values)


def base_implicit() -> ImplicitMod:
    return ImplicitMod(BASE_IMPLICIT, 0, (8,))


def starts() -> dict[str, Item]:
    """Rare boots with no implicit, one Eldritch implicit, both, and (on a base with one) the base implicit stored or not and an Eldritch one."""
    mods = (roll("LifeA"), roll("CasterA"))
    return {
        "none": boots(*mods),
        "one": boots(*mods, implicits=(exarch(),)),
        "two": boots(*mods, implicits=(exarch(), eater())),
        "base-and-eldritch": boots(*mods, base=IMPLICIT_BOOTS, implicits=(base_implicit(), eater())),
        "unstored-base-implicit": boots(*mods, base=IMPLICIT_BOOTS, implicits=(eater(),)),  # the base has one the item does not store
        "fractured": boots(roll("CasterA", fractured=True), roll("LifeA"), implicits=(exarch(),)),
    }


def forbidding(*tags: str):
    """The world with a Bloodstained Fossil that forbids the item tags `tags` (the real one forbids the three heist tags)."""
    record = DATA.fossils[fossil_id(BLOODSTAINED)]
    changed = dataclasses.replace(record, forbidden_tags=tags)
    return dataclasses.replace(DATA, fossils={**DATA.fossils, record.id: changed})


def unstored_of(item: Item) -> list[str]:
    """The implicits of the item's base that the item does not store: the game's item has them too."""
    stored = {entry.mod_id for entry in item.implicits}
    return [mod_id for mod_id in DATA.base_items[item.base_id].implicits if mod_id not in stored]


def pool_weights(level: int = LEVEL) -> dict[str, int]:
    """The corrupted pool of boots at `level`, written out: the oracle's own copy of ADR-0037's rule."""
    return {mod_id: weight for mod_id, (weight, required, *_) in POOL.items() if required <= level}


def implicit_cases(
    held: list[str], pool: dict[str, int], replaces_all: bool, unstored: list[str] = ()
) -> list[tuple[Fraction, frozenset[str]]]:
    """Every end of the implicit draw by hand: the chance and the ids of the implicits the finished item holds.

    The game's item has the `held` implicits it stores and the `unstored` implicits of its base; one of them, chosen uniformly, is
    replaced (all, with a Gilded Fossil), and an item with none gains the drawn one. An unstored implicit is on no finished item.
    """
    candidates = [*held, *unstored]
    if replaces_all or not candidates:
        kept = [(Fraction(1), [])]
    else:
        kept = [(Fraction(1, len(candidates)), [other for other in held if other != gone]) for gone in candidates]
    whole = sum(pool.values())
    return [
        (stay * Fraction(weight, whole), frozenset([*left, mod_id]))
        for stay, left in kept
        for mod_id, weight in pool.items()
    ]
