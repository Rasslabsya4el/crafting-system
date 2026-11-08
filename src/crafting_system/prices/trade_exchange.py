"""The trade site's bulk exchange: the instant offers for a currency-like item, read beside a thin poe.ninja line (#616).

A fossil, an essence, a lifeforce or an oil is bought on the trade site in the bulk exchange: each offer says how
many units it holds (`stock`) and what it asks for them (`exchange.amount` of a currency for `item.amount` units).
`read_offers` turns the offers of one item into a reading, by the owner's rule for a trade price (OR-8): the mean of the
`k` cheapest offers, per unit, five by default, whatever the number of offers the book holds (a book of three offers is the mean
of the three; no count of offers decides, OR-12). The depth of the reading is the units those offers hold. Nothing here
sends a request or reads the clock; `trade_pricing.read_exchange` does both.

The site's answer is `{"result": {offer id: {"listing": {"offers": [{"exchange": {"currency", "amount"},
"item": {"amount", "stock"}}]}}}, "total": n}`; an offer paid in a currency this code has no rate for, or with no
usable amounts, is dropped and counted, never guessed.
"""

import statistics
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_K = 5
HAVE = ("chaos", "divine")  # the currencies an offer may ask in; the others are dropped


@dataclass(frozen=True)
class ExchangeReading:
    chaos: float  # the mean per unit of the `used` cheapest offers
    depth: float  # the units those offers hold
    used: int  # the offers in the mean
    offers: int  # the offers the answer holds that could be priced
    total: int  # the search `total`
    dropped: int  # offers that could not be priced


def static_ids(answer: Mapping[str, Any]) -> dict[str, str]:
    """Text -> exchange id from the `data/static` answer ("Prismatic Fossil" -> "prismatic-fossil"); the first of a text wins."""
    found: dict[str, str] = {}
    groups = answer.get("result")
    for group in groups if isinstance(groups, list) else []:
        entries = group.get("entries") if isinstance(group, dict) else None
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("text"), str):
                found.setdefault(entry["text"], entry["id"])
    return found


def exchange_body(item_id: str, have: tuple[str, ...] = HAVE) -> dict[str, Any]:
    """The query: offers of `item_id` that ask for one of the `have` currencies, the cheapest first, online sellers."""
    return {"query": {"status": {"option": "online"}, "have": list(have), "want": [item_id]}, "sort": {"have": "asc"}, "engine": "new"}


def _positive(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def read_offers(answer: Mapping[str, Any], rates: Mapping[str, float], k: int = DEFAULT_K) -> ExchangeReading | None:
    """The reading of one exchange answer, or None when no offer can be priced.

    `rates` is the Chaos value of one unit of each currency an offer may ask (`{"chaos": 1.0, "divine": 372.2}`).
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")
    result = answer.get("result")
    total = answer.get("total")
    priced: list[tuple[float, float]] = []  # (Chaos per unit, units held)
    dropped = 0
    for entry in result.values() if isinstance(result, dict) else []:
        listing = entry.get("listing") if isinstance(entry, dict) else None
        offers = listing.get("offers") if isinstance(listing, dict) else None
        for offer in offers if isinstance(offers, list) else []:
            asks = offer.get("exchange") if isinstance(offer, dict) else None
            gives = offer.get("item") if isinstance(offer, dict) else None
            rate = rates.get(asks.get("currency")) if isinstance(asks, dict) else None
            if not (isinstance(asks, dict) and isinstance(gives, dict) and rate and _positive(asks.get("amount")) and _positive(gives.get("amount"))):
                dropped += 1
                continue
            stock = gives.get("stock")
            units = float(stock) if _positive(stock) else float(gives["amount"])
            priced.append((float(asks["amount"]) * rate / float(gives["amount"]), units))
    if not priced:
        return None
    cheapest = sorted(priced)[:k]
    price = statistics.fmean(each for each, _ in cheapest)
    return ExchangeReading(
        chaos=float(price),
        depth=sum(units for _, units in cheapest),
        used=len(cheapest),
        offers=len(priced),
        total=total if isinstance(total, int) and not isinstance(total, bool) else len(priced),
        dropped=dropped,
    )
