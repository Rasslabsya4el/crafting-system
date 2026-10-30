"""The price fetch: poe.ninja's current overviews, then the fallback chain for the names still unpriced (ADR-0007, #40).

The transport is injected as `get_json(url) -> parsed JSON`; `http_get_json` is the real one. The clock is
injected too (`now`): nothing here reads it. The fetcher never touches the hand-written overrides file; it
only builds a `PriceFile` for the caller to write.

Priced from the current overviews: currency, fossils, resonators and essences (exchange), then beasts and
bases (stash). A stash line seen fewer than `MIN_COUNT` times, or an exchange line traded on zero volume, is
too thin to price: it is listed in `FetchResult.thin`. A `wanted` name left without a price becomes a `Gap`
and goes down the stages (`DEFAULT_STAGES`: poe.ninja history, poe.watch, the previous league). The history
endpoints are undocumented, so a stage whose source fails prices nothing and the name stays in `missing`.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .fallbacks import MIN_COUNT, Context, Gap, Stage, run_stages
from .http_json import GetJson, SourceError
from .ninja_history import ninja_history_stage
from .ninja_items import BASE_TYPE, STASH_TYPES, StashLine, parse_stash_overview
from .poe_ninja import BASE_URL, OVERVIEW_TYPES, SOURCE, api_url, history_slug, parse_overview
from .poe_watch import poe_watch_stage
from .previous_league import previous_league_stage
from .price_file import CHAOS_ORB, DIVINE_ORB, PriceEntry, PriceFile, missing_prices
from .price_names import parse_base_price_name

DEFAULT_STAGES: tuple[Stage, ...] = (ninja_history_stage, poe_watch_stage, previous_league_stage)


@dataclass(frozen=True)
class FetchResult:
    price_file: PriceFile
    warnings: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # wanted names still without a price
    thin: list[str] = field(default_factory=list)  # names of current lines too thin to price, sorted


def fetch_price_file(
    get_json: GetJson,
    now: datetime,
    wanted: Iterable[str] | None = None,
    league: str | None = None,
    previous_league: str | None = None,
    stages: Sequence[Stage] = DEFAULT_STAGES,
) -> FetchResult:
    """Build a price file for `league` (default: the first league poe.ninja lists).

    A partial fetch never makes a file: the leagues call and every category (Currency, Fossil, Resonator,
    Essence, Beast, BaseType) must answer with at least one usable line, else a `SourceError` is raised.
    `wanted` names that the overviews do not price (or only on a thin line) are walked down `stages`, with
    the 7 days ending on `now`'s UTC date as the window; those still unpriced come back in `missing`.
    """
    if now.tzinfo is None:
        raise ValueError("`now` needs a time zone (pass a UTC time)")
    if league is not None and not league.strip():
        raise ValueError("league must not be blank")
    fetched_at = now.astimezone(UTC).replace(microsecond=0)
    wanted_names = sorted(set(wanted or ()))
    league = league if league is not None else _current_league(get_json)

    prices: dict[str, PriceEntry] = {}
    thin_exchange: dict[str, str] = {}  # zero-volume line name -> its details id
    thin_stash: dict[str, StashLine] = {}
    divine_rate: float | None = None
    for kind in OVERVIEW_TYPES:
        overview = _category(get_json, kind, "exchange/current/overview", league, parse_overview)
        if kind == "Currency":
            divine_rate = overview.divine_rate
        for line in overview.lines:
            if line.thin:
                thin_exchange.setdefault(line.name, line.details_id)
            else:
                prices.setdefault(line.name, PriceEntry(line.chaos, SOURCE))
    for kind in STASH_TYPES:
        lines = _category(
            get_json, kind, "stash/current/item/overview", league, lambda data: parse_stash_overview(data, kind)
        )
        for stash_line in lines:
            if stash_line.count < MIN_COUNT:
                thin_stash.setdefault(stash_line.key, stash_line)
            else:
                prices.setdefault(stash_line.key, PriceEntry(stash_line.chaos, SOURCE))

    prices[CHAOS_ORB] = PriceEntry(1.0, SOURCE)
    chaos_per_divine = _chaos_per_divine(prices, divine_rate)
    prices.setdefault(DIVINE_ORB, PriceEntry(chaos_per_divine, SOURCE))
    thin = sorted(name for name in (*thin_exchange, *thin_stash) if name not in prices)

    gaps = [_gap(name, thin_exchange, thin_stash) for name in wanted_names if name not in prices]
    found, warnings = run_stages(stages, get_json, Context(league, fetched_at.date(), previous_league), gaps)
    gap_names = {gap.name for gap in gaps}
    prices.update({name: entry for name, entry in found.items() if name in gap_names})
    for name in wanted_names:
        if name not in prices and (name in thin_exchange or name in thin_stash):
            warnings.append(
                f"{name}: current line is too thin (fewer than {MIN_COUNT} observations or no trade volume) "
                "and no fallback gave a price; dropped"
            )

    price_file = PriceFile(league, fetched_at, chaos_per_divine, prices)
    return FetchResult(price_file, warnings, missing_prices(wanted_names, prices), thin)


def _gap(name: str, thin_exchange: dict[str, str], thin_stash: dict[str, StashLine]) -> Gap:
    """What the fallback sources need to look `name` up, from the kind of line it has (or lacks)."""
    if name in thin_exchange:
        return Gap(name, exchange_id=thin_exchange[name])
    if name in thin_stash:
        line = thin_stash[name]
        base = parse_base_price_name(name) if line.kind == BASE_TYPE else None
        return Gap(name, stash_kind=line.kind, stash_id=line.line_id, base=base)
    base = parse_base_price_name(name)
    if base is not None:
        return Gap(name, stash_kind=BASE_TYPE, base=base)
    return Gap(name, exchange_id=history_slug(name))


def _category(get_json: GetJson, kind: str, route: str, league: str, parse: Callable[[Any], Any]) -> Any:
    """One overview of `kind`, parsed; a failure names the category and says the old file was kept."""
    try:
        return parse(get_json(api_url(route, league=league, type=kind)))
    except SourceError as error:
        raise SourceError(
            f"the {kind} prices failed: {error}; no price file was written, the old price file was kept"
        ) from error


def _current_league(get_json: GetJson) -> str:
    leagues = get_json(f"{BASE_URL}/leagues")
    first = leagues[0] if isinstance(leagues, list) and leagues else None
    league = first.get("id") if isinstance(first, dict) else None
    if not isinstance(league, str) or not league.strip():
        raise SourceError("poe.ninja returned no usable league list")
    return league


def _chaos_per_divine(prices: dict[str, PriceEntry], divine_rate: float | None) -> float:
    if DIVINE_ORB in prices:
        return prices[DIVINE_ORB].chaos
    if divine_rate is not None:
        return 1 / divine_rate
    raise SourceError("the Currency overview has no Divine Orb price")
