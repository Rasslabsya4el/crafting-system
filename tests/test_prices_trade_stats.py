"""Mapping repoe mods and stat texts to trade stat ids (#39): text normalization, lookup, resolution."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from crafting_system.prices.trade_query import (
    INFLUENCE_STAT_IDS,
    BuyMod,
    BuySpec,
    StatFilter,
    TradeSpecError,
    build_query,
)
from crafting_system.prices.trade_stats import (
    normalize_text,
    parse_trade_stats,
    resolve_buy_mod,
)
from repoe_support import fixture_game_data

STATS_FILE = Path(__file__).resolve().parent / "fixtures" / "trade" / "stats_excerpt.json"
RECORDED_STATS_FILE = Path(__file__).resolve().parent / "fixtures" / "trade" / "recorded" / "stats_excerpt.json"


@pytest.fixture(scope="module")
def stats():
    return parse_trade_stats(json.loads(STATS_FILE.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def recorded():
    return parse_trade_stats(json.loads(RECORDED_STATS_FILE.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def game_mods():
    return tuple(fixture_game_data().mods.values())


# -- normalize_text -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("repoe_text", "trade_text", "expected"),
    [
        (
            "+(6-11)% to Lightning Resistance",
            "+#% to Lightning Resistance",
            "+#% to lightning resistance",
        ),
        (
            "+1 to Level of all Lightning Skill Gems",
            "+# to Level of all Lightning Skill Gems",
            "+# to level of all lightning skill gems",
        ),
        ("Adds (3-5) to (6-7) Fire Damage", "Adds # to # Fire Damage", "adds # to # fire damage"),
        (
            "(10-14)% increased Rarity of Items found",
            "#% increased Rarity of Items found",
            "#% increased rarity of items found",
        ),
        (
            "40% increased Global Accuracy Rating",
            "#% increased Global Accuracy Rating",
            "#% increased global accuracy rating",
        ),
    ],
)
def test_repoe_text_and_trade_text_normalize_to_one_key(repoe_text, trade_text, expected):
    assert normalize_text(repoe_text) == expected
    assert normalize_text(trade_text) == expected


def test_normalize_text_handles_negative_ranges_and_decimals():
    assert normalize_text("(-10--5)% to Fire Resistance") == "#% to fire resistance"
    assert normalize_text("(1.5-2.5)% of Life Regenerated per second") == (
        "#% of life regenerated per second"
    )
    assert normalize_text("Regenerate 1.5 Life per second") == "regenerate # life per second"


def test_normalize_text_collapses_whitespace_and_strips():
    assert normalize_text("  Adds  (3-5)\tto (6-7)   Fire Damage \n") == "adds # to # fire damage"


def test_normalize_text_keeps_a_leading_sign_as_shown():
    assert normalize_text("+(6-11) to Armour").startswith("+")
    assert normalize_text("-(5-9) to Armour") == "-# to armour"


# -- parse_trade_stats and ids_for --------------------------------------------------------------


def test_ids_for_finds_the_ids_of_a_group_by_normalized_text(stats):
    assert stats.ids_for("explicit", "+(6-11)% to Lightning Resistance") == (
        "explicit.stat_1671376347",
    )
    assert stats.ids_for("fractured", "+#% to LIGHTNING resistance") == (
        "fractured.stat_1671376347",
    )
    assert stats.ids_for("implicit", "+#% to Lightning Resistance") == (
        "implicit.stat_1671376347",
    )


def test_ids_for_unknown_text_or_group_is_empty(stats):
    assert stats.ids_for("explicit", "no such stat") == ()
    assert stats.ids_for("crafted", "+#% to Lightning Resistance") == ()


def test_ids_for_lists_every_id_of_a_duplicated_text(stats):
    assert stats.ids_for("explicit", "#% increased Elemental Damage") == (
        "explicit.stat_4444444444",
        "explicit.stat_5555555555",
    )


def test_the_pseudo_group_has_the_influence_stats(stats):
    assert stats.ids_for("pseudo", "Has Shaper Influence") == ("pseudo.pseudo_has_shaper_influence",)


def test_an_entry_with_options_is_still_found_by_its_text(stats):
    assert stats.ids_for("explicit", "Allocates #") == ("explicit.stat_6666666666",)


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ([], "list"),
        ({}, "result"),
        ({"result": {}}, "result"),
        ({"result": [5]}, "group"),
        ({"result": [{"label": "x", "entries": []}]}, "id"),
        ({"result": [{"id": "explicit"}]}, "entries"),
        ({"result": [{"id": "explicit", "entries": {}}]}, "entries"),
        ({"result": [{"id": "explicit", "entries": [7]}]}, "entry"),
        ({"result": [{"id": "explicit", "entries": [{"text": "x"}]}]}, "id"),
        ({"result": [{"id": "explicit", "entries": [{"id": "explicit.stat_1"}]}]}, "text"),
        ({"result": [{"id": "explicit", "entries": [{"id": 1, "text": "x"}]}]}, "id"),
    ],
)
def test_a_malformed_stats_answer_is_refused_saying_what_is_wrong(raw, fragment):
    with pytest.raises(TradeSpecError) as error:
        parse_trade_stats(raw)

    assert fragment in str(error.value)


# -- resolve_buy_mod ----------------------------------------------------------------------------


def test_the_r12_family_resolves_to_the_fractured_stat(stats, game_mods):
    found = resolve_buy_mod(BuyMod("LightningResistance", fractured=True), game_mods, stats)

    assert found == StatFilter("fractured.stat_1671376347")


def test_the_r12_family_resolves_to_the_explicit_stat_when_not_fractured(stats, game_mods):
    found = resolve_buy_mod(BuyMod("LightningResistance", minimum=30), game_mods, stats)

    assert found == StatFilter("explicit.stat_1671376347", min=30)


def test_stat_text_resolves_the_same_as_the_family(stats, game_mods):
    by_text = resolve_buy_mod(BuyMod("+#% to Lightning Resistance", fractured=True), game_mods, stats)
    by_repoe_text = resolve_buy_mod(
        BuyMod("+(6-11)% to Lightning Resistance", fractured=True), game_mods, stats
    )

    assert by_text == by_repoe_text == StatFilter("fractured.stat_1671376347")


def test_a_two_number_family_resolves(stats, game_mods):
    found = resolve_buy_mod(BuyMod("FireDamage", minimum=3), game_mods, stats)

    assert found == StatFilter("explicit.stat_2222222222", min=3)


def test_a_family_whose_tiers_have_different_texts_is_refused_listing_them(stats, game_mods):
    with pytest.raises(TradeSpecError) as error:
        resolve_buy_mod(BuyMod("WeaponCasterDamagePrefix"), game_mods, stats)

    message = str(error.value)
    assert "#% increased spell damage" in message
    assert "#% increased fire damage" in message


def test_a_hybrid_family_is_refused(stats, game_mods):
    with pytest.raises(TradeSpecError) as error:
        resolve_buy_mod(BuyMod("IncreasedPhysicalDamageReductionRating"), game_mods, stats)

    assert "hybrid mods are not supported" in str(error.value)


def test_text_that_no_trade_stat_has_is_refused_with_the_searched_text(stats, game_mods):
    with pytest.raises(TradeSpecError) as error:
        resolve_buy_mod(BuyMod("+(1-5) to Imaginary Stat"), game_mods, stats)

    message = str(error.value)
    assert "no trade stat" in message
    assert "explicit" in message
    assert "+# to imaginary stat" in message


def test_the_group_matters_for_the_lookup(stats, game_mods):
    with pytest.raises(TradeSpecError) as error:
        resolve_buy_mod(BuyMod("+# to Level of all Lightning Skill Gems", fractured=True), game_mods, stats)

    assert "fractured" in str(error.value)


def test_a_text_with_several_trade_ids_is_refused_listing_them(stats, game_mods):
    with pytest.raises(TradeSpecError) as error:
        resolve_buy_mod(BuyMod("ElementalDamagePercent"), game_mods, stats)

    message = str(error.value)
    assert "explicit.stat_4444444444" in message
    assert "explicit.stat_5555555555" in message


GEM_LEVEL_SIBLINGS = {
    "GlobalFireGemLevel1_",
    "GlobalColdGemLevel1__",
    "GlobalPhysicalGemLevel1_",
    "GlobalChaosGemLevel1",
}


def test_a_gem_level_family_resolves_through_its_text(stats, game_mods):
    # The real family has five texts (fire, cold, lightning, physical, chaos); this test keeps
    # only the Lightning member, so the family has one text.
    lightning_only = [mod for mod in game_mods if mod.id not in GEM_LEVEL_SIBLINGS]

    found = resolve_buy_mod(BuyMod("GlobalDamageTypeGemLevel"), lightning_only, stats)

    assert found == StatFilter("explicit.stat_1111111111")


def test_the_whole_gem_level_family_of_the_game_data_has_different_texts(stats, game_mods):
    # A real-data fact: the five mods of GlobalDamageTypeGemLevel say five different things.
    with pytest.raises(TradeSpecError, match="different texts"):
        resolve_buy_mod(BuyMod("GlobalDamageTypeGemLevel"), game_mods, stats)


# -- the "(Local)" suffix and the recorded R12 stats (#39) --------------------------------------


def stats_of(*entries):
    return parse_trade_stats(
        {"result": [{"id": "explicit", "entries": [{"id": i, "text": t} for i, t in entries]}]}
    )


def test_a_text_without_the_local_suffix_finds_the_local_stat_of_the_recorded_list(recorded):
    assert recorded.ids_for("explicit", "Adds (1-3) to (5-9) Lightning Damage") == (
        "explicit.stat_3336890334",
    )
    found = resolve_buy_mod(BuyMod("Adds # to # Lightning Damage", minimum=2), [], recorded)
    assert found == StatFilter("explicit.stat_3336890334", min=2)


def test_the_plain_text_wins_over_the_local_one_when_both_exist():
    stats = stats_of(("explicit.stat_1", "#% increased Armour"), ("explicit.stat_2", "#% increased Armour (Local)"))

    assert stats.ids_for("explicit", "#% increased Armour") == ("explicit.stat_1",)


def test_two_local_stats_with_one_text_stay_an_error():
    stats = stats_of(("explicit.stat_1", "Adds # Damage (Local)"), ("explicit.stat_2", "Adds # Damage (Local)"))

    with pytest.raises(TradeSpecError, match="explicit.stat_1"):
        resolve_buy_mod(BuyMod("Adds # Damage"), [], stats)


def test_the_local_suffix_is_tried_in_the_same_group_only():
    stats = parse_trade_stats(
        {"result": [{"id": "implicit", "entries": [{"id": "implicit.stat_9", "text": "Adds # Damage (Local)"}]}]}
    )

    assert stats.ids_for("explicit", "Adds # Damage") == ()


def test_the_r12_lightning_resistance_resolves_on_the_recorded_list(recorded):
    fractured = resolve_buy_mod(BuyMod("+#% to Lightning Resistance", fractured=True), [], recorded)
    explicit = resolve_buy_mod(BuyMod("+#% to Lightning Resistance"), [], recorded)

    assert fractured == StatFilter("fractured.stat_1671376347")
    assert explicit == StatFilter("explicit.stat_1671376347")


def test_the_r12_target_prefix_resolves_on_the_recorded_list(recorded):
    found = resolve_buy_mod(BuyMod("+# to Level of all Lightning Skill Gems"), [], recorded)

    assert found == StatFilter("explicit.stat_1147690586")


def test_the_six_influence_pseudo_ids_exist_on_the_recorded_list(recorded):
    listed = {entry.id for entry in recorded.entries if entry.group == "pseudo"}

    assert len(INFLUENCE_STAT_IDS) == 6
    assert set(INFLUENCE_STAT_IDS.values()) <= listed


# -- a mod named by stat text or mod id, not only by family (#47) -------------------------------

LIGHTNING_GEM_LEVEL_TEXT = "+1 to Level of all Lightning Skill Gems"


def test_one_member_of_a_multi_text_family_is_named_by_its_stat_text(stats, game_mods):
    found = resolve_buy_mod(BuyMod(LIGHTNING_GEM_LEVEL_TEXT), game_mods, stats)

    assert found == StatFilter("explicit.stat_1111111111")


def test_one_member_of_a_multi_text_family_is_named_by_its_mod_id(stats, game_mods):
    found = resolve_buy_mod(BuyMod("GlobalLightningGemLevel1", minimum=1), game_mods, stats)

    assert found == StatFilter("explicit.stat_1111111111", min=1)


def test_a_buy_spec_naming_the_lightning_gem_level_builds_a_query_with_that_stat_only(stats, game_mods):
    spec = BuySpec(name="gem level amulet", category="accessory.amulet", mods=(BuyMod(LIGHTNING_GEM_LEVEL_TEXT),))
    filters = [resolve_buy_mod(mod, game_mods, stats) for mod in spec.mods]

    body = build_query(spec, filters).body()

    assert [stat["id"] for stat in body["query"]["stats"][0]["filters"]] == ["explicit.stat_1111111111"]


def test_naming_the_whole_gem_level_family_is_still_refused_and_points_to_the_text_and_the_id(stats, game_mods):
    with pytest.raises(TradeSpecError, match="different texts") as error:
        resolve_buy_mod(BuyMod("GlobalDamageTypeGemLevel"), game_mods, stats)

    assert "stat text" in str(error.value) and "mod id" in str(error.value)


def test_a_mod_id_whose_text_the_trade_list_lacks_is_refused_with_the_searched_text(stats, game_mods):
    with pytest.raises(TradeSpecError, match="no trade stat") as error:
        resolve_buy_mod(BuyMod("GlobalFireGemLevel1_"), game_mods, stats)  # the excerpt lists only Lightning

    assert "+# to level of all fire skill gems" in str(error.value)


def test_a_hybrid_mod_named_by_id_is_refused(stats, game_mods):
    with pytest.raises(TradeSpecError, match="hybrid mods are not supported"):
        resolve_buy_mod(BuyMod("JunMaster2ArmourAndEnergyShield1"), game_mods, stats)


def test_a_name_that_is_neither_family_nor_mod_id_nor_listed_text_says_so(stats, game_mods):
    with pytest.raises(TradeSpecError, match="not a family id or mod id"):
        resolve_buy_mod(BuyMod("NoSuchFamily"), game_mods, stats)


def test_a_stat_text_does_not_need_the_game_data(stats):
    assert resolve_buy_mod(BuyMod(LIGHTNING_GEM_LEVEL_TEXT), [], stats) == StatFilter("explicit.stat_1111111111")


def test_repoe_markup_in_a_mod_text_is_stripped_before_the_lookup(stats, game_mods):
    marked = tuple(
        replace(mod, text="+(6-11)% to [Resistances|Lightning Resistance]") if "LightningResistance" in mod.families else mod
        for mod in game_mods
    )

    assert any(mod.text == "+(6-11)% to [Resistances|Lightning Resistance]" for mod in marked)
    assert normalize_text("+(6-11)% to [Resistances|Lightning Resistance]") == "+#% to lightning resistance"
    assert normalize_text("[Mana] and [Life|Health]") == "mana and health"
    assert resolve_buy_mod(BuyMod("LightningResistance"), marked, stats) == StatFilter("explicit.stat_1671376347")
