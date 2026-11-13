"""A price snapshot of a league as it stood on an earlier day, from poe.ninja's daily exchange rows (#838).

The owner's decision of 2026-11-13: the tests and benchmarks read the 3.29 league (Allflame) about one week in, not its end. Every
number below is made up and worked by hand: a rate of 2.5 Chaos on 1,000 Chaos of volume is 400 units traded on the day; Allflame
started on 2026-07-24, so 2026-07-31 is league day 7; from 2026-07-31 to 2026-11-10 is 31 + 30 + 31 + 10 = 102 days.
"""

import json
from datetime import UTC, date, datetime

import pytest

from crafting_system.prices import PriceEntry, PriceFile, load_price_file, write_price_file
from crafting_system.prices.ninja_history import exchange_readings, exchange_rows
from crafting_system.prices.price_marks import DEPTH, EARLIER, LATER, OLD, price_marks
from crafting_system.prices.provenance import EXCHANGE, HISTORY, PREVIOUS_LEAGUE, STASH, TRADE, Provenance
from crafting_system.prices.week_snapshot import DayRow, build_snapshot, reading_on, wants_history

START, AS_OF = date(2026, 7, 24), date(2026, 7, 31)
END = datetime(2026, 11, 10, 19, 0, tzinfo=UTC)


def details(*rows):
    """An exchange `details` answer: (timestamp, rate, volume) rows of the chaos pair."""
    return {"pairs": [{"id": "chaos", "history": [{"timestamp": t, "rate": r, "volumePrimaryValue": v} for t, r, v in rows]}]}


# --- the daily rows -----------------------------------------------------------------------------------------------


def test_an_exchange_reading_keeps_the_volume_beside_the_rate_and_the_old_rows_still_read():
    data = details(("2026-07-31T00:00:00Z", 2.5, 1000), ("2026-07-30T00:00:00Z", 2.0, 0), ("2026-07-20T00:00:00Z", 9.0, 50))

    assert exchange_readings(data, date(2026, 7, 25), AS_OF) == [DayRow(AS_OF, 2.5, 1000.0)]  # a day with no volume is no trade
    assert exchange_rows(data, date(2026, 7, 25), AS_OF) == [(AS_OF, 2.5)]


def test_the_reading_is_the_as_of_day_else_the_latest_traded_day_of_the_week_ending_on_it():
    on_day, before = DayRow(AS_OF, 2.5, 1000.0), DayRow(date(2026, 7, 29), 2.0, 300.0)

    assert reading_on([before, on_day], AS_OF) == on_day
    assert reading_on([before, DayRow(date(2026, 8, 1), 3.0, 10.0)], AS_OF) == before  # a later day is never read
    assert reading_on([DayRow(date(2026, 7, 24), 1.0, 10.0)], AS_OF) is None  # 7 days before: outside 07-25..07-31
    assert reading_on([], AS_OF) is None


# --- which names are read from the rows ---------------------------------------------------------------------------


def test_only_a_bulk_name_is_read_from_the_exchange_rows():
    query = {"query": {"status": {"option": "securable"}}}

    assert wants_history(PriceEntry(3.6, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", "2026-11-10", 99.0)))
    assert wants_history(PriceEntry(519.7, "trade-api", None, {"exchange": "bloodstained-fossil"}, Provenance(TRADE, "Allflame", "2026-11-10", 2.0)))
    assert not wants_history(PriceEntry(2.2, "trade-api", None, {"query": query}, Provenance(TRADE, "Allflame", "2026-11-10", 5.0)))
    assert not wants_history(PriceEntry(7.5, "poe.ninja", None, {"category": "BaseType"}, Provenance(STASH, "Allflame", "2026-11-10", 26.0, "observations")))


# --- the snapshot -------------------------------------------------------------------------------------------------


QUERY = {"query": {"status": {"option": "securable"}}}
RING = "Amethyst Ring, item level 75, fractured +(13-16) to all Attributes"


def end_file():
    """The league's end, as the 2026-11-10 snapshot holds it: an exchange line, a bulk trade reading and a bought start item."""
    prices = {
        "Chaos Orb": PriceEntry(1.0, "poe.ninja"),
        "Divine Orb": PriceEntry(516.2, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", "2026-11-10", 5.0)),
        "Exalted Orb": PriceEntry(3.61, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", "2026-11-10", 1596.7)),
        "Bloodstained Fossil": PriceEntry(519.7, "trade-api", None, {"exchange": "bloodstained-fossil"}, Provenance(TRADE, "Allflame", "2026-11-10", 2.0)),
        RING: PriceEntry(2.2, "trade-api", "mean of the 5 cheapest", {"query": QUERY}, Provenance(TRADE, "Allflame", "2026-11-10", 5.0, listings=5)),
    }
    return PriceFile("Allflame", END, 516.2, prices)


def older_file():
    """An older snapshot with one name the end file lacks."""
    return PriceFile("Allflame", datetime(2026, 10, 31, tzinfo=UTC), 372.2, {"Orb of Annulment": PriceEntry(4.0, "poe.ninja")})


ROWS = {
    ("Allflame", "divine-orb"): [DayRow(AS_OF, 176.6, 1766.0)],
    ("Allflame", "exalted-orb"): [DayRow(AS_OF, 2.5, 1000.0)],
    ("Allflame", "orb-of-annulment"): [DayRow(date(2026, 7, 29), 4.7, 47.0)],
    ("Mirage", "bound-fossil"): [DayRow(date(2026, 3, 13), 3.0, 60.0), DayRow(date(2026, 3, 14), 9.0, 90.0)],
}
MIRAGE = ("Mirage", date(2026, 3, 6))  # its league day 7 is 2026-03-13


def rows_of(league, slug):
    return ROWS.get((league, slug), [])


def build(previous=MIRAGE):
    templates = [("routes-allflame-2026-11-10.json", end_file()), ("routes-allflame-2026-10-31.json", older_file())]
    return build_snapshot(templates, rows_of, "Allflame", START, AS_OF, previous)


def test_a_bulk_name_is_its_rate_on_the_day_with_the_units_traded_as_its_depth():
    snapshot, _ = build()
    exalted = snapshot.prices["Exalted Orb"]

    assert (exalted.chaos, exalted.source) == (2.5, "poe.ninja-history")
    assert exalted.provenance == Provenance(HISTORY, "Allflame", "2026-07-31", 400.0)  # 1,000 Chaos at 2.5 Chaos is 400 units
    assert exalted.detail == {"league": "Allflame", "date": "2026-07-31", "exchange": "exalted-orb", "as_of": "2026-07-31", "league_day": 7}
    assert exalted.note == "poe.ninja daily exchange rate of 2026-07-31 (league day 7), 400 units traded that day"


def test_the_file_is_dated_on_the_day_it_is_a_snapshot_of_and_its_divine_is_that_days():
    snapshot, _ = build()

    assert (snapshot.league, snapshot.fetched_at, snapshot.chaos_per_divine) == ("Allflame", datetime(2026, 7, 31, tzinfo=UTC), 176.6)
    assert snapshot.prices["Divine Orb"].chaos == 176.6
    assert snapshot.prices["Chaos Orb"] == PriceEntry(1.0, "poe.ninja")


def test_a_day_with_no_trade_reads_the_latest_traded_day_before_it_and_says_so():
    snapshot, _ = build()
    annul = snapshot.prices["Orb of Annulment"]  # a name only the older template has

    assert (annul.chaos, annul.provenance.date, annul.provenance.depth) == (4.7, "2026-07-29", pytest.approx(10.0))
    assert annul.note == "poe.ninja daily exchange rate of 2026-07-29 (league day 5), 10 units traded that day; 2026-07-31 had no traded row"


def test_a_name_with_no_daily_row_keeps_the_templates_reading_as_a_marked_stand_in():
    snapshot, notes = build()
    ring, fossil = snapshot.prices[RING], snapshot.prices["Bloodstained Fossil"]

    assert (ring.chaos, ring.source, ring.detail, ring.provenance) == (2.2, "trade-api", {"query": QUERY}, end_file().prices[RING].provenance)
    assert ring.note == (
        "stand-in (OR-7): a trade search has no daily history; the reading of 2026-11-10 from routes-allflame-2026-11-10.json is kept"
        " (mean of the 5 cheapest)"
    )
    assert fossil.chaos == 519.7 and fossil.note == (
        "stand-in (OR-7): no poe.ninja daily row in Allflame from 2026-07-25 to 2026-07-31 nor in Mirage from 2026-03-07 to 2026-03-13;"
        " the reading of 2026-11-10 from routes-allflame-2026-11-10.json is kept"
    )
    assert notes == [f"{name}: stand-in, the reading of 2026-11-10 from routes-allflame-2026-11-10.json" for name in ("Bloodstained Fossil", RING)]


def test_a_bulk_name_the_league_lost_is_read_from_the_previous_league_at_the_same_age_and_marked_as_such():
    end = end_file()
    end.prices["Bound Fossil"] = PriceEntry(9.03, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", "2026-11-10", 26.2))
    snapshot, _ = build_snapshot([("t.json", end)], rows_of, "Allflame", START, AS_OF, MIRAGE)
    bound = snapshot.prices["Bound Fossil"]

    assert (bound.chaos, bound.source) == (3.0, "poe.ninja-previous-league")  # Mirage's day 7, not its day 8
    assert bound.provenance == Provenance(PREVIOUS_LEAGUE, "Mirage", "2026-03-13", 20.0)
    assert bound.note == (
        "poe.ninja daily exchange rate of 2026-03-13 in Mirage (its league day 7, the same age), 20 units traded that day:"
        " Allflame has no daily row from 2026-07-25 to 2026-07-31"
    )
    assert [mark.code for mark in price_marks(bound, snapshot, uses=1.0)] == [EARLIER]
    assert build_snapshot([("t.json", end)], rows_of, "Allflame", START, AS_OF, None)[0].prices["Bound Fossil"].chaos == 9.03  # no previous league: the stand-in


def test_a_stand_in_of_a_later_day_is_marked_with_its_day_and_a_reading_of_the_day_is_a_plain_fact():
    snapshot, _ = build()

    marks = price_marks(snapshot.prices[RING], snapshot, uses=1.0)
    assert [mark.code for mark in marks] == [LATER]
    assert marks[0].reason == "price of 2026-11-10, 102 days after the file"
    assert price_marks(snapshot.prices["Exalted Orb"], snapshot, uses=400.0) == ()
    assert [mark.code for mark in price_marks(snapshot.prices["Exalted Orb"], snapshot, uses=401.0)] == [DEPTH]


def test_a_reading_within_seven_days_after_the_file_is_not_marked_and_one_long_before_still_is():
    file = PriceFile("Allflame", datetime(2026, 7, 31, tzinfo=UTC), 176.6)

    def marks(day):
        return [mark.code for mark in price_marks(PriceEntry(1.0, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", day, 99.0)), file, uses=1.0)]

    assert marks("2026-08-07") == []
    assert marks("2026-08-08") == [LATER]
    assert marks("2026-07-23") == [OLD]


def test_a_snapshot_with_no_divine_row_on_the_day_is_refused():
    with pytest.raises(ValueError, match="Divine Orb"):
        build_snapshot([("t.json", end_file())], lambda league, slug: [], "Allflame", START, AS_OF, None)


def test_the_snapshot_writes_and_reads_back_in_the_format_of_the_others(tmp_path):
    snapshot, _ = build()
    path = tmp_path / "routes-allflame-2026-07-31.json"

    write_price_file(path, snapshot)

    assert load_price_file(path) == snapshot
    assert json.loads(path.read_text(encoding="utf-8"))["fetched_at"] == "2026-07-31T00:00:00Z"
