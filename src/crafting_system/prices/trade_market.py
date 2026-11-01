"""The market rule of a trade price and what the planner may be offered (#355, ADR-0061).

A trade search ends in one of three recorded states:

- `quoted`: the site has at least `DEFAULT_MIN_LISTINGS` listings (the search `total`) and at least
  `MIN_USABLE` of the fetched ones can be turned into Chaos. The price is the mean of the `k` cheapest
  usable listings and sits in the price file as a `trade-api` entry with its listing total, its usable
  count and its date.
- `thin`: the site has listings but not enough of them (fewer than the rail, or too few usable). Kept
  as a `MarketRecord` with its counts, never offered.
- `none`: a successful search answered `total = 0`. Kept as a `MarketRecord`, never offered.

The listing-count rail (default 10) is a setting, so `offer` takes it and says which rail cut an offer
and at what value, which lets two rail values be compared later. A record, quoted or not, is fresh for
`MAX_AGE_DAYS` (7) whole days; an older one is `stale` and is not offered, and a refresher would ask again.

Nothing here reads a clock: the caller passes `today`.
"""

from dataclasses import dataclass
from datetime import date

from .price_file import MARKET_NONE, MARKET_THIN, MAX_AGE_DAYS, PriceEntry, PriceFile

TRADE_SOURCE = "trade-api"

QUOTED = "quoted"
THIN = MARKET_THIN
NONE = MARKET_NONE
STALE = "stale"  # a record older than the limit (or without a date): not offered, ask again
UNKNOWN = "unknown"  # nothing recorded under the name

DEFAULT_MIN_LISTINGS = 10  # the market rule: listings on the site (#337, owner Q4)
MIN_USABLE = 3  # listings that can be priced; fewer cannot make a mean worth quoting


def classify(listings: int, usable: int, min_listings: int = DEFAULT_MIN_LISTINGS) -> str:
    """`none`, `thin` or `quoted` for a search of `listings` on the site, `usable` of them priced."""
    if listings <= 0:
        return NONE
    if listings < min_listings or usable < MIN_USABLE:
        return THIN
    return QUOTED


def age_in_days(stamp: object, today: date) -> int | None:
    """Whole days from the ISO date `stamp` to `today`; None when `stamp` is not a date."""
    try:
        searched_on = date.fromisoformat(stamp) if isinstance(stamp, str) else None
    except ValueError:
        return None
    return None if searched_on is None else (today - searched_on).days


@dataclass(frozen=True)
class TradeOffer:
    """What the price file says about one name, for the planner and for a refresher.

    `state` is one of `quoted`, `thin`, `none`, `stale`, `unknown`; `entry` is the price and is set only
    when the name is offered (`quoted` and fresh). `reason` says what cut a name that is not offered,
    with the value that cut it (the rail or the age). `age_days` is None when nothing is recorded or the
    record has no date.
    """

    name: str
    state: str
    entry: PriceEntry | None = None
    reason: str | None = None
    age_days: int | None = None
    listings: int | None = None
    usable: int | None = None

    @property
    def offered(self) -> bool:
        return self.entry is not None

    @property
    def fresh(self) -> bool:
        """A record exists and is within the age limit: a refresher need not ask again."""
        return self.state in (QUOTED, THIN, NONE)


def offer(
    price_file: PriceFile,
    name: str,
    today: date,
    min_listings: int = DEFAULT_MIN_LISTINGS,
    max_age_days: int = MAX_AGE_DAYS,
) -> TradeOffer:
    """The trade price of `name` if it may be offered, else the state that cuts it and why.

    A price is offered when it is a fresh `trade-api` price whose listing total meets `min_listings` and
    whose usable count meets `MIN_USABLE`. The state is judged on the stored counts with the rail given
    now, so raising the rail cuts a price that was quoted under a lower one. A price file's league other
    than the record's own league is not offered (the record is another league's market).
    """
    entry = price_file.prices.get(name)
    record = price_file.markets.get(name)
    if entry is not None and entry.source == TRADE_SOURCE:
        return _offer_from_entry(price_file, name, entry, today, min_listings, max_age_days)
    if record is not None:
        age = (today - record.date).days
        if age < 0:
            return TradeOffer(name, STALE, reason="record is dated in the future", age_days=age)
        if record.league != price_file.league:
            return TradeOffer(name, UNKNOWN, reason=f"recorded for league {record.league}", age_days=age)
        if age > max_age_days:
            return TradeOffer(
                name, STALE, reason=f"{record.state} record is {age} days old (limit {max_age_days})",
                age_days=age, listings=record.listings, usable=record.usable,
            )
        return TradeOffer(
            name, record.state, reason=_count_reason(record.state, record.listings, record.usable, min_listings),
            age_days=age, listings=record.listings, usable=record.usable,
        )
    return TradeOffer(name, UNKNOWN, reason="no trade price recorded")


def _offer_from_entry(
    price_file: PriceFile, name: str, entry: PriceEntry, today: date, min_listings: int, max_age_days: int
) -> TradeOffer:
    detail = entry.detail or {}
    listings = detail.get("listings")
    usable = detail.get("usable", detail.get("used"))  # `used` (at most k) is all an older entry has
    counts = {
        "listings": listings if isinstance(listings, int) and not isinstance(listings, bool) else None,
        "usable": usable if isinstance(usable, int) and not isinstance(usable, bool) else None,
    }
    age = age_in_days(detail.get("date"), today)
    if detail.get("league") not in (None, price_file.league):
        return TradeOffer(name, UNKNOWN, reason=f"price of league {detail['league']}", age_days=age, **counts)
    if age is None:
        return TradeOffer(name, STALE, reason="trade price has no usable date", **counts)
    if age < 0:
        return TradeOffer(name, STALE, reason="trade price is dated in the future", age_days=age, **counts)
    if age > max_age_days:
        return TradeOffer(
            name, STALE, reason=f"trade price is {age} days old (limit {max_age_days})", age_days=age, **counts
        )
    if counts["listings"] is None or counts["usable"] is None:
        return TradeOffer(name, UNKNOWN, reason="trade price has no listing count", age_days=age, **counts)
    state = classify(counts["listings"], counts["usable"], min_listings)
    if state != QUOTED:
        reason = _count_reason(state, counts["listings"], counts["usable"], min_listings)
        return TradeOffer(name, state, reason=reason, age_days=age, **counts)
    return TradeOffer(name, QUOTED, entry=entry, age_days=age, **counts)


def _count_reason(state: str, listings: int, usable: int, min_listings: int) -> str:
    if state == NONE:
        return "the trade site has no listings (total 0)"
    if state == THIN and listings < min_listings:
        return f"{listings} listings on the site, the listing-count rail needs {min_listings}"
    if state == THIN and usable < MIN_USABLE:
        return f"{usable} usable listings, at least {MIN_USABLE} are needed"
    return "recorded thin"
