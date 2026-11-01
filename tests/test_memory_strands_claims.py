"""The Memory Strands claims in the rules registry (ticket #274, ADR-0040 to ADR-0044).

"Done when": the registry and history tests pass. This file holds the ones of this ticket: the 21 claims of the research on
strands and the 4 on the Foulborn orbs are in `rules/claims/`, with the changes of the sheet fit (#271) and the second pass (#273)
where those won; the claims the ADRs add are there and marked `approximate` where the ADRs say; and the two claims of "v1 items
carry no strands" are superseded through the claim history.
"""

import pytest

from crafting_system.rules import get_rule, load_registry

REGISTRY = load_registry()

# The 21 claims of docs/research/2026-10-31-memory-strands-claims/memory_strands.yaml.
DRAFT_STRANDS = (
    "property rollable_tiers cull_counts_eligible_tiers zero_is_no_cull cut_uses_strands_before_spend identification_is_cut"
    " spend_ranges_basic spend_ranges_chaos_family spend_ranges_essence spend_ranges_special_orbs spend_exalted_by_mod_count"
    " spend_bench_rerolls not_spent_by remembrance_action remembrance_distribution unravelling_effect unravelling_limits"
    " unravelling_ignores_metamods unravelling_needs_identified_item unravelling_chance_model unravelling_destination_tier"
).split()
# The 4 of foulborn.yaml.
DRAFT_FOULBORN = "effect_tier_cull on_stranded_item spend_ranges availability".split()
# The claims of the sheet fit (#271) that are new, and those of the second pass (#273).
SHEET_STRANDS = (
    "weights_of_kept_tiers spend_law_uniform identification_spends_none unravelling_destination_not_cut"
    " remembrance_independent_of_old_count"
).split()
SECOND_PASS_STRANDS = (
    "fossil_harvest_not_cut cut_follows_spend_table annulment_keeps_strands scouring_keeps_strands divine_keeps_strands"
    " recombinator_strands_from_either_base unravelling_skips_fractured_and_veiled unravelling_side_weight_is_whole_pool"
    " remembrance_classes_observed"
).split()
OF_THE_ADRS = ["recombination_neither_cuts_nor_spends"]
FOULBORN_NEW = "bonus_is_added_to_the_strand_denominator exalted_spend_by_mod_count zero_strand_cut_matches_eleven_strands".split()


def strands(names):
    return [f"memory_strands.{name}" for name in names]


def foulborn(names):
    return [f"foulborn.{name}" for name in names]


def test_the_21_claims_of_the_strands_research_are_promoted():
    assert len(DRAFT_STRANDS) == 21
    assert [rule_id for rule_id in strands(DRAFT_STRANDS) if rule_id not in REGISTRY] == []


def test_the_4_claims_of_the_foulborn_research_are_promoted():
    assert len(DRAFT_FOULBORN) == 4
    assert [rule_id for rule_id in foulborn(DRAFT_FOULBORN) if rule_id not in REGISTRY] == []


def test_the_claims_the_sheet_fit_and_the_second_pass_add_are_there():
    wanted = strands(SHEET_STRANDS + SECOND_PASS_STRANDS + OF_THE_ADRS) + foulborn(FOULBORN_NEW)

    assert [rule_id for rule_id in wanted if rule_id not in REGISTRY] == []


def test_the_registry_holds_exactly_these_strand_and_foulborn_claims():
    expected = set(
        strands(DRAFT_STRANDS + SHEET_STRANDS + SECOND_PASS_STRANDS + OF_THE_ADRS) + foulborn(DRAFT_FOULBORN + FOULBORN_NEW)
    )

    found = {rule_id for rule_id in REGISTRY if rule_id.startswith(("memory_strands.", "foulborn."))}

    assert found == expected


def test_the_genesis_tree_claims_stay_a_record_and_are_not_promoted():
    assert [rule_id for rule_id in REGISTRY if "genesis" in rule_id] == []
    assert not any("Genesis Tree" in rule.statement and rule.id.startswith("memory_strands.") for rule in REGISTRY.values())


# --- approximate where the ADRs say ---------------------------------------------------------------------------


APPROXIMATE = (
    # ADR-0041: the shapes and the unknowns; ADR-0043: the Remembrance bounds, the old count, the classes; ADR-0044: the destination
    strands(
        "weights_of_kept_tiers spend_law_uniform identification_spends_none spend_exalted_by_mod_count"
        " remembrance_action remembrance_distribution remembrance_independent_of_old_count remembrance_classes_observed"
        " unravelling_destination_tier unravelling_skips_fractured_and_veiled unravelling_side_weight_is_whole_pool"
        " cut_follows_spend_table fossil_harvest_not_cut annulment_keeps_strands scouring_keeps_strands divine_keeps_strands"
        " recombinator_strands_from_either_base recombination_neither_cuts_nor_spends".split()
    )
    + foulborn("effect_tier_cull bonus_is_added_to_the_strand_denominator exalted_spend_by_mod_count zero_strand_cut_matches_eleven_strands".split())
    + ["affix_pool.royale_duplicates_do_not_spawn"]
)


@pytest.mark.parametrize("rule_id", APPROXIMATE)
def test_the_claims_the_adrs_call_approximate_are_marked_with_a_reason(rule_id):
    rule = REGISTRY[rule_id]

    assert rule.approximate is True
    assert rule.approximate_reason.strip()


def test_the_unravelling_chance_is_settled_by_the_sheet_and_not_approximate():
    rule = REGISTRY["memory_strands.unravelling_chance_model"]

    assert rule.approximate is False
    assert dict(rule.value) == {"chance": "min(1, s * W_up / (2 * W_side))", "constant": 1, "divisor": 2}


def test_the_wiki_claims_that_nobody_doubts_are_not_approximate():
    for rule_id in strands("property rollable_tiers spend_ranges_basic spend_ranges_chaos_family spend_ranges_essence".split()):
        assert REGISTRY[rule_id].approximate is False, rule_id


# --- the values the later tickets read -----------------------------------------------------------------------------


def tiers_kept(total: int, strands_: int, *, foulborn_orb: bool = False) -> int:
    """K of ADR-0040 from the numbers of the claim `memory_strands.rollable_tiers`, in integers."""
    value = REGISTRY["memory_strands.rollable_tiers"].value
    rating = value["base_rating"]
    if strands_ >= 1:
        rating += value["strand_rating_per_strand"] * strands_ + value["strand_rating_offset"]
    if foulborn_orb:
        rating += value["foulborn_rating"]
    return value["numerator"] * (total - 1) // rating + 1


def test_the_cut_values_give_the_wiki_breakpoints():
    assert [tiers_kept(8, s) for s in (80, 81, 82)] == [3, 3, 2]  # 8 tiers at 81 strands is exactly 2.0 before the floor
    assert tiers_kept(13, 1) == 9  # one strand already leaves 9 of 13 tiers
    assert [tiers_kept(total, 0) for total in range(1, 14)] == list(range(1, 14))  # no strands, no cut


def test_the_cut_values_give_the_wiki_list_of_a_foulborn_orb_on_an_item_with_no_strands():
    assert [tiers_kept(total, 0, foulborn_orb=True) for total in range(1, 14)] == [1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7]


def test_a_foulborn_orb_adds_75_to_the_denominator_of_a_stranded_item_as_30_strands_do():
    for total in (3, 8, 13):
        for count in (1, 20, 57):
            assert tiers_kept(total, count, foulborn_orb=True) == tiers_kept(total, count + 30)


def test_the_foulborn_exalted_row_is_the_emulators_values_by_the_mods_before_the_craft():
    rule = REGISTRY["foulborn.exalted_spend_by_mod_count"]

    assert rule.value == (46, 52, 56, 60, 62, 66)
    assert rule.approximate


def test_the_plain_exalted_row_is_the_wikis_moved_by_one_mod_and_exceeds_the_sheets_spends():
    ceilings = REGISTRY["memory_strands.spend_exalted_by_mod_count"].value["ceiling_by_mods_before"]

    assert dict(ceilings) == {0: 16, 1: 22, 2: 26, 3: 32, 4: 34, 5: 38}
    assert ceilings[4] >= 33 and ceilings[5] >= 38  # the two crafts of the sheet that broke the planned 32 and 34


def test_the_spend_law_is_uniform_and_chaos_and_alchemy_have_no_bins():
    law = REGISTRY["memory_strands.spend_law_uniform"]

    assert dict(law.value) == {"shape": "uniform_integer", "lowest": 0, "count_after": "max(0, count - draw)"}
    assert not any("bins" in rule.id for rule in REGISTRY.values() if rule.id.startswith("memory_strands."))
    assert dict(REGISTRY["memory_strands.spend_ranges_chaos_family"].value) == {"alchemy": 50, "binding": 50, "chaos": 50, "chance": 50}


def test_the_kept_tiers_weigh_their_old_weight_times_t_over_k():
    rule = REGISTRY["memory_strands.weights_of_kept_tiers"]

    assert dict(rule.value) == {"reading": "refactored", "factor": "T/K"}


def test_the_remembrance_count_is_the_normal_35_25_accepted_from_10_below_100_5_and_rounded():
    rule = REGISTRY["memory_strands.remembrance_distribution"]

    assert dict(rule.value) == {"mean": 35, "sd": 25, "accept_from": 10, "accept_below": 100.5, "rounding": "nearest"}


def test_the_royale_duplicates_are_four_mod_ids_of_the_export():
    rule = REGISTRY["affix_pool.royale_duplicates_do_not_spawn"]

    assert set(rule.value["excluded_ids"]) == {
        "MovementVelocity2Royale",
        "IncreasedCastSpeed2Royale",
        "IncreasedAttackSpeed2Royale",
        "LocalIncreasedAttackSpeed2Royale____",
    }


def test_the_unravelling_exclusions_are_claims():
    assert "fractured" in REGISTRY["memory_strands.unravelling_skips_fractured_and_veiled"].statement
    assert "veiled" in REGISTRY["memory_strands.unravelling_skips_fractured_and_veiled"].statement
    assert "crafted" in REGISTRY["memory_strands.unravelling_limits"].statement
    assert "Elevated" in REGISTRY["memory_strands.unravelling_limits"].statement


def test_a_recombination_neither_cuts_nor_spends_and_hands_over_either_base_count():
    assert "no part in the strand cut" in REGISTRY["memory_strands.recombination_neither_cuts_nor_spends"].statement
    assert "spends no strands" in REGISTRY["memory_strands.recombination_neither_cuts_nor_spends"].statement
    assert "migrate" in REGISTRY["memory_strands.recombinator_strands_from_either_base"].quote


# --- superseded through the claim history (#120) ---------------------------------------------------------------------


def test_no_memory_strands_is_rewritten_and_keeps_the_old_text_in_its_history():
    rule = get_rule("affix_pool.no_memory_strands")

    assert "carry no Memory Strands" not in rule.statement
    assert "start item" in rule.statement and "memory_strands" in rule.statement
    assert len(rule.history) == 1
    old = rule.history[0]
    assert old.statement == "The planner's items carry no Memory Strands, so a draw is not tier-gated and the ordinary pool applies."
    assert old.held_until == "3.29.3.3"
    assert old.source_kind.value == "wiki"


def test_the_bench_rerolls_claim_is_rewritten_and_keeps_the_old_text_in_its_history():
    rule = get_rule("bench_craft.rerolls_not_b1_actions")

    assert "which v1 start items do not carry" not in rule.statement
    assert "50" in rule.statement and "memory_strands.spend_bench_rerolls" in rule.statement
    assert len(rule.history) == 1
    old = rule.history[0]
    assert "which v1 start items do not carry" in old.statement
    assert old.quote == "v1 start items carry no Memory Strands until Memory Strands get their batch"


def test_the_superseded_claims_still_load_for_the_code_that_reads_them():
    # The pool no longer holds `NO_MEMORY_STRANDS` (ticket #275: it takes the item's count through a `Cut`); the bench still reads its claim.
    from crafting_system.actions import pool
    from crafting_system.actions.bench import REROLLS_NOT_B1

    assert not hasattr(pool, "NO_MEMORY_STRANDS")
    assert REROLLS_NOT_B1 == REGISTRY["bench_craft.rerolls_not_b1_actions"]
