"""The kernel cache keyed by pool signature, `integer_weights` and `reachable` (ticket #24).

The signature says what decides the distribution of the labels of the new mods; two states with equal
signatures share one computation. These tests count the computations (`stats.kernels`) and the reuses
(`stats.hits`) and check that a reused result is still the exact one: equal to the brute force of
`abstraction_oracle` once the junk family has been renamed.
"""

import dataclasses
import itertools
import math
from collections import defaultdict
from fractions import Fraction

import pytest
from abstraction_oracle import assert_same_distribution
from abstraction_pool import (
    COLD_RESIST,
    CRAFTED,
    DAMAGE_1,
    FIRE_GEM,
    FIRE_RESIST,
    GEM,
    LIFE_1,
    MANA_1,
    POOL_IDS,
    RESIST_1,
    RESIST_2,
    fractured_item,
    roll,
    small_item,
)
from abstraction_support import (
    ABSENT,
    BELOW,
    CHAOS,
    PASSING,
    REFORGE,
    abstraction,
    check_kernel,
    expected_kernel,
    with_fractured,
)

from crafting_system.abstraction import CompressedState, Flags, integer_weights
from crafting_system.actions import ActionError
from crafting_system.items import Rarity

FLAGS = Flags(Rarity.RARE, False, frozenset())


def projection(kernel):
    """A kernel as {status: probability}: for one start state the status tells the next states apart."""
    return {state.status: chance for state, chance in kernel.items()}


def test_a_new_abstraction_has_computed_nothing():
    ab = abstraction()

    assert (ab.stats.kernels, ab.stats.hits) == (0, 0)


@pytest.mark.parametrize("action", [CHAOS, REFORGE])
def test_two_states_that_differ_only_in_the_fractured_junk_family_share_one_computation(action):
    ab = abstraction()
    cold, fire = ab.compress(fractured_item(COLD_RESIST)), ab.compress(fractured_item(FIRE_RESIST))

    first = ab.kernel(cold, action)
    second = ab.kernel(fire, action)

    assert (ab.stats.kernels, ab.stats.hits) == (1, 1)
    assert ab.signature(cold, action) == ab.signature(fire, action)
    assert cold != fire
    assert {with_fractured(state, fire): chance for state, chance in first.items()} == dict(second)
    assert_same_distribution(second, expected_kernel(ab, fractured_item(FIRE_RESIST), action))
    assert_same_distribution(first, expected_kernel(ab, fractured_item(COLD_RESIST), action))


def test_junk_families_of_a_different_shape_have_different_signatures_and_computations():
    ab = abstraction()
    cold = ab.compress(fractured_item(COLD_RESIST))
    mana = ab.compress(fractured_item(MANA_1))
    life = ab.compress(fractured_item(LIFE_1))

    ab.kernel(cold, CHAOS)
    ab.kernel(mana, CHAOS)
    ab.kernel(life, CHAOS)

    assert len({ab.signature(state, CHAOS) for state in (cold, mana, life)}) == 3
    assert (ab.stats.kernels, ab.stats.hits) == (3, 0)


def test_a_chaos_orb_and_a_reforge_on_one_state_have_different_signatures():
    ab = abstraction()
    state = ab.compress(fractured_item(RESIST_2))

    chaos, reforge = ab.kernel(state, CHAOS), ab.kernel(state, REFORGE)

    assert ab.signature(state, CHAOS) != ab.signature(state, REFORGE)
    assert (ab.stats.kernels, ab.stats.hits) == (2, 0)
    assert chaos != reforge


def test_a_request_made_twice_is_computed_once_and_answers_the_same():
    ab = abstraction()
    state = ab.compress(fractured_item(RESIST_2))

    first = ab.kernel(state, CHAOS)
    second = ab.kernel(state, CHAOS)

    assert dict(first) == dict(second)
    assert ab.stats.kernels == 1 and ab.stats.hits >= 1


def test_states_that_differ_only_in_the_status_of_the_whole_item_share_one_computation():
    ab = abstraction()
    clean = ab.compress(fractured_item(RESIST_2))
    dirty = ab.compress(small_item(roll(RESIST_2, fractured=True), roll(GEM), roll(LIFE_1)))

    first, second = ab.kernel(clean, CHAOS), ab.kernel(dirty, CHAOS)

    assert clean.status != dirty.status and clean.fractured == dirty.fractured
    assert dict(first) == dict(second)
    assert (ab.stats.kernels, ab.stats.hits) == (1, 1)


def test_states_with_equal_signatures_have_the_same_kernel_up_to_the_status_they_lead_to():
    # Every single fractured mod of the pool, under both actions: whenever two share a signature,
    # their kernels give the same probabilities; only the status a fractured mod itself gives (a
    # fractured Lightning gem level against a fractured Cold one) tells the next states apart.
    ab = abstraction()
    mod_ids = sorted(POOL_IDS - {CRAFTED})
    groups = defaultdict(list)
    for mod_id in mod_ids:
        state = ab.compress(fractured_item(mod_id))
        for action in (CHAOS, REFORGE):
            groups[ab.signature(state, action)].append(sorted(ab.kernel(state, action).values()))

    assert any(len(group) > 1 for group in groups.values())
    for group in groups.values():
        assert all(shown == group[0] for shown in group)


def test_the_cache_counts_one_computation_per_signature_over_a_whole_closure():
    ab = abstraction()
    start = ab.compress(fractured_item())

    reached = ab.reachable([start], [CHAOS, REFORGE])

    assert len(reached) == 4
    assert ab.stats.kernels == 2 and ab.stats.hits > 0


def test_integer_weights_of_a_hand_made_kernel():
    a, b, c = (CompressedState(FLAGS, (), (status,)) for status in (ABSENT, BELOW, PASSING))

    assert integer_weights({a: Fraction(1, 2), b: Fraction(1, 3), c: Fraction(1, 6)}) == {a: 3, b: 2, c: 1}
    assert integer_weights({a: Fraction(1, 2), b: Fraction(1, 2)}) == {a: 1, b: 1}
    assert integer_weights({a: Fraction(1)}) == {a: 1}
    assert integer_weights({a: Fraction(1, 6), b: Fraction(5, 6)}) == {a: 1, b: 5}
    assert integer_weights({a: Fraction(1, 4), b: Fraction(1, 4), c: Fraction(1, 2)}) == {a: 1, b: 1, c: 2}
    assert integer_weights({a: Fraction(1, 10), b: Fraction(1, 15), c: Fraction(5, 6)}) == {a: 3, b: 2, c: 25}


@pytest.mark.parametrize("action", [CHAOS, REFORGE])
def test_integer_weights_of_a_real_kernel_are_in_proportion_and_in_lowest_terms(action):
    ab = abstraction()
    kernel = ab.kernel(ab.compress(fractured_item(RESIST_2)), action)

    weights = integer_weights(kernel)

    total = sum(weights.values())
    assert weights.keys() == kernel.keys()
    assert all(type(weight) is int and weight > 0 for weight in weights.values())
    assert math.gcd(*weights.values()) == 1
    assert all(Fraction(weight, total) == kernel[state] for state, weight in weights.items())
    assert total == math.lcm(*(chance.denominator for chance in kernel.values()))


def test_reachable_from_the_r12_start_is_the_start_and_the_state_with_the_gem_mod():
    ab = abstraction()
    start = ab.compress(fractured_item(RESIST_2))

    reached = ab.reachable([start], [CHAOS, REFORGE])

    assert isinstance(reached, frozenset)
    assert reached == {start, dataclasses.replace(start, status=(PASSING, PASSING))}
    assert start.status == (ABSENT, PASSING)


def test_reachable_from_a_plain_amulet_holds_the_four_status_pairs():
    ab = abstraction()
    start = ab.compress(fractured_item())

    reached = ab.reachable([start], [CHAOS, REFORGE])

    assert {state.status for state in reached} == {
        (ABSENT, ABSENT),
        (PASSING, ABSENT),
        (ABSENT, PASSING),
        (PASSING, PASSING),
    }
    assert start in reached and len(reached) == 4


def test_reachable_with_one_action_and_with_several_starts():
    ab = abstraction()
    plain, resist = ab.compress(fractured_item()), ab.compress(fractured_item(RESIST_2))

    assert len(ab.reachable([plain], [CHAOS])) == 4
    assert len(ab.reachable([resist], [REFORGE])) == 2
    assert ab.reachable([plain, resist], [CHAOS]) == ab.reachable([plain], [CHAOS]) | ab.reachable([resist], [CHAOS])
    assert ab.reachable([plain], []) == {plain}
    assert ab.reachable([], [CHAOS]) == frozenset()


def test_reachable_skips_an_action_that_the_state_refuses():
    ab = abstraction()
    blocked = ab.compress(fractured_item(GEM, DAMAGE_1, RESIST_1))

    assert ab.reachable([blocked], [REFORGE]) == {blocked}
    assert ab.reachable([blocked], [REFORGE, CHAOS]) == {blocked}
    other_gem = ab.compress(fractured_item(FIRE_GEM, RESIST_2))
    assert {state.status for state in ab.reachable([other_gem], [REFORGE, CHAOS])} == {(ABSENT, PASSING)}


def test_reachable_skips_an_action_that_is_out_of_scope_for_the_state():
    ab = abstraction()
    crafted = ab.compress(small_item(roll(CRAFTED, crafted=True)))

    assert ab.reachable([crafted], [CHAOS, REFORGE]) == {crafted}
    corrupted = ab.compress(dataclasses.replace(fractured_item(RESIST_2), corrupted=True))
    assert ab.reachable([corrupted], [CHAOS]) == {corrupted}



@pytest.mark.parametrize("action", [CHAOS, REFORGE])
def test_a_fractured_mod_outside_the_pool_still_changes_the_signature(action):
    # At item level 12 the fire gem-level family cannot be drawn, so removing it leaves the pool as
    # it was; only the kept mod and the free prefix slot tell this state from a plain one.
    ab = abstraction(level=12)
    plain = ab.compress(small_item(roll(RESIST_1, fractured=True), level=12))
    blocked = ab.compress(small_item(roll(RESIST_1, fractured=True), roll(FIRE_GEM, fractured=True), level=12))

    assert ab.signature(plain, action) != ab.signature(blocked, action)
    check_kernel(ab, small_item(roll(RESIST_1, fractured=True), level=12), action)
    check_kernel(ab, small_item(roll(RESIST_1, fractured=True), roll(FIRE_GEM, fractured=True), level=12), action)
    assert ab.stats.kernels == 2


def test_a_state_of_another_goal_is_refused():
    state = abstraction("nested").compress(fractured_item(RESIST_1))

    with pytest.raises(ValueError, match="another abstraction"):
        abstraction("any").kernel(state, CHAOS)


def test_an_out_of_pool_fractured_prefix_and_suffix_differ_in_the_signature():
    # At item level 12 neither the fire gem-level family (a prefix) nor the mana leech family (a
    # suffix) can be drawn, so both states have the same pool, the same kept count and the same
    # total of free slots; only which side has room tells them apart.
    ab = abstraction(level=12)
    prefix = fractured_item(FIRE_GEM, level=12)
    suffix = fractured_item(MANA_1, level=12)

    for action in (CHAOS, REFORGE):
        assert ab.signature(ab.compress(prefix), action) != ab.signature(ab.compress(suffix), action)
        check_kernel(ab, prefix, action)
        check_kernel(ab, suffix, action)
    assert ab.stats.kernels == 4


@pytest.mark.parametrize("level", [12, 84])
def test_one_cache_serves_every_fractured_combination_of_the_pool_exactly(level):
    # One abstraction, so every request after the first may be answered from the cache: a signature
    # that merged two pools or two slot counts would hand one of these states a wrong kernel.
    ab = abstraction(level=level)
    one_per_family = [GEM, FIRE_GEM, DAMAGE_1, LIFE_1, RESIST_1, COLD_RESIST, FIRE_RESIST, MANA_1]
    combinations = [(mod_id,) for mod_id in one_per_family]
    combinations += [
        pair for pair in itertools.combinations(one_per_family, 2) if not {GEM, FIRE_GEM} <= set(pair)
    ]
    asked = 0
    for mod_ids in combinations:
        item = fractured_item(*mod_ids, level=level)
        for action in (CHAOS, REFORGE):
            try:
                check_kernel(ab, item, action)
            except ActionError:
                continue
            asked += 1
    assert asked > 40
    assert ab.stats.hits > 0
