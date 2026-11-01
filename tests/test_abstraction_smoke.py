"""Quick checks of `abstraction` on the fixture amulet, for development (the oracle tests are separate)."""

from fractions import Fraction

import pytest
from actions_support import AMULET, DATA, RESIST, TARGET, amulet, fractured_resist, roll

from crafting_system.abstraction import (
    Abstraction,
    AtLeast,
    Goal,
    Status,
    Wanted,
    integer_weights,
)
from crafting_system.actions import ChaosOrb, HarvestReforge, NotApplicableError, OutOfScopeError
from crafting_system.items import Rarity

LIGHTNING_RESISTANCE = frozenset(
    mod.id for mod in DATA.mods.values() if "LightningResistance" in mod.families
)
GOAL = Goal((Wanted(frozenset({TARGET})), Wanted(LIGHTNING_RESISTANCE)))
ACTIONS = (ChaosOrb(), HarvestReforge("lightning"))


@pytest.fixture(scope="module")
def abstraction():
    return Abstraction(DATA, GOAL, AMULET, 86)


@pytest.mark.parametrize("action", ACTIONS)
def test_kernel_sums_to_one_and_gem_leaf_matches_chance_all(abstraction, action):
    item = amulet(fractured_resist())
    state = abstraction.compress(item)
    kernel = abstraction.kernel(state, action)

    assert sum(kernel.values()) == 1
    assert all(chance > 0 for chance in kernel.values())
    gem = sum(
        (chance for next_state, chance in kernel.items() if next_state.status[0] is Status.PASSING),
        Fraction(0),
    )
    assert gem == action.outcomes(DATA, item).chance_all([TARGET])


def test_r12_start_reaches_two_states(abstraction):
    state = abstraction.compress(amulet(fractured_resist()))

    assert state.status == (Status.ABSENT, Status.PASSING)
    assert len(abstraction.reachable([state], ACTIONS)) == 2


def test_compress_merges_tiers_and_sorts_fractured(abstraction):
    one = abstraction.compress(amulet(roll("LightningResist1", fractured=True)))
    five = abstraction.compress(amulet(roll("LightningResist5", fractured=True)))

    assert one == five
    assert abstraction.compress(amulet(roll("LightningResist5"))).fractured == ()


def test_compress_rejects_another_level(abstraction):
    with pytest.raises(ValueError):
        abstraction.compress(amulet(item_level=84))


def test_junk_of_equal_shape_shares_one_computation():
    shared = Abstraction(DATA, GOAL, AMULET, 86)
    cold = shared.compress(amulet(roll("ColdResist1", fractured=True)))
    fire = shared.compress(amulet(roll("FireResist1", fractured=True)))

    assert shared.signature(cold, ChaosOrb()) == shared.signature(fire, ChaosOrb())
    shared.kernel(cold, ChaosOrb())
    shared.kernel(fire, ChaosOrb())
    assert (shared.stats.kernels, shared.stats.hits) == (1, 1)
    assert shared.signature(cold, ChaosOrb()) != shared.signature(cold, HarvestReforge("lightning"))


def test_integer_weights_are_proportional_and_reduced(abstraction):
    kernel = abstraction.kernel(abstraction.compress(amulet(fractured_resist())), ChaosOrb())
    weights = integer_weights(kernel)
    total = sum(weights.values())

    assert {state: Fraction(weight, total) for state, weight in weights.items()} == dict(kernel)


def test_refusals_come_from_the_action(abstraction):
    with pytest.raises(NotApplicableError):
        abstraction.kernel(abstraction.compress(amulet(rarity=Rarity.MAGIC)), ChaosOrb())
    with pytest.raises(OutOfScopeError):
        abstraction.kernel(abstraction.compress(amulet(roll("DexMasterItemGenerationCannotChangeSuffixes", crafted=True))), ChaosOrb())


def test_at_least_goal_and_roll_limit_on_drawn_mod():
    goal = Goal((AtLeast(1, (Wanted(frozenset({TARGET})), Wanted(LIGHTNING_RESISTANCE))),))
    assert goal.is_met((Status.ABSENT, Status.PASSING))
    assert not goal.is_met((Status.BELOW, Status.ABSENT))

    limited = Abstraction(DATA, Goal((Wanted(frozenset({RESIST}), min_roll=(5,)),)), AMULET, 86)
    assert sum(limited.kernel(limited.compress(amulet()), ChaosOrb()).values()) == 1  # a drawn mod rolls its values (#71)


def test_family_types_group_the_pool(abstraction):
    types = abstraction.family_types()

    assert sum(len(names) for names in types.values()) == 14
