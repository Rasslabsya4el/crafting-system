"""A thin poe.ninja line read beside the trade site's bulk-exchange offers; the deeper reading is the price (#616).

The recorded answer is a real one (anonymous, Allflame, 2026-11-07): one offer for the Prismatic Fossil, 18 Chaos each, 24 in stock.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.price_file import DeepReading
from crafting_system.prices.deepen import ReadStopped, deepen_with_trade, exchange_entry
from crafting_system.prices.provenance import EXCHANGE, OLD_PRICE, PREVIOUS_LEAGUE, THIN_MARKET, TRADE, Provenance
from crafting_system.prices.trade_exchange import ExchangeReading, exchange_body, read_offers, static_ids
from crafting_system.prices.trade_market import classify

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
    return exchange_entry(ExchangeReading(chaos, depth, 5, 12, 12, 0, "quoted"), "Allflame", DAY, "x")  # twelve offers: a market with enough


# --- reading the offers ------------------------------------------------------------------------------------------------


def test_the_recorded_offer_is_18_chaos_a_unit_on_24_units():
    got = read_offers(json.loads(RECORDED.read_text(encoding="utf-8")), RATES)

    assert (got.chaos, got.depth, got.used, got.total, got.state) == (18.0, 24.0, 1, 1, "thin")  # one offer in the book: a thin market


def test_the_price_is_the_mean_of_the_five_cheapest_units_and_the_depth_the_units_of_the_offers_they_come_from():
    """OR-8 on the bulk exchange: a unit is what a listing is. Units 10, 10, 11, 11, 11 from the first two offers: 53 / 5 = 10.6 c on 2 + 3 units."""
    offers = [offer(ask, units) for ask, units in [(10, 2), (11, 3), (12, 4), (13, 5), (14, 6), (50, 1000), (60, 1000)]]

    got = read_offers(answer(*offers), RATES, k=5)

    assert got.chaos == pytest.approx(53 / 5)
    assert got.depth == 5.0
    assert (got.used, got.offers, got.total) == (2, 7, 7)


def test_the_cheapest_are_found_whatever_order_the_site_lists_them_in():
    got = read_offers(answer(offer(50, 9), offer(10, 2), offer(30, 4)), RATES, k=3)

    assert got.chaos == pytest.approx((10 * 2 + 30 * 1) / 3) and got.depth == 6.0  # 2 units at 10 and 1 of the 4 at 30: 50 / 3 = 16.67 on 2 + 4 units


def test_a_book_with_fewer_units_than_five_is_the_mean_of_all_its_units():
    got = read_offers(answer(offer(5, 1), offer(15, 2)), RATES)

    assert got.chaos == pytest.approx(35 / 3) and got.depth == 3.0 and got.used == 2  # (5 + 15 * 2) / 3


def test_one_large_dear_stock_does_not_set_the_price():
    """#706: Muttering Essence of Hatred read 134,936 c when the five cheapest offers were weighted by their units and the dearest held the most."""
    book = answer(offer(20, 2), offer(25, 2), offer(30, 1), offer(200_000, 8), *[offer(300_000, 1) for _ in range(6)])

    got = read_offers(book, RATES)

    assert got.chaos == pytest.approx((20 * 2 + 25 * 2 + 30) / 5) and got.depth == 5.0  # 120 / 5 = 24 c, the 200,000 c stock is not reached


def test_a_bulk_offer_prices_the_units_a_buyer_takes_from_it():
    """80 units at 1 c and four single units at 20 c: the five cheapest units are all at 1 c (not the 16.2 c of five offers' plain mean,
    nor the 1.905 c of a mean weighted by five offers' units); 80 units stand behind the price."""
    book = answer(offer(1, 80), *[offer(20, 1) for _ in range(4)])

    got = read_offers(book, RATES)

    assert got.chaos == pytest.approx(1.0) and got.depth == 80.0 and got.used == 1


def test_an_item_listing_of_one_unit_each_is_priced_by_the_plain_mean_as_before():
    """One unit a listing: the five cheapest units are the five cheapest listings (what a start item and `cli trade` give)."""
    book = answer(*[offer(ask, 1) for ask in (3, 5, 7, 9, 11, 40)])

    got = read_offers(book, RATES)

    assert got.chaos == pytest.approx(7.0) and got.depth == 5.0


def test_the_market_rule_of_355_is_read_on_the_offers_of_the_book():
    """Ten offers with three priced is a market with enough offers; nine, or ten with two priced, is thin (OR-8, #718)."""
    ten = [offer(ask, 1) for ask in range(1, 11)]

    assert read_offers(answer(*ten), RATES).state == "quoted"
    assert read_offers(answer(*ten[:9]), RATES).state == "thin"
    assert read_offers(answer(*ten[:2], total=10), RATES).state == "thin"  # ten in the book, two of them priced


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

    outcome = deepen_with_trade(start, ["Prismatic Fossil"], lambda name: reading(8.0, 24.0))
    got, warnings = outcome.price_file, outcome.warnings

    entry = got.prices["Prismatic Fossil"]
    assert (entry.chaos, entry.source, entry.provenance.kind, entry.provenance.depth) == (8.0, "trade-api", TRADE, 24.0)
    assert entry.provenance.other == {"kind": EXCHANGE, "chaos": 0.2, "depth": 3.0}
    assert "are taken over" in warnings[0]


def test_the_exchange_line_stays_when_it_is_the_deeper_one_and_the_trade_reading_is_kept_beside_it():
    start = file(**{"Prismatic Fossil": ninja_entry(6.0, 40.0)})

    outcome = deepen_with_trade(start, ["Prismatic Fossil"], lambda name: reading(18.0, 24.0))
    got, warnings = outcome.price_file, outcome.warnings

    entry = got.prices["Prismatic Fossil"]
    assert (entry.chaos, entry.provenance.kind) == (6.0, EXCHANGE)
    assert entry.provenance.other == {"kind": TRADE, "chaos": 18.0, "depth": 24.0}


def test_a_name_with_no_price_gets_the_trade_reading_and_one_with_nothing_anywhere_gets_a_warning_and_stays_unpriced():
    outcome = deepen_with_trade(file(), ["A", "B"], lambda name: reading(3.0, 5.0) if name == "A" else None)
    got, warnings = outcome.price_file, outcome.warnings

    assert got.prices["A"].chaos == 3.0 and "B" not in got.prices
    assert any(w.startswith("B:") and "no offer on the trade site" in w for w in warnings)


def test_this_leagues_reading_beats_a_previous_leagues_price_whatever_the_depths():
    start = file(**{"Shrieking Essence of Fear": ninja_entry(0.3425, 90_000.0, PREVIOUS_LEAGUE, "Mirage", "2026-06-13")})

    outcome = deepen_with_trade(start, ["Shrieking Essence of Fear"], lambda name: reading(7.8, 2.0))
    got, warnings = outcome.price_file, outcome.warnings

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

    outcome = deepen_with_trade(start, ["Hand", "Bought"], lambda name: asked.append(name) or reading(1.0, 99.0))
    got, warnings = outcome.price_file, outcome.warnings

    assert asked == [] and got.prices == start.prices


def book(chaos, depth, used=5, offers=12):
    """The entry of a trade reading: `used` offers priced, holding `depth` units, out of `offers` in the book (fewer than ten: thin)."""
    return exchange_entry(ExchangeReading(chaos, depth, used, offers, offers, 0, classify(offers, offers)), "Allflame", DAY, "x")


def test_the_deeper_reading_wins_measured_in_units_whatever_the_number_of_offers_behind_it():
    """poe.ninja 0.33 on 0.5 units against a book of twelve offers, 12.5 on 94 units: the units decide (the spec's "the deeper of the two")."""
    start = file(**{"Shrieking Essence of Fear": ninja_entry(0.33, 0.5)})

    outcome = deepen_with_trade(start, ["Shrieking Essence of Fear"], lambda name: book(12.5, 94.0, used=4, offers=12))

    entry = outcome.price_file.prices["Shrieking Essence of Fear"]
    assert (entry.chaos, entry.provenance.kind, entry.provenance.depth, entry.provenance.market) == (12.5, TRADE, 94.0, None)
    assert entry.provenance.other == {"kind": EXCHANGE, "chaos": 0.33, "depth": 0.5}
    assert "are taken over" in outcome.warnings[0]


def test_a_book_with_fewer_units_than_the_exchange_line_does_not_replace_it_whatever_the_number_of_offers():
    """The other way round: a book of twelve offers on 3 units loses to a line on 40 units; the offers' number decides nothing, the units do."""
    start = file(Line=ninja_entry(1.0, 40.0))

    outcome = deepen_with_trade(start, ["Line"], lambda name: book(9.0, 3.0, used=5, offers=12))

    entry = outcome.price_file.prices["Line"]
    assert (entry.chaos, entry.provenance.kind) == (1.0, EXCHANGE)
    assert entry.provenance.other == {"kind": TRADE, "chaos": 9.0, "depth": 3.0}


def test_a_thin_book_never_replaces_a_line_of_this_league_whatever_its_depth():
    """OR-8 (#718): a book of four offers is a thin market. The Fear of 2026-11-07, 12.5 on 94 units in 4 offers, keeps the line of 0.5 units,
    which stays marked by its depth; the Orb of Transmutation's six-offer book (one at 372 c) cannot replace its line of 750 units either."""
    start = file(**{"Shrieking Essence of Fear": ninja_entry(0.33, 0.5)})

    outcome = deepen_with_trade(start, ["Shrieking Essence of Fear"], lambda name: book(12.5, 94.0, used=4, offers=4))

    entry = outcome.price_file.prices["Shrieking Essence of Fear"]
    assert (entry.chaos, entry.provenance.kind) == (0.33, EXCHANGE)
    assert entry.provenance.other == {"kind": TRADE, "chaos": 12.5, "depth": 94.0}


def test_a_thin_book_where_this_league_has_no_price_is_its_mean_marked_thin():
    """The start of a league or a rare item: no line of this league, a previous league's price or none; the thin mean stands, marked (OR-8)."""
    previous = file(Old=ninja_entry(0.34, 9e4, PREVIOUS_LEAGUE, "Mirage", "2026-06-13"))

    outcome = deepen_with_trade(previous, ["Old", "New"], lambda name: book(8.8, 71.0, used=2, offers=2))

    for name in ("Old", "New"):
        entry = outcome.price_file.prices[name]
        assert (entry.chaos, entry.provenance.market, entry.provenance.book) == (8.8, THIN_MARKET, 2)
    assert outcome.price_file.deep == {}  # a thin book is never remembered as a deep reading


def test_a_thin_book_after_a_deep_reading_this_league_is_the_old_price_marked_with_its_day():
    """The end of a league: Hatred was read deep on 2026-11-01 at 3 c; now five troll offers. The page shows 3 c, old, read on 2026-11-01."""
    deep = {"Hatred": DeepReading(3.0, "Allflame", date(2026, 11, 1), 40, 38)}
    start = PriceFile("Allflame", NOW, 400.0, {}, deep=deep)

    outcome = deepen_with_trade(start, ["Hatred"], lambda name: book(134_936.0, 13.0, used=5, offers=5))

    entry = outcome.price_file.prices["Hatred"]
    assert (entry.chaos, entry.provenance.market, entry.provenance.date, entry.provenance.book) == (3.0, OLD_PRICE, "2026-11-01", 5)
    assert outcome.price_file.deep == deep  # kept through the thin reading


def test_a_deep_reading_of_another_league_is_never_the_old_price():
    deep = {"Hatred": DeepReading(3.0, "Mirage", date(2026, 6, 1), 40, 38)}
    start = PriceFile("Allflame", NOW, 400.0, {}, deep=deep)

    outcome = deepen_with_trade(start, ["Hatred"], lambda name: book(50.0, 13.0, used=5, offers=5))

    entry = outcome.price_file.prices["Hatred"]
    assert (entry.chaos, entry.provenance.market) == (50.0, THIN_MARKET)


def test_a_book_with_enough_offers_that_is_taken_becomes_the_last_deep_reading_and_replaces_an_older_one():
    """A deep reading, then a thin one, then a deep one: the memory holds the first through the thin one and the second after it (#718)."""
    old = {"Fossil": DeepReading(5.0, "Allflame", date(2026, 11, 1), 30, 30)}
    start = PriceFile("Allflame", NOW, 400.0, {}, deep=old)

    thin = deepen_with_trade(start, ["Fossil"], lambda name: book(90.0, 2.0, used=2, offers=3)).price_file
    assert thin.deep == old and thin.prices["Fossil"].chaos == 5.0

    fresh = deepen_with_trade(PriceFile("Allflame", NOW, 400.0, {}, deep=thin.deep), ["Fossil"], lambda name: book(7.0, 60.0, used=3, offers=25)).price_file
    assert fresh.deep["Fossil"] == DeepReading(7.0, "Allflame", DAY, 25, 25)
    assert fresh.prices["Fossil"].provenance.market is None


# --- a site that stops: nothing already read is thrown away -------------------------------------------------------------


def test_a_read_that_stops_leaves_the_rest_unread_and_marked_and_keeps_what_was_read():
    start = file(A=ninja_entry(1.0, 2.0), B=ninja_entry(2.0, 3.0), C=ninja_entry(3.0, 4.0))

    def read(name):
        if name == "B":
            raise ReadStopped("the trade site blocked the run")
        return book(9.0, 50.0)

    outcome = deepen_with_trade(start, ["A", "B", "C", "D"], read)

    prices = outcome.price_file.prices
    assert prices["A"].chaos == 9.0 and prices["A"].provenance.trade_unread is None  # read before the stop
    assert prices["B"].chaos == 2.0 and prices["B"].provenance.trade_unread == "the trade site blocked the run"
    assert prices["C"].provenance.trade_unread == "the trade site blocked the run"
    assert "D" not in prices  # no price at all: nothing to mark, but it is reported
    assert outcome.unread == dict.fromkeys(["B", "C", "D"], "the trade site blocked the run")


def test_the_unread_mark_round_trips_through_the_price_file_json():
    from crafting_system.prices.provenance import from_json, to_json

    p = Provenance(EXCHANGE, "Allflame", "2026-11-07", 3.0, trade_unread="the request budget of the run was spent")

    assert from_json(to_json(p), "test") == p



def test_the_chaos_orb_and_the_divine_orb_are_never_read_on_the_trade_site():
    """The Chaos Orb is the unit of every price (always 1) and the Divine Orb's price is the file's rate: a trade reading of either would break the file (the first snapshot of this PR priced the Chaos Orb at 1.158)."""
    start = file(**{"Chaos Orb": PriceEntry(1.0, "poe.ninja"), "Divine Orb": PriceEntry(400.0, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", "2026-11-07", 2.0))})
    asked = []

    outcome = deepen_with_trade(start, ["Chaos Orb", "Divine Orb"], lambda name: asked.append(name) or book(9.0, 9e5))

    assert asked == [] and outcome.price_file.prices == start.prices
