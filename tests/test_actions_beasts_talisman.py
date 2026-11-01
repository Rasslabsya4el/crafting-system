"""The Talisman fracture beasts against their exact hand oracle, and what they refuse (ticket #147).

The recipe fractures one mod (a rare Talisman with 4 or more mods) or two mods (6 or more), uniformly among all
explicit mods and among all pairs of distinct mods (`beastcraft.talisman_fracture_uniform`, approximate: the
choice of grill B2 as for the Fracturing Orb). The fixture holds no Talisman base, so `beasts_support` copies the
amulet base with the tag `talisman`.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from abstraction_pool import COLD_RESIST, DAMAGE_1, FIRE_GEM, LIFE_1, MANA_1, RESIST_2
from beasts_support import (
    AMULET,
    BEAST_DATA,
    CRAFTED,
    DATA,
    FIRE,
    LEVEL,
    LIFE,
    METAMOD,
    SIX_MODS,
    TALISMAN,
    contract_beast_data,
    contract_item,
    rare,
    roll,
)
from contract_support import check_action
from repoe_support import no_network  # noqa: F401

from crafting_system.actions import Fractured, NotApplicableError, catalog, kinds
from crafting_system.actions.beasts import TalismanFracture, TalismanFractureOutcomes
from crafting_system.items import ExplicitMod, Influence, Item, ItemError, Rarity

# the six mods in the order an item stores them (sorted by id), as the hand oracle lists them
ORDER = ("AddedLightningDamage1", "ColdResist1", "FireResist1", "IncreasedEnergyShield1", "IncreasedLife1", "ManaLeechPermyriadSuffix1")
PAIRS = [  # all 15 pairs of the six positions, written out
    (0, 1), (0, 2), (0, 3), (0, 4), (0, 5),
    (1, 2), (1, 3), (1, 4), (1, 5),
    (2, 3), (2, 4), (2, 5),
    (3, 4), (3, 5),
    (4, 5),
]  # fmt: skip


def talisman(count: int, **fields) -> Item:
    return rare(TALISMAN, SIX_MODS[:count], **fields)


def finished(item: Item, *fractured: int) -> tuple[ExplicitMod, ...]:
    """The mods of `item` with those positions flagged fractured."""
    return tuple(dataclasses.replace(mod, fractured=position in fractured) for position, mod in enumerate(item.mods))


def results(outcomes) -> dict:
    return {result.mods: chance for chance, result in outcomes.results}


def fractured_chance(outcomes, mod_ids) -> Fraction:
    """The chance that every one of `mod_ids` ends fractured."""
    return sum(
        (chance for chance, result in outcomes.results if {e.mod_id for e in result.mods if e.fractured} >= set(mod_ids)),
        Fraction(0),
    )


# --- one mod ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("count", [4, 5, 6])
def test_one_fracture_equals_the_hand_oracle(count):
    item = talisman(count)
    expected = {finished(item, position): Fraction(1, count) for position in range(count)}

    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, item)

    assert isinstance(outcomes, TalismanFractureOutcomes)
    assert results(outcomes) == expected
    assert len(outcomes.results) == count


def test_the_hand_oracle_of_four_mods_lists_each_mod_with_chance_one_quarter():
    item = talisman(4)

    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, item)

    # the item stores its mods sorted by id: damage, fire resistance, energy shield, life
    assert [(c, [e.mod_id for e in r.mods if e.fractured]) for c, r in outcomes.results] == [
        (Fraction(1, 4), ["AddedLightningDamage1"]),
        (Fraction(1, 4), ["FireResist1"]),
        (Fraction(1, 4), ["IncreasedEnergyShield1"]),
        (Fraction(1, 4), ["IncreasedLife1"]),
    ]


@pytest.mark.parametrize("count", [4, 5, 6])
def test_chance_all_of_one_and_of_two_mods_is_one_for_mods_on_the_item_and_zero_for_the_rest(count):
    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, talisman(count))

    assert outcomes.chance_all([LIFE]) == 1
    assert outcomes.chance_all([LIFE, FIRE]) == 1
    assert outcomes.chance_all(SIX_MODS[:count]) == 1
    assert outcomes.chance_all(["LightningResist1"]) == 0
    assert outcomes.chance_all([LIFE, "LightningResist1"]) == 0
    assert outcomes.chance_all([]) == 1
    with pytest.raises(ValueError, match="NoSuchMod is not in the game data"):
        outcomes.chance_all(["NoSuchMod"])


@pytest.mark.parametrize(("count", "chance"), [(4, Fraction(1, 4)), (5, Fraction(1, 5)), (6, Fraction(1, 6))])
def test_each_mod_is_fractured_with_chance_one_over_the_number_of_mods(count, chance):
    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, talisman(count))

    for mod_id in SIX_MODS[:count]:
        assert fractured_chance(outcomes, [mod_id]) == chance
    assert fractured_chance(outcomes, [LIFE, FIRE]) == 0  # one mod only


def test_the_distribution_shows_the_one_fractured_mod_seen_through_the_label():
    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, talisman(6))

    assert dict(outcomes.distribution(lambda mod: mod.generation_type)) == {
        frozenset({(Fractured("prefix"), 1)}): Fraction(1, 2),
        frozenset({(Fractured("suffix"), 1)}): Fraction(1, 2),
    }
    by_id = outcomes.distribution(lambda mod: mod.id)
    assert by_id == {frozenset({(Fractured(mod_id), 1)}): Fraction(1, 6) for mod_id in SIX_MODS}
    assert sum(by_id.values()) == 1


def test_one_fracture_declares_that_it_fractures_and_its_components_are_fixed_results():
    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, talisman(5))

    assert outcomes.fractures is True
    assert [share for share, _ in outcomes.components] == [Fraction(1, 5)] * 5
    assert {part.result for _, part in outcomes.components} == {result for _, result in outcomes.results}


def test_the_sampler_fractures_each_mod_with_its_chance():
    item = talisman(4)
    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, item)
    rng, runs, hits = random.Random(147), 4000, {}
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        drawn.validate(BEAST_DATA)
        (only,) = drawn.fractured_mods
        hits[only.mod_id] = hits.get(only.mod_id, 0) + 1

    assert set(hits) == {entry.mod_id for entry in item.mods}
    assert all(abs(count / runs - 0.25) < 5 * (0.25 * 0.75 / runs) ** 0.5 for count in hits.values())


def test_the_seeded_sample_is_the_same_each_time_and_one_of_the_results():
    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, talisman(5))

    first = outcomes.sample(random.Random(5))
    assert first == outcomes.sample(random.Random(5))
    assert first.mods in results(outcomes)


def test_nothing_but_the_flag_changes():
    item = talisman(5)

    for _, result in TalismanFracture(1).outcomes(BEAST_DATA, item).results:
        assert [(e.mod_id, e.tier, e.values, e.crafted) for e in result.mods] == [(e.mod_id, e.tier, e.values, e.crafted) for e in item.mods]
        assert (result.base_id, result.rarity, result.influences, result.corrupted, result.item_level) == (
            item.base_id, item.rarity, item.influences, item.corrupted, item.item_level
        )  # fmt: skip


# --- two mods --------------------------------------------------------------------------------------


def test_two_fractures_of_six_mods_equal_the_hand_oracle_of_fifteen_pairs():
    item = talisman(6)
    assert tuple(mod.mod_id for mod in item.mods) == ORDER
    expected = {finished(item, first, second): Fraction(1, 15) for first, second in PAIRS}

    outcomes = TalismanFracture(2).outcomes(BEAST_DATA, item)

    assert len(outcomes.results) == 15 and len(expected) == 15
    assert results(outcomes) == expected
    assert outcomes.fractures is True


def test_two_fractures_fracture_a_given_mod_with_chance_one_third_and_a_given_pair_with_one_fifteenth():
    outcomes = TalismanFracture(2).outcomes(BEAST_DATA, talisman(6))

    for mod_id in SIX_MODS:
        assert fractured_chance(outcomes, [mod_id]) == Fraction(5, 15)
    assert fractured_chance(outcomes, [LIFE, FIRE]) == Fraction(1, 15)
    assert fractured_chance(outcomes, SIX_MODS[:3]) == 0  # a third mod never joins the pair


def test_two_fractures_chance_all_is_one_for_the_mods_on_the_item():
    outcomes = TalismanFracture(2).outcomes(BEAST_DATA, talisman(6))

    assert outcomes.chance_all([LIFE]) == 1
    assert outcomes.chance_all([LIFE, FIRE]) == 1
    assert outcomes.chance_all(["LightningResist1"]) == 0


def test_two_fractures_distribution_adds_the_counts_of_a_shared_label():
    outcomes = TalismanFracture(2).outcomes(BEAST_DATA, talisman(6))  # three prefixes, three suffixes

    shown = outcomes.distribution(lambda mod: mod.generation_type)

    assert dict(shown) == {
        frozenset({(Fractured("prefix"), 2)}): Fraction(3, 15),
        frozenset({(Fractured("suffix"), 2)}): Fraction(3, 15),
        frozenset({(Fractured("prefix"), 1), (Fractured("suffix"), 1)}): Fraction(9, 15),
    }
    by_id = outcomes.distribution(lambda mod: mod.id)
    assert len(by_id) == 15 and set(by_id.values()) == {Fraction(1, 15)}
    assert frozenset({(Fractured(LIFE), 1), (Fractured(FIRE), 1)}) in by_id
    assert dict(outcomes.distribution(lambda mod: "any")) == {frozenset({(Fractured("any"), 2)}): Fraction(1)}


def test_two_fractures_hold_exactly_two_fractured_mods_in_every_sample():
    item = talisman(6)
    outcomes = TalismanFracture(2).outcomes(BEAST_DATA, item)
    rng, runs, pairs = random.Random(2147), 3000, {}
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        drawn.validate(BEAST_DATA)
        pair = frozenset(entry.mod_id for entry in drawn.fractured_mods)
        assert len(pair) == 2
        pairs[pair] = pairs.get(pair, 0) + 1

    assert len(pairs) == 15
    assert all(abs(count / runs - 1 / 15) < 5 * ((1 / 15) * (14 / 15) / runs) ** 0.5 for count in pairs.values())
    assert outcomes.sample(random.Random(3)) == outcomes.sample(random.Random(3))


# --- refusals --------------------------------------------------------------------------------------


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.MAGIC])
def test_an_item_that_is_not_rare_is_refused(count, rarity):
    item = rare(TALISMAN, (LIFE,), rarity=rarity) if rarity is Rarity.MAGIC else rare(TALISMAN, (), rarity=rarity)

    with pytest.raises(NotApplicableError, match="rare item only"):
        TalismanFracture(count).outcomes(BEAST_DATA, item)


@pytest.mark.parametrize("count", [1, 2])
def test_a_corrupted_item_is_refused(count):
    with pytest.raises(NotApplicableError, match="corrupted"):
        TalismanFracture(count).outcomes(BEAST_DATA, talisman(6, corrupted=True))


@pytest.mark.parametrize("count", [1, 2])
def test_an_influenced_item_is_refused(count):
    with pytest.raises(NotApplicableError, match="influenced"):
        TalismanFracture(count).outcomes(BEAST_DATA, talisman(6, influences=frozenset({Influence.SHAPER})))


@pytest.mark.parametrize("count", [1, 2])
def test_an_item_with_a_fractured_mod_is_refused(count):
    item = rare(TALISMAN, (), extra=(roll(LIFE, fractured=True), *(roll(mod_id) for mod_id in SIX_MODS[1:])))

    with pytest.raises(NotApplicableError, match="already has a fractured mod"):
        TalismanFracture(count).outcomes(BEAST_DATA, item)


@pytest.mark.parametrize("count", [1, 2])
def test_an_item_on_a_base_that_is_not_a_talisman_is_refused(count):
    amulet = rare(AMULET, SIX_MODS, data=DATA)

    with pytest.raises(NotApplicableError, match="not a Talisman base"):
        TalismanFracture(count).outcomes(BEAST_DATA, amulet)
    with pytest.raises(NotApplicableError, match="not a Talisman base"):
        TalismanFracture(count).outcomes(DATA, amulet)


@pytest.mark.parametrize("have", [0, 1, 2, 3])
def test_one_fracture_needs_four_mods(have):
    with pytest.raises(NotApplicableError, match=rf"at least 4 mods.*has {have}"):
        TalismanFracture(1).outcomes(BEAST_DATA, talisman(have))


@pytest.mark.parametrize("have", [0, 1, 2, 3, 4, 5])
def test_two_fractures_need_six_mods(have):
    with pytest.raises(NotApplicableError, match=rf"at least 6 mods.*has {have}"):
        TalismanFracture(2).outcomes(BEAST_DATA, talisman(have))


def test_four_mods_take_the_single_fracture_and_not_the_double_one():
    item = talisman(4)

    assert TalismanFracture(1).outcomes(BEAST_DATA, item).chance_all(SIX_MODS[:4]) == 1
    with pytest.raises(NotApplicableError):
        TalismanFracture(2).outcomes(BEAST_DATA, item)


def test_the_refusals_come_in_order_rarity_corruption_influence_base_count():
    item = dataclasses.replace(rare(AMULET, (LIFE,), data=DATA), corrupted=True, influences=frozenset({Influence.SHAPER}))
    with pytest.raises(NotApplicableError, match="corrupted"):
        TalismanFracture(1).outcomes(BEAST_DATA, item)
    with pytest.raises(NotApplicableError, match="influenced"):
        TalismanFracture(1).outcomes(BEAST_DATA, dataclasses.replace(item, corrupted=False))
    with pytest.raises(NotApplicableError, match="not a Talisman base"):
        TalismanFracture(1).outcomes(BEAST_DATA, dataclasses.replace(item, corrupted=False, influences=frozenset()))


def test_a_count_other_than_one_or_two_is_a_value_error():
    for count in (0, 3, -1):
        with pytest.raises(ValueError, match="one or two"):
            TalismanFracture(count)


# --- crafted mods and metamods count (claim talisman_fracture_uniform) ---------------------------------


def item_refuses_a_fractured_crafted_mod() -> bool:
    """True until ticket #68 lets `Item` hold a mod that is both fractured and crafted."""
    try:
        Item(base_id=TALISMAN, item_level=LEVEL, rarity=Rarity.RARE, mods=(ExplicitMod(CRAFTED, 1, (12,), fractured=True, crafted=True),))
    except ItemError:
        return True
    return False


needs_fractured_crafted_mods = pytest.mark.skipif(
    item_refuses_a_fractured_crafted_mod(), reason="Item still refuses a fractured crafted mod (ticket #68, PR #164)"
)


@needs_fractured_crafted_mods
@pytest.mark.parametrize("crafted_id", [CRAFTED, METAMOD])
def test_a_crafted_mod_or_metamod_counts_toward_the_minimum_and_is_one_of_the_choices(crafted_id):
    item = rare(TALISMAN, (LIFE, FIRE, "ColdResist1"), extra=(roll(crafted_id, crafted=True),))
    assert len(item.mods) == 4

    outcomes = TalismanFracture(1).outcomes(BEAST_DATA, item)

    assert len(outcomes.results) == 4 and {chance for chance, _ in outcomes.results} == {Fraction(1, 4)}
    assert fractured_chance(outcomes, [crafted_id]) == Fraction(1, 4)
    chosen = next(result for _, result in outcomes.results if any(e.mod_id == crafted_id and e.fractured for e in result.mods))
    assert next(e for e in chosen.mods if e.mod_id == crafted_id).crafted
    assert outcomes.distribution(lambda mod: mod.id)[frozenset({(Fractured(crafted_id), 1)})] == Fraction(1, 4)


@needs_fractured_crafted_mods
def test_a_crafted_mod_makes_the_double_fracture_possible_with_five_ordinary_mods():
    item = rare(TALISMAN, SIX_MODS[:2] + SIX_MODS[3:], extra=(roll(CRAFTED, crafted=True),))  # life, shield, 3 suffixes + a crafted prefix
    assert len(item.mods) == 6

    outcomes = TalismanFracture(2).outcomes(BEAST_DATA, item)

    assert len(outcomes.results) == 15 and {chance for chance, _ in outcomes.results} == {Fraction(1, 15)}
    assert fractured_chance(outcomes, [CRAFTED]) == Fraction(5, 15)


# --- the contract every action meets -------------------------------------------------------------------


@pytest.mark.parametrize(("count", "mods"), [(1, 4), (1, 6), (2, 6)])
def test_the_fracture_meets_the_contract_suite(count, mods):
    data = contract_beast_data()
    pool = (RESIST_2, LIFE_1, DAMAGE_1, FIRE_GEM, MANA_1, COLD_RESIST)  # the first four hold a Talisman of 4 mods, all six one of 6
    item = contract_item(TALISMAN, pool[:mods], data=data)

    assert check_action(TalismanFracture(count), item, data) is True


# --- the action around the outcomes ------------------------------------------------------------------


def test_the_labels():
    assert TalismanFracture(1).label() == "Beastcraft Fracture a Talisman Modifier"
    assert TalismanFracture(2).label(BEAST_DATA) == "Beastcraft Fracture two Talisman Modifiers"


def test_the_resources_are_the_named_beasts_and_the_rare_beasts_as_chaos_orbs():
    assert TalismanFracture(1).resources() == {"Farric Frost Hellion Alpha": 1, "Chaos Orb": 3}
    assert TalismanFracture(2).resources(BEAST_DATA) == {"Fenumal Plagued Arachnid": 1, "The Black Mórrígan": 1, "Chaos Orb": 2}


def test_the_rare_creature_price_is_a_setting():
    assert TalismanFracture(1, rare_creature_price=2).resources() == {"Farric Frost Hellion Alpha": 1, "Chaos Orb": 6}
    assert TalismanFracture(2, rare_creature_price=2).resources() == {"Fenumal Plagued Arachnid": 1, "The Black Mórrígan": 1, "Chaos Orb": 4}
    assert TalismanFracture(1) == TalismanFracture(1, rare_creature_price=1)
    assert TalismanFracture(1) != TalismanFracture(1, rare_creature_price=2) and TalismanFracture(1) != TalismanFracture(2)


def test_the_declarations():
    for count in (1, 2):
        action = TalismanFracture(count)
        reads, adds = action.reads(BEAST_DATA), action.adds(BEAST_DATA, talisman(6))

        assert reads.junk and reads.block_invariant is False
        assert not adds.draws and adds.keeps_crafted and adds.named is None


def test_the_kind_lists_both_recipes_for_a_rare_talisman_and_is_an_opt_in_planner_kind():
    assert [a for a in catalog(BEAST_DATA, talisman(6)) if isinstance(a, TalismanFracture)] == [TalismanFracture(1), TalismanFracture(2)]
    assert [a for a in catalog(BEAST_DATA, talisman(0)) if isinstance(a, TalismanFracture)] == [TalismanFracture(1), TalismanFracture(2)]
    assert not [a for a in catalog(BEAST_DATA, rare(TALISMAN, (LIFE,), rarity=Rarity.MAGIC)) if isinstance(a, TalismanFracture)]
    assert not [a for a in catalog(DATA, rare(AMULET, SIX_MODS, data=DATA)) if isinstance(a, TalismanFracture)]
    assert TalismanFracture(1) not in catalog(BEAST_DATA, talisman(6), planner_only=True)  # opt-in: listed only when a target names the kind
    assert TalismanFracture(1) in catalog(BEAST_DATA, talisman(6), planner_only=True, names={"talisman-fracture"})
    registered = {entry.name: entry for entry in kinds()}["talisman-fracture"]
    assert registered.planner and registered.opt_in and registered.order == 83 and not registered.why_not
