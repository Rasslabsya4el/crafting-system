"""What the snapshot script keeps of a start item's trade search under OR-8 (#718, #727): the last deep reading, or a thin or none record.

The script's network part is not run here; `remembered_starts` and `start_record` are its pure parts, worked by hand.
"""

import datetime
import importlib.util
from pathlib import Path

import pytest

from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.price_file import DeepReading, MarketRecord
from crafting_system.prices.trade_market import planned_price

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "price_snapshot.py"
NOW = datetime.datetime(2026, 11, 10, tzinfo=datetime.UTC)
DAY = datetime.date(2026, 11, 10)
BOOTS = "Sorcerer Boots, item level 86-100"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("price_snapshot", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quoted(chaos, listings, usable, league="Allflame", day="2026-10-31"):
    return PriceEntry(chaos, "trade-api", None, {"league": league, "date": day, "listings": listings, "usable": usable, "query": {"query": {}}})


def test_a_quoted_start_item_of_the_old_file_is_remembered_as_its_last_deep_reading(script):
    old = PriceFile("Allflame", NOW, 400.0, {BOOTS: quoted(4.0, 22, 20), "Thin one": quoted(9.0, 6, 6), "Ninja line": PriceEntry(1.0, "poe.ninja")})

    deep = script.remembered_starts(old, "Allflame")

    assert deep == {BOOTS: DeepReading(4.0, "Allflame", datetime.date(2026, 10, 31), 22, 20)}  # six listings is not deep; a poe.ninja line is no trade reading
    assert script.remembered_starts(old, "Keepers") == {}  # another league's reading is never this one's


def test_a_thin_search_today_leaves_a_thin_record_with_its_mean_plus_what_the_plan_adds(script):
    """Three priced listings of 7 on the site: (2 + 3 + 4) / 3 = 3 c, plus one Orb of Alchemy of 0.25 c for a composite."""
    record, reading = script.start_record("thin", [2.0, 3.0, 4.0], 7, {"q": 1}, "h", "Allflame", DAY, 0.25)

    assert reading is None
    assert record == MarketRecord("thin", "Allflame", DAY, 7, 3, "h", {"q": 1}, 3.25, 3)


def test_a_search_with_no_listing_is_a_none_record_and_a_quoted_one_a_deep_reading(script):
    none, _ = script.start_record("none", [], 0, {}, "h", "Allflame", DAY)
    _, deep = script.start_record("quoted", [1.0, 2.0, 3.0, 4.0, 5.0, 60.0], 30, {}, "h", "Allflame", DAY, 0.25)

    assert (none.state, none.chaos, none.used) == ("none", None, 0)
    assert deep == DeepReading(3.25, "Allflame", DAY, 30, 6)  # (1 + 2 + 3 + 4 + 5) / 5 + 0.25


def test_the_planner_reads_a_thin_start_item_as_its_old_price_marked_with_its_day(script):
    """The old file's 4 c of 2026-10-31 and today's thin record: the plan buys at 4 c, marked old (OR-8), not at today's thin mean."""
    old = PriceFile("Allflame", NOW, 400.0, {BOOTS: quoted(4.0, 22, 20)})
    record, _ = script.start_record("thin", [50.0, 60.0, 70.0], 5, {}, "h", "Allflame", DAY)
    new = PriceFile("Allflame", NOW, 400.0, {}, {BOOTS: record}, deep=script.remembered_starts(old, "Allflame"))

    planned = planned_price(new, BOOTS)

    assert planned.chaos == 4.0 and planned.mark == "old price, read on 2026-10-31, the market has few offers now"
