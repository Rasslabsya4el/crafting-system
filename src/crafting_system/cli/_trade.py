"""`python -m crafting_system.cli trade TARGET.yaml`: price the bought start item of a target on the trade site, by hand only (#39, #474).

The buy spec, the query and the name the price is stored under are computed from the target (`targets.start_buy`), so the target is the
only description of the item. A few anonymous requests through the trade limiter of `prices.trade_http` (no login, no session unless the
caller sets `POESESSID` himself), one write at the very end. The command sits in `cli` and not in `prices` because it reads a target, and
`prices` may not import `targets` (ADR-0018). `fetch` never calls it.
"""

import argparse
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from crafting_system.config import Config, load_config
from crafting_system.data import DataError, GameData, load_game_data
from crafting_system.prices import TradeError
from crafting_system.prices.price_file import (
    OVERRIDE_SOURCE,
    PriceFileNotFound,
    default_overrides_path,
    default_price_file_path,
    load_overrides,
    load_prices,
    to_divine,
)
from crafting_system.prices.price_names import canonical_price_name
from crafting_system.prices.trade_http import (
    RateLimiter,
    RequestBudget,
    TradeClient,
    Transport,
    package_version,
    urllib_transport,
    user_agent,
)
from crafting_system.prices.trade_market import DEFAULT_MIN_LISTINGS
from crafting_system.prices.trade_pricing import (
    DEFAULT_K,
    DEFAULT_MAX_REQUESTS,
    NotEnoughListings,
    entry_for,
    price_buy_spec,
    refuse_name_collision,
    store_market,
    store_trade_price,
)
from crafting_system.prices.trade_query import DEFAULT_INDEXED, INDEXED_OPTIONS
from crafting_system.targets import TargetError, buy_spec_of, load_target

COMMAND = "python -m crafting_system.cli trade"
DATA_FETCH_COMMAND = "python -m crafting_system.data fetch"


def trade_main(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    data: GameData | None = None,
    now: datetime | None = None,
    transport: Transport | None = None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
) -> int:
    """Run `trade` and return the exit code; `env`, `data`, `now`, `transport`, `sleep` and `monotonic` are for tests."""
    parser = argparse.ArgumentParser(
        prog=COMMAND, description="Price the bought start item of a target from the trade site (by hand only; a few requests)."
    )
    parser.add_argument("target", help="the target YAML file whose start item is priced (it must say buys_start_item: true)")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="price as the mean of the k cheapest listings")
    parser.add_argument(
        "--min-listings",
        type=int,
        default=DEFAULT_MIN_LISTINGS,
        help="a market needs at least this many listings on the site (the listing-count rail)",
    )
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS, help="most requests this run may send")
    parser.add_argument(
        "--indexed",
        choices=[*INDEXED_OPTIONS, "any"],
        default=DEFAULT_INDEXED,
        help=(
            "keep only listings made within this window (default: listings of any age, since an "
            "instant-buyout price stands however old the listing is); 'any' keeps all"
        ),
    )
    parser.add_argument("--refresh-stats", action="store_true", help="download the stat list again")
    args = parser.parse_args(list(argv))
    try:
        config = load_config(env)
        return _trade(args, config, env, data, now, transport, sleep, monotonic)
    except (TradeError, TargetError, DataError, PriceFileNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def _trade(
    args: argparse.Namespace,
    config: Config,
    env: Mapping[str, str] | None,
    data: GameData | None,
    now: datetime | None,
    transport: Transport | None,
    sleep: Callable[[float], None] | None,
    monotonic: Callable[[], float] | None,
) -> int:
    """One target, a few requests, one write at the very end. Errors propagate to `trade_main`."""
    price_path = default_price_file_path(config)
    overrides_path = default_overrides_path(config)
    price_file = load_prices(price_path, overrides_path)  # a missing file says to run `fetch` first
    try:
        game = data if data is not None else load_game_data(cache_dir=config.cache_dir)
    except DataError as error:
        raise DataError(f"{error}; run `{DATA_FETCH_COMMAND}`") from error
    target = load_target(Path(args.target), game)
    if not target.buys_start_item:
        raise ValueError(f"{args.target}: the target does not buy its start item (no `buys_start_item: true`), so there is nothing to price")
    spec = buy_spec_of(game, target)
    if canonical_price_name(spec.name) in load_overrides(overrides_path):
        print(f"{spec.name}: a hand override wins, so no request was made and the price file is unchanged")
        return 0
    existing = price_file.prices.get(spec.name)
    if existing is not None and existing.source != OVERRIDE_SOURCE:
        refuse_name_collision(spec.name, existing)  # before any request is spent

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
    try:
        price = price_buy_spec(
            spec,
            list(game.mods.values()),
            price_file,
            client,
            config.cache_dir,
            instant,
            args.k,
            args.refresh_stats,
            None if args.indexed == "any" else args.indexed,
            args.min_listings,
        )
    except NotEnoughListings as error:
        if error.market is not None:  # thin or none: kept as a state, the price file has no price for it
            store_market(price_path, error.market)
            print(f"{spec.name}: no market ({error.market.state}); recorded as {error.market.state}, not offered")
        raise
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
