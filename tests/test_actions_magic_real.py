"""The per-click chances of route R13 (T1 life, double-resist belt by Alteration and Regal), on the real 3.29.3.3 dump (ticket #64).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, which is the case in CI.

The route (reference routes, R13): Alteration until the magic belt holds T1 Life and a T1 resistance,
then a Regal Orb for a second T1 resistance. The base is the Leather Belt (the belt of the other
tests; every belt base has the same mod pool). The route gives no item level, and T1 resistance
needs level 84, so both 84 and 86 are pinned (at 85 and 86 more belt mods open up). "T1" is the
best tier of the family on the belt (`tier_table`): Life 9, Fire, Cold and Lightning Resistance 8.
Chaos Resistance is not counted as a resistance of the route.

* Alteration: the chance that the new magic belt holds T1 Life and one named T1 elemental
  resistance in one click; the chance of any of the three is three times it (a magic belt holds one suffix).
* Regal Orb: on a magic belt with T1 Life and T1 Lightning Resistance, the chance that the new mod
  is the T1 Fire or the T1 Cold Resistance (either: twice the chance of one).

The pins are exact fractions that the engine gave. The independent check is the hand formula in
`test_the_pins_equal_the_hand_formula`, written from the pool weights: an Alteration with a total of
2 draws the two mods in either order, the second from the other side only; a Regal Orb draws one
mod from the whole pool without the two families on the item.
"""

import random
from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import AlterationOrb, RegalOrb, build_pool
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table

BELT = "Metadata/Items/Belts/Belt3"
LIFE, FIRE, COLD, LIGHTNING = "IncreasedLife9", "FireResist8", "ColdResist8", "LightningResist8"
FAMILIES = ("IncreasedLife", "FireResistance", "ColdResistance", "LightningResistance")

ALTERATION = {84: Fraction(1, 6600), 86: Fraction(10, 69077)}  # T1 Life and one named T1 resistance
REGAL = {84: Fraction(1, 98), 86: Fraction(20, 2011)}  # a named second T1 resistance


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def belt(data, rarity, *mod_ids, level):
    tiers = tier_table(data, BELT)
    return Item.build(
        data, base_id=BELT, item_level=level, rarity=rarity,
        mods=tuple(
            ExplicitMod(mod_id, tiers[mod_id], tuple(min(s.min, s.max) for s in data.mods[mod_id].stats))
            for mod_id in mod_ids
        ),
    )  # fmt: skip


@pytest.mark.parametrize("level", sorted(ALTERATION))
@pytest.mark.parametrize("resist", [FIRE, COLD, LIGHTNING])
def test_alteration_chance_of_t1_life_and_a_t1_resistance_is_pinned(data, level, resist):
    outcomes = AlterationOrb().outcomes(data, belt(data, Rarity.MAGIC, LIFE, level=level))

    assert outcomes.chance_all([LIFE, resist]) == ALTERATION[level]


@pytest.mark.parametrize("level", sorted(ALTERATION))
def test_alteration_chance_of_any_t1_elemental_resistance_is_three_times_one(data, level):
    outcomes = AlterationOrb().outcomes(data, belt(data, Rarity.MAGIC, LIFE, level=level))
    label = lambda mod: "life" if mod.id == LIFE else "t1" if mod.id in (FIRE, COLD, LIGHTNING) else None  # noqa: E731
    both = outcomes.distribution(label)[frozenset({("life", 1), ("t1", 1)})]

    assert both == 3 * ALTERATION[level]


@pytest.mark.parametrize("level", sorted(REGAL))
@pytest.mark.parametrize("resist", [FIRE, COLD])
def test_regal_chance_of_the_second_t1_resistance_is_pinned(data, level, resist):
    outcomes = RegalOrb().outcomes(data, belt(data, Rarity.MAGIC, LIFE, LIGHTNING, level=level))

    assert outcomes.chance_all([LIFE, LIGHTNING, resist]) == REGAL[level]


@pytest.mark.parametrize("level", sorted(REGAL))
def test_regal_chance_of_either_other_t1_resistance_is_twice_one(data, level):
    outcomes = RegalOrb().outcomes(data, belt(data, Rarity.MAGIC, LIFE, LIGHTNING, level=level))
    either = outcomes.distribution(lambda mod: "t1" if mod.id in (FIRE, COLD) else None)

    assert either[frozenset({("t1", 1)})] == 2 * REGAL[level]


@pytest.mark.parametrize("level", sorted(ALTERATION))
def test_the_pins_equal_the_hand_formula(data, level):
    pool = build_pool(data, belt(data, Rarity.MAGIC, level=level))
    family = {entry.family: entry.weight for entry in pool}
    weight = {item.mod.id: item.weight for entry in pool for item in entry.mods}
    prefixes = sum(entry.weight for entry in pool if entry.side.value == "prefix")
    total = sum(family.values())
    suffixes = total - prefixes

    alteration = Fraction(1, 2) * (
        weight[LIFE] / total * weight[FIRE] / suffixes + weight[FIRE] / total * weight[LIFE] / prefixes
    )
    regal = weight[FIRE] / (total - family["IncreasedLife"] - family["LightningResistance"])

    assert (alteration, regal) == (ALTERATION[level], REGAL[level])


def test_the_sampler_agrees_with_the_regal_pin(data):
    outcomes = RegalOrb().outcomes(data, belt(data, Rarity.MAGIC, LIFE, LIGHTNING, level=84))
    chance = float(REGAL[84])
    rng, runs, hits = random.Random(3), 10000, 0
    for _ in range(runs):
        hits += any(entry.mod_id == FIRE for entry in outcomes.sample(rng).mods)

    assert abs(hits / runs - chance) < 5 * (chance * (1 - chance) / runs) ** 0.5
