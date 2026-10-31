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

from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .fallbacks import MIN_COUNT, Context, Gap, Stage, run_stages
from .http_json import GetJson, SourceError
from .ninja_history import ninja_history_stage
from .ninja_items import BASE_TYPE, BEAST, STASH_TYPES, StashLine, parse_stash_overview
from .poe_ninja import BASE_URL, OVERVIEW_TYPES, SOURCE, api_url, history_slug, parse_overview
from .poe_watch import poe_watch_stage
from .previous_league import previous_league_stage
from .price_file import CHAOS_ORB, DIVINE_ORB, PriceEntry, PriceFile, missing_prices
from .price_names import canonical_price_name, parse_base_price_name
from .trade_pricing import current_trade_prices

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
    overrides: Collection[str] = (),
    old_price_file: PriceFile | None = None,
) -> FetchResult:
    """Build a price file for `league` (default: the first league poe.ninja lists).

    The leagues call and every exchange category (Currency, Fossil, Resonator, Essence) must answer with at
    least one usable line, else a `SourceError` is raised and no file is made. A failed stash category
    (Beast, BaseType) does not abort: it warns, its old poe.ninja prices of the same league in
    `old_price_file` stay (a beast is any old poe.ninja price that is not a base name), and the rest finishes.
    `wanted` names that the overviews do not price (or only on a thin line) are walked down `stages`, with
    the 7 days ending on `now`'s UTC date as the window; those still unpriced come back in `missing`.

    A wanted name that `overrides` (the names of the hand prices) or the trade-api prices of
    `old_price_file` for this league already cover is left out of all that: no request is spent on it and
    it is neither a gap nor `missing`. The caller's merge keeps those prices. A trade-api price older than
    the stale limit (7 days) covers nothing: its name is fetched like any other, and the merge flags it.
    """
    if now.tzinfo is None:
        raise ValueError("`now` needs a time zone (pass a UTC time)")
    if league is not None and not league.strip():
        raise ValueError("league must not be blank")
    fetched_at = now.astimezone(UTC).replace(microsecond=0)
    league = league if league is not None else _current_league(get_json)
    trade_covered = current_trade_prices(old_price_file, league, fetched_at.date())
    covered = {canonical_price_name(name) for name in overrides} | set(trade_covered)
    wanted_names = sorted({canonical_price_name(name) for name in wanted or ()} - covered)

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
    warnings: list[str] = []
    failed_stash: list[str] = []
    for kind in STASH_TYPES:
        try:
            lines = _category(
                get_json,
                kind,
                "stash/current/item/overview",
                league,
                lambda data: parse_stash_overview(data, kind),
                "",
            )
        except SourceError as error:
            failed_stash.append(kind)
            warnings.append(f"{error}; the other categories were still fetched")
            continue
        for stash_line in lines:
            if stash_line.count < MIN_COUNT:
                thin_stash.setdefault(stash_line.key, stash_line)
            else:
                prices.setdefault(stash_line.key, PriceEntry(stash_line.chaos, SOURCE))
    for kind in failed_stash:
        kept = _kept_stash_prices(old_price_file, league, kind, prices)
        prices.update(kept)
        warnings.append(
            f"kept {len(kept)} old {kind} price(s) of {old_price_file.fetched_at:%Y-%m-%d}"
            if kept and old_price_file is not None
            else f"no old {kind} prices to keep: {kind} names are priced by the fallbacks only"
        )

    prices[CHAOS_ORB] = PriceEntry(1.0, SOURCE)
    chaos_per_divine = _chaos_per_divine(prices, divine_rate)
    prices.setdefault(DIVINE_ORB, PriceEntry(chaos_per_divine, SOURCE))
    thin = sorted(name for name in (*thin_exchange, *thin_stash) if name not in prices)

    gaps = [_gap(name, thin_exchange, thin_stash) for name in wanted_names if name not in prices]
    found, stage_warnings = run_stages(stages, get_json, Context(league, fetched_at.date(), previous_league), gaps)
    warnings.extend(stage_warnings)
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


def _kept_stash_prices(
    old: PriceFile | None, league: str, kind: str, prices: dict[str, PriceEntry]
) -> dict[str, PriceEntry]:
    """The poe.ninja prices of `old` (same league) that stand in for the failed stash overview of `kind`.

    The file does not record a price's category: a base is told by its name (`parse_base_price_name`), and
    a beast is any other poe.ninja price the fresh overviews did not give. A price a fresh overview gave
    is never replaced.
    """
    if old is None or old.league != league:
        return {}
    return {
        name: entry
        for name, entry in sorted(old.prices.items())
        if entry.source == SOURCE
        and name not in prices
        and name not in (CHAOS_ORB, DIVINE_ORB)
        and (BASE_TYPE if parse_base_price_name(name) is not None else BEAST) == kind
    }


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


_ABORTED = "no price file was written, the old price file was kept"


def _category(
    get_json: GetJson, kind: str, route: str, league: str, parse: Callable[[Any], Any], consequence: str = _ABORTED
) -> Any:
    """One overview of `kind`, parsed; a failure names the category (and, if given, says what follows from it)."""
    try:
        return parse(get_json(api_url(route, league=league, type=kind)))
    except SourceError as error:
        suffix = f"; {consequence}" if consequence else ""
        raise SourceError(f"the {kind} prices failed: {error}{suffix}") from error


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
