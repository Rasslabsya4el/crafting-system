"""Pricing a buy spec from trade listings: stats cache, query cache, extraction to Chaos, the median (#39).

Every test runs on the recorded responses (or copies of the recorded rows) through a fake transport.
"""

import json
import statistics
from dataclasses import replace
from datetime import date, timedelta

import pytest

from crafting_system.prices import (
    NotEnoughListings,
    PriceEntry,
    TradePrice,
    load_buy_spec,
    load_price_file,
    merge_trade_prices,
    price_buy_spec,
    write_price_file,
)
from crafting_system.prices.trade_http import BudgetExceeded
from crafting_system.prices.trade_pricing import (
    DEFAULT_K,
    QUERY_TTL,
    STATS_TTL,
    TRADE_SOURCE,
    entry_for,
    store_trade_price,
)
from crafting_system.prices.trade_query import BuyMod, query_hash
from repoe_support import fixture_game_data
from trade_support import NOW, R12_SPEC, FakeTrade, api_row, make_client, network_guard, price_file  # noqa: F401


@pytest.fixture
def trade():
    return FakeTrade()


@pytest.fixture(scope="module")
def game_mods():
    return tuple(fixture_game_data().mods.values())


@pytest.fixture(scope="module")
def spec():
    return load_buy_spec(R12_SPEC)


def price(trade, spec, game_mods, tmp_path, *, now=NOW, file=None, budget=4, **options):
    return price_buy_spec(
        spec, game_mods, file or price_file(), make_client(trade, budget), tmp_path / "cache", now, **options
    )


def with_rows(trade, *rows):
    trade.rows = list(rows)
    trade.search["result"] = [f"id{n}" for n in range(len(rows))]


# -- the R12 case on recorded responses ----------------------------------------------------------


def test_r12_is_priced_from_the_recorded_listings(trade, spec, game_mods, tmp_path):
    found = price(trade, spec, game_mods, tmp_path)

    assert (found.name, found.chaos, found.league, found.date) == (
        "R12 start amulet",
        1.0,
        "Allflame",
        date(2026, 10, 30),
    )
    assert (found.listings, found.used, found.k, found.fetched, found.dropped) == (910, 5, 5, 10, {})
    assert found.query["query"]["stats"][0]["filters"][0]["id"] == "fractured.stat_1671376347"
    assert found.query_hash == query_hash("Allflame", found.query)


def test_one_run_sends_stats_search_and_fetch_of_the_first_ten_ids(trade, spec, game_mods, tmp_path):
    price(trade, spec, game_mods, tmp_path)

    assert trade.kinds == ["stats", "search", "fetch"]
    fetch_url = trade.requests[2].url
    first_ten = ",".join(trade.search["result"][:10])
    assert first_ten in fetch_url and trade.search["result"][10] not in fetch_url
    assert fetch_url.endswith("?query=" + trade.search["id"])


def test_the_query_cache_answers_a_second_run_with_no_request(trade, spec, game_mods, tmp_path):
    first = price(trade, spec, game_mods, tmp_path)
    trade.requests.clear()

    again = price(trade, spec, game_mods, tmp_path, budget=1)

    assert trade.requests == []
    assert again == first


def test_an_expired_query_cache_asks_again_but_not_for_the_stats(trade, spec, game_mods, tmp_path):
    price(trade, spec, game_mods, tmp_path)
    trade.requests.clear()

    price(trade, spec, game_mods, tmp_path, now=NOW + QUERY_TTL + timedelta(minutes=1))

    assert trade.kinds == ["search", "fetch"]


def test_a_query_cache_younger_than_the_ttl_is_still_used(trade, spec, game_mods, tmp_path):
    price(trade, spec, game_mods, tmp_path)
    trade.requests.clear()

    price(trade, spec, game_mods, tmp_path, now=NOW + QUERY_TTL - timedelta(minutes=1))

    assert trade.requests == []


def test_refresh_stats_asks_for_the_stats_list_again(trade, spec, game_mods, tmp_path):
    price(trade, spec, game_mods, tmp_path)
    trade.requests.clear()

    price(trade, spec, game_mods, tmp_path, refresh_stats=True)

    assert trade.kinds == ["stats"]


def test_an_old_stats_list_is_asked_for_again(trade, spec, game_mods, tmp_path):
    price(trade, spec, game_mods, tmp_path)
    trade.requests.clear()

    price(trade, spec, game_mods, tmp_path, now=NOW + STATS_TTL + timedelta(hours=1))

    assert trade.kinds[0] == "stats"


def test_a_budget_of_two_stops_before_the_fetch(trade, spec, game_mods, tmp_path):
    with pytest.raises(BudgetExceeded):
        price(trade, spec, game_mods, tmp_path, budget=2)

    assert trade.kinds == ["stats", "search"]
    assert [p.name for p in (tmp_path / "cache" / "trade").iterdir()] == ["stats.json"]


def test_the_query_cache_keeps_only_what_pricing_needs(trade, spec, game_mods, tmp_path):
    found = price(trade, spec, game_mods, tmp_path)

    cached = json.loads((tmp_path / "cache" / "trade" / f"{found.query_hash}.json").read_text(encoding="utf-8"))
    assert cached["total"] == 910 and "fetched_at" in cached
    assert len(cached["rows"]) == 10
    assert set(cached["rows"][0]) == {"price", "indexed", "fractured", "influences"}
    assert "Glyph Noose" not in json.dumps(cached)


def test_a_broken_cache_file_is_ignored_and_the_site_asked(trade, spec, game_mods, tmp_path):
    found = price(trade, spec, game_mods, tmp_path)
    (tmp_path / "cache" / "trade" / f"{found.query_hash}.json").write_text("{not json", encoding="utf-8")
    trade.requests.clear()

    assert price(trade, spec, game_mods, tmp_path) == found
    assert trade.kinds == ["search", "fetch"]


# -- extraction to Chaos and the median ----------------------------------------------------------


def test_divine_and_exalted_prices_convert_with_the_price_file_rates(trade, spec, game_mods, tmp_path):
    with_rows(trade, api_row(10), api_row(1, "divine"), api_row(5, "exalted"), api_row(0.5, "divine"))

    found = price(trade, spec, game_mods, tmp_path, k=4)

    assert found.used == 4 and found.chaos == statistics.median([10, 400, 100, 200])


@pytest.mark.parametrize(
    ("bad_row", "reason"),
    [
        (api_row(priced=False), "no price"),
        (api_row(5, "coin-of-doom"), "unknown currency"),
        (api_row(5, "annul"), "currency not in the price file"),
        (api_row(5, influences={"shaper": True}), "wrong influence"),
        (api_row(5, fractured=False), "not fractured"),
    ],
)
def test_a_listing_that_cannot_be_used_is_dropped_and_counted(trade, spec, game_mods, tmp_path, bad_row, reason):
    with_rows(trade, api_row(1), api_row(2), api_row(3), api_row(4), bad_row)

    found = price(trade, spec, game_mods, tmp_path)

    assert found.dropped == {reason: 1}
    assert (found.used, found.fetched, found.chaos) == (4, 5, 2.5)


def test_the_median_of_the_k_cheapest_ignores_the_dearer_listings(trade, spec, game_mods, tmp_path):
    with_rows(trade, *(api_row(n) for n in (90, 1, 80, 2, 70, 3)))

    found = price(trade, spec, game_mods, tmp_path, k=3)

    assert (found.used, found.k, found.chaos) == (3, 3, 2.0)


def test_with_fewer_listings_than_k_the_median_takes_all_of_them(trade, spec, game_mods, tmp_path):
    with_rows(trade, api_row(7), api_row(1), api_row(2))

    found = price(trade, spec, game_mods, tmp_path)

    assert (found.used, found.k, found.chaos) == (3, DEFAULT_K, 2.0)


def test_an_even_count_takes_the_mean_of_the_two_middle_ones(trade, spec, game_mods, tmp_path):
    with_rows(trade, api_row(1), api_row(2), api_row(3), api_row(10))

    assert price(trade, spec, game_mods, tmp_path).chaos == 2.5


def test_k_below_one_is_refused(trade, spec, game_mods, tmp_path):
    with pytest.raises(ValueError, match="k"):
        price(trade, spec, game_mods, tmp_path, k=0)


def test_influence_must_equal_the_spec(trade, spec, game_mods, tmp_path):
    influenced = replace(spec, influences=("shaper",))
    with_rows(
        trade,
        api_row(1, influences={"shaper": True}),
        api_row(2, influences={"shaper": True}),
        api_row(3, influences={"shaper": True}),
        api_row(4),
        api_row(5, influences={"shaper": True, "elder": True}),
    )

    found = price(trade, influenced, game_mods, tmp_path)

    assert (found.used, found.dropped) == (3, {"wrong influence": 2})


def test_a_spec_without_a_fractured_mod_does_not_need_fractured_listings(trade, spec, game_mods, tmp_path):
    plain = replace(spec, mods=(BuyMod("+#% to Lightning Resistance"),))
    with_rows(trade, api_row(1, fractured=False), api_row(2), api_row(3, fractured=False))

    found = price(trade, plain, game_mods, tmp_path)

    assert (found.used, found.dropped) == (3, {})


# -- not enough listings -------------------------------------------------------------------------


def test_two_usable_listings_are_not_enough_and_the_message_says_why(trade, spec, game_mods, tmp_path):
    with_rows(trade, api_row(1), api_row(2), api_row(priced=False), api_row(5, "coin-of-doom"))

    with pytest.raises(NotEnoughListings) as error:
        price(trade, spec, game_mods, tmp_path)

    message = str(error.value)
    assert "2" in message and "no price" in message and "unknown currency" in message


def test_a_search_with_no_listings_is_not_enough_and_fetches_nothing(trade, spec, game_mods, tmp_path):
    trade.search.update(total=0, result=[])

    with pytest.raises(NotEnoughListings):
        price(trade, spec, game_mods, tmp_path)

    assert trade.kinds == ["stats", "search"]


# -- the entry and the price file ----------------------------------------------------------------


def test_the_entry_carries_source_note_and_the_query(trade, spec, game_mods, tmp_path):
    found = price(trade, spec, game_mods, tmp_path)

    entry = entry_for(found)

    assert (entry.chaos, entry.source) == (1.0, TRADE_SOURCE) and TRADE_SOURCE == "trade-api"
    assert entry.note == "median of the 5 cheapest of 10 fetched listings, 910 on the site"
    assert entry.detail == {
        "league": "Allflame",
        "date": "2026-10-30",
        "listings": 910,
        "used": 5,
        "k": 5,
        "query_hash": found.query_hash,
        "query": found.query,
    }


def made(name="Amulet", chaos=2.0) -> TradePrice:
    return TradePrice(name, chaos, "Allflame", date(2026, 10, 30), 910, 5, 5, 10, {}, "h" * 64, {"query": {}})


def test_storing_adds_the_entry_and_keeps_everything_else(tmp_path):
    path = tmp_path / "prices.json"
    before = price_file()
    write_price_file(path, before)

    store_trade_price(path, made(), entry_for(made()))

    saved = load_price_file(path)
    assert saved.prices["Amulet"].source == TRADE_SOURCE
    assert (saved.fetched_at, saved.league, saved.chaos_per_divine) == (before.fetched_at, "Allflame", 400.0)
    assert {k: v for k, v in saved.prices.items() if k != "Amulet"} == before.prices


def test_storing_over_an_older_trade_price_replaces_it(tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, price_file())
    store_trade_price(path, made(chaos=2.0), entry_for(made(chaos=2.0)))

    store_trade_price(path, made(chaos=3.0), entry_for(made(chaos=3.0)))

    assert load_price_file(path).prices["Amulet"].chaos == 3.0


def test_a_name_that_is_another_source_price_is_refused_and_the_file_kept(tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, price_file())
    before = path.read_bytes()

    with pytest.raises(ValueError, match="collides with a poe.ninja price"):
        store_trade_price(path, made("Hollow Fossil"), entry_for(made("Hollow Fossil")))

    assert path.read_bytes() == before


# -- merging trade prices into a fresh fetch -----------------------------------------------------


def with_trade(file, name="Amulet"):
    prices = {**file.prices, name: PriceEntry(2.0, TRADE_SOURCE, "n", {"league": file.league})}
    return replace(file, prices=prices)


def test_merge_keeps_trade_prices_of_the_same_league():
    new, old = price_file(), with_trade(price_file(chaos_per_divine=300.0))

    merged, warnings = merge_trade_prices(new, old)

    assert merged.prices["Amulet"] == old.prices["Amulet"] and warnings == []
    assert merged.chaos_per_divine == 400.0 and "Amulet" not in new.prices


def test_merge_drops_trade_prices_of_another_league_with_a_warning():
    new, old = price_file(league="Standard"), with_trade(price_file())

    merged, warnings = merge_trade_prices(new, old)

    assert "Amulet" not in merged.prices
    assert len(warnings) == 1 and "Amulet" in warnings[0] and "Allflame" in warnings[0]


def test_merge_drops_a_trade_price_whose_own_league_differs_even_in_a_same_league_file():
    other = PriceEntry(3.0, TRADE_SOURCE, "n", {"league": "Standard"})
    same = PriceEntry(2.0, TRADE_SOURCE, "n", {"league": "Allflame"})
    bare = PriceEntry(4.0, TRADE_SOURCE, "n", None)
    old = price_file()
    old = replace(old, prices={**old.prices, "Mixed": other, "Same": same, "Bare": bare})

    merged, warnings = merge_trade_prices(price_file(), old)

    assert "Mixed" not in merged.prices
    assert merged.prices["Same"] == same and merged.prices["Bare"] == bare
    assert len(warnings) == 1 and "Mixed" in warnings[0] and "Standard" in warnings[0]
    assert "Same" not in warnings[0]


def test_merge_never_overwrites_a_name_the_fresh_file_already_has():
    new, old = price_file(), with_trade(price_file(), "Hollow Fossil")

    merged, _ = merge_trade_prices(new, old)

    assert merged.prices["Hollow Fossil"].source == "poe.ninja"


def test_merge_without_an_old_file_changes_nothing():
    new = price_file()

    assert merge_trade_prices(new, None) == (new, [])
