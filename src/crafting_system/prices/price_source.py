"""Which price a start item is priced with, and both prices side by side (#357, ADR-0061 decision 2).

The price source is a profile setting (with the #323 user inputs, apart from the target): `ninja`, `trade` or `both`.

- `ninja`: the poe.ninja base row, nothing else. A fractured base has no poe.ninja row, so it is not offered.
- `trade`: the trade price only (`trade_market.offer`: instant buyout, fresh, the market rule met), no fallback.
- `both` (the default): the trade price; when it is missing or stale (any reason `offer` gives), the poe.ninja row,
  and the price is marked as the fallback it is. With both prices at hand the answer carries them side by side and
  flags a gap above `gap_percent` (default 20).

No price from the chosen source means no option (`SourcedPrice.chaos` is None and `reason` says why). A hand override
of the name wins over every source and setting, as it does everywhere else (ADR-0007).

The gap is the dearer price over the cheaper one, in percent (125 against 100 is 25), so it does not depend on which
of the two is the planner's. It is flagged when strictly above the threshold. The poe.ninja row of a name whose trade
price covers it sits in the price file's `ninja` table (`PriceFile.ninja`); a name that only has a poe.ninja row keeps
it in `prices`. A poe.ninja row does not prove that an instant-buyout listing exists, and the marks say so.

Nothing here reads a clock or the network: the caller passes `today`.
"""

import math
from dataclasses import dataclass
from datetime import date

from ..config import PRICE_SOURCES
from .poe_ninja import HISTORY_SOURCE
from .poe_ninja import SOURCE as NINJA_SOURCE
from .price_file import MAX_AGE_DAYS, OVERRIDE_SOURCE, PriceEntry, PriceFile
from .price_names import canonical_price_name
from .trade_market import DEFAULT_MIN_LISTINGS, TradeOffer, offer

NINJA = "ninja"
TRADE = "trade"
BOTH = "both"
DEFAULT_PRICE_SOURCE = BOTH
DEFAULT_GAP_PERCENT = 20.0

NINJA_SOURCES = (NINJA_SOURCE, HISTORY_SOURCE)  # entries that are a poe.ninja row of this league

USED_TRADE = "trade"
USED_NINJA = "poe.ninja"
USED_OVERRIDE = "override"
USED_NONE = "none"

NINJA_NOT_PROOF = "a poe.ninja row does not prove an instant-buyout listing exists"


def check_price_source(value: object) -> str:
    """`value` if it is one of `ninja`, `trade`, `both`; else a `ValueError` that names the three."""
    if not isinstance(value, str) or value not in PRICE_SOURCES:
        raise ValueError(f"the price source must be one of {', '.join(PRICE_SOURCES)}, got {value!r}")
    return value


def check_gap_percent(value: object) -> float:
    """`value` as a gap threshold in percent: a finite number above zero (not a bool); else a `ValueError`."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"the price gap flag must be a number of percent above zero, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class SourcedPrice:
    """What the planner prices `name` with, and what both sources say.

    `chaos` is the planner's price, None when no option is offered (`reason` says why). `used` is `trade`, `poe.ninja`,
    `override` or `none`. `fallback` is true when the setting asked for the trade price and the poe.ninja row stands in
    for it. `trade` is what the price file says about the trade price (offered, or the state and rail that cut it);
    None when the setting is `ninja`. `trade_chaos` and `ninja_chaos` are the two prices when each exists and was
    consulted, `gap_percent` the dearer over the cheaper in percent when both exist under `both`, `gap_flagged` whether it
    is above the threshold. `marks` are the words the answer prints with the price.
    """

    name: str
    setting: str
    used: str
    chaos: float | None
    fallback: bool = False
    trade: TradeOffer | None = None
    trade_chaos: float | None = None
    ninja_chaos: float | None = None
    gap_percent: float | None = None
    gap_flagged: bool = False
    gap_threshold: float = DEFAULT_GAP_PERCENT
    reason: str | None = None
    marks: tuple[str, ...] = ()

    @property
    def offered(self) -> bool:
        return self.chaos is not None

    @property
    def side_by_side(self) -> bool:
        """Both prices are at hand (only under `both`)."""
        return self.trade_chaos is not None and self.ninja_chaos is not None

    @property
    def source_label(self) -> str:
        """The source of the planner's price as the start line prints it."""
        if self.used == USED_TRADE and self.trade is not None and self.trade.entry is not None:
            return f"trade-api, {self.trade.listings} listings, {self.trade.age_days} d old"
        if self.used == USED_NINJA:
            return "poe.ninja (fallback: trade price not usable)" if self.fallback else "poe.ninja"
        return self.used if self.used != USED_NONE else "no price"

    def lines(self) -> list[str]:
        """The price text under a start option: the price used with its marks, both prices side by side, the gap flag."""
        if self.chaos is None:
            return [f"price source {self.setting}: no price, {self.reason}"]
        out = [f"price source {self.setting}: {self.chaos:,.2f} Chaos [{self.source_label}]"]
        out.extend(f"  {mark}" for mark in self.marks)
        if self.side_by_side:
            assert self.trade_chaos is not None and self.ninja_chaos is not None and self.gap_percent is not None
            flag = f"; GAP over {self.gap_threshold:g}%: check before relying on it" if self.gap_flagged else ""
            out.append(
                f"  trade {self.trade_chaos:,.2f} Chaos | poe.ninja {self.ninja_chaos:,.2f} Chaos | gap {self.gap_percent:.1f}%{flag}"
            )
        return out

    def document(self) -> dict:
        """The JSON block of the price: every field a reader needs, numbers or None."""
        return {
            "name": self.name,
            "setting": self.setting,
            "used": self.used,
            "chaos": self.chaos,
            "fallback": self.fallback,
            "trade_chaos": self.trade_chaos,
            "ninja_chaos": self.ninja_chaos,
            "gap_percent": self.gap_percent,
            "gap_flagged": self.gap_flagged,
            "gap_threshold_percent": self.gap_threshold,
            "reason": self.reason,
            "marks": list(self.marks),
        }


def ninja_row(price_file: PriceFile, name: str) -> PriceEntry | None:
    """The poe.ninja row of `name`: the `ninja` table first (it sits there beside a trade price), else a poe.ninja `prices` entry."""
    beside = price_file.ninja.get(name)
    if beside is not None:
        return beside
    entry = price_file.prices.get(name)
    return entry if entry is not None and entry.source in NINJA_SOURCES else None


def gap_percent(first: float, second: float) -> float:
    """The dearer of two positive prices over the cheaper, in percent."""
    low, high = min(first, second), max(first, second)
    return (high - low) * 100.0 / low  # not high / low - 1: that gives 10.000000000000009 for 110 against 100


def source_price(
    price_file: PriceFile,
    name: str,
    setting: str,
    today: date,
    *,
    fractured: bool = False,
    gap_threshold: float = DEFAULT_GAP_PERCENT,
    min_listings: int = DEFAULT_MIN_LISTINGS,
    max_age_days: int = MAX_AGE_DAYS,
) -> SourcedPrice:
    """The price of `name` under the price source `setting`, with the other source beside it under `both`.

    `fractured` is true for a fractured start: no poe.ninja row exists for one, so under `ninja` it is not offered and
    under `both` it is priced by the trade data alone. `min_listings` and `max_age_days` are the rails of
    `trade_market.offer`. `gap_threshold` is in percent. Raises `ValueError` for a setting or threshold that is not valid.
    """
    check_price_source(setting)
    check_gap_percent(gap_threshold)
    name = canonical_price_name(name)
    entry = price_file.prices.get(name)
    if entry is not None and entry.source == OVERRIDE_SOURCE:
        return SourcedPrice(
            name, setting, USED_OVERRIDE, entry.chaos, gap_threshold=gap_threshold, marks=("hand override of the price",)
        )
    ninja = None if fractured else ninja_row(price_file, name)
    trade = None if setting == NINJA else offer(price_file, name, today, min_listings, max_age_days)
    trade_chaos = trade.entry.chaos if trade is not None and trade.entry is not None else None

    if setting == NINJA:
        if ninja is None:
            why = "a fractured base has no poe.ninja row" if fractured else "no poe.ninja row of this name"
            return SourcedPrice(name, setting, USED_NONE, None, gap_threshold=gap_threshold, reason=why)
        return SourcedPrice(
            name, setting, USED_NINJA, ninja.chaos, ninja_chaos=ninja.chaos, gap_threshold=gap_threshold, marks=(NINJA_NOT_PROOF,)
        )

    assert trade is not None
    if trade_chaos is not None:
        beside = ninja.chaos if ninja is not None and setting == BOTH else None
        gap = gap_percent(trade_chaos, beside) if beside is not None else None
        return SourcedPrice(
            name, setting, USED_TRADE, trade_chaos, trade=trade, trade_chaos=trade_chaos, ninja_chaos=beside,
            gap_percent=gap, gap_flagged=gap is not None and gap > gap_threshold, gap_threshold=gap_threshold,
        )  # fmt: skip
    if setting == TRADE:
        return SourcedPrice(name, setting, USED_NONE, None, trade=trade, gap_threshold=gap_threshold, reason=trade.reason)
    if ninja is not None:
        mark = f"fallback: the trade price is not usable ({trade.state}: {trade.reason}), the poe.ninja row stands in"
        return SourcedPrice(
            name, setting, USED_NINJA, ninja.chaos, fallback=True, trade=trade, ninja_chaos=ninja.chaos,
            gap_threshold=gap_threshold, marks=(mark, NINJA_NOT_PROOF),
        )  # fmt: skip
    tail = "a fractured base has no poe.ninja row" if fractured else "no poe.ninja row of this name"
    return SourcedPrice(
        name, setting, USED_NONE, None, trade=trade, gap_threshold=gap_threshold, reason=f"{trade.reason}; {tail}"
    )
