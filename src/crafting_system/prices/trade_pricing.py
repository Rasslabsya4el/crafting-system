"""Price a buy spec from the trade site's listings and store it beside the poe.ninja prices (#39).

The flow of `price_buy_spec`: the stats list (cached for a week) maps the spec's mods to stat ids, the
query goes to the site (the answer is cached for a day by the hash of league and body), ten listings
are fetched, and each is turned into Chaos with the rates of the price file. A listing that cannot be
turned into Chaos or does not match the spec is dropped and counted, never guessed. The price is the
mean of the `k` cheapest of what is left (#133: the query asks for instant-buyout listings of any age,
so the cheapest listings are real prices).

Nothing here reads a clock: the caller passes `now`. The client's request budget is the only limit on
requests; a cache hit costs none.
"""

import json
import os
import statistics
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..data import Mod
from .price_file import MAX_AGE_DAYS, PriceEntry, PriceFile, load_price_file, write_price_file
from .trade_http import MAX_FETCH_IDS, TradeClient, TradeError
from .trade_query import DEFAULT_INDEXED, BuySpec, build_query, query_hash
from .trade_stats import TradeStats, parse_trade_stats, resolve_buy_mod

TRADE_SOURCE = "trade-api"
DEFAULT_K = 5
MIN_LISTINGS = 3
FETCH_COUNT = MAX_FETCH_IDS  # the site's maximum for one fetch call
QUERY_TTL = timedelta(hours=24)
STATS_TTL = timedelta(days=7)
DEFAULT_MAX_REQUESTS = 4

# Trade currency id -> the name the price file uses. A plain table: a currency not listed here is
# dropped as "unknown currency".
CURRENCY_NAMES: Mapping[str, str] = {
    "chaos": "Chaos Orb",
    "divine": "Divine Orb",
    "exalted": "Exalted Orb",
    "mirror": "Mirror of Kalandra",
    "annul": "Orb of Annulment",
    "alch": "Orb of Alchemy",
    "vaal": "Vaal Orb",
    "regal": "Regal Orb",
    "chance": "Orb of Chance",
    "fusing": "Orb of Fusing",
    "jewellers": "Jeweller's Orb",
    "chrome": "Chromatic Orb",
    "scour": "Orb of Scouring",
    "alt": "Orb of Alteration",
    "aug": "Orb of Augmentation",
    "transmute": "Orb of Transmutation",
    "blessed": "Blessed Orb",
    "regret": "Orb of Regret",
    "gcp": "Gemcutter's Prism",
    "wisdom": "Scroll of Wisdom",
    "fracturing-orb": "Fracturing Orb",
}

NO_PRICE = "no price"
UNKNOWN_CURRENCY = "unknown currency"
NOT_IN_PRICE_FILE = "currency not in the price file"
WRONG_INFLUENCE = "wrong influence"
NOT_FRACTURED = "not fractured"


class NotEnoughListings(TradeError):
    """The search found too few listings that can be priced; nothing is stored."""


@dataclass(frozen=True)
class TradePrice:
    name: str
    chaos: float
    league: str
    date: date  # UTC date of the run
    listings: int  # the search `total`: how many listings the site has
    used: int  # listings in the mean, at most `k`
    k: int
    fetched: int  # rows fetched
    dropped: Mapping[str, int]  # reason -> count
    query_hash: str
    query: Mapping[str, Any]  # the search body

    @property
    def indexed(self) -> str | None:
        """The listing-age window the query was sent with (None = any time)."""
        window = self.query["query"].get("filters", {}).get("trade_filters", {}).get("filters", {})
        return window.get("indexed", {}).get("option")


# --- cache files ---------------------------------------------------------------------------------


def _read_cache(path: Path, now: datetime, ttl: timedelta) -> dict | None:
    """The cached JSON object when it is younger than `ttl`; a missing, broken or stale file is a miss."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(document["fetched_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(document, dict) or fetched_at.tzinfo is None or now - fetched_at >= ttl:
        return None
    return document


def _write_cache(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, sort_keys=True)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _stamp(now: datetime) -> str:
    return now.astimezone(UTC).isoformat()


def _stats(client: TradeClient, cache_dir: Path, now: datetime, refresh: bool) -> TradeStats:
    path = cache_dir / "trade" / "stats.json"
    cached = None if refresh else _read_cache(path, now, STATS_TTL)
    if cached is not None:
        try:
            return parse_trade_stats(cached.get("stats"))
        except ValueError:
            pass  # a damaged cache is asked for again
    raw = client.data_stats()
    stats = parse_trade_stats(raw)
    _write_cache(path, {"fetched_at": _stamp(now), "stats": raw})
    return stats


def _row(item: Mapping[str, Any]) -> dict[str, Any]:
    listing = item.get("listing") if isinstance(item.get("listing"), dict) else {}
    found = item.get("item") if isinstance(item.get("item"), dict) else {}
    return {
        "price": listing.get("price"),
        "indexed": listing.get("indexed"),
        "fractured": found.get("fractured"),
        "influences": found.get("influences"),
    }


def _listings(
    client: TradeClient, league: str, body: dict, path: Path, now: datetime
) -> tuple[int, list[dict[str, Any]]]:
    """(total, rows) of the query, from the cache or the site (one search, one fetch)."""
    cached = _read_cache(path, now, QUERY_TTL)
    if cached is not None and isinstance(cached.get("rows"), list) and isinstance(cached.get("total"), int):
        return cached["total"], cached["rows"]
    answer = client.search(league, body)
    total, ids, search_id = answer.get("total"), answer.get("result"), answer.get("id")
    if not total or not isinstance(ids, list) or not ids:
        raise NotEnoughListings("the trade site has no listings for this query (total 0)")
    if not isinstance(total, int) or not isinstance(search_id, str):
        raise TradeError("the search answer has no usable 'total' or 'id'")
    fetched = client.fetch(ids[:FETCH_COUNT], search_id).get("result")
    if not isinstance(fetched, list):
        raise TradeError("the fetch answer has no 'result' list")
    rows = [_row(item) for item in fetched if isinstance(item, dict)]
    _write_cache(path, {"fetched_at": _stamp(now), "total": total, "rows": rows})
    return total, rows


# --- pricing -------------------------------------------------------------------------------------


def _influences(row: Mapping[str, Any]) -> frozenset[str]:
    found = row.get("influences")
    if not isinstance(found, dict):
        return frozenset()
    return frozenset(name for name, present in found.items() if present)


def _chaos_of(row: Mapping[str, Any], spec: BuySpec, price_file: PriceFile) -> float | str:
    """The listing's price in Chaos, or the reason it is dropped."""
    price = row.get("price")
    amount = price.get("amount") if isinstance(price, dict) else None
    if isinstance(amount, bool) or not isinstance(amount, int | float) or amount <= 0:
        return NO_PRICE
    name = CURRENCY_NAMES.get(price.get("currency"))
    if name is None:
        return UNKNOWN_CURRENCY
    rate = price_file.prices.get(name)
    if rate is None:
        return NOT_IN_PRICE_FILE
    if _influences(row) != frozenset(spec.influences):
        return WRONG_INFLUENCE
    if any(mod.fractured for mod in spec.mods) and row.get("fractured") is not True:
        return NOT_FRACTURED
    return amount * rate.chaos


def price_buy_spec(
    spec: BuySpec,
    game_mods: Iterable[Mod],
    price_file: PriceFile,
    client: TradeClient,
    cache_dir: Path,
    now: datetime,
    k: int = DEFAULT_K,
    refresh_stats: bool = False,
    indexed: str | None = DEFAULT_INDEXED,
) -> TradePrice:
    """Mean Chaos price of the `k` cheapest usable listings of `spec`; see the module text.

    `price_file` should already carry the overrides (`load_prices`). Raises `NotEnoughListings` when
    fewer than `MIN_LISTINGS` listings are usable, and the `TradeError`s of the client. `indexed` is the
    listing-age window of the query (None = any time); it is part of the body, so of the cache key.
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")
    mods = tuple(game_mods)
    stats = _stats(client, cache_dir, now, refresh_stats)
    filters = [resolve_buy_mod(mod, mods, stats) for mod in spec.mods]
    body = build_query(spec, filters, indexed).body()
    digest = query_hash(price_file.league, body)
    hint = _window_hint(indexed)
    try:
        total, rows = _listings(client, price_file.league, body, cache_dir / "trade" / f"{digest}.json", now)
    except NotEnoughListings as error:
        raise NotEnoughListings(f"{error}{hint}") from None

    usable: list[float] = []
    dropped: dict[str, int] = {}
    for row in rows:
        result = _chaos_of(row, spec, price_file)
        if isinstance(result, str):
            dropped[result] = dropped.get(result, 0) + 1
        else:
            usable.append(result)
    if len(usable) < MIN_LISTINGS:
        why = "; ".join(f"{count} {reason}" for reason, count in sorted(dropped.items())) or "none dropped"
        raise NotEnoughListings(
            f"only {len(usable)} of {len(rows)} fetched listings ({total} on the site) can be priced; "
            f"at least {MIN_LISTINGS} are needed. Dropped: {why}{hint}"
        )
    cheapest = sorted(usable)[:k]
    return TradePrice(
        name=spec.name,
        chaos=float(statistics.fmean(cheapest)),
        league=price_file.league,
        date=now.astimezone(UTC).date(),
        listings=total,
        used=len(cheapest),
        k=k,
        fetched=len(rows),
        dropped=dropped,
        query_hash=digest,
        query=body,
    )


# --- the price file ------------------------------------------------------------------------------


def _window_hint(indexed: str | None) -> str:
    if indexed is None:
        return ""
    return f". Only listings listed {within(indexed)} count; a wider window (--indexed) may find more"


def within(indexed: str | None) -> str:
    return "any time" if indexed is None else f"within {indexed}"


def entry_for(price: TradePrice) -> PriceEntry:
    note = (
        f"mean of the {price.used} cheapest instant-buyout listings of {price.fetched} fetched, "
        f"{price.listings} on the site, listed {within(price.indexed)}"
    )
    detail = {
        "league": price.league,
        "date": price.date.isoformat(),
        "listings": price.listings,
        "used": price.used,
        "k": price.k,
        "query_hash": price.query_hash,
        "query": price.query,
    }
    return PriceEntry(price.chaos, TRADE_SOURCE, note, detail)


def refuse_name_collision(name: str, existing: PriceEntry | None) -> None:
    """`ValueError` when `existing` (the entry already under `name`) is another source's price."""
    if existing is not None and existing.source != TRADE_SOURCE:
        raise ValueError(f"name {name!r} collides with a {existing.source} price; rename the buy spec")


def store_trade_price(path: Path, price: TradePrice, entry: PriceEntry) -> None:
    """Add `entry` under the price's name to the price file at `path`; nothing else changes.

    A name that is already another source's price is refused (`ValueError`) and the file is untouched.
    """
    current = load_price_file(path)
    refuse_name_collision(price.name, current.prices.get(price.name))
    write_price_file(path, replace(current, prices={**current.prices, price.name: entry}))


def trade_price_age_days(entry: PriceEntry, today: date) -> int | None:
    """Whole days from the run that made a trade-api `entry` to `today`; None when it carries no usable date."""
    stamp = entry.detail.get("date") if entry.detail else None
    try:
        ran_on = date.fromisoformat(stamp) if isinstance(stamp, str) else None
    except ValueError:
        return None
    return None if ran_on is None else (today - ran_on).days


def _aged(entry: PriceEntry, today: date, max_age_days: int) -> int | None:
    """The age in days of a trade-api `entry` older than `max_age_days`, else None."""
    if entry.source != TRADE_SOURCE:
        return None
    age = trade_price_age_days(entry, today)
    return age if age is not None and age > max_age_days else None


def _stale_line(name: str, age: int) -> str:
    return (
        f"trade-api price {name!r} is {age} days old (limit {MAX_AGE_DAYS}); "
        f"run `trade` for it again to refresh it"
    )


def stale_trade_warnings(price_file: PriceFile, today: date, max_age_days: int = MAX_AGE_DAYS) -> list[str]:
    """One warning line per trade-api price older than `max_age_days`, sorted by name.

    The age counts from the UTC date of the run that made the price (`detail["date"]`); a trade price
    without a usable date has no age and gets no warning.
    """
    ages = {name: _aged(entry, today, max_age_days) for name, entry in price_file.prices.items()}
    return [_stale_line(name, age) for name, age in sorted(ages.items()) if age is not None]


def current_trade_prices(old: PriceFile | None, league: str, today: date | None = None) -> dict[str, PriceEntry]:
    """The trade-api prices of `old` that are prices of `league`: the ones a fetch of `league` keeps.

    With `today`, a price older than the stale limit is left out: it no longer covers its name, so a
    fetch treats the name like any other wanted name (the aged price itself is kept and flagged).
    """
    if old is None or old.league != league:
        return {}
    return {
        name: entry
        for name, entry in old.prices.items()
        if entry.source == TRADE_SOURCE
        and (entry.detail is None or entry.detail.get("league") in (None, league))
        and (today is None or _aged(entry, today, MAX_AGE_DAYS) is None)
    }


def merge_trade_prices(new: PriceFile, old: PriceFile | None) -> tuple[PriceFile, list[str]]:
    """`new` plus the trade prices of `old`, so a re-fetch of poe.ninja does not lose them.

    A trade price is a price of one league: a different league drops them, with a warning line naming
    them. So is a trade price whose own `detail["league"]` names another league than the new file's.
    A name the new file already has stays as the new file has it. A kept price older than the stale limit
    (counted to the new file's date) is flagged in the warnings, like a stale price file. Returns (file, warnings).
    """
    if old is None:
        return new, []
    trade = {name: entry for name, entry in old.prices.items() if entry.source == TRADE_SOURCE}
    if not trade:
        return new, []
    if old.league != new.league:
        names = ", ".join(sorted(trade))
        return new, [
            f"dropped {len(trade)} trade-api price(s) of league {old.league} "
            f"(the new price file is for {new.league}): {names}"
        ]
    warnings = []
    kept = {}
    for name, entry in trade.items():
        entry_league = entry.detail.get("league") if entry.detail else None
        if entry_league is not None and entry_league != new.league:
            warnings.append(
                f"trade-api price {name!r} dropped: it is a price of league {entry_league}, "
                f"the new price file is for {new.league}"
            )
        elif name in new.prices:
            warnings.append(f"trade-api price {name!r} dropped: the fetch has a {new.prices[name].source} price of that name")
        else:
            kept[name] = entry
    aged = stale_trade_warnings(replace(new, prices=kept), new.fetched_at.astimezone(UTC).date())
    return replace(new, prices={**new.prices, **kept}), [*warnings, *aged]
