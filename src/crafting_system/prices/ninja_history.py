"""poe.ninja price history, read as dated rows of one item in one league (undocumented endpoints).

Two shapes, both fetched by the numbers the current overviews give:

- exchange items (currency, fossils, resonators, essences): `exchange/current/details?...&id=<detailsId>`
  answers `pairs[]`; the pair with id `chaos` has `history[{timestamp, rate, volumePrimaryValue}]`.
- stash items (bases, beasts): `stash/current/item/history?...&type=<BaseType|Beast>&id=<line id>`
  answers `[{count, value, daysAgo}]`. `daysAgo` 0 is the league's last day: today for a running
  league, the league's end date for a finished one, so the caller passes that day as `anchor`. A line
  id is the same in every league.

A row counts when it has a real price and a sample: volume above zero (exchange) or `count` of at
least `MIN_COUNT` (stash). Every function returns `(day, price)` pairs inside the window `first..last`
(UTC dates, both ends included); a changed shape or a failed request gives no rows, never an error:
the history endpoints are not documented, so "this source failed" is an ordinary answer.
"""

import statistics
import urllib.parse
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from .fallbacks import HISTORY_DAYS, MIN_COUNT, Context, Gap, StageResult, stamped_entry
from .http_json import GetJson, SourceError
from .poe_ninja import BASE_URL, HISTORY_SOURCE, OVERVIEW_TYPES
from .price_file import is_price


def window_ending(last: date, days: int = HISTORY_DAYS) -> tuple[date, date]:
    """The `days` days ending on `last`, as (first, last)."""
    return last - timedelta(days=days - 1), last


def exchange_rows(data: Any, first: date, last: date) -> list[tuple[date, float]]:
    """Chaos rates of the traded days of an exchange `details` answer inside the window."""
    pairs = data.get("pairs") if isinstance(data, dict) else None
    if not isinstance(pairs, list):
        return []
    chaos = next((p for p in pairs if isinstance(p, dict) and p.get("id") == "chaos"), None)
    history = chaos.get("history") if chaos is not None else None
    if not isinstance(history, list):
        return []
    rows = []
    for row in history:
        if not isinstance(row, dict) or not isinstance(row.get("timestamp"), str):
            continue
        if not (is_price(row.get("rate")) and is_price(row.get("volumePrimaryValue"))):
            continue
        try:
            stamp = datetime.fromisoformat(row["timestamp"])
        except ValueError:
            continue
        day = stamp.astimezone(UTC).date() if stamp.tzinfo else stamp.date()
        if first <= day <= last:
            rows.append((day, float(row["rate"])))
    return rows


def stash_rows(data: Any, anchor: date, first: date, last: date) -> list[tuple[date, float]]:
    """Chaos values of the days with `count >= MIN_COUNT` of a stash `history` answer inside the window."""
    if not isinstance(data, list):
        return []
    rows = []
    for row in data:
        if not isinstance(row, dict):
            continue
        count, value, ago = row.get("count"), row.get("value"), row.get("daysAgo")
        if isinstance(count, bool) or not isinstance(count, int) or count < MIN_COUNT:
            continue
        if isinstance(ago, bool) or not isinstance(ago, int) or ago < 0 or not is_price(value):
            continue
        day = anchor - timedelta(days=ago)
        if first <= day <= last:
            rows.append((day, float(value)))
    return rows


def _url(route: str, **params: object) -> str:
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{BASE_URL}/{route}?{query}"


def exchange_history(
    get_json: GetJson, league: str, details_id: str, first: date, last: date
) -> list[tuple[date, float]]:
    """Rows of the item in `league`; every overview type is tried in turn until one answers with rows."""
    for kind in OVERVIEW_TYPES:
        url = _url("exchange/current/details", league=league, type=kind, id=details_id)
        try:
            rows = exchange_rows(get_json(url), first, last)
        except SourceError:
            continue
        if rows:
            return rows
    return []


def stash_history(
    get_json: GetJson, league: str, kind: str, line_id: int, anchor: date, first: date, last: date
) -> list[tuple[date, float]]:
    """Rows of the stash line `line_id` (`kind` is "BaseType" or "Beast") in `league`."""
    url = _url("stash/current/item/history", league=league, type=kind, id=line_id)
    try:
        return stash_rows(get_json(url), anchor, first, last)
    except SourceError:
        return []


def ninja_history_stage(get_json: GetJson, context: Context, gaps: Sequence[Gap]) -> StageResult:
    """Price each gap with the median of its poe.ninja daily rows in the 7 days ending on `context.today`.

    A gap with an `exchange_id` is read from the exchange history, one with a `stash_kind` and `stash_id`
    from the stash history; any other gap, or one without rows, stays a gap.
    """
    first, last = window_ending(context.today)
    prices, warnings = {}, []
    for gap in gaps:
        if gap.exchange_id is not None:
            rows = exchange_history(get_json, context.league, gap.exchange_id, first, last)
        elif gap.stash_kind is not None and gap.stash_id is not None:
            rows = stash_history(get_json, context.league, gap.stash_kind, gap.stash_id, context.today, first, last)
        else:
            continue
        if not rows:
            continue
        note = f"median of {len(rows)} daily rows in the {HISTORY_DAYS} days ending {last.isoformat()}"
        median = float(statistics.median(price for _, price in rows))
        newest = max(day for day, _ in rows)
        prices[gap.name] = stamped_entry(median, HISTORY_SOURCE, context.league, newest, note)
        warnings.append(f"{gap.name}: no current price, used history ({note})")
    return StageResult(prices, warnings)
