"""Bases and beasts from the poe.ninja stash overview, and the minimum sample, on recorded responses."""

import copy
from datetime import UTC, datetime

import pytest

from ninja_support import STASH_TYPES, ninja, ninja_fixture  # noqa: F401  (ninja is a fixture)
from crafting_system.prices import PriceEntry, PriceFile, load_price_file, write_price_file
from crafting_system.prices.__main__ import main
from crafting_system.prices.fetch import fetch_price_file
from crafting_system.prices.http_json import SourceError
from crafting_system.prices.ninja_items import StashLine, parse_stash_overview

BASE_TAG = {"category": "BaseType"}

NOW = datetime(2026, 10, 30, 21, 0, 5, tzinfo=UTC)
VISE = "Stygian Vise (ilvl 85"


def bases() -> dict[str, StashLine]:
    return {line.key: line for line in parse_stash_overview(ninja_fixture("stash_basetype"), "BaseType")}


def beasts() -> dict[str, StashLine]:
    return {line.key: line for line in parse_stash_overview(ninja_fixture("stash_beast"), "Beast")}


def base_line(**changes) -> dict:
    """A copy of the recorded Imperial Skean 85 Hunter line (count 5) with `changes`; None removes a field."""
    line = copy.deepcopy(next(l for l in ninja_fixture("stash_basetype")["lines"] if l["id"] == 27326))
    for field, value in changes.items():
        if value is None:
            line.pop(field, None)
        else:
            line[field] = value
    return line


# --- the keys ------------------------------------------------------------------------------


def test_a_base_is_keyed_by_name_item_level_and_influences_in_game_order():
    assert set(bases()) == {
        f"{VISE})",
        f"{VISE}, Hunter)",
        f"{VISE}, Elder)",
        f"{VISE}, Hunter/Warlord)",
        f"{VISE}, Crusader)",
        "Imperial Skean (ilvl 85, Hunter)",
        "Archon Kite Shield (ilvl 85, Crusader)",
        "Helical Ring (ilvl 84, Elder/Warlord)",
        "Steel Kite Shield (ilvl 86)",
        "Vaal Regalia (ilvl 86)",
    }


def test_a_line_carries_its_price_count_id_and_kind():
    line = bases()[f"{VISE}, Hunter)"]

    assert line == StashLine(f"{VISE}, Hunter)", 1262.0, 85, 34026, "BaseType")


def test_the_non_canonical_variant_order_of_the_source_gives_the_canonical_name():
    assert f"{VISE}, Hunter/Warlord)" in bases()  # recorded as "Warlord/Hunter"
    assert "Stygian Vise (ilvl 85, Warlord/Hunter)" not in bases()


def test_a_beast_is_keyed_by_its_name():
    assert set(beasts()) == {
        "Wild Bristle Matron",
        "Aboriginal Chieftain",
        "Tunnelfiend",
        "Plated Parasite",
        "Stygian Silverback",
        "Vivid Vulture",
    }
    assert beasts()["Vivid Vulture"] == StashLine("Vivid Vulture", 88.1, 32, 101096, "Beast")


def test_two_lines_with_one_key_keep_the_higher_count():
    data = {"lines": [base_line(id=1, count=7, chaosValue=10), base_line(id=2, count=9, chaosValue=20), base_line(id=3, count=8, chaosValue=30)]}

    (line,) = parse_stash_overview(data, "BaseType")

    assert (line.line_id, line.chaos, line.count) == (2, 20.0, 9)


def test_the_same_base_in_two_influence_orders_is_one_key():
    data = {
        "lines": [
            base_line(id=1, variant="Hunter/Warlord", count=7, chaosValue=10),
            base_line(id=2, variant="Warlord/Hunter", count=12, chaosValue=20),
        ]
    }

    (line,) = parse_stash_overview(data, "BaseType")

    assert line.key == "Imperial Skean (ilvl 85, Hunter/Warlord)" and line.chaos == 20.0


@pytest.mark.parametrize(
    "changes",
    [
        {"count": None},
        {"count": "5"},
        {"count": 5.0},
        {"count": True},
        {"variant": "Bogus"},
        {"variant": "Hunter/Bogus"},
        {"variant": 7},
        {"variant": ""},
        {"name": None},
        {"name": "  "},
        {"name": 5},
        {"chaosValue": None},
        {"chaosValue": 0},
        {"chaosValue": -1},
        {"chaosValue": "9"},
        {"chaosValue": float("inf")},
        {"levelRequired": None},
        {"levelRequired": "85"},
    ],
)
def test_a_malformed_base_line_is_skipped_not_an_error(changes):
    data = {"lines": [base_line(**changes), "garbage", None, base_line(id=2, name="Vaal Regalia")]}

    assert [line.key for line in parse_stash_overview(data, "BaseType")] == ["Vaal Regalia (ilvl 85, Hunter)"]


def test_a_beast_line_needs_no_item_level_or_variant():
    data = {"lines": [{"id": 1, "name": "Tunnelfiend", "chaosValue": 3, "count": 6}]}

    assert parse_stash_overview(data, "Beast") == [StashLine("Tunnelfiend", 3.0, 6, 1, "Beast")]


def test_a_line_without_a_numeric_id_still_parses_with_no_id():
    (line,) = parse_stash_overview({"lines": [base_line(id=None)]}, "BaseType")

    assert line.line_id is None


@pytest.mark.parametrize("answer", [[], None, "x", {}, {"lines": 5}, {"lines": []}, {"lines": ["x", {}]}])
def test_an_answer_without_a_usable_line_is_a_source_error(answer):
    with pytest.raises(SourceError):
        parse_stash_overview(answer, "BaseType")


# --- what the fetch writes -----------------------------------------------------------------


def test_the_stash_overviews_are_asked_for_after_the_exchange_ones(ninja):
    fetch_price_file(ninja, NOW)

    stash_urls = [url for url in ninja.requests if "/stash/" in url]
    assert stash_urls == [
        "https://poe.ninja/poe1/api/economy/stash/current/item/overview?league=Allflame&type=Beast",
        "https://poe.ninja/poe1/api/economy/stash/current/item/overview?league=Allflame&type=BaseType",
    ]
    assert ninja.requests.index(stash_urls[0]) > max(
        i for i, url in enumerate(ninja.requests) if "/exchange/" in url
    )


def test_bases_are_priced_at_their_recorded_value(ninja):
    prices = fetch_price_file(ninja, NOW).price_file.prices

    assert prices["Stygian Vise (ilvl 85)"] == PriceEntry(5.0, "poe.ninja", None, BASE_TAG)
    assert prices["Stygian Vise (ilvl 85, Hunter)"] == PriceEntry(1262.0, "poe.ninja", None, BASE_TAG)
    assert prices["Stygian Vise (ilvl 85, Elder)"].chaos == 721.4
    assert prices["Stygian Vise (ilvl 85, Crusader)"].chaos == 1515.0
    assert prices["Vaal Regalia (ilvl 86)"].chaos == 10.0
    assert prices["Stygian Vise (ilvl 85, Hunter)"].note is None
    assert prices["Stygian Vise (ilvl 85, Hunter)"].detail == BASE_TAG  # the category, for a failed overview later


def test_beasts_are_priced_at_their_recorded_value(ninja):
    prices = fetch_price_file(ninja, NOW).price_file.prices

    assert prices["Wild Bristle Matron"] == PriceEntry(139.0, "poe.ninja", None, {"category": "Beast"})
    assert prices["Tunnelfiend"].chaos == 100.0
    assert prices["Vivid Vulture"].chaos == 88.1


def test_every_recorded_line_with_enough_observations_is_priced_at_its_chaos_value(ninja):
    prices = fetch_price_file(ninja, NOW).price_file.prices

    for kind in STASH_TYPES:
        recorded = {line["id"]: line for line in ninja_fixture(f"stash_{kind.lower()}")["lines"]}
        lines = parse_stash_overview(ninja_fixture(f"stash_{kind.lower()}"), kind)
        assert len(lines) == len(recorded)
        for line in lines:
            if recorded[line.line_id]["count"] >= 5:
                assert prices[line.key].chaos == recorded[line.line_id]["chaosValue"]
            else:
                assert line.key not in prices


def test_a_line_seen_exactly_five_times_is_priced_and_one_seen_four_times_is_not(ninja):
    prices = fetch_price_file(ninja, NOW).price_file.prices

    assert prices["Imperial Skean (ilvl 85, Hunter)"].chaos == 360.7  # count 5
    assert "Archon Kite Shield (ilvl 85, Crusader)" not in prices  # count 4
    assert prices["Plated Parasite"].chaos == 4.2  # count 5
    assert "Stygian Silverback" not in prices  # count 4


def test_the_two_million_chaos_line_seen_once_is_not_priced_and_is_reported_thin(ninja):
    result = fetch_price_file(ninja, NOW)

    assert "Helical Ring (ilvl 84, Elder/Warlord)" not in result.price_file.prices
    assert "Helical Ring (ilvl 84, Elder/Warlord)" in result.thin
    assert not any(price.chaos > 1_000_000 for price in result.price_file.prices.values())


def test_thin_lines_are_listed_sorted_and_not_repeated_in_the_warnings(ninja):
    result = fetch_price_file(ninja, NOW)

    assert result.thin == [
        "Aboriginal Chieftain",
        "Archon Kite Shield (ilvl 85, Crusader)",
        "Helical Ring (ilvl 84, Elder/Warlord)",
        "Steel Kite Shield (ilvl 86)",
        "Stygian Silverback",
        "Stygian Vise (ilvl 85, Hunter/Warlord)",
    ]
    assert result.warnings == []
    assert result.missing == []


def test_a_zero_volume_exchange_line_is_thin_too(ninja):
    for line in ninja.overviews["Fossil"]["lines"]:
        if line["id"] == "hollow-fossil":
            line["volumePrimaryValue"] = 0

    result = fetch_price_file(ninja, NOW)

    assert "Hollow Fossil" in result.thin and "Hollow Fossil" not in result.price_file.prices


def test_a_category_whose_lines_are_all_thin_is_not_an_error(ninja):
    for line in ninja.stash_overviews["Beast"]["lines"]:
        line["count"] = 1

    result = fetch_price_file(ninja, NOW)

    assert "Wild Bristle Matron" in result.thin and "Wild Bristle Matron" not in result.price_file.prices
    assert "Stygian Vise (ilvl 85, Hunter)" in result.price_file.prices


def test_a_wanted_base_with_no_line_at_all_is_missing(ninja):
    result = fetch_price_file(ninja, NOW, wanted=["Stygian Vise (ilvl 83, Hunter)", "Wild Bristle Matron"])

    assert result.missing == ["Stygian Vise (ilvl 83, Hunter)"]
    assert "Stygian Vise (ilvl 83, Hunter)" not in result.thin


def test_the_written_file_with_bases_and_beasts_loads_back_equal(ninja, tmp_path):
    price_file = fetch_price_file(ninja, NOW).price_file
    path = tmp_path / "prices.json"

    write_price_file(path, price_file)

    assert load_price_file(path) == price_file


# --- a stash category that fails -----------------------------------------------------------


@pytest.mark.parametrize("kind", STASH_TYPES)
@pytest.mark.parametrize(
    "answer",
    [SourceError("HTTP 500 for the overview"), {"lines": []}, [], {"lines": 5}, {"lines": [{"name": "x"}]}],
)
def test_a_failing_empty_or_changed_stash_category_warns_and_the_fetch_finishes(ninja, kind, answer):
    ninja.stash_overviews[kind] = answer

    result = fetch_price_file(ninja, NOW)

    assert any(f"the {kind} prices failed" in line for line in result.warnings)
    assert "Hollow Fossil" in result.price_file.prices  # the exchange categories were still written


@pytest.mark.parametrize("kind", STASH_TYPES)
def test_a_failing_stash_category_still_writes_the_file_and_prints_the_warning(ninja, tmp_path, capsys, kind):
    path = tmp_path / "data" / "prices.json"
    ninja.stash_overviews[kind] = SourceError(f"HTTP 500 for {kind}")

    code = main(["fetch"], get_json=ninja, now=NOW, env={"CRAFTING_DATA_DIR": str(path.parent)})

    assert code == 0
    assert "Hollow Fossil" in load_price_file(path).prices
    out = capsys.readouterr().out
    assert any(line.startswith("Warning:") and kind in line and f"HTTP 500 for {kind}" in line for line in out.splitlines())


@pytest.mark.parametrize("kind", STASH_TYPES)
def test_an_empty_stash_category_still_writes_a_file_with_a_warning(ninja, tmp_path, capsys, kind):
    ninja.stash_overviews[kind] = {"lines": []}

    code = main(["fetch"], get_json=ninja, now=NOW, env={"CRAFTING_DATA_DIR": str(tmp_path / "data")})

    assert code == 0
    assert (tmp_path / "data" / "prices.json").exists()
    assert f"the {kind} prices failed" in capsys.readouterr().out


# --- the command line ----------------------------------------------------------------------


def test_fetch_reports_how_many_lines_were_too_thin_to_price(ninja, tmp_path, capsys):
    code = main(["fetch"], get_json=ninja, now=NOW, env={"CRAFTING_DATA_DIR": str(tmp_path)})

    assert code == 0
    out = capsys.readouterr().out
    assert "6 current lines were too thin to price (fewer than 5 observations or no trade volume)" in out
    assert out.index("prices written") < out.index("too thin")


def test_fetch_says_nothing_about_thin_lines_when_there_are_none(ninja, tmp_path, capsys):
    for kind in STASH_TYPES:
        for line in ninja.stash_overviews[kind]["lines"]:
            line["count"] = 50

    main(["fetch"], get_json=ninja, now=NOW, env={"CRAFTING_DATA_DIR": str(tmp_path)})

    assert "too thin" not in capsys.readouterr().out
