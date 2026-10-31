"""Layer 1 for the magic-item orbs on the real Leather Belt of 3.29.3.3, and the state count of route R13 (ticket #65).

The belt pool at item level 86 has 90-odd mods in 19 families, so an orb that draws one or two mods
is compared with the brute force of `abstraction_adds_oracle.py` on the whole pool, in exact fractions.
The Alchemy draws 4 to 6 mods, too many for the brute force on the whole pool, so it is compared on a
subset of the real families (a few mods each, the real weights and levels).

The goal is the one of the R13 target (`examples/targets/r13-life-resist-belt.yaml`): T1 life, two
of three T1 resistances, a crafted damage modifier. The state count and the kernel cache figures of
the route (Transmutation, Alteration, Augmentation, Regal on a normal belt) are pinned below.

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there; CI fetches it (ticket #165), so they run there.
"""

import dataclasses

import pytest
from abstraction_adds_oracle import altered, augmented, regaled, scoured, transmuted
from abstraction_oracle import assert_same_distribution, compressed_distribution, finished_items
from abstraction_support import real_game_data
from targets_support import EXAMPLES

from crafting_system.abstraction import Abstraction, CacheStats, Goal
from crafting_system.actions import (
    AlchemyOrb,
    AlterationOrb,
    AugmentationOrb,
    RegalOrb,
    ScouringOrb,
    TransmutationOrb,
    build_pool,
)
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table
from crafting_system.targets import load_target

BELT = "Metadata/Items/Belts/Belt3"
LEVEL = 86
LIFE, FIRE, COLD, LIGHTNING = "IncreasedLife9", "FireResist8", "ColdResist8", "LightningResist8"
ROUTE = (TransmutationOrb(), AlterationOrb(), AugmentationOrb(), RegalOrb())
ALL = (*ROUTE, AlchemyOrb(), ScouringOrb())

R13_STATES = 1507  # reachable from a normal Leather Belt by the four orbs of the route
R13_CACHE = CacheStats(kernels=117, hits=184)


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.fixture(scope="module")
def goal(real):
    return Goal.from_target(load_target(EXAMPLES / "r13-life-resist-belt.yaml", real))


def belt(data, *mods, rarity=Rarity.MAGIC):
    tiers = tier_table(data, BELT)
    rolled = tuple(
        ExplicitMod(
            mod_id, tiers[mod_id], tuple(min(s.min, s.max) for s in data.mods[mod_id].stats),
            fractured=fractured,
        )
        for mod_id, fractured in mods
    )  # fmt: skip
    return Item.build(data, base_id=BELT, item_level=LEVEL, rarity=rarity, mods=rolled)


def check(ab, start, action, finished):
    kernel = ab.kernel(ab.compress(start), action)
    assert_same_distribution(kernel, compressed_distribution(finished, ab.compress))
    return kernel


def test_the_target_goal_asks_for_the_tier_one_mods(goal):
    assert len(goal.leaves) == 6


@pytest.mark.parametrize(
    "mods",
    [
        pytest.param((), id="no_mod"),
        pytest.param(((LIFE, False),), id="t1_life"),
        pytest.param(((FIRE, False),), id="t1_resistance"),
        pytest.param(((LIFE, False), (LIGHTNING, False)), id="life_and_resistance"),
        pytest.param(((COLD, True),), id="fractured_resistance"),
        pytest.param(((LIFE, True), (FIRE, False)), id="fractured_life_and_junk"),
    ],
)
def test_the_magic_orbs_equal_the_brute_force_on_the_real_belt(real, goal, mods):
    ab = Abstraction(real, goal, BELT, LEVEL, ROUTE)
    start = belt(real, *mods)

    check(ab, start, AlterationOrb(), altered(real, start))
    check(ab, start, RegalOrb(), regaled(real, start))
    if len(mods) < 2:
        check(ab, start, AugmentationOrb(), augmented(real, start))


def test_transmutation_equals_the_brute_force_on_the_real_belt(real, goal):
    ab = Abstraction(real, goal, BELT, LEVEL, ROUTE)
    start = belt(real, rarity=Rarity.NORMAL)

    check(ab, start, TransmutationOrb(), transmuted(real, start))


@pytest.mark.parametrize("rarity", [Rarity.MAGIC, Rarity.RARE])
def test_scouring_equals_the_brute_force_on_the_real_belt(real, goal, rarity):
    ab = Abstraction(real, goal, BELT, LEVEL, ALL)
    start = belt(real, (LIFE, False), (COLD, True), rarity=rarity)

    check(ab, start, ScouringOrb(), scoured(real, start))


def test_alchemy_equals_the_brute_force_on_a_subset_of_the_real_belt(real):
    families = {"IncreasedLife", "FireResistance", "ColdResistance", "LightningResistance", "LifeRegeneration", "IncreasedEnergyShield"}
    pool = build_pool(real, Item.build(real, base_id=BELT, item_level=LEVEL, rarity=Rarity.RARE))
    keep = {
        entry.mod.id for family in pool if family.family in families for entry in sorted(family.mods, key=lambda e: e.mod.id)[:3]
    }  # fmt: skip
    small = dataclasses.replace(real, mods={mod_id: mod for mod_id, mod in real.mods.items() if mod_id in keep})
    leaves = Goal.from_target(load_target(EXAMPLES / "r13-life-resist-belt.yaml", real)).leaves[:1]
    ab = Abstraction(small, Goal(leaves), BELT, LEVEL, ALL)
    start = Item.build(small, base_id=BELT, item_level=LEVEL, rarity=Rarity.NORMAL)

    kernel = ab.kernel(ab.compress(start), AlchemyOrb())

    assert_same_distribution(kernel, compressed_distribution(finished_items(small, start), ab.compress))


def test_the_route_r13_reachable_state_count_and_cache_figures(real, goal):
    ab = Abstraction(real, goal, BELT, LEVEL, ROUTE)
    start = ab.compress(Item.build(real, base_id=BELT, item_level=LEVEL, rarity=Rarity.NORMAL))

    states = ab.reachable([start], ROUTE)

    assert len(states) == R13_STATES and ab.stats == R13_CACHE
