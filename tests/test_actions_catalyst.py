"""The ten regular catalysts, the Sinistral and the Dextral as exact actions (ticket #157, ADR-0029).

"Done when": exact tests against a hand oracle; the mean number of catalysts to 20% comes out as the research's 9.53, 13.35,
14.42 and 20 at item level 75, 84, 86 and 95; R06's 35 x 1.2 = 42.

The oracles are written without the code under test: the wiki's table of the gain per catalyst (to two decimals), a forward
walk of the quality with `math.exp` that sums the chance of not being done yet, a coin-flip gain whose mean is worked out by
hand (23/8), and a brute-force search for the smallest stored roll that shows a displayed value.
"""

import dataclasses
import math
from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from contract_support import (
    check_action,
    check_chances_agree,
    check_item_state_declarations,
    check_resources_are_priced,
    check_sums_to_one,
    finished,
)
from item_state_support import ITEM_DATA, amulet, intrinsic, roll
from abstraction_pool import RESIST_2

from crafting_system.actions import (
    Action,
    ApplyCatalyst,
    NotApplicableError,
    base_roll_for,
    boosts,
    catalog,
    expected_catalysts,
    expected_catalysts_for,
    gain_law,
    kinds,
    scale_value,
    scaled_values,
)
from crafting_system.actions import catalyst as catalyst_module
from crafting_system.data import Mod
from crafting_system.items import CatalystType, ExplicitMod, Item, Quality, Rarity
from crafting_system.rules import rule_by_id

LEVEL = 84
TYPES = list(CatalystType)


def at(level: int, *mods: ExplicitMod, **fields) -> Item:
    """The fixture amulet at item level `level`."""
    return amulet(roll(RESIST_2), *mods, **fields).changed(ITEM_DATA, item_level=level)


def result_of(action: ApplyCatalyst, item: Item) -> dict[tuple[CatalystType, int], Fraction]:
    """The qualities the action leaves, with their chances."""
    return {(held.quality.type, held.quality.percent): chance for chance, held in action.outcomes(ITEM_DATA, item).results}


# --- the gain per catalyst: the wiki's table, to two decimals ---------------------------------------------


WIKI_TABLE = {  # item level: {points: percent}, poewiki.net/wiki/Quality#Amount, 3.29.3.3
    75: {2: 83.75, 3: 16.25},
    84: {1: 47.57, 2: 52.43},
    86: {1: 59.34, 2: 40.66},
    95: {1: 100.0},
    100: {1: 100.0},
}


@pytest.mark.parametrize("level", list(WIKI_TABLE))
def test_the_gain_law_is_the_wikis_table_to_two_decimals(level):
    law = gain_law(level)
    assert sum(chance for _, chance in law) == 1
    assert {points: round(float(chance) * 100, 2) for points, chance in law} == WIKI_TABLE[level]


def test_a_low_item_level_gives_the_whole_20_points_and_a_high_one_one_point():
    assert gain_law(1) == ((20, 1),) and gain_law(60)[0][0] >= 3
    assert gain_law(95) == ((1, 1),) and gain_law(99) == ((1, 1),)


def test_the_probabilities_are_exact_fractions_and_the_mean_gain_is_the_formula():
    for level in (40, 75, 84, 86, 91):
        mean = sum((points * chance for points, chance in gain_law(level)), Fraction(0))
        formula = max(1.0, min(30 * math.exp(-level / 30) - 0.3, 20.0))
        assert abs(float(mean) - formula) < 1e-12, level
        assert all(isinstance(chance, Fraction) and chance > 0 for _, chance in gain_law(level))


# --- the mean number of catalysts to 20% ---------------------------------------------------------------------


def walk_oracle(level: int, target: int = 20, start: int = 0, steps: int = 400) -> float:
    """The mean number of catalysts, as the sum over n of the chance that n catalysts have not reached `target` yet (a forward walk)."""
    f = max(1.0, min(30 * math.exp(-level / 30) - 0.3, 20.0))
    low = math.floor(f)
    p_high = f - low
    quality = {start: 1.0}
    total = 0.0
    for _ in range(steps):
        total += sum(quality.values())  # P(not done after n catalysts): the term for n
        step: dict[int, float] = {}
        for percent, chance in quality.items():
            for points, share in ((low, 1 - p_high), (low + 1, p_high)):
                if share and percent + points < target:
                    step[percent + points] = step.get(percent + points, 0.0) + chance * share
        quality = step
        if not quality:
            break
    return total


RESEARCH = {75: 9.53, 84: 13.35, 86: 14.42, 95: 20.0}  # #89: mean catalysts to 20% by item level


@pytest.mark.parametrize("level", list(RESEARCH))
def test_the_mean_catalysts_to_20_percent_are_the_researchs(level):
    mean = expected_catalysts(level)
    assert isinstance(mean, Fraction)
    assert round(float(mean), 2) == RESEARCH[level]
    assert abs(float(mean) - walk_oracle(level)) < 1e-9


@pytest.mark.parametrize("level", [30, 75, 84, 88, 95])
@pytest.mark.parametrize("start, target", [(0, 20), (7, 20), (19, 20), (0, 5), (3, 12)])
def test_the_mean_agrees_with_the_forward_walk_from_any_start_to_any_target(level, start, target):
    assert abs(float(expected_catalysts(level, target, start)) - walk_oracle(level, target, start)) < 1e-9


def test_a_gain_of_exactly_one_point_needs_the_whole_distance():
    assert expected_catalysts(95) == 20 and expected_catalysts(95, 20, 12) == 8 and expected_catalysts(95, 7) == 7
    assert expected_catalysts(1) == 1  # 20 points at once


def test_nothing_is_needed_at_or_past_the_target():
    assert expected_catalysts(84, 10, 10) == 0 and expected_catalysts(84, 10, 20) == 0 and expected_catalysts(84, 0, 0) == 0


def test_a_coin_flip_gain_of_one_or_two_points_to_4_percent_is_23_over_8(monkeypatch):
    # worked by hand: E[3] = 1; E[2] = 1 + 1/2 * E[3]; E[1] = 1 + 1/2 * E[2] + 1/2 * E[3]; E[0] = 1 + 1/2 * E[1] + 1/2 * E[2]
    monkeypatch.setattr(catalyst_module, "gain_law", lambda level: ((1, Fraction(1, 2)), (2, Fraction(1, 2))))
    expected_catalysts.cache_clear()
    try:
        assert expected_catalysts(7, 4, 3) == 1 and expected_catalysts(7, 4, 2) == Fraction(3, 2)
        assert expected_catalysts(7, 4, 1) == Fraction(9, 4) and expected_catalysts(7, 4, 0) == Fraction(23, 8)
    finally:
        expected_catalysts.cache_clear()


def test_the_quality_out_of_range_is_refused():
    for start, target in ((-1, 20), (0, 21), (21, 20)):
        with pytest.raises(ValueError):
            expected_catalysts(84, target, start)


def test_the_cost_of_an_item_counts_its_quality_only_when_it_is_of_the_type():
    item = at(75, quality=intrinsic(10))
    assert expected_catalysts_for(item, CatalystType.INTRINSIC) == expected_catalysts(75, 20, 10)
    assert expected_catalysts_for(item, CatalystType.IMBUED) == expected_catalysts(75, 20, 0)  # another type restarts from 0
    assert expected_catalysts_for(at(75), CatalystType.INTRINSIC, 12) == expected_catalysts(75, 12, 0)
    assert expected_catalysts_for(at(75, quality=intrinsic(15)), CatalystType.INTRINSIC, 12) == 0


# --- the action: what one catalyst does ------------------------------------------------------------------------


def test_one_catalyst_on_an_item_with_no_quality_gives_the_gain_at_its_level():
    for level in (75, 84, 86, 95):
        found = result_of(ApplyCatalyst(CatalystType.INTRINSIC), at(level))
        assert found == {(CatalystType.INTRINSIC, points): chance for points, chance in gain_law(level)}


def test_the_same_type_adds_to_the_quality_and_the_cap_merges_the_results():
    assert result_of(ApplyCatalyst(CatalystType.INTRINSIC), at(84, quality=intrinsic(10))) == {
        (CatalystType.INTRINSIC, 11): Fraction(gain_law(84)[0][1]),
        (CatalystType.INTRINSIC, 12): Fraction(gain_law(84)[1][1]),
    }
    assert result_of(ApplyCatalyst(CatalystType.INTRINSIC), at(75, quality=intrinsic(18))) == {(CatalystType.INTRINSIC, 20): 1}  # 20 or 21 points: capped
    assert result_of(ApplyCatalyst(CatalystType.INTRINSIC), at(84, quality=intrinsic(19))) == {(CatalystType.INTRINSIC, 20): 1}


def test_another_type_replaces_the_quality_and_starts_again_from_zero():
    held = at(84, quality=intrinsic(15))
    assert result_of(ApplyCatalyst(CatalystType.IMBUED), held) == {
        (CatalystType.IMBUED, points): chance for points, chance in gain_law(84)
    }
    assert result_of(ApplyCatalyst(CatalystType.IMBUED), at(84, quality=intrinsic(20))) == {
        (CatalystType.IMBUED, points): chance for points, chance in gain_law(84)
    }  # even from the cap of another type


@pytest.mark.parametrize("catalyst", TYPES)
def test_every_type_puts_its_own_quality(catalyst):
    assert result_of(ApplyCatalyst(catalyst), at(95)) == {(catalyst, 1): 1}


def test_the_catalyst_leaves_everything_but_the_quality_as_it_was():
    item = at(84, rarity=Rarity.MAGIC)
    for _, result in ApplyCatalyst(CatalystType.FERTILE).outcomes(ITEM_DATA, item).results:
        assert dataclasses.replace(result, quality=None) == item


def test_a_20_percent_item_of_the_type_is_refused_and_a_20_percent_item_of_another_type_is_not():
    with pytest.raises(NotApplicableError, match="20%"):
        ApplyCatalyst(CatalystType.INTRINSIC).outcomes(ITEM_DATA, at(84, quality=intrinsic(20)))
    assert ApplyCatalyst(CatalystType.NOXIOUS).outcomes(ITEM_DATA, at(84, quality=intrinsic(20)))


def test_a_corrupted_item_and_an_item_that_is_no_jewellery_are_refused():
    with pytest.raises(NotApplicableError, match="corrupted"):
        ApplyCatalyst(CatalystType.INTRINSIC).outcomes(ITEM_DATA, at(84, corrupted=True))
    from implicits_support import BOOTS

    boots = Item.build(ITEM_DATA, base_id=BOOTS, item_level=84, rarity=Rarity.RARE)
    with pytest.raises(NotApplicableError, match="ring, an amulet or a belt"):
        ApplyCatalyst(CatalystType.INTRINSIC).outcomes(ITEM_DATA, boots)


def test_the_label_and_the_price_name_are_the_items_name():
    assert ApplyCatalyst(CatalystType.INTRINSIC).label(ITEM_DATA) == "Intrinsic Catalyst"
    assert ApplyCatalyst(CatalystType.SINISTRAL).resources(ITEM_DATA) == {"Sinistral Catalyst": 1}
    assert {ApplyCatalyst(kind).label() for kind in TYPES} == {
        f"{kind.value.capitalize()} Catalyst" for kind in TYPES
    }


# --- the contract suite -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("catalyst", [CatalystType.INTRINSIC, CatalystType.IMBUED, CatalystType.SINISTRAL, CatalystType.DEXTRAL])
@pytest.mark.parametrize("quality", [None, 5, 10, 19, 20])
@pytest.mark.parametrize("level", [75, 84, 95])
def test_the_catalyst_passes_the_contract_suite_and_layer_1(catalyst, quality, level):
    held = Quality(CatalystType.INTRINSIC, quality) if quality else None
    item = at(level, quality=held) if held else at(level)
    expected = not (quality == 20 and catalyst is CatalystType.INTRINSIC)
    assert check_action(ApplyCatalyst(catalyst), item, ITEM_DATA) is expected


def test_the_remaining_types_pass_the_checks_of_the_suite_that_do_not_need_the_kernel():
    for catalyst in TYPES:
        action = ApplyCatalyst(catalyst)
        item = at(84, quality=intrinsic(8))
        outcomes = action.outcomes(ITEM_DATA, item)
        items = finished(outcomes, ITEM_DATA)
        check_sums_to_one(outcomes, ITEM_DATA)
        check_chances_agree(outcomes, items, ITEM_DATA)
        check_item_state_declarations(action, action.reads(ITEM_DATA), action.adds(ITEM_DATA, item), items, item, ITEM_DATA)
        check_resources_are_priced(action, item, ITEM_DATA)


def test_the_declarations_name_the_quality_and_nothing_else_of_the_item_state():
    reads, adds = ApplyCatalyst(CatalystType.INTRINSIC).reads(ITEM_DATA), ApplyCatalyst(CatalystType.INTRINSIC).adds(ITEM_DATA, None)
    assert reads.quality and not reads.implicits and not reads.offer
    assert adds.quality and not adds.implicits and not adds.offer
    assert adds.named == frozenset() and not adds.draws


def test_the_kind_lists_the_twelve_catalysts_for_jewellery_only_and_is_no_planner_kind_yet():
    entry = next(entry for entry in kinds() if entry.name == "catalyst")
    assert entry.planner is False and "158" in entry.why_not
    listed = catalog(ITEM_DATA, at(84), names={"catalyst"})
    assert listed == tuple(ApplyCatalyst(kind) for kind in CatalystType) and len(listed) == 12
    assert catalog(ITEM_DATA, at(84, corrupted=True), names={"catalyst"}) == ()
    from implicits_support import BOOTS

    assert catalog(ITEM_DATA, Item.build(ITEM_DATA, base_id=BOOTS, item_level=84, rarity=Rarity.RARE), names={"catalyst"}) == ()
    assert not any(isinstance(action, ApplyCatalyst) for action in catalog(ITEM_DATA, at(84), planner_only=True))
    assert all(isinstance(action, Action) for action in listed)


def test_the_catalyst_names_its_claims_and_marks_the_ones_no_other_source_settles():
    claims = ApplyCatalyst(CatalystType.INTRINSIC).claims()
    assert {
        "catalyst.single_quality_type",
        "catalyst.gain_formula_and_rounding",
        "catalyst.quality_capped_at_20",
        "catalyst.rounding_floor",
        "catalyst.match_by_implicit_tags",
        "catalyst.cost",
    } <= claims
    for rule_id in (
        "catalyst.gain_formula_and_rounding",
        "catalyst.quality_capped_at_20",
        "catalyst.rounding_floor",
        "catalyst.sinistral_dextral_by_side",
    ):
        assert rule_by_id(rule_id).approximate and rule_by_id(rule_id).approximate_reason


# --- the scaling of the mods -----------------------------------------------------------------------------------


def hand_mod(generation_type: str, *tags: str) -> Mod:
    base = next(iter(ITEM_DATA.mods.values()))
    return dataclasses.replace(base, id="Hand", generation_type=generation_type, implicit_tags=tags)


def test_r06_a_strength_roll_of_35_under_20_percent_intrinsic_shows_42():
    assert scale_value(35, 20) == 42 == 35 * 120 // 100
    assert scaled_values(hand_mod("unique", "attribute"), (35,), intrinsic(20)) == (42,)


def test_the_value_is_rounded_down_in_the_stored_unit():
    assert scale_value(11, 20) == 13  # 13.2
    assert scale_value(12, 20) == 14  # 14.4: R06's "14% increased attributes" needs the maximum roll 12
    assert scale_value(7, 5) == 7 and scale_value(8, 5) == 8 and scale_value(20, 5) == 21
    assert scale_value(5, 0) == 5 and scale_value(0, 20) == 0


@pytest.mark.parametrize("percent", range(0, 21))
def test_the_roll_that_shows_a_displayed_value_is_the_smallest_by_brute_force(percent):
    for shown in range(1, 61):
        smallest = next(value for value in range(0, 200) if value * (100 + percent) // 100 >= shown)
        assert base_roll_for(shown, percent) == smallest, (shown, percent)


def test_r06_the_attribute_target_of_14_percent_at_20_percent_quality_needs_the_roll_12():
    assert base_roll_for(14, 20) == 12 and scale_value(12, 20) == 14 and scale_value(11, 20) == 13


def test_a_regular_catalyst_boosts_by_the_tags_of_the_mod_and_once():
    table = {
        CatalystType.ABRASIVE: "attack", CatalystType.ACCELERATING: "speed", CatalystType.FERTILE: "resource",
        CatalystType.IMBUED: "caster", CatalystType.INTRINSIC: "attribute", CatalystType.NOXIOUS: "physical_damage",
        CatalystType.PRISMATIC: "resistance", CatalystType.TEMPERING: "defences", CatalystType.TURBULENT: "elemental_damage",
        CatalystType.UNSTABLE: "critical",
    }  # PoEDB's table, written out here
    for catalyst, tag in table.items():
        assert boosts(hand_mod("suffix", tag), catalyst)
        assert not any(boosts(hand_mod("suffix", tag), other) for other in table if other is not catalyst and table[other] != tag)
    assert boosts(hand_mod("prefix", "chaos_damage"), CatalystType.NOXIOUS)  # Noxious has two tags
    assert not boosts(hand_mod("prefix", "life"), CatalystType.FERTILE) and not boosts(hand_mod("prefix"), CatalystType.INTRINSIC)
    assert scaled_values(hand_mod("suffix", "attribute", "attack"), (10,), intrinsic(20)) == (12,)  # two tags of the type: scaled once
    assert scaled_values(hand_mod("suffix", "attribute"), (10,), Quality(CatalystType.IMBUED, 20)) == (10,)  # not its tag: unchanged
    assert scaled_values(hand_mod("suffix", "attribute"), (10,), None) == (10,)


def test_sinistral_boosts_prefixes_and_dextral_suffixes_and_neither_an_implicit():
    for catalyst, side, other in ((CatalystType.SINISTRAL, "prefix", "suffix"), (CatalystType.DEXTRAL, "suffix", "prefix")):
        assert boosts(hand_mod(side, "life"), catalyst) and not boosts(hand_mod(other, "life"), catalyst)
        assert not boosts(hand_mod("unique", "attribute"), catalyst)
        assert not boosts(hand_mod("eater_of_worlds_implicit"), catalyst)
    assert boosts(hand_mod("prefix", "attribute"), CatalystType.INTRINSIC)  # a regular catalyst ignores the side


# --- the real data ----------------------------------------------------------------------------------------------


def test_r06_the_real_heavy_belt_strength_implicit_is_boosted_by_intrinsic_and_35_shows_42():
    data = real_game_data()
    base = next(base for base in data.base_items.values() if base.name == "Heavy Belt" and base.item_class == "Belt")
    strength = data.mods[base.implicits[0]]
    assert (strength.stats[0].min, strength.stats[0].max) == (25, 35)
    assert boosts(strength, CatalystType.INTRINSIC)
    assert not any(boosts(strength, kind) for kind in TYPES if kind is not CatalystType.INTRINSIC)
    assert scaled_values(strength, (35,), intrinsic(20)) == (42,)
    assert scaled_values(strength, (25,), intrinsic(20)) == (30,)


def test_the_real_ring_amulet_belt_census_matches_the_researchs():
    """#89's census: of the 316 ordinary ring, amulet and belt modifier records (a spawn weight above zero on any of the three),
    56 match two catalyst types and 50 match none, by PoEDB's tag table."""
    data = real_game_data()
    jewellery = {"ring", "amulet", "belt"}
    records = [
        mod
        for mod in data.mods.values()
        if mod.domain == "item"
        and mod.generation_type in ("prefix", "suffix")
        and any(weight.tag in jewellery and weight.weight > 0 for weight in mod.spawn_weights)
    ]
    regular = [kind for kind in CatalystType if kind not in (CatalystType.SINISTRAL, CatalystType.DEXTRAL)]
    matched = [sum(boosts(mod, kind) for kind in regular) for mod in records]
    assert len(records) == 316
    assert matched.count(2) == 56 and matched.count(0) == 50
    assert max(matched) == 2
