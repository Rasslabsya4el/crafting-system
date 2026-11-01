"""Shared helpers for the #69 `abstraction` tests: the fixture Thicket Bow with a fuller pool, its items, the goals and the checks.

`abstraction_metamod_oracle.py` is the brute force (no `abstraction` import); this module is the one that builds
`Abstraction`s and compares a kernel with it. The pool of the fixture bow is the plain fixture one (fire, cold and
bow-gem prefixes, the generic socketed-gem prefix, attack speed and additional arrows suffixes, and the Hunter families
at the Hunter tag) plus three mods that the fixture has for other items and that this module lets a bow roll, so that every
case of the metamods has something to act on (the tags are the ones of the data):

* `SpellDamageOnWeapon1`, a prefix of the family `WeaponCasterDamagePrefix` with the Caster tag, weight 1500: what
  `Cannot roll Caster Modifiers` blocks (no fixture mod of a bow has the tag);
* `FireResist1` and `ColdResist1`, two suffixes without the Attack tag, weight 1000 each: what is left to a suffix
  draw under `Cannot roll Attack Modifiers`.

Every tag of the other bow mods is the fixture's: fire, cold, the bow gems, attack speed and the arrows are Attack mods; the
generic socketed-gem prefix has neither tag.
"""

import dataclasses
from collections.abc import Callable, Hashable, Iterable
from fractions import Fraction

import pytest
from abstraction_metamod_oracle import (
    annulled,
    exalted,
    fracture_one,
    low_roll,
    rerolled,
    scoured,
    tier_table,
)
from abstraction_oracle import assert_same_distribution, compressed_distribution
from items_support import DATA

from crafting_system.abstraction import Abstraction, CompressedState, Goal, Status, Wanted
from crafting_system.actions import (
    AnnulmentOrb,
    ChaosOrb,
    ExaltedOrb,
    FracturingOrb,
    HarvestReforge,
    NotApplicableError,
    ScouringOrb,
)
from crafting_system.data import Weight
from crafting_system.items import Influence, Item, Rarity

BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
LEVEL = 84
HUNTER = frozenset({Influence.HUNTER})

# prefixes
FIRE, COLD = "LocalAddedFireDamageTwoHand1", "LocalAddedColdDamageTwoHand1"  # Attack
SOCKET = "LocalIncreaseSocketedGemLevel1"  # no tag
SPEC_1, SPEC_2 = "LocalIncreaseSocketedBowGemLevel1", "LocalIncreaseSocketedBowGemLevel2"  # Attack; 2 is tier 1
CASTER = "SpellDamageOnWeapon1"  # Caster (made a bow mod here)
# suffixes
AS_1, AS_5 = "LocalIncreasedAttackSpeed1", "LocalIncreasedAttackSpeed5"  # Attack; 5 is tier 1
ARROW_1, ARROW_2 = "AdditionalArrowBow1_", "AdditionalArrowBow2_"  # Attack
FIRE_RES, COLD_RES = "FireResist1", "ColdResist1"  # no tag (made bow mods here)
# the Hunter families
HYBRID = tuple(f"LocalAddedChaosDamageAndPenetrationInfluence{n}" for n in range(1, 6))  # Attack prefixes
COLD_PER_DEX = "AddedColdDamagePerDexterityInfluence1"
ARMOUR_PEN = ("ArmourPenetrationTwoHandWeaponInfluence1_", "ArmourPenetrationTwoHandWeaponInfluence2_")
INTIMIDATE = ("ChanceToIntimidateOnHitWeaponInfluence1", "ChanceToIntimidateOnHitWeaponInfluence2")
# crafted mods
CRAFT = "EinharMasterWeaponElementalDamage1_"  # an ordinary crafted prefix (Attack tag)
PL = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix; locks the prefixes
SL = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix; locks the suffixes
NA = "IntMasterItemGenerationCannotRollAttackAffixes"  # a suffix
NC = "StrDexMasterItemGenerationCannotRollCasterAffixes"  # a suffix
MM = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # a suffix
METAMODS = {"PL": PL, "SL": SL, "NA": NA, "NC": NC, "MM": MM}
BLOCKING = ("PL", "SL", "NA", "NC")  # the four an `Abstraction` needs the `metamods` flag for


def _on_bow(mod, weight: int):
    return dataclasses.replace(mod, spawn_weights=(Weight("bow", weight), *mod.spawn_weights))


BOW_DATA = dataclasses.replace(
    DATA,
    mods={
        **DATA.mods,
        CASTER: _on_bow(DATA.mods[CASTER], 1500),
        FIRE_RES: _on_bow(DATA.mods[FIRE_RES], 1000),
        COLD_RES: _on_bow(DATA.mods[COLD_RES], 1000),
    },
)

_TIERS: dict[tuple, dict[str, int]] = {}


def tiers(data, base: str, influences: Iterable[Influence] = ()) -> dict[str, int]:
    """The tier table of the oracle (cached): a mod that cannot spawn is absent (1 is used for it)."""
    key = (id(data), base, frozenset(influences))
    if key not in _TIERS:
        _TIERS[key] = tier_table(data, base, influences)
    return _TIERS[key]


def build(
    data,
    base: str,
    mod_ids: Iterable[str],
    *,
    fractured: Iterable[str] = (),
    level: int = LEVEL,
    influences: frozenset[Influence] = frozenset(),
    rarity: Rarity = Rarity.RARE,
    **fields,
) -> Item:
    """A validated item of `base` holding `mod_ids` at their tier (counted with the influence tags) and low rolls.

    A mod of the crafted domain is flagged crafted; a mod in `fractured` is fractured.
    """
    table, fixed = tiers(data, base, influences), set(fractured)
    mods = tuple(
        low_roll(data, mod_id, table.get(mod_id, 1), fractured=mod_id in fixed, crafted=data.mods[mod_id].domain == "crafted")
        for mod_id in mod_ids
    )
    return Item.build(data, base_id=base, item_level=level, rarity=rarity, influences=influences, mods=mods, **fields)


def bow(*mod_ids: str, fractured: Iterable[str] = (), **fields) -> Item:
    """A rare Thicket Bow of the fixture at item level 84 (`level=` and `influences=` change that)."""
    return build(BOW_DATA, BOW, mod_ids, fractured=fractured, **fields)


# --- the goals ----------------------------------------------------------------------------------------

SOCKET_LEAF = Wanted(frozenset({SOCKET}))
SPEC_TIER_1 = Wanted(frozenset({SPEC_1, SPEC_2}), min_tier=1)
ARROW_LEAF = Wanted(frozenset({ARROW_1, ARROW_2}))
SPEED_TIER_1 = Wanted(frozenset({AS_1, AS_5}), min_tier=1)
CASTER_LEAF = Wanted(frozenset({CASTER}))
GOAL = Goal((SOCKET_LEAF, SPEC_TIER_1, ARROW_LEAF, SPEED_TIER_1))
CASTER_GOAL = Goal((SOCKET_LEAF, CASTER_LEAF, SPEED_TIER_1))

# --- the starts ---------------------------------------------------------------------------------------

# the ordinary mods of a start; the metamod, when there is one, is added on top (a suffix but SL, which is a prefix)
BASES = {
    "gem": (FIRE, SOCKET, AS_5, FIRE_RES),
    "mixed": (FIRE, CASTER, AS_5, FIRE_RES),
    "crafted": (FIRE, CRAFT, AS_5, FIRE_RES),
}


def start_of(kind: str, meta: str | None = None, *, fractured: Iterable[str] = (), **fields) -> Item:
    """A rare bow of the base `kind` of `BASES` with the metamod `meta` (a key of `METAMODS`, or none) crafted on it."""
    ids = (*BASES[kind], *([METAMODS[meta]] if meta else []))
    return bow(*ids, fractured=fractured, **fields)


# starts with two or three metamods (the ids, ordinary mods first); each is a legal bow: at most three mods a side
COMBOS = {
    "SL+NA": (FIRE, SOCKET, AS_5, FIRE_RES, SL, NA),  # the suffix lock keeps the Attack metamod: a reroll stays under it
    "SL+NC": (FIRE, CASTER, AS_5, FIRE_RES, SL, NC),
    "PL+SL": (FIRE, SOCKET, AS_5, FIRE_RES, PL, SL),  # both locks: everything is kept
    "NA+NC": (FIRE, CASTER, SOCKET, AS_5, NA, NC),  # nothing is locked: a reroll removes both
    "SL+MM+NA": (FIRE, SOCKET, AS_5, SL, MM, NA),
}


# starts with two or three metamods and a free slot for an Exalted Orb
EXALT_COMBOS = {
    "SL+NA": (FIRE, SOCKET, AS_5, SL, NA),  # one free suffix slot; the Attack metamod keeps the arrows out
    "SL+NC": (FIRE, CASTER, AS_5, SL, NC),
    "NA+NC": (FIRE, CASTER, AS_5, NA, NC),  # one free prefix slot; only the socketed-gem prefix is left
    "NC+MM": (FIRE, CASTER, AS_5, NC, MM),
}


def start_kinds(meta: str | None) -> list[str]:
    """The base kinds that make a legal bow with `meta`: one crafted mod only, unless the multimod is there."""
    return ["gem", "mixed", *(["crafted"] if meta in (None, "MM") else [])]


# a smaller pool of the same bow (the brute force can then walk every concrete item a route reaches)
TINY_IDS = (FIRE, SOCKET, CASTER, AS_5, FIRE_RES, *METAMODS.values())
TINY_DATA = dataclasses.replace(BOW_DATA, mods={mod_id: BOW_DATA.mods[mod_id] for mod_id in TINY_IDS})


# the Hunter bow at item level 78 with a pool small enough to walk: the socketed-gem prefix and the five hybrid tiers
# (four can be drawn at 78), the attack speed and resistance suffixes
HUNTER_TINY_IDS = (SOCKET, AS_5, FIRE_RES, *HYBRID, *METAMODS.values())
HUNTER_TINY_DATA = dataclasses.replace(BOW_DATA, mods={mod_id: BOW_DATA.mods[mod_id] for mod_id in HUNTER_TINY_IDS})


# a mid-size Hunter pool at item level 78: eight families (four prefix, four suffix), for the rerolls that list every finished item
HUNTER_MID_IDS = (SOCKET, FIRE, CASTER, AS_5, FIRE_RES, ARROW_1, ARMOUR_PEN[0], *HYBRID, *METAMODS.values())
HUNTER_MID_DATA = dataclasses.replace(BOW_DATA, mods={mod_id: BOW_DATA.mods[mod_id] for mod_id in HUNTER_MID_IDS})


# --- the abstractions and the checks ---------------------------------------------------------------------

REMOVING = (AnnulmentOrb(), ExaltedOrb())
FRACTURING = (FracturingOrb(), AnnulmentOrb(), ExaltedOrb())


def abstraction(
    goal: Goal = GOAL,
    actions=REMOVING,
    *,
    metamods: bool = False,
    data=BOW_DATA,
    base: str = BOW,
    level: int = LEVEL,
) -> Abstraction:
    """A fresh `Abstraction` of the fixture bow (or of `data`, `base`, `level`) for `goal`; `actions` read the junk."""
    return Abstraction(data, goal, base, level, actions, metamods=metamods)


def oracle_for(action) -> Callable[[object, Item], list[tuple[Item, Fraction]]]:
    """The brute-force finished items of `action`: `(data, start) -> [(item, chance)]`."""
    if isinstance(action, AnnulmentOrb):
        return annulled
    if isinstance(action, ExaltedOrb):
        return exalted
    if isinstance(action, FracturingOrb):
        return fracture_one
    if isinstance(action, ScouringOrb):
        return scoured
    if isinstance(action, ChaosOrb):
        return rerolled
    if isinstance(action, HarvestReforge):
        return lambda data, start: rerolled(data, start, action.tag)
    raise TypeError(f"the oracle plays no {action!r}")


def finished(ab: Abstraction, start: Item, action) -> list[tuple[Item, Fraction]]:
    """The brute-force finished items of `action` on `start`."""
    return oracle_for(action)(ab.data, start)


def expected(ab: Abstraction, start: Item, action) -> dict[Hashable, Fraction]:
    """The brute-force kernel: the finished items passed through `ab.compress`, added up."""
    return compressed_distribution(finished(ab, start, action), ab.compress)


def check(ab: Abstraction, start: Item, action) -> dict[CompressedState, Fraction]:
    """Assert that the kernel of `compress(start)` equals the brute force exactly, and return it."""
    kernel = ab.kernel(ab.compress(start), action)
    assert_same_distribution(kernel, expected(ab, start, action))
    assert sum(kernel.values()) == 1
    return dict(kernel)


def check_or_refusal(ab: Abstraction, start: Item, action) -> dict[CompressedState, Fraction]:
    """`check`, or, when the brute force says the game refuses (it raises `ValueError`), assert that the kernel refuses too.

    Returns the kernel, empty for a refusal. For a matrix of starts where some actions cannot be used.
    """
    try:
        items = finished(ab, start, action)
    except ValueError:
        with pytest.raises(NotApplicableError):
            ab.kernel(ab.compress(start), action)
        return {}
    kernel = ab.kernel(ab.compress(start), action)
    assert_same_distribution(kernel, compressed_distribution(items, ab.compress))
    assert sum(kernel.values()) == 1
    return dict(kernel)


def passing(state: CompressedState, leaf: int) -> bool:
    """Whether the state meets leaf number `leaf` of the goal."""
    return state.status[leaf] is Status.PASSING
