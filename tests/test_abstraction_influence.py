"""Layer 1 (ADR-0019) on the Hunter-influenced fixture Thicket Bow, with a `min_tier` goal on an influence mod (ticket #69).

R14's bow is a Hunter Thicket Bow at item level 78. Its pool is the plain one plus the Hunter families (the Chaos
Damage Hybrid prefix in five tiers, cold damage per Dexterity, armour penetration, chance to intimidate), and the tier of
an influence mod counts among the mods of its type that can spawn with the Hunter tag: Chaos Damage Hybrid 5 is tier 1
and 1 is tier 5, mods that the table of the bare base does not list at all (it would call each of them tier 1). A goal
asking `min_tier=2` of the hybrid prefix is met by 5 and 4 only, and at item level 78 only 4 can be drawn (weight 300
of the 10300 of the pool at hand). The kernels equal the brute force of `abstraction_metamod_oracle.py` (which counts the
tiers on its own), alone and with each metamod; the Fracturing Orb refuses an influenced item and is tested elsewhere.
"""

from fractions import Fraction

import pytest
from abstraction_metamod_oracle import annulled, closure, exalted
from abstraction_removals_support import (
    AS_5,
    BLOCKING,
    BOW,
    BOW_DATA,
    CASTER_LEAF,
    FIRE,
    FIRE_RES,
    HUNTER,
    HUNTER_MID_DATA,
    HUNTER_TINY_DATA,
    HYBRID,
    METAMODS,
    MM,
    NA,
    SOCKET,
    SOCKET_LEAF,
    SPEED_TIER_1,
    abstraction,
    bow,
    build,
    check,
    check_or_refusal,
)

from crafting_system.abstraction import Goal, Status, Wanted
from crafting_system.actions import (
    ActionError,
    AnnulmentOrb,
    ChaosOrb,
    ExaltedOrb,
    HarvestReforge,
    ScouringOrb,
)

LEVEL = 78
HYBRID_TIER_2 = Wanted(frozenset(HYBRID), min_tier=2)  # Chaos Damage Hybrid 4 or 5
GOAL = Goal((HYBRID_TIER_2, SOCKET_LEAF, SPEED_TIER_1))
R14_GOAL = Goal((SOCKET_LEAF, CASTER_LEAF, SPEED_TIER_1, HYBRID_TIER_2))
ANNUL, EXALT, SCOUR, CHAOS = AnnulmentOrb(), ExaltedOrb(), ScouringOrb(), ChaosOrb()
ACTIONS = {
    "annul": ANNUL,
    "exalted": EXALT,
    "scour": SCOUR,
    "chaos": CHAOS,
    "reforge_chaos": HarvestReforge("chaos"),
    "reforge_fire": HarvestReforge("fire"),
}
ARMOUR_PEN = "ArmourPenetrationTwoHandWeaponInfluence1_"

STARTS = {
    "plain": (SOCKET, FIRE, AS_5, FIRE_RES),
    "hybrid_passing": (SOCKET, HYBRID[3], AS_5, FIRE_RES),  # Chaos Damage Hybrid 4 is tier 2
    "hybrid_below": (HYBRID[0], FIRE, AS_5, ARMOUR_PEN),  # Chaos Damage Hybrid 1 is tier 5
}


def hunter_bow(*mod_ids, **fields):
    return bow(*mod_ids, influences=HUNTER, level=LEVEL, **fields)


def hunter_bow_of(data, *mod_ids, **fields):
    return build(data, BOW, mod_ids, influences=HUNTER, level=LEVEL, **fields)


def hunting(goal=GOAL, actions=(ANNUL, EXALT), *, metamods=True, data=BOW_DATA):
    return abstraction(goal, actions, metamods=metamods, level=LEVEL, data=data)


# --- the tier of an influence mod in a state --------------------------------------------------------------------------------


def test_a_concrete_influence_mod_gives_the_goal_what_its_influence_tier_gives():
    ab = hunting()

    states = {n: ab.compress(hunter_bow(SOCKET, HYBRID[n], AS_5, FIRE_RES)) for n in range(4)}

    assert [states[n].status[0] for n in range(4)] == [Status.BELOW, Status.BELOW, Status.BELOW, Status.PASSING]


def test_influence_mods_that_fail_the_tier_are_one_state():
    ab = hunting()

    first = ab.compress(hunter_bow(SOCKET, HYBRID[0], AS_5, FIRE_RES))
    third = ab.compress(hunter_bow(SOCKET, HYBRID[2], AS_5, FIRE_RES))

    assert first == third  # tiers 5 and 3 both fail min_tier=2 and nothing else tells them apart


def test_an_exalted_orb_lands_the_tier_2_influence_mod_with_the_chance_of_its_weight():
    ab = hunting()
    start = hunter_bow(*STARTS["plain"])

    kernel = check(ab, start, EXALT)

    passing = sum(chance for after, chance in kernel.items() if after.status[0] is Status.PASSING)
    assert passing == Fraction(300, 10300)  # a table of the bare base would call every hybrid tier 1 and say 1700/10300
    assert passing == ExaltedOrb().outcomes(BOW_DATA, start).chance_all({HYBRID[3]})


def test_the_pool_of_a_hunter_bow_is_a_state_the_plain_bow_does_not_have():
    ab = hunting()
    plain, hunter = bow(*STARTS["plain"], level=LEVEL), hunter_bow(*STARTS["plain"])

    check(ab, plain, EXALT)  # one abstraction serves both: each item has the pool of its own influences
    check(ab, hunter, EXALT)

    assert ab.compress(plain) != ab.compress(hunter)
    assert ab.compress(hunter).flags.influences == HUNTER


# --- layer 1 --------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("action", ACTIONS.values(), ids=ACTIONS.keys())
@pytest.mark.parametrize("start", STARTS)
def test_the_kernel_on_a_hunter_bow_equals_the_brute_force(start, action, flag):
    ab = hunting(metamods=flag, data=HUNTER_MID_DATA)

    check_or_refusal(ab, hunter_bow_of(HUNTER_MID_DATA, *STARTS[start]), action)


@pytest.mark.parametrize("action", ACTIONS.values(), ids=ACTIONS.keys())
@pytest.mark.parametrize("meta", [*BLOCKING, "MM"])
@pytest.mark.parametrize("start", ["hybrid_passing", "hybrid_below"])
def test_the_kernel_on_a_hunter_bow_with_a_metamod_equals_the_brute_force(start, meta, action):
    ab = hunting(data=HUNTER_MID_DATA)

    check_or_refusal(ab, hunter_bow_of(HUNTER_MID_DATA, *STARTS[start], METAMODS[meta]), action)


@pytest.mark.parametrize("flag", [False, True])
def test_a_hunter_bow_with_fractured_junk_equals_the_brute_force(flag):
    ab = hunting(metamods=flag, data=HUNTER_MID_DATA)
    start = hunter_bow_of(HUNTER_MID_DATA, *STARTS["hybrid_passing"], fractured=[HYBRID[3]])

    for action in (ANNUL, EXALT, CHAOS, SCOUR, HarvestReforge("chaos")):
        check_or_refusal(ab, start, action)


def test_a_fractured_influence_mod_keeps_its_tier_through_a_reroll():
    ab = hunting(data=HUNTER_MID_DATA)
    start = hunter_bow_of(HUNTER_MID_DATA, *STARTS["hybrid_passing"], fractured=[HYBRID[3]])

    kernel = check(ab, start, CHAOS)

    assert all(after.status[0] is Status.PASSING for after in kernel)  # the fractured tier 2 mod stays: the goal is met in every state


# --- R14's shape: the multimod and `Cannot roll Attack Modifiers` fill the suffixes of the Hunter bow --------------------------------------------------


def r14_bow():
    return hunter_bow(AS_5, MM, NA)


def test_r14_the_attack_metamod_leaves_two_prefix_families_to_the_exalted_orb():
    ab = hunting(R14_GOAL)

    kernel = check(ab, r14_bow(), EXALT)

    assert len(kernel) == 2  # the socketed-gem prefix and the caster prefix: every Attack prefix, the Hunter ones too, is out
    wanted = {leaf: sum(chance for after, chance in kernel.items() if after.status[leaf] is Status.PASSING) for leaf in (0, 1)}
    assert wanted == {0: Fraction(2, 5), 1: Fraction(3, 5)}  # the weights 1000 and 1500


def test_r14_two_exalted_orbs_land_both_wanted_prefixes_with_certainty():
    ab = hunting(R14_GOAL)
    first = ab.kernel(ab.compress(r14_bow()), EXALT)

    both = Fraction(0)
    for state, chance in first.items():
        for after, inner in ab.kernel(state, EXALT).items():
            if after.status[0] is Status.PASSING and after.status[1] is Status.PASSING:
                both += chance * inner

    assert both == 1


def test_the_closure_of_a_hunter_route_equals_the_compressed_concrete_closure():
    actions = (ANNUL, EXALT)
    ab = abstraction(GOAL, actions, metamods=True, level=LEVEL, data=HUNTER_TINY_DATA)
    start = build(HUNTER_TINY_DATA, ab.base_id, (SOCKET, AS_5), influences=HUNTER, level=LEVEL)
    steps = [lambda item: annulled(HUNTER_TINY_DATA, item), lambda item: exalted(HUNTER_TINY_DATA, item)]

    reached = ab.reachable([ab.compress(start)], actions)

    assert len(reached) > 10
    assert reached == {ab.compress(item) for item in closure(start, steps)}
    for state in reached:
        for action in actions:
            try:
                assert sum(ab.kernel(state, action).values()) == 1
            except ActionError:
                pass
