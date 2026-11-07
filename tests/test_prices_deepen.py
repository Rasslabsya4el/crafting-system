"""A thin poe.ninja line read beside the trade site's bulk-exchange offers; the deeper reading is the price (#616).

The recorded answer is a real one (anonymous, Allflame, 2026-11-07): one offer for the Prismatic Fossil, 18 Chaos each, 24 in stock.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.deepen import deepen_with_trade, exchange_entry
from crafting_system.prices.provenance import EXCHANGE, PREVIOUS_LEAGUE, TRADE, Provenance
from crafting_system.prices.trade_exchange import ExchangeReading, exchange_body, read_offers, static_ids

RECORDED = Path(__file__).resolve().parent / "fixtures" / "trade" / "recorded" / "exchange_prismatic_fossil.json"
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
DAY = date(2026, 11, 7)
RATES = {"chaos": 1.0, "divine": 400.0}


def offer(ask: float, units: float, currency="chaos", amount=1):
    return {"listing": {"offers": [{"exchange": {"currency": currency, "amount": ask * amount}, "item": {"amount": amount, "stock": units}}]}}


def answer(*offers, total=None):
    return {"total": len(offers) if total is None else total, "result": {f"id{i}": each for i, each in enumerate(offers)}}


def ninja_entry(chaos, depth, kind=EXCHANGE, league="Allflame", day="2026-11-07"):
    source = "poe.ninja-previous-league" if kind == PREVIOUS_LEAGUE else "poe.ninja"
    return PriceEntry(chaos, source, None, None, Provenance(kind, league, day, depth))


def file(**prices):
    return PriceFile("Allflame", NOW, 400.0, prices)


def reading(chaos, depth):
    return exchange_entry(ExchangeReading(chaos, depth, 5, 12, 12, 0), "Allflame", DAY, "x")


# --- reading the offers ------------------------------------------------------------------------------------------------


def test_the_recorded_offer_is_18_chaos_a_unit_on_24_units():
    got = read_offers(json.loads(RECORDED.read_text(encoding="utf-8")), RATES)

    assert (got.chaos, got.depth, got.used, got.total) == (18.0, 24.0, 1, 1)


def test_the_price_is_the_mean_of_the_cheapest_five_offers_and_the_depth_the_units_they_hold():
    offers = [offer(ask, units) for ask, units in [(10, 2), (11, 3), (12, 4), (13, 5), (14, 6), (50, 1000), (60, 1000)]]

    got = read_offers(answer(*offers), RATES, k=5)

    assert got.chaos == pytest.approx(12.0)
    assert got.depth == 20.0
    assert (got.used, got.offers) == (5, 7)


def test_the_cheapest_are_found_whatever_order_the_site_lists_them_in():
    got = read_offers(answer(offer(50, 9), offer(10, 2), offer(30, 4)), RATES, k=2)

    assert (got.chaos, got.depth) == (20.0, 6.0)


def test_an_offer_asked_in_divine_orbs_is_turned_to_chaos_per_unit():
    got = read_offers(answer(offer(0.05, 7, currency="divine", amount=2)), RATES)

    assert got.chaos == pytest.approx(0.05 * 400.0)  # 0.1 Divine for 2 units is 0.05 Divine each


def test_an_offer_in_a_currency_with_no_rate_or_without_amounts_is_dropped_and_counted():
    got = read_offers(answer(offer(5, 3), offer(4, 3, currency="mirror"), {"listing": {"offers": [{}]}}), RATES)

    assert (got.chaos, got.offers, got.dropped) == (5.0, 1, 2)
    assert read_offers(answer(offer(4, 3, currency="mirror")), RATES) is None
    assert read_offers({"total": 0, "result": {}}, RATES) is None


def test_the_exchange_query_asks_for_chaos_and_divine_offers_cheapest_first():
    body = exchange_body("prismatic-fossil")

    assert body["query"]["want"] == ["prismatic-fossil"] and body["query"]["have"] == ["chaos", "divine"]
    assert body["sort"] == {"have": "asc"}


def test_an_item_text_maps_to_its_exchange_id_from_the_static_list():
    static = {"result": [{"id": "Delve", "entries": [{"id": "prismatic-fossil", "text": "Prismatic Fossil"}]}, {"id": "Currency", "entries": [{"id": "chaos", "text": "Chaos Orb"}]}]}

    assert static_ids(static) == {"Prismatic Fossil": "prismatic-fossil", "Chaos Orb": "chaos"}


# --- keeping the deeper reading ----------------------------------------------------------------------------------------


def test_the_trade_offers_win_over_a_thin_exchange_line_and_the_exchange_reading_is_kept_in_the_provenance():
    """#616: 0.2 Chaos on 3 units against 8 on 24 in stock."""
    start = file(**{"Prismatic Fossil": ninja_entry(0.2, 3.0)})

    got, warnings = deepen_with_trade(start, ["Prismatic Fossil"], lambda name: reading(8.0, 24.0))

    entry = got.prices["Prismatic Fossil"]
    assert (entry.chaos, entry.source, entry.provenance.kind, entry.provenance.depth) == (8.0, "trade-api", TRADE, 24.0)
    assert entry.provenance.other == {"kind": EXCHANGE, "chaos": 0.2, "depth": 3.0}
    assert "deeper" in warnings[0]


def test_the_exchange_line_stays_when_it_is_the_deeper_one_and_the_trade_reading_is_kept_beside_it():
    start = file(**{"Prismatic Fossil": ninja_entry(6.0, 40.0)})

    got, _ = deepen_with_trade(start, ["Prismatic Fossil"], lambda name: reading(18.0, 24.0))

    entry = got.prices["Prismatic Fossil"]
    assert (entry.chaos, entry.provenance.kind) == (6.0, EXCHANGE)
    assert entry.provenance.other == {"kind": TRADE, "chaos": 18.0, "depth": 24.0}


def test_a_name_with_no_price_gets_the_trade_reading_and_one_with_nothing_anywhere_gets_a_warning_and_stays_unpriced():
    got, warnings = deepen_with_trade(file(), ["A", "B"], lambda name: reading(3.0, 5.0) if name == "A" else None)

    assert got.prices["A"].chaos == 3.0 and "B" not in got.prices
    assert any(w.startswith("B:") and "no offer on the trade site" in w for w in warnings)


def test_this_leagues_reading_beats_a_previous_leagues_price_whatever_the_depths():
    start = file(**{"Shrieking Essence of Fear": ninja_entry(0.3425, 90_000.0, PREVIOUS_LEAGUE, "Mirage", "2026-06-13")})

    got, _ = deepen_with_trade(start, ["Shrieking Essence of Fear"], lambda name: reading(7.8, 2.0))

    assert got.prices["Shrieking Essence of Fear"].chaos == 7.8


def test_a_price_deep_enough_is_not_read_again_and_no_request_is_spent_on_it():
    asked = []
    start = file(Deep=ninja_entry(1.0, 500.0), Thin=ninja_entry(1.0, 5.0))

    deepen_with_trade(start, ["Deep", "Thin"], lambda name: asked.append(name) or None, below_units=100.0)

    assert asked == ["Thin"]


def test_a_hand_price_and_a_trade_price_already_in_the_file_are_never_replaced():
    hand = PriceEntry(5.0, "override", None, None, Provenance("override", "Allflame", "2026-11-07"))
    start = file(Hand=hand, Bought=reading(9.0, 3.0))
    asked = []

    got, _ = deepen_with_trade(start, ["Hand", "Bought"], lambda name: asked.append(name) or reading(1.0, 99.0))

    assert asked == [] and got.prices == start.prices


def thin_book(chaos, depth):
    """A book of fewer offers than the market rail: the mean is of all of them."""
    return exchange_entry(ExchangeReading(chaos, depth, 5, 5, 5, 0), "Allflame", DAY, "x")


def test_a_book_of_fewer_offers_than_the_market_rail_replaces_no_price_of_this_league():
    """The Screaming Essence of Spite on 2026-11-07: five offers, 5, 10, 15, 35 Chaos and one Divine Orb, a mean of 110 against poe.ninja's 1."""
    start = file(**{"Screaming Essence of Spite": ninja_entry(1.0, 6.7)})

    got, warnings = deepen_with_trade(start, ["Screaming Essence of Spite"], lambda name: thin_book(110.6, 91.0))

    entry = got.prices["Screaming Essence of Spite"]
    assert (entry.chaos, entry.provenance.kind) == (1.0, EXCHANGE)
    assert entry.provenance.other == {"kind": TRADE, "chaos": 110.6, "depth": 91.0}
    assert "kept" in warnings[0]


def test_a_thin_book_still_beats_a_previous_leagues_price_and_a_missing_price():
    previous = file(Old=ninja_entry(0.34, 9e4, PREVIOUS_LEAGUE, "Mirage", "2026-06-13"))

    got, _ = deepen_with_trade(previous, ["Old", "New"], lambda name: thin_book(8.8, 71.0))

    assert got.prices["Old"].chaos == 8.8 and got.prices["New"].chaos == 8.8
