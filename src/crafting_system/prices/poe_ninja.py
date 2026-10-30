"""The poe.ninja fetcher: current exchange prices, with price history as the fallback (ADR-0007).

The transport is injected as `get_json(url) -> parsed JSON`; `http_get_json` is the real one.
The clock is injected too (`now`): nothing here reads it. The fetcher never touches the
hand-written overrides file; it only builds a `PriceFile` for the caller to write.

The `details` endpoint is undocumented, so any failure or changed shape there means "this
source failed": the resource stays unpriced and is reported, nothing crashes.
"""

import re
import statistics
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from .http_json import TIMEOUT_SECONDS, USER_AGENT, GetJson, SourceError, http_get_json  # noqa: F401  (re-exported)
from .price_file import CHAOS_ORB, DIVINE_ORB, PriceEntry, PriceFile, is_price, missing_prices

BASE_URL = "https://poe.ninja/poe1/api/economy"
OVERVIEW_TYPES = ("Currency", "Fossil", "Resonator", "Essence")
SOURCE = "poe.ninja"
HISTORY_SOURCE = "poe.ninja-history"
HISTORY_DAYS = 7


@dataclass(frozen=True)
class FetchResult:
    price_file: PriceFile
    warnings: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # wanted names still without a price


def history_slug(name: str) -> str:
    """The id poe.ninja gives an item: lowercase, apostrophes dropped, other gaps as hyphens.

    "Hollow Fossil" -> "hollow-fossil", "Jeweller's Orb" -> "jewellers-orb" (checked against
    every Currency, Essence, Fossil and Resonator `detailsId` of the 3.29 data).
    """
    lowered = name.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def _url(route: str, **params: str) -> str:
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{BASE_URL}/{route}?{query}"


# --- the fetch -----------------------------------------------------------------------------


def fetch_price_file(
    get_json: GetJson,
    now: datetime,
    wanted: Iterable[str] | None = None,
    league: str | None = None,
) -> FetchResult:
    """Build a price file for `league` (default: the first league poe.ninja lists).

    A partial fetch never makes a file: the leagues call and every category (Currency, Fossil,
    Resonator, Essence) must answer with at least one usable price, else a `SourceError` is
    raised. `wanted` names that the overviews do not price (or price on zero volume) get the
    history fallback (daily rows of the 7 days ending on `now`'s UTC date); those still
    unpriced come back in `missing`.
    """
    if now.tzinfo is None:
        raise ValueError("`now` needs a time zone (pass a UTC time)")
    if league is not None and not league.strip():
        raise ValueError("league must not be blank")
    fetched_at = now.astimezone(UTC).replace(microsecond=0)
    wanted_names = sorted(set(wanted or ()))
    league = league if league is not None else _current_league(get_json)

    warnings: list[str] = []
    prices: dict[str, PriceEntry] = {}
    thin: dict[str, str] = {}  # zero-volume line name -> its details id
    divine_rate: float | None = None
    for kind in OVERVIEW_TYPES:
        try:
            overview = _parse_overview(get_json(_url("exchange/current/overview", league=league, type=kind)))
        except SourceError as error:
            raise SourceError(
                f"the {kind} prices failed: {error}; no price file was written, the old price file was kept"
            ) from error
        if kind == "Currency":
            divine_rate = overview.divine_rate
        for line in overview.lines:
            if line.thin:
                thin.setdefault(line.name, line.details_id)
            else:
                prices.setdefault(line.name, PriceEntry(line.chaos, SOURCE))

    prices[CHAOS_ORB] = PriceEntry(1.0, SOURCE)
    chaos_per_divine = _chaos_per_divine(prices, divine_rate)
    prices.setdefault(DIVINE_ORB, PriceEntry(chaos_per_divine, SOURCE))

    for name in wanted_names:
        if name in prices:
            continue
        entry = _history_price(
            get_json, league, thin.get(name) or history_slug(name), fetched_at.date()
        )
        if entry is not None:
            prices[name] = entry
            warnings.append(f"{name}: no current price, used history ({entry.note})")
        elif name in thin:
            warnings.append(f"{name}: current line has no trade volume and history gave nothing; dropped")

    price_file = PriceFile(league, fetched_at, chaos_per_divine, prices)
    return FetchResult(price_file, warnings, missing_prices(wanted_names, prices))


def _current_league(get_json: GetJson) -> str:
    leagues = get_json(f"{BASE_URL}/leagues")
    first = leagues[0] if isinstance(leagues, list) and leagues else None
    league = first.get("id") if isinstance(first, dict) else None
    if not isinstance(league, str) or not league.strip():
        raise SourceError("poe.ninja returned no usable league list")
    return league


def _chaos_per_divine(prices: dict[str, PriceEntry], divine_rate: float | None) -> float:
    if DIVINE_ORB in prices:
        return prices[DIVINE_ORB].chaos
    if divine_rate is not None:
        return 1 / divine_rate
    raise SourceError("the Currency overview has no Divine Orb price")


# --- current overviews ---------------------------------------------------------------------


@dataclass(frozen=True)
class _Line:
    name: str
    chaos: float
    details_id: str
    thin: bool  # traded on zero volume: the price is not trustworthy


@dataclass(frozen=True)
class _Overview:
    lines: list[_Line]
    divine_rate: float | None  # Divine Orbs per Chaos Orb, from `core.rates`


def _parse_overview(data: Any) -> _Overview:
    if not isinstance(data, dict):
        raise SourceError("unexpected answer shape (not an object)")
    core, items, lines = data.get("core"), data.get("items"), data.get("lines")
    if not isinstance(core, dict):
        raise SourceError("unexpected answer shape (no 'core' block)")
    if core.get("primary") != "chaos":
        raise SourceError(f"prices are not in chaos (core.primary is {core.get('primary')!r})")
    if not isinstance(items, list) or not isinstance(lines, list):
        raise SourceError("unexpected answer shape ('items' and 'lines' must be lists)")

    items_by_id = {
        item["id"]: item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str) and _is_text(item.get("name"))
    }
    parsed = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        item = items_by_id.get(line.get("id"))
        if item is None or not is_price(line.get("primaryValue")):
            continue
        volume = line.get("volumePrimaryValue")
        thin = isinstance(volume, int | float) and not isinstance(volume, bool) and volume <= 0
        details_id = item.get("detailsId") if _is_text(item.get("detailsId")) else item["id"]
        parsed.append(_Line(item["name"], float(line["primaryValue"]), details_id, thin))

    if not parsed:
        raise SourceError("no line with a usable price")

    rates = core.get("rates")
    rate = rates.get("divine") if isinstance(rates, dict) else None
    return _Overview(parsed, float(rate) if is_price(rate) else None)


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


# --- history fallback ----------------------------------------------------------------------


def _history_price(get_json: GetJson, league: str, details_id: str, today: date) -> PriceEntry | None:
    """Median Chaos rate of the daily rows with trades in the 7 days ending `today` (UTC).

    Tries each overview type in turn. Rows older than the window or dated after `today` do not
    count; with no usable row the resource stays unpriced.
    """
    for kind in OVERVIEW_TYPES:
        url = _url("exchange/current/details", league=league, type=kind, id=details_id)
        try:
            rates = _window_rates(get_json(url), today)
        except SourceError:
            continue
        if rates:
            note = f"median of {len(rates)} daily rows in the {HISTORY_DAYS} days ending {today.isoformat()}"
            return PriceEntry(float(statistics.median(rates)), HISTORY_SOURCE, note)
    return None


def _window_rates(data: Any, today: date) -> list[float]:
    """Chaos rates of the rows with trades dated in the window ending `today`; [] if the shape is off."""
    pairs = data.get("pairs") if isinstance(data, dict) else None
    if not isinstance(pairs, list):
        return []
    chaos = next((p for p in pairs if isinstance(p, dict) and p.get("id") == "chaos"), None)
    history = chaos.get("history") if chaos is not None else None
    if not isinstance(history, list):
        return []
    first_day = today - timedelta(days=HISTORY_DAYS - 1)
    rates = []
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
        if first_day <= day <= today:
            rates.append(float(row["rate"]))
    return rates
