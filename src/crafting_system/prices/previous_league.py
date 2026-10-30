"""The previous league at the same league age, then Standard (#40).

The last stages of the chain, for prices neither poe.ninja nor poe.watch has for the current league.
Both read poe.ninja's history (`ninja_history`) of a different economy, so every price is stamped
with its league and warned about as one to check.

- The previous league is the owner's choice (`context.previous_league`) or, from poe.ninja's
  undocumented league dump (`/poe1/api/data/dumps`), the softcore league that ended last. Its dates
  come from the dump; the current league's start from poe.watch's `/leagues`. The price is the
  median of the 7 days at the current league's age (days since its start) in the previous league.
- Standard is the last resort: the median of the 7 days ending today.

The stage applies only to a plain softcore challenge league. A source that fails or answers in an
unexpected shape skips its step with a warning and never raises.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from .fallbacks import HISTORY_DAYS, Context, Gap, StageResult, stamped_entry
from .http_json import GetJson, SourceError
from .ninja_history import exchange_history, stash_history, window_ending
from .poe_watch import BASE_URL as WATCH_URL
from .poe_watch import chaos_text
from .price_file import PriceEntry

DUMPS_URL = "https://poe.ninja/poe1/api/data/dumps"
LEAGUES_URL = f"{WATCH_URL}/leagues"
PREVIOUS_SOURCE = "poe.ninja-previous-league"
STANDARD_SOURCE = "poe.ninja-standard"
STANDARD = "Standard"
OTHER_MODES = ("hardcore", "hc", "ruthless", "ssf", "solo")  # league names that start so are not plain softcore


@dataclass(frozen=True)
class _Old:
    """A finished league as poe.ninja's dump lists it: first and last day it has data for."""

    name: str
    start: date
    end: date


def _day_of(text: object) -> date | None:
    """The UTC date of an ISO timestamp like 2026-03-06T00:00:00Z; None when it is not one."""
    if not isinstance(text, str):
        return None
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    return stamp.astimezone(UTC).date() if stamp.tzinfo else stamp.date()


def _is_plain_softcore(league: str) -> bool:
    return league.casefold() != STANDARD.casefold() and not league.casefold().startswith(OTHER_MODES)


def _readable(gap: Gap) -> bool:
    """Whether poe.ninja's history can be asked about the gap: it has an exchange id or a stash line id."""
    return bool(gap.exchange_id) or (bool(gap.stash_kind) and gap.stash_id is not None)


def _fetch(get_json: GetJson, url: str) -> Any:
    """The parsed answer of `url`, or None when the request failed."""
    try:
        return get_json(url)
    except SourceError:
        return None


def _old_leagues(data: Any) -> list[_Old]:
    """The plain softcore leagues of the dump, with valid dates."""
    found = []
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("leagueName"), str):
            continue
        start, end = _day_of(entry.get("minDate")), _day_of(entry.get("maxDate"))
        if start is not None and end is not None and _is_plain_softcore(entry["leagueName"]):
            found.append(_Old(entry["leagueName"], start, end))
    return found


def _league_start(data: Any, league: str) -> date | None:
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, dict) and entry.get("name") == league:
            return _day_of(entry.get("start_date"))
    return None


def _rows(get_json: GetJson, gap: Gap, league: str, anchor: date, first: date, last: date) -> list[tuple[date, float]]:
    """poe.ninja's daily rows of the gap in `league` inside the window (one history request)."""
    if gap.exchange_id:
        return exchange_history(get_json, league, gap.exchange_id, first, last)
    return stash_history(get_json, league, gap.stash_kind, gap.stash_id, anchor, first, last)


def previous_league_stage(get_json: GetJson, context: Context, gaps: Sequence[Gap]) -> StageResult:
    """Price the gaps from the previous league at the same age, then from Standard; see the module docstring."""
    left = [gap for gap in gaps if _readable(gap)]
    if not left or not _is_plain_softcore(context.league):
        return StageResult()
    prices: dict[str, PriceEntry] = {}
    warnings: list[str] = []

    def take(
        league: str, source: str, anchor: date, first: date, last: date, why: str, where: str, caution: str, **detail: object
    ) -> None:
        """Price the open gaps from `league`'s rows in the window; the note and the warning say what it is."""
        nonlocal left
        for gap in left:
            rows = _rows(get_json, gap, league, anchor, first, last)
            if not rows:
                continue
            chaos, day = statistics.median(price for _, price in rows), max(day for day, _ in rows)
            note = f"median of {len(rows)} poe.ninja daily rows in the {HISTORY_DAYS} days ending {last.isoformat()} of {league}: {why}"
            prices[gap.name] = stamped_entry(chaos, source, league, day, note, current_league=context.league, **detail)
            warnings.append(
                f"{gap.name}: no usable price in {context.league}; used {chaos_text(chaos)} Chaos "
                f"from {league}{where} ({day.isoformat()}): {caution}"
            )
        left = [gap for gap in left if gap.name not in prices]

    old = _previous(get_json, context, warnings)
    if old is not None:
        age_days = _age(get_json, context, warnings)
        if age_days is not None:
            first, last = window_ending(old.start + timedelta(days=age_days))
            if first > old.end:
                warnings.append(
                    f"previous league {old.name} ended on {old.end.isoformat()}, before league day {age_days}; skipped"
                )
            else:
                take(
                    old.name,
                    PREVIOUS_SOURCE,
                    old.end,
                    first,
                    last,
                    f"the same league age in an older league (league day {age_days})",
                    f" at league day {age_days}",
                    "a different economy, check it",
                    age_days=age_days,
                )

    if left:
        first, last = window_ending(context.today)
        take(
            STANDARD,
            STANDARD_SOURCE,
            context.today,
            first,
            last,
            "the Standard economy, not this league's",
            "",
            "the Standard economy, check it",
        )
    return StageResult(prices, warnings)


def _previous(get_json: GetJson, context: Context, warnings: list[str]) -> _Old | None:
    """The previous league: the owner's choice or the softcore league that ended last; None means Standard."""
    wanted = context.previous_league
    if wanted is not None and wanted.casefold() == STANDARD.casefold():
        return None
    data = _fetch(get_json, DUMPS_URL)
    leagues = [old for old in _old_leagues(data) if old.name != context.league]
    if wanted is not None:
        chosen = next((old for old in leagues if old.name == wanted), None)
        if chosen is None:
            warnings.append(f"previous league {wanted} is not in poe.ninja's league list")
        return chosen
    if not leagues:
        warnings.append("poe.ninja's league list gave no previous league")
        return None
    return max(leagues, key=lambda old: (old.end, old.start))


def _age(get_json: GetJson, context: Context, warnings: list[str]) -> int | None:
    """Days since the current league started, from poe.watch's league list; None when it is unknown."""
    start = _league_start(_fetch(get_json, LEAGUES_URL), context.league)
    age_days = (context.today - start).days if start is not None else -1
    if age_days < 0:
        warnings.append(
            f"the age of {context.league} is unknown (poe.watch's league list has no start date); previous league skipped"
        )
        return None
    return age_days
