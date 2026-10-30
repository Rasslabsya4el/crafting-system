"""The poe.ninja fetcher and its history fallback, on recorded responses (no network, no clock)."""

import http.client
import statistics
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest

from ninja_support import OVERVIEW_TYPES, STASH_TYPES, ninja, ninja_fixture  # noqa: F401  (ninja is a fixture)
from crafting_system.prices import (
    CHAOS_ORB,
    DIVINE_ORB,
    PriceEntry,
    default_overrides_path,
    load_price_file,
    write_price_file,
)
from crafting_system.config import Config
from crafting_system.prices.fetch import fetch_price_file
from crafting_system.prices.poe_ninja import (
    BASE_URL,
    USER_AGENT,
    SourceError,
    history_slug,
    http_get_json,
)

NOW = datetime(2026, 10, 30, 21, 0, 5, 123456, tzinfo=UTC)


def fixture_price(kind: str, name: str) -> float:
    """primaryValue of the named item in a recorded overview, looked up by hand from the fixture."""
    overview = ninja_fixture(f"overview_{kind.lower()}")
    ids = {item["name"]: item["id"] for item in overview["items"]}
    return next(line["primaryValue"] for line in overview["lines"] if line["id"] == ids[name])


def usable_history_rates() -> list[float]:
    """Chaos rates of the recorded Hollow Fossil history, newest first, volume above zero."""
    pairs = ninja_fixture("details_hollow_fossil")["pairs"]
    rows = next(pair for pair in pairs if pair["id"] == "chaos")["history"]
    rows = sorted(rows, key=lambda row: row["timestamp"], reverse=True)
    return [row["rate"] for row in rows if row["volumePrimaryValue"] > 0]


def set_line(ninja, kind, line_id, **changes):
    for line in ninja.overviews[kind]["lines"]:
        if line["id"] == line_id:
            line.update(changes)
            return
    raise AssertionError(line_id)


# --- the current league and the prices -----------------------------------------------------


def test_the_current_league_is_the_first_one_poe_ninja_lists(ninja):
    result = fetch_price_file(ninja, NOW)

    assert result.price_file.league == "Allflame"
    assert ninja.requests[0] == f"{BASE_URL}/leagues"
    overview_urls = [url for url in ninja.requests if "/overview" in url]
    assert len(overview_urls) == len(OVERVIEW_TYPES) + len(STASH_TYPES)
    assert all("league=Allflame" in url for url in overview_urls)
    for kind in OVERVIEW_TYPES:
        assert any(f"/exchange/current/overview?league=Allflame&type={kind}" in url for url in overview_urls)
    stash_urls = [url for url in overview_urls if "/stash/" in url]
    assert [url.split("type=")[1] for url in stash_urls] == ["Beast", "BaseType"]
    assert overview_urls[-2:] == stash_urls  # the stash overviews come after the four exchange ones


def test_prices_are_the_recorded_values_in_chaos(ninja):
    prices = fetch_price_file(ninja, NOW).price_file.prices

    assert prices[CHAOS_ORB] == PriceEntry(1.0, "poe.ninja")
    assert prices[DIVINE_ORB].chaos == fixture_price("Currency", "Divine Orb") == 359.7
    assert prices["Hollow Fossil"].chaos == fixture_price("Fossil", "Hollow Fossil") == 206.8
    assert prices["Deafening Essence of Doubt"].chaos == 1.0
    assert prices["Potent Chaotic Resonator"].chaos == 1.6
    assert prices["Fracturing Orb"].chaos == 254.3
    assert prices["Hollow Fossil"].source == "poe.ninja"
    assert prices["Hollow Fossil"].note is None


def test_every_recorded_line_becomes_a_price(ninja):
    prices = fetch_price_file(ninja, NOW).price_file.prices

    for kind in OVERVIEW_TYPES:
        overview = ninja_fixture(f"overview_{kind.lower()}")
        names = {item["name"] for item in overview["items"]}
        assert names - set(prices) == set()


def test_chaos_per_divine_is_the_divine_orb_price(ninja):
    assert fetch_price_file(ninja, NOW).price_file.chaos_per_divine == 359.7


def test_the_divine_price_comes_from_the_rates_when_the_divine_line_is_missing(ninja):
    ninja.drop_line("Currency", "divine")

    price_file = fetch_price_file(ninja, NOW).price_file

    assert price_file.chaos_per_divine == pytest.approx(1 / 0.00278)
    assert price_file.prices[DIVINE_ORB].chaos == pytest.approx(1 / 0.00278)


def test_no_divine_price_at_all_is_an_error(ninja):
    ninja.drop_line("Currency", "divine")
    del ninja.overviews["Currency"]["core"]["rates"]

    with pytest.raises(SourceError, match="Divine"):
        fetch_price_file(ninja, NOW)


def test_chaos_orb_is_one_even_when_poe_ninja_has_no_line_for_it(ninja):
    ninja.drop_line("Currency", "chaos")

    assert fetch_price_file(ninja, NOW).price_file.prices[CHAOS_ORB].chaos == 1.0


def test_the_fetch_time_is_stored_in_utc_whole_seconds(ninja):
    price_file = fetch_price_file(ninja, NOW).price_file

    assert price_file.fetched_at == datetime(2026, 10, 30, 21, 0, 5, tzinfo=UTC)


def test_a_fetch_time_without_a_zone_is_refused(ninja):
    with pytest.raises(ValueError, match="time zone"):
        fetch_price_file(ninja, datetime(2026, 10, 30, 21, 0))


def test_the_fetched_file_writes_and_reads_back_equal(ninja, tmp_path):
    price_file = fetch_price_file(ninja, NOW).price_file
    path = tmp_path / "data" / "prices.json"

    write_price_file(path, price_file)

    assert load_price_file(path) == price_file


def test_lines_without_a_usable_price_or_a_name_are_skipped(ninja):
    set_line(ninja, "Fossil", "bound-fossil", primaryValue=0)
    set_line(ninja, "Fossil", "aberrant-fossil", primaryValue=-3)
    set_line(ninja, "Fossil", "dense-fossil", primaryValue="14")
    del ninja.overviews["Fossil"]["lines"][3]["primaryValue"]  # jagged-fossil
    ninja.overviews["Fossil"]["lines"].append({"id": "nameless", "primaryValue": 5, "volumePrimaryValue": 9})
    ninja.overviews["Fossil"]["lines"].append("garbage")

    prices = fetch_price_file(ninja, NOW).price_file.prices

    assert {name for name in prices if name.endswith("Fossil")} == {"Pristine Fossil", "Hollow Fossil"}


def test_a_league_name_with_a_space_is_url_encoded(ninja):
    ninja.leagues = [{"id": "Hardcore Allflame", "name": "Hardcore Allflame"}, {"id": "Allflame"}]

    result = fetch_price_file(ninja, NOW)

    assert result.price_file.league == "Hardcore Allflame"
    overview_urls = [url for url in ninja.requests if "/overview" in url]
    assert overview_urls and all("league=Hardcore%20Allflame" in url for url in overview_urls)
    assert not any(" " in url for url in ninja.requests)


def test_a_given_league_skips_the_leagues_call(ninja):
    result = fetch_price_file(ninja, NOW, league="Standard")

    assert result.price_file.league == "Standard"
    assert not any(url.endswith("/leagues") for url in ninja.requests)
    assert all("league=Standard" in url for url in ninja.requests)


@pytest.mark.parametrize("leagues", [[], {"id": "x"}, [{"name": "x"}], [{"id": ""}], "x"])
def test_an_unusable_leagues_answer_is_an_error(ninja, leagues):
    ninja.leagues = leagues

    with pytest.raises(SourceError, match="league"):
        fetch_price_file(ninja, NOW)


def test_the_leagues_call_failing_raises(ninja):
    ninja.leagues = SourceError("network down")

    with pytest.raises(SourceError, match="network down"):
        fetch_price_file(ninja, NOW)


# --- categories that fail ------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["Currency", "Fossil", "Resonator", "Essence"])
def test_any_failing_category_raises_and_says_the_old_file_was_kept(ninja, kind):
    ninja.overviews[kind] = SourceError(f"HTTP 500 for {kind}")

    with pytest.raises(SourceError, match=kind) as error:
        fetch_price_file(ninja, NOW)

    assert "old price file was kept" in str(error.value)
    assert f"HTTP 500 for {kind}" in str(error.value)


@pytest.mark.parametrize("kind", ["Currency", "Fossil", "Resonator", "Essence"])
def test_prices_not_in_chaos_fail_the_whole_fetch(ninja, kind):
    ninja.overviews[kind]["core"]["primary"] = "divine"

    with pytest.raises(SourceError, match=kind) as error:
        fetch_price_file(ninja, NOW)

    assert "chaos" in str(error.value)


@pytest.mark.parametrize("kind", ["Fossil", "Essence"])
def test_a_category_with_an_empty_lines_list_fails_the_whole_fetch(ninja, kind):
    ninja.overviews[kind]["lines"] = []
    ninja.overviews[kind]["items"] = []

    with pytest.raises(SourceError, match=kind) as error:
        fetch_price_file(ninja, NOW)

    assert "old price file was kept" in str(error.value)


def test_a_category_whose_lines_all_lack_a_usable_price_fails_the_whole_fetch(ninja):
    for line in ninja.overviews["Resonator"]["lines"]:
        line["primaryValue"] = 0

    with pytest.raises(SourceError, match="Resonator"):
        fetch_price_file(ninja, NOW)


@pytest.mark.parametrize(
    "answer", [[], {"lines": []}, {"core": {"primary": "chaos"}, "lines": 5, "items": []}]
)
def test_a_changed_overview_shape_fails_the_whole_fetch(ninja, answer):
    ninja.overviews["Resonator"] = answer

    with pytest.raises(SourceError, match="Resonator"):
        fetch_price_file(ninja, NOW)


@pytest.mark.parametrize("league", ["", "   "])
def test_a_blank_league_is_refused(ninja, league):
    with pytest.raises(ValueError, match="league"):
        fetch_price_file(ninja, NOW, league=league)

    assert ninja.requests == []


# --- history fallback ----------------------------------------------------------------------


def test_a_wanted_name_with_no_current_line_gets_the_median_of_the_last_seven_days(ninja):
    ninja.drop_line("Fossil", "hollow-fossil")
    last_seven_days = usable_history_rates()[:7]  # the fixture runs 2026-10-21..30, NOW is the 30th

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil", "Chaos Orb"])

    entry = result.price_file.prices["Hollow Fossil"]
    assert entry.chaos == statistics.median(last_seven_days) == 158.5
    assert entry.source == "poe.ninja-history"
    assert entry.note == "median of 7 daily rows in the 7 days ending 2026-10-30"
    assert result.missing == []
    assert any("Hollow Fossil" in warning and "history" in warning for warning in result.warnings)
    assert any("id=hollow-fossil" in url and "league=Allflame" in url for url in ninja.detail_requests())


def test_a_name_that_has_a_current_line_never_asks_for_history(ninja):
    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil", "Divine Orb"])

    assert ninja.detail_requests() == []
    assert result.price_file.prices["Hollow Fossil"].source == "poe.ninja"


def test_history_is_not_asked_for_names_nobody_wanted(ninja):
    ninja.drop_line("Fossil", "hollow-fossil")

    result = fetch_price_file(ninja, NOW)

    assert ninja.detail_requests() == []
    assert "Hollow Fossil" not in result.price_file.prices
    assert result.missing == []


def set_history(ninja, rows):
    """Replace the Hollow Fossil history with rows given as (days before NOW, rate, volume)."""
    history = [
        {
            "timestamp": f"{(NOW.date() - timedelta(days=days)).isoformat()}T00:00:00Z",
            "rate": rate,
            "volumePrimaryValue": volume,
        }
        for days, rate, volume in rows
    ]
    ninja.details[("Fossil", "hollow-fossil")] = {"pairs": [{"id": "chaos", "history": history}]}


def test_only_rows_with_volume_inside_the_seven_day_window_count(ninja):
    ninja.drop_line("Fossil", "hollow-fossil")
    set_history(
        ninja,
        [
            (-1, 7777.0, 100),  # tomorrow: not in the window
            (0, 999.0, 0),  # today, no trades
            (1, 888.0, 0),
            (2, 10.0, 50),
            (3, 20.0, 50),
            (4, 30.0, 50),
            (5, 40.0, 50),
            (6, 50.0, 50),  # the oldest day of the window
            (7, 5000.0, 100),  # one day too old
        ],
    )

    entry = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil"]).price_file.prices["Hollow Fossil"]

    assert entry.chaos == 30.0
    assert entry.note == "median of 5 daily rows in the 7 days ending 2026-10-30"


def test_fewer_than_seven_usable_rows_still_give_a_median(ninja):
    ninja.drop_line("Fossil", "hollow-fossil")
    set_history(ninja, [(0, 213.0, 5), (1, 165.3, 5), (2, 158.5, 5), (3, 1.0, 0)])

    entry = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil"]).price_file.prices["Hollow Fossil"]

    assert entry.chaos == statistics.median([213.0, 165.3, 158.5])
    assert entry.note == "median of 3 daily rows in the 7 days ending 2026-10-30"


def test_history_that_is_only_old_leaves_the_name_missing_not_priced(ninja):
    ninja.drop_line("Fossil", "hollow-fossil")
    two_months_later = datetime(2026, 12, 30, 12, 0, tzinfo=UTC)  # the fixture ends 2026-10-30

    result = fetch_price_file(ninja, two_months_later, wanted=["Hollow Fossil"])

    assert "Hollow Fossil" not in result.price_file.prices
    assert result.missing == ["Hollow Fossil"]


def test_history_without_usable_rows_leaves_the_name_missing(ninja):
    ninja.drop_line("Fossil", "hollow-fossil")
    for row in ninja.details[("Fossil", "hollow-fossil")]["pairs"][0]["history"]:
        row["volumePrimaryValue"] = 0

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil"])

    assert "Hollow Fossil" not in result.price_file.prices
    assert result.missing == ["Hollow Fossil"]


def test_a_details_404_leaves_the_name_missing_without_crashing(ninja):
    ninja.drop_line("Fossil", "hollow-fossil")
    ninja.details.clear()

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil", "Divine Orb"])

    assert result.missing == ["Hollow Fossil"]
    assert "Divine Orb" in result.price_file.prices


@pytest.mark.parametrize(
    "answer",
    [
        {},
        [],
        "gone",
        {"pairs": "x"},
        {"pairs": []},
        {"pairs": [{"id": "divine", "history": [{"timestamp": "2026-10-30T00:00:00Z", "rate": 2, "volumePrimaryValue": 5}]}]},
        {"pairs": [{"id": "chaos"}]},
        {"pairs": [{"id": "chaos", "history": "x"}]},
        {"pairs": [{"id": "chaos", "history": ["x", 5, {}]}]},
        {"pairs": [{"id": "chaos", "history": [{"timestamp": "2026-10-30T00:00:00Z", "rate": "5", "volumePrimaryValue": 5}]}]},
        {"pairs": [{"id": "chaos", "history": [{"timestamp": "2026-10-30T00:00:00Z", "rate": -5, "volumePrimaryValue": 5}]}]},
        {"pairs": [{"id": "chaos", "history": [{"rate": 5, "volumePrimaryValue": 5}]}]},
        SourceError("invalid JSON"),
    ],
)
def test_a_changed_details_shape_leaves_the_name_missing_without_crashing(ninja, answer):
    ninja.drop_line("Fossil", "hollow-fossil")
    ninja.details = {("Fossil", "hollow-fossil"): answer}

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil"])

    assert result.missing == ["Hollow Fossil"]
    assert "Hollow Fossil" not in result.price_file.prices


def test_history_is_tried_under_each_overview_type_until_one_answers(ninja):
    ninja.drop_line("Fossil", "hollow-fossil")
    ninja.details = {("Resonator", "hollow-fossil"): ninja_fixture("details_hollow_fossil")}

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil"])

    assert result.price_file.prices["Hollow Fossil"].source == "poe.ninja-history"
    assert {url.split("type=")[1].split("&")[0] for url in ninja.detail_requests()} >= {"Resonator"}


def test_a_zero_volume_current_line_is_rescued_by_history(ninja):
    set_line(ninja, "Fossil", "hollow-fossil", volumePrimaryValue=0)

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil"])

    entry = result.price_file.prices["Hollow Fossil"]
    assert entry.chaos == 158.5
    assert entry.source == "poe.ninja-history"


def test_a_zero_volume_line_that_history_cannot_rescue_is_dropped(ninja):
    set_line(ninja, "Fossil", "hollow-fossil", volumePrimaryValue=0)
    ninja.details.clear()

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil"])

    assert "Hollow Fossil" not in result.price_file.prices
    assert result.missing == ["Hollow Fossil"]


def test_a_zero_volume_line_nobody_wanted_is_dropped_too(ninja):
    set_line(ninja, "Fossil", "hollow-fossil", volumePrimaryValue=0)

    result = fetch_price_file(ninja, NOW)

    assert "Hollow Fossil" not in result.price_file.prices
    assert ninja.detail_requests() == []


def test_a_zero_volume_line_asks_history_with_its_own_details_id(ninja):
    set_line(ninja, "Fossil", "hollow-fossil", volumePrimaryValue=0)
    for item in ninja.overviews["Fossil"]["items"]:
        if item["id"] == "hollow-fossil":
            item["detailsId"] = "hollow-fossil-v2"
    ninja.details = {("Fossil", "hollow-fossil-v2"): ninja_fixture("details_hollow_fossil")}

    result = fetch_price_file(ninja, NOW, wanted=["Hollow Fossil"])

    assert result.price_file.prices["Hollow Fossil"].chaos == 158.5


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Hollow Fossil", "hollow-fossil"),
        ("Jeweller's Orb", "jewellers-orb"),
        ("Deafening Essence of Doubt", "deafening-essence-of-doubt"),
        ("Orb of  Annulment ", "orb-of-annulment"),
    ],
)
def test_history_ids_follow_the_poe_ninja_spelling(name, slug):
    assert history_slug(name) == slug


def test_missing_lists_wanted_names_no_source_could_price(ninja):
    result = fetch_price_file(ninja, NOW, wanted=["Zzz", "Hollow Fossil", "Aaa", "Zzz"])

    assert result.missing == ["Aaa", "Zzz"]


# --- the real transport --------------------------------------------------------------------


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_real_transport_sends_a_user_agent_and_decodes_json(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return FakeResponse(b'{"a": [1, 2]}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert http_get_json(f"{BASE_URL}/leagues") == {"a": [1, 2]}
    assert seen["url"] == f"{BASE_URL}/leagues"
    assert seen["agent"] == USER_AGENT
    assert "https://github.com/Rasslabsya4el/crafting-system" in USER_AGENT
    assert seen["timeout"] is not None


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.HTTPError("https://poe.ninja/x", 404, "Not Found", {}, None),
        urllib.error.URLError("no route"),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        http.client.IncompleteRead(b"partial"),
        http.client.RemoteDisconnected("closed"),
    ],
)
def test_the_real_transport_turns_http_and_network_errors_into_source_errors(monkeypatch, failure):
    def fake_urlopen(request, timeout=None):
        raise failure

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(SourceError, match="poe.ninja"):
        http_get_json("https://poe.ninja/x")


@pytest.mark.parametrize("body", [b"<html>", b"", b"\xff\xfe"])
def test_the_real_transport_turns_invalid_json_into_a_source_error(monkeypatch, body):
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout=None: FakeResponse(body))

    with pytest.raises(SourceError, match="JSON"):
        http_get_json("https://poe.ninja/x")


# --- the fetcher does not touch the overrides ----------------------------------------------


def test_fetching_and_writing_leave_the_overrides_file_alone(ninja, tmp_path):
    config = Config(data_dir=tmp_path, cache_dir=tmp_path, output_dir=tmp_path)
    overrides = default_overrides_path(config)
    overrides.write_text('[prices]\n"Fracturing Orb" = 250\n', encoding="utf-8")
    before = overrides.read_bytes()

    write_price_file(tmp_path / "prices.json", fetch_price_file(ninja, NOW).price_file)

    assert overrides.read_bytes() == before
