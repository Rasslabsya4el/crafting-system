"""The age of a price does not depend on the day the suite runs (ticket #542, split from #473 point 9; OR-7).

The committed trade prices are dated 2026-10-31 and 2026-11-01 and the limit is 7 whole days (`MAX_AGE_DAYS`), so they are stale from
2026-11-07 and 2026-11-08. These tests pin the rule on both sides with the day written as an offset from the stored date, and pin the
test clock: every place that defaults to the real clock reads `clock_support.FIXED_NOW`.
"""

import importlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from clock_support import CLOCK_READERS, FIXED_DAY, FIXED_NOW
from cli_support import R12, price_file
from targets_support import DATA

from crafting_system.cli import main
from crafting_system.prices import TRADE_SOURCE, load_price_file
from crafting_system.prices.price_file import MAX_AGE_DAYS, stale_warning
from crafting_system.prices.trade_market import offer

FIXTURES = Path(__file__).parent / "fixtures" / "prices"
COMMITTED = sorted(FIXTURES.glob("*.json"))


def trade_entries(path: Path):
    """The trade-api prices of a committed price file with the day each was searched."""
    prices = load_price_file(path)
    return prices, [
        (name, date.fromisoformat(entry.detail["date"])) for name, entry in prices.prices.items() if entry.source == TRADE_SOURCE and entry.detail
    ]


@pytest.mark.parametrize("path", COMMITTED, ids=lambda path: path.name)
def test_a_committed_trade_price_is_offered_on_the_seventh_day_and_stale_on_the_eighth(path):
    prices, entries = trade_entries(path)
    for name, searched in entries:
        seventh = offer(prices, name, searched + timedelta(days=MAX_AGE_DAYS))
        eighth = offer(prices, name, searched + timedelta(days=MAX_AGE_DAYS + 1))
        assert seventh.state != "stale" and seventh.age_days == MAX_AGE_DAYS, name
        assert eighth.state == "stale" and eighth.age_days == MAX_AGE_DAYS + 1 and not eighth.offered, name


@pytest.mark.parametrize("path", COMMITTED, ids=lambda path: path.name)
def test_a_committed_price_file_warns_after_seven_days_and_not_before(path):
    prices = load_price_file(path)
    fetched = prices.fetched_at.astimezone(UTC).date()

    assert stale_warning(prices, fetched + timedelta(days=MAX_AGE_DAYS)) is None
    assert f"{MAX_AGE_DAYS + 1} days old" in stale_warning(prices, fetched + timedelta(days=MAX_AGE_DAYS + 1))


def test_the_two_route_price_files_hold_the_trade_prices_the_rule_is_pinned_on():
    dated = {name: {day for _, day in trade_entries(FIXTURES / name)[1]} for name in ("routes-allflame-2026-10-31.json", "vendor-v01-2026-11-01.json")}

    assert dated["routes-allflame-2026-10-31.json"] == {date(2026, 10, 31), date(2026, 11, 1)}
    assert dated["vendor-v01-2026-11-01.json"]


@pytest.mark.parametrize("name", CLOCK_READERS)
def test_every_place_that_defaults_to_the_real_clock_reads_the_fixed_one(name):
    module = importlib.import_module(name)

    assert module.datetime.now(UTC) == FIXED_NOW
    assert module.datetime.now(UTC).date() == FIXED_DAY
    assert isinstance(FIXED_NOW, datetime) and isinstance(module.datetime.now(UTC), datetime)


def test_the_command_without_a_given_day_judges_the_price_file_by_the_fixed_clock(tmp_path, capsys):
    fetched = price_file().fetched_at.astimezone(UTC).date()
    assert (FIXED_DAY - fetched).days <= MAX_AGE_DAYS  # the fixed day is within the limit of the file's own date

    code = main([str(R12), "--json", str(tmp_path / "policy.json")], data=DATA, prices=price_file(), env={})

    assert code == 0
    assert "days old" not in capsys.readouterr().err


def test_the_command_warns_when_the_given_day_is_past_the_limit(tmp_path, capsys):
    fetched = price_file().fetched_at.astimezone(UTC).date()

    main([str(R12), "--json", str(tmp_path / "policy.json")], data=DATA, prices=price_file(), env={}, today=fetched + timedelta(days=MAX_AGE_DAYS + 1))

    assert f"{MAX_AGE_DAYS + 1} days old" in capsys.readouterr().err
