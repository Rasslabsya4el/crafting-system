"""The claims of `rules/claims/sockets.yaml` and the price names of the socket family (ticket #228, B6 S2; ADR-0047 "Marks and claims").

The marks are those of the ADR's table, written out here and not read from the file: a claim is `approximate` exactly where the table says so.
The registry and history tests (`test_rules_registry.py`, `test_rules_history.py`) run on the same file, so a claim of the wrong form fails there.
"""

from fractions import Fraction

from crafting_system.actions import BenchSocketCount, BenchSocketLinks, JewellersOrb, OrbOfFusing
from crafting_system.prices.price_names import (
    ARMOURERS_SCRAP,
    BLACKSMITHS_WHETSTONE,
    CHROMATIC_ORB,
    CRAICIC_SAND_SPITTER,
    CRAICIC_SHIELD_CRAB,
    JEWELLERS_ORB,
    OMEN_OF_CONNECTIONS,
    OMEN_OF_THE_JEWELLER,
    OMEN_OF_TRICHROMATISM,
    ORB_OF_BINDING,
    ORB_OF_FUSING,
    SOCKET_PRICE_NAMES,
    THE_BLACK_MORRIGAN,
)
from crafting_system.rules import SourceKind, load_registry, rule_by_id

REGISTRY = load_registry()
SOCKET_CLAIMS = {rule_id: rule for rule_id, rule in REGISTRY.items() if rule_id.startswith("sockets.")}

RESEARCH_CLAIMS = {  # the 25 draft claims of the research (ticket #99), the Binding claim replaced (ADR-0048)
    "sockets_white_by_default", "added_sockets_are_white", "chromatic_forces_one_non_white", "chromatic_roll_then_force",
    "chromatic_nonwhite_chance", "chromatic_natural_colour_weights", "chromatic_colour_weighted_by_requirements",
    "chromatic_ignores_abyssal_sockets", "jeweller_rerolls_count_to_a_different_number", "socket_count_weights",
    "quality_one_percent_per_percent", "fusing_rerolls_links_only", "fusing_six_link_sample", "fusing_group_size_weights",
    "bench_socket_count_cost", "bench_link_cost", "bench_colour_cost", "bench_on_corrupted_costs_vaal",
    "omen_of_the_jeweller_max_sockets", "omen_of_connections_all_linked", "omen_of_trichromatism",
    "black_morrigan_max_links_and_sockets", "chromatic_not_sold_by_vendors", "vorici_add_remove_trick_gone",
}
BINDING_REPLACED = "binding_normal_to_rare_four_links"
WIKI_CLAIMS = {"class_maximum_sockets", "quality_currency_gain_by_item_level", "binding_rolls_like_alchemy"}
OWNER_CLAIMS = {  # the owner's answers of grill B6 round 1, and the readings of the design that carry its mark
    "jeweller_keeps_old_sockets_when_adding", "chromatic_one_socket_always_coloured", "chromatic_never_repeats_the_current_colours",
    "omen_of_trichromatism_below_three_sockets", "binding_links_existing_sockets", "black_morrigan_maximum_is_the_class_maximum",
    "jeweller_removes_sockets_from_the_end", "chromatic_ignores_requirement_mods", "jeweller_ignores_quality",
    "bench_link_makes_the_first_sockets_one_group", "bench_at_least_n_non_white_is_a_conditioned_roll",
    "omen_of_trichromatism_conditions_the_roll",
}
OTHER_CLAIMS = {  # derived claims of the table: the forced colour, the second reading, Binding's loss, the price names
    "chromatic_forced_socket_colour", "jeweller_second_reading_2014_table", "binding_loses_sockets_above_four",
    "jewellers_orb_cost", "fusing_cost", "omen_of_the_jeweller_cost", "omen_of_connections_cost",
}

# ADR-0047, "Marks and claims": the claims that are `approximate`
APPROXIMATE = {
    "chromatic_forced_socket_colour", "chromatic_never_repeats_the_current_colours", "chromatic_ignores_requirement_mods",  # Chromatic
    "fusing_group_size_weights",  # the group-size table at 20% quality
    "socket_count_weights", "jeweller_second_reading_2014_table", "jeweller_ignores_quality", "jeweller_removes_sockets_from_the_end",
    "bench_link_makes_the_first_sockets_one_group", "bench_at_least_n_non_white_is_a_conditioned_roll", "omen_of_trichromatism_conditions_the_roll",
    "class_maximum_sockets",
    "omen_of_trichromatism_below_three_sockets",  # the owner does not know (answer 3e)
    "binding_loses_sockets_above_four", "black_morrigan_maximum_is_the_class_maximum",  # ADR-0048
}
UNMARKED = {  # ADR-0047: "none" in the table
    "chromatic_nonwhite_chance", "chromatic_natural_colour_weights", "chromatic_roll_then_force", "chromatic_one_socket_always_coloured",
    "bench_socket_count_cost", "bench_link_cost", "bench_colour_cost", "omen_of_the_jeweller_max_sockets", "omen_of_connections_all_linked",
    "jewellers_orb_cost", "fusing_cost", "omen_of_the_jeweller_cost", "omen_of_connections_cost",
    "jeweller_keeps_old_sockets_when_adding", "binding_links_existing_sockets",
}


def ids(*names) -> set[str]:
    return {f"sockets.{name}" for names_ in names for name in names_}


def test_the_file_holds_the_research_claims_the_wiki_claims_and_the_owners_answers():
    """Later tickets add claims to the file (the Chromatic Orb, Binding, the beasts), so the test asks for these and not for no others."""
    assert ids(RESEARCH_CLAIMS, WIKI_CLAIMS, OWNER_CLAIMS, OTHER_CLAIMS) <= set(SOCKET_CLAIMS)
    assert len(RESEARCH_CLAIMS) == 24 and len(RESEARCH_CLAIMS | {BINDING_REPLACED}) == 25  # the 25th, Binding's, is replaced
    assert f"sockets.{BINDING_REPLACED}" not in SOCKET_CLAIMS


def test_the_binding_claim_is_replaced_by_the_owners_and_the_wikis():
    assert SOCKET_CLAIMS["sockets.binding_links_existing_sockets"].source_kind is SourceKind.OWNER
    assert SOCKET_CLAIMS["sockets.binding_rolls_like_alchemy"].source_kind is SourceKind.WIKI
    assert "never adds sockets" in SOCKET_CLAIMS["sockets.binding_links_existing_sockets"].statement


def test_the_three_claims_checked_on_the_wiki_carry_that_date():
    for name in WIKI_CLAIMS:
        rule = SOCKET_CLAIMS[f"sockets.{name}"]
        assert rule.source_kind is SourceKind.WIKI and str(rule.date_checked) == "2026-11-01" and rule.patch_verified == "3.29.3.3"
    gain = SOCKET_CLAIMS["sockets.quality_currency_gain_by_item_level"]
    assert "item level" in gain.statement and "0.8.1" in gain.statement  # the old rule is named as the old one


def test_the_owners_answers_are_claims_of_kind_owner_with_their_source():
    for name in ("jeweller_keeps_old_sockets_when_adding", "chromatic_one_socket_always_coloured", "chromatic_never_repeats_the_current_colours",
                 "omen_of_trichromatism_below_three_sockets", "binding_links_existing_sockets", "black_morrigan_maximum_is_the_class_maximum"):
        rule = SOCKET_CLAIMS[f"sockets.{name}"]
        assert rule.source_kind is SourceKind.OWNER and rule.url.endswith("issues/104#issuecomment-6556328366"), name


def test_the_claims_carry_the_marks_of_adr_0047():
    for name in APPROXIMATE:
        rule = SOCKET_CLAIMS[f"sockets.{name}"]
        assert rule.approximate and rule.approximate_reason, name
    for name in UNMARKED:
        assert not SOCKET_CLAIMS[f"sockets.{name}"].approximate, name


def test_siverans_formula_is_unmarked_for_the_owner_took_it_as_the_rule():
    for name in ("chromatic_nonwhite_chance", "chromatic_roll_then_force", "chromatic_natural_colour_weights"):
        assert not SOCKET_CLAIMS[f"sockets.{name}"].approximate
    assert SOCKET_CLAIMS["sockets.chromatic_nonwhite_chance"].value["quality_cap"] == 30
    value = SOCKET_CLAIMS["sockets.chromatic_nonwhite_chance"].value
    assert Fraction(value["slope_numerator"], value["slope_denominator"]) == Fraction(375, 100_000) and value["level_offset"] == 14


def test_the_values_the_actions_read():
    fusing = SOCKET_CLAIMS["sockets.fusing_group_size_weights"].value
    assert tuple(fusing["parts_of_100000"]) == (17818, 34818, 26766, 19672, 826, 100) and sum(fusing["parts_of_100000"]) == 100_000
    assert fusing["at_quality"] == 20
    weights = SOCKET_CLAIMS["sockets.socket_count_weights"].value
    assert tuple(weights["six_or_three"]) == (50, 120, 100, 30, 5, 1) and tuple(weights["four"]) == (100, 90, 80, 30)
    assert tuple(weights["minimum_item_level"]) == (1, 1, 2, 25, 35, 50)
    assert tuple(SOCKET_CLAIMS["sockets.jeweller_second_reading_2014_table"].value["six_or_three"]) == (100, 90, 80, 30, 5, 1)
    assert dict(SOCKET_CLAIMS["sockets.bench_socket_count_cost"].value) == {2: 1, 3: 3, 4: 10, 5: 70, 6: 350}
    assert dict(SOCKET_CLAIMS["sockets.bench_link_cost"].value) == {2: 1, 3: 3, 4: 5, 5: 150, 6: 1500}
    assert dict(SOCKET_CLAIMS["sockets.bench_colour_cost"].value) == {2: 5, 3: 20, 4: 75}


def test_the_bench_craft_claim_no_longer_lists_the_socket_options_as_not_modelled():
    statement = REGISTRY["bench_craft.other_options_not_mod_crafts"].statement
    assert "flask enchants, Remove Enchantments, Reroll the Rarity" in statement and "flask enchants, sockets" not in statement
    assert "13 socket options" in statement and "actions/socket_orbs.py" in statement
    assert "Sockets, links and colours and the Orb of Chance have no batch yet" not in statement


# --- the price names ------------------------------------------------------------------------------------------------------------------


def test_the_price_names_are_the_names_of_the_game_and_distinct():
    assert SOCKET_PRICE_NAMES == (
        JEWELLERS_ORB, ORB_OF_FUSING, CHROMATIC_ORB, ORB_OF_BINDING, OMEN_OF_THE_JEWELLER, OMEN_OF_CONNECTIONS, OMEN_OF_TRICHROMATISM,
        BLACKSMITHS_WHETSTONE, ARMOURERS_SCRAP, THE_BLACK_MORRIGAN, CRAICIC_SHIELD_CRAB, CRAICIC_SAND_SPITTER,
    )
    assert len(set(SOCKET_PRICE_NAMES)) == 12
    assert [JEWELLERS_ORB, ORB_OF_FUSING, CHROMATIC_ORB, ORB_OF_BINDING] == ["Jeweller's Orb", "Orb of Fusing", "Chromatic Orb", "Orb of Binding"]
    assert [OMEN_OF_THE_JEWELLER, OMEN_OF_CONNECTIONS, OMEN_OF_TRICHROMATISM] == ["Omen of the Jeweller", "Omen of Connections", "Omen of Trichromatism"]
    assert [BLACKSMITHS_WHETSTONE, ARMOURERS_SCRAP] == ["Blacksmith's Whetstone", "Armourer's Scrap"]
    assert [THE_BLACK_MORRIGAN, CRAICIC_SHIELD_CRAB, CRAICIC_SAND_SPITTER] == ["The Black Mórrígan", "Craicic Shield Crab", "Craicic Sand Spitter"]


def test_the_beast_names_are_the_ones_the_claims_use():
    text = " ".join(SOCKET_CLAIMS[f"sockets.{name}"].statement + SOCKET_CLAIMS[f"sockets.{name}"].quote for name in ("black_morrigan_max_links_and_sockets", "black_morrigan_maximum_is_the_class_maximum"))
    for name in (THE_BLACK_MORRIGAN, CRAICIC_SHIELD_CRAB, CRAICIC_SAND_SPITTER):
        assert name.removeprefix("The ") in text, name


def test_the_actions_price_what_the_price_names_say():
    assert dict(SOCKET_CLAIMS["sockets.jewellers_orb_cost"].value) == {JEWELLERS_ORB: 1}
    assert dict(SOCKET_CLAIMS["sockets.fusing_cost"].value) == {ORB_OF_FUSING: 1}
    assert dict(SOCKET_CLAIMS["sockets.omen_of_the_jeweller_cost"].value) == {OMEN_OF_THE_JEWELLER: 1}
    assert dict(SOCKET_CLAIMS["sockets.omen_of_connections_cost"].value) == {OMEN_OF_CONNECTIONS: 1}
    assert JewellersOrb().resources(None) == {JEWELLERS_ORB: 1}
    assert JewellersOrb(omen=True).resources(None) == {JEWELLERS_ORB: 1, OMEN_OF_THE_JEWELLER: 1}
    assert OrbOfFusing().resources(None) == {ORB_OF_FUSING: 1}
    assert OrbOfFusing(omen=True).resources(None) == {ORB_OF_FUSING: 1, OMEN_OF_CONNECTIONS: 1}


def test_an_answer_names_the_approximate_inputs_of_each_action():
    def approximate(action) -> set[str]:
        return {rule_id for rule_id in action.claims(None) if rule_by_id(rule_id).approximate}

    assert approximate(JewellersOrb()) == ids(["socket_count_weights", "jeweller_second_reading_2014_table", "jeweller_ignores_quality",
                                              "jeweller_removes_sockets_from_the_end", "class_maximum_sockets"])
    assert approximate(JewellersOrb(omen=True)) == ids(["jeweller_ignores_quality", "jeweller_removes_sockets_from_the_end", "class_maximum_sockets"])
    assert approximate(OrbOfFusing()) == ids(["fusing_group_size_weights", "jeweller_ignores_quality", "class_maximum_sockets"])
    assert approximate(OrbOfFusing(omen=True)) == ids(["class_maximum_sockets"])
    assert approximate(BenchSocketCount(2)) == ids(["class_maximum_sockets", "jeweller_removes_sockets_from_the_end"])
    assert approximate(BenchSocketLinks(2)) == ids(["class_maximum_sockets", "bench_link_makes_the_first_sockets_one_group"])


def test_every_claim_an_action_names_is_in_the_registry():
    for action in (JewellersOrb(), JewellersOrb(omen=True), OrbOfFusing(), OrbOfFusing(omen=True), BenchSocketCount(3), BenchSocketLinks(3)):
        assert action.claims(None) <= set(REGISTRY)
        assert action.strand_claims(None) <= set(REGISTRY)
