"""The fallback chain behind `fetch_price_file`: gaps, stash history, and the order of the stages (recorded data)."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from ninja_support import ninja, ninja_fixture  # noqa: F401  (ninja is a fixture)
from crafting_system.prices import (
    BaseKey,
    Context,
    Gap,
    PriceEntry,
    StageResult,
    load_price_file,
    stamped_entry,
    write_price_file,
)
from crafting_system.prices.__main__ import main
from crafting_system.prices.fetch import DEFAULT_STAGES, fetch_price_file
from crafting_system.prices.ninja_history import ninja_history_stage
from crafting_system.prices.poe_watch import poe_watch_stage
from crafting_system.prices.previous_league import previous_league_stage

NOW = datetime(2026, 10, 30, 21, 0, 5, 123456, tzinfo=UTC)
HUNTER_VISE = "Stygian Vise (ilvl 85, Hunter)"
HUNTER_VISE_HISTORY = ("Allflame", "BaseType", 34026)
CHIEFTAIN_HISTORY = ("Allflame", "Beast", 167860)


class Recorder:
    """A stage that remembers what it was called with and prices what `prices` says (name -> chaos)."""

    def __init__(self, prices=None, warn=False):
        self.prices = prices or {}
        self.warn = warn
        self.calls: list[tuple[Context, tuple[Gap, ...]]] = []

    def __call__(self, get_json, context, gaps):
        self.calls.append((context, tuple(gaps)))
        found = {
            gap.name: stamped_entry(self.prices[gap.name], "fake", context.league, context.today, "n")
            for gap in gaps
            if gap.name in self.prices
        }
        return StageResult(found, [f"{name}: fake stage" for name in found] if self.warn else [])

    @property
    def gaps(self) -> list[Gap]:
        return [gap for _, gaps in self.calls for gap in gaps]


def thin_hunter_vise(ninja):
    ninja.set_stash_line("BaseType", 34026, count=2)
    ninja.stash_histories[HUNTER_VISE_HISTORY] = ninja_fixture("stash_history_basetype_34026")


# --- stash history rescues a thin line -----------------------------------------------------


def test_a_wanted_thin_base_is_priced_from_its_stash_history(ninja):
    thin_hunter_vise(ninja)

    result = fetch_price_file(ninja, NOW, wanted=[HUNTER_VISE])

    entry = result.price_file.prices[HUNTER_VISE]
    assert entry.chaos == 1313.0  # median of the seven rows daysAgo 0..6: 1262 1349 1348 1365 1233 1034 1313
    assert entry.source == "poe.ninja-history"
    assert entry.note == "median of 7 daily rows in the 7 days ending 2026-10-30"
    assert entry.detail == {"league": "Allflame", "date": "2026-10-30"}
    assert result.warnings == [
        f"{HUNTER_VISE}: no current price, used history (median of 7 daily rows in the 7 days ending 2026-10-30)"
    ]
    assert result.missing == []
    assert HUNTER_VISE in result.thin  # the current line was thin, rescued or not
    assert any("type=BaseType" in url and "id=34026" in url and "league=Allflame" in url
               for url in ninja.stash_history_requests())


def test_a_rescued_price_survives_the_file_round_trip(ninja, tmp_path):
    thin_hunter_vise(ninja)
    price_file = fetch_price_file(ninja, NOW, wanted=[HUNTER_VISE]).price_file

    write_price_file(tmp_path / "prices.json", price_file)

    assert load_price_file(tmp_path / "prices.json") == price_file


def test_a_wanted_thin_beast_whose_history_is_all_thin_stays_missing(ninja):
    ninja.stash_histories[CHIEFTAIN_HISTORY] = ninja_fixture("stash_history_beast_167860")

    result = fetch_price_file(ninja, NOW, wanted=["Aboriginal Chieftain"])

    assert result.missing == ["Aboriginal Chieftain"]
    assert "Aboriginal Chieftain" not in result.price_file.prices
    assert "Aboriginal Chieftain" in result.thin
    assert any("id=167860" in url and "type=Beast" in url for url in ninja.stash_history_requests())
    assert result.warnings == [
        "Aboriginal Chieftain: current line is too thin (fewer than 5 observations or no trade volume) "
        "and no fallback gave a price; dropped"
    ]


def test_a_stash_history_that_answers_with_an_error_leaves_the_name_missing(ninja):
    ninja.set_stash_line("BaseType", 34026, count=2)  # no history set up: it answers 404

    result = fetch_price_file(ninja, NOW, wanted=[HUNTER_VISE])

    assert result.missing == [HUNTER_VISE]
    assert any("too thin" in warning for warning in result.warnings)


def test_a_wanted_base_with_no_line_at_all_is_missing_and_asks_nobody_for_history(ninja):
    result = fetch_price_file(ninja, NOW, wanted=["Stygian Vise (ilvl 83, Hunter)"])

    assert result.missing == ["Stygian Vise (ilvl 83, Hunter)"]
    assert ninja.stash_history_requests() == []
    assert ninja.detail_requests() == []
    assert result.warnings == []  # there was no thin line to explain


def test_history_is_not_asked_for_names_nobody_wanted(ninja):
    thin_hunter_vise(ninja)

    result = fetch_price_file(ninja, NOW)

    assert ninja.stash_history_requests() == []
    assert ninja.detail_requests() == []
    assert HUNTER_VISE in result.thin and HUNTER_VISE not in result.price_file.prices


def test_a_wanted_name_with_a_current_price_asks_for_no_history(ninja):
    result = fetch_price_file(ninja, NOW, wanted=[HUNTER_VISE, "Wild Bristle Matron", "Hollow Fossil"])

    assert ninja.stash_history_requests() == [] and ninja.detail_requests() == []
    assert result.warnings == [] and result.missing == []


# --- the gaps the fetcher hands to the stages ----------------------------------------------


def test_each_kind_of_unpriced_name_becomes_the_gap_its_sources_need(ninja):
    ninja.set_stash_line("BaseType", 34026, count=2)
    for line in ninja.overviews["Fossil"]["lines"]:
        if line["id"] == "hollow-fossil":
            line["volumePrimaryValue"] = 0
    for item in ninja.overviews["Fossil"]["items"]:
        if item["id"] == "hollow-fossil":
            item["detailsId"] = "hollow-fossil-v2"
    recorder = Recorder()

    fetch_price_file(
        ninja,
        NOW,
        wanted=[
            "Hollow Fossil",  # a thin exchange line
            HUNTER_VISE,  # a thin stash line
            "Aboriginal Chieftain",  # a thin beast line
            "Stygian Vise (ilvl 83, Hunter/Warlord)",  # a base with no line
            "Jeweller's Orb",  # no line at all, not a base
            "Wild Bristle Matron",  # priced: no gap
        ],
        stages=[recorder],
    )

    assert {gap.name: gap for gap in recorder.gaps} == {
        "Hollow Fossil": Gap("Hollow Fossil", exchange_id="hollow-fossil-v2"),
        HUNTER_VISE: Gap(
            HUNTER_VISE, stash_kind="BaseType", stash_id=34026, base=BaseKey("Stygian Vise", 85, ("Hunter",))
        ),
        "Aboriginal Chieftain": Gap("Aboriginal Chieftain", stash_kind="Beast", stash_id=167860),
        "Stygian Vise (ilvl 83, Hunter/Warlord)": Gap(
            "Stygian Vise (ilvl 83, Hunter/Warlord)",
            stash_kind="BaseType",
            base=BaseKey("Stygian Vise", 83, ("Hunter", "Warlord")),
        ),
        "Jeweller's Orb": Gap("Jeweller's Orb", exchange_id="jewellers-orb"),
    }


def test_the_context_has_the_league_the_utc_date_and_the_previous_league(ninja):
    recorder = Recorder()

    fetch_price_file(ninja, NOW, wanted=["Zzz"], league="Standard", previous_league="Mirage", stages=[recorder])

    assert recorder.calls[0][0] == Context("Standard", date(2026, 10, 30), "Mirage")


def test_the_context_date_is_the_utc_date_of_the_fetch(ninja):
    recorder = Recorder()
    late_in_moscow = datetime(2026, 10, 31, 1, 30, tzinfo=timezone(timedelta(hours=3)))  # 22:30 UTC on the 30th

    fetch_price_file(ninja, late_in_moscow, wanted=["Zzz"], stages=[recorder])

    assert recorder.calls[0][0].today == date(2026, 10, 30)
    assert recorder.calls[0][0].previous_league is None


# --- the order of the stages ---------------------------------------------------------------


def test_the_default_chain_is_ninja_history_then_poe_watch_then_the_previous_league():
    assert DEFAULT_STAGES == (ninja_history_stage, poe_watch_stage, previous_league_stage)


def test_later_stages_see_only_the_gaps_earlier_ones_left(ninja):
    first = Recorder({"Aaa": 10.0}, warn=True)
    second = Recorder({"Bbb": 20.0}, warn=True)
    third = Recorder()

    result = fetch_price_file(ninja, NOW, wanted=["Aaa", "Bbb", "Ccc"], stages=[first, second, third])

    assert [gap.name for gap in first.gaps] == ["Aaa", "Bbb", "Ccc"]
    assert [gap.name for gap in second.gaps] == ["Bbb", "Ccc"]
    assert [gap.name for gap in third.gaps] == ["Ccc"]
    prices = result.price_file.prices
    assert prices["Aaa"].chaos == 10.0 and prices["Aaa"].source == "fake"
    assert prices["Bbb"].chaos == 20.0
    assert "Ccc" not in prices
    assert result.warnings == ["Aaa: fake stage", "Bbb: fake stage"]
    assert result.missing == ["Ccc"]


def test_the_stages_are_not_called_when_nothing_is_left_to_price(ninja):
    recorder = Recorder()

    fetch_price_file(ninja, NOW, wanted=["Hollow Fossil", HUNTER_VISE], stages=[recorder])

    assert recorder.calls == []


def test_a_stage_never_overwrites_a_price_the_overviews_gave(ninja):
    rogue = Recorder({"Hollow Fossil": 1.0, HUNTER_VISE: 1.0, "Chaos Orb": 99.0, "Zzz": 7.0})

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil", HUNTER_VISE, "Zzz"], stages=[rogue])

    prices = result.price_file.prices
    assert prices["Hollow Fossil"] == PriceEntry(206.8, "poe.ninja")
    assert prices[HUNTER_VISE] == PriceEntry(1262.0, "poe.ninja")
    assert prices["Chaos Orb"] == PriceEntry(1.0, "poe.ninja")
    assert prices["Zzz"].chaos == 7.0


def test_a_stage_after_ninja_history_prices_what_history_could_not(ninja):
    thin_hunter_vise(ninja)
    ninja.set_stash_line("BaseType", 34781, count=1)  # Elder: thin, and no history set up
    after = Recorder({"Stygian Vise (ilvl 85, Elder)": 700.0}, warn=True)

    result = fetch_price_file(
        ninja,
        NOW,
        wanted=[HUNTER_VISE, "Stygian Vise (ilvl 85, Elder)"],
        stages=[ninja_history_stage, after],
    )

    assert [gap.name for gap in after.gaps] == ["Stygian Vise (ilvl 85, Elder)"]
    prices = result.price_file.prices
    assert prices[HUNTER_VISE].source == "poe.ninja-history"
    assert prices["Stygian Vise (ilvl 85, Elder)"].source == "fake"
    assert result.missing == []
    assert "Stygian Vise (ilvl 85, Elder)" in result.thin


def test_the_thin_list_keeps_names_a_fallback_rescued(ninja):
    thin_hunter_vise(ninja)
    ninja.set_stash_line("BaseType", 34781, count=1)

    result = fetch_price_file(ninja, NOW, wanted=[HUNTER_VISE])

    assert HUNTER_VISE in result.thin and "Stygian Vise (ilvl 85, Elder)" in result.thin
    assert HUNTER_VISE in result.price_file.prices


def test_no_stages_means_no_fallback(ninja):
    thin_hunter_vise(ninja)

    result = fetch_price_file(ninja, NOW, wanted=[HUNTER_VISE], stages=())

    assert result.missing == [HUNTER_VISE]
    assert ninja.stash_history_requests() == []


# --- the command line ----------------------------------------------------------------------


def test_fetch_passes_the_previous_league_to_the_chain(ninja, tmp_path, monkeypatch):
    seen = {}

    def fake_fetch(get_json, now, wanted, league, previous_league):
        seen["previous_league"] = previous_league
        return fetch_price_file(get_json, now, wanted, league, previous_league, stages=())

    monkeypatch.setattr("crafting_system.prices.__main__.fetch_price_file", fake_fetch)

    code = main(
        ["fetch", "--previous-league", "Mirage"], get_json=ninja, now=NOW, env={"CRAFTING_DATA_DIR": str(tmp_path)}
    )

    assert code == 0
    assert seen == {"previous_league": "Mirage"}


def test_fetch_prints_a_rescued_price_warning_and_still_counts_the_thin_line(ninja, tmp_path, capsys):
    thin_hunter_vise(ninja)
    wanted = tmp_path / "wanted.txt"
    wanted.write_text(f"{HUNTER_VISE}\n", encoding="utf-8")

    code = main(
        ["fetch", "--wanted-file", str(wanted)], get_json=ninja, now=NOW, env={"CRAFTING_DATA_DIR": str(tmp_path / "data")}
    )

    out = capsys.readouterr().out
    assert code == 0
    assert f"Warning: {HUNTER_VISE}: no current price, used history" in out
    assert "7 current lines were too thin to price" in out  # the six recorded ones plus the edited one
    assert "No price for" not in out
