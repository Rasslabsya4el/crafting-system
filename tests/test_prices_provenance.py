"""Where a price came from, as data (#616): the record, its JSON, what a fetch writes into it, and the rule that reads it.

A price is a plain fact only when it is today's league, of the exact item, and deep enough for what the plan buys; any other price is an
approximate input with its reason (OR-12, OR-23). The numbers below are made up or read from the recorded poe.ninja answers; the case of the
Prismatic Fossil (#616: 0.2 Chaos in the snapshot, 8 Chaos a week later on 26.67 Chaos of volume) is written out as arithmetic.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ninja_support import ninja, ninja_fixture  # noqa: F401  (ninja is a fixture)

from crafting_system.prices import PriceEntry, PriceFile, load_price_file, write_price_file
from crafting_system.prices.fetch import fetch_price_file
from crafting_system.prices.poe_ninja import parse_overview
from crafting_system.prices.price_marks import DEPTH, EARLIER, NO_DEPTH, NOT_RECORDED, NOT_RECORDED_WORDS, OLD, OTHER_LEAGUE, STAND_IN, TRADE_UNREAD, price_marks, units_text
from crafting_system.prices.provenance import (
    EXCHANGE,
    HISTORY,
    OVERRIDE,
    PREVIOUS_LEAGUE,
    TRADE,
    WIDER,
    Provenance,
    derive,
    from_json,
    to_json,
)

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
FILE = PriceFile("Allflame", NOW, 400.0, {})


def entry(chaos=5.87, provenance=None, source="poe.ninja", detail=None):
    return PriceEntry(chaos, source, None, detail, provenance)


def codes(marks):
    return [mark.code for mark in marks]


# --- the record ------------------------------------------------------------------------------------------------------


def test_a_provenance_writes_to_json_and_reads_back_equal():
    p = Provenance(TRADE, "Allflame", "2026-11-07", 5.0, "units", 5, WIDER, "a Hunter bow of any rarity", 2, 744.4, {"kind": "ninja-exchange", "chaos": 3.0, "depth": 1.5})

    assert from_json(json.loads(json.dumps(to_json(p))), "x") == p


def test_a_default_field_is_left_out_of_the_json():
    assert to_json(Provenance(EXCHANGE, "Allflame", "2026-11-07")) == {"kind": "ninja-exchange", "league": "Allflame", "date": "2026-11-07"}


@pytest.mark.parametrize(
    "raw",
    [
        {"kind": "made-up", "league": "L", "date": "2026-11-07"},
        {"kind": "trade", "league": "", "date": "2026-11-07"},
        {"kind": "trade", "league": "L", "date": "2026-11-07", "depth": -1},
        {"kind": "trade", "league": "L", "date": "2026-11-07", "listings": 2.5},
        {"kind": "trade", "league": "L", "date": "2026-11-07", "item": "bigger"},
        {"kind": "trade", "league": "L", "date": "2026-11-07", "surprise": 1},
        "not an object",
    ],
)
def test_a_bad_provenance_is_refused_with_the_place_named(raw):
    with pytest.raises(ValueError, match="where: "):
        from_json(raw, "where")


def test_a_price_file_keeps_the_provenance_of_each_entry(tmp_path):
    p = Provenance(EXCHANGE, "Allflame", "2026-11-07", 34.6)
    file = PriceFile("Allflame", NOW, 400.0, {"Prismatic Fossil": entry(provenance=p), "Chaos Orb": PriceEntry(1.0, "poe.ninja")})
    path = tmp_path / "prices.json"

    write_price_file(path, file)
    back = load_price_file(path)

    assert back.prices["Prismatic Fossil"].provenance == p
    assert back.prices["Chaos Orb"].provenance is None
    assert "provenance" not in json.loads(path.read_text(encoding="utf-8"))["prices"]["Chaos Orb"]


def test_an_entry_with_no_provenance_is_read_from_its_source_and_detail_and_is_not_recorded():
    p = derive("poe.ninja-previous-league", {"league": "Mirage", "date": "2026-06-13"}, "Allflame", "2026-11-07")

    assert (p.kind, p.league, p.date, p.recorded) == (PREVIOUS_LEAGUE, "Mirage", "2026-06-13", False)
    assert derive("made-up", None, "Allflame", "2026-11-07") is None
    assert derive("hand", None, "Allflame", "2026-11-07").kind == OVERRIDE


# --- what a fetch writes ---------------------------------------------------------------------------------------------


def test_an_exchange_line_keeps_its_traded_units(ninja):
    line = next(l for l in parse_overview(ninja_fixture("overview_fossil")).lines if l.name == "Bound Fossil")

    assert (line.chaos, line.volume) == (9.03, 236.2)


def test_a_fetched_exchange_price_carries_the_units_traded_on_the_day_its_league_and_its_date(ninja):
    result = fetch_price_file(ninja, NOW)

    got = result.price_file.prices["Bound Fossil"].provenance

    assert (got.kind, got.league, got.date, got.item) == (EXCHANGE, result.price_file.league, "2026-11-07", "exact")
    assert got.depth == pytest.approx(236.2 / 9.03)


# --- the rule --------------------------------------------------------------------------------------------------------


def test_a_deep_exact_price_of_this_league_is_a_plain_fact():
    p = Provenance(EXCHANGE, "Allflame", "2026-11-07", 100.0)

    assert price_marks(entry(provenance=p), FILE, uses=45.0) == ()


def test_a_price_on_fewer_units_than_the_plan_buys_is_marked_with_the_units():
    """#616: the Prismatic Fossil, 26.67 Chaos of volume at 8 Chaos, is 3.3 units; R08 buys it about 45 times."""
    p = Provenance(EXCHANGE, "Allflame", "2026-11-07", 26.67 / 8)

    marks = price_marks(entry(8.0, p), FILE, uses=45.0)

    assert codes(marks) == [DEPTH]
    assert marks[0].reason == "price on 3.3 units"


def test_the_same_price_is_a_plain_fact_for_a_plan_that_buys_fewer_units_than_stand_behind_it():
    p = Provenance(EXCHANGE, "Allflame", "2026-11-07", 3.3)

    assert price_marks(entry(8.0, p), FILE, uses=3.0) == ()
    assert codes(price_marks(entry(8.0, p), FILE, uses=3.5)) == [DEPTH]


def test_there_is_no_fixed_cut_a_price_on_a_single_unit_is_kept_and_marked_not_dropped():
    p = Provenance(EXCHANGE, "Allflame", "2026-11-07", 0.2)

    assert codes(price_marks(entry(1.0, p), FILE, uses=1_000_000.0)) == [DEPTH]
    assert price_marks(entry(1.0, p), FILE, uses=0.1) == ()


def test_an_unsolved_plan_buys_at_least_one_unit():
    assert codes(price_marks(entry(provenance=Provenance(EXCHANGE, "Allflame", "2026-11-07", 0.5)), FILE, uses=None)) == [DEPTH]
    assert price_marks(entry(provenance=Provenance(EXCHANGE, "Allflame", "2026-11-07", 1.0)), FILE, uses=None) == ()


def test_a_recorded_price_with_no_depth_is_marked_as_such():
    assert codes(price_marks(entry(provenance=Provenance(HISTORY, "Allflame", "2026-11-05")), FILE, uses=1.0)) == [NO_DEPTH]


def test_a_previous_leagues_price_is_marked_whatever_its_depth():
    p = Provenance(PREVIOUS_LEAGUE, "Mirage", "2026-06-13", 10_000.0)

    marks = price_marks(entry(0.3425, p, "poe.ninja-previous-league"), FILE, uses=1.0)

    assert codes(marks) == [EARLIER]
    assert marks[0].reason == "previous league's price (Mirage, 2026-06-13)"


def test_a_price_of_another_league_and_an_old_one_are_marked():
    assert codes(price_marks(entry(provenance=Provenance(EXCHANGE, "Mirage", "2026-11-07", 99.0)), FILE, uses=1.0)) == [OTHER_LEAGUE]
    assert codes(price_marks(entry(provenance=Provenance(EXCHANGE, "Allflame", "2026-10-20", 99.0)), FILE, uses=1.0)) == [OLD]
    assert price_marks(entry(provenance=Provenance(EXCHANGE, "Allflame", "2026-10-31", 99.0)), FILE, uses=1.0) == ()  # 7 days is still fresh


@pytest.mark.parametrize(
    ("listings", "price", "words"),
    [
        (2, 744.4, "price of a wider item; the exact item has 2 listings at 744 Chaos"),
        (1, 20.0, "price of a wider item; the exact item has 1 listing at 20 Chaos"),
        (0, None, "price of a wider item; the exact item has 0 listings"),
        (None, None, "price of a wider item; the exact item's listings were not read"),
    ],
)
def test_a_stand_in_for_a_wider_item_says_what_the_exact_item_has(listings, price, words):
    """#601: R14's start bow is 13 Chaos for a Hunter bow of any rarity; the exact Magic bow has 2 listings at 744.4 Chaos."""
    p = Provenance(TRADE, "Allflame", "2026-11-07", 5.0, "units", 5, WIDER, "a Hunter bow of any rarity", listings, price)

    marks = price_marks(entry(13.0, p, "trade-api"), FILE, uses=1.0)

    assert codes(marks) == [STAND_IN]
    assert marks[0].reason == words


def test_a_hand_price_and_a_default_are_not_approximate_inputs():
    assert price_marks(entry(provenance=Provenance(OVERRIDE, "Allflame", "2026-11-07")), FILE, uses=1e9) == ()
    assert price_marks(PriceEntry(0.0001, "default"), FILE, uses=1e9) == ()


def test_an_entry_with_no_provenance_is_an_approximate_input_never_a_plain_fact():
    """Nothing shows it is of today's league, of the exact item and deep enough (finding 6 of the checker): the reason says so, beside the previous league's if it is one."""
    assert [m.reason for m in price_marks(entry(0.2), FILE, uses=1e9)] == [NOT_RECORDED_WORDS]
    legacy = entry(0.3425, None, "poe.ninja-previous-league", {"league": "Mirage", "date": "2026-06-13"})
    assert codes(price_marks(legacy, FILE, uses=1.0)) == [EARLIER, NOT_RECORDED]
    assert codes(price_marks(entry(1.0, None, "made-up source"), FILE, uses=1.0)) == [NOT_RECORDED]


@pytest.mark.parametrize(("depth", "words"), [(0.0, "0"), (3.33, "3.3"), (3.0, "3"), (9.96, "10"), (10.4, "10"), (1546.0, "1,546")])
def test_units_are_said_with_one_decimal_below_ten(depth, words):
    assert units_text(depth) == words


def test_the_old_snapshot_reads_without_a_provenance_block_and_every_price_of_it_is_marked():
    """The Prismatic Fossil at 0.2 Chaos (2026-10-31) would have passed as a plain fact: it is marked as not recorded (it was 8 Chaos a week later, #616)."""
    path = Path(__file__).resolve().parent / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"

    old = load_price_file(path)

    assert all(e.provenance is None for e in old.prices.values())
    assert codes(price_marks(old.prices["Shrieking Essence of Fear"], old, uses=50.0)) == [EARLIER, NOT_RECORDED]
    prismatic = old.prices["Prismatic Fossil"]
    assert prismatic.chaos == 0.2
    assert [m.reason for m in price_marks(prismatic, old, uses=50.0)] == [NOT_RECORDED_WORDS]


def test_a_thin_price_whose_trade_offers_were_not_read_says_so_and_a_deep_enough_one_does_not():
    """A fetch that was blocked, or spent its request budget, marks the names it meant to read (finding 5): a plan that buys more than the price's depth prints it."""
    p = Provenance(EXCHANGE, "Allflame", "2026-11-07", 3.0, trade_unread="the trade site blocked the run")

    marks = price_marks(entry(0.2, p), FILE, uses=45.0)

    assert codes(marks) == [DEPTH, TRADE_UNREAD]
    assert [m.reason for m in marks] == ["price on 3 units", "the trade offers beside it were not read: the trade site blocked the run"]
    assert price_marks(entry(0.2, p), FILE, uses=2.0) == ()  # the plan buys less than the 3 units there are: a plain fact
