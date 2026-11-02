"""The Blacksmith's Whetstone and the Armourer's Scrap (ticket #229, B6 S3; ADR-0049).

"Done when", test by test:

* the expected number of Scraps and Whetstones to 20% is 9.5, 13.3 and 20 at item levels 75, 84 and 95
  (`test_the_expected_count_to_20_percent`), restated by value iteration over the gain law of ADR-0049;
* the contract suite passes for each action on the quality fixtures (`test_each_quality_action_meets_the_contract_on_every_quality_fixture`; the shared
  suite asks them too) and the claim marks are those of ADR-0049 (`test_the_claims_carry_the_marks`).
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_pool import LIFE_1
from contract_support import check_action, extra_fixture_items
from items_support import AMULET, BODY
from sockets_colour_support import colour_data, expected_currency, quality_gain
from sockets_support import BOW, HELMET, SWORD, socketed, white

from crafting_system.actions import (
    ARMOUR_CLASSES,
    WEAPON_CLASSES,
    Adds,
    ApplyQualityCurrency,
    NotApplicableError,
    catalog,
    expected_quality_currency,
    kinds,
    quality_gain_law,
)
from crafting_system.items import PLAIN_QUALITY_ITEM_CLASSES, Item, PlainQuality, Rarity
from crafting_system.prices.price_names import ARMOURERS_SCRAP, BLACKSMITHS_WHETSTONE
from crafting_system.rules import load_registry, rule_by_id

DATA = colour_data()
WHETSTONE, SCRAP = ApplyQualityCurrency(BLACKSMITHS_WHETSTONE), ApplyQualityCurrency(ARMOURERS_SCRAP)
EXTRA = extra_fixture_items()
QUALITY_ITEMS = sorted(name for name in EXTRA if name.startswith("quality_"))


def gain(action, item):
    return action.outcomes(DATA, item)


def percents(outcome) -> dict[int, Fraction]:
    found: dict[int, Fraction] = {}
    for chance, result in outcome.results:
        found[result.quality.percent] = found.get(result.quality.percent, Fraction(0)) + chance
    return found


@pytest.mark.parametrize("item_level,expected", [(75, 9.5), (84, 13.3), (95, 20.0)])
def test_the_expected_count_to_20_percent(item_level, expected):
    assert round(float(expected_quality_currency(item_level)), 1) == expected
    assert float(expected_quality_currency(item_level)) == pytest.approx(expected_currency(item_level), abs=1e-9)  # the restatement
    assert expected_quality_currency(item_level, 20, 20) == 0 and expected_quality_currency(item_level, 20, 25) == 0  # nothing to buy from the cap up


def test_the_expected_count_from_a_start_quality_is_lower_and_the_cap_is_20():
    assert expected_quality_currency(84, 20, 10) < expected_quality_currency(84)
    with pytest.raises(ValueError, match="stops at 20"):
        expected_quality_currency(84, 21)


@pytest.mark.parametrize("item_level", [1, 30, 60, 75, 84, 86, 95, 100])
def test_the_gain_law_is_the_formula_of_adr_0049_floored_with_the_fraction_as_the_chance_of_one_more_point(item_level):
    f = quality_gain(item_level)
    law = dict(quality_gain_law(item_level))
    assert sum(law.values()) == 1
    assert sum(points * float(chance) for points, chance in law.items()) == pytest.approx(f, abs=1e-12)
    assert set(law) <= {int(f), int(f) + 1}


def test_a_whetstone_adds_the_gain_of_the_item_level_to_the_plain_quality():
    sword = socketed(white(3), base_id=SWORD, quality=0, item_level=84)
    outcome = gain(WHETSTONE, sword)
    assert percents(outcome) == {points: chance for points, chance in quality_gain_law(84)} and sorted(percents(outcome)) == [1, 2]
    for _, result in outcome.results:
        assert isinstance(result.quality, PlainQuality)
        assert dataclasses.replace(result, quality=sword.quality) == sword  # nothing but the quality changes
    at_75 = percents(gain(WHETSTONE, socketed(white(3), base_id=SWORD, quality=0, item_level=75)))
    assert sorted(at_75) == [2, 3] and at_75 == dict(quality_gain_law(75)) and round(float(at_75[3]), 2) == 0.16  # the wiki's table: +2 83.75%, +3 16.25%


def test_the_quality_grows_from_the_start_quality_and_stops_at_20():
    near = socketed(white(2), base_id=HELMET, quality=19)
    assert percents(gain(SCRAP, near)) == {20: Fraction(1)}
    assert percents(gain(SCRAP, socketed(white(2), base_id=HELMET, quality=10, item_level=95))) == {11: Fraction(1)}  # f floors at 1: 20 items from item level 95
    early = socketed(white(2), base_id=HELMET, quality=5, item_level=1)  # f = 20 at item level 1 (the cap of the formula): one item reaches 20%
    assert percents(gain(SCRAP, early)) == {20: Fraction(1)}


@pytest.mark.parametrize("quality", [20, 25, 30])
def test_a_currency_is_refused_at_20_percent_or_more_and_spends_nothing(quality):
    with pytest.raises(NotApplicableError, match="stops at 20%"):
        gain(SCRAP, socketed(white(2), quality=quality))


def test_a_whetstone_works_on_weapons_and_a_scrap_on_armour_only():
    assert WEAPON_CLASSES | ARMOUR_CLASSES == PLAIN_QUALITY_ITEM_CLASSES and not WEAPON_CLASSES & ARMOUR_CLASSES
    assert "Shield" in ARMOUR_CLASSES and {"Sceptre", "Bow", "Wand", "Staff"} <= WEAPON_CLASSES
    with pytest.raises(NotApplicableError, match="does not work on a Body Armour"):
        gain(WHETSTONE, socketed(white(2), quality=0))
    with pytest.raises(NotApplicableError, match="does not work on a One Hand Sword"):
        gain(SCRAP, socketed(white(2), base_id=SWORD, quality=0))
    gain(WHETSTONE, socketed(white(2), base_id=BOW, quality=0))
    gain(SCRAP, socketed(white(2), quality=0))


def test_the_refusals():
    with pytest.raises(NotApplicableError, match="corrupted"):
        gain(SCRAP, socketed(white(2), quality=0, corrupted=True))
    amulet = Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=())
    with pytest.raises(NotApplicableError, match="works on a weapon or armour"):
        gain(SCRAP, amulet)
    with pytest.raises(ValueError, match="quality currencies"):
        ApplyQualityCurrency("Orb of Fusing")


def test_it_needs_no_sockets_and_leaves_them_alone():
    outcome = gain(SCRAP, socketed(None, quality=5))
    assert all(result.sockets is None for _, result in outcome.results)
    held = socketed(white(4, (2, 2)), quality=5)
    assert all(result.sockets == held.sockets for _, result in gain(SCRAP, held).results)


def test_the_kind_offers_a_whetstone_to_weapons_and_a_scrap_to_armour():
    by_name = {entry.name: entry for entry in kinds()}
    entry = by_name["quality-currency"]
    assert not entry.planner and "ADR-0049" in entry.why_not and entry.applies_only_to == "weapon and armour" and entry.reads_item_state_while_not_planner == "quality"
    assert list(entry.members(DATA, socketed(white(2), base_id=SWORD, quality=0))) == [WHETSTONE]
    assert list(entry.members(DATA, socketed(white(2), quality=0))) == [SCRAP]
    assert list(entry.members(DATA, socketed(white(2), quality=0, corrupted=True))) == []
    amulet = Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=())
    assert not any(isinstance(action, ApplyQualityCurrency) for action in catalog(DATA, amulet))
    assert not {type(a) for a in catalog(DATA, socketed(white(2), quality=0), planner_only=True)} & {ApplyQualityCurrency}


def test_it_is_a_quality_action_offered_last_like_a_catalyst():
    for action in (WHETSTONE, SCRAP):
        adds, reads = action.adds(DATA, None), action.reads(DATA)
        assert adds.only_quality and adds == Adds(named=frozenset(), draws=False, quality=True)
        assert reads.quality and reads.junk and reads.families == frozenset() and not (reads.socket_count or reads.socket_links or reads.socket_colours)


def test_each_is_priced_by_the_name_of_the_game_and_labelled_with_it():
    assert WHETSTONE.resources(DATA) == {BLACKSMITHS_WHETSTONE: 1} and SCRAP.resources(None) == {ARMOURERS_SCRAP: 1}
    assert [WHETSTONE.label(DATA), SCRAP.label()] == ["Blacksmith's Whetstone", "Armourer's Scrap"]
    registry = load_registry()
    assert dict(registry["sockets.blacksmiths_whetstone_cost"].value) == {BLACKSMITHS_WHETSTONE: 1}
    assert dict(registry["sockets.armourers_scrap_cost"].value) == {ARMOURERS_SCRAP: 1}


@pytest.mark.parametrize("name", QUALITY_ITEMS)
def test_each_quality_action_meets_the_contract_on_every_quality_fixture(name):
    extra = EXTRA[name]
    entry = next(entry for entry in kinds() if entry.name == "quality-currency")
    actions = list(entry.members(extra.data, extra.item))
    assert actions, f"quality-currency lists an action for the item {name}"
    for action in actions:
        assert isinstance(check_action(action, extra.item, extra.data), bool)


def test_it_applies_where_the_game_lets_it_and_works_on_a_stranded_item():
    wanted = {"quality_sword_plain", "quality_body_ten", "quality_helmet_nineteen", "quality_body_stranded"}  # the bow holds 20%: refused
    entry = next(entry for entry in kinds() if entry.name == "quality-currency")
    for name in QUALITY_ITEMS:
        extra, applied = EXTRA[name], False
        for action in entry.members(extra.data, extra.item):
            try:
                action.outcomes(extra.data, extra.item)
                applied = True
            except NotApplicableError:
                pass
        assert applied == (name in wanted), name
    stranded = EXTRA["quality_body_stranded"].item
    assert stranded.memory_strands == 45
    use = SCRAP.strand_use(DATA)
    assert use is not None and not use.cuts and use.spend is None and use.claims and SCRAP.strand_claims(DATA) == use.claims
    assert all(found.memory_strands == 45 for _, found in SCRAP.outcomes(DATA, stranded).results)


def test_the_claims_carry_the_marks():
    """ADR-0049: the gain by item level is the wiki's (unmarked); the rounding of the gain and the cap are the catalysts' approximate readings."""
    registry = load_registry()
    for action in (WHETSTONE, SCRAP):
        claims = action.claims(None)
        assert claims <= set(registry) and action.strand_claims(None) <= set(registry)
        assert {"sockets.quality_currency_gain_by_item_level", "catalyst.gain_formula_and_rounding", "catalyst.quality_capped_at_20"} <= claims
        assert {rule_id for rule_id in claims if rule_by_id(rule_id).approximate} == {"catalyst.gain_formula_and_rounding", "catalyst.quality_capped_at_20"}
    assert "sockets.blacksmiths_whetstone_cost" in WHETSTONE.claims(None) and "sockets.armourers_scrap_cost" in SCRAP.claims(None)
    assert not registry["sockets.blacksmiths_whetstone_cost"].approximate and not registry["sockets.armourers_scrap_cost"].approximate
    assert not registry["sockets.quality_currency_gain_by_item_level"].approximate
