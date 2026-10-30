"""The kernel on the fixture amulet, the real shape (14 families) at item levels 80, 84 and 86 (ticket #24, layer 1).

A concrete enumeration is out of reach here, so the chance of the gem-level leaf is compared with two
other ways to get it: `Outcomes.chance_all` of the actions, and the hand oracle `actions_oracle.py`
that walks the draw orders by hand. All three must be equal as exact fractions, with and without the
fractured Lightning Resistance.
"""

import pytest
from abstraction_support import ABSENT, CHAOS, PASSING, REFORGE, passing_chance
from actions_oracle import chaos_chance, harvest_chance
from actions_support import AMULET, DATA, RESIST, TARGET, amulet, fractured_resist

from crafting_system.abstraction import Abstraction, Goal, Wanted

RESISTS = frozenset(f"LightningResist{number}" for number in range(1, 9))
GOAL = Goal((Wanted(frozenset({TARGET})), Wanted(RESISTS)))
LEVELS = (80, 84, 86)
HAND = {CHAOS: chaos_chance, REFORGE: harvest_chance}


def fixture_abstraction(level):
    return Abstraction(DATA, GOAL, AMULET, level)


@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
@pytest.mark.parametrize("level", LEVELS)
def test_the_gem_leaf_chance_of_a_plain_amulet_equals_chance_all_and_the_hand_oracle(level, action):
    ab = fixture_abstraction(level)
    item = amulet(item_level=level)

    kernel = ab.kernel(ab.compress(item), action)

    assert sum(kernel.values()) == 1
    assert passing_chance(kernel, 0) == action.outcomes(DATA, item).chance_all([TARGET])
    assert passing_chance(kernel, 0) == HAND[action](level)


@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
@pytest.mark.parametrize("level", LEVELS)
def test_the_gem_leaf_chance_with_a_fractured_resist_equals_chance_all_and_the_hand_oracle(level, action):
    ab = fixture_abstraction(level)
    item = amulet(fractured_resist(), item_level=level)

    kernel = ab.kernel(ab.compress(item), action)

    assert sum(kernel.values()) == 1
    assert passing_chance(kernel, 0) == action.outcomes(DATA, item).chance_all([TARGET])
    assert passing_chance(kernel, 0) == HAND[action](level, ("LightningResistance",))
    assert passing_chance(kernel, 1) == 1
    assert {state.status for state in kernel} == {(ABSENT, PASSING), (PASSING, PASSING)}


@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
def test_the_resist_leaf_and_both_leaves_together_equal_chance_all_of_each_mod(action):
    # The eight tiers of the resist are disjoint, so the chances add up; the pair holds the gem mod too.
    ab = fixture_abstraction(86)
    item = amulet()
    outcomes = action.outcomes(DATA, item)

    kernel = ab.kernel(ab.compress(item), action)

    both = sum(chance for state, chance in kernel.items() if state.status == (PASSING, PASSING))
    assert passing_chance(kernel, 1) == sum(outcomes.chance_all([mod_id]) for mod_id in sorted(RESISTS))
    assert both == sum(outcomes.chance_all([TARGET, mod_id]) for mod_id in sorted(RESISTS))


def test_the_amulet_pool_has_the_real_shape():
    types = fixture_abstraction(86).family_types()

    assert sum(len(group) for group in types.values()) == 14
    assert any({"ColdResistance", "FireResistance"} <= set(group) for group in types.values())


def test_the_chance_does_not_depend_on_which_tier_of_the_resist_is_fractured():
    ab = fixture_abstraction(86)
    states = {ab.compress(amulet(fractured_resist(f"LightningResist{number}"))) for number in range(1, 9)}

    assert len(states) == 1
    assert ab.compress(amulet(fractured_resist(RESIST))) in states
