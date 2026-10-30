"""The listing-age window (`indexed`) of the trade query: model, recorded end to end, command line (#40).

Why it exists: a months-old listing can set a floor price. The recordings show it: the R12 query without
the window found 910 listings, the cheapest from August; with `1week` the site found 17.
"""

import json
from datetime import datetime, timedelta

import pytest

from crafting_system.prices import load_buy_spec, load_price_file, price_buy_spec, write_price_file
from crafting_system.prices.__main__ import main
from crafting_system.prices.trade_pricing import entry_for
from crafting_system.prices.trade_query import (
    DEFAULT_INDEXED,
    INDEXED_OPTIONS,
    TradeQuery,
    TradeSpecError,
    build_query,
    query_hash,
)
from repoe_support import fixture_game_data
from trade_support import NOW, R12_SPEC, FakeTrade, make_client, price_file, recorded

BODY = {"filters": {"indexed": {"option": "1week"}}}


@pytest.fixture(scope="module")
def game_mods():
    return tuple(fixture_game_data().mods.values())


@pytest.fixture(scope="module")
def spec():
    return load_buy_spec(R12_SPEC)


@pytest.fixture
def trade():
    """A fake that answers with the recordings made with the `1week` window."""
    fake = FakeTrade()
    fake.search = recorded("search_r12_1week.json")
    fake.rows = recorded("fetch_r12_1week.json")["result"]
    fake.headers = {
        "stats": fake.headers["stats"],
        "search": recorded("headers_search_1week.json")["headers"],
        "fetch": recorded("headers_fetch_1week.json")["headers"],
    }
    return fake


def search_body(trade):
    request = next(r for r, kind in zip(trade.requests, trade.kinds) if kind == "search")
    return json.loads(request.body)


# -- the query model -------------------------------------------------------------------------------


def test_the_default_window_is_one_week():
    assert DEFAULT_INDEXED == "1week"
    assert DEFAULT_INDEXED in INDEXED_OPTIONS


def test_a_window_is_written_as_the_trade_filters_indexed_option():
    body = TradeQuery(type="Amulet", indexed="1week").body()

    assert body["query"]["filters"]["trade_filters"] == BODY


def test_no_window_writes_no_trade_filters_group():
    assert "filters" not in TradeQuery(type="Amulet").body()["query"]
    body = TradeQuery(type="Amulet", rarity="rare", indexed=None).body()
    assert "trade_filters" not in body["query"]["filters"]


@pytest.mark.parametrize("option", INDEXED_OPTIONS)
def test_every_known_window_builds(option):
    body = TradeQuery(type="Amulet", indexed=option).body()

    assert body["query"]["filters"]["trade_filters"]["filters"]["indexed"] == {"option": option}


def test_an_unknown_window_is_refused_and_the_options_are_listed():
    with pytest.raises(TradeSpecError) as error:
        TradeQuery(type="Amulet", indexed="2days")

    for option in INDEXED_OPTIONS:
        assert option in str(error.value)
    assert "2days" in str(error.value)


def test_build_query_gives_the_default_window_unless_told_otherwise(spec):
    assert build_query(spec, []).indexed == DEFAULT_INDEXED
    assert build_query(spec, [], indexed="3days").indexed == "3days"
    assert build_query(spec, [], indexed=None).indexed is None


def test_the_hash_tells_two_windows_apart_and_equal_windows_together():
    def digest(window):
        return query_hash("Allflame", TradeQuery(type="Amulet", indexed=window).body())

    assert digest("1week") == digest("1week")
    assert len({digest("1week"), digest("2weeks"), digest(None)}) == 3


# -- the recording ---------------------------------------------------------------------------------


def test_the_options_in_the_code_are_the_options_the_site_accepts():
    listed = recorded("filters_indexed.json")["filter"]["option"]["options"]

    assert INDEXED_OPTIONS == tuple(item["id"] for item in listed if item["id"] is not None)


# -- recorded end to end ---------------------------------------------------------------------------


def run(trade, spec, game_mods, tmp_path, **options):
    return price_buy_spec(
        spec, game_mods, price_file(), make_client(trade), tmp_path / "cache", NOW, **options
    )


def test_the_search_body_is_the_one_recorded_with_the_window(trade, spec, game_mods, tmp_path):
    found = run(trade, spec, game_mods, tmp_path)

    assert search_body(trade) == recorded("search_body_r12_1week.json")
    assert found.query == recorded("search_body_r12_1week.json")


def test_the_price_is_the_median_of_the_five_cheapest_recent_listings(trade, spec, game_mods, tmp_path):
    found = run(trade, spec, game_mods, tmp_path)

    assert (found.chaos, found.listings, found.used, found.fetched) == (4.0, 17, 5, 10)


def test_the_stored_query_carries_the_window(trade, spec, game_mods, tmp_path):
    found = run(trade, spec, game_mods, tmp_path)

    entry = entry_for(found)
    assert entry.detail["query"]["query"]["filters"]["trade_filters"] == BODY
    assert entry.detail["query_hash"] == query_hash("Allflame", recorded("search_body_r12_1week.json"))
    assert "listed within 1week" in entry.note
    assert entry.note.startswith("median of the 5 cheapest of 10 fetched listings, 17 on the site")


def test_every_recorded_listing_is_within_a_week_of_the_run(trade):
    ages = [
        NOW - datetime.fromisoformat(row["listing"]["indexed"].replace("Z", "+00:00"))
        for row in trade.rows
    ]

    assert all(timedelta(0) <= age <= timedelta(days=7) for age in ages)


def test_without_a_window_the_body_has_no_trade_filters_and_the_note_says_any_time(
    trade, spec, game_mods, tmp_path
):
    found = run(trade, spec, game_mods, tmp_path, indexed=None)

    assert "trade_filters" not in search_body(trade)["query"]["filters"]
    assert "trade_filters" not in found.query["query"]["filters"]
    assert "listed any time" in entry_for(found).note


def test_a_different_window_is_a_different_cache_entry(trade, spec, game_mods, tmp_path):
    week = run(trade, spec, game_mods, tmp_path)
    trade.requests.clear()

    two_weeks = run(trade, spec, game_mods, tmp_path, indexed="2weeks")

    assert week.query_hash != two_weeks.query_hash
    assert trade.kinds == ["search", "fetch"]


# -- command line ----------------------------------------------------------------------------------


@pytest.fixture
def prices_path(tmp_path):
    path = tmp_path / "data" / "prices.json"
    write_price_file(path, price_file())
    return path


@pytest.fixture(autouse=True)
def game_data(monkeypatch):
    monkeypatch.setattr("crafting_system.prices.__main__.load_game_data", lambda **kwargs: fixture_game_data())


def cli(tmp_path, trade, *argv):
    environment = {"CRAFTING_DATA_DIR": str(tmp_path / "data"), "CRAFTING_CACHE_DIR": str(tmp_path / "cache")}
    return main(
        ["trade", "--spec", str(R12_SPEC), *argv],
        transport=trade,
        sleep=lambda seconds: None,
        monotonic=lambda: 0.0,
        now=NOW,
        env=environment,
    )


def test_the_command_line_default_is_one_week(tmp_path, trade, prices_path, capsys):
    assert cli(tmp_path, trade) == 0

    assert search_body(trade)["query"]["filters"]["trade_filters"] == BODY
    assert "listings from the last 1week" in capsys.readouterr().out


def test_indexed_two_weeks_reaches_the_search_body(tmp_path, trade, prices_path, capsys):
    assert cli(tmp_path, trade, "--indexed", "2weeks") == 0

    filters = search_body(trade)["query"]["filters"]["trade_filters"]["filters"]
    assert filters == {"indexed": {"option": "2weeks"}}
    assert "listings from the last 2weeks" in capsys.readouterr().out


def test_indexed_any_sends_no_window(tmp_path, trade, prices_path, capsys):
    assert cli(tmp_path, trade, "--indexed", "any") == 0

    assert "trade_filters" not in search_body(trade)["query"]["filters"]
    assert "listings from any time" in capsys.readouterr().out


def test_an_invalid_window_exits_with_code_2_and_sends_nothing(tmp_path, trade, prices_path, capsys):
    with pytest.raises(SystemExit) as stop:
        cli(tmp_path, trade, "--indexed", "yesterday")

    assert stop.value.code == 2
    assert trade.requests == []
    assert "1week" in capsys.readouterr().err


def test_the_price_file_entry_carries_the_window(tmp_path, trade, prices_path):
    cli(tmp_path, trade, "--indexed", "3days")

    entry = load_price_file(prices_path).prices["R12 start amulet"]
    assert entry.detail["query"]["query"]["filters"]["trade_filters"] == {
        "filters": {"indexed": {"option": "3days"}}
    }
    assert "listed within 3days" in entry.note
