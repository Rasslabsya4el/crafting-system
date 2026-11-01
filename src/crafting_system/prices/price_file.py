"""The price file, hand-written overrides, staleness and missing prices (ADR-0007).

`prices.json` is written by the fetcher; `price_overrides.toml` is written by hand and never
touched by any code here, so a re-fetch cannot clobber a hand edit. Both live in the data
directory of the config. Every price is in Chaos Orbs. Nothing here reads the clock: the caller
passes `today`.
"""

import json
import math
import os
import tempfile
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ..config import Config
from .price_names import canonical_price_name

UNIT = "chaos"
CHAOS_ORB = "Chaos Orb"
DIVINE_ORB = "Divine Orb"
OVERRIDE_SOURCE = "override"
PRICE_FILE_NAME = "prices.json"
OVERRIDES_FILE_NAME = "price_overrides.toml"
MAX_AGE_DAYS = 7
FETCH_COMMAND = "python -m crafting_system.prices fetch"
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class PriceFileNotFound(FileNotFoundError):
    """The price file does not exist yet; the owner has to run the fetcher."""


@dataclass(frozen=True)
class PriceEntry:
    chaos: float
    source: str
    note: str | None = None
    detail: Mapping[str, Any] | None = None  # a JSON object: how the price was found (#39)


MARKET_THIN = "thin"
MARKET_NONE = "none"
MARKET_STATES = (MARKET_THIN, MARKET_NONE)


@dataclass(frozen=True)
class MarketRecord:
    """A trade search that did not make a price, kept as a recorded state (#355).

    `none`: the site answered a successful search with no listing (total 0). `thin`: it has listings but
    too few to call a market (fewer than the listing-count rail, or too few that can be priced). Neither
    is offered and neither is "unknown": the trade site said so on `date`, and the record ages like a price.
    """

    state: str  # MARKET_THIN or MARKET_NONE
    league: str
    date: date  # UTC date of the search
    listings: int  # the search `total`
    usable: int  # listings that could be priced (0 when none were fetched)
    query_hash: str
    query: Mapping[str, Any]


@dataclass(frozen=True)
class PriceFile:
    league: str
    fetched_at: datetime  # timezone-aware, whole seconds
    chaos_per_divine: float
    prices: dict[str, PriceEntry] = field(default_factory=dict)
    markets: dict[str, MarketRecord] = field(default_factory=dict)  # thin / none trade searches, by name
    ninja: dict[str, PriceEntry] = field(default_factory=dict)  # poe.ninja rows of names whose `prices` entry is a trade price, so both show side by side (#357)


def default_price_file_path(config: Config) -> Path:
    return config.data_dir / PRICE_FILE_NAME


def default_overrides_path(config: Config) -> Path:
    return config.data_dir / OVERRIDES_FILE_NAME


def to_divine(chaos: float, price_file: PriceFile) -> float:
    """A Chaos amount as Divine Orbs, for reports."""
    return chaos / price_file.chaos_per_divine


def is_price(value: object) -> bool:
    """A real number above zero that is not infinite (a bool is not a number here)."""
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


# --- the price file on disk ----------------------------------------------------------------


def write_price_file(path: Path, price_file: PriceFile) -> None:
    """Write `price_file` as sorted, indented JSON; the old file is replaced in one step."""
    document = {
        "unit": UNIT,
        "league": price_file.league,
        "fetched_at": price_file.fetched_at.astimezone(UTC).strftime(_TIMESTAMP_FORMAT),
        "chaos_per_divine": price_file.chaos_per_divine,
        "prices": {name: _entry_to_json(entry) for name, entry in price_file.prices.items()},
    }
    if price_file.markets:
        document["markets"] = {name: _market_to_json(record) for name, record in price_file.markets.items()}
    if price_file.ninja:
        document["ninja"] = {name: _entry_to_json(entry) for name, entry in price_file.ninja.items()}
    text = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _entry_to_json(entry: PriceEntry) -> dict[str, Any]:
    return {
        "chaos": entry.chaos,
        "source": entry.source,
        **({"note": entry.note} if entry.note is not None else {}),
        **({"detail": entry.detail} if entry.detail is not None else {}),
    }


def _market_to_json(record: MarketRecord) -> dict[str, Any]:
    return {
        "state": record.state,
        "league": record.league,
        "date": record.date.isoformat(),
        "listings": record.listings,
        "usable": record.usable,
        "query_hash": record.query_hash,
        "query": record.query,
    }


def load_price_file(path: Path) -> PriceFile:
    """Read and validate a price file; a bad shape is a `ValueError` naming the file.

    A base name is put in canonical form (`canonical_price_name`), as `load_overrides` does, so a price
    stored under `... Warlord/Hunter)` is found under `... Hunter/Warlord)`. Two names that become one
    are an error.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise PriceFileNotFound(
            f"No price file at {path}. Run `{FETCH_COMMAND}` to create it."
        ) from None
    except UnicodeDecodeError as error:
        raise ValueError(f"{path}: not a UTF-8 text file: {error}") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: not valid JSON: {error}") from error
    return _price_file_from_document(document, path)


def _price_file_from_document(document: object, path: Path) -> PriceFile:
    if not isinstance(document, dict):
        raise ValueError(f"{path}: the price file must be a JSON object")
    for key in ("unit", "league", "fetched_at", "chaos_per_divine", "prices"):
        if key not in document:
            raise ValueError(f"{path}: missing key {key!r}")
    if document["unit"] != UNIT:
        raise ValueError(f"{path}: unit must be {UNIT!r}, not {document['unit']!r}")
    league = document["league"]
    if not isinstance(league, str) or not league.strip():
        raise ValueError(f"{path}: league must be a non-empty string")
    fetched_at = _parse_timestamp(document["fetched_at"], path)
    chaos_per_divine = document["chaos_per_divine"]
    if not is_price(chaos_per_divine):
        raise ValueError(f"{path}: chaos_per_divine must be a number above zero")
    raw_prices = document["prices"]
    if not isinstance(raw_prices, dict):
        raise ValueError(f"{path}: prices must be an object of name -> price entry")

    prices = {}
    for name, raw in raw_prices.items():
        entry = _entry_from_document(raw, name, "price", path)
        if name == CHAOS_ORB and raw["chaos"] != 1:
            raise ValueError(f"{path}: price {name!r}: Chaos Orb is always 1")
        canonical = canonical_price_name(name)
        if canonical in prices:
            raise ValueError(f"{path}: {name!r} and another name give the same price name {canonical!r}")
        prices[canonical] = entry
    markets = _markets_from_document(document.get("markets", {}), path)
    ninja = _ninja_from_document(document.get("ninja", {}), path)
    return PriceFile(league, fetched_at, float(chaos_per_divine), prices, markets, ninja)


def _entry_from_document(raw: object, name: str, label: str, path: Path) -> PriceEntry:
    """One entry of the `prices` or `ninja` block; `label` ("price" or "ninja") names the block in errors."""
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: {label} {name!r} must be an object")
    if not is_price(raw.get("chaos")):
        raise ValueError(f"{path}: {label} {name!r}: chaos must be a number above zero")
    source = raw.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError(f"{path}: {label} {name!r}: source must be a non-empty string")
    note = raw.get("note")
    if note is not None and not isinstance(note, str):
        raise ValueError(f"{path}: {label} {name!r}: note must be a string")
    detail = raw.get("detail")
    if detail is not None and not isinstance(detail, dict):
        raise ValueError(f"{path}: {label} {name!r}: detail must be an object")
    return PriceEntry(float(raw["chaos"]), source, note, detail)


def _ninja_from_document(raw_ninja: object, path: Path) -> dict[str, PriceEntry]:
    if not isinstance(raw_ninja, dict):
        raise ValueError(f"{path}: ninja must be an object of name -> price entry")
    ninja = {}
    for name, raw in raw_ninja.items():
        entry = _entry_from_document(raw, name, "ninja", path)
        canonical = canonical_price_name(name)
        if canonical in ninja:
            raise ValueError(f"{path}: ninja {name!r} and another name give the same price name {canonical!r}")
        ninja[canonical] = entry
    return ninja


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _markets_from_document(raw_markets: object, path: Path) -> dict[str, MarketRecord]:
    if not isinstance(raw_markets, dict):
        raise ValueError(f"{path}: markets must be an object of name -> market record")
    markets: dict[str, MarketRecord] = {}
    for name, raw in raw_markets.items():
        where = f"{path}: market {name!r}"
        if not isinstance(raw, dict):
            raise ValueError(f"{where} must be an object")
        if raw.get("state") not in MARKET_STATES:
            raise ValueError(f"{where}: state must be one of {', '.join(MARKET_STATES)}")
        if not isinstance(raw.get("league"), str) or not raw["league"].strip():
            raise ValueError(f"{where}: league must be a non-empty string")
        try:
            searched_on = date.fromisoformat(raw["date"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{where}: date must be an ISO date") from None
        if not _count(raw.get("listings")) or not _count(raw.get("usable")):
            raise ValueError(f"{where}: listings and usable must be whole numbers, zero or more")
        if not isinstance(raw.get("query_hash"), str) or not isinstance(raw.get("query"), dict):
            raise ValueError(f"{where}: query_hash must be a string and query an object")
        canonical = canonical_price_name(name)
        if canonical in markets:
            raise ValueError(f"{path}: {name!r} and another name give the same market name {canonical!r}")
        markets[canonical] = MarketRecord(
            raw["state"], raw["league"], searched_on, raw["listings"], raw["usable"], raw["query_hash"], raw["query"]
        )
    return markets


def _parse_timestamp(value: object, path: Path) -> datetime:
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError:
        raise ValueError(
            f"{path}: fetched_at must be an ISO timestamp with a time zone, got {value!r}"
        ) from None
    return parsed.astimezone(UTC)


# --- hand-written overrides ----------------------------------------------------------------


def load_overrides(path: Path) -> dict[str, float]:
    """Name -> Chaos price from the `[prices]` table; a missing file means no overrides.

    A base name is put in canonical form (`canonical_price_name`: influences in game order), so a
    hand price for `Stygian Vise (ilvl 85, Warlord/Hunter)` is the price of `... Hunter/Warlord)`,
    the name the wanted lists and the fetchers use. Two names that become one are an error.
    """
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        return {}
    except UnicodeDecodeError as error:
        raise ValueError(f"{path}: not a UTF-8 text file (save it as UTF-8): {error}") from error
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: not valid TOML: {error}") from error

    unknown = sorted(set(document) - {"prices"})
    if unknown:
        raise ValueError(f"{path}: unknown key {unknown[0]!r} (only a [prices] table is allowed)")
    table = document.get("prices", {})
    if not isinstance(table, dict):
        raise ValueError(f"{path}: 'prices' must be a table of name = Chaos price")

    overrides = {}
    for name, value in table.items():
        if not is_price(value):
            raise ValueError(f"{path}: {name!r} must be a number above zero, got {value!r}")
        if name == CHAOS_ORB and value != 1:
            raise ValueError(f"{path}: {name!r} is always 1 and cannot be overridden")
        canonical = canonical_price_name(name)
        if canonical in overrides:
            raise ValueError(f"{path}: {name!r} and another name give the same price name {canonical!r}")
        overrides[canonical] = float(value)
    return overrides


def load_prices(price_file_path: Path, overrides_path: Path) -> PriceFile:
    """The price file with the overrides on top: an override always wins, source "override".

    A missing price file is a `PriceFileNotFound` even when overrides exist: a price view
    needs the league and the date, which only a fetch gives.
    """
    fetched = load_price_file(price_file_path)
    overrides = load_overrides(overrides_path)
    if not overrides:
        return fetched
    prices = dict(fetched.prices)
    for name, chaos in overrides.items():
        prices[name] = PriceEntry(chaos, OVERRIDE_SOURCE)
    chaos_per_divine = overrides.get(DIVINE_ORB, fetched.chaos_per_divine)
    return replace(fetched, prices=prices, chaos_per_divine=chaos_per_divine)


# --- staleness and missing prices ----------------------------------------------------------


def stale_warning(price_file: PriceFile, today: date, max_age_days: int = MAX_AGE_DAYS) -> str | None:
    """A warning when the snapshot is more than `max_age_days` whole days old, else None.

    The age counts from the UTC date of the fetch. This is a warning, never an exception
    (ADR-0007). `today` is always the caller's: nothing here reads the clock.
    """
    if isinstance(today, datetime):
        raise TypeError("today must be a date, not a datetime")
    fetched_on = price_file.fetched_at.astimezone(UTC).date()
    age_days = (today - fetched_on).days
    if age_days <= max_age_days:
        return None
    return (
        f"Price file for {price_file.league} is {age_days} days old (fetched {fetched_on.isoformat()}); "
        f"snapshots older than {max_age_days} days may be out of date. "
        f"Run `{FETCH_COMMAND}` to refresh it."
    )


def missing_prices(wanted_names: Iterable[str], prices: Mapping[str, PriceEntry]) -> list[str]:
    """The wanted names that have no price, sorted and listed once."""
    return sorted({name for name in wanted_names if name not in prices})
