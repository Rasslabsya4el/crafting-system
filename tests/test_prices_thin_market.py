"""A thin market's price: the league's last deep price marked old, else the mean of what is there marked thin (#718, OR-8).

Every market here is made by hand from listings whose prices are worked out in the test: no network, no snapshot, no
recorded answer and no price of today. A market goes in the price file through the writer (`store_market`) and is read
back through `source_price`, so the writer, the file and the rule are tested together.
"""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from test_start_price_report import candidate, choice_of
from trade_support import R12_SPEC, api_row
from trade_support import price_file as allflame_prices

from crafting_system.cli._start_report import start_document, start_lines
from crafting_system.prices import (
    PriceEntry,
    load_buy_spec,
    load_price_file,
    market_of_listings,
    merge_trade_prices,
    offer,
    store_market,
    write_price_file,
)
from crafting_system.prices.price_file import DeepReading
from crafting_system.prices.price_source import source_price
from crafting_system.prices.trade_pricing import _row

SPEC = load_buy_spec(R12_SPEC)
NAME = SPEC.name
LEAGUE = "Allflame"
MID_LEAGUE = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
LEAGUE_END = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
TROLLS = [136000, 134000, 138000, 135000, 137000]  # 5 listings: the end of the Allflame league, 2026-11-08

OLD_MARK = "old price, read on 2026-11-01, the market has few offers now"
THIN_MARK = "few offers: the mean of the 5 listings there are"


def read(price_file, rows, total, now):
    """The market of one search: `total` listings on the site, `rows` priced in Chaos fetched."""
    return market_of_listings(SPEC, price_file, total, [_row(api_row(chaos)) for chaos in rows], now, "hash", {"query": {}})


def stored(tmp_path, *markets, ninja=None, **changes):
    """A price file with the markets written to it in order, read back; `ninja` is a poe.ninja row of the name."""
    path = tmp_path / "prices.json"
    prices = allflame_prices(**changes)
    if ninja is not None:  # beside the trade price, in the `ninja` table, as the refresher keeps it (#357)
        prices = replace(prices, ninja={NAME: PriceEntry(ninja, "poe.ninja")})
    write_price_file(path, prices)
    for market in markets:
        store_market(path, market)
    return load_price_file(path)


def deep_market(now=MID_LEAGUE):
    """40 listings on the site, 8 fetched: the cheapest five are 10, 12, 14, 16, 18, whose mean is 14."""
    return read(allflame_prices(), [30, 10, 50, 12, 14, 100, 16, 18], 40, now)


def thin_market(now=LEAGUE_END):
    """5 listings on the site, all troll asks; their mean is (134000 + 135000 + 136000 + 137000 + 138000) / 5 = 136000."""
    return read(allflame_prices(), TROLLS, 5, now)


# -- the four markets --------------------------------------------------------------------------------------------------


def test_1_a_thick_market_is_the_plain_mean_of_the_cheapest_five_and_unmarked(tmp_path):
    market = deep_market()
    assert (market.state, market.price.chaos) == ("quoted", 14.0)

    result = source_price(stored(tmp_path, market), NAME, "both", date(2026, 11, 1))

    assert (result.used, result.chaos, result.fallback, result.marks) == ("trade", 14.0, False, ())


def test_2_a_thin_market_after_a_deep_reading_this_league_is_that_old_price_marked_old_with_its_date(tmp_path):
    file = stored(tmp_path, deep_market(MID_LEAGUE), thin_market(LEAGUE_END))

    result = source_price(file, NAME, "both", date(2026, 11, 8))

    assert (result.used, result.chaos, result.fallback) == ("trade", 14.0, False)  # not the trolls' 136000
    assert result.marks == (OLD_MARK,)
    assert result.trade.state == "thin" and result.trade.basis == "old" and result.trade.read_on == date(2026, 11, 1)


def test_3_a_thin_market_with_no_deep_reading_this_league_is_the_mean_of_what_is_there_marked_thin(tmp_path):
    previous = DeepReading(14.0, "Settlers", date(2026, 7, 1), 40, 8)  # a reading of the previous league is no price of this one

    file = stored(tmp_path, thin_market(), deep={NAME: previous})
    result = source_price(file, NAME, "both", date(2026, 11, 8))

    assert (result.used, result.chaos, result.fallback) == ("trade", 136000.0, False)
    assert result.marks == (THIN_MARK,)
    assert result.trade.state == "thin" and result.trade.basis == "thin" and result.trade.mean_of == 5


def test_3_the_previous_leagues_reading_is_never_this_leagues_even_when_it_is_the_only_one_in_the_file():
    foreign = DeepReading(14.0, "Settlers", date(2026, 7, 1), 40, 8)
    file = allflame_prices(deep={NAME: foreign})
    thin = thin_market()
    record = replace(thin.record(), query_hash="h")

    got = offer(replace(file, markets={NAME: record}), NAME, date(2026, 11, 8))

    assert got.basis == "thin" and got.entry.chaos == 136000.0


def test_4_a_search_with_no_listings_at_all_stays_the_poe_ninja_stand_in_even_with_a_deep_reading(tmp_path):
    empty = read(allflame_prices(), [], 0, LEAGUE_END)
    assert empty.state == "none"

    for markets in ((empty,), (deep_market(), empty)):
        file = stored(tmp_path, *markets, ninja=7.0)
        result = source_price(file, NAME, "both", date(2026, 11, 8))

        assert (result.used, result.chaos, result.fallback) == ("poe.ninja", 7.0, True)
        assert result.trade.state == "none" and result.trade.basis is None
        assert result.marks[0].startswith("fallback: the trade price is not usable (none: ")
        assert OLD_MARK not in result.marks and THIN_MARK not in result.marks


# -- what a thin market with nothing to show does ------------------------------------------------------------------------------


def test_a_thin_market_with_no_priced_listing_and_no_deep_reading_is_still_the_marked_fallback(tmp_path):
    unpriced = market_of_listings(SPEC, allflame_prices(), 6, [_row(api_row(priced=False))], LEAGUE_END, "hash", {"query": {}})

    result = source_price(stored(tmp_path, unpriced, ninja=7.0), NAME, "both", date(2026, 11, 8))

    assert (result.used, result.fallback, result.chaos) == ("poe.ninja", True, 7.0)
    assert "thin" in result.marks[0]  # the reason is said, the record is not dropped silently


def test_a_thin_market_of_two_usable_listings_among_many_is_thin_too(tmp_path):
    two_of_many = read(allflame_prices(), [20, 30], 300, LEAGUE_END)  # the #355 rule: fewer than 3 usable

    result = source_price(stored(tmp_path, two_of_many), NAME, "both", date(2026, 11, 8))

    assert (result.chaos, result.marks) == (25.0, ("few offers: the mean of the 2 listings there are",))


def test_a_thin_market_uses_the_cheapest_k_of_the_listings_there_are(tmp_path):
    four = read(allflame_prices(), [8, 2, 4, 6], 4, LEAGUE_END)  # 4 listings: the mean of all 4 is 5

    result = source_price(stored(tmp_path, four), NAME, "both", date(2026, 11, 8))

    assert (result.chaos, result.marks) == (5.0, ("few offers: the mean of the 4 listings there are",))


def test_an_old_price_is_offered_however_old_while_the_thin_record_itself_is_fresh(tmp_path):
    file = stored(tmp_path, deep_market(datetime(2026, 9, 1, 12, 0, tzinfo=UTC)), thin_market(LEAGUE_END))

    result = source_price(file, NAME, "both", date(2026, 11, 8))

    assert result.chaos == 14.0 and result.marks == ("old price, read on 2026-09-01, the market has few offers now",)


def test_a_thin_record_older_than_seven_days_is_not_offered_the_refresher_asks_again(tmp_path):
    file = stored(tmp_path, deep_market(), thin_market(LEAGUE_END), ninja=7.0)

    result = source_price(file, NAME, "both", date(2026, 11, 16))  # 8 days after the thin search

    assert (result.used, result.fallback) == ("poe.ninja", True) and result.trade.state == "stale"


def test_the_trade_setting_prices_a_thin_market_with_its_mark_and_ninja_never_sees_it(tmp_path):
    file = stored(tmp_path, deep_market(), thin_market(), ninja=7.0)

    trade = source_price(file, NAME, "trade", date(2026, 11, 8))
    ninja = source_price(file, NAME, "ninja", date(2026, 11, 8))

    assert (trade.chaos, trade.marks) == (14.0, (OLD_MARK,))
    assert ninja.chaos == 7.0 and ninja.marks != trade.marks


# -- the writer: a deep reading is kept through a thin one -------------------------------------------------------------------------


def test_the_remembered_deep_price_is_kept_through_a_thin_reading_and_replaced_by_the_next_deep_one(tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, allflame_prices())

    store_market(path, deep_market(MID_LEAGUE))
    first = load_price_file(path)
    assert first.deep[NAME] == DeepReading(14.0, LEAGUE, date(2026, 11, 1), 40, 8)
    assert NAME in first.prices and NAME not in first.markets

    store_market(path, thin_market(LEAGUE_END))
    thin = load_price_file(path)
    assert thin.deep[NAME] == first.deep[NAME]  # kept, not overwritten by the thin 136000
    assert NAME not in thin.prices and thin.markets[NAME].state == "thin"
    assert (thin.markets[NAME].chaos, thin.markets[NAME].used) == (136000.0, 5)

    second = read(allflame_prices(), [20, 22, 24, 26, 28], 25, datetime(2026, 11, 9, 12, 0, tzinfo=UTC))  # mean 24
    store_market(path, second)
    after = load_price_file(path)
    assert after.deep[NAME] == DeepReading(24.0, LEAGUE, date(2026, 11, 9), 25, 5)
    assert after.prices[NAME].chaos == 24.0 and NAME not in after.markets


def test_a_thin_reading_keeps_the_deep_price_of_a_file_written_before_the_memory_existed(tmp_path):
    path = tmp_path / "prices.json"
    deep = deep_market(MID_LEAGUE)
    write_price_file(path, allflame_prices())
    store_market(path, deep)
    document = load_price_file(path)
    write_price_file(path, replace(document, deep={}))  # an older file: the quote is in `prices`, the memory is empty

    store_market(path, thin_market(LEAGUE_END))

    assert load_price_file(path).deep[NAME].chaos == 14.0


def test_a_deep_price_of_another_league_in_the_file_is_not_remembered_as_this_leagues(tmp_path):
    path = tmp_path / "prices.json"
    other = PriceEntry(14.0, "trade-api", "n", {"league": "Settlers", "date": "2026-07-01", "listings": 40, "used": 5, "usable": 8})
    write_price_file(path, allflame_prices(prices={**allflame_prices().prices, NAME: other}))

    store_market(path, thin_market(LEAGUE_END))

    assert NAME not in load_price_file(path).deep


def test_the_memory_and_a_thin_mean_survive_the_file_round_trip(tmp_path):
    file = stored(tmp_path, deep_market(), thin_market())

    assert file.deep[NAME].chaos == 14.0 and file.markets[NAME].chaos == 136000.0
    assert stored(tmp_path, read(allflame_prices(), [], 0, LEAGUE_END)).markets[NAME].chaos is None


def test_a_file_with_no_thin_trade_record_is_written_as_before(tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, allflame_prices())
    store_market(path, read(allflame_prices(), [], 0, LEAGUE_END))

    document = path.read_text(encoding="utf-8")

    assert '"deep"' not in document and '"chaos": null' not in document


@pytest.mark.parametrize("damage", [{"chaos": -1}, {"date": "soon"}, {"league": ""}, {"listings": -2}, {"usable": "x"}])
def test_a_damaged_deep_reading_is_a_load_error(tmp_path, damage):
    import json

    path = tmp_path / "prices.json"
    write_price_file(path, allflame_prices())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["deep"] = {NAME: {"chaos": 14.0, "league": LEAGUE, "date": "2026-11-01", "listings": 40, "usable": 8, **damage}}
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="deep"):
        load_price_file(path)


# -- the marks on the page and the report -------------------------------------------------------------------------------------------


def test_both_marks_reach_the_start_text_and_the_json_the_way_the_fallback_mark_does(tmp_path):
    old = source_price(stored(tmp_path, deep_market(), thin_market()), NAME, "both", date(2026, 11, 8))
    thin = source_price(stored(tmp_path, thin_market()), NAME, "both", date(2026, 11, 8))
    choice = choice_of(candidate("old", 14.0, old), candidate("thin", 136000.0, thin))

    lines = start_lines(choice)
    document = start_document(choice)

    assert f"        {OLD_MARK}" in lines and f"        {THIN_MARK}" in lines
    assert lines.index(f"        {OLD_MARK}") < lines.index(f"        {THIN_MARK}")
    old_price, thin_price = (option["price"] for option in document["options"])
    assert old_price["marks"] == [OLD_MARK] and old_price["chaos"] == 14.0 and old_price["fallback"] is False
    assert thin_price["marks"] == [THIN_MARK] and thin_price["chaos"] == 136000.0 and thin_price["fallback"] is False
    assert "      price source both: 14.00 Chaos [trade-api, old price of 2026-11-01]" in lines
    assert "      price source both: 136,000.00 Chaos [trade-api, thin: 5 listings]" in lines


# -- only a reading that meets the default rail is the league's deep reading ----------------------------------------------------------


def test_a_quote_made_under_a_lowered_rail_is_a_price_but_never_the_deep_reading(tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, allflame_prices())
    rows = [_row(api_row(n)) for n in (1, 2, 3, 4, 5, 6)]
    lowered = market_of_listings(SPEC, allflame_prices(), 6, rows, MID_LEAGUE, "hash", {"query": {}}, min_listings=5)
    assert lowered.state == "quoted"  # 6 listings meet a rail of 5, not the default 10

    store_market(path, lowered)
    assert NAME in load_price_file(path).prices and NAME not in load_price_file(path).deep

    store_market(path, deep_market(MID_LEAGUE))
    store_market(path, lowered)  # a later lowered-rail quote does not replace the deep reading either
    assert load_price_file(path).deep[NAME].chaos == 14.0


def test_a_legacy_quote_under_a_lowered_rail_is_not_promoted_to_the_deep_reading(tmp_path):
    path = tmp_path / "prices.json"
    detail = {"league": LEAGUE, "date": "2026-11-01", "listings": 9, "used": 5, "usable": 9}
    legacy = PriceEntry(3.0, "trade-api", "n", detail)
    write_price_file(path, allflame_prices(prices={**allflame_prices().prices, NAME: legacy}))

    store_market(path, thin_market(LEAGUE_END))

    assert NAME not in load_price_file(path).deep


# -- a refresh of the same league keeps the memory --------------------------------------------------------------------------------


def test_a_poe_ninja_refetch_of_the_same_league_keeps_the_deep_reading_even_where_the_new_file_prices_the_name(tmp_path):
    old = stored(tmp_path, deep_market(), thin_market())
    new = allflame_prices(prices={**allflame_prices().prices, NAME: PriceEntry(7.0, "poe.ninja")})

    merged, warnings = merge_trade_prices(new, old)

    assert merged.deep[NAME].chaos == 14.0 and merged.prices[NAME] == PriceEntry(7.0, "poe.ninja")
    assert not any("deep" in warning for warning in warnings)


def test_a_refetch_of_another_league_drops_the_deep_reading_with_a_warning(tmp_path):
    old = stored(tmp_path, deep_market())

    merged, warnings = merge_trade_prices(allflame_prices(league="Standard"), old)

    assert merged.deep == {} and any("last deep trade reading" in warning and NAME in warning for warning in warnings)
