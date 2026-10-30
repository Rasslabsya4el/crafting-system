"""The shared poe.ninja history readers: exchange and stash rows inside a date window, on recordings."""

from datetime import date

from ninja_support import ninja, ninja_fixture  # noqa: F401  (ninja is a fixture)

from crafting_system.prices.http_json import SourceError
from crafting_system.prices.ninja_history import (
    exchange_history,
    exchange_rows,
    stash_history,
    stash_rows,
    window_ending,
)

TODAY = date(2026, 10, 30)


def test_the_window_is_seven_days_ending_on_the_last_day():
    assert window_ending(TODAY) == (date(2026, 10, 24), TODAY)


def test_exchange_rows_keep_traded_days_inside_the_window():
    data = ninja_fixture("details_hollow_fossil")
    rows = exchange_rows(data, *window_ending(TODAY))

    assert rows
    assert all(date(2026, 10, 24) <= day <= TODAY for day, _ in rows)
    assert exchange_rows(data, date(2020, 1, 1), date(2020, 1, 7)) == []


def test_exchange_rows_of_the_wrong_shape_are_empty():
    for data in (None, [], {}, {"pairs": "x"}, {"pairs": [{"id": "chaos"}]}):
        assert exchange_rows(data, date(2026, 1, 1), TODAY) == []


def test_stash_rows_date_from_the_anchor_and_drop_thin_days():
    thin = ninja_fixture("stash_history_beast_167860")  # every count below 5
    assert stash_rows(thin, TODAY, *window_ending(TODAY)) == []

    rows = stash_rows(ninja_fixture("stash_history_basetype_34026"), TODAY, *window_ending(TODAY))
    assert len(rows) == 7
    assert rows[0][0] == TODAY and all(price > 0 for _, price in rows)


def test_stash_rows_of_a_finished_league_date_from_its_last_day():
    data = ninja_fixture("stash_history_basetype_34026_mirage")
    rows = stash_rows(data, date(2026, 7, 20), date(2026, 6, 6), date(2026, 6, 12))

    assert sorted(day for day, _ in rows) == [date(2026, 6, d) for d in range(6, 13)]


def test_a_history_that_fails_gives_no_rows():
    def failing(url):
        raise SourceError("HTTP 500")

    assert exchange_history(failing, "Allflame", "hollow-fossil", date(2026, 10, 24), TODAY) == []
    assert stash_history(failing, "Allflame", "BaseType", 1, TODAY, date(2026, 10, 24), TODAY) == []
