"""The trade site's bulk exchange: the instant offers for a currency-like item, read beside a thin poe.ninja line (#616).

A fossil, an essence, a lifeforce or an oil is bought on the trade site in the bulk exchange: each offer says how
many units it holds (`stock`) and what it asks for them (`exchange.amount` of a currency for `item.amount` units).
`read_offers` turns the offers of one item into a reading by the owner's rule for a trade price (OR-8, as amended by #718):

* **The price** is the mean of the cheapest few units, five by default. On the bulk exchange a buyer takes units from an offer,
  not the offer whole, so a unit is what a listing is on the item search: one thing bought at one price. One offer of 80 units
  at 1 c and four of 1 unit at 20 c price at 1 c (the five cheapest units are all in the first offer), not at the 16.2 c of the
  plain mean of five offers nor at a mean weighted by the units of five offers, where one large dear stock sets the price
  (the 134,936 c Muttering Essence of Hatred of #706). For an item listing (one listing, one unit) it is the plain mean of five.
* **The depth** is the units held by the offers those cheapest units come from: what can be bought at about that price. A plan
  that buys more is marked (`price_marks`, "price on N units"); the price is not raised by a walk down the book (#726).
* **The market** is the rule of #355 on the offers: at least `DEFAULT_MIN_LISTINGS` offers in the book and `MIN_USABLE` priced
  (`trade_market.classify`). A thin book is a thin market: `deepen` offers the league's last deep price marked old, else this
  mean marked thin, never a plain price (OR-8). Every troll-priced book of the end of Allflame had five offers or fewer.

Nothing here sends a request or reads the clock;
`trade_pricing.read_exchange` does both.

The site's answer is `{"result": {offer id: {"listing": {"offers": [{"exchange": {"currency", "amount"},
"item": {"amount", "stock"}}]}}}, "total": n}`; an offer paid in a currency this code has no rate for, or with no
usable amounts, is dropped and counted, never guessed.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .trade_market import classify

DEFAULT_K = 5
HAVE = ("chaos", "divine")  # the currencies an offer may ask in; the others are dropped


@dataclass(frozen=True)
class ExchangeReading:
    chaos: float  # the mean price of the `k` cheapest units (all the units there are when fewer)
    depth: float  # the units held by the offers those units come from
    used: int  # the offers those units come from
    offers: int  # the offers the answer holds that could be priced
    total: int  # the search `total`: the offers in the book
    dropped: int  # offers that could not be priced
    state: str = "quoted"  # the market rule on the book (`trade_market.classify(total, offers)`): `quoted` or `thin`


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
    """The reading of one exchange answer, or None when no offer can be priced: the mean of the `k` cheapest units, each offer's
    units at its price per unit, the cheapest first.

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
    wanted = float(k)
    cost = taken = depth = 0.0
    used = 0
    for each, units in sorted(priced):
        if taken >= wanted:
            break
        part = min(units, wanted - taken)
        cost, taken, depth, used = cost + each * part, taken + part, depth + units, used + 1
    book = total if isinstance(total, int) and not isinstance(total, bool) else len(priced)
    return ExchangeReading(
        chaos=cost / taken,
        depth=depth,
        used=used,
        offers=len(priced),
        total=book,
        dropped=dropped,
        state=classify(book, len(priced)),
    )
