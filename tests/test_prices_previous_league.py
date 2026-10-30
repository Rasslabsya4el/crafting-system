"""The previous-league and Standard fallback stage on recorded responses (no network, no clock)."""

import statistics
from datetime import date, timedelta

import pytest

from watch_support import FakeWatch, NINJA_HOST, ninja_fixture, watch  # noqa: F401  (watch is a fixture)
from crafting_system.prices.fallbacks import Context, Gap
from crafting_system.prices.http_json import SourceError
from crafting_system.prices.previous_league import previous_league_stage

TODAY = date(2026, 10, 30)
CONTEXT = Context(league="Allflame", today=TODAY)

HOLLOW = Gap("Hollow Fossil", exchange_id="hollow-fossil")
VISE = Gap("Stygian Vise (ilvl 85, Hunter)", stash_kind="BaseType", stash_id=34026)

DETAILS = "/poe1/api/economy/exchange/current/details"
STASH = "/poe1/api/economy/stash/current/item/history"
DUMPS = "/poe1/api/data/dumps"


def run(watch: FakeWatch, *gaps: Gap, context: Context = CONTEXT):
    return previous_league_stage(watch, context, gaps)


def leagues_asked(watch: FakeWatch, route: str) -> list[str]:
    return [url.split("league=")[1].split("&")[0] for url in watch.asked(NINJA_HOST, route)]


def mirage_stash_median() -> float:
    """Median of the recorded Mirage stash rows on 2026-06-06..12, counted by hand from the fixture."""
    end = date(2026, 7, 20)
    rows = ninja_fixture("stash_history_basetype_34026_mirage")
    values = [r["value"] for r in rows if date(2026, 6, 6) <= end - timedelta(days=r["daysAgo"]) <= date(2026, 6, 12) and r["count"] >= 5]
    assert len(values) == 7
    return statistics.median(values)


def mirage_exchange_median() -> float:
    history = ninja_fixture("details_hollow_fossil_mirage")["pairs"][0]["history"]
    values = [r["rate"] for r in history if "2026-06-06" <= r["timestamp"][:10] <= "2026-06-12" and r["volumePrimaryValue"] > 0]
    assert len(values) == 7
    return statistics.median(values)


def standard_stash_median() -> float:
    rows = ninja_fixture("stash_history_basetype_34026_standard")
    return statistics.median(r["value"] for r in rows if r["daysAgo"] <= 6 and r["count"] >= 5)


# --- the previous league at the same age -----------------------------------------------------


def test_mirage_is_the_previous_league_not_ancestors(watch):
    run(watch, HOLLOW)

    assert set(leagues_asked(watch, DETAILS)) == {"Mirage"}
    assert len(watch.asked(NINJA_HOST, DUMPS)) == 1


def test_the_previous_league_prices_a_stash_base_at_the_same_league_age(watch):
    result = run(watch, VISE)

    entry = result.prices[VISE.name]
    assert entry.chaos == mirage_stash_median()
    assert entry.source == "poe.ninja-previous-league"
    assert entry.detail == {"league": "Mirage", "date": "2026-06-12", "age_days": 98, "current_league": "Allflame"}
    assert "same league age in an older league" in entry.note and "2026-06-12" in entry.note
    assert "7 poe.ninja daily rows" in entry.note
    assert [url.split("id=")[1] for url in watch.asked(NINJA_HOST, STASH)] == ["34026"]
    assert leagues_asked(watch, STASH) == ["Mirage"]


def test_the_previous_league_prices_an_exchange_item_with_a_warning(watch):
    result = run(watch, HOLLOW)

    entry = result.prices["Hollow Fossil"]
    assert entry.chaos == mirage_exchange_median() == 238.0
    assert entry.source == "poe.ninja-previous-league"
    assert entry.detail == {"league": "Mirage", "date": "2026-06-12", "age_days": 98, "current_league": "Allflame"}
    assert result.warnings == [
        "Hollow Fossil: no usable price in Allflame; used 238 Chaos from Mirage at league day 98 (2026-06-12): "
        "a different economy, check it"
    ]
    assert "Standard" not in " ".join(watch.requests)


def test_the_age_is_asked_once_from_poe_watchs_league_list(watch):
    run(watch, HOLLOW, VISE)

    assert watch.asked("api.poe.watch", "/leagues") == ["https://api.poe.watch/leagues"]


def test_the_age_and_the_window_follow_the_date_of_the_fetch(watch):
    result = run(watch, HOLLOW, context=Context("Allflame", date(2026, 10, 25)))

    history = ninja_fixture("details_hollow_fossil_mirage")["pairs"][0]["history"]
    values = [r["rate"] for r in history if "2026-06-01" <= r["timestamp"][:10] <= "2026-06-07" and r["volumePrimaryValue"] > 0]
    assert result.prices["Hollow Fossil"].chaos == statistics.median(values)
    assert result.prices["Hollow Fossil"].detail["age_days"] == 93
    assert result.prices["Hollow Fossil"].detail["date"] == "2026-06-07"


def test_the_owners_previous_league_wins(watch):
    watch.details[("Keepers", "Fossil", "hollow-fossil")] = ninja_fixture("details_hollow_fossil_mirage")

    run(watch, HOLLOW, context=Context("Allflame", TODAY, previous_league="Keepers"))

    assert set(leagues_asked(watch, DETAILS)) == {"Keepers", "Standard"}  # no rows of Keepers at league day 98 here


def test_the_owners_previous_league_prices_from_its_own_dates(watch):
    watch.details[("Keepers", "Fossil", "hollow-fossil")] = {
        "pairs": [{"id": "chaos", "history": [{"timestamp": "2026-02-02T00:00:00Z", "rate": 42.5, "volumePrimaryValue": 8}]}]
    }

    result = run(watch, HOLLOW, context=Context("Allflame", TODAY, previous_league="Keepers"))

    entry = result.prices["Hollow Fossil"]  # Keepers started 2025-10-31: day 98 is 2026-02-06, window 01-31..02-06
    assert (entry.chaos, entry.detail["league"], entry.detail["date"]) == (42.5, "Keepers", "2026-02-02")
    assert "from Keepers at league day 98" in result.warnings[0]


def test_an_owner_league_missing_from_poe_ninjas_list_warns_and_goes_to_standard(watch):
    result = run(watch, VISE, context=Context("Allflame", TODAY, previous_league="Nope"))

    assert result.warnings[0] == "previous league Nope is not in poe.ninja's league list"
    assert result.prices[VISE.name].detail["league"] == "Standard"
    assert watch.asked("api.poe.watch", "/leagues") == []
    assert "league=Mirage" not in " ".join(watch.requests)


def test_the_current_league_and_other_modes_are_not_previous_leagues(watch):
    watch.dumps += [
        {"leagueName": "Hardcore Mirage", "minDate": "2026-03-06T00:00:00Z", "maxDate": "2026-07-25T00:00:00Z"},
        {"leagueName": "HC SSF Mirage", "minDate": "2026-03-06T00:00:00Z", "maxDate": "2026-07-26T00:00:00Z"},
        {"leagueName": "Ruthless Mirage", "minDate": "2026-03-06T00:00:00Z", "maxDate": "2026-07-27T00:00:00Z"},
        {"leagueName": "Solo Self-Found", "minDate": "2013-01-23T00:00:00Z", "maxDate": "2026-08-01T00:00:00Z"},
        {"leagueName": "Standard", "minDate": "2013-01-23T00:00:00Z", "maxDate": "2026-10-30T00:00:00Z"},
        {"leagueName": "Allflame", "minDate": "2026-07-24T00:00:00Z", "maxDate": "2026-10-30T00:00:00Z"},
    ]

    run(watch, HOLLOW)

    assert set(leagues_asked(watch, DETAILS)) == {"Mirage"}


def test_a_tie_on_the_last_day_goes_to_the_league_that_started_later(watch):
    watch.dumps.append({"leagueName": "Early", "minDate": "2026-01-01T00:00:00Z", "maxDate": "2026-07-20T00:00:00Z"})

    run(watch, HOLLOW)

    assert set(leagues_asked(watch, DETAILS)) == {"Mirage"}


def test_a_short_event_league_ending_later_does_not_hide_the_real_previous_league(watch):
    watch.dumps.append({"leagueName": "Ancestors 2", "minDate": "2026-06-25T00:00:00Z", "maxDate": "2026-07-25T00:00:00Z"})

    result = run(watch, HOLLOW)

    assert result.prices["Hollow Fossil"].detail["league"] == "Mirage"
    assert set(leagues_asked(watch, DETAILS)) == {"Mirage"}  # Ancestors 2 ends 2026-07-25 but starts on 06-25: day 98 is 10-01
    assert len(watch.asked(NINJA_HOST, DUMPS)) == 1
    assert len(watch.asked("api.poe.watch", "/leagues")) == 1


def test_the_last_league_to_reach_the_age_wins(watch):
    watch.dumps.append({"leagueName": "Long", "minDate": "2026-03-06T00:00:00Z", "maxDate": "2026-07-14T00:00:00Z"})  # reaches day 98 too, ends earlier

    run(watch, HOLLOW)

    assert set(leagues_asked(watch, DETAILS)) == {"Mirage"}


def test_a_league_that_ends_exactly_on_the_age_reaches_it(watch):
    watch.dumps = [{"leagueName": "Exact", "minDate": "2026-03-06T00:00:00Z", "maxDate": "2026-06-12T00:00:00Z"}]
    watch.details[("Exact", "Fossil", "hollow-fossil")] = ninja_fixture("details_hollow_fossil_mirage")

    result = run(watch, HOLLOW)

    assert result.prices["Hollow Fossil"].detail["league"] == "Exact"
    assert result.prices["Hollow Fossil"].chaos == mirage_exchange_median()


def test_no_league_that_reaches_the_age_warns_once_and_goes_to_standard(watch):
    watch.dumps = [{"leagueName": "Ancestors", "minDate": "2026-06-25T00:00:00Z", "maxDate": "2026-07-16T00:00:00Z"}]

    result = run(watch, VISE)

    assert result.warnings[0] == "no league in poe.ninja's league list lasted until league day 98; previous league skipped"
    assert len(result.warnings) == 2
    assert result.prices[VISE.name].source == "poe.ninja-standard"
    assert leagues_asked(watch, STASH) == ["Standard"]


def test_an_unknown_age_does_not_ask_for_the_league_dump(watch):
    watch.leagues = SourceError("HTTP 500")

    run(watch, VISE)

    assert watch.asked(NINJA_HOST, DUMPS) == []


def test_a_previous_league_that_ended_before_the_current_age_is_skipped(watch):
    result = run(watch, HOLLOW, context=Context("Allflame", TODAY, previous_league="Ancestors"))

    assert "league=Ancestors" not in " ".join(watch.requests)
    assert result.warnings[0] == "previous league Ancestors ended on 2026-07-16, before league day 98; skipped"
    assert result.prices == {}  # Standard's rows are all untraded too


def test_the_previous_leagues_end_date_anchors_a_stash_history(watch):
    result = run(watch, VISE)

    # Mirage's last day is 2026-07-20 (daysAgo 0); day 2026-06-12 is daysAgo 38, so the window is daysAgo 38..44
    rows = ninja_fixture("stash_history_basetype_34026_mirage")
    by_ago = {r["daysAgo"]: r["value"] for r in rows}
    assert result.prices[VISE.name].chaos == statistics.median(by_ago[ago] for ago in range(38, 45))


def test_an_unknown_age_skips_the_previous_league_but_tries_standard(watch):
    for leagues in (SourceError("HTTP 500"), [], "text", [{"name": "Allflame"}], [{"name": "Allflame", "start_date": "soon"}]):
        watch.requests.clear()
        watch.leagues = leagues

        result = run(watch, VISE)

        assert result.warnings[0].startswith("the age of Allflame is unknown")
        assert len(result.warnings) == 2
        assert result.prices[VISE.name].source == "poe.ninja-standard"
        assert "league=Mirage" not in " ".join(watch.requests)


def test_a_league_start_in_the_future_counts_as_an_unknown_age(watch):
    watch.leagues = [{"name": "Allflame", "start_date": "2026-11-05T20:00:00Z", "end_date": "0001-01-01T00:00:00Z"}]

    assert run(watch, VISE).warnings[0].startswith("the age of Allflame is unknown")


def test_a_failing_league_dump_warns_and_goes_to_standard(watch):
    for dumps in (SourceError("HTTP 500"), [], {}, "text", [None, 5, {"leagueName": "Mirage"}, {"leagueName": 3, "minDate": "x", "maxDate": "y"}]):
        watch.requests.clear()
        watch.dumps = dumps

        result = run(watch, VISE)

        assert result.warnings[0] == "poe.ninja's league list gave no previous league"
        assert result.prices[VISE.name].source == "poe.ninja-standard"
        assert len(watch.asked("api.poe.watch", "/leagues")) == 1


def test_a_gap_the_previous_league_cannot_price_falls_through_to_standard(watch):
    result = run(watch, Gap("Mystery Beast", stash_kind="Beast", stash_id=4242))

    assert result.prices == {}
    assert leagues_asked(watch, STASH) == ["Mirage", "Standard"]


def test_changed_history_shapes_leave_the_gap_without_raising(watch):
    for bad in (SourceError("HTTP 500"), None, {}, "text", [None, {"count": "x"}, {"count": 9, "value": 5, "daysAgo": -1}]):
        watch.stash[("Mirage", "BaseType", 34026)] = bad
        watch.stash[("Standard", "BaseType", 34026)] = bad

        assert run(watch, VISE).prices == {}


# --- Standard --------------------------------------------------------------------------------


def test_standard_prices_a_stash_base_and_leaves_a_gap_with_untraded_rows(watch):
    result = run(watch, VISE, HOLLOW, context=Context("Allflame", TODAY, previous_league="Standard"))

    assert set(result.prices) == {VISE.name}  # Standard's Hollow Fossil rows all have volume 0
    entry = result.prices[VISE.name]
    assert entry.chaos == standard_stash_median() == 1130
    assert entry.source == "poe.ninja-standard"
    assert entry.detail == {"league": "Standard", "date": "2026-10-30", "current_league": "Allflame"}
    assert "Standard economy" in entry.note
    assert result.warnings == [
        "Stygian Vise (ilvl 85, Hunter): no usable price in Allflame; used 1130 Chaos from Standard (2026-10-30): "
        "the Standard economy, check it"
    ]
    assert watch.asked(NINJA_HOST, DUMPS) == [] and watch.asked("api.poe.watch", "/leagues") == []


def test_standard_takes_the_gaps_the_previous_league_left(watch):
    other = Gap("Mystery Fossil", exchange_id="mystery-fossil")
    watch.details[("Standard", "Fossil", "mystery-fossil")] = {
        "pairs": [{"id": "chaos", "history": [{"timestamp": "2026-10-29T00:00:00Z", "rate": 12.0, "volumePrimaryValue": 5}]}]
    }

    result = run(watch, HOLLOW, VISE, other)

    assert result.prices["Hollow Fossil"].source == "poe.ninja-previous-league"
    assert result.prices[VISE.name].source == "poe.ninja-previous-league"
    assert result.prices["Mystery Fossil"].source == "poe.ninja-standard"
    assert result.prices["Mystery Fossil"].detail == {"league": "Standard", "date": "2026-10-29", "current_league": "Allflame"}
    assert leagues_asked(watch, STASH) == ["Mirage"]  # priced gaps do not go on to Standard


def test_standards_window_is_the_seven_days_ending_today(watch):
    watch.stash[("Standard", "BaseType", 34026)] = [
        {"count": 20, "value": 100, "daysAgo": 0},
        {"count": 20, "value": 300, "daysAgo": 6},
        {"count": 20, "value": 9999, "daysAgo": 7},
        {"count": 4, "value": 9999, "daysAgo": 1},
    ]

    entry = run(watch, VISE, context=Context("Allflame", TODAY, previous_league="Standard")).prices[VISE.name]

    assert entry.chaos == 200


# --- where it does not apply, and how much it asks ---------------------------------------------


@pytest.mark.parametrize(
    "league",
    ["Standard", "standard", "Hardcore", "Hardcore Allflame", "HC Allflame", "HC Ruthless Allflame", "Ruthless Allflame", "SSF Allflame", "Solo Self-Found"],
)
def test_it_is_not_applied_to_standard_hardcore_ruthless_or_solo_leagues(watch, league):
    result = run(watch, HOLLOW, VISE, context=Context(league, TODAY))

    assert result.prices == {} and result.warnings == []
    assert watch.requests == []


def test_gaps_without_an_id_are_skipped_and_ask_nothing(watch):
    result = run(watch, Gap("Mystery"), Gap("Half a line", stash_kind="Beast"), Gap("Other half", stash_id=5))

    assert result.prices == {} and result.warnings == []
    assert watch.requests == []


def test_no_gaps_ask_nothing(watch):
    assert run(watch).prices == {}
    assert watch.requests == []


def test_nothing_is_asked_twice(watch):
    run(watch, HOLLOW, VISE, Gap("Mystery Fossil", exchange_id="mystery-fossil"), Gap("Mystery Beast", stash_kind="Beast", stash_id=4242))

    assert len(watch.requests) == len(set(watch.requests))
    assert len(watch.asked(NINJA_HOST, DUMPS)) == 1
    assert len(watch.asked("api.poe.watch", "/leagues")) == 1
