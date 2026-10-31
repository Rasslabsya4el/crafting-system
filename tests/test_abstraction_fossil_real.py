"""Verification layer 1 for the fossil reforges on the real 3.29.3.3 boots (ticket #62).

The real pool has about 65 families, too many for the brute force, so each case keeps seven families
of the real boots pool (three mods each, the real weights, levels and tags) and the mods the case
needs, with the real fossil records. The kernel is compared with `abstraction_fossil.fossil_finished`
in exact fractions: single fossils, a summed pair, blocks, the forced mod of the Hollow Fossil, the
Fractured Fossil and the Tangled Fossil.

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, which is the case in CI.
"""

import pytest
from abstraction_fossil import fossil_finished
from abstraction_oracle import assert_same_distribution, compressed_distribution
from abstraction_support import PASSING, real_game_data
from test_abstraction_b1_real import LEVEL, rolled, subset

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import ApplyFossils
from crafting_system.items import Item, Rarity

BASE = "Metadata/Items/Armours/Boots/BootsInt1"  # Sorcerer Boots
FAMILIES = {"IncreasedLife", "MovementVelocity", "IncreasedMana", "Intelligence", "FireResistance", "StunRecovery", "ColdResistance"}
FORCED = "DelveAbyssJewelSocket1"  # the suffix that the Hollow Fossil forces
FRACTURED = "StunRecovery1"


@pytest.fixture(scope="module")
def world():
    data = subset(real_game_data(), BASE, FAMILIES, {FORCED, FRACTURED})
    life = Wanted(frozenset(mod.id for mod in data.mods.values() if mod.families == ("IncreasedLife",)))
    speed = Wanted(frozenset(mod.id for mod in data.mods.values() if mod.families == ("MovementVelocity",)))
    fire = Wanted(frozenset(mod.id for mod in data.mods.values() if mod.families == ("FireResistance",)))
    return data, Abstraction(data, Goal((life, speed, fire)), BASE, LEVEL)


def rare(data, *mods):
    return Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=mods)


def fossils(*names):
    return ApplyFossils(tuple(f"{name} Fossil" for name in names))


SETS = {
    "single-boost-and-block": ("Scorched",),  # fire x10, cold blocked
    "single-block-of-a-family": ("Shuddering",),  # speed x10, the mana family blocked
    "single-boost": ("Pristine",),  # life x10, defences blocked (no such mod in the subset)
    "summed-pair": ("Scorched", "Prismatic"),  # fire resistance: fire x10 + elemental x6
    "opposing-blocks": ("Shuddering", "Lucent"),  # speed and mana blocked, each by the other
    "a-pair-of-different-tags": ("Pristine", "Shuddering"),
    "forced": ("Hollow", "Scorched"),
    "fractured": ("Fractured", "Shuddering"),
    "fractured-and-forced": ("Fractured", "Hollow"),
    "tangled": ("Tangled", "Scorched"),
}


@pytest.mark.parametrize("name", SETS)
def test_the_real_kernel_equals_the_brute_force(world, name):
    data, ab = world
    action = fossils(*SETS[name])
    item = rare(data)

    kernel = ab.kernel(ab.compress(item), action)

    assert_same_distribution(kernel, compressed_distribution(fossil_finished(data, action, item), ab.compress))


def test_the_real_kernel_equals_the_brute_force_beside_a_fractured_mod(world):
    data, ab = world
    action = fossils("Scorched", "Prismatic")
    item = rare(data, rolled(data, FRACTURED, fractured=True), rolled(data, "IncreasedMana1"))

    kernel = ab.kernel(ab.compress(item), action)

    assert_same_distribution(kernel, compressed_distribution(fossil_finished(data, action, item), ab.compress))
    assert all(state.fractured for state in kernel)


def test_a_boost_changes_the_chance_of_the_wanted_mod(world):
    data, ab = world
    state = ab.compress(rare(data))

    plain = ab.kernel(state, fossils("Gilded"))
    boosted = ab.kernel(state, fossils("Scorched"))

    def fire(kernel):
        return sum(chance for s, chance in kernel.items() if s.status[2] is PASSING)

    assert fire(boosted) > fire(plain)
