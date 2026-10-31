"""The compressed kernel equals full enumeration over concrete items, in exact fractions (ticket #24, layer 1).

For each start item, goal and action, `Abstraction.kernel(compress(start), action)` is compared with
`abstraction_oracle`: every concrete finished item of the reroll, with its exact probability, passed
through `compress` and added up per state. The pool is the small amulet of `abstraction_pool` (3
prefix and 4 suffix families), so the enumeration is a thousand items or fewer. The comparison is
exact `==` on `Fraction`s and the probabilities must add up to exactly 1.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_pool import (
    COLD_RESIST,
    CRAFTED,
    DAMAGE_1,
    FIRE_GEM,
    FIRE_RESIST,
    GEM,
    LIFE_1,
    MANA_1,
    RESIST_1,
    RESIST_2,
    RESIST_3,
    RESISTS,
    SMALL,
    fractured_item,
    roll,
    small_item,
)
from abstraction_support import (
    ABSENT,
    ACTIONS,
    BELOW,
    CHAOS,
    PASSING,
    REFORGE,
    abstraction,
    check_kernel,
)

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.items import Influence, Rarity

STARTS = {
    "plain": (),
    "resist": (RESIST_2,),
    "resist_tier_3": (RESIST_1,),
    "resist_tier_1": (RESIST_3,),
    "junk_cold": (COLD_RESIST,),
    "junk_fire": (FIRE_RESIST,),
    "junk_life": (LIFE_1,),
    "junk_mana": (MANA_1,),
    "damage": (DAMAGE_1,),
    "other_gem": (FIRE_GEM,),
    "resist_and_other_gem": (RESIST_2, FIRE_GEM),
    "resist_and_damage": (RESIST_2, DAMAGE_1),
    "two_junk": (COLD_RESIST, LIFE_1),
    "three_suffixes": (COLD_RESIST, FIRE_RESIST, MANA_1),
    "resist_and_two_suffixes": (RESIST_2, COLD_RESIST, FIRE_RESIST),
    "three_prefixes": (LIFE_1, DAMAGE_1, FIRE_GEM),
    "four": (RESIST_2, COLD_RESIST, LIFE_1, DAMAGE_1),
    "six": (LIFE_1, DAMAGE_1, FIRE_GEM, COLD_RESIST, FIRE_RESIST, MANA_1),
    "tagged_blocked": (GEM, DAMAGE_1, RESIST_1),
}
# The reforge refuses these: no tagged mod has a free family and a free slot.
REFORGE_REFUSES = {"six", "tagged_blocked"}
CORE = ("plain", "resist", "junk_cold", "other_gem", "resist_and_damage")

CASES = (
    [("r12", start, action, 84) for start in STARTS for action in ACTIONS]
    + [("tier", start, action, 84) for start in (*CORE, "resist_tier_3", "resist_tier_1") for action in ACTIONS]
    + [("any", start, action, 84) for start in (*CORE, "two_junk") for action in ACTIONS]
    + [("two_of_three", start, action, 84) for start in (*CORE, "three_prefixes") for action in ACTIONS]
    + [("nested", start, action, 84) for start in ("plain", "resist_and_damage", "three_suffixes", "four") for action in ACTIONS]
    + [("unspawnable", start, action, 84) for start in ("plain", "resist", "three_suffixes") for action in ACTIONS]
    + [("roll_not_asked", start, action, 84) for start in ("plain", "resist") for action in ACTIONS]
    + [("r12", start, action, 70) for start in ("plain", "resist", "junk_cold") for action in ACTIONS]
    + [("r12", start, action, 12) for start in ("plain", "junk_cold", "damage") for action in ACTIONS]
)
CASES = [case for case in CASES if not (case[2] == "reforge" and case[1] in REFORGE_REFUSES)]


@pytest.mark.parametrize(("goal", "start", "action", "level"), CASES, ids=["-".join(map(str, case)) for case in CASES])
def test_the_kernel_equals_the_enumeration_over_concrete_items(goal, start, action, level):
    ab = abstraction(goal, level)

    check_kernel(ab, fractured_item(*STARTS[start], level=level), ACTIONS[action])


@pytest.mark.parametrize("action", ACTIONS.values())
def test_the_probabilities_of_a_kernel_sum_to_exactly_one_and_none_is_a_float(action):
    ab = abstraction()
    for ids in STARTS.values():
        if action is REFORGE and ids in (STARTS["six"], STARTS["tagged_blocked"]):
            continue
        kernel = ab.kernel(ab.compress(fractured_item(*ids)), action)

        assert sum(kernel.values()) == 1
        assert all(type(chance) is Fraction and chance > 0 for chance in kernel.values())


@pytest.mark.parametrize("action", ACTIONS.values())
def test_the_r12_goal_reaches_four_status_pairs_from_a_plain_amulet(action):
    kernel = check_kernel(abstraction(), fractured_item(), action)

    assert {state.status for state in kernel} == {
        (ABSENT, ABSENT),
        (PASSING, ABSENT),
        (ABSENT, PASSING),
        (PASSING, PASSING),
    }


def test_a_resist_below_the_asked_tier_is_told_apart_from_one_that_passes():
    kernel = check_kernel(abstraction("tier"), fractured_item(), CHAOS)

    assert {state.status[1] for state in kernel} == {ABSENT, BELOW, PASSING}


def test_a_fractured_resist_below_the_asked_tier_stays_below_whatever_is_drawn():
    kernel = check_kernel(abstraction("tier"), fractured_item(RESIST_1), CHAOS)

    assert {state.status[1] for state in kernel} == {BELOW}


def test_a_fractured_gem_mod_of_another_type_blocks_the_target():
    kernel = check_kernel(abstraction(), fractured_item(FIRE_GEM), REFORGE)

    assert {state.status[0] for state in kernel} == {ABSENT}


def test_a_leaf_with_no_spawnable_mod_stays_absent_and_the_goal_is_never_met():
    ab = abstraction("unspawnable")

    kernel = check_kernel(ab, fractured_item(), CHAOS)

    assert {state.status[1] for state in kernel} == {ABSENT}
    assert not any(ab.is_goal(state) for state in kernel)


def test_a_leaf_that_cannot_spawn_at_this_item_level_stays_absent():
    # The gem-level mods need item level 75.
    kernel = check_kernel(abstraction("r12", 70), fractured_item(level=70), REFORGE)

    assert {state.status[0] for state in kernel} == {ABSENT}


def test_the_fractured_mods_and_flags_of_the_state_are_unchanged_by_the_action():
    ab = abstraction()
    start = ab.compress(fractured_item(RESIST_2, COLD_RESIST))

    for action in ACTIONS.values():
        for state in ab.kernel(start, action):
            assert state.flags == start.flags and state.fractured == start.fractured


def test_junk_that_is_not_fractured_does_not_change_the_kernel():
    ab = abstraction()
    clean = fractured_item(RESIST_2)
    dirty = small_item(roll(RESIST_2, fractured=True), roll(GEM), roll(LIFE_1), roll(FIRE_RESIST))

    for action in ACTIONS.values():
        assert ab.kernel(ab.compress(dirty), action) == check_kernel(ab, clean, action)
        assert check_kernel(ab, dirty, action)


@pytest.mark.parametrize("action", ACTIONS.values())
def test_a_roll_limit_that_asks_nothing_does_not_stop_the_kernel(action):
    kernel = check_kernel(abstraction("roll_not_asked"), fractured_item(), action)

    assert any(state.status[1] == PASSING for state in kernel)


@pytest.mark.parametrize("action", ACTIONS.values())
def test_a_roll_limit_on_a_mod_that_can_be_drawn_is_out_of_scope(action):
    ab = abstraction(Goal((Wanted(RESISTS, min_roll=(10,)),)))

    with pytest.raises(OutOfScopeError, match="roll"):
        ab.kernel(ab.compress(fractured_item()), action)


REFUSED = {
    "normal": lambda: small_item(rarity=Rarity.NORMAL),
    "magic": lambda: small_item(roll(LIFE_1), rarity=Rarity.MAGIC),
    "corrupted": lambda: dataclasses.replace(fractured_item(RESIST_2), corrupted=True),
    "crafted_mod": lambda: small_item(roll(CRAFTED, crafted=True)),
    "crafted_mod_and_fractured": lambda: small_item(roll(RESIST_2, fractured=True), roll(CRAFTED, crafted=True)),
    "corrupted_and_influenced": lambda: dataclasses.replace(
        fractured_item(), corrupted=True, influences=frozenset({Influence.HUNTER})
    ),
    "corrupted_and_crafted": lambda: dataclasses.replace(small_item(roll(CRAFTED, crafted=True)), corrupted=True),
}


@pytest.mark.parametrize("action", ACTIONS.values())
@pytest.mark.parametrize("name", REFUSED)
def test_an_item_the_action_refuses_is_refused_with_the_same_error(name, action):
    item = REFUSED[name]()
    ab = abstraction()
    with pytest.raises((NotApplicableError, OutOfScopeError)) as direct:
        action.outcomes(SMALL, item)

    with pytest.raises((NotApplicableError, OutOfScopeError)) as compressed:
        ab.kernel(ab.compress(item), action)

    assert type(compressed.value) is type(direct.value)
    if "crafted" not in name:
        assert str(compressed.value) == str(direct.value)


def test_a_crafted_mod_is_out_of_scope_even_though_the_rest_of_the_item_could_be_rerolled():
    item = small_item(roll(RESIST_2, fractured=True), roll(CRAFTED, crafted=True))
    ab = abstraction()

    with pytest.raises(OutOfScopeError, match="crafted"):
        ab.kernel(ab.compress(item), CHAOS)


def test_a_reforge_with_no_tagged_mod_to_draw_is_refused_while_a_chaos_orb_works():
    ab = abstraction()
    item = fractured_item(*STARTS["tagged_blocked"])
    state = ab.compress(item)

    with pytest.raises(NotApplicableError, match="no lightning mod"):
        ab.kernel(state, REFORGE)
    check_kernel(ab, item, CHAOS)
    assert {after.status for after in ab.kernel(state, CHAOS)} == {(PASSING, PASSING)}


def test_a_reforge_is_refused_when_the_side_of_every_tagged_mod_is_full():
    # Three fractured suffixes fill that side; the tagged prefixes are blocked by one fractured mod each.
    item = fractured_item(COLD_RESIST, FIRE_RESIST, MANA_1, DAMAGE_1, GEM)
    ab = abstraction()

    with pytest.raises(NotApplicableError, match="no lightning mod"):
        ab.kernel(ab.compress(item), REFORGE)
