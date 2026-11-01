"""The price source setting and the two prices side by side (#357, ADR-0061 decision 2).

Every test builds a small `PriceFile` by hand and passes `today`: no network and no clock.
"""

import math
from datetime import UTC, date, datetime

import pytest
from trade_support import price_file as allflame_prices

from crafting_system.prices import (
    MarketRecord,
    PriceEntry,
    PriceFile,
    load_price_file,
    write_price_file,
)
from crafting_system.prices.price_source import (
    BOTH,
    NINJA,
    TRADE,
    check_gap_percent,
    check_price_source,
    gap_percent,
    ninja_row,
    source_price,
)

TODAY = date(2026, 11, 1)
LEAGUE = "Allflame"
BASE = "Test Boots (ilvl 86)"
FRACTURED_BASE = "Test Boots (ilvl 86, Shaper)"
FRESH = "2026-11-01"
STALE_DAY = "2026-10-24"  # 8 days before TODAY; the limit is 7


def trade_entry(chaos: float, day: str = FRESH, listings: int = 14, usable: int = 5) -> PriceEntry:
    """A trade-api price `offer` accepts when the day is fresh and the market meets the rail."""
    detail = {"date": day, "league": LEAGUE, "listings": listings, "usable": usable, "k": 5}
    return PriceEntry(chaos, "trade-api", detail=detail)


def ninja_entry(chaos: float) -> PriceEntry:
    return PriceEntry(chaos, "poe.ninja")


def pf(*, trade: PriceEntry | None = None, ninja: PriceEntry | None = None, name: str = BASE, beside: bool = True, **changes) -> PriceFile:
    """A price file with `name` priced by `trade`; its poe.ninja row sits in the `ninja` table (`beside`) or, with no trade price, in `prices`."""
    prices = dict(allflame_prices().prices)
    table: dict[str, PriceEntry] = {}
    if trade is not None:
        prices[name] = trade
        if ninja is not None:
            table[name] = ninja
    elif ninja is not None:
        if beside:
            table[name] = ninja
        else:
            prices[name] = ninja
    return allflame_prices(prices=prices, ninja=table, **changes)


def market(state: str, listings: int, usable: int, day: str = FRESH) -> MarketRecord:
    return MarketRecord(state, LEAGUE, date.fromisoformat(day), listings, usable, "hash", {})


# -- 1. the three settings ----------------------------------------------------------------------------------------------


def test_ninja_prices_with_the_ninja_row_and_does_not_consult_the_trade_price():
    result = source_price(pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, NINJA, TODAY)

    assert (result.used, result.chaos, result.ninja_chaos) == ("poe.ninja", 100.0, 100.0)
    assert result.trade is None and result.trade_chaos is None
    assert not result.fallback and result.gap_percent is None and not result.gap_flagged and not result.side_by_side
    assert result.setting == "ninja" and result.offered


def test_trade_prices_with_the_trade_price_and_does_not_read_the_ninja_row():
    result = source_price(pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, TRADE, TODAY)

    assert (result.used, result.chaos, result.trade_chaos) == ("trade", 125.0, 125.0)
    assert result.ninja_chaos is None and result.gap_percent is None and not result.gap_flagged
    assert not result.fallback and not result.side_by_side
    assert result.trade is not None and result.trade.state == "quoted"


def test_both_prices_with_the_trade_price_not_as_a_fallback_and_shows_both_prices():
    result = source_price(pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY)

    assert (result.used, result.chaos, result.fallback) == ("trade", 125.0, False)
    assert (result.trade_chaos, result.ninja_chaos, result.side_by_side) == (125.0, 100.0, True)
    assert result.gap_percent == pytest.approx(25.0) and result.marks == ()
    assert result.source_label == "trade-api, 14 listings, 0 d old"


def test_a_ninja_row_in_prices_is_the_ninja_price_when_no_trade_price_exists():
    prices = pf(ninja=ninja_entry(80.0), beside=False)

    assert ninja_row(prices, BASE) == ninja_entry(80.0)
    assert source_price(prices, BASE, NINJA, TODAY).chaos == 80.0
    both = source_price(prices, BASE, BOTH, TODAY)
    assert (both.used, both.chaos, both.fallback, both.ninja_chaos, both.trade_chaos) == ("poe.ninja", 80.0, True, 80.0, None)


def test_a_poe_ninja_history_entry_in_prices_counts_as_a_ninja_row():
    prices = pf(ninja=PriceEntry(70.0, "poe.ninja-history"), beside=False)

    assert source_price(prices, BASE, NINJA, TODAY).chaos == 70.0


def test_an_unknown_setting_is_a_value_error_naming_the_three():
    with pytest.raises(ValueError, match="ninja, trade, both"):
        source_price(pf(), BASE, "poe", TODAY)


# -- 2. both falls back, trade and ninja refuse --------------------------------------------------------------------------


def test_both_with_a_stale_trade_price_falls_back_to_the_ninja_row_and_says_why():
    prices = pf(trade=trade_entry(125.0, day=STALE_DAY), ninja=ninja_entry(100.0))

    result = source_price(prices, BASE, BOTH, TODAY)

    assert (result.used, result.chaos, result.fallback) == ("poe.ninja", 100.0, True)
    assert result.trade is not None and result.trade.state == "stale" and result.trade.age_days == 8
    assert result.trade_chaos is None and result.ninja_chaos == 100.0
    assert not result.side_by_side and result.gap_percent is None and not result.gap_flagged
    fallback_mark = result.marks[0]
    assert fallback_mark.startswith("fallback:") and "stale" in fallback_mark and "8 days old (limit 7)" in fallback_mark
    assert result.source_label == "poe.ninja (fallback: trade price not usable)"


def test_a_trade_price_exactly_seven_days_old_is_still_fresh():
    result = source_price(pf(trade=trade_entry(125.0, day="2026-10-25"), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY)

    assert (result.used, result.fallback) == ("trade", False)


def test_both_with_a_thin_trade_market_of_5_listings_falls_back():
    prices = pf(trade=trade_entry(125.0, listings=5), ninja=ninja_entry(100.0))

    result = source_price(prices, BASE, BOTH, TODAY)

    assert (result.used, result.chaos, result.fallback) == ("poe.ninja", 100.0, True)
    assert result.trade is not None and result.trade.state == "thin"
    assert "thin" in result.marks[0] and "5 listings on the site" in result.marks[0]


def test_both_with_a_recorded_thin_market_and_a_ninja_row_falls_back():
    prices = pf(ninja=ninja_entry(100.0), beside=False, markets={BASE: market("thin", 4, 4)})

    result = source_price(prices, BASE, BOTH, TODAY)

    assert (result.used, result.chaos, result.fallback) == ("poe.ninja", 100.0, True)
    assert result.trade is not None and result.trade.state == "thin" and result.trade.listings == 4


def test_both_with_no_trade_listings_at_all_falls_back():
    prices = pf(ninja=ninja_entry(100.0), beside=False, markets={BASE: market("none", 0, 0)})

    result = source_price(prices, BASE, BOTH, TODAY)

    assert (result.used, result.chaos, result.fallback) == ("poe.ninja", 100.0, True)
    assert result.trade is not None and result.trade.state == "none"
    assert "no listings" in result.marks[0]


def test_both_with_nothing_recorded_about_the_trade_price_falls_back():
    result = source_price(pf(ninja=ninja_entry(100.0), beside=False), BASE, BOTH, TODAY)

    assert (result.used, result.fallback) == ("poe.ninja", True)
    assert result.trade is not None and result.trade.state == "unknown"


def test_both_with_a_stale_trade_price_and_no_ninja_row_is_not_offered_with_a_reason():
    result = source_price(pf(trade=trade_entry(125.0, day=STALE_DAY)), BASE, BOTH, TODAY)

    assert (result.used, result.chaos, result.offered, result.fallback) == ("none", None, False, False)
    assert result.trade is not None and result.trade.state == "stale"
    assert "8 days old" in (result.reason or "") and "no poe.ninja row of this name" in (result.reason or "")


def test_trade_with_a_stale_trade_price_is_not_offered_even_though_a_ninja_row_exists():
    result = source_price(pf(trade=trade_entry(125.0, day=STALE_DAY), ninja=ninja_entry(100.0)), BASE, TRADE, TODAY)

    assert (result.used, result.chaos, result.offered, result.fallback) == ("none", None, False, False)
    assert result.trade is not None and result.trade.state == "stale"
    assert result.reason == "trade price is 8 days old (limit 7)"
    assert result.ninja_chaos is None


def test_ninja_with_no_ninja_row_is_not_offered_even_with_a_fresh_trade_price():
    result = source_price(pf(trade=trade_entry(125.0)), BASE, NINJA, TODAY)

    assert (result.used, result.chaos, result.offered) == ("none", None, False)
    assert result.reason == "no poe.ninja row of this name"


# -- 3. the gap ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("trade", "ninja", "threshold", "percent", "flagged"),
    [
        (125.0, 100.0, 20.0, 25.0, True),
        (115.0, 100.0, 20.0, 15.0, False),
        (120.0, 100.0, 20.0, 20.0, False),  # exactly at the threshold is not flagged
        (100.0, 125.0, 20.0, 25.0, True),  # the ninja price the dearer one: the same gap
        (100.0, 115.0, 20.0, 15.0, False),
        (115.0, 100.0, 10.0, 15.0, True),  # a lower threshold flags the 15% case
        (125.0, 100.0, 50.0, 25.0, False),  # a higher one clears the 25% case
        (110.0, 100.0, 10.0, 10.0, False),  # exactly 10% is not above 10 (no float noise)
        (130.0, 100.0, 30.0, 30.0, False),
        (1.1, 1.0, 10.0, 10.0, False),  # float noise: 1.1 / 1.0 - 1 is 10.000000000000009
        (1.3, 1.0, 30.0, 30.0, False),
        (100.0, 100.0, 20.0, 0.0, False),
    ],
)
def test_the_gap_is_flagged_only_strictly_above_the_threshold(trade, ninja, threshold, percent, flagged):
    result = source_price(pf(trade=trade_entry(trade), ninja=ninja_entry(ninja)), BASE, BOTH, TODAY, gap_threshold=threshold)

    assert result.gap_percent == pytest.approx(percent)
    assert result.gap_flagged is flagged
    assert result.gap_threshold == threshold
    assert result.chaos == trade  # the planner's price is the trade price either way


@pytest.mark.parametrize("setting", [NINJA, TRADE])
def test_the_gap_is_only_computed_under_both(setting):
    result = source_price(pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, setting, TODAY)

    assert result.gap_percent is None and result.gap_flagged is False


def test_the_default_threshold_is_20_percent():
    result = source_price(pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY)

    assert result.gap_threshold == 20.0 and result.gap_flagged


def test_a_fallback_has_no_gap_to_flag():
    result = source_price(pf(trade=trade_entry(125.0, day=STALE_DAY), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY)

    assert result.gap_percent is None and not result.gap_flagged


@pytest.mark.parametrize("threshold", [0, -5.0, math.nan, math.inf, True, "20"])
def test_source_price_refuses_a_bad_threshold(threshold):
    with pytest.raises(ValueError, match="percent above zero"):
        source_price(pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY, gap_threshold=threshold)


def test_gap_percent_is_the_dearer_over_the_cheaper_in_percent_either_way_round():
    assert gap_percent(125.0, 100.0) == gap_percent(100.0, 125.0) == pytest.approx(25.0)
    assert gap_percent(3.0, 3.0) == 0.0


# -- 4. a fractured start ------------------------------------------------------------------------------------------------


def test_a_fractured_start_under_ninja_is_not_offered_even_when_the_file_holds_a_ninja_row_of_that_name():
    prices = pf(trade=trade_entry(900.0), ninja=ninja_entry(500.0), name=FRACTURED_BASE)
    assert ninja_row(prices, FRACTURED_BASE) == ninja_entry(500.0)  # the row is there ...

    result = source_price(prices, FRACTURED_BASE, NINJA, TODAY, fractured=True)  # ... and is not used

    assert (result.used, result.chaos, result.offered) == ("none", None, False)
    assert "no poe.ninja row" in (result.reason or "")


@pytest.mark.parametrize("setting", [TRADE, BOTH])
def test_a_fractured_start_is_priced_by_the_trade_price_alone_under_trade_and_both(setting):
    prices = pf(trade=trade_entry(900.0), ninja=ninja_entry(500.0), name=FRACTURED_BASE)

    result = source_price(prices, FRACTURED_BASE, setting, TODAY, fractured=True)

    assert (result.used, result.chaos, result.trade_chaos, result.fallback) == ("trade", 900.0, 900.0, False)
    assert result.ninja_chaos is None and result.gap_percent is None and not result.gap_flagged and not result.side_by_side


def test_a_fractured_start_under_both_with_no_trade_price_is_not_offered():
    prices = pf(ninja=ninja_entry(500.0), name=FRACTURED_BASE)

    result = source_price(prices, FRACTURED_BASE, BOTH, TODAY, fractured=True)

    assert (result.used, result.chaos, result.offered, result.fallback) == ("none", None, False, False)
    assert "a fractured base has no poe.ninja row" in (result.reason or "")


def test_a_fractured_start_under_trade_with_no_trade_price_is_not_offered():
    result = source_price(pf(name=FRACTURED_BASE), FRACTURED_BASE, TRADE, TODAY, fractured=True)

    assert (result.used, result.chaos) == ("none", None) and result.reason == "no trade price recorded"


# -- 5. a hand override --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("setting", [NINJA, TRADE, BOTH])
def test_a_hand_override_wins_under_every_setting(setting):
    prices = pf(ninja=ninja_entry(100.0), beside=False)
    prices.prices[BASE] = PriceEntry(42.0, "override")

    result = source_price(prices, BASE, setting, TODAY)

    assert (result.used, result.chaos, result.fallback, result.offered) == ("override", 42.0, False, True)
    assert result.trade is None and result.gap_percent is None
    assert result.marks == ("hand override of the price",)
    assert result.source_label == "override"


def test_a_hand_override_wins_for_a_fractured_start_under_ninja_too():
    prices = pf(name=FRACTURED_BASE)
    prices.prices[FRACTURED_BASE] = PriceEntry(42.0, "override")

    assert source_price(prices, FRACTURED_BASE, NINJA, TODAY, fractured=True).chaos == 42.0


# -- 6. the market rail and the printed text -----------------------------------------------------------------------------


def test_raising_min_listings_cuts_a_quoted_price_and_both_then_falls_back():
    prices = pf(trade=trade_entry(125.0, listings=14), ninja=ninja_entry(100.0))
    assert source_price(prices, BASE, BOTH, TODAY, min_listings=14).used == "trade"

    cut = source_price(prices, BASE, BOTH, TODAY, min_listings=15)

    assert cut.trade is not None and cut.trade.state == "thin" and "needs 15" in (cut.trade.reason or "")
    assert (cut.used, cut.chaos, cut.fallback) == ("poe.ninja", 100.0, True)
    assert source_price(prices, BASE, TRADE, TODAY, min_listings=15).chaos is None


def test_a_flagged_both_case_prints_both_numbers_and_the_word_gap():
    result = source_price(pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY)

    text = "\n".join(result.lines())
    assert "price source both: 125.00 Chaos [trade-api, 14 listings, 0 d old]" in text
    assert "trade 125.00 Chaos | poe.ninja 100.00 Chaos | gap 25.0%; GAP over 20%" in text
    document = result.document()
    assert document["trade_chaos"] == 125.0 and document["ninja_chaos"] == 100.0
    assert document["gap_flagged"] is True and document["gap_threshold_percent"] == 20.0
    assert document["gap_percent"] == pytest.approx(25.0) and document["used"] == "trade" and document["fallback"] is False


def test_an_unflagged_both_case_prints_both_numbers_without_the_flag():
    result = source_price(pf(trade=trade_entry(115.0), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY)

    text = "\n".join(result.lines())
    assert "trade 115.00 Chaos | poe.ninja 100.00 Chaos | gap 15.0%" in text and "GAP" not in text
    assert result.document()["gap_flagged"] is False


def test_the_fallback_case_prints_and_documents_the_mark():
    result = source_price(pf(trade=trade_entry(125.0, day=STALE_DAY), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY)

    text = "\n".join(result.lines())
    assert "price source both: 100.00 Chaos [poe.ninja (fallback: trade price not usable)]" in text
    assert "fallback: the trade price is not usable (stale: trade price is 8 days old (limit 7))" in text
    assert "does not prove an instant-buyout listing exists" in text
    document = result.document()
    assert document["fallback"] is True and document["used"] == "poe.ninja" and document["chaos"] == 100.0
    assert document["trade_chaos"] is None and document["gap_percent"] is None
    assert document["marks"][0].startswith("fallback:") and len(document["marks"]) == 2


def test_the_ninja_setting_prints_the_not_proof_mark():
    result = source_price(pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, NINJA, TODAY)

    assert result.lines() == [
        "price source ninja: 100.00 Chaos [poe.ninja]",
        "  a poe.ninja row does not prove an instant-buyout listing exists",
    ]


def test_a_not_offered_start_says_no_price_with_the_reason():
    result = source_price(pf(trade=trade_entry(125.0, day=STALE_DAY)), BASE, BOTH, TODAY)

    (line,) = result.lines()
    assert line.startswith("price source both: no price, ") and "8 days old" in line
    document = result.document()
    assert document["chaos"] is None and document["used"] == "none" and document["reason"] == result.reason


# -- 7. the setting checks -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["ninja", "trade", "both"])
def test_check_price_source_accepts_the_three_settings(value):
    assert check_price_source(value) == value


@pytest.mark.parametrize("value", ["poe.ninja", "Both", "", None, True, 0, ["both"]])
def test_check_price_source_rejects_anything_else(value):
    with pytest.raises(ValueError, match="ninja, trade, both"):
        check_price_source(value)


@pytest.mark.parametrize(("value", "expected"), [(20, 20.0), (0.5, 0.5), (15.0, 15.0), (1000, 1000.0)])
def test_check_gap_percent_accepts_a_positive_finite_number(value, expected):
    result = check_gap_percent(value)

    assert result == expected and isinstance(result, float)


@pytest.mark.parametrize("value", ["20", None, True, False, 0, 0.0, -1, -0.5, math.nan, math.inf, -math.inf, [20]])
def test_check_gap_percent_rejects_anything_else(value):
    with pytest.raises(ValueError, match="percent above zero"):
        check_gap_percent(value)


# -- 8. the price file keeps the ninja row -------------------------------------------------------------------------------


def test_the_ninja_row_survives_writing_and_loading_and_source_price_reads_it(tmp_path):
    original = pf(trade=trade_entry(125.0, day=STALE_DAY), ninja=ninja_entry(100.0))
    path = tmp_path / "prices.json"

    write_price_file(path, original)
    loaded = load_price_file(path)

    assert loaded.ninja == {BASE: ninja_entry(100.0)}
    result = source_price(loaded, BASE, BOTH, TODAY)
    assert (result.used, result.chaos, result.fallback) == ("poe.ninja", 100.0, True)
    fresh = source_price(
        pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0)), BASE, BOTH, TODAY
    )
    assert fresh.ninja_chaos == 100.0


def test_a_file_without_ninja_rows_loads_with_an_empty_table(tmp_path):
    path = tmp_path / "prices.json"
    write_price_file(path, PriceFile(LEAGUE, datetime(2026, 10, 30, tzinfo=UTC), 400.0, {"Chaos Orb": PriceEntry(1.0, "poe.ninja")}))

    assert load_price_file(path).ninja == {}


def test_a_ninja_row_is_found_under_the_canonical_influence_order_after_loading(tmp_path):
    messy = "Test Boots (ilvl 85, Warlord/Hunter)"
    canonical = "Test Boots (ilvl 85, Hunter/Warlord)"
    path = tmp_path / "prices.json"
    write_price_file(path, pf(trade=trade_entry(125.0), ninja=ninja_entry(100.0), name=messy))

    loaded = load_price_file(path)

    assert set(loaded.ninja) == {canonical}
    result = source_price(loaded, messy, BOTH, TODAY)  # the name is made canonical on the way in
    assert (result.name, result.used, result.trade_chaos, result.ninja_chaos) == (canonical, "trade", 125.0, 100.0)
