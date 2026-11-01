"""The cost of a recombination, its price entries and the junk-craft option (ticket #216, ADR-0035).

Done when: a recombination priced from a fixture price file costs about 7 Chaos at the default Dust and Gold prices and a different amount when
the Dust price changes; the junk-craft variant is absent from the catalog by default and present when the setting is on; its Dust is halved and
its Gold is not; an influenced input raises both Dust and Gold by half; every cost claim the action reads is in its claims and marked approximate.
The worlds are the fixture worlds of `test_actions_recombinator.py` (amulets, with bench crafts of the fixture).
"""

import datetime

import pytest
from contract_support import check_action
from test_actions_recombinator import ALPHA, DATA, SCENARIOS, make

from crafting_system.actions import NotApplicableError, Recombinator, catalog
from crafting_system.actions.bench import BenchCraft, bench_crafts
from crafting_system.actions.recombinator import (
    DUST_PER_COMBINE,
    GOLD_PER_COMBINE,
    GOLD_PER_MOD,
    INFLUENCED_FACTOR,
    JUNK_DUST_FACTOR,
    junk_craft_enabled,
    junk_craft_for,
    junk_craft_offered,
)
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.items import Influence, Rarity
from crafting_system.prices import DUST, GOLD, PriceEntry, PriceFile, default_prices
from crafting_system.rules import rule_by_id

SHAPER = frozenset({Influence.SHAPER})
COLD = "ContractCraftCold"  # the lowest-level, cheapest, first-by-id suffix craft of the fixture amulets
COST_CLAIMS = (
    "recombinator_cost.dust_per_combine_reports_3_26",
    "recombinator_cost.gold_per_combine_reports_3_26",
    "recombinator_cost.junk_craft_halves_dust_3_26",
    "recombinator_cost.gold_linear_in_mod_count_3_25",
    "recombinator_cost.influenced_input_multiplies_both",
)
DUST_NAME, GOLD_NAME = "Thaumaturgic Dust", "Gold"


def pair():
    """Two rares with room for a suffix craft each (2 prefixes and 1 suffix)."""
    return SCENARIOS["tiers"]


def junk(donor, **fields):
    return Recombinator(donor, junk_crafts=(COLD, COLD), **fields)


def bench_currencies(*mod_ids) -> dict[str, int]:
    found: dict[str, int] = {}
    for mod_id in mod_ids:
        for name, count in BenchCraft(mod_id).resources(DATA).items():
            found[name] = found.get(name, 0) + count
    return found


def price_file(**changes) -> PriceFile:
    prices = {**default_prices(), "Chaos Orb": PriceEntry(1.0, "test")}
    prices.update(changes)
    return PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, prices)


def cost_in_chaos(action, prices) -> float:
    priced, dropped = price_offers([offer_of(action, action.label(DATA), DATA)], prices)
    assert not dropped
    return priced[0].cost


# --- the plain cost ------------------------------------------------------------------------------------------------------------------


def test_a_recombination_is_priced_from_a_fixture_price_file_about_seven_chaos_and_follows_the_dust_price():
    _, donor = pair()
    action = Recombinator(donor)
    assert action.resources(DATA) == {DUST_NAME: 100_000, GOLD_NAME: 12_000}
    at_default = cost_in_chaos(action, price_file())
    assert 6.5 < at_default < 7.0
    assert at_default == pytest.approx(100_000 / 150_000 + 12_000 * 0.0005)
    dearer = cost_in_chaos(action, price_file(**{DUST: PriceEntry(1 / 15_000, "test")}))
    assert dearer == pytest.approx(100_000 / 15_000 + 6.0)
    assert dearer != at_default and 12.5 < dearer < 13.0


def test_the_price_file_names_are_the_ones_of_the_prices_crate():
    assert (DUST_NAME, GOLD_NAME) == (DUST, GOLD)
    assert set(Recombinator(pair()[1]).resources(DATA)) == {DUST, GOLD}


def test_the_plain_cost_needs_no_data():
    assert Recombinator(pair()[1]).resources() == {DUST_NAME: 100_000, GOLD_NAME: 12_000}


def test_the_cost_numbers_are_the_points_of_the_claims():
    assert DUST_PER_COMBINE.value["point"] == 100_000
    assert GOLD_PER_COMBINE.value["point"] == 12_000
    assert JUNK_DUST_FACTOR.value["factor_point"] == 0.5
    assert GOLD_PER_MOD.value["gold_per_mod"] == 323.5
    assert INFLUENCED_FACTOR.value["factor"] == 1.5


# --- the influence factor ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "donor_influences,hand_influenced,dust,gold",
    [
        (frozenset(), None, 100_000, 12_000),
        (frozenset(), False, 100_000, 12_000),
        (SHAPER, None, 150_000, 18_000),  # an influenced donor
        (SHAPER, False, 150_000, 18_000),
        (frozenset(), True, 150_000, 18_000),  # an influenced item in hand, a plain donor
        (SHAPER, True, 150_000, 18_000),  # not 2.25 times: one factor for the combine
    ],
)
def test_an_influenced_input_multiplies_both_dust_and_gold_by_one_and_a_half(donor_influences, hand_influenced, dust, gold):
    donor = make(["RP25", "RS500"], Rarity.MAGIC, influences=donor_influences)
    assert Recombinator(donor, hand_influenced=hand_influenced).resources(DATA) == {DUST_NAME: dust, GOLD_NAME: gold}


def test_a_price_for_an_item_in_hand_with_an_influence_refuses_one_without_and_the_other_way_round():
    plain, donor = make(["RP25", "RS500"], Rarity.MAGIC), make(["RP1000a", "RS250"], Rarity.MAGIC)
    influenced = make(["RP25", "RS500"], Rarity.MAGIC, influences=SHAPER)
    with pytest.raises(NotApplicableError, match="influence"):
        Recombinator(donor, hand_influenced=True).outcomes(DATA, plain)
    with pytest.raises(NotApplicableError, match="influence"):
        Recombinator(donor, hand_influenced=False).outcomes(DATA, influenced)
    Recombinator(donor, hand_influenced=False).outcomes(DATA, plain)
    Recombinator(donor, hand_influenced=True).outcomes(DATA, influenced)
    Recombinator(donor).outcomes(DATA, influenced)  # unspecified: no check


def test_the_catalog_prices_each_action_for_the_item_it_was_listed_for():
    plain, shaper = make(["RP25", "RS500"], Rarity.MAGIC), make(["RP25", "RS500"], Rarity.MAGIC, influences=SHAPER)
    for item, flag in ((plain, False), (shaper, True)):
        members = catalog(DATA, item, names={"recombinator"})
        assert members and all(isinstance(member, Recombinator) and member.hand_influenced is flag for member in members)


# --- the junk craft ------------------------------------------------------------------------------------------------------------------


def test_the_dust_factor_applies_to_dust_only_and_the_gold_gains_the_two_mods_and_the_bench_currencies():
    item, donor = pair()
    action = junk(donor)
    assert action.resources(DATA) == {DUST_NAME: 50_000, GOLD_NAME: 12_647, **bench_currencies(COLD, COLD)}
    assert action.resources(DATA)[GOLD_NAME] > Recombinator(donor).resources(DATA)[GOLD_NAME]  # Gold is not halved


def test_junk_and_influenced_round_the_half_gold_up():
    _, donor = pair()
    both = junk(donor, hand_influenced=True)
    assert both.resources(DATA)[DUST_NAME] == 75_000
    assert both.resources(DATA)[GOLD_NAME] == 18_971  # 18970.5


def test_the_junk_cost_needs_the_data():
    with pytest.raises(ValueError, match="needs the data"):
        junk(pair()[1]).resources()


def test_a_junk_craft_is_two_mod_ids_or_none():
    _, donor = pair()
    with pytest.raises(ValueError):
        Recombinator(donor, junk_crafts=(COLD,))
    with pytest.raises(ValueError):
        Recombinator(donor, junk_crafts=(COLD, COLD, COLD))


def test_the_variants_and_the_labels_tell_the_priced_actions_apart():
    _, donor = pair()
    plain, crafted, influenced = Recombinator(donor), junk(donor), Recombinator(donor, hand_influenced=True)
    assert len({plain.variant, crafted.variant, influenced.variant, Recombinator(donor, hand_influenced=False).variant}) == 4
    assert crafted.label(DATA) == plain.label(DATA) + " with a junk craft on each input"
    assert plain.label(DATA) == Recombinator(donor, hand_influenced=True).label(DATA)


def test_the_junk_variant_is_absent_from_the_catalog_by_default_present_inside_the_setting_and_absent_after_it():
    item, _ = pair()

    def crafts():
        return [member.junk_crafts for member in catalog(DATA, item, names={"recombinator"}) if member.junk_crafts]

    assert not junk_craft_enabled() and crafts() == []
    with junk_craft_offered():
        assert junk_craft_enabled()
        found = crafts()
        assert (COLD, COLD) in found  # the copy of the item as the donor
        assert all(pair_[0] == COLD and len(pair_) == 2 for pair_ in found)  # the donor of other mods may take another craft
        with junk_craft_offered(False):
            assert crafts() == []
        assert crafts() == found
    assert not junk_craft_enabled() and crafts() == []


def test_the_setting_is_restored_when_the_block_raises():
    with pytest.raises(RuntimeError):
        with junk_craft_offered():
            raise RuntimeError
    assert not junk_craft_enabled()


def test_with_the_setting_off_the_catalog_is_the_plain_actions():
    item, _ = pair()
    members = catalog(DATA, item, names={"recombinator"})
    assert members and all(not member.junk_crafts and member.hand_influenced is False for member in members)


def test_the_junk_craft_is_the_lowest_level_then_cheapest_then_first_by_id_and_never_a_metamod():
    item, _ = pair()
    craft = junk_craft_for(DATA, item)
    assert craft == BenchCraft(COLD)
    levels = {c.mod_id: DATA.mods[c.mod_id].required_level for c in bench_crafts(DATA)}
    assert levels[COLD] == min(levels[c.mod_id] for c in bench_crafts(DATA) if c.mod_id != "StrMasterItemGenerationCannotChangePrefixes")
    assert levels["StrMasterItemGenerationCannotChangePrefixes"] == 1  # the lock metamod is the lowest of all and is not chosen


def test_a_full_item_has_no_junk_craft_and_the_variant_is_not_applicable():
    full_item, full_donor = SCENARIOS["six_and_six"]
    assert junk_craft_for(DATA, full_item) is None
    assert not [m for m in _offered(full_item) if m.junk_crafts]
    with pytest.raises(NotApplicableError):
        junk(full_donor).outcomes(DATA, full_item)


def test_an_item_of_a_class_without_a_bench_craft_has_no_junk_craft():
    jewel = make(["RP25"], Rarity.MAGIC, base="Metadata/Items/Jewels/RecombJewel")
    assert junk_craft_for(DATA, jewel) is None


def _offered(item):
    with junk_craft_offered():
        return catalog(DATA, item, names={"recombinator"})


def test_the_junk_results_sum_to_one_differ_from_the_plain_ones_and_can_carry_a_crafted_mod():
    item, donor = pair()
    outcomes = junk(donor).outcomes(DATA, item)
    plain = Recombinator(donor).outcomes(DATA, item)
    assert sum(chance for chance, _ in outcomes.results) == 1
    results = {result for _, result in outcomes.results}
    assert results != {result for _, result in plain.results}
    assert any(entry.crafted for result in results for entry in result.mods)
    assert all(sum(1 for entry in result.mods if entry.crafted) <= 1 for result in results)  # at most one exclusive mod on the output
    assert 0 < outcomes.chance_all([COLD]) < 1
    assert plain.chance_all([COLD]) == 0


def test_a_craft_the_side_cannot_take_makes_the_variant_not_applicable():
    _, donor = SCENARIOS["tiers"]
    with pytest.raises(NotApplicableError):  # three prefixes are held: no prefix slot is free for the first craft
        Recombinator(donor, junk_crafts=("ContractCraftLightningDamage", "ContractCraftLightningDamage")).outcomes(
            DATA, make(["RP25", "RP1000a", "RP400", "RS500"])
        )


def test_the_junk_variant_passes_the_contract_suite_and_declares_what_it_does():
    item, donor = pair()
    action = junk(donor)
    assert check_action(action, item, data=DATA)
    assert action.adds(DATA, item).crafted and action.adds(DATA, item).keeps_crafted
    assert not Recombinator(donor).adds(DATA, item).crafted
    assert action.reads(DATA) == Recombinator(donor).reads(DATA)
    assert action.inputs(DATA, item) == Recombinator(donor).inputs(DATA, item)


def test_the_junk_variant_begins_from_the_original_item():
    item, donor = pair()
    outcomes = junk(donor).outcomes(DATA, item)
    assert outcomes.given == item  # the Finite starts at the item in hand, not at the crafted copy


# --- the claims ----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", [Recombinator(pair()[1]), junk(pair()[1])])
def test_every_cost_claim_the_action_reads_is_in_its_claims_and_is_approximate(action):
    assert set(COST_CLAIMS) <= action.claims(DATA)
    for claim_id in COST_CLAIMS:
        rule = rule_by_id(claim_id)
        assert rule.approximate and rule.approximate_reason, claim_id
    assert "recombinator.cost_per_combine" not in action.claims(DATA)
    assert ALPHA  # the exponent axis stays
