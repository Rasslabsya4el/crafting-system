"""The fallback chain for a price that poe.ninja's current overviews do not give (ADR-0007, #21, #40).

A name the owner wants (`wanted`) but the current overviews cannot price is a `Gap`. The fetcher
walks the gaps down a list of stages, each a function `(get_json, context, gaps) -> StageResult`:
poe.ninja history, poe.watch for the current league, then the previous league / Standard. Every
price a stage finds is stamped (`stamped_entry`) with its source, league and date and comes with
a warning line; the gaps it priced leave the chain, the others go on to the next stage. A stage
whose source fails (`SourceError`) or answers in an unexpected shape prices nothing and never
raises: the gap stays a gap. Nothing here reads the clock: the caller passes `today`.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from .http_json import GetJson
from .price_file import PriceEntry
from .price_names import BaseKey

HISTORY_DAYS = 7  # a history fallback takes the median of the 7 days ending on its last day


@dataclass(frozen=True)
class Gap:
    """A wanted name without a current price, with what the sources need to look it up."""

    name: str  # the price-file name
    exchange_id: str | None = None  # poe.ninja exchange `details` id (currency, fossil, resonator, essence)
    stash_kind: str | None = None  # poe.ninja stash type: "BaseType" or "Beast"
    stash_id: int | None = None  # poe.ninja numeric line id, from the current stash overview
    base: BaseKey | None = None  # set when `name` is a base price name


@dataclass(frozen=True)
class Context:
    league: str  # the league being fetched
    today: date  # UTC date of the fetch
    previous_league: str | None = None  # the owner's choice; None = work it out


@dataclass(frozen=True)
class StageResult:
    prices: dict[str, PriceEntry] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


Stage = Callable[[GetJson, Context, Sequence[Gap]], StageResult]


def stamped_entry(chaos: float, source: str, league: str, day: date, note: str, **detail: object) -> PriceEntry:
    """A fallback price: `source`, plus the league and the date it is a price of in `detail`."""
    return PriceEntry(chaos, source, note, {"league": league, "date": day.isoformat(), **detail})


def run_stages(
    stages: Iterable[Stage], get_json: GetJson, context: Context, gaps: Iterable[Gap]
) -> tuple[dict[str, PriceEntry], list[str]]:
    """Run `stages` in order over `gaps`; returns (prices found, warnings). Later stages see only what is left."""
    left = list(gaps)
    prices: dict[str, PriceEntry] = {}
    warnings: list[str] = []
    for stage in stages:
        if not left:
            break
        result = stage(get_json, context, tuple(left))
        prices.update(result.prices)
        warnings.extend(result.warnings)
        left = [gap for gap in left if gap.name not in result.prices]
    return prices, warnings
