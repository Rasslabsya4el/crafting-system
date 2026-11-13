"""The bought start items of the 17 benchmark targets, on the real 3.29.3.3 export (#474, OR-3, OR-6, OR-7).

The buy spec, the trade query and the price key are computed from the target (`targets/start_buy.py`). These tests pin, for every benchmark
target: whether it buys, the key and the item level window; that the committed price files hold an entry under that key; and (row 2 of the
fact base of #468) that the query built from the target equals the body stored in that entry. The entries whose stored body differs were
priced for another item; they are strict `xfail`s that name the issue that holds the work. They need the cached dump (`CRAFTING_CACHE_DIR`)
and skip cleanly without it.
"""

import dataclasses
import gzip
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml
from abstraction_support import real_game_data

from crafting_system.cli import RESTART, make_plan
from crafting_system.planner._plan import PlanError, resolve_start_price
from crafting_system.cli._route_trade import buy_step
from crafting_system.prices import load_price_file
from crafting_system.prices.trade_query import TradeSpecError, build_query
from crafting_system.prices.trade_stats import parse_trade_stats, resolve_buy_mod
from crafting_system.targets import StartKind, buy_spec_of, load_target, shared_name_refusal, start_price_key
from crafting_system.targets.start_buy import differences_between_same_name_bases

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "examples" / "targets"
PRICES = ROOT / "tests" / "fixtures" / "prices"
STATS = ROOT / "tests" / "fixtures" / "trade" / "recorded" / "stats_full.json.gz"  # the trade site's stat list, 2026-10-31
DERIVED = ROOT / "tests" / "reconcile" / "derived_specs"  # the buy spec of each bought target, written down for the reconcile package
KEYS = ROOT / "tests" / "reconcile" / "expected_keys.txt"  # the independent table of keys, hand-written, read by the reconcile package too

GIVEN = {"j01-cobalt-life-attack-speed"}  # "what you hold after you scour a rare jewel": the player already has it (OR-6, #505); every other target buys
WINDOWS = {  # (item level, highest item level with the same pool)
    "r03-avoid-shock-boots": (100, 100),
    "r06-strength-heavy-belt": (75, 75),
    "r07-minion-wand": (84, 84),
    "r04-penetrating-quiver": (81, 81),
    "r05-strength-ring": (75, 75),
    "r08-energy-shield-boots": (86, 100),
    "r09-life-boots": (86, 100),
    "r10-fractured-boots": (84, 84),
    "r10-fractured-boots-70-life": (84, 84),
    "r11-reservation-helmet": (84, 84),
    "r12-lightning-amulet": (84, 84),
    "r13-life-resist-belt": (86, 100),
    "r14-hunter-bow": (78, 79),
    "r17-lightning-talisman": (85, 85),
    "r24-avoid-shock-boots": (86, 100),
    "v01-minion-helmet": (84, 84),
}
# The entries priced for another item than the one the target computes (a price file entry keeps the body it was priced with).
OTHER_ITEM = {
    "r03-avoid-shock-boots": "#483 the exact item has 0 listings (searched on 2026-11-06; the query itself is #514): the bought start item has no price, so none is written",
    "r06-strength-heavy-belt": "#483 the exact item has 0 listings (searched on 2026-11-06; a normal item cannot carry an influence, #515): the bought start item has no price, so none is written",
    "r05-strength-ring": "#483 the exact item has 0 listings: the stored price is for any ring of item level 75 or more",
    "r10-fractured-boots": "#483 the exact item has 9 listings (rail 10): the stored price is for item level 84 or more",
    "r10-fractured-boots-70-life": "#483 the exact item has 9 listings (rail 10): the stored price is for item level 84 or more",
    "r11-reservation-helmet": "#483 the exact item has 3 listings (rail 10): the stored price is for item level 84 or more",
    "r12-lightning-amulet": "#483 the exact item has 1 listing (rail 10): the stored price is for any amulet of item level 75 or more",
    "r14-hunter-bow": "#601 (and #483) the exact item, a magic Hunter bow, has 0 listings: the stored price is for any non-unique rarity of item level 78 or more",
    "r08-energy-shield-boots": "#494 point 2 the key names a rare item with no mods, the stored price is of a normal base plus a typed Alchemy",
    "r09-life-boots": "#494 point 2 and #483 the stored price is of a normal base plus a typed Alchemy, taken for any of the three Two-Toned Boots",
    "r04-penetrating-quiver": "#426 the stored price is a poe.ninja row, not a trade search: it has no body",
    "r17-lightning-talisman": "#426 the stored price is a poe.ninja row, not a trade search: it has no body",
    "v01-minion-helmet": "#426 the stored price is a hand price, not a trade search: it has no body",
    "r07-minion-wand": "#758 the stored price is a hand stand-in (Allflame has left the trade site, 2026-11-12): it has no body",
    "r24-avoid-shock-boots": "#758 the stored price is a hand stand-in (Allflame has left the trade site, 2026-11-12): it has no body",
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def stats():
    return parse_trade_stats(json.loads(gzip.decompress(STATS.read_bytes()))["stats"])


def expected_keys() -> dict[str, str]:
    rows = [line.split("\t") for line in KEYS.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    return {stem: key for stem, key in rows}


def stems() -> list[str]:
    return sorted(path.stem for path in TARGETS.glob("*.yaml"))


def bought(stem: str) -> bool:
    return stem not in GIVEN


def entries_of(key: str) -> list[dict]:
    """The committed price entries under `key`, one per file that holds it."""
    found = []
    for path in sorted(PRICES.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))["prices"].get(key)
        if entry is not None:
            found.append(entry)
    return found


def query_of(data, stats, stem: str) -> dict:
    target = load_target(TARGETS / f"{stem}.yaml", data)
    spec = buy_spec_of(data, target)
    filters = [resolve_buy_mod(mod, list(data.mods.values()), stats) for mod in spec.mods]
    return build_query(spec, filters).body()


@pytest.mark.parametrize("stem", stems())
def test_a_target_gives_its_start_item_only_where_it_is_given_and_buys_it_everywhere_else(data, stem):
    target = load_target(TARGETS / f"{stem}.yaml", data)

    assert target.bought is bought(stem)
    assert target.start is (StartKind.BOUGHT if bought(stem) else StartKind.GIVEN)


@pytest.mark.parametrize("stem", [stem for stem in stems() if bought(stem)])
def test_the_key_computed_from_the_target_is_the_independent_one(data, stem):
    assert start_price_key(data, load_target(TARGETS / f"{stem}.yaml", data)) == expected_keys()[stem]


def test_the_table_of_keys_names_every_bought_target_once():
    assert sorted(expected_keys()) == [stem for stem in stems() if bought(stem)]
    assert len(set(expected_keys().values())) == len(expected_keys()) - 1  # the two R10 files share one start item and one key


@pytest.mark.parametrize(("stem", "window"), sorted(WINDOWS.items()))
def test_the_item_level_window_of_each_bought_start_item(data, stem, window):
    spec = buy_spec_of(data, load_target(TARGETS / f"{stem}.yaml", data))

    assert (spec.item_level_min, spec.item_level_max or 100) == window


def test_the_shared_names_of_r04_and_r09_say_which_base_and_the_others_do_not(data):
    keys = {stem: start_price_key(data, load_target(TARGETS / f"{stem}.yaml", data)) for stem in WINDOWS}

    assert "[QuiverNew5]" in keys["r04-penetrating-quiver"] and "[BootsAtlas1]" in keys["r09-life-boots"]
    assert [stem for stem, key in keys.items() if "[" in key.split(",")[0]] == ["r04-penetrating-quiver", "r09-life-boots"]


QUIVER = "Metadata/Items/Quivers/"
BOOTS = "Metadata/Items/Armours/Boots/"


def test_r04s_two_quivers_agree_in_class_implicits_and_tags_and_r09s_three_boots_do_not(data):
    assert differences_between_same_name_bases(data, f"{QUIVER}QuiverNew5") == ()  # Quiver12's only other tag is trade_market_legacy_item, read by no mod
    assert data.base_items[f"{QUIVER}Quiver12"].tags != data.base_items[f"{QUIVER}QuiverNew5"].tags
    assert differences_between_same_name_bases(data, f"{BOOTS}BootsAtlas1") == ("implicit mods", "mod tags")


def test_a_poe_ninja_price_prices_r04s_quiver_and_does_not_price_r09s_boots(data):
    """R04's committed start price is a poe.ninja stand-in and plans; R09's would be refused on poe.ninja (its committed price is from the trade API)."""
    for stem, base_id, expected in (
        ("r04-penetrating-quiver", f"{QUIVER}QuiverNew5", None),
        ("r09-life-boots", f"{BOOTS}BootsAtlas1", "that differ in implicit mods and mod tags, so the line is the price of none of them"),
    ):
        target = load_target(TARGETS / f"{stem}.yaml", data)
        key = start_price_key(data, target)
        refusal = shared_name_refusal(data, base_id, "poe.ninja", f"the start item {key!r}")
        assert (refusal is None) if expected is None else (expected in refusal), stem
    committed = {name: entries_of(start_price_key(data, load_target(TARGETS / f"{name}.yaml", data)))[0]["source"] for name in ("r04-penetrating-quiver", "r09-life-boots")}
    assert committed == {"r04-penetrating-quiver": "poe.ninja", "r09-life-boots": "trade-api"}


NO_PRICE = {
    "r03-avoid-shock-boots": OTHER_ITEM["r03-avoid-shock-boots"],
    "r06-strength-heavy-belt": OTHER_ITEM["r06-strength-heavy-belt"],
}  # bought, and the market holds fewer listings than the rail: kept bought, no price written (#505, #483)


VEILED = {"r07-minion-wand", "r24-avoid-shock-boots"}  # priced only in their own file, by hand stand-ins (#758)


def price_row(stem: str):
    marks = [pytest.mark.xfail(strict=True, raises=AssertionError, reason=NO_PRICE[stem])] if stem in NO_PRICE else []
    return pytest.param(stem, id=stem, marks=marks)


@pytest.mark.parametrize("stem", [price_row(stem) for stem in stems() if bought(stem)])
def test_every_bought_start_item_has_a_price_under_its_key_in_each_committed_file_that_has_it(stem):
    key = expected_keys()[stem]
    committed = [path.name for path in sorted(PRICES.glob("*.json")) if key in json.loads(path.read_text(encoding="utf-8"))["prices"]]

    # the vendor file is V01's own (`price_file:`) and holds a copy of every other route's entries; the veiled file is R24's and R07's own
    # (`price_file:`) and holds a copy of the 2026-11-10 file (#146)
    if stem == "v01-minion-helmet":
        assert committed == ["vendor-v01-2026-11-01.json"]
    elif stem in VEILED:
        assert committed == ["veiled-r24-r07-2026-11-12.json"]
    elif stem == "r17-lightning-talisman":  # R17's own file (`price_file:`, #223): the 2026-11-10 file without the other routes' start items, plus its beasts and Talisman
        assert committed == ["r17-allflame-2026-11-10.json"]
    else:
        assert committed == [
            "routes-allflame-2026-07-31.json",  # the default of the tests and benchmarks (#838); its start items are stand-ins of the 2026-11-10 readings
            "routes-allflame-2026-10-31.json",
            "routes-allflame-2026-11-10.json",
            "veiled-r24-r07-2026-11-12.json",
            "vendor-v01-2026-11-01.json",
        ]


def row(stem: str):
    marks = [pytest.mark.xfail(strict=True, raises=(AssertionError, TradeSpecError), reason=OTHER_ITEM[stem])] if stem in OTHER_ITEM else []
    return pytest.param(stem, id=stem, marks=marks)


@pytest.mark.parametrize("stem", [row(stem) for stem in stems() if bought(stem)])
def test_the_query_built_from_the_target_is_the_body_stored_in_its_price_entry(data, stats, stem):
    entries = entries_of(expected_keys()[stem])
    built = query_of(data, stats, stem)

    assert entries
    for entry in entries:
        assert entry["source"] == "trade-api"
        assert entry["detail"]["query"] == built


RECORDED = ROOT / "tests" / "fixtures" / "trade" / "recorded" / "start_items"
SEARCH_BODIES = {  # tag of the recorded search -> the target whose start item it priced (the files `search_body_<tag>.json`)
    "r05": "r05-strength-ring",
    "r10": "r10-fractured-boots",
    "r11": "r11-reservation-helmet",
    "r12": "r12-lightning-amulet",
}


def body_row(tag: str):
    marks = [pytest.mark.xfail(strict=True, raises=(AssertionError, TradeSpecError), reason=OTHER_ITEM[SEARCH_BODIES[tag]])]
    return pytest.param(tag, id=tag, marks=marks)


@pytest.mark.parametrize("tag", [body_row(tag) for tag in SEARCH_BODIES])
def test_the_query_built_from_the_target_is_the_recorded_search_body(data, stats, tag):
    """#470 point 2: the recorded body, the stored `detail.query` and the query of the target are one body, or the xfail names why not."""
    recorded = json.loads((RECORDED / f"search_body_{tag}.json").read_text(encoding="utf-8"))

    assert query_of(data, stats, SEARCH_BODIES[tag]) == recorded


def link_body(url: str) -> dict:
    return json.loads(parse_qs(urlparse(url).query)["q"][0])


@pytest.mark.parametrize("stem", [stem for stem in stems() if bought(stem) and stem != "r03-avoid-shock-boots"])
def test_the_trade_link_of_the_page_is_the_query_built_from_the_target(data, stats, stem):
    """#470 point 2: every bought target's buy step links the very body the price is taken with (R04, R08, R09, R12, R14 had no check)."""
    spec = buy_spec_of(data, load_target(TARGETS / f"{stem}.yaml", data))

    step = buy_step(spec, "Allflame", data.mods.values(), stats)

    assert step.unresolved == ()
    assert link_body(step.url) == query_of(data, stats, stem)


def test_the_link_of_r03_leaves_out_the_one_stat_the_site_lists_twice_and_the_page_says_so(data, stats):
    spec = buy_spec_of(data, load_target(TARGETS / "r03-avoid-shock-boots.yaml", data))

    step = buy_step(spec, "Allflame", data.mods.values(), stats)

    assert len(step.unresolved) == 1 and "Suppress Spell Damage" in step.unresolved[0]  # #514
    assert link_body(step.url)["query"]["stats"][0]["filters"] == []


@pytest.mark.parametrize("stem", [stem for stem in stems() if bought(stem)])
def test_the_buy_step_is_titled_by_the_price_key_and_names_the_base(data, stats, stem):
    """#470 point 4: not "Buy R05 start ring" and not a step without the base: the key names the base, the Accepts line starts with it."""
    target = load_target(TARGETS / f"{stem}.yaml", data)
    spec = buy_spec_of(data, target)

    step = buy_step(spec, "Allflame", data.mods.values(), stats)

    assert step.name == expected_keys()[stem]
    assert step.accepts[0] == f"{target.start_item.rarity.value.capitalize()} {data.base_items[target.base_id].name}"
    assert step.name.startswith(data.base_items[target.base_id].name)


def test_the_three_two_toned_boots_are_told_apart_by_their_implicit_and_the_two_quivers_are_not(data, stats):
    def implicit_ids(stem):
        body = query_of(data, stats, stem)["query"]
        return [found["id"] for found in body["stats"][0]["filters"] if found["id"].startswith("implicit.")]

    assert implicit_ids("r09-life-boots") == ["implicit.stat_4277795662"]  # BootsAtlas1: Cold and Lightning Resistances
    assert implicit_ids("r04-penetrating-quiver") == []  # QuiverNew5 and Quiver12 share their implicit and their pool
    assert implicit_ids("r08-energy-shield-boots") == []  # a name with one base needs none


@pytest.mark.parametrize(
    ("base", "stat"),
    [
        ("BootsAtlas1", "implicit.stat_4277795662"),
        ("BootsAtlas2", "implicit.stat_2915988346"),
        ("BootsAtlas3", "implicit.stat_3441501978"),
    ],
)
def test_each_two_toned_base_asks_for_its_own_implicit_stat_of_the_recorded_stat_list(data, stats, base, stat):
    target = load_target(TARGETS / "r09-life-boots.yaml", data)
    other = dataclasses.replace(target, base_id=f"Metadata/Items/Armours/Boots/{base}")
    spec = buy_spec_of(data, other)
    filters = [resolve_buy_mod(mod, list(data.mods.values()), stats) for mod in spec.mods]

    assert [found.id for found in filters] == [stat]
    assert spec.name.startswith(f"Two-Toned Boots [{base}]")


@pytest.mark.parametrize("stem", stems())
def test_every_example_target_says_in_its_own_text_how_its_start_item_is_had(stem):
    text = (TARGETS / f"{stem}.yaml").read_text(encoding="utf-8")

    (word,) = re.findall(r"(?m)^start:\s*(\w+)\s*$", text)
    assert word == ("bought" if bought(stem) else "given")
    assert "buys_start_item" not in text


def test_a_given_start_item_names_its_reason_in_a_comment_and_does_not_call_it_a_guide_quote():
    text = (TARGETS / "j01-cobalt-life-attack-speed.yaml").read_text(encoding="utf-8")

    comment = text[text.index("# How the start item is had") : text.index("start: given")]
    assert "you already have the item" in comment and "what you hold after you scour a rare jewel" in comment
    assert "No guide exists" in comment and "own reading, not a quotation" in comment  # #201 holds no such sentence


@pytest.mark.parametrize(("stem", "guide_words"), [("r03-avoid-shock-boots", "Get suppression fracture boot"), ("r06-strength-heavy-belt", "Buy an item level 75+ Hunter- or Elder-influenced Heavy Belt")])
def test_where_the_guide_buys_the_start_item_the_target_says_bought_and_quotes_the_guide(stem, guide_words):
    text = (TARGETS / f"{stem}.yaml").read_text(encoding="utf-8")

    assert "start: bought" in text
    assert guide_words.lower() in text.lower()


SEARCHES = ROOT / "tests" / "fixtures" / "trade" / "recorded" / "start_items" / "searches_r03_r06_2026-11-06.json"


def test_the_recorded_search_of_r06_is_the_query_built_from_the_target_and_had_no_listing(data, stats):
    record = json.loads(SEARCHES.read_text(encoding="utf-8"))["r06-strength-heavy-belt"]

    assert record["key"] == expected_keys()["r06-strength-heavy-belt"] and record["date"] == "2026-11-06" and record["league"] == "Allflame"
    assert record["total"] == 0 and record["requests"] == 1
    assert record["query"] == query_of(data, stats, "r06-strength-heavy-belt")  # the stored query is the computed one (OR-3)


def test_r03_asks_for_a_stat_the_trade_site_lists_twice_and_both_were_searched_with_no_listing(data, stats):
    record = json.loads(SEARCHES.read_text(encoding="utf-8"))["r03-avoid-shock-boots"]

    assert record["key"] == expected_keys()["r03-avoid-shock-boots"] and record["date"] == "2026-11-06"
    assert [(each["stat"], each["total"]) for each in record["searches"]] == [("fractured.stat_3680664274", 0), ("fractured.stat_492027537", 0)]
    with pytest.raises(TradeSpecError, match="several trade stats.*stat_3680664274.*stat_492027537|several trade stats.*stat_492027537.*stat_3680664274"):
        query_of(data, stats, "r03-avoid-shock-boots")  # #514: the query cannot be built from the target alone yet


PRICE_FILE = PRICES / "routes-allflame-2026-10-31.json"


@pytest.mark.parametrize("stem", sorted(NO_PRICE))
def test_a_bought_start_item_with_no_price_in_the_committed_files_is_refused_naming_its_key(data, stem):
    target = load_target(TARGETS / f"{stem}.yaml", data)

    with pytest.raises(PlanError) as caught:
        resolve_start_price(data, target, load_price_file(PRICE_FILE), None)

    # when #483 gives the exact item a price this test fails: remove the strict xfails that name #483 with it
    assert repr(expected_keys()[stem]) in str(caught.value) and "must have a price" in str(caught.value)


def test_j01_plans_from_its_example_file_as_a_given_start_item_with_no_restart(data):
    target = load_target(TARGETS / "j01-cobalt-life-attack-speed.yaml", data)

    plan = make_plan(data, target, load_price_file(PRICE_FILE))

    assert plan.start_price.given and plan.start_price.chaos == 0.0
    assert all(priced.label != RESTART for priced in plan.offers)
    assert [limit.what for limit in plan.limits if limit.kind == "start-item"] == ["The start item is given"]


@pytest.mark.parametrize(
    "stem",
    [
        pytest.param(
            "r03-avoid-shock-boots",
            marks=pytest.mark.xfail(strict=True, raises=PlanError, reason="#483 the bought start item has no price, and #516 the planner refuses its implicits first"),
        ),
        pytest.param(
            "r06-strength-heavy-belt",
            marks=pytest.mark.xfail(strict=True, raises=PlanError, reason="#483 the bought start item has no price, and #516 the planner refuses its implicits and quality first"),
        ),
    ],
)
def test_r03_and_r06_plan_from_their_example_files(data, stem):
    plan = make_plan(data, load_target(TARGETS / f"{stem}.yaml", data), load_price_file(PRICE_FILE))

    assert plan.start_price.bought and plan.start_price.chaos > 0


def test_no_buy_spec_file_and_no_start_price_line_is_left():
    assert not (ROOT / "examples" / "buy").exists()
    for path in TARGETS.glob("*.yaml"):
        assert not re.search(r"(?m)^\s*start_price\s*:", path.read_text(encoding="utf-8")), path.name


# -- the buy specs written down for the reconcile package ---------------------------------------------------------------------------------


HEADER = (
    "# GENERATED by tests/test_start_buy_real.py from examples/targets/{stem}.yaml (UPDATE_DERIVED_SPECS=1 rewrites it): the buy spec the\n"
    "# planner computes from the target. Not an input; the reconcile package reads it to check it against the target, the game data and\n"
    "# the price entry without importing the planner.\n"
)


def spec_text(stem: str, spec) -> str:
    document = {"name": spec.name, "base_type": spec.base_type, "category": spec.category, "rarity": spec.rarity, "item_level_min": spec.item_level_min}
    if spec.item_level_max is not None:
        document["item_level_max"] = spec.item_level_max
    if spec.influences:
        document["influence"] = list(spec.influences)
    document["corrupted"] = spec.corrupted
    document["mods"] = [
        {"stat": mod.stat, **({} if mod.minimum is None else {"minimum": mod.minimum}), "fractured": mod.fractured, **({"implicit": True, "own": True} if mod.own else {})}
        for mod in spec.mods
    ]
    return HEADER.format(stem=stem) + yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def test_the_derived_specs_folder_is_what_the_planner_computes_for_each_bought_target(data):
    update = os.environ.get("UPDATE_DERIVED_SPECS") == "1"
    written: dict[str, str] = {}  # key -> the stem whose file holds it: the two R10 files share one start item, so one spec
    for stem in [stem for stem in stems() if bought(stem)]:
        spec = buy_spec_of(data, load_target(TARGETS / f"{stem}.yaml", data))
        if spec.name in written:
            assert spec_text(written[spec.name], spec) == (DERIVED / f"{written[spec.name]}.yaml").read_text(encoding="utf-8"), stem
            continue
        written[spec.name] = stem
        text = spec_text(stem, spec)
        path = DERIVED / f"{stem}.yaml"
        if update:
            DERIVED.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        assert path.read_text(encoding="utf-8") == text, f"{path.name} is not what the planner computes; UPDATE_DERIVED_SPECS=1 rewrites it"

    assert sorted(path.stem for path in DERIVED.glob("*.yaml")) == sorted(written.values())
