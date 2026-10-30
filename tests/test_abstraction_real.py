"""The R12 target on the real 3.29.3.3 dump: two compressed states, and a kernel equal to `chance_all` (ticket #24).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, which is the case in CI.
"""

import math
from fractions import Fraction

import pytest
from abstraction_support import ABSENT, CHAOS, PASSING, REFORGE, passing_chance, real_game_data
from targets_support import EXAMPLES

from crafting_system.abstraction import Abstraction, Goal, integer_weights
from crafting_system.targets import load_target

GEM = "GlobalLightningGemLevel1"


@pytest.fixture(scope="module")
def r12():
    data = real_game_data()
    target = load_target(EXAMPLES / "r12-lightning-amulet.yaml", data)
    goal = Goal.from_target(target)
    return data, target, goal, Abstraction(data, goal, target.base_id, target.item_level)


def test_the_goal_of_the_r12_target_has_the_gem_leaf_and_the_resist_leaf(r12):
    _, target, goal, _ = r12

    assert [leaf.mod_ids for leaf in goal.requirements] == [node.mod_ids for node in target.requirements]
    assert GEM in goal.requirements[0].mod_ids and len(goal.requirements) == 2


def test_the_start_item_compresses_to_the_fractured_resist_and_no_gem_mod(r12):
    _, target, _, ab = r12

    start = ab.compress(target.start_item)

    assert len(start.fractured) == 1 and start.status == (ABSENT, PASSING)
    assert not ab.is_goal(start)


def test_the_r12_target_has_exactly_two_compressed_states(r12):
    _, target, _, ab = r12
    start = ab.compress(target.start_item)

    reached = ab.reachable([start], [CHAOS, REFORGE])

    assert len(reached) == 2
    assert {state.status for state in reached} == {(ABSENT, PASSING), (PASSING, PASSING)}
    assert sum(ab.is_goal(state) for state in reached) == 1


@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
def test_the_gem_leaf_chance_of_the_kernel_equals_chance_all_on_the_real_pool(r12, action):
    data, target, goal, ab = r12
    outcomes = action.outcomes(data, target.start_item)

    kernel = ab.kernel(ab.compress(target.start_item), action)

    assert sum(kernel.values()) == 1
    assert passing_chance(kernel, 0) == outcomes.chance_all([GEM])
    assert passing_chance(kernel, 1) == 1
    # The other mod of the leaf is the influenced one, which an uninfluenced amulet cannot draw.
    assert all(outcomes.chance_all([mod_id]) == 0 for mod_id in goal.requirements[0].mod_ids - {GEM})


@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
def test_the_integer_weights_of_the_real_kernel_keep_its_proportions(r12, action):
    _, target, _, ab = r12
    kernel = ab.kernel(ab.compress(target.start_item), action)

    weights = integer_weights(kernel)

    assert math.gcd(*weights.values()) == 1
    assert all(Fraction(weight, sum(weights.values())) == kernel[state] for state, weight in weights.items())


def test_the_real_pool_has_fewer_family_types_than_families(r12):
    *_, ab = r12

    types = ab.family_types("lightning")

    assert sum(len(group) for group in types.values()) > len(types) > 1
