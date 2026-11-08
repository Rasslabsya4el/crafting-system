"""A thin poe.ninja line read beside the same day's trade offers; the deeper reading is the price (#616, OR-8, OR-23).

poe.ninja's exchange line of an item can rest on a few units (the Prismatic Fossil was 0.2 Chaos on a day it traded
a few; a week later it was 8 on 26.67 Chaos of volume). The trade site's bulk exchange holds the offers of the same
day. `deepen_with_trade` reads them for the names it is given and keeps, for each name, the reading with the greater
depth in units, the other one in the entry's provenance (`other`), so the price stays marked and a reader sees both.

The order of preference is: a reading of the league being priced before one of an earlier league (a previous-league
or Standard price is only ever kept when nothing of this league exists), then the greater depth **in units**; a reading with no
recorded depth loses to one that has it. A trade book is read as the mean of its cheapest few offers whatever their number
(OR-8), and its depth is the units the offers priced hold: no count of offers decides, a book of three offers with 94 units
beats a line of 0.5 units (OR-12). A hand price, a default and a trade price already in the file are never replaced.
Nothing here reads the clock or sends a request: `read(name)` is the caller's.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date

from .price_file import CHAOS_ORB, DIVINE_ORB, PriceEntry, PriceFile
from .provenance import EXCHANGE, HISTORY, KIND_OF_SOURCE, PREVIOUS_LEAGUE, STANDARD, TRADE, WATCH, Provenance
from .trade_exchange import DEFAULT_K, ExchangeReading
from .trade_market import TRADE_SOURCE

REPLACEABLE = (EXCHANGE, HISTORY, WATCH, PREVIOUS_LEAGUE, STANDARD)  # the kinds a trade reading may replace
EARLIER_LEAGUE = (PREVIOUS_LEAGUE, STANDARD)
UNITS_OF_THE_FILE = (CHAOS_ORB, DIVINE_ORB)  # the Chaos Orb is the unit of every price and the Divine Orb's price is the file's rate: no trade reading replaces either


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


class ReadStopped(Exception):
    """`read` raises this when the trade site cannot be read any more (blocked, or the run's request budget is spent); `reason` says which."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Deepened:
    """The outcome of `deepen_with_trade`: the file, the warnings, and the names left unread with the reason each was (empty when every read was made)."""

    price_file: PriceFile
    warnings: list[str]
    unread: dict[str, str]


def wants_trade_reading(current: PriceEntry | None, below_units: float | None) -> bool:
    """Whether a name with price `current` (None: no price) is read on the trade site: it has no price, or its price is of a kind a trade
    reading may replace and its depth is not recorded or is below `below_units` (None reads every such name)."""
    if current is None:
        return True
    kind = current.provenance.kind if current.provenance is not None else KIND_OF_SOURCE.get(current.source)  # a line with no provenance is read from its source
    if kind not in REPLACEABLE:
        return False
    depth = _depth(current)
    return not (below_units is not None and depth is not None and depth >= below_units and kind not in EARLIER_LEAGUE)


def mark_unread(price_file: PriceFile, names: Iterable[str], reason: str, below_units: float | None = None) -> tuple[PriceFile, list[str]]:
    """`price_file` with the trade offers of each name that has a price and would have been read marked as unread (`Provenance.trade_unread`);
    returns (file, the names that would have been read, priced or not), so the caller reports every one."""
    prices = dict(price_file.prices)
    left: list[str] = []
    for name in sorted(set(names)):
        current = prices.get(name)
        if name in UNITS_OF_THE_FILE or not wants_trade_reading(current, below_units):
            continue
        left.append(name)
        if current is not None and current.provenance is not None:
            prices[name] = replace(current, provenance=replace(current.provenance, trade_unread=reason))
    return replace(price_file, prices=prices), left


def deepen_with_trade(
    price_file: PriceFile,
    names: Iterable[str],
    read: Callable[[str], PriceEntry | None],
    below_units: float | None = None,
) -> Deepened:
    """`price_file` with, for each of `names`, the deeper of its price and the trade reading `read(name)`.

    A name is read when it has no price, or its price is of a kind a trade reading may replace and its depth is not recorded or
    is below `below_units` (None reads every such name). `read` returns an entry (see `exchange_entry`) or None when the site has
    nothing, or raises `ReadStopped`: the names not yet read are then left as they are, each with a price marked unread, and returned
    in `unread` with the reason. The warnings say which names changed and which were read and kept.
    """
    prices = dict(price_file.prices)
    warnings: list[str] = []
    unread: dict[str, str] = {}
    todo = sorted(set(names))
    for position, name in enumerate(todo):
        current = prices.get(name)
        if name in UNITS_OF_THE_FILE or not wants_trade_reading(current, below_units):
            continue
        try:
            found = read(name)
        except ReadStopped as stopped:
            rest, left = mark_unread(replace(price_file, prices=prices), todo[position:], stopped.reason, below_units)
            prices = dict(rest.prices)
            unread = dict.fromkeys(left, stopped.reason)
            break
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
    return Deepened(replace(price_file, prices=prices), warnings, unread)
