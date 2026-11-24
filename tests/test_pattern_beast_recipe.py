"""The beast recipe "Add a Mod to a <influence> Item" reads as an Exalted Orb does (#1571, H54 of #1434).

Since #1538 the recipe draws one mod of the item's whole pool, less the families held, exactly as an Exalted Orb draws it, and keeps every mod.
So the pure junk on the item matters to it only by the pool weight it takes out, and its member policy is `EXTREMES` (`abstraction._pattern`,
module docstring: one draw by pool weight), where it was `ALL` (every family told apart): on R14's fourth group 520,707 kernels against 9,123.

On the fixture bow of `test_abstraction_pattern` (attack prefixes of four weights, suffixes of three) with the Hunter influence, every member
of every key a seeded walk meets is compared by brute force (`Mode.ALL`): the recipe refuses where the Exalted Orb refuses and otherwise gives
the same kernel through the key, and the members its policy offers are at least as good as every member for random successor values.
"""

import dataclasses
import random

import pytest
from pattern_support import all_members, check_dominates, pushed
from test_abstraction_pattern import BOW, GOAL, LEVEL, STARTS, build, pattern_data

from crafting_system.abstraction import Abstraction
from crafting_system.abstraction._pattern import Mode, Pattern
from crafting_system.actions import ActionError, AnnulmentOrb, ChaosOrb, ExaltedOrb
from crafting_system.actions.influence import BeastInfluenceRecipe
from crafting_system.items import Influence

HUNTER = frozenset({Influence.HUNTER})
RECIPE = BeastInfluenceRecipe(Influence.HUNTER)
ACTIONS = (RECIPE, ExaltedOrb(), AnnulmentOrb(), ChaosOrb())


@pytest.fixture(scope="module")
def world():
    data = pattern_data()
    ab = Abstraction(data, GOAL, BOW, LEVEL, ACTIONS, metamods=True)
    starts = [ab.compress(build(data, BOW, ids, influences=HUNTER)) for ids in STARTS]
    rng = random.Random(1571)
    states: dict = {}
    for start in starts:
        for _ in range(40):
            state = start
            for _ in range(8):
                states[state] = None
                try:
                    kernel = ab.kernel(state, rng.choice(ACTIONS))
                except ActionError:
                    continue
                state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    pattern = Pattern(ab, True, list(ACTIONS))
    return data, ab, pattern, list(dict.fromkeys(map(pattern.key, states)))


def test_the_recipe_reads_as_the_exalted_orb(world):
    data, *_ = world
    assert RECIPE.reads(data) == ExaltedOrb().reads(data)


def test_the_recipe_is_extremes_at_every_key(world):
    _, _, pattern, keys = world
    assert keys
    assert {pattern.mode_of(RECIPE, key) for key in keys} == {Mode.EXTREMES}


def test_the_recipe_has_the_exalted_orbs_outcomes_on_a_hunter_rare(world):
    """Field by field (`Outcomes` compares by identity): the same item kept, the same pool, the same chances of each count of mods."""
    data, *_ = world
    for ids in STARTS:
        item = build(data, BOW, ids, influences=HUNTER)
        recipe, orb = RECIPE.outcomes(data, item), ExaltedOrb().outcomes(data, item)
        for field in dataclasses.fields(recipe):
            assert getattr(recipe, field.name) == getattr(orb, field.name), (ids, field.name)


def test_at_every_member_the_recipe_gives_the_exalted_orbs_kernel(world):
    """Brute force over every member of every key (`Mode.ALL`): 0 members where the recipe and the Exalted Orb differ through the key."""
    _, ab, pattern, keys = world
    members = legal = 0
    mismatches = []
    for key in keys:
        for member in all_members(pattern, key):
            recipe, orb = pushed(pattern, ab, member, RECIPE), pushed(pattern, ab, member, ExaltedOrb())
            members += 1
            legal += recipe is not None
            if recipe != orb:
                mismatches.append(member)
    assert mismatches == []
    assert members > 500 and legal > 500


def test_the_members_extremes_offers_are_as_good_as_every_member(world):
    """The soundness of `EXTREMES` for the recipe against the `ALL` reading, at every key with a choice of pure junk."""
    _, ab, pattern, keys = world
    choosy = [key for key in keys if len(all_members(pattern, key)) > len(pattern.members(key, Mode.EXTREMES))]
    assert choosy
    rng = random.Random(1571)
    offered = 0
    for key in choosy:
        offered += check_dominates(pattern, ab, key, RECIPE, Mode.EXTREMES, rng, trials=12)[1]
    assert offered
