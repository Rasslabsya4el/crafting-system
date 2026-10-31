"""Command line for the price file: `python -m crafting_system.prices fetch|check|trade`.

This is the one place that reads the clocks (`datetime.now(UTC)`, `time.monotonic`, `time.sleep`);
the library functions take `now`, `today`, a clock and a sleep from here. `trade` prices a buy spec
from the trade site and is only ever run by hand: `fetch` never calls it.
"""

import argparse
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from ..config import Config, load_config
from ..data import DataError, load_game_data
from .fallbacks import MIN_COUNT
from .fetch import fetch_price_file
from .http_json import GetJson, SourceError, http_get_json, paced
from .price_names import canonical_price_name
from .price_file import (
    OVERRIDE_SOURCE,
    PriceFile,
    PriceFileNotFound,
    default_overrides_path,
    default_price_file_path,
    load_overrides,
    load_price_file,
    load_prices,
    missing_prices,
    stale_warning,
    to_divine,
    write_price_file,
)
from .trade_http import (
    RateLimiter,
    RequestBudget,
    TradeClient,
    TradeError,
    Transport,
    package_version,
    urllib_transport,
    user_agent,
)
from .trade_pricing import (
    DEFAULT_K,
    DEFAULT_MAX_REQUESTS,
    entry_for,
    merge_trade_prices,
    price_buy_spec,
    refuse_name_collision,
    stale_trade_warnings,
    store_trade_price,
)
from .trade_query import DEFAULT_INDEXED, INDEXED_OPTIONS, load_buy_spec

DATA_FETCH_COMMAND = "python -m crafting_system.data fetch"


def main(
    argv: Sequence[str] | None = None,
    *,
    get_json: GetJson | None = None,
    today: date | None = None,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
    transport: Transport | None = None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
) -> int:
    """Run one command; returns the exit code.

    `get_json`, `today`, `now`, `env`, `transport`, `sleep` and `monotonic` are for tests.
    """
    parser = argparse.ArgumentParser(prog="python -m crafting_system.prices")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="fetch poe.ninja prices into the price file")
    fetch.add_argument("--league", help="league id (default: the current league poe.ninja lists)")
    fetch.add_argument("--previous-league", help="league to take old prices from (default: work it out)")
    fetch.add_argument("--wanted-file", help="text file, one resource name per line")
    check = commands.add_parser("check", help="report a stale price file and unpriced names")
    check.add_argument("--wanted-file", help="text file, one resource name per line")
    trade = commands.add_parser(
        "trade", help="price a buy spec from the trade site (by hand only; a few requests)"
    )
    trade.add_argument("--spec", required=True, help="YAML file with the buy spec")
    trade.add_argument("--k", type=int, default=DEFAULT_K, help="price as the mean of the k cheapest listings")
    trade.add_argument(
        "--max-requests", type=int, default=DEFAULT_MAX_REQUESTS, help="most requests this run may send"
    )
    trade.add_argument(
        "--indexed",
        choices=[*INDEXED_OPTIONS, "any"],
        default=DEFAULT_INDEXED,
        help=(
            "keep only listings made within this window (default: listings of any age, since an "
            "instant-buyout price stands however old the listing is); 'any' keeps all"
        ),
    )
    trade.add_argument("--refresh-stats", action="store_true", help="download the stat list again")
    args = parser.parse_args(argv)

    try:
        config = load_config(env)
        if args.command == "trade":
            return _trade(args, config, env, now, transport, sleep, monotonic)
        wanted = _read_wanted(args.wanted_file)
        price_path = default_price_file_path(config)
        overrides_path = default_overrides_path(config)
        if args.command == "fetch":
            instant = now if now is not None else datetime.now(UTC)
            old_file, old_problem = _old_price_file(price_path)
            if old_problem:
                print(f"Warning: the old price file was not kept: {old_problem}")
            result = fetch_price_file(
                get_json
                if get_json is not None
                else paced(
                    http_get_json,
                    monotonic if monotonic is not None else time.monotonic,
                    sleep if sleep is not None else time.sleep,
                ),
                instant,
                wanted,
                args.league,
                args.previous_league,
                overrides=load_overrides(overrides_path),
                old_price_file=old_file,
            )
            new_file, trade_warnings = merge_trade_prices(result.price_file, _old_price_file(price_path)[0])
            write_price_file(price_path, new_file)
            print(f"League {new_file.league}: {len(new_file.prices)} prices written to {price_path}")
            if result.thin:
                print(
                    f"{len(result.thin)} current lines were too thin to price "
                    f"(fewer than {MIN_COUNT} observations or no trade volume)"
                )
            for warning in [*result.warnings, *trade_warnings]:
                print(f"Warning: {warning}")
        merged = load_prices(price_path, overrides_path)  # overrides count as priced
        if args.command == "check":
            print(f"League {merged.league}, fetched {merged.fetched_at:%Y-%m-%d}: {len(merged.prices)} prices")
            day = today if today is not None else datetime.now(UTC).date()
            stale = stale_warning(merged, day)
            if stale:
                print(f"Warning: {stale}")
            for line in stale_trade_warnings(merged, day):
                print(f"Warning: {line}")
        missing = missing_prices(wanted, merged.prices)
        if missing:
            print(f"No price for {len(missing)} wanted resources:")
            for name in missing:
                print(f"  {name}")
    except (SourceError, TradeError, PriceFileNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


def _old_price_file(path: Path) -> tuple[PriceFile | None, str | None]:
    """(the price file on disk, None), or (None, why) when it does not load (a fetch replaces it).

    A missing file is (None, None): there is nothing to report.
    """
    try:
        return load_price_file(path), None
    except PriceFileNotFound:
        return None, None
    except (ValueError, OSError) as error:
        return None, str(error)


def _trade(
    args: argparse.Namespace,
    config: Config,
    env: Mapping[str, str] | None,
    now: datetime | None,
    transport: Transport | None,
    sleep: Callable[[float], None] | None,
    monotonic: Callable[[], float] | None,
) -> int:
    """`trade`: one buy spec, a few requests, one write at the very end. Errors propagate to `main`."""
    price_path = default_price_file_path(config)
    overrides_path = default_overrides_path(config)
    price_file = load_prices(price_path, overrides_path)  # a missing file says to run `fetch` first
    spec = load_buy_spec(Path(args.spec))
    if canonical_price_name(spec.name) in load_overrides(overrides_path):
        print(f"{spec.name}: a hand override wins, so no request was made and the price file is unchanged")
        return 0
    existing = price_file.prices.get(spec.name)
    if existing is not None and existing.source != OVERRIDE_SOURCE:
        refuse_name_collision(spec.name, existing)  # before any request is spent
    try:
        game_mods = list(load_game_data(cache_dir=config.cache_dir).mods.values())
    except DataError:
        game_mods = []
        print(f"Note: no repoe data in the cache, so family ids cannot be used; run `{DATA_FETCH_COMMAND}`")

    cookie = (env if env is not None else os.environ).get("POESESSID") or None
    budget = RequestBudget(args.max_requests)
    client = TradeClient(
        transport if transport is not None else urllib_transport(),
        user_agent(package_version()),
        RateLimiter(
            monotonic if monotonic is not None else time.monotonic,
            sleep if sleep is not None else time.sleep,
        ),
        budget,
        cookie,
    )
    instant = now if now is not None else datetime.now(UTC)
    price = price_buy_spec(
        spec,
        game_mods,
        price_file,
        client,
        config.cache_dir,
        instant,
        args.k,
        args.refresh_stats,
        None if args.indexed == "any" else args.indexed,
    )
    store_trade_price(price_path, price, entry_for(price))
    print(
        f"{price.name}: {price.chaos:g} Chaos ({to_divine(price.chaos, price_file):.4g} Divine), "
        f"mean of the {price.used} cheapest instant-buyout listings ({price.fetched} fetched, "
        f"{price.listings} on the site), league {price.league}"
    )
    print(f"  listings from {'any time' if price.indexed is None else 'the last ' + price.indexed}")
    for reason, count in sorted(price.dropped.items()):
        print(f"  dropped {count} {reason}")
    print(f"{budget.used} requests used")
    return 0


def _read_wanted(path: str | None) -> list[str]:
    """Names from a text file, one per line; blank lines and `#` comment lines are skipped."""
    if path is None:
        return []
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    names = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return [canonical_price_name(name) for name in names]


if __name__ == "__main__":
    sys.exit(main())
