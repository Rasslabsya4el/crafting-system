"""A price snapshot of a league as it stood on an earlier day, from poe.ninja's daily exchange rows (#838).

The owner's decision of 2026-11-13: the tests and benchmarks read the 3.29 league about one week after its start, a stable early
economy, not the skewed prices of its end. A snapshot of a day is built from earlier snapshots (the templates: the names to price)
and poe.ninja's daily rows of each bulk name (`exchange/current/details`, kept for a finished league while the item stays in its
overview). For each name of the templates, in order:

1. A bulk name (currency, fossil, resonator, essence, oil: an entry that is neither a stored trade search nor a stash line) is its
   exchange rate on the day, or on the latest traded day of the week ending on it (`reading_on`), with the units traded that day
   as its depth, source `poe.ninja-history`. The file is dated on that day, so such a price is of the file's own day.
2. A bulk name the league has no row for (an item that left the overview before the league ended has no history any more) is read
   from the previous league at the same league age, the fetcher's own fallback (`previous_league`), marked as that league's price.
3. Anything else keeps the first template's reading as a stand-in (OR-7): a trade search and a stash line have no daily history
   of a finished league. Its provenance keeps its own day, which `price_marks` marks as a price of a later day than the file's.

The Chaos Orb is 1 and the Divine Orb's reading on the day is the file's `chaos_per_divine`. Pure: the rows come from `rows_of`.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from .fallbacks import HISTORY_DAYS
from .ninja_history import DayRow, window_ending
from .poe_ninja import HISTORY_SOURCE, history_slug
from .ninja_items import STASH_TYPES
from .previous_league import PREVIOUS_SOURCE
from .price_file import CHAOS_ORB, DIVINE_ORB, PriceEntry, PriceFile
from .provenance import EXCHANGE, HISTORY, KIND_OF_SOURCE, PREVIOUS_LEAGUE, STANDARD, STASH, TRADE, WATCH, Provenance

__all__ = ["DayRow", "build_snapshot", "reading_on", "wants_history"]

BULK_KINDS = (EXCHANGE, HISTORY, PREVIOUS_LEAGUE, STANDARD, WATCH, TRADE)  # a stash line (STASH) is told by its kind or its category

RowsOf = Callable[[str, str], Sequence[DayRow]]  # (league, poe.ninja details id) -> that item's traded days
Previous = tuple[str, date, date]  # the previous league, its first day, and its day of the same league age


def reading_on(rows: Sequence[DayRow], as_of: date, days: int = HISTORY_DAYS) -> DayRow | None:
    """The row of `as_of`, else the latest row of the `days` days ending on it; None when that week has none."""
    first, last = window_ending(as_of, days)
    inside = [row for row in rows if first <= row.day <= last]
    return max(inside, key=lambda row: row.day, default=None)


def wants_history(entry: PriceEntry) -> bool:
    """Whether a template entry is a bulk name the exchange rows can price: a market reading of a name (`BULK_KINDS`), not a
    stored trade search and not a stash line; a hand price or a default stays the user's and the model's own number."""
    detail = entry.detail or {}
    if isinstance(detail.get("query"), dict) or detail.get("category") in STASH_TYPES:
        return False
    kind = entry.provenance.kind if entry.provenance is not None else KIND_OF_SOURCE.get(entry.source)
    return kind in BULK_KINDS


def _units(row: DayRow) -> float:
    return row.volume / row.chaos


def _units_text(units: float) -> str:
    return f"{units:,.0f}" if units >= 10 else f"{units:.1f}"


def _window(as_of: date) -> str:
    first, last = window_ending(as_of)
    return f"from {first.isoformat()} to {last.isoformat()}"


def build_snapshot(
    templates: Sequence[tuple[str, PriceFile]],
    rows_of: RowsOf,
    league: str,
    start: date,
    as_of: date,
    previous: tuple[str, date] | None,
) -> tuple[PriceFile, list[str]]:
    """The snapshot of `league` on `as_of` (the module docstring) and one note per stand-in.

    `templates` are (label, file) pairs, the first of them first for a stand-in; `start` is the league's first day, so `as_of` is
    league day `(as_of - start).days`; `previous` is the previous league and its first day, or None to skip that step.
    """
    names: dict[str, tuple[str, PriceEntry]] = {}
    for label, template in templates:
        for name, entry in template.prices.items():
            names.setdefault(name, (label, entry))
    age = (as_of - start).days
    if age < 0:
        raise ValueError(f"the day of the snapshot, {as_of.isoformat()}, is before {league}'s first day, {start.isoformat()}")
    divine = reading_on(rows_of(league, history_slug(DIVINE_ORB)), as_of)
    if divine is None:
        raise ValueError(f"{league} has no Divine Orb row {_window(as_of)}: the snapshot has no Chaos per Divine")

    back = None if previous is None else (previous[0], previous[1], previous[1] + timedelta(days=age))
    prices: dict[str, PriceEntry] = {CHAOS_ORB: PriceEntry(1.0, "poe.ninja")}
    notes: list[str] = []
    for name, (label, entry) in names.items():
        if name == CHAOS_ORB:
            continue
        found = _read(name, rows_of, league, start, as_of, back) if wants_history(entry) else None
        if found is None:
            found = _stand_in(entry, label, league, as_of, back)
            notes.append(f"{name}: stand-in, the reading of {_day_of(entry, label)} from {label}")
        prices[name] = found
    return PriceFile(league, datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC), divine.chaos, prices), notes


def _read(name: str, rows_of: RowsOf, league: str, start: date, as_of: date, previous: Previous | None) -> PriceEntry | None:
    slug = history_slug(name)
    row = reading_on(rows_of(league, slug), as_of)
    if row is not None:
        note = f"poe.ninja daily exchange rate of {row.day.isoformat()} (league day {(row.day - start).days}), {_units_text(_units(row))} units traded that day"
        if row.day != as_of:
            note += f"; {as_of.isoformat()} had no traded row"
        detail = {"league": league, "date": row.day.isoformat(), "exchange": slug, "as_of": as_of.isoformat(), "league_day": (as_of - start).days}
        return PriceEntry(row.chaos, HISTORY_SOURCE, note, detail, Provenance(HISTORY, league, row.day.isoformat(), _units(row)))
    if previous is None:
        return None
    old, old_start, same_age = previous
    row = reading_on(rows_of(old, slug), same_age)
    if row is None:
        return None
    note = (
        f"poe.ninja daily exchange rate of {row.day.isoformat()} in {old} (its league day {(row.day - old_start).days}, the same age),"
        f" {_units_text(_units(row))} units traded that day: {league} has no daily row {_window(as_of)}"
    )
    detail = {"league": old, "date": row.day.isoformat(), "exchange": slug, "current_league": league, "age_days": (as_of - start).days}
    return PriceEntry(row.chaos, PREVIOUS_SOURCE, note, detail, Provenance(PREVIOUS_LEAGUE, old, row.day.isoformat(), _units(row)))


def _day_of(entry: PriceEntry, label: str) -> str:
    if entry.provenance is not None:
        return entry.provenance.date
    day = (entry.detail or {}).get("date")
    return day if isinstance(day, str) else f"the day of {label}"


def _stand_in(entry: PriceEntry, label: str, league: str, as_of: date, previous: Previous | None) -> PriceEntry:
    """The template's entry kept whole, its note saying why and from where (OR-7); its own day is in its provenance."""
    if isinstance((entry.detail or {}).get("query"), dict):
        why = "a trade search has no daily history"
    elif (entry.detail or {}).get("category") in STASH_TYPES or (entry.provenance is not None and entry.provenance.kind == STASH):
        why = "poe.ninja keeps no daily rows of a stash line of a finished league"
    elif not wants_history(entry):
        why = "a hand price or a default is no market reading"
    else:
        why = f"no poe.ninja daily row in {league} {_window(as_of)}"
        if previous is not None:
            old, _, same_age = previous
            why += f" nor in {old} {_window(same_age)}"
    note = f"stand-in (OR-7): {why}; the reading of {_day_of(entry, label)} from {label} is kept"
    if entry.note:
        note += f" ({entry.note})"
    return replace(entry, note=note)
