"""The corruption claims and the pools data of ticket #92, admitted by ticket #255 (B4, ADR-0036 to ADR-0039).

The 27 draft claims of the research note (17 in `corruption.yaml`, 10 in `tainted.yaml`) load with the
edits and additions the ADRs name: three claims marked `approximate` (the brick, the jewel brick, the
Locus share with its interval), two `owner` claims, and the reworded `fossils.bloodstained_is_corruption`.
The note and the pools JSON sit under `docs/research/`.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from crafting_system.rules import SourceKind, load_registry

RESEARCH = Path(__file__).resolve().parents[1] / "docs" / "research"
NOTE = RESEARCH / "2026-10-31-corruption.md"
POOLS = RESEARCH / "2026-10-31-corruption-implicit-pools.json"

ISSUE_95 = "https://github.com/Rasslabsya4el/crafting-system/issues/95#issuecomment-6556328111"

CORRUPTION_IDS = {
    "corruption.vaal_equipment_four_outcomes",
    "corruption.vaal_uniform_in_coe_code",
    "corruption.vaal_socket_outcome_3_29",
    "corruption.vaal_brick_rare_six_mods",
    "corruption.implicit_replaces_existing",
    "corruption.implicit_pool_by_item_class",
    "corruption.implicit_pool_matches_coe",
    "corruption.locus_four_outcomes",
    "corruption.locus_two_implicit_share_observed",
    "corruption.locus_second_implicit_other_group",
    "corruption.locus_no_preview",
    "corruption.corrupted_modifiable_exceptions",
    "corruption.bench_corrupted_extra_vaal",
    "corruption.bloodstained_fossil_implicit",
    "corruption.vaal_incompatible_with_allflame",
    "corruption.jewel_vaal_outcomes",
    "corruption.jewel_implicit_pool",
    # added by the ADRs
    "corruption.jewel_brick_fills_to_limit",
    "corruption.bloodstained_never_fails",
    "corruption.locus_two_implicit_share_decision",
}

TAINTED_IDS = {
    "tainted.chaos_reforge_or_clear",
    "tainted.exalted_add_or_remove",
    "tainted.divine_teardrop_tier_step",
    "tainted.jeweller_even_split",
    "tainted.fusing_even_split",
    "tainted.chromatic_forces_non_white",
    "tainted.scrap_whetstone_random_max_20",
    "tainted.catalyst_random_type_and_amount",
    "tainted.catalyst_source_trialmaster",
    "tainted.source_beyond",
}

# The three claims of the ticket, then the three more that an ADR calls "marked approximate".
TICKET_APPROXIMATE = {
    "corruption.vaal_brick_rare_six_mods",  # ADR-0037
    "corruption.jewel_brick_fills_to_limit",  # ADR-0037
    "corruption.locus_two_implicit_share_decision",  # ADR-0038
}
ADR_APPROXIMATE = {
    "corruption.locus_second_implicit_other_group",  # ADR-0038: the only support is Craft of Exile's code
    "tainted.jeweller_even_split",  # ADR-0036 "Sockets": a community test of unknown size
    "tainted.fusing_even_split",  # ADR-0036 "Sockets": the same
}


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def family(registry, name):
    return {rule_id for rule_id in registry if rule_id.startswith(name + ".")}


# --- the claims load ---------------------------------------------------------------------------


def test_every_corruption_and_tainted_claim_is_in_the_registry(registry):
    assert family(registry, "corruption") == CORRUPTION_IDS
    assert family(registry, "tainted") == TAINTED_IDS


def test_the_27_draft_claims_and_the_three_additions_are_counted(registry):
    assert len(family(registry, "corruption")) == 17 + 3
    assert len(family(registry, "tainted")) == 10


def test_every_claim_is_checked_on_the_pinned_patch_with_its_provenance(registry):
    for rule_id in CORRUPTION_IDS | TAINTED_IDS:
        rule = registry[rule_id]
        assert rule.date_checked.year == 2026, rule_id
        assert rule.patch_verified in {"3.29.3.3", "3.23.0"}, rule_id
        assert rule.url.startswith("https://"), rule_id
        assert 0 < len(rule.quote) <= 400, rule_id


# --- approximate claims carry their reason; the share carries its interval ---------------------


@pytest.mark.parametrize("rule_id", sorted(TICKET_APPROXIMATE | ADR_APPROXIMATE))
def test_an_approximate_corruption_claim_carries_its_reason(registry, rule_id):
    rule = registry[rule_id]

    assert rule.approximate is True
    assert rule.approximate_reason.strip()
    assert "\n" not in rule.approximate_reason


def test_only_the_named_corruption_and_tainted_claims_are_approximate(registry):
    marked = {
        rule_id
        for rule_id in CORRUPTION_IDS | TAINTED_IDS
        if registry[rule_id].approximate
    }

    assert marked == TICKET_APPROXIMATE | ADR_APPROXIMATE


def test_the_brick_reason_names_both_readings(registry):
    reason = registry["corruption.vaal_brick_rare_six_mods"].approximate_reason

    assert "wiki" in reason
    assert "Craft of Exile" in reason


def test_the_locus_share_decision_is_the_owners_25_percent_with_its_interval(registry):
    rule = registry["corruption.locus_two_implicit_share_decision"]

    assert rule.source_kind is SourceKind.OWNER
    assert rule.url == ISSUE_95
    assert rule.approximate_reason == (
        "sources disagree: wiki, Craft of Exile and one sheet 25% to 26.5%; other counts 8.8%"
    )
    assert dict(rule.value) == {"share": 0.25, "interval_low": 0.088, "interval_high": 0.265}
    assert rule.value["interval_low"] < rule.value["share"] < rule.value["interval_high"]


def test_the_observed_share_stays_as_the_evidence(registry):
    rule = registry["corruption.locus_two_implicit_share_observed"]

    assert rule.source_kind is SourceKind.EXPERIMENT
    assert not rule.approximate
    assert dict(rule.value) == {"n": 1612, "two_implicits": 427}


def test_the_jewel_brick_claim_rests_on_craft_of_exile(registry):
    rule = registry["corruption.jewel_brick_fills_to_limit"]

    assert rule.source_kind is SourceKind.COE
    assert "four" in rule.statement.lower()
    assert rule.quote == 'poec_simRerollItem("rare",null,null,6,!0,!1,!1,!1,null,!1,!1,!1,!1)'
    assert dict(rule.value) == {"affixes": 4}


def test_bloodstained_never_fails_is_an_owner_claim_that_is_not_approximate(registry):
    rule = registry["corruption.bloodstained_never_fails"]

    assert rule.source_kind is SourceKind.OWNER
    assert rule.url == ISSUE_95
    assert not rule.approximate
    assert "never fails" in rule.quote


def test_the_brick_claim_is_marked_but_keeps_its_wiki_source(registry):
    rule = registry["corruption.vaal_brick_rare_six_mods"]

    assert rule.source_kind is SourceKind.WIKI
    assert dict(rule.value) == {"affixes": 6}


def test_the_vaal_orb_split_is_not_approximate(registry):
    rule = registry["corruption.vaal_equipment_four_outcomes"]

    assert not rule.approximate
    assert sum(rule.value.values()) == pytest.approx(1)
    assert set(rule.value) == {"implicit", "socket_colour", "brick", "nothing"}


def test_the_locus_split_is_four_equal_outcomes(registry):
    rule = registry["corruption.locus_four_outcomes"]

    assert sum(rule.value.values()) == pytest.approx(1)
    assert set(rule.value.values()) == {0.25}


def test_the_tainted_even_splits_are_half_and_half(registry):
    for rule_id in ("tainted.jeweller_even_split", "tainted.fusing_even_split"):
        assert dict(registry[rule_id].value) == {"add": 0.5, "remove": 0.5}


# --- the reworded fossil claim ------------------------------------------------------------------


def test_the_bloodstained_fossil_claim_points_to_corruption(registry):
    rule = registry["fossils.bloodstained_is_corruption"]

    assert rule.source_kind is SourceKind.WIKI
    assert rule.date_checked >= date(2026, 11, 1)
    assert "ADR-0038" in rule.statement
    assert "corruption.bloodstained_never_fails" in rule.statement
    assert "out of scope" not in rule.statement
    assert "corrupted implicit" in rule.statement


# --- the note and the pools JSON under docs/research --------------------------------------------


def test_the_note_is_under_docs_research():
    text = NOTE.read_text(encoding="utf-8")

    assert text.startswith("# Corruption and Tainted currencies in 3.29 (ticket #92)")
    assert "## 8. Draft claims" in text
    assert POOLS.name in text


def test_the_claims_name_only_research_files_that_exist(registry):
    for rule_id in CORRUPTION_IDS | TAINTED_IDS:
        statement = registry[rule_id].statement
        if "docs/research/" in statement:
            name = statement.split("docs/research/")[1].split()[0].rstrip(".,;)")
            assert (RESEARCH / name).is_file(), (rule_id, name)


# Mods and total weight per class at an item level that cuts nothing (the note's section 4 and ADR-0037).
POOL_PINS = {
    "Ring": (39, 31_850),
    "Amulet": (30, 28_500),
    "Belt": (19, 18_500),
    "Body Armour": (21, 20_500),
    "Boots": (25, 21_500),
    "Gloves": (28, 27_500),
    "Helmet": (29, 27_750),
    "Shield": (27, 26_500),
    "Quiver": (25, 19_850),
    "Bow": (27, 21_900),
    "Claw": (16, 13_750),
    "Dagger": (20, 17_000),
    "Rune Dagger": (27, 20_250),
    "Wand": (24, 17_250),
    "Sceptre": (20, 14_750),
    "Staff": (28, 24_250),
    "Warstaff": (24, 21_000),  # the class holds a second group of three rod bases, see WARSTAFF_RODS
    "One Hand Axe": (12, 11_250),
    "One Hand Mace": (11, 10_250),
    "One Hand Sword": (12, 11_250),
    "Thrusting One Hand Sword": (9, 9_000),
    "Two Hand Axe": (18, 17_250),
    "Two Hand Mace": (15, 14_250),
    "Two Hand Sword": (15, 13_750),
    "FishingRod": (5, 5_000),
    "Jewel": (21, 21_000),
    "AbyssJewel": (21, 21_000),
}


WARSTAFF_RODS = (28, 24_250)  # Capacity Rod and Potentiality Rod share the item class with the warstaves


@pytest.fixture(scope="module")
def pools():
    return json.loads(POOLS.read_text(encoding="utf-8"))


def mods_of(pools, name, item_level=100, variant=0):
    return [mod for mod in pools[name][variant]["mods"] if mod["required_level"] <= item_level]


def test_the_pools_json_holds_every_class_of_the_note(pools):
    assert set(pools) == set(POOL_PINS)


@pytest.mark.parametrize("name", sorted(POOL_PINS))
def test_a_class_pool_has_the_mods_and_weight_of_the_note(pools, name):
    mods = mods_of(pools, name)
    count, weight = POOL_PINS[name]

    assert (len(mods), sum(mod["weight"] for mod in mods)) == (count, weight)
    assert len({mod["id"] for mod in mods}) == len(mods)


def test_the_rods_of_the_warstaff_class_have_a_pool_of_their_own(pools):
    assert len(pools["Warstaff"]) == 2
    mods = mods_of(pools, "Warstaff", variant=1)

    assert (len(mods), sum(mod["weight"] for mod in mods)) == WARSTAFF_RODS
    assert pools["Warstaff"][1]["example_bases"][0] == "Capacity Rod"


def test_a_ring_of_item_level_80_loses_the_three_added_damage_tiers(pools):
    assert sum(mod["weight"] for mod in mods_of(pools, "Ring", 80)) == 31_100
    assert len(mods_of(pools, "Ring", 80)) == 36


def test_four_mods_of_each_jewel_pool_need_item_level_33_to_60(pools):
    for name in ("Jewel", "AbyssJewel"):
        levels = sorted(mod["required_level"] for mod in mods_of(pools, name) if mod["required_level"] > 1)

        assert levels == [33, 40, 40, 60]
        assert {mod["weight"] for mod in mods_of(pools, name)} == {1000}
