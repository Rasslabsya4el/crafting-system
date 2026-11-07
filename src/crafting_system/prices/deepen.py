"""A thin poe.ninja line read beside the same day's trade offers; the deeper reading is the price (#616, OR-8, OR-23).

poe.ninja's exchange line of an item can rest on a few units (the Prismatic Fossil was 0.2 Chaos on a day it traded
a few; a week later it was 8 on 26.67 Chaos of volume). The trade site's bulk exchange holds the offers of the same
day. `deepen_with_trade` reads them for the names it is given and keeps, for each name, the reading with the greater
depth in units, the other one in the entry's provenance (`other`), so the price stays marked and a reader sees both.

The order of preference is: a reading of the league being priced before one of an earlier league (a previous-league
or Standard price is only ever kept when nothing of this league exists), then the greater depth; a reading with no
recorded depth loses to one that has it. A hand price, a default and a trade price already in the file are never replaced.
Nothing here reads the clock or sends a request: `read(name)` is the caller's.
"""

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date

from .price_file import PriceEntry, PriceFile
from .provenance import EXCHANGE, HISTORY, PREVIOUS_LEAGUE, STANDARD, TRADE, WATCH, Provenance
from .trade_exchange import DEFAULT_K, ExchangeReading
from .trade_market import TRADE_SOURCE

REPLACEABLE = (EXCHANGE, HISTORY, WATCH, PREVIOUS_LEAGUE, STANDARD)  # the kinds a trade reading may replace
EARLIER_LEAGUE = (PREVIOUS_LEAGUE, STANDARD)


def exchange_entry(reading: ExchangeReading, league: str, day: date, item_id: str, k: int = DEFAULT_K) -> PriceEntry:
    """The price entry of a reading of the bulk exchange: source `trade-api`, provenance `trade` with the units the offers hold."""
    note = (
        f"mean of the {reading.used} cheapest instant offers of the trade site's bulk exchange, "
        f"{reading.depth:g} units in them, {reading.total} offers in all, {day.isoformat()}"
    )
    detail = {"league": league, "date": day.isoformat(), "exchange": item_id, "listings": reading.total, "used": reading.used, "k": k}
    return PriceEntry(reading.chaos, TRADE_SOURCE, note, detail, Provenance(TRADE, league, day.isoformat(), reading.depth, "units", reading.used))


def _depth(entry: PriceEntry) -> float | None:
    return entry.provenance.depth if entry.provenance is not None else None


def _rank(entry: PriceEntry, league: str) -> tuple[int, float]:
    """Higher is better: a reading of this league before an earlier one, then the greater depth (none = below any)."""
    p = entry.provenance
    earlier = p is not None and (p.kind in EARLIER_LEAGUE or p.league != league)
    depth = _depth(entry)
    return (0 if earlier else 1, -1.0 if depth is None else depth)


def _with_other(chosen: PriceEntry, other: PriceEntry) -> PriceEntry:
    """`chosen` with the reading it was preferred to written into its provenance (`other`)."""
    p = chosen.provenance
    if p is None:
        return chosen
    kind = other.provenance.kind if other.provenance is not None else other.source
    reading = {"kind": kind, "chaos": other.chaos, "depth": _depth(other)}
    return replace(chosen, provenance=replace(p, other=reading))


def deepen_with_trade(
    price_file: PriceFile,
    names: Iterable[str],
    read: Callable[[str], PriceEntry | None],
    below_units: float | None = None,
) -> tuple[PriceFile, list[str]]:
    """`price_file` with, for each of `names`, the deeper of its price and the trade reading `read(name)`; returns (file, warnings).

    A name is read when it has no price, or its price is of a kind a trade reading may replace and its depth is not recorded or
    is below `below_units` (None reads every such name). `read` returns an entry (see `exchange_entry`) or None when the site has
    nothing. The warnings say which names changed and which were read and kept.
    """
    prices = dict(price_file.prices)
    warnings: list[str] = []
    for name in sorted(set(names)):
        current = prices.get(name)
        if current is not None:
            kind = current.provenance.kind if current.provenance is not None else None
            if kind not in REPLACEABLE:
                continue
            depth = _depth(current)
            if below_units is not None and depth is not None and depth >= below_units and kind not in EARLIER_LEAGUE:
                continue
        found = read(name)
        if found is None:
            if current is None:
                warnings.append(f"{name}: no price from poe.ninja and no offer on the trade site")
            continue
        if current is None:
            prices[name] = found
            warnings.append(f"{name}: no poe.ninja price; the trade offers give {found.chaos:g} Chaos on {_depth(found):g} units")
        elif _rank(found, price_file.league) > _rank(current, price_file.league):
            prices[name] = _with_other(found, current)
            warnings.append(f"{name}: the trade offers are deeper ({_depth(found):g} units, {found.chaos:g} Chaos) than {current.source} ({_depth(current)} units, {current.chaos:g} Chaos); taken")
        else:
            prices[name] = _with_other(current, found)
            warnings.append(f"{name}: kept {current.source} ({_depth(current)} units, {current.chaos:g} Chaos) over the trade offers ({_depth(found):g} units, {found.chaos:g} Chaos)")
    return replace(price_file, prices=prices), warnings
