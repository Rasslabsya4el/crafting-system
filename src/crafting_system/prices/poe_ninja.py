"""The poe.ninja exchange overviews: current prices of currency, fossils, resonators and essences (ADR-0007).

The transport is injected as `get_json(url) -> parsed JSON`; `http_get_json` is the real one (`SourceError`
is re-exported here for the callers that import both). Nothing here reads the clock. The fetch that
puts these overviews, the stash overviews and the fallback chain together is in `fetch.py`.
"""

import re
import urllib.parse
from dataclasses import dataclass
from typing import Any

from .http_json import TIMEOUT_SECONDS, USER_AGENT, GetJson, SourceError, http_get_json  # noqa: F401  (re-exported)
from .price_file import is_price

BASE_URL = "https://poe.ninja/poe1/api/economy"
OVERVIEW_TYPES = ("Currency", "Fossil", "Resonator", "Essence")
SOURCE = "poe.ninja"
HISTORY_SOURCE = "poe.ninja-history"


def history_slug(name: str) -> str:
    """The id poe.ninja gives an item: lowercase, apostrophes dropped, other gaps as hyphens.

    "Hollow Fossil" -> "hollow-fossil", "Jeweller's Orb" -> "jewellers-orb" (checked against
    every Currency, Essence, Fossil and Resonator `detailsId` of the 3.29 data).
    """
    lowered = name.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def api_url(route: str, **params: str) -> str:
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{BASE_URL}/{route}?{query}"


# --- current overviews ---------------------------------------------------------------------


@dataclass(frozen=True)
class ExchangeLine:
    name: str
    chaos: float
    details_id: str
    thin: bool  # traded on zero volume: the price is not trustworthy


@dataclass(frozen=True)
class Overview:
    lines: list[ExchangeLine]
    divine_rate: float | None  # Divine Orbs per Chaos Orb, from `core.rates`


def parse_overview(data: Any) -> Overview:
    """The priced lines of an exchange overview; a changed shape or no usable line is a `SourceError`."""
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
        if isinstance(item, dict) and isinstance(item.get("id"), str) and is_text(item.get("name"))
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
        details_id = item.get("detailsId") if is_text(item.get("detailsId")) else item["id"]
        parsed.append(ExchangeLine(item["name"], float(line["primaryValue"]), details_id, thin))

    if not parsed:
        raise SourceError("no line with a usable price")

    rates = core.get("rates")
    rate = rates.get("divine") if isinstance(rates, dict) else None
    return Overview(parsed, float(rate) if is_price(rate) else None)


def is_text(value: object) -> bool:
    """A string with something other than blanks in it."""
    return isinstance(value, str) and bool(value.strip())
