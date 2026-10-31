"""Verification layer 1 for the Harvest reforges beyond Lightning: the kernel of `abstraction` against the brute force (ticket #72).

For every craft, the influence reforge and both likelihood reforges the kernel of the compressed start must equal the
brute force of `abstraction_oracle.py`: every finished item with its exact probability, compressed one by one and added up.
The data and the starts are those of `harvest_reforge_support.py`. The kernels are the generic ones: no tag is named in
`abstraction`, so each craft with its own set of tagged mods checks that.
"""

import pytest
from abstraction_oracle import assert_same_distribution, compressed_distribution, finished_items
from abstraction_pool import (
    COLD_RESIST,
    DAMAGE_1,
    FIRE_RESIST,
    GEM,
    LEVEL,
    LIFE_1,
    MANA_1,
    MANA_2,
    RESIST_1,
    RESIST_2,
    RESIST_3,
    SMALL,
    roll,
    small_item,
)
from harvest_reforge_support import (
    ATTACK_SPEED,
    BOW,
    HAND_TAG,
    HUNTER,
    LIKELIHOOD_STARTS,
    STARTS,
    TABLE,
    TAGGED_DATA,
    bow,
    held_weighted_pool,
    hunter_marked_pool,
    start_of,
)
from fractions import Fraction
from items_support import AMULET, DATA
from items_support import roll as fixture_roll

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import HarvestReforge, HarvestReforgeInfluence, HarvestReforgeLikelihood

TAGGED_GOALS = {
    "r12": Goal((Wanted(frozenset({GEM})), Wanted(frozenset({RESIST_1, RESIST_2, RESIST_3})))),
    "mana_and_fire": Goal((Wanted(frozenset({MANA_1, MANA_2})), Wanted(frozenset({FIRE_RESIST, COLD_RESIST})))),
}


@pytest.mark.parametrize("goal", TAGGED_GOALS)
@pytest.mark.parametrize("start", STARTS)
@pytest.mark.parametrize("craft", TABLE)
def test_a_tagged_craft_kernel_equals_the_brute_force(craft, start, goal):
    ab = Abstraction(TAGGED_DATA, TAGGED_GOALS[goal], AMULET, LEVEL)
    item_ = start_of(start)

    kernel = ab.kernel(ab.compress(item_), HarvestReforge(craft))

    expected = compressed_distribution(finished_items(TAGGED_DATA, item_, TABLE[craft][0]), ab.compress)
    assert_same_distribution(kernel, expected)


def test_two_crafts_with_different_tagged_mods_have_different_kernels():
    ab = Abstraction(TAGGED_DATA, TAGGED_GOALS["mana_and_fire"], AMULET, LEVEL)
    state = ab.compress(start_of("plain"))
    assert ab.kernel(state, HarvestReforge("speed")) != ab.kernel(state, HarvestReforge("fire"))


HUNTER_GOALS = {
    "chaos_hybrid": Goal((Wanted(frozenset({f"LocalAddedChaosDamageAndPenetrationInfluence{n}" for n in range(1, 6)})),)),
    "suffix_and_prefix": Goal(
        (
            Wanted(frozenset({"ArmourPenetrationTwoHandWeaponInfluence1_", "ArmourPenetrationTwoHandWeaponInfluence2_"})),
            Wanted(frozenset({"AddedColdDamagePerDexterityInfluence1"})),
        )
    ),
}


@pytest.mark.parametrize("goal", HUNTER_GOALS)
@pytest.mark.parametrize("fractured", [(), (ATTACK_SPEED,)], ids=["empty", "fractured"])
def test_the_influence_reforge_kernel_equals_the_brute_force(fractured, goal):
    ab = Abstraction(DATA, HUNTER_GOALS[goal], BOW, 78)
    start = bow(*(fixture_roll(mod_id, fractured=True) for mod_id in fractured))

    kernel = ab.kernel(ab.compress(start), HarvestReforgeInfluence())

    expected = compressed_distribution(
        finished_items(DATA, start, HAND_TAG, pool=hunter_marked_pool(DATA, start)), ab.compress
    )
    assert_same_distribution(kernel, expected)
    assert start.influences == HUNTER


LIKELIHOOD_GOALS = {
    "r12": TAGGED_GOALS["r12"],
    "life": Goal((Wanted(frozenset({LIFE_1})), Wanted(frozenset({DAMAGE_1, GEM})))),
}


@pytest.mark.parametrize("goal", LIKELIHOOD_GOALS)
@pytest.mark.parametrize("more", [True, False], ids=["more", "less"])
@pytest.mark.parametrize("start", LIKELIHOOD_STARTS)
def test_a_likelihood_reforge_kernel_equals_the_brute_force(start, more, goal):
    action = HarvestReforgeLikelihood(more)
    ab = Abstraction(SMALL, LIKELIHOOD_GOALS[goal], AMULET, LEVEL, [action])
    item_ = LIKELIHOOD_STARTS[start]()
    factor = Fraction(90) if more else Fraction(1, 90)
    totals = {max(len(item_.mods), 4): Fraction(1)}

    kernel = ab.kernel(ab.compress(item_), action)

    expected = compressed_distribution(
        finished_items(SMALL, item_, None, pool=held_weighted_pool(SMALL, item_, factor), totals=totals), ab.compress
    )
    assert_same_distribution(kernel, expected)


def test_a_likelihood_reforge_is_not_a_block_invariant_action():
    """The junk a likelihood reforge reads decides its pool, so it cannot be declared invariant to pooling (ADR-0023)."""
    assert HarvestReforgeLikelihood(True).reads(SMALL).block_invariant is False
    assert HarvestReforgeLikelihood(True).reads(SMALL).junk is True


def test_junk_families_of_one_type_share_one_cached_distribution():
    """Cold and Fire Resistance have the same side and weights and give the goal nothing: held, they weigh the pool alike."""
    action = HarvestReforgeLikelihood(True)
    ab = Abstraction(SMALL, LIKELIHOOD_GOALS["r12"], AMULET, LEVEL, [action])
    cold, fire = (ab.compress(small_item(roll(mod_id))) for mod_id in (COLD_RESIST, FIRE_RESIST))

    assert ab.signature(cold, action) == ab.signature(fire, action)
    assert ab.signature(cold, action) != ab.signature(ab.compress(small_item(roll(MANA_1))), action)
