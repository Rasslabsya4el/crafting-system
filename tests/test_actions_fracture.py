"""The Fracturing Orb against its own exact oracle, and what it refuses (ticket #67).

The contract suite does not compare a fracturing action with the brute force, so the oracle is here:
a rare item with n mods fractures each mod with chance 1/n (D6 of issue #28), changes nothing else,
and the item then holds exactly one fractured mod. R04's published odds: a 4-mod quiver fractures the
wanted mod with chance 25% (reference routes, "There is a 25% chance of success").
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from actions_support import DATA, amulet, fractured_resist, roll

from crafting_system.actions import (
    AnnulmentOrb,
    ChaosOrb,
    Fractured,
    FracturingOrb,
    NotApplicableError,
    catalog,
    kinds,
)
from crafting_system.items import Influence, Rarity

MODS = ("IncreasedLife1", "IncreasedEnergyShield1", "AddedLightningDamage1", "FireResist1", "ColdResist1", "ManaLeechPermyriadSuffix1")
CRAFTED = "DexMasterItemGenerationCannotChangeSuffixes"


def rare(count: int, **fields):
    return dataclasses.replace(amulet(*(roll(mod_id) for mod_id in MODS[:count])), **fields)


def oracle(item):
    """Every finished item with its chance, written by hand: one result per mod, that mod flagged fractured."""
    count = len(item.mods)
    return {
        tuple(dataclasses.replace(mod, fractured=mod.mod_id == chosen.mod_id) for mod in item.mods): Fraction(1, count)
        for chosen in item.mods
    }


def results(outcomes):
    return {result.mods: chance for chance, result in outcomes.results}


@pytest.mark.parametrize("count", [4, 5, 6])
def test_the_outcomes_equal_the_hand_oracle(count):
    item = rare(count)

    assert results(FracturingOrb().outcomes(DATA, item)) == oracle(item)


@pytest.mark.parametrize(("count", "chance"), [(4, Fraction(1, 4)), (5, Fraction(1, 5)), (6, Fraction(1, 6))])
def test_each_mod_is_fractured_with_the_chance_one_over_the_number_of_mods(count, chance):
    item = rare(count)
    outcomes = FracturingOrb().outcomes(DATA, item)

    for mod in item.mods:
        fractured = sum(c for c, result in outcomes.results if any(e.mod_id == mod.mod_id and e.fractured for e in result.mods))
        assert fractured == chance


def test_r04_a_four_mod_item_fractures_the_wanted_mod_with_chance_twenty_five_percent():
    outcomes = FracturingOrb().outcomes(DATA, rare(4))
    wanted = "IncreasedLife1"
    fractured = sum(c for c, result in outcomes.results if any(e.mod_id == wanted and e.fractured for e in result.mods))

    assert fractured == Fraction(25, 100)
    # through the distribution, with the label of the mod: the fractured label of the wanted mod
    shown = outcomes.distribution(lambda mod: "wanted" if mod.id == wanted else "other")
    assert shown[frozenset({(Fractured("wanted"), 1)})] == Fraction(1, 4)
    assert shown[frozenset({(Fractured("other"), 1)})] == Fraction(3, 4)
    assert sum(shown.values()) == 1


def test_exactly_one_mod_is_fractured_and_nothing_else_changes():
    item = rare(5)
    outcomes = FracturingOrb().outcomes(DATA, item)

    for _, result in outcomes.results:
        assert len(result.fractured_mods) == 1
        assert [(e.mod_id, e.tier, e.values, e.crafted) for e in result.mods] == [(e.mod_id, e.tier, e.values, e.crafted) for e in item.mods]
        assert (result.rarity, result.influences, result.corrupted, result.item_level) == (item.rarity, item.influences, item.corrupted, item.item_level)


def test_chance_all_is_one_for_the_mods_on_the_item_and_zero_for_the_rest():
    outcomes = FracturingOrb().outcomes(DATA, rare(4))

    assert outcomes.chance_all(MODS[:4]) == 1
    assert outcomes.chance_all([MODS[4]]) == 0
    assert outcomes.chance_all(["LightningResist1", "LightningResist2"]) == 0


def test_the_outcomes_declare_that_they_fracture_and_have_fixed_components():
    outcomes = FracturingOrb().outcomes(DATA, rare(4))

    assert outcomes.fractures is True
    assert sum(share for share, _ in outcomes.components) == 1 and len(outcomes.components) == 4


def test_the_sampler_fractures_each_mod_with_its_chance():
    item = rare(4)
    outcomes = FracturingOrb().outcomes(DATA, item)
    rng, runs, hits = random.Random(13), 4000, {}
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        drawn.validate(DATA)
        (only,) = drawn.fractured_mods
        hits[only.mod_id] = hits.get(only.mod_id, 0) + 1

    assert set(hits) == {entry.mod_id for entry in item.mods}
    assert all(abs(count / runs - 0.25) < 5 * (0.25 * 0.75 / runs) ** 0.5 for count in hits.values())


def test_the_fractured_mod_stays_through_an_annulment_and_a_chaos_orb():
    [(_, fractured)] = [(c, r) for c, r in FracturingOrb().outcomes(DATA, rare(4)).results][:1]
    [kept] = fractured.fractured_mods

    for _, result in AnnulmentOrb().outcomes(DATA, fractured).results:
        assert kept in result.mods
    assert ChaosOrb().outcomes(DATA, fractured).retained.fractured_mods == (kept,)


@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.MAGIC])
def test_an_item_that_is_not_rare_is_refused_by_the_game(rarity):
    item = amulet(*(roll(mod_id) for mod_id in MODS[:1]), rarity=rarity) if rarity is Rarity.MAGIC else amulet(rarity=rarity)

    with pytest.raises(NotApplicableError, match="rare item only"):
        FracturingOrb().outcomes(DATA, item)


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_a_rare_item_with_fewer_than_four_mods_is_refused(count):
    with pytest.raises(NotApplicableError, match=rf"at least 4 mods.*has {count}"):
        FracturingOrb().outcomes(DATA, rare(count))


def test_a_corrupted_item_is_refused():
    with pytest.raises(NotApplicableError, match="corrupted.*Fracturing Orb"):
        FracturingOrb().outcomes(DATA, rare(4, corrupted=True))


def test_an_influenced_item_is_refused():
    with pytest.raises(NotApplicableError, match="influenced"):
        FracturingOrb().outcomes(DATA, rare(4, influences=frozenset({Influence.SHAPER})))


def test_an_item_that_already_has_a_fractured_mod_is_refused():
    item = amulet(fractured_resist(), roll(MODS[0]), roll(MODS[1]), roll(MODS[2]))

    with pytest.raises(NotApplicableError, match="already has a fractured mod"):
        FracturingOrb().outcomes(DATA, item)


def test_the_refusals_come_in_order_rarity_corruption_influence_count():
    item = dataclasses.replace(rare(2), corrupted=True, influences=frozenset({Influence.SHAPER}))
    with pytest.raises(NotApplicableError, match="corrupted"):
        FracturingOrb().outcomes(DATA, item)
    with pytest.raises(NotApplicableError, match="influenced"):
        FracturingOrb().outcomes(DATA, rare(2, influences=frozenset({Influence.SHAPER})))


@pytest.mark.parametrize("crafted_id", ["JunMaster2AllDamage2_", CRAFTED])
def test_a_crafted_mod_and_a_metamod_are_candidates_like_the_rest(crafted_id):
    item = amulet(roll(MODS[0]), roll(MODS[3]), roll(MODS[4]), roll(crafted_id, crafted=True))

    outcomes = FracturingOrb().outcomes(DATA, item)

    assert len(outcomes.results) == 4 and {chance for chance, _ in outcomes.results} == {Fraction(1, 4)}
    fractured = {result.fractured_mods[0].mod_id: result for _, result in outcomes.results}
    assert crafted_id in fractured and fractured[crafted_id].fractured_mods[0].crafted
    assert outcomes.chance_all([crafted_id]) == 1  # it stays on the item, fractured


def test_the_orb_is_named_priced_and_declared():
    action = FracturingOrb()
    reads, adds = action.reads(DATA), action.adds(DATA, rare(4))

    assert action.label(DATA) == "Fracturing Orb"
    assert action.resources(DATA) == {"Fracturing Orb": 1}
    assert reads.junk and reads.block_invariant is False
    assert not adds.draws and adds.keeps_crafted and adds.named is None


def test_the_kind_lists_rare_items_and_is_not_a_planner_kind():
    assert FracturingOrb() in catalog(DATA, rare(4))
    assert FracturingOrb() not in catalog(DATA, amulet(roll(MODS[0]), rarity=Rarity.MAGIC))
    assert FracturingOrb() not in catalog(DATA, rare(4), planner_only=True)
    assert {entry.name: entry.planner for entry in kinds()}["fracturing-orb"] is False
