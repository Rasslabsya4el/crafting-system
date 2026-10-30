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
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

from ..config import Config, load_config
from ..data import DataError, load_game_data
from .poe_ninja import GetJson, SourceError, fetch_price_file, http_get_json
from .price_file import (
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
    store_trade_price,
)
from .trade_query import load_buy_spec

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
    fetch.add_argument("--wanted-file", help="text file, one resource name per line")
    check = commands.add_parser("check", help="report a stale price file and unpriced names")
    check.add_argument("--wanted-file", help="text file, one resource name per line")
    trade = commands.add_parser(
        "trade", help="price a buy spec from the trade site (by hand only; a few requests)"
    )
    trade.add_argument("--spec", required=True, help="YAML file with the buy spec")
    trade.add_argument("--k", type=int, default=DEFAULT_K, help="price from the k cheapest listings")
    trade.add_argument(
        "--max-requests", type=int, default=DEFAULT_MAX_REQUESTS, help="most requests this run may send"
    )
    trade.add_argument("--refresh-stats", action="store_true", help="download the stat list again")
    trade.add_argument("--league", help="league to search (default: the league of the price file)")
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
            result = fetch_price_file(
                get_json if get_json is not None else http_get_json, instant, wanted, args.league
            )
            new_file, trade_warnings = merge_trade_prices(result.price_file, _old_price_file(price_path))
            write_price_file(price_path, new_file)
            print(f"League {new_file.league}: {len(new_file.prices)} prices written to {price_path}")
            for warning in [*result.warnings, *trade_warnings]:
                print(f"Warning: {warning}")
        merged = load_prices(price_path, overrides_path)  # overrides count as priced
        if args.command == "check":
            print(f"League {merged.league}, fetched {merged.fetched_at:%Y-%m-%d}: {len(merged.prices)} prices")
            stale = stale_warning(merged, today if today is not None else datetime.now(UTC).date())
            if stale:
                print(f"Warning: {stale}")
        missing = missing_prices(wanted, merged.prices)
        if missing:
            print(f"No price for {len(missing)} wanted resources:")
            for name in missing:
                print(f"  {name}")
    except (SourceError, TradeError, PriceFileNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


def _old_price_file(path: Path) -> PriceFile | None:
    """The price file on disk, or None when there is none or it does not load (a fetch replaces it)."""
    try:
        return load_price_file(path)
    except (ValueError, OSError):
        return None


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
    if spec.name in load_overrides(overrides_path):
        print(f"{spec.name}: a hand override wins, so no request was made and the price file is unchanged")
        return 0
    if args.league is not None:
        if not args.league.strip():
            raise ValueError("league must not be empty")
        price_file = replace(price_file, league=args.league)
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
        spec, game_mods, price_file, client, config.cache_dir, instant, args.k, args.refresh_stats
    )
    store_trade_price(price_path, price, entry_for(price))
    print(
        f"{price.name}: {price.chaos:g} Chaos ({to_divine(price.chaos, price_file):.4g} Divine), "
        f"{price.used} of {price.fetched} fetched listings used ({price.listings} on the site), "
        f"league {price.league}"
    )
    for reason, count in sorted(price.dropped.items()):
        print(f"  dropped {count} {reason}")
    print(f"{budget.used} requests used")
    return 0


def _read_wanted(path: str | None) -> list[str]:
    """Names from a text file, one per line; blank lines and `#` comment lines are skipped."""
    if path is None:
        return []
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


if __name__ == "__main__":
    sys.exit(main())
