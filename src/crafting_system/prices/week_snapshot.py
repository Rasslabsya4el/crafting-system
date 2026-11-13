"""A price snapshot of a league as it stood on an earlier day, from poe.ninja's daily exchange rows (#838).

The owner's decision of 2026-11-13: the tests and benchmarks read the 3.29 league about one week after its start, a stable early
economy, not the skewed prices of its end. A snapshot of a day is built from earlier snapshots (the templates: the names to price)
and poe.ninja's daily rows of each bulk name (`exchange/current/details`, kept for a finished league while the item stays in its
overview). For each name of the templates, in order:

1. A bulk name (currency, fossil, resonator, essence, oil: an entry that is neither a stored trade search nor a stash line) is its
   exchange rate on the day, or on the latest traded day of the week ending on it (`reading_on`), with the units traded that day
   as its depth, source `poe.ninja-history`. The file is dated on that day, so such a price is of the file's own day.
   A **beast** has no exchange row: it is its stash line's value on the day (`beast_rows_of`, #885; poe.ninja keeps the daily rows
   of a finished league's beasts while its Beast overview lists them), with the listings poe.ninja saw that day as its depth, in
   observations. A day with fewer than 5 listings is no reading (`MIN_COUNT`, as in every stash reading). A base's stash line
   is not read this way yet: it stays a stand-in (step 3).
2. A bulk name the league has no row for (an item that left the overview before the league ended has no history any more) is read
   from the previous league at the same league age, the fetcher's own fallback (`previous_league`), marked as that league's price.
3. Anything else keeps the first template's reading as a stand-in (OR-7): a trade search and a stash line have no daily history
   of a finished league. Its provenance keeps its own day, which `price_marks` marks as a price of a later day than the file's.
   A bulk name's stand-in is divided by how far its kind of item (essences, fossils, resonators, oils, other currency) rose from
   the day to the template's: the median over the names of that kind priced on both days (#860, OR-23). Prices rise very unevenly
   over a league (Allflame, 2026-07-31 to 2026-11-10: essences x4.7, other currency x2.3, fossils x1.2, the Divine Orb x2.9), so
   no single rate such as the Divine Orb's fits them all. The sample is the names that traded on the day, and a stand-in is a
   name that did not: the rarer tiers of a kind may have moved otherwise, so the estimate is as good as the evidence and no
   better. A scaled stand-in keeps its reading's day (marked as a later day's) and no depth (marked as such), and its `detail`
   holds the reading, the divisor and the sample.

A **wanted** name (what a method spends, `spends.py`, #885) that no template holds is read by steps 1 and 2 only: with no template
reading there is nothing to stand in, so a name neither league has a row for gets no price and a note that says so. A hand-made
template is how such a name gets a marked stand-in.

Last, the lower essence tiers are priced from the vendor upgrade recipe (`essence_recipe.py`, #885): a third of the next tier up,
unless the tier's own row of the day is cheaper. It replaces the stand-ins and the previous league's rows of those tiers, and
gives a row to every wanted tier the file lacks.

The Chaos Orb is 1 and the Divine Orb's reading on the day is the file's `chaos_per_divine`. Pure: the rows come from `rows_of`.
"""

import statistics
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from .essence_recipe import RECIPE_SOURCE, apply_upgrade_recipe
from .fallbacks import HISTORY_DAYS, MIN_COUNT
from .ninja_history import DayRow, StashDay, window_ending
from .poe_ninja import HISTORY_SOURCE, history_slug
from .ninja_items import BEAST, STASH_TYPES
from .previous_league import PREVIOUS_SOURCE
from .price_file import CHAOS_ORB, DIVINE_ORB, PriceEntry, PriceFile
from .provenance import ESTIMATE, EXCHANGE, HISTORY, KIND_OF_SOURCE, OBSERVATIONS, PREVIOUS_LEAGUE, RECIPE, STANDARD, STASH, TRADE, WATCH, Provenance

__all__ = ["DayRow", "build_snapshot", "reading_on", "wants_history"]

GROUP_WORDS = (("Essence", "essence"), ("Fossil", "fossil"), ("Resonator", "resonator"), (" Oil", "oil"))
CURRENCY_GROUP = "currency"
# a stash line (STASH) is told by its kind or its category; a template's recipe row (RECIPE) is a bulk name too: its own rows are read again
BULK_KINDS = (EXCHANGE, HISTORY, PREVIOUS_LEAGUE, STANDARD, WATCH, TRADE, RECIPE)

RowsOf = Callable[[str, str], Sequence[DayRow]]  # (league, poe.ninja details id) -> that item's traded days
BeastRowsOf = Callable[[str, str], Sequence[StashDay]]  # (league, beast name) -> the days of its stash line; empty for a name that is no beast there
Previous = tuple[str, date, date]  # the previous league, its first day, and its day of the same league age


def reading_on[Row: (DayRow, StashDay)](rows: Sequence[Row], as_of: date, days: int = HISTORY_DAYS) -> Row | None:
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
    wanted: Sequence[str] = (),
    beast_rows_of: BeastRowsOf | None = None,
) -> tuple[PriceFile, list[str]]:
    """The snapshot of `league` on `as_of` (the module docstring) and its notes: one per stand-in ("<name>: stand-in, ..."), one per
    wanted name left without a price ("<name>: no price, ..."), one per row the upgrade recipe wrote ("<name>: vendor recipe, ...").

    `templates` are (label, file) pairs, the first of them first for a stand-in; `start` is the league's first day, so `as_of` is
    league day `(as_of - start).days`; `previous` is the previous league and its first day, or None to skip that step; `wanted`
    are names to price whether or not a template holds them; `beast_rows_of` gives the daily rows of a beast's stash line (None:
    no beast is read, and a template's beast stays a stand-in).
    """
    names: dict[str, tuple[str, PriceEntry]] = {}
    leagues = {label: template.league for label, template in templates}  # the league each template's readings are of
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
    prices: dict[str, PriceEntry | None] = {CHAOS_ORB: PriceEntry(1.0, "poe.ninja")}
    stand_ins: dict[str, str] = {}
    unpriced: list[str] = []
    left: list[str] = []
    for name, (label, entry) in names.items():
        if name == CHAOS_ORB:
            continue
        found = _read(name, rows_of, league, start, as_of, back, beast_rows_of) if wants_history(entry) or _is_beast(entry) else None
        if found is None:
            left.append(name)
        prices[name] = found  # a stand-in's place is kept; it is made below, from what was read on the day
    for name in left:
        label, entry = names[name]
        drift = _drift(name, label, names, prices) if wants_history(entry) else None
        prices[name] = _stand_in(entry, label, league, as_of, back, name, drift, leagues[label])
        stand_ins[name] = f"{name}: stand-in, the reading of {_day_of(entry, label)} from {label}" + ("" if drift is None or drift[1] == 0 else f", divided by {drift[0]:.4g}")
    for name in dict.fromkeys(wanted):
        if name in prices:
            continue
        found = _read(name, rows_of, league, start, as_of, back, beast_rows_of)
        if found is None:
            unpriced.append(name)
        else:
            prices[name] = found
    snapshot, recipe = apply_upgrade_recipe(PriceFile(league, datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC), divine.chaos, prices), wanted)
    notes = [note for name, note in stand_ins.items() if snapshot.prices[name] is prices[name]]  # a stand-in the recipe replaced is one no longer
    notes += [f"{name}: no price, no poe.ninja daily row in {league} {_window(as_of)}" + ("" if back is None else f" nor in {back[0]} {_window(back[2])}") + " and no template holds it" for name in unpriced if name not in snapshot.prices]
    notes += [note.replace(": ", ": vendor recipe, ", 1) for note in recipe]  # a row the rule wrote, or a type it kept as it is
    return snapshot, notes


def group_of(name: str) -> str:
    """The kind of bulk item a name is, by the word poe.ninja's overviews sort it by: its prices drift together over a league (#860)."""
    for word, group in GROUP_WORDS:
        if word in name:
            return group
    return CURRENCY_GROUP


def _drift(name: str, label: str, names: dict[str, tuple[str, PriceEntry]], prices: dict[str, PriceEntry | None]) -> tuple[float, int]:
    """How far the names of `name`'s kind moved from the snapshot's day to the day of `label`: the median of (the template's price /
    the day's), over the names of that kind the same template prices and the league's own rows priced on the day; and how many.
    (1.0, 0) when there is none: the stand-in is not scaled."""
    group = group_of(name)
    ratios = [
        entry.chaos / found.chaos
        for other, (other_label, entry) in names.items()
        if other_label == label and group_of(other) == group and (found := prices.get(other)) is not None and found.source == HISTORY_SOURCE and entry.chaos > 0
        and entry.source != RECIPE_SOURCE  # a template's recipe row is no market reading of its day: it says nothing of how far the market moved
        and not _is_beast(entry) and not _is_beast(found)  # a beast is no currency: its stash line moves with its own market (#885)
    ]
    return (statistics.median(ratios), len(ratios)) if ratios else (1.0, 0)


def _is_beast(entry: PriceEntry) -> bool:
    return (entry.detail or {}).get("category") == BEAST


def _read(
    name: str, rows_of: RowsOf, league: str, start: date, as_of: date, previous: Previous | None, beast_rows_of: BeastRowsOf | None = None
) -> PriceEntry | None:
    """The reading of `name` on the day: its exchange row or its stash line's row in the league, else the same in the previous league."""
    found = _read_exchange(name, rows_of, league, start, as_of, None)
    if found is None and beast_rows_of is not None:
        found = _read_beast(name, beast_rows_of, league, start, as_of, None)
    if found is None and previous is not None:
        found = _read_exchange(name, rows_of, league, start, as_of, previous)
    if found is None and previous is not None and beast_rows_of is not None:
        found = _read_beast(name, beast_rows_of, league, start, as_of, previous)
    return found


def _read_beast(name: str, beast_rows_of: BeastRowsOf, league: str, start: date, as_of: date, previous: Previous | None) -> PriceEntry | None:
    """The stash line of the beast `name` on the day in `league` (`previous` None), or in the previous league at the same league age."""
    if previous is None:
        row = reading_on(beast_rows_of(league, name), as_of)
        if row is None:
            return None
        note = f"poe.ninja daily value of the beast on {row.day.isoformat()} (league day {(row.day - start).days}), {row.count:,} listings seen that day"
        if row.day != as_of:
            note += f"; {as_of.isoformat()} had no row of {MIN_COUNT} listings or more"
        detail = {"league": league, "date": row.day.isoformat(), "category": BEAST, "as_of": as_of.isoformat(), "league_day": (as_of - start).days}
        return PriceEntry(row.chaos, HISTORY_SOURCE, note, detail, Provenance(HISTORY, league, row.day.isoformat(), float(row.count), OBSERVATIONS))
    old, old_start, same_age = previous
    row = reading_on(beast_rows_of(old, name), same_age)
    if row is None:
        return None
    note = (
        f"poe.ninja daily value of the beast on {row.day.isoformat()} in {old} (its league day {(row.day - old_start).days}, the same age),"
        f" {row.count:,} listings seen that day: {league} has no daily row {_window(as_of)}"
    )
    detail = {"league": old, "date": row.day.isoformat(), "category": BEAST, "current_league": league, "age_days": (as_of - start).days}
    return PriceEntry(row.chaos, PREVIOUS_SOURCE, note, detail, Provenance(PREVIOUS_LEAGUE, old, row.day.isoformat(), float(row.count), OBSERVATIONS))


def _read_exchange(name: str, rows_of: RowsOf, league: str, start: date, as_of: date, previous: Previous | None) -> PriceEntry | None:
    """The exchange row of `name` on the day in `league` (`previous` None), or in the previous league at the same league age."""
    slug = history_slug(name)
    if previous is None:
        return _league_row(name, slug, rows_of, league, start, as_of)
    return _previous_row(slug, rows_of, league, start, as_of, previous)


def _league_row(name: str, slug: str, rows_of: RowsOf, league: str, start: date, as_of: date) -> PriceEntry | None:
    row = reading_on(rows_of(league, slug), as_of)
    if row is not None:
        note = f"poe.ninja daily exchange rate of {row.day.isoformat()} (league day {(row.day - start).days}), {_units_text(_units(row))} units traded that day"
        if row.day != as_of:
            note += f"; {as_of.isoformat()} had no traded row"
        detail = {"league": league, "date": row.day.isoformat(), "exchange": slug, "as_of": as_of.isoformat(), "league_day": (as_of - start).days}
        return PriceEntry(row.chaos, HISTORY_SOURCE, note, detail, Provenance(HISTORY, league, row.day.isoformat(), _units(row)))
    return None


def _previous_row(slug: str, rows_of: RowsOf, league: str, start: date, as_of: date, previous: Previous) -> PriceEntry | None:
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


def _is_day(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _day_of(entry: PriceEntry, label: str) -> str:
    if entry.provenance is not None:
        return entry.provenance.date
    day = (entry.detail or {}).get("date")
    return day if isinstance(day, str) else f"the day of {label}"


def _stand_in(
    entry: PriceEntry, label: str, league: str, as_of: date, previous: Previous | None, name: str = "", drift: tuple[float, int] | None = None,
    template_league: str | None = None,
) -> PriceEntry:
    """The template's entry, its note saying why and from where (OR-7); its own day is in its provenance. A bulk name's price is
    divided by the drift of its kind (`_drift`, #860), the best estimate the evidence gives (OR-23); any other is kept whole."""
    if isinstance((entry.detail or {}).get("query"), dict):
        why = "a trade search has no daily history"
    elif entry.provenance is not None and entry.provenance.kind == ESTIMATE:
        why = "no market lists it, so an estimate stands in"
    elif _is_beast(entry):
        why = f"no daily row of the beast was read in {league} {_window(as_of)}" + ("" if previous is None else f" nor in {previous[0]} {_window(previous[2])}")
    elif (entry.detail or {}).get("category") in STASH_TYPES or (entry.provenance is not None and entry.provenance.kind == STASH):
        why = "the daily rows of a base's stash line are not read"
    elif not wants_history(entry):
        why = "a hand price or a default is no market reading"
    else:
        why = f"no poe.ninja daily row in {league} {_window(as_of)}"
        if previous is not None:
            old, _, same_age = previous
            why += f" nor in {old} {_window(same_age)}"
    day = _day_of(entry, label)
    if drift is None:
        note = f"stand-in (OR-7): {why}; the reading of {day} from {label} is kept"
    elif drift[1] == 0:
        note = f"stand-in (OR-7): {why}; the reading of {day} from {label} is kept: no other {group_of(name)} name was priced on both days, so it is not scaled"
    else:
        ratio, count = drift
        note = (
            f"stand-in (OR-7, OR-23): {why}; the reading of {day} from {label} ({entry.chaos:g} Chaos) divided by {ratio:.4g},"
            f" the median rise of the {count} {group_of(name)} {'name' if count == 1 else 'names'} priced on both days"
        )
    if drift is None or drift[1] == 0:
        if entry.note:
            note += f" ({entry.note})"
        return replace(entry, note=note)
    # an estimate, not the reading: the reading's own words, depth and counts no longer describe it, so they go and the
    # estimate is marked as a price with no recorded depth besides its later day (OR-23); `detail` keeps what it was made from
    ratio, count = drift
    reading_league = entry.provenance.league if entry.provenance is not None else (entry.detail or {}).get("league", template_league or league)
    detail = {"league": reading_league, "reading_chaos": entry.chaos, "template": label, "divided_by": ratio, "sample": count, "group": group_of(name)}
    if _is_day(day):  # a reading with no recorded day has none to give: never the words that stand in for it in the note
        detail = {"league": reading_league, "date": day, **{k: v for k, v in detail.items() if k != "league"}}
    kept = None if entry.provenance is None else Provenance(entry.provenance.kind, entry.provenance.league, entry.provenance.date)
    return replace(entry, chaos=entry.chaos / ratio, note=note, detail=detail, provenance=kept)
