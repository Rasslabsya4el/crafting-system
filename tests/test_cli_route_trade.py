"""The buy step of the route view: the buy filter in words and the trade-site search link (#78)."""

import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from repoe_support import fixture_game_data

from crafting_system.cli._route_trade import buy_step
from crafting_system.prices import BuyMod, BuySpec, load_buy_spec
from crafting_system.prices.trade_stats import parse_trade_stats

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trade"
R12_SPEC = load_buy_spec(FIXTURES / "r12_buy_spec.yaml")
STATS = parse_trade_stats(json.loads((FIXTURES / "stats_excerpt.json").read_text(encoding="utf-8")))
MODS = tuple(fixture_game_data().mods.values())


def query_of(url: str) -> dict:
    return json.loads(parse_qs(urlparse(url).query)["q"][0])


def test_the_link_opens_the_search_of_the_league_with_the_query_of_the_spec():
    step = buy_step(R12_SPEC, "Allflame", MODS, STATS)

    assert step.url.startswith("https://www.pathofexile.com/trade/search/Allflame?q=")
    query = query_of(step.url)["query"]
    assert query["stats"] == [
        {"type": "and", "filters": [{"id": "fractured.stat_1671376347", "disabled": False}]}
    ]
    assert query["filters"]["type_filters"]["filters"]["category"] == {"option": "accessory.amulet"}
    assert query["filters"]["misc_filters"]["filters"]["ilvl"] == {"min": 75}
    assert step.unresolved == ()


def test_the_link_is_one_url_without_spaces_or_raw_quotes():
    step = buy_step(R12_SPEC, "Mirage of Echoes", MODS, STATS)

    assert " " not in step.url and '"' not in step.url
    assert "/Mirage%20of%20Echoes?q=" in step.url
    assert unquote(step.url).count("?") == 1


def test_the_accepts_lines_are_the_buy_filter_one_per_line():
    step = buy_step(R12_SPEC, "Allflame", MODS, STATS)

    assert step.accepts == (
        "Rare",
        "item level 75 or more",
        "no influence",
        "not corrupted",
        "fractured: +#% to Lightning Resistance",
    )


def test_without_a_stat_list_the_link_has_no_mod_filter_and_the_mod_is_named_as_unresolved():
    step = buy_step(R12_SPEC, "Allflame", MODS, None)

    assert query_of(step.url)["query"]["stats"] == [{"type": "and", "filters": []}]
    assert step.unresolved == ("+#% to Lightning Resistance",)


def test_a_mod_the_stat_list_does_not_know_is_unresolved_and_the_rest_still_filters():
    spec = BuySpec(
        "Spec", category="accessory.amulet", mods=(BuyMod("LightningResistance"), BuyMod("a mod no list has"))
    )

    step = buy_step(spec, "Allflame", MODS, STATS)

    assert [f["id"] for f in query_of(step.url)["query"]["stats"][0]["filters"]] == ["explicit.stat_1671376347"]
    assert step.unresolved == ("a mod no list has",)


def test_influence_corruption_item_level_range_and_a_minimum_are_spelled_out():
    spec = BuySpec(
        "Spec",
        base_type="Onyx Amulet",
        rarity="normal",
        item_level_min=80,
        item_level_max=86,
        influences=("shaper",),
        corrupted=True,
        mods=(BuyMod("LightningResistance", minimum=30),),
    )

    step = buy_step(spec, "Allflame", MODS, STATS)

    assert step.accepts == (
        "Normal",
        "item level 80 to 86",
        "Shaper influence",
        "corrupted",
        "+#% to Lightning Resistance (at least 30)",
    )
