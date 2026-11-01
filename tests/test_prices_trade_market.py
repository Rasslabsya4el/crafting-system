"""The market rule of a trade price, the recorded `thin` / `none` states and the 7-day offer window (#355).

Every test runs on the recorded trade answers of `fixtures/trade/recorded/` (or copies of them) through the
fake transport; nothing touches the network.
"""

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from crafting_system.prices import (
    DEFAULT_MIN_LISTINGS,
    TRADE_SOURCE,
    MarketRecord,
    NotEnoughListings,
    PriceEntry,
    assess_buy_spec,
    load_buy_spec,
    load_price_file,
    market_of_listings,
    merge_trade_prices,
    offer,
    price_buy_spec,
    store_market,
    write_price_file,
)
from crafting_system.prices.trade_market import MIN_USABLE, classify
from crafting_system.prices.trade_pricing import _row, entry_for
from crafting_system.prices.trade_query import query_hash
from repoe_support import fixture_game_data
from trade_support import NOW, R12_SPEC, FakeTrade, api_row, make_client, price_file

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROUTE_PRICES = FIXTURES / "prices" / "routes-allflame-2026-10-31.json"
RECORDED = FIXTURES / "trade" / "recorded" / "start_items"
BUY_SPECS = Path(__file__).resolve().parents[1] / "examples" / "buy"
STARTS = {
    "r10": ("r10-start-boots.yaml", "R10 start boots"),
    "r11": ("r11-start-helmet.yaml", "R11 start helmet"),
    "r05": ("r05-start-ring.yaml", "R05 start ring"),
    "r12": ("r12-start-amulet.yaml", "R12 start amulet"),
}
TODAY = NOW.date()


@pytest.fixture
def trade():
    return FakeTrade()


@pytest.fixture(scope="module")
def game_mods():
    return tuple(fixture_game_data().mods.values())


@pytest.fixture(scope="module")
def spec():
    return load_buy_spec(R12_SPEC)


def assess(trade, spec, game_mods, tmp_path, **options):
    return assess_buy_spec(
        spec, game_mods, price_file(), make_client(trade), tmp_path / "cache", NOW, **options
    )


def with_listings(trade, count, rows=None):
    """The search says `count` listings; the fetch gives `rows` (default: the recorded ones)."""
    trade.search.update(total=count, result=[f"id{n}" for n in range(min(count, 100))])
    if rows is not None:
        trade.rows = list(rows)


# -- the rule: replaying the recorded answers ------------------------------------------------------


@pytest.mark.parametrize("tag", STARTS)
def test_the_recorded_start_items_give_the_stored_prices_and_are_quoted(tag):
    spec_file, name = STARTS[tag]
    stored = load_price_file(ROUTE_PRICES)
    spec = load_buy_spec(BUY_SPECS / spec_file)
    search = json.loads((RECORDED / f"search_{tag}.json").read_text(encoding="utf-8"))
    body = json.loads((RECORDED / f"search_body_{tag}.json").read_text(encoding="utf-8"))
    fetched = json.loads((RECORDED / f"fetch_{tag}.json").read_text(encoding="utf-8"))["result"]

    market = market_of_listings(
        spec, stored, search["total"], [_row(item) for item in fetched], NOW,
        query_hash(stored.league, body), body,
    )

    assert market.state == "quoted" and market.reason is None
    assert market.price is not None and market.price.chaos == pytest.approx(stored.prices[name].chaos)
    assert (market.listings, market.price.used) == (
        stored.prices[name].detail["listings"],
        stored.prices[name].detail["used"],
    )


def test_r12_through_the_client_is_quoted_with_total_usable_count_and_date(trade, spec, game_mods, tmp_path):
    market = assess(trade, spec, game_mods, tmp_path)

    assert market.state == "quoted" and market.price is not None
    assert (market.price.chaos, market.listings, market.usable) == (1.0, 910, 10)
    entry = entry_for(market.price)
    assert (entry.detail["listings"], entry.detail["used"], entry.detail["date"]) == (910, 5, "2026-10-30")
    again = price_buy_spec(spec, game_mods, price_file(), make_client(FakeTrade()), tmp_path / "other", NOW)
    assert again.chaos == 1.0


def test_a_nine_listing_answer_is_thin_and_makes_no_price(trade, spec, game_mods, tmp_path):
    with_listings(trade, 9, trade.rows[:9])

    market = assess(trade, spec, game_mods, tmp_path)

    assert (market.state, market.price, market.listings, market.usable) == ("thin", None, 9, 9)
    assert "only 9 listings" in market.reason and "at least 10" in market.reason
    with pytest.raises(NotEnoughListings, match="only 9 listings") as error:
        price_buy_spec(spec, game_mods, price_file(), make_client(trade), tmp_path / "other", NOW)
    assert error.value.market.state == "thin"


def test_ten_listings_are_the_smallest_market(trade, spec, game_mods, tmp_path):
    with_listings(trade, 10)

    market = assess(trade, spec, game_mods, tmp_path)

    assert (market.state, market.listings) == ("quoted", 10)
    assert market.price.used == 5  # the mean of the 5 cheapest of the usable ones


def test_a_search_with_no_listing_is_none_and_fetches_nothing(trade, spec, game_mods, tmp_path):
    trade.search.update(total=0, result=[])

    market = assess(trade, spec, game_mods, tmp_path)

    assert (market.state, market.listings, market.usable, market.price) == ("none", 0, 0, None)
    assert trade.kinds == ["stats", "search"]


def test_enough_listings_on_the_site_but_too_few_usable_is_thin(trade, spec, game_mods, tmp_path):
    with_listings(trade, 300, [api_row(1), api_row(2), api_row(priced=False)])

    market = assess(trade, spec, game_mods, tmp_path)

    assert (market.state, market.listings, market.usable) == ("thin", 300, 2)
    assert "only 2 of 3" in market.reason and f"at least {MIN_USABLE}" in market.reason


def test_the_listing_count_rail_is_a_parameter(trade, spec, game_mods, tmp_path):
    with_listings(trade, 15)

    strict = assess(trade, spec, game_mods, tmp_path, min_listings=20)
    loose = assess(trade, spec, game_mods, tmp_path, min_listings=5)

    assert strict.state == "thin" and "at least 20" in strict.reason
    assert loose.state == "quoted"


def test_the_mean_is_of_the_five_cheapest_usable_listings(trade, spec, game_mods, tmp_path):
    with_listings(trade, 50, [api_row(n) for n in (9, 1, 8, 2, 7, 3, 6, 4)])

    market = assess(trade, spec, game_mods, tmp_path)

    assert market.price.chaos == pytest.approx((1 + 2 + 3 + 4 + 6) / 5)


def test_classify_is_none_thin_or_quoted():
    assert classify(0, 0) == "none"
    assert classify(9, 9) == "thin"
    assert classify(10, 2) == "thin"
    assert classify(10, 3) == "quoted"
    assert classify(5, 5, min_listings=5) == "quoted"
    assert DEFAULT_MIN_LISTINGS == 10


# -- recording the states in the price file ----------------------------------------------------


def thin_market(spec, trade, game_mods, tmp_path, count=9):
    with_listings(trade, count, trade.rows[:count])
    return assess(trade, spec, game_mods, tmp_path)


def test_thin_and_none_are_recorded_and_read_back(trade, spec, game_mods, tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, price_file())
    market = thin_market(spec, trade, game_mods, tmp_path)

    store_market(path, market)

    saved = load_price_file(path)
    assert saved.markets[spec.name] == MarketRecord(
        "thin", "Allflame", date(2026, 10, 30), 9, 9, market.query_hash, market.query
    )
    assert saved.prices == price_file().prices  # a record is not a price


def test_a_file_without_records_is_written_as_before(tmp_path):
    path = tmp_path / "prices.json"

    write_price_file(path, price_file())

    assert "markets" not in json.loads(path.read_text(encoding="utf-8"))


def test_a_thin_result_replaces_an_older_quote_and_a_quote_replaces_a_record(trade, spec, game_mods, tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, price_file())
    quoted = assess(trade, spec, game_mods, tmp_path)
    store_market(path, quoted)
    assert spec.name in load_price_file(path).prices

    store_market(path, thin_market(spec, FakeTrade(), game_mods, tmp_path / "t"))
    after_thin = load_price_file(path)
    assert spec.name not in after_thin.prices and after_thin.markets[spec.name].state == "thin"

    store_market(path, quoted)
    after_quote = load_price_file(path)
    assert spec.name in after_quote.prices and spec.name not in after_quote.markets


def test_a_record_over_another_sources_price_is_refused_and_the_file_kept(trade, spec, game_mods, tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, price_file())
    before = path.read_bytes()
    market = replace(thin_market(spec, trade, game_mods, tmp_path), name="Hollow Fossil")

    with pytest.raises(ValueError, match="collides with a poe.ninja price"):
        store_market(path, market)

    assert path.read_bytes() == before


def test_a_damaged_record_is_a_load_error(tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, price_file())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["markets"] = {"X": {"state": "quoted", "league": "Allflame", "date": "2026-10-30"}}
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="state must be one of"):
        load_price_file(path)


def test_records_survive_a_poe_ninja_refetch_in_the_same_league_only():
    record = MarketRecord("none", "Allflame", date(2026, 10, 30), 0, 0, "h", {"query": {}})
    old = replace(price_file(), markets={"Amulet": record})

    kept, warnings = merge_trade_prices(price_file(), old)
    dropped, league_warnings = merge_trade_prices(price_file(league="Standard"), old)

    assert kept.markets == {"Amulet": record} and warnings == []
    assert dropped.markets == {} and len(league_warnings) == 1 and "Amulet" in league_warnings[0]


# -- what is offered: fresh for 7 days --------------------------------------------------------


def stored_entry(listings=910, used=5, day="2026-10-30", **detail):
    return PriceEntry(
        2.0, TRADE_SOURCE, "n", {"league": "Allflame", "date": day, "listings": listings, "used": used, **detail}
    )


def file_with(entry=None, record=None):
    base = price_file()
    prices = {**base.prices, **({"Amulet": entry} if entry else {})}
    return replace(base, prices=prices, markets={"Amulet": record} if record else {})


@pytest.mark.parametrize("age,state", [(0, "quoted"), (7, "quoted"), (8, "stale"), (30, "stale")])
def test_an_entry_older_than_seven_days_is_not_offered(age, state):
    entry = stored_entry(day=(TODAY - timedelta(days=age)).isoformat())

    found = offer(file_with(entry), "Amulet", TODAY)

    assert found.state == state and found.offered == (state == "quoted")
    assert found.age_days == age
    assert found.fresh == (state == "quoted")
    if state == "stale":
        assert f"{age} days old (limit 7)" in found.reason


def test_a_quoted_entry_below_the_rail_or_with_few_usable_is_not_offered_and_says_which():
    nine = offer(file_with(stored_entry(listings=9, used=5)), "Amulet", TODAY)
    few = offer(file_with(stored_entry(listings=40, used=2)), "Amulet", TODAY)
    raised = offer(file_with(stored_entry(listings=15)), "Amulet", TODAY, min_listings=20)

    assert (nine.state, nine.offered, nine.listings) == ("thin", False, 9)
    assert "rail needs 10" in nine.reason
    assert (few.state, few.offered) == ("thin", False) and "2 usable" in few.reason
    assert (raised.state, raised.offered) == ("thin", False) and "rail needs 20" in raised.reason
    assert nine.fresh  # a thin answer of today is a fresh answer: no need to ask again


def test_a_recorded_thin_or_none_state_is_not_offered_but_is_fresh():
    thin = MarketRecord("thin", "Allflame", TODAY - timedelta(days=2), 9, 9, "h", {"query": {}})
    none = MarketRecord("none", "Allflame", TODAY, 0, 0, "h", {"query": {}})

    got_thin = offer(file_with(record=thin), "Amulet", TODAY)
    got_none = offer(file_with(record=none), "Amulet", TODAY)

    assert (got_thin.state, got_thin.offered, got_thin.fresh, got_thin.listings) == ("thin", False, True, 9)
    assert (got_none.state, got_none.offered, got_none.fresh) == ("none", False, True)
    assert "total 0" in got_none.reason


def test_a_recorded_state_goes_stale_after_seven_days_too():
    old = MarketRecord("none", "Allflame", TODAY - timedelta(days=8), 0, 0, "h", {"query": {}})

    got = offer(file_with(record=old), "Amulet", TODAY)

    assert (got.state, got.offered, got.fresh) == ("stale", False, False)


def test_the_usable_count_is_stored_apart_from_the_k_cheapest_used(trade, spec, game_mods, tmp_path):
    with_listings(trade, 300, [api_row(n) for n in range(1, 9)])

    market = assess(trade, spec, game_mods, tmp_path, k=2)
    entry = entry_for(market.price)

    assert (entry.detail["used"], entry.detail["usable"]) == (2, 8)
    assert offer(file_with(replace(entry, detail={**entry.detail, "date": TODAY.isoformat()})), "Amulet", TODAY).offered


def test_an_entry_without_counts_or_dated_in_the_future_is_not_offered():
    no_counts = PriceEntry(2.0, TRADE_SOURCE, "n", {"league": "Allflame", "date": TODAY.isoformat()})
    future = stored_entry(day=(TODAY + timedelta(days=2)).isoformat())
    future_record = MarketRecord("none", "Allflame", TODAY + timedelta(days=2), 0, 0, "h", {"query": {}})

    assert offer(file_with(no_counts), "Amulet", TODAY).state == "unknown"
    assert offer(file_with(future), "Amulet", TODAY).state == "stale"
    assert offer(file_with(record=future_record), "Amulet", TODAY).state == "stale"


def test_a_name_with_nothing_recorded_is_unknown():
    got = offer(price_file(), "Amulet", TODAY)

    assert (got.state, got.offered, got.fresh) == ("unknown", False, False)


def test_an_entry_without_a_date_or_of_another_league_is_not_offered():
    undated = PriceEntry(2.0, TRADE_SOURCE, "n", {"league": "Allflame", "listings": 910, "used": 5})
    other = stored_entry(league="Standard")

    assert offer(file_with(undated), "Amulet", TODAY).state == "stale"
    assert offer(file_with(other), "Amulet", TODAY).state == "unknown"


def test_the_recorded_route_prices_are_offered_while_fresh_and_not_after_a_week():
    stored = load_price_file(ROUTE_PRICES)  # every start item was priced on 2026-10-31

    fresh = [offer(stored, name, date(2026, 11, 7)) for _, name in STARTS.values()]
    late = [offer(stored, name, date(2026, 11, 8)) for _, name in STARTS.values()]

    assert all(found.offered for found in fresh)
    assert not any(found.offered for found in late)
    assert {found.state for found in late} == {"stale"}
