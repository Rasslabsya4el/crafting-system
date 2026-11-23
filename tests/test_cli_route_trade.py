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
        "Rare, any amulet base",  # a spec with no base type takes any base of its category (#937)
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
        "Normal Onyx Amulet",  # the base is named (the page used to leave it out, #470 point 4)
        "item level 80 to 86",
        "Shaper influence",
        "corrupted",
        "+#% to Lightning Resistance (at least 30)",
    )


def test_the_link_asks_for_instant_buyout_listings_of_any_age():
    query = query_of(buy_step(R12_SPEC, "Allflame", MODS, STATS).url)["query"]

    assert query["status"] == {"option": "securable"}
    assert "trade_filters" not in query["filters"]


def test_equal_ends_of_the_item_level_window_read_as_one_level_not_as_84_to_84():
    one = BuySpec("Spec", base_type="Onyx Amulet", item_level_min=84, item_level_max=84)
    two = BuySpec("Spec", base_type="Onyx Amulet", item_level_min=84, item_level_max=85)

    assert buy_step(one, "Allflame", MODS, STATS).accepts[1] == "item level 84"
    assert buy_step(two, "Allflame", MODS, STATS).accepts[1] == "item level 84 to 85"


WIDER_RING = {
    "query": {
        "status": {"option": "securable"},
        "stats": [{"type": "and", "filters": [{"id": "fractured.stat_1379411836", "disabled": False, "value": {"min": 13}}]}],
        "filters": {
            "type_filters": {"filters": {"rarity": {"option": "rare"}, "category": {"option": "accessory.ring"}}},
            "misc_filters": {"filters": {"ilvl": {"min": 75}, "corrupted": {"option": "false"}, "fractured_item": {"option": "true"}}},
        },
    },
    "sort": {"price": "asc"},
}  # R05's stored search (2026-11-10): any ring base of item level 75 or more, no `type`


def test_a_start_priced_from_a_wider_search_links_that_search_and_says_it_in_words():
    """#937 (OR-7): R05's ring is priced from a search of any ring base of item level 75 or more, so the step links that search itself
    (the listings the price came from) and says that item, not the Amethyst Ring of item level 75 the plan is worked out on."""
    from crafting_system.prices.query_compare import searched_spec

    spec = BuySpec(
        "Amethyst Ring, item level 75, fractured +(13-16) to all Attributes", base_type="Amethyst Ring", category="accessory.ring",
        item_level_min=75, item_level_max=75, mods=(BuyMod("+(13-16) to all Attributes", 13, fractured=True),),
    )  # fmt: skip
    wider = searched_spec(spec, WIDER_RING)
    step = buy_step(wider, "Allflame", MODS, STATS, WIDER_RING)

    assert (wider.base_type, wider.category, wider.item_level_min, wider.item_level_max) == (None, "accessory.ring", 75, None)
    assert wider.name == spec.name and [(mod.minimum, mod.fractured) for mod in wider.mods] == [(13, True)]
    assert query_of(step.url) == WIDER_RING
    assert step.accepts[:2] == ("Rare, any ring base", "item level 75 or more")
    assert step.accepts[-1] == "fractured: +# to all Attributes (at least 13)"
    assert step.item == "any ring, item level 75 or more, fractured +# to all Attributes (at least 13)"


WIDER_BOW = {
    "query": {
        "status": {"option": "securable"},
        "type": "Thicket Bow",
        "stats": [{"type": "and", "filters": [{"id": "pseudo.pseudo_has_hunter_influence", "disabled": False, "value": {"min": 1}}]}],
        "filters": {
            "type_filters": {"filters": {"rarity": {"option": "nonunique"}, "category": {"option": "weapon.bow"}}},
            "misc_filters": {"filters": {"ilvl": {"min": 78}, "corrupted": {"option": "false"}, "mirrored": {"option": "false"}}},
        },
    },
    "sort": {"price": "asc"},
}  # R14's stored search (2026-11-10): a Thicket Bow of any rarity but unique, item level 78 or more, Hunter influence


def test_a_wider_search_of_any_rarity_but_unique_with_an_influence_is_said_in_words():
    """#937 (OR-7), R14: the magic Thicket Bow of item level 78-79 is priced from a search of any rarity but unique and item level 78 or
    more, with the Hunter influence; the step says that item, never the trade site's option `nonunique`, and keeps the influence."""
    from crafting_system.prices.query_compare import searched_spec

    spec = BuySpec(
        "Thicket Bow, magic, item level 78-79, Hunter influence", base_type="Thicket Bow", category="weapon.bow", rarity="magic",
        item_level_min=78, item_level_max=79, influences=("hunter",),
    )  # fmt: skip
    wider = searched_spec(spec, WIDER_BOW)
    step = buy_step(wider, "Allflame", MODS, STATS, WIDER_BOW)

    assert (wider.rarity, wider.base_type, wider.item_level_min, wider.item_level_max, wider.influences) == ("nonunique", "Thicket Bow", 78, None, ("hunter",))
    assert query_of(step.url) == WIDER_BOW
    assert step.accepts[:2] == ("Any rarity but unique Thicket Bow", "item level 78 or more")
    assert step.item == "Thicket Bow, any rarity but unique, item level 78 or more, Hunter influence"
    assert "nonunique" not in step.item and not any("nonunique" in line for line in step.accepts)
