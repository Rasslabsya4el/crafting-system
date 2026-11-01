"""Verification layer 1 on a bow, a Hunter bow and a quiver of the real 3.29.3.3 dump: removals, adds, fractures and metamods (ticket #69).

The real pools have 23 to 35 families, too many for the brute force of `abstraction_metamod_oracle.py`, so each case
keeps six or seven families of the real pool (a few mods each, the real weights, levels and tags) and the metamods it uses.
The kernel is compared with the brute force on that subset, in exact fractions, for the Annulment, the Exalted Orb, the
Orb of Scouring, the Chaos Orb and an Attack Harvest reforge, with and without each metamod, and for each item a Fracturing
Orb can leave. The Hunter bow is R14's (item level 78): the Chaos Damage Hybrid prefix keeps all its five tiers so that the
goal `min_tier=2` of an influence mod means what it does in the game. Another test marks the Hunter caster prefix with the
Caster tag (the real pool has no Caster mod on a bow or a quiver) so that `Cannot roll Caster Modifiers` has something to block.

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`).
They skip cleanly when it is not there; CI fetches it (ticket #165), so they run there.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_metamod_oracle import fracture_one
from abstraction_removals_support import (
    FRACTURING,
    HUNTER,
    METAMODS,
    abstraction,
    build,
    check,
    check_or_refusal,
    tiers,
)
from abstraction_support import real_game_data

from crafting_system.abstraction import Goal, Status, Wanted
from crafting_system.actions import (
    AnnulmentOrb,
    ChaosOrb,
    ExaltedOrb,
    FracturingOrb,
    HarvestReforge,
    ScouringOrb,
    build_pool,
)
from crafting_system.items import Item, Rarity

BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
QUIVER = "Metadata/Items/Quivers/QuiverNew5"
ANNUL, EXALT, SCOUR, CHAOS, FRACTURE = AnnulmentOrb(), ExaltedOrb(), ScouringOrb(), ChaosOrb(), FracturingOrb()
ATTACK_REFORGE = HarvestReforge("attack")
CRAFT = "EinharMasterWeaponElementalDamage1_"  # an ordinary crafted prefix of weapons

HYBRID = tuple(f"LocalAddedChaosDamageAndPenetrationInfluence{n}" for n in range(1, 6))
AS_BOW = ("LocalIncreasedAttackSpeed1", "LocalIncreasedAttackSpeed4", "LocalIncreasedAttackSpeed5")
FASTER = ("FasterBleedDamageTwoHandInfluence1", "FasterBleedDamageTwoHandInfluence2", "FasterPoisonDamageTwoHandInfluence1", "FasterPoisonDamageTwoHandInfluence2")
CASTER_PREFIX = ("PoisonDamagePrefixInfluence1__", "PoisonDamagePrefixInfluence2__")


def pick(real, base, level, influences, family, count):
    """The ids of the first `count` mods (by id) of `family` in the pool of an empty rare item of `base` at `level`."""
    empty = Item.build(real, base_id=base, item_level=level, rarity=Rarity.RARE, influences=influences)
    (found,) = [entry for entry in build_pool(real, empty) if entry.family == family]
    return tuple(sorted(mod.mod.id for mod in found.mods)[:count])


def reduced(real, ids, mark_caster=()):
    """`real` with only the mods `ids` and the five metamods; the mods `mark_caster` also get the Caster tag."""
    keep = set(ids) | set(METAMODS.values()) | {CRAFT}
    mods = {mod_id: real.mods[mod_id] for mod_id in real.mods if mod_id in keep}
    for mod_id in mark_caster:
        mods[mod_id] = dataclasses.replace(mods[mod_id], implicit_tags=(*mods[mod_id].implicit_tags, "caster"))
    return dataclasses.replace(real, mods=mods)


@pytest.fixture(scope="module")
def real():
    return real_game_data()


class Case:
    """A reduced pool, its goal and the starts that fit it."""

    def __init__(self, real, base, level, influences, picks, goal_for, start_ids, *, extra=(), mark_caster=()):
        self.base, self.level, self.influences = base, level, influences
        self.ids = {family: ids if isinstance(ids, tuple) else pick(real, base, level, influences, family, ids) for family, ids in picks.items()}
        self.data = reduced(real, [mod_id for ids in self.ids.values() for mod_id in ids] + list(extra), mark_caster)
        self.goal = goal_for(self.ids)
        self.start_ids = start_ids(self.ids)

    def item(self, mod_ids, **fields):
        return build(self.data, self.base, mod_ids, level=self.level, influences=self.influences, **fields)

    def abstraction(self, actions=(ANNUL, EXALT), *, metamods=True):
        return abstraction(self.goal, actions, metamods=metamods, data=self.data, base=self.base, level=self.level)

    def start(self, meta=None, **fields):
        """The item of this case's `start_ids` (two prefixes, two suffixes) with the metamod `meta` (a key of `METAMODS`, or none) on top."""
        return self.item([*self.start_ids, *([METAMODS[meta]] if meta else [])], **fields)


def bow_case(real):
    return Case(
        real,
        BOW,
        84,
        frozenset(),
        {
            "IncreaseSocketedGemLevel": 1,
            "IncreaseSpecificSocketedGemLevel": 2,
            "FireDamage": 3,
            "IncreasedAttackSpeed": AS_BOW,
            "StunDurationIncreasePercent": 3,
            "AdditionalArrows": 1,
            "LifeGainedFromEnemyDeath": 3,
        },
        lambda ids: Goal(
            (
                Wanted(frozenset(ids["IncreaseSocketedGemLevel"])),
                Wanted(frozenset(ids["IncreaseSpecificSocketedGemLevel"]), min_tier=1),
                Wanted(frozenset(ids["IncreasedAttackSpeed"]), min_tier=1),
            )
        ),
        lambda ids: (ids["FireDamage"][0], ids["IncreaseSpecificSocketedGemLevel"][0], AS_BOW[2], ids["StunDurationIncreasePercent"][0]),
    )


def quiver_case(real):
    return Case(
        real,
        QUIVER,
        81,
        frozenset(),
        {
            "IncreasedLife": 3,
            "DamageWithWeaponTypeSkill": 3,
            "PhysicalDamage": 3,
            "IncreasedAttackSpeed": 3,
            "AdditionalArrows": 1,
            "ColdResistance": 3,
            "CriticalStrikeChanceIncrease": 3,
        },
        lambda ids: Goal(
            (
                Wanted(frozenset(ids["IncreasedLife"])),
                Wanted(frozenset(ids["DamageWithWeaponTypeSkill"])),
                Wanted(frozenset(ids["AdditionalArrows"])),
            )
        ),
        lambda ids: (ids["PhysicalDamage"][0], ids["IncreasedLife"][0], ids["IncreasedAttackSpeed"][0], ids["ColdResistance"][0]),
    )


def hunter_case(real, *, mark_caster=False):
    return Case(
        real,
        BOW,
        78,
        HUNTER,
        {
            "IncreaseSocketedGemLevel": 1,
            "ChaosDamageHybrid": HYBRID,
            "WeaponCasterDamagePrefix": CASTER_PREFIX,
            "IncreasedAttackSpeed": AS_BOW,
            "FasterDamageAilments": FASTER,
            "StunDurationIncreasePercent": 3,
        },
        lambda ids: Goal(
            (
                Wanted(frozenset(HYBRID), min_tier=2),
                Wanted(frozenset(ids["IncreaseSocketedGemLevel"])),
                Wanted(frozenset(ids["IncreasedAttackSpeed"]), min_tier=1),
            )
        ),
        lambda ids: (HYBRID[3], ids["IncreaseSocketedGemLevel"][0], AS_BOW[2], FASTER[0]),
        mark_caster=CASTER_PREFIX if mark_caster else (),
    )


CASES = {"bow": bow_case, "quiver": quiver_case, "hunter": hunter_case}
METAS = [None, *METAMODS]
ACTIONS = {"annul": ANNUL, "exalted": EXALT, "scour": SCOUR, "chaos": CHAOS, "reforge_attack": ATTACK_REFORGE}


@pytest.fixture(scope="module", params=list(CASES))
def case(request, real):
    return CASES[request.param](real)


@pytest.fixture(scope="module", params=["bow", "quiver"])
def plain_case(request, real):
    """A case without influence: the Fracturing Orb refuses an influenced item."""
    return CASES[request.param](real)


# --- the kernel against the brute force on the real pool ---------------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS.values(), ids=ACTIONS.keys())
@pytest.mark.parametrize("meta", METAS, ids=lambda meta: meta or "plain")
def test_the_kernel_equals_the_brute_force_with_and_without_each_metamod(case, meta, action):
    ab = case.abstraction()

    check_or_refusal(ab, case.start(meta), action)


@pytest.mark.parametrize("action", ACTIONS.values(), ids=ACTIONS.keys())
def test_the_kernel_equals_the_brute_force_with_a_fractured_mod_and_a_crafted_mod(case, action):
    ab = case.abstraction()
    start = case.item([CRAFT, *case.start_ids[1:]], fractured=[case.start_ids[1]])  # a crafted prefix replaces the first prefix

    check_or_refusal(ab, start, action)


def test_the_flag_off_gives_the_same_kernel_for_an_item_with_no_blocking_metamod(case):
    ab = case.abstraction(metamods=False)

    for action in (ANNUL, EXALT, SCOUR, CHAOS):
        check_or_refusal(ab, case.start(), action)


# --- the Fracturing Orb and a fracture in the middle of a route -------------------------------------------------------------


@pytest.mark.parametrize("meta", [None, "PL", "SL", "NA", "MM"], ids=lambda meta: meta or "plain")
def test_a_fracture_equals_the_brute_force_and_so_does_the_next_action(plain_case, meta):
    ab = plain_case.abstraction(FRACTURING)
    start = plain_case.start(meta)

    check(ab, start, FRACTURE)
    for after, _ in fracture_one(ab.data, start):
        for action in (ANNUL, CHAOS, SCOUR):
            check_or_refusal(ab, after, action)


@pytest.mark.parametrize("fractured", [CRAFT, METAMODS["PL"], METAMODS["NA"]], ids=["craft", "PL", "NA"])
def test_a_fractured_crafted_mod_and_a_fractured_metamod_stay_through_the_next_action(plain_case, fractured):
    ab = plain_case.abstraction(FRACTURING)
    start = plain_case.item([CRAFT, *plain_case.start_ids[1:]] if fractured == CRAFT else [*plain_case.start_ids, fractured])

    (after,) = [item for item, _ in fracture_one(ab.data, start) if any(e.mod_id == fractured and e.fractured for e in item.mods)]

    kept = check(ab, after, CHAOS)
    assert all(len(state.fractured) == 1 for state in kept)
    for action in (ANNUL, SCOUR, EXALT):
        check_or_refusal(ab, after, action)


# --- the Hunter bow: the tier of an influence mod, R14's shape ---------------------------------------------------------------


def test_an_exalted_orb_on_the_hunter_bow_lands_the_tier_2_hybrid_with_the_chance_of_its_weight(real):
    case = hunter_case(real)
    ab = case.abstraction()
    start = case.item([case.ids["IncreaseSocketedGemLevel"][0], AS_BOW[2], FASTER[0]])

    kernel = check(ab, start, EXALT)

    passing = sum(chance for state, chance in kernel.items() if state.status[0] is Status.PASSING)
    assert passing == ExaltedOrb().outcomes(case.data, start).chance_all({HYBRID[3]})
    assert tiers(case.data, BOW, HUNTER)[HYBRID[3]] == 2  # tier 2 with the Hunter tag; the bare base does not list it at all
    assert HYBRID[3] not in tiers(case.data, BOW)


def test_cannot_roll_caster_modifiers_blocks_a_caster_tagged_hunter_prefix(real):
    case = hunter_case(real, mark_caster=True)
    ab = case.abstraction()

    for meta in ("NC", "NA", None):
        for action in (ANNUL, EXALT, CHAOS):
            check_or_refusal(ab, case.start(meta), action)
    check_or_refusal(ab, case.item([*case.start_ids[:3], METAMODS["NC"]], fractured=[METAMODS["NC"]]), CHAOS)


def test_r14_two_exalted_orbs_under_the_attack_metamod_on_the_real_hunter_pool(real):
    case = hunter_case(real, mark_caster=False)
    goal = Goal((Wanted(frozenset(case.ids["IncreaseSocketedGemLevel"])), Wanted(frozenset(CASTER_PREFIX))))
    ab = abstraction(goal, (ANNUL, EXALT), metamods=True, data=case.data, base=BOW, level=78)
    start = case.item([AS_BOW[2], METAMODS["MM"], METAMODS["NA"]])

    first = check(ab, start, EXALT)
    both = Fraction(0)
    for state, chance in first.items():
        for after, inner in ab.kernel(state, EXALT).items():
            if all(status is Status.PASSING for status in after.status):
                both += chance * inner

    assert both == 1  # the socketed-gem prefix and the Hunter caster prefix are all the Attack metamod leaves, and two orbs land both

