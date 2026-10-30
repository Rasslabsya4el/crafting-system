"""The sampler draws finished items by the same process the exact engine counts."""

import math
import random
from functools import cache

import pytest
from actions_support import DATA, RESIST, TARGET, amulet, fractured_resist

from crafting_system.actions import ChaosOrb, HarvestReforge
from crafting_system.items import Rarity, Side, tier_table

DRAWS = 10_000
SEED = 20261030
LIGHTNING = "lightning"


def _cases():
    plain, kept = amulet(), amulet(fractured_resist())
    return [
        pytest.param(action, item, id=f"{type(action).__name__}-{'kept' if item.mods else 'plain'}")
        for action in (ChaosOrb(), HarvestReforge(LIGHTNING))
        for item in (plain, kept)
    ]


CASES = _cases()


@cache
def samples(action, item, count=DRAWS, seed=SEED):
    """The outcomes and `count` sampled items; cached so that the tests of one case share one run."""
    outcomes = action.outcomes(DATA, item)
    rng = random.Random(seed)
    return outcomes, [outcomes.sample(rng) for _ in range(count)]


@pytest.mark.parametrize(("action", "item"), CASES)
def test_the_frequency_of_the_target_agrees_with_the_exact_chance(action, item):
    outcomes, items = samples(action, item)

    chance = float(outcomes.chance_all([TARGET]))
    seen = sum(any(m.mod_id == TARGET for m in drawn.mods) for drawn in items) / len(items)
    sigma = math.sqrt(chance * (1 - chance) / len(items))

    assert abs(seen - chance) < 5 * sigma


@pytest.mark.parametrize(("action", "item"), CASES)
def test_the_number_of_mods_follows_the_exact_distribution(action, item):
    outcomes, items = samples(action, item)
    exact = {}
    for outcome, chance in outcomes.distribution(lambda mod: "mod").items():
        number = len(item.fractured_mods) + sum(count for _, count in outcome)
        exact[number] = exact.get(number, 0) + float(chance)

    for number, chance in exact.items():
        seen = sum(len(drawn.mods) == number for drawn in items) / len(items)
        assert abs(seen - chance) < 5 * math.sqrt(chance * (1 - chance) / len(items))
    assert {len(drawn.mods) for drawn in items} <= set(exact)


def test_the_same_seed_gives_the_same_items():
    first = samples(ChaosOrb(), amulet(), count=200, seed=7)[1]
    second = samples(ChaosOrb(), amulet(), count=200, seed=7)[1]
    other = samples(ChaosOrb(), amulet(), count=200, seed=8)[1]

    assert first == second
    assert first != other


@pytest.mark.parametrize(("action", "item"), CASES)
def test_every_sampled_item_is_valid_and_keeps_the_fractured_mod(action, item):
    outcomes, items = samples(action, item, count=2_000)
    tiers = tier_table(DATA, item.base_id)

    for drawn in items:
        drawn.validate(DATA)
        assert drawn.rarity is Rarity.RARE and drawn.item_level == item.item_level
        assert set(item.fractured_mods) <= set(drawn.mods)
        assert all(drawn.free_slots(DATA, side) >= 0 for side in Side)
        families = [family for m in drawn.mods for family in DATA.mods[m.mod_id].families]
        assert len(families) == len(set(families))
        assert 4 <= len(drawn.mods) <= 6
        for entry in drawn.mods:
            if entry in item.fractured_mods:
                continue
            assert entry.tier == tiers[entry.mod_id]
            assert not entry.fractured and not entry.crafted
            for value, stat in zip(entry.values, DATA.mods[entry.mod_id].stats, strict=True):
                assert min(stat.min, stat.max) <= value <= max(stat.min, stat.max)


def test_a_reforge_always_holds_a_lightning_mod():
    _, items = samples(HarvestReforge(LIGHTNING), amulet(), count=2_000)

    assert all(any(LIGHTNING in DATA.mods[m.mod_id].implicit_tags for m in drawn.mods) for drawn in items)


def test_a_reforge_with_a_kept_resistance_holds_another_lightning_mod():
    _, items = samples(HarvestReforge(LIGHTNING), amulet(fractured_resist()), count=2_000)

    for drawn in items:
        others = [m for m in drawn.mods if m.mod_id != RESIST]
        assert any(LIGHTNING in DATA.mods[m.mod_id].implicit_tags for m in others)


def test_values_roll_over_the_whole_range():
    outcomes = ChaosOrb().outcomes(DATA, amulet())
    rng = random.Random(SEED)
    seen = set()
    for _ in range(3_000):
        for entry in outcomes.sample(rng).mods:
            if entry.mod_id == "IncreasedLife1":
                seen.add(entry.values[0])

    assert seen == set(range(10, 25))


def test_a_dry_pool_gives_fewer_mods():
    outcomes = ChaosOrb().outcomes(DATA, amulet(item_level=1))
    rng = random.Random(SEED)

    assert {len(outcomes.sample(rng).mods) for _ in range(50)} == {3}
