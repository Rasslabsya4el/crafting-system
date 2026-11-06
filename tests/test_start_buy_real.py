"""The bought start items of the 14 benchmark targets, on the real 3.29.3.3 export (#474, OR-3, OR-6, OR-7).

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

import pytest
import yaml
from abstraction_support import real_game_data

from crafting_system.prices.trade_query import build_query
from crafting_system.prices.trade_stats import parse_trade_stats, resolve_buy_mod
from crafting_system.targets import buy_spec_of, load_target, start_price_key

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "examples" / "targets"
PRICES = ROOT / "tests" / "fixtures" / "prices"
STATS = ROOT / "tests" / "fixtures" / "trade" / "recorded" / "stats_full.json.gz"  # the trade site's stat list, 2026-10-31
DERIVED = ROOT / "tests" / "reconcile" / "derived_specs"  # the buy spec of each bought target, written down for the reconcile package
KEYS = ROOT / "tests" / "reconcile" / "expected_keys.txt"  # the independent table of keys, hand-written, read by the reconcile package too

NOT_BOUGHT = {"j01-cobalt-life-attack-speed", "r03-avoid-shock-boots", "r06-strength-heavy-belt"}  # #427, the next step-4 ticket
WINDOWS = {  # (item level, highest item level with the same pool)
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
    "v01-minion-helmet": (84, 84),
}
# The entries priced for another item than the one the target computes (a price file entry keeps the body it was priced with).
OTHER_ITEM = {
    "r05-strength-ring": "#483 the exact item has 0 listings: the stored price is for any ring of item level 75 or more",
    "r10-fractured-boots": "#483 the exact item has 9 listings (rail 10): the stored price is for item level 84 or more",
    "r10-fractured-boots-70-life": "#483 the exact item has 9 listings (rail 10): the stored price is for item level 84 or more",
    "r11-reservation-helmet": "#483 the exact item has 3 listings (rail 10): the stored price is for item level 84 or more",
    "r12-lightning-amulet": "#483 the exact item has 1 listing (rail 10): the stored price is for any amulet of item level 75 or more",
    "r14-hunter-bow": "#483 the exact item has 0 listings: the stored price is for any non-unique rarity of item level 78 or more",
    "r08-energy-shield-boots": "#494 point 2 the key names a rare item with no mods, the stored price is of a normal base plus a typed Alchemy",
    "r09-life-boots": "#494 point 2 and #483 the stored price is of a normal base plus a typed Alchemy, taken for any of the three Two-Toned Boots",
    "r04-penetrating-quiver": "#426 the stored price is a poe.ninja row, not a trade search: it has no body",
    "r13-life-resist-belt": "#426 the stored price is a poe.ninja row, not a trade search: it has no body",
    "v01-minion-helmet": "#426 the stored price is a hand price, not a trade search: it has no body",
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
    return stem not in NOT_BOUGHT


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
def test_a_target_buys_its_start_item_unless_it_is_one_of_the_three_without_a_price(data, stem):
    target = load_target(TARGETS / f"{stem}.yaml", data)

    assert target.buys_start_item is bought(stem)


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


@pytest.mark.parametrize("stem", [stem for stem in stems() if bought(stem)])
def test_every_bought_start_item_has_a_price_under_its_key_in_each_committed_file_that_has_it(stem):
    key = expected_keys()[stem]
    committed = [path.name for path in sorted(PRICES.glob("*.json")) if key in json.loads(path.read_text(encoding="utf-8"))["prices"]]

    # the vendor file is V01's own (`price_file:`) and holds a copy of every other route's entries
    assert committed == (["vendor-v01-2026-11-01.json"] if stem == "v01-minion-helmet" else ["routes-allflame-2026-10-31.json", "vendor-v01-2026-11-01.json"])


def row(stem: str):
    marks = [pytest.mark.xfail(strict=True, raises=AssertionError, reason=OTHER_ITEM[stem])] if stem in OTHER_ITEM else []
    return pytest.param(stem, id=stem, marks=marks)


@pytest.mark.parametrize("stem", [row(stem) for stem in stems() if bought(stem)])
def test_the_query_built_from_the_target_is_the_body_stored_in_its_price_entry(data, stats, stem):
    entries = entries_of(expected_keys()[stem])
    built = query_of(data, stats, stem)

    assert entries
    for entry in entries:
        assert entry["source"] == "trade-api"
        assert entry["detail"]["query"] == built


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
