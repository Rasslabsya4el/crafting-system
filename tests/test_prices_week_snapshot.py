"""A price snapshot of a league as it stood on an earlier day, from poe.ninja's daily exchange rows (#838).

The owner's decision of 2026-11-13: the tests and benchmarks read the 3.29 league (Allflame) about one week in, not its end. Every
number below is made up and worked by hand: a rate of 2.5 Chaos on 1,000 Chaos of volume is 400 units traded on the day; Allflame
started on 2026-07-24, so 2026-07-31 is league day 7; from 2026-07-31 to 2026-11-10 is 31 + 30 + 31 + 10 = 102 days.
"""

import importlib.util
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from crafting_system.prices import PriceEntry, PriceFile, load_price_file, write_price_file
from crafting_system.prices.http_json import SourceError
from crafting_system.prices.ninja_history import StashDay, exchange_readings, exchange_rows, stash_readings
from crafting_system.prices.price_marks import DEPTH, EARLIER, LATER, NO_DEPTH, OLD, OLD_THIN, price_marks
from crafting_system.prices.provenance import EXCHANGE, HISTORY, PREVIOUS_LEAGUE, STASH, TRADE, Provenance
from crafting_system.prices.week_snapshot import DayRow, build_snapshot, reading_on, wants_history

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "week_snapshot.py"
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
        " the reading of 2026-11-10 from routes-allflame-2026-11-10.json is kept: no other fossil name was priced on both days, so it is not scaled"
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


def test_a_bulk_stand_in_is_divided_by_the_median_rise_of_its_kind_and_a_start_item_is_not():
    """#860. Essences A, B, C rose x4, x2, x10 from the day to the template's (12/3, 10/5, 30/3): their median is 4, so D, read only at
    the end at 9 Chaos, stands in at 9 / 4 = 2.25. The currency names rose x3 (Divine 600/200) and x2 (Exalted 4/2): median 2.5, so the
    Lock's 1,000 stands in at 400. A fossil has no fossil read on both days, so it is kept; the trade start item is kept whole."""
    def ninja(chaos):
        return PriceEntry(chaos, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", "2026-11-10", 50.0))

    end = PriceFile("Allflame", END, 600.0, {
        "Divine Orb": ninja(600.0), "Exalted Orb": ninja(4.0), "Hinekora's Lock": ninja(1000.0),
        "Essence of A": ninja(12.0), "Essence of B": ninja(10.0), "Essence of C": ninja(30.0), "Essence of D": ninja(9.0),
        "Dense Fossil": ninja(7.0), RING: end_file().prices[RING],
    })  # fmt: skip
    rows = {"divine-orb": 200.0, "exalted-orb": 2.0, "essence-of-a": 3.0, "essence-of-b": 5.0, "essence-of-c": 3.0}

    snapshot, notes = build_snapshot([("end.json", end)], lambda league, slug: [DayRow(AS_OF, rows[slug], 100.0)] if slug in rows else [], "Allflame", START, AS_OF, None)

    assert snapshot.prices["Essence of D"].chaos == pytest.approx(2.25)
    assert snapshot.prices["Essence of D"].note == (
        "stand-in (OR-7, OR-23): no poe.ninja daily row in Allflame from 2026-07-25 to 2026-07-31; the reading of 2026-11-10 from end.json (9 Chaos)"
        " divided by 4, the median rise of the 3 essence names priced on both days"
    )
    assert snapshot.prices["Hinekora's Lock"].chaos == pytest.approx(400.0)
    assert snapshot.prices["Dense Fossil"].chaos == 7.0
    assert snapshot.prices[RING].chaos == 2.2
    d = snapshot.prices["Essence of D"]
    assert d.provenance == Provenance(EXCHANGE, "Allflame", "2026-11-10")  # its day kept, the reading's depth gone
    assert d.detail == {
        "league": "Allflame", "date": "2026-11-10", "reading_chaos": 9.0, "template": "end.json", "divided_by": 4.0, "sample": 3, "group": "essence",
    }  # `league` and `date` as every reading's detail has them: the readers of a trade price's day find it (#838)
    assert [mark.code for mark in price_marks(d, snapshot, uses=1.0)] == [LATER, NO_DEPTH]
    assert "Essence of D: stand-in, the reading of 2026-11-10 from end.json, divided by 4" in notes


def test_a_scaled_trade_stand_in_keeps_its_source_and_the_day_it_was_read():
    """The low essences are bulk names the 2026-11-10 file priced from the trade site (26 of them): scaled, each is still that day's
    trade reading in its detail, so the age rule (`test_price_age_rule.py`) reads its day. Essence B rose x3 (6/2), so 900 stands in at 300."""
    muttering = PriceEntry(900.0, "trade-api", "mean of the 5 cheapest", {"league": "Allflame", "date": "2026-11-10", "exchange": "muttering-essence-of-fear"}, Provenance(TRADE, "Allflame", "2026-11-10", 2.0))
    end = PriceFile("Allflame", END, 600.0, {"Divine Orb": PriceEntry(600.0, "poe.ninja"), "Essence of B": PriceEntry(6.0, "poe.ninja"), "Muttering Essence of Fear": muttering})
    rows = {"divine-orb": 200.0, "essence-of-b": 2.0}
    snapshot, _ = build_snapshot([("end.json", end)], lambda league, slug: [DayRow(AS_OF, rows[slug], 10.0)] if slug in rows else [], "Allflame", START, AS_OF, None)
    scaled = snapshot.prices["Muttering Essence of Fear"]

    assert (scaled.chaos, scaled.source, scaled.detail["date"], scaled.detail["league"]) == (pytest.approx(300.0), "trade-api", "2026-11-10", "Allflame")


def test_a_scaled_reading_with_no_recorded_day_has_no_date_and_the_league_of_its_template():
    """An entry with no provenance and no detail: its note says "the day of" its template, but its detail gets no `date`, which a
    reader would parse; its league is its template's (Mirage here), not the snapshot's."""
    old = PriceFile("Mirage", END, 600.0, {"Divine Orb": PriceEntry(600.0, "poe.ninja"), "Essence of B": PriceEntry(6.0, "poe.ninja"), "Essence of D": PriceEntry(9.0, "poe.ninja")})
    rows = {"divine-orb": 200.0, "essence-of-b": 2.0}
    snapshot, _ = build_snapshot([("old.json", old)], lambda league, slug: [DayRow(AS_OF, rows[slug], 10.0)] if slug in rows else [], "Allflame", START, AS_OF, None)
    d = snapshot.prices["Essence of D"]

    assert d.chaos == pytest.approx(3.0) and "date" not in d.detail and d.detail["league"] == "Mirage"


def test_a_previous_leagues_reading_and_a_zero_price_stay_out_of_the_sample():
    """Essence A is read only from Mirage (its rise would be 12/1 = 12) and essence Z is priced 0 at the end: neither counts, so the
    sample is B alone (10/5 = 2) and D stands in at 9 / 2 = 4.5."""
    end = PriceFile("Allflame", END, 600.0, {
        "Divine Orb": PriceEntry(600.0, "poe.ninja"), "Essence of A": PriceEntry(12.0, "poe.ninja"), "Essence of B": PriceEntry(10.0, "poe.ninja"),
        "Essence of Z": PriceEntry(0.0, "poe.ninja"), "Essence of D": PriceEntry(9.0, "poe.ninja"),
    })  # fmt: skip
    rows = {("Allflame", "divine-orb"): 200.0, ("Mirage", "essence-of-a"): 1.0, ("Allflame", "essence-of-b"): 5.0, ("Allflame", "essence-of-z"): 1.0}

    snapshot, _ = build_snapshot([("end.json", end)], lambda league, slug: [DayRow(AS_OF if league == "Allflame" else date(2026, 3, 13), rows[league, slug], 10.0)] if (league, slug) in rows else [], "Allflame", START, AS_OF, MIRAGE)

    assert snapshot.prices["Essence of A"].source == "poe.ninja-previous-league"
    assert snapshot.prices["Essence of D"].chaos == pytest.approx(4.5)
    assert snapshot.prices["Essence of D"].detail["sample"] == 1


def test_a_stash_line_and_a_hand_price_are_kept_and_never_read_from_the_rows():
    end = end_file()
    belt = PriceEntry(7.5, "poe.ninja", None, {"category": "BaseType"}, Provenance(STASH, "Allflame", "2026-11-10", 26.0, "observations"))
    unrecorded_belt = PriceEntry(6.0, "poe.ninja", None, {"category": "BaseType"})
    hand = PriceEntry(50.0, "hand")
    end.prices.update({"Leather Belt (ilvl 86)": belt, "Leather Belt (ilvl 85)": unrecorded_belt, "Exalted Orb": hand})
    snapshot, _ = build_snapshot([("t.json", end)], rows_of, "Allflame", START, AS_OF, None)

    assert snapshot.prices["Leather Belt (ilvl 86)"].note == "stand-in (OR-7): poe.ninja keeps no daily rows of a stash line of a finished league; the reading of 2026-11-10 from t.json is kept"
    assert snapshot.prices["Leather Belt (ilvl 85)"].chaos == 6.0
    assert snapshot.prices["Exalted Orb"].chaos == 50.0  # the rows hold 2.5 for it: a hand price is the user's own
    assert price_marks(snapshot.prices["Exalted Orb"], snapshot, uses=1.0) == ()
    assert not wants_history(hand) and not wants_history(unrecorded_belt)


def test_an_old_price_kept_from_a_later_day_says_its_day_once():
    file = PriceFile("Allflame", datetime(2026, 7, 31, tzinfo=UTC), 176.6)
    old = Provenance(TRADE, "Allflame", "2026-11-01", None, "units", None, market="old", book=2)

    assert [mark.code for mark in price_marks(PriceEntry(9.0, "trade-api", None, None, old), file, uses=1.0)] == [OLD_THIN]


def test_a_snapshot_with_no_divine_row_on_the_day_or_of_a_day_before_the_league_is_refused():
    with pytest.raises(ValueError, match="Divine Orb"):
        build_snapshot([("t.json", end_file())], lambda league, slug: [], "Allflame", START, AS_OF, None)
    with pytest.raises(ValueError, match="before Allflame's first day"):
        build_snapshot([("t.json", end_file())], rows_of, "Allflame", AS_OF, START, None)


# --- the script's cache -------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("week_snapshot_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_cache_keeps_an_answer_and_a_404_and_stops_on_any_other_failure(script, tmp_path):
    asked = []

    def get(url):
        asked.append(url)
        if url == "missing":
            raise SourceError("HTTP 404 from missing")
        if url == "limited":
            raise SourceError("HTTP 429 from limited")
        return {"pairs": []}

    get_json = script.cached(get, tmp_path)
    assert get_json("found") == {"pairs": []} and get_json("found") == {"pairs": []}
    for _ in range(2):
        with pytest.raises(SourceError, match="404"):
            get_json("missing")
    with pytest.raises(script.Stopped, match="429"):
        get_json("limited")
    assert asked == ["found", "missing", "limited"]  # each cached answer asked once; a failure other than 404 is not kept
    assert sorted(path.suffix for path in tmp_path.iterdir()) == [".json", ".json"]


def test_an_unreadable_cached_answer_is_asked_again(script, tmp_path):
    get_json = script.cached(lambda url: {"ok": 1}, tmp_path)
    get_json("u")
    (cached_file,) = tmp_path.iterdir()
    cached_file.write_text('{"cut', encoding="utf-8")

    assert get_json("u") == {"ok": 1}


def test_the_snapshot_writes_and_reads_back_in_the_format_of_the_others(tmp_path):
    snapshot, _ = build()
    path = tmp_path / "routes-allflame-2026-07-31.json"

    write_price_file(path, snapshot)

    assert load_price_file(path) == snapshot
    assert json.loads(path.read_text(encoding="utf-8"))["fetched_at"] == "2026-07-31T00:00:00Z"


# --- wanted names and the upgrade recipe (#885) -------------------------------------------------------------------


def test_a_wanted_name_no_template_holds_is_read_from_the_rows_and_one_with_no_row_gets_no_price_and_a_note():
    """What a method spends is priced whether or not an earlier snapshot held it: Allflame's row of the day, else Mirage's of the same
    league age (marked); a name neither league has a row for has no reading to stand in, so it stays unpriced and the notes say so."""
    rows = {
        **ROWS,
        ("Allflame", "awakeners-orb"): [DayRow(AS_OF, 300.0, 6000.0)],
        ("Mirage", "orb-of-conflict"): [DayRow(date(2026, 3, 13), 40.0, 400.0)],
    }

    snapshot, notes = build_snapshot(
        [("routes-allflame-2026-11-10.json", end_file())], lambda league, slug: rows.get((league, slug), []), "Allflame", START, AS_OF, MIRAGE,
        wanted=["Awakener's Orb", "Orb of Conflict", "Wild Bristle Matron", "Exalted Orb", "Chaos Orb", "Awakener's Orb"],
    )  # fmt: skip

    awakener, conflict = snapshot.prices["Awakener's Orb"], snapshot.prices["Orb of Conflict"]
    assert (awakener.chaos, awakener.source, awakener.provenance) == (300.0, "poe.ninja-history", Provenance(HISTORY, "Allflame", "2026-07-31", 20.0))
    assert (conflict.chaos, conflict.source, conflict.provenance) == (40.0, "poe.ninja-previous-league", Provenance(PREVIOUS_LEAGUE, "Mirage", "2026-03-13", 10.0))
    assert "Wild Bristle Matron" not in snapshot.prices
    assert snapshot.prices["Exalted Orb"].chaos == 2.5 and snapshot.prices["Chaos Orb"] == PriceEntry(1.0, "poe.ninja")  # a template's name is read once
    assert notes[-1] == (
        "Wild Bristle Matron: no price, no poe.ninja daily row in Allflame from 2026-07-25 to 2026-07-31 nor in Mirage from 2026-03-07 to 2026-03-13"
        " and no template holds it"
    )
    assert sum(": no price, " in note for note in notes) == 1


def test_the_lower_essence_tiers_of_a_snapshot_are_a_third_of_the_next_tier_up_not_stand_ins():
    """Deafening Essence of Fear traded at 2.7 on the day. Shrieking has no row: its reading of the league's end (4.0) would stand in at
    4.0 / 3 (the essences rose x3: 8.1 / 2.7), but the recipe prices it at 2.7 / 3 = 0.9, and the wanted Screaming tier at 0.3."""
    end = PriceFile(
        "Allflame", END, 516.2,
        {
            "Divine Orb": PriceEntry(516.2, "poe.ninja"),
            "Deafening Essence of Fear": PriceEntry(8.1, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", "2026-11-10", 50.0)),
            "Shrieking Essence of Fear": PriceEntry(4.0, "trade-api", None, {"exchange": "shrieking-essence-of-fear"}, Provenance(TRADE, "Allflame", "2026-11-10", 2.0)),
            "Essence of Horror": PriceEntry(90.0, "trade-api", None, {"exchange": "essence-of-horror"}, Provenance(TRADE, "Allflame", "2026-11-10", 2.0)),
        },
    )  # fmt: skip
    rows = {("Allflame", "divine-orb"): [DayRow(AS_OF, 176.6, 1766.0)], ("Allflame", "deafening-essence-of-fear"): [DayRow(AS_OF, 2.7, 270.0)]}

    snapshot, notes = build_snapshot([("end.json", end)], lambda league, slug: rows.get((league, slug), []), "Allflame", START, AS_OF, None, wanted=["Screaming Essence of Fear"])

    shrieking, screaming = snapshot.prices["Shrieking Essence of Fear"], snapshot.prices["Screaming Essence of Fear"]
    assert (shrieking.chaos, shrieking.source) == (pytest.approx(0.9), "upgrade-recipe")
    assert shrieking.detail["replaced"] == {"chaos": pytest.approx(4.0 / 3), "source": "trade-api"}
    assert (screaming.chaos, screaming.source, screaming.detail["of"]) == (pytest.approx(0.3), "upgrade-recipe", "Shrieking Essence of Fear")
    assert [mark.code for mark in price_marks(shrieking, snapshot, 1.0)] == ["upgrade-recipe"]
    assert snapshot.prices["Essence of Horror"].chaos == pytest.approx(30.0)  # no tier: it stays the scaled stand-in it was
    assert notes == [
        "Essence of Horror: stand-in, the reading of 2026-11-10 from end.json, divided by 3",
        "Shrieking Essence of Fear: vendor recipe, 0.9 Chaos, one third of Deafening Essence of Fear; before: 1.333 Chaos (trade-api)",
        "Screaming Essence of Fear: vendor recipe, 0.3 Chaos, one third of Shrieking Essence of Fear; before: no row",
    ]


def test_a_templates_recipe_row_is_read_from_the_rows_again():
    recipe_row = PriceEntry(0.9, "upgrade-recipe", None, {"of": "Deafening Essence of Fear"}, Provenance("upgrade-recipe", "Allflame", "2026-11-10"))

    assert wants_history(recipe_row)


def test_a_templates_recipe_row_does_not_count_in_the_rise_of_its_kind():
    """A template built under the rule holds Shrieking Essence of Fear as a recipe row (2.7, a third of 8.1), which also traded on the
    day at 3.0. Only Deafening counts as a market reading of both days (8.1 / 2.7 = x3): Essence of Horror stands in at 90 / 3 = 30."""
    end = PriceFile(
        "Allflame", END, 516.2,
        {
            "Divine Orb": PriceEntry(516.2, "poe.ninja"),
            "Deafening Essence of Fear": PriceEntry(8.1, "poe.ninja", None, None, Provenance(EXCHANGE, "Allflame", "2026-11-10", 50.0)),
            "Shrieking Essence of Fear": PriceEntry(2.7, "upgrade-recipe", None, {"of": "Deafening Essence of Fear"}, Provenance("upgrade-recipe", "Allflame", "2026-11-10")),
            "Essence of Horror": PriceEntry(90.0, "trade-api", None, {"exchange": "essence-of-horror"}, Provenance(TRADE, "Allflame", "2026-11-10", 2.0)),
        },
    )  # fmt: skip
    rows = {
        ("Allflame", "divine-orb"): [DayRow(AS_OF, 176.6, 1766.0)],
        ("Allflame", "deafening-essence-of-fear"): [DayRow(AS_OF, 2.7, 270.0)],
        ("Allflame", "shrieking-essence-of-fear"): [DayRow(AS_OF, 3.0, 30.0)],
    }

    snapshot, _ = build_snapshot([("end.json", end)], lambda league, slug: rows.get((league, slug), []), "Allflame", START, AS_OF, None)

    assert snapshot.prices["Essence of Horror"].chaos == pytest.approx(30.0)
    assert snapshot.prices["Essence of Horror"].detail["sample"] == 1
    assert snapshot.prices["Shrieking Essence of Fear"].chaos == pytest.approx(0.9)  # its own row of the day (3.0) does not win


# --- beasts: the daily rows of a stash line (#885) ------------------------------------------------------------------


def stash_days(*rows):
    """A stash `history` answer: (daysAgo, value, count) rows."""
    return [{"daysAgo": ago, "value": value, "count": count} for ago, value, count in rows]


def test_a_stash_reading_keeps_the_count_beside_the_value_and_dates_it_from_the_last_day_of_data():
    """Allflame's data ends on 2026-11-11 (`daysAgo` 0), so 2026-07-31 is 103 days before it; a day with fewer than 5 listings is no reading."""
    end = date(2026, 11, 11)
    data = stash_days((103, 45.0, 121), (104, 40.0, 4), (0, 362.0, 194))

    assert stash_readings(data, end, date(2026, 7, 25), AS_OF) == [StashDay(AS_OF, 45.0, 121)]
    assert stash_readings(data, end, date(2000, 1, 1), date(2100, 1, 1)) == [StashDay(AS_OF, 45.0, 121), StashDay(end, 362.0, 194)]
    assert stash_readings({"not": "a list"}, end, date(2026, 7, 25), AS_OF) == []


BEASTS = {
    ("Allflame", "Wild Bristle Matron"): [StashDay(AS_OF, 45.0, 121), StashDay(date(2026, 11, 11), 362.0, 194)],
    ("Allflame", "Farric Wolf Alpha"): [StashDay(date(2026, 7, 28), 3.0, 40)],
    ("Mirage", "Farrul, First of the Plains"): [StashDay(date(2026, 3, 13), 900.0, 12)],
    ("Allflame", "Exalted Orb"): [StashDay(AS_OF, 999.0, 50)],  # never read: the exchange prices the name first
}


def beast_rows_of(league, name):
    return BEASTS.get((league, name), [])


def test_a_beast_is_its_stash_lines_value_on_the_day_with_the_listings_seen_as_its_depth():
    snapshot, notes = build_snapshot(
        [("routes-allflame-2026-11-10.json", end_file())], rows_of, "Allflame", START, AS_OF, MIRAGE,
        wanted=["Wild Bristle Matron", "Farric Wolf Alpha", "Farrul, First of the Plains", "The Black Mórrígan"], beast_rows_of=beast_rows_of,
    )  # fmt: skip

    matron, wolf, farrul = snapshot.prices["Wild Bristle Matron"], snapshot.prices["Farric Wolf Alpha"], snapshot.prices["Farrul, First of the Plains"]
    assert (matron.chaos, matron.source, matron.provenance) == (45.0, "poe.ninja-history", Provenance(HISTORY, "Allflame", "2026-07-31", 121.0, "observations"))
    assert matron.detail == {"league": "Allflame", "date": "2026-07-31", "category": "Beast", "as_of": "2026-07-31", "league_day": 7}
    assert matron.note == "poe.ninja daily value of the beast on 2026-07-31 (league day 7), 121 listings seen that day"
    assert (wolf.chaos, wolf.provenance.date) == (3.0, "2026-07-28")
    assert wolf.note == "poe.ninja daily value of the beast on 2026-07-28 (league day 4), 40 listings seen that day; 2026-07-31 had no row of 5 listings or more"
    assert (farrul.chaos, farrul.source, farrul.provenance) == (900.0, "poe.ninja-previous-league", Provenance(PREVIOUS_LEAGUE, "Mirage", "2026-03-13", 12.0, "observations"))
    assert farrul.note == (
        "poe.ninja daily value of the beast on 2026-03-13 in Mirage (its league day 7, the same age), 12 listings seen that day:"
        " Allflame has no daily row from 2026-07-25 to 2026-07-31"
    )
    assert snapshot.prices["Exalted Orb"].chaos == 2.5
    assert "The Black Mórrígan" not in snapshot.prices and sum(": no price, " in note for note in notes) == 1
    assert [mark.reason for mark in price_marks(matron, snapshot, 200.0)] == ["price on 121 observations"] and price_marks(matron, snapshot, 100.0) == ()
    assert [mark.code for mark in price_marks(farrul, snapshot, 1.0)] == [EARLIER]


def test_a_templates_beast_is_read_from_its_stash_line_again_and_stays_a_stand_in_when_no_reader_is_given():
    end = end_file()
    end.prices["Wild Bristle Matron"] = PriceEntry(362.0, "poe.ninja", None, {"category": "Beast"}, Provenance(STASH, "Allflame", "2026-11-10", 194.0, "observations"))

    read, _ = build_snapshot([("t.json", end)], rows_of, "Allflame", START, AS_OF, MIRAGE, beast_rows_of=beast_rows_of)
    kept, notes = build_snapshot([("t.json", end)], rows_of, "Allflame", START, AS_OF, MIRAGE)

    assert read.prices["Wild Bristle Matron"].chaos == 45.0
    assert kept.prices["Wild Bristle Matron"].chaos == 362.0
    assert "Wild Bristle Matron: stand-in, the reading of 2026-11-10 from t.json" in notes


def test_the_scripts_beast_reader_asks_the_overview_once_and_the_history_of_a_listed_beast_only(script):
    asked = []
    overview = {"lines": [{"name": "Wild Bristle Matron", "chaosValue": 362.0, "count": 194, "id": 101094}]}

    def get(url):
        asked.append(url)
        if "item/overview" in url and "league=Allflame" in url:
            return overview
        if "item/history" in url and "id=101094" in url:
            return stash_days((103, 45.0, 121), (0, 362.0, 194))
        raise SourceError(f"HTTP 404 from {url}")

    rows = script.beast_reader(get, {"Allflame": date(2026, 11, 11), "Mirage": date(2026, 7, 20)})

    assert rows("Allflame", "Wild Bristle Matron") == [StashDay(AS_OF, 45.0, 121), StashDay(date(2026, 11, 11), 362.0, 194)]
    assert rows("Allflame", "Exalted Orb") == [] and rows("Allflame", "Wild Bristle Matron")[0].chaos == 45.0
    assert rows("Mirage", "Wild Bristle Matron") == [] and rows("Mirage", "Farric Wolf Alpha") == []  # its overview answers 404: asked once
    assert rows("Standard", "Wild Bristle Matron") == []  # a league with no last day given is not asked at all
    assert sum("item/overview" in url for url in asked) == 2 and sum("item/history" in url for url in asked) == 2
