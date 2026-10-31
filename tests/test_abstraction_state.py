"""`Abstraction.compress`, `is_goal` and `family_types` on the small amulet pool: what a state stores and what it merges."""

import dataclasses

import pytest
from abstraction_pool import (
    COLD_GEM,
    COLD_RESIST,
    CRAFTED,
    DAMAGE_2,
    FAMILIES,
    FIRE_GEM,
    FIRE_RESIST,
    GEM,
    LIFE_1,
    RESIST_1,
    RESIST_2,
    RESIST_3,
    RESISTS,
    TIERS,
    fractured_item,
    roll,
    small_item,
)
from abstraction_support import ABSENT, BELOW, PASSING, abstraction

from crafting_system.abstraction import Flags, FracturedMod, Goal, Wanted
from crafting_system.items import Influence, Item, Rarity

PLAIN_FLAGS = Flags(rarity=Rarity.RARE, corrupted=False, influences=frozenset())


def test_a_state_keeps_the_flags_the_fractured_mod_and_the_status_of_the_whole_item():
    item = small_item(roll(RESIST_2, fractured=True), roll(GEM), roll(LIFE_1), roll(COLD_RESIST))

    state = abstraction().compress(item)

    assert state.flags == PLAIN_FLAGS
    assert state.fractured == (FracturedMod(RESIST_1, (ABSENT, PASSING)),)
    assert state.status == (PASSING, PASSING)


def test_a_plain_item_is_all_absent_with_nothing_fractured():
    state = abstraction().compress(fractured_item())

    assert state.fractured == () and state.status == (ABSENT, ABSENT)


def test_a_state_is_a_hashable_value():
    ab = abstraction()
    state = ab.compress(fractured_item(RESIST_2))

    assert state == ab.compress(fractured_item(RESIST_2)) and hash(state) == hash(ab.compress(fractured_item(RESIST_2)))
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.status = ()


def test_every_tier_of_a_fractured_resist_is_one_state_when_no_tier_is_asked():
    ab = abstraction()

    states = {ab.compress(fractured_item(mod_id)) for mod_id in RESISTS}

    assert len(states) == 1
    assert states.pop().fractured[0].mod_id == RESIST_1


def test_the_tiers_that_the_goal_tells_apart_are_different_states():
    ab = abstraction("tier")

    below, better, best = (ab.compress(fractured_item(mod_id)) for mod_id in (RESIST_1, RESIST_2, RESIST_3))

    assert TIERS[RESIST_1] > 2 >= TIERS[RESIST_2] > TIERS[RESIST_3]
    assert below.fractured == (FracturedMod(RESIST_1, (ABSENT, BELOW)),)
    assert better == best and better.fractured[0].mod_id == RESIST_2
    assert below != better
    assert (below.status, better.status) == ((ABSENT, BELOW), (ABSENT, PASSING))


def test_two_gem_level_mods_of_other_types_are_one_state_that_only_blocks_the_family():
    ab = abstraction()

    fire, cold = ab.compress(fractured_item(FIRE_GEM)), ab.compress(fractured_item(COLD_GEM))

    assert fire == cold
    assert fire.fractured == (FracturedMod(COLD_GEM, (ABSENT, ABSENT)),)
    assert fire != ab.compress(fractured_item(GEM))


def test_fractured_junk_of_different_families_stays_two_states():
    ab = abstraction()

    assert ab.compress(fractured_item(COLD_RESIST)) != ab.compress(fractured_item(FIRE_RESIST))


def test_the_fractured_mods_are_sorted_by_id_and_contribution():
    state = abstraction().compress(fractured_item(RESIST_3, FIRE_RESIST, COLD_RESIST))

    assert [mod.mod_id for mod in state.fractured] == [COLD_RESIST, FIRE_RESIST, RESIST_1]
    assert list(state.fractured) == sorted(state.fractured, key=lambda mod: (mod.mod_id, mod.contribution))


def test_the_same_fractured_mods_give_the_same_state_in_any_order():
    ab = abstraction()

    assert ab.compress(fractured_item(COLD_RESIST, FIRE_RESIST)) == ab.compress(fractured_item(FIRE_RESIST, COLD_RESIST))


def test_the_best_of_several_mods_counts_for_a_leaf():
    leaf = Wanted(frozenset({LIFE_1, DAMAGE_2}), min_tier=1)
    ab = abstraction(Goal((leaf,)))

    assert (TIERS[LIFE_1], TIERS[DAMAGE_2]) == (2, 1)
    assert ab.compress(small_item(roll(LIFE_1))).status == (BELOW,)
    assert ab.compress(small_item(roll(DAMAGE_2))).status == (PASSING,)
    assert ab.compress(small_item(roll(LIFE_1), roll(DAMAGE_2))).status == (PASSING,)


def test_the_tier_stored_on_a_mod_is_the_one_that_counts_for_a_mod_on_the_item():
    ab = abstraction("tier")
    claimed_best = dataclasses.replace(roll(RESIST_1, fractured=True), tier=1)
    claimed_worst = dataclasses.replace(roll(RESIST_3, fractured=True), tier=5)

    assert ab.compress(small_item(claimed_best)).status == (ABSENT, PASSING)
    assert ab.compress(small_item(claimed_worst)).status == (ABSENT, BELOW)


@pytest.mark.parametrize(
    ("min_roll", "expected"),
    [((12,), PASSING), ((14,), PASSING), ((15,), BELOW), ((None,), PASSING), ((None, None), BELOW), ((10, 10), BELOW)],
)
def test_a_roll_limit_is_checked_against_the_values_stored_on_the_mod(min_roll, expected):
    ab = abstraction(Goal((Wanted(RESISTS, min_roll=min_roll),)))
    rolled = dataclasses.replace(roll(RESIST_2, fractured=True), values=(14,))

    assert ab.compress(small_item(rolled)).status == (expected,)


def test_a_crafted_mod_sets_the_flag_and_fails_a_not_crafted_leaf():
    item = small_item(roll(CRAFTED, crafted=True))
    asked = abstraction(Goal((Wanted(frozenset({CRAFTED}), not_crafted=True),)))
    not_asked = abstraction(Goal((Wanted(frozenset({CRAFTED})),)))

    assert asked.compress(item).crafted and asked.compress(item).status == (BELOW,)
    assert not_asked.compress(item).status == (PASSING,)
    assert not abstraction().compress(fractured_item()).crafted


def test_the_flags_of_the_item_are_carried_into_the_state():
    item = dataclasses.replace(
        fractured_item(RESIST_2), corrupted=True, influences=frozenset({Influence.SHAPER, Influence.HUNTER})
    )

    flags = abstraction().compress(item).flags

    assert flags == Flags(Rarity.RARE, True, frozenset({Influence.SHAPER, Influence.HUNTER}))
    assert abstraction().compress(small_item(roll(LIFE_1), rarity=Rarity.MAGIC)).flags.rarity is Rarity.MAGIC


@pytest.mark.parametrize(
    "item",
    [
        fractured_item(level=83),
        fractured_item(level=85),
        Item(base_id="Metadata/Items/Belts/Belt3", item_level=84, rarity=Rarity.RARE),
    ],
    ids=["lower item level", "higher item level", "other base"],
)
def test_an_item_of_another_base_or_item_level_is_refused(item):
    with pytest.raises(ValueError):
        abstraction().compress(item)


def test_is_goal_asks_the_goal_about_the_status_of_the_state():
    ab = abstraction()

    assert ab.is_goal(ab.compress(small_item(roll(RESIST_2, fractured=True), roll(GEM))))
    assert not ab.is_goal(ab.compress(fractured_item(RESIST_2)))
    assert not ab.is_goal(ab.compress(fractured_item(FIRE_GEM)))


def test_is_goal_does_not_count_a_mod_below_the_asked_tier():
    ab = abstraction("tier")

    assert not ab.is_goal(ab.compress(small_item(roll(RESIST_1, fractured=True), roll(GEM))))
    assert ab.is_goal(ab.compress(small_item(roll(RESIST_2, fractured=True), roll(GEM))))


def test_the_family_types_of_the_pool_group_families_of_the_same_shape():
    types = abstraction().family_types()

    groups = sorted(types.values())
    assert sum(len(group) for group in groups) == FAMILIES
    assert ("ColdResistance", "FireResistance") in groups
    assert len(types) == FAMILIES - 1
    assert all(group == tuple(sorted(group)) for group in groups)
    assert {key[0] for key in types} == {"prefix", "suffix"}


def test_a_guaranteed_tag_is_part_of_the_family_type():
    ab = abstraction()
    plain, tagged = ab.family_types(), ab.family_types("lightning")

    assert sorted(plain.values()) == sorted(tagged.values())
    assert plain.keys() != tagged.keys()


def test_two_families_of_one_shape_are_two_types_once_the_goal_tells_their_mods_apart():
    # The goal now wants Cold Resistance, so its mod has another label than the Fire one.
    goal = Goal((Wanted(frozenset({COLD_RESIST})),))

    groups = sorted(abstraction(goal).family_types().values())

    assert ("ColdResistance", "FireResistance") not in groups
    assert ("ColdResistance",) in groups and ("FireResistance",) in groups
