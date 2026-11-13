"""Command line for the price file: `python -m crafting_system.prices fetch|check`.

This is the one place that reads the clocks (`datetime.now(UTC)`, `time.monotonic`, `time.sleep`);
the library functions take `now`, `today`, a clock and a sleep from here. The trade-site pricing of a target's start item is
`python -m crafting_system.cli trade TARGET.yaml` (`cli/_trade.py`): it reads a target, which this layer may not import (#474).
"""

import argparse
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from ..config import load_config
from .fallbacks import MIN_COUNT
from .deepen import Deepened, ReadStopped, deepen_with_trade, exchange_entry, mark_unread
from .essence_recipe import apply_upgrade_recipe
from .fetch import fetch_price_file
from .http_json import GetJson, SourceError, http_get_json, paced
from .price_names import FORESIGHT_PRICE_NAMES, canonical_price_name
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
    write_price_file,
)
from .trade_exchange import exchange_body, read_offers, static_ids
from .trade_http import BudgetExceeded, RateLimiter, RequestBudget, TradeBlocked, TradeClient, TradeError, Transport, package_version, urllib_transport, user_agent
from .trade_pricing import merge_trade_prices, stale_trade_warnings


MAX_DEEPEN_REQUESTS = 400  # a safety bound on one run; the trade site's limits are what spaces the requests
MAX_DEEPEN_WAIT = 1800.0  # seconds the limiter may wait for a window to open: a run that reads many names is slow by design, never faster than the site allows


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
    fetch.add_argument(
        "--trade-below",
        type=float,
        help=(
            "read the trade site's offers for every wanted name that has no price or a price on fewer units than this, "
            "and keep the deeper reading (anonymous, a few requests a name, within the trade site's limits)"
        ),
    )
    check = commands.add_parser("check", help="report a stale price file and unpriced names")
    check.add_argument("--wanted-file", help="text file, one resource name per line")
    commands.add_parser("trade", help="moved: python -m crafting_system.cli trade TARGET.yaml")
    if list(argv if argv is not None else sys.argv[1:])[:1] == ["trade"]:
        print("Error: `trade` moved to the target's own command: python -m crafting_system.cli trade TARGET.yaml", file=sys.stderr)
        return 2
    args = parser.parse_args(argv)

    try:
        config = load_config(env)
        wanted = [*_read_wanted(args.wanted_file), *FORESIGHT_PRICE_NAMES]  # the Lock and its burns are always wanted (ADR-0056)
        price_path = default_price_file_path(config)
        overrides_path = default_overrides_path(config)
        unread: dict[str, str] = {}
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
            if args.trade_below is not None:
                deepened = _deepen(new_file, wanted, args.trade_below, instant, env, transport, sleep, monotonic)
                new_file, unread = deepened.price_file, deepened.unread
                trade_warnings = [*trade_warnings, *deepened.warnings]
            # last, so that no later reading puts a lower tier's own inflated row back (#885)
            new_file, from_recipe = apply_upgrade_recipe(new_file, wanted)
            write_price_file(price_path, new_file)  # what poe.ninja and the trade site gave is kept whether or not the rest could be read
            print(f"League {new_file.league}: {len(new_file.prices)} prices written to {price_path}")
            if from_recipe:
                print(f"{len(from_recipe)} lower essence tiers are priced from the vendor upgrade recipe (a third of the next tier up)")
            if result.thin:
                print(
                    f"{len(result.thin)} current lines were too thin to price "
                    f"(fewer than {MIN_COUNT} observations or no trade volume)"
                )
            for warning in [*result.warnings, *trade_warnings]:
                print(f"Warning: {warning}")
            for reason in sorted(set(unread.values())):
                names = sorted(name for name, why in unread.items() if why == reason)
                print(f"Error: {len(names)} names were not read on the trade site ({reason}); the prices from poe.ninja are written and these are marked unread:", file=sys.stderr)
                for name in names:
                    print(f"  {name}", file=sys.stderr)
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
        if unread:
            return 1  # the file is written, but the run did not read what it meant to: a scheduled run must show it is incomplete
    except (SourceError, TradeError, PriceFileNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


def _deepen(
    price_file: PriceFile,
    wanted: Sequence[str],
    below: float | None,
    now: datetime,
    env: Mapping[str, str] | None,
    transport: Transport | None,
    sleep: Callable[[float], None] | None,
    monotonic: Callable[[], float] | None,
) -> Deepened:
    """The price file with the trade site's offers read for the thin and the missing names of `wanted` (#616).

    A blocked site or a spent request budget stops the reading, never the run: the names not yet read keep their poe.ninja price,
    marked unread (`Provenance.trade_unread`), and are returned in `unread` with the reason, for the caller to write and report.
    """
    client = TradeClient(
        transport if transport is not None else urllib_transport(),
        user_agent(package_version()),
        RateLimiter(monotonic if monotonic is not None else time.monotonic, sleep if sleep is not None else time.sleep, max_wait=MAX_DEEPEN_WAIT, margin=2),
        RequestBudget(MAX_DEEPEN_REQUESTS),
        None,  # anonymous: no session is ever sent
    )
    try:
        ids = static_ids(client.data_static())
    except TradeError as error:
        reason = _why_stopped(error)
        marked, left = mark_unread(price_file, wanted, reason, below)
        return Deepened(marked, [], dict.fromkeys(left, reason))
    rates = {"chaos": 1.0, "divine": price_file.chaos_per_divine}
    day = now.astimezone(UTC).date()

    def read(name: str):
        item_id = ids.get(name)
        if item_id is None:
            return None  # not an item of the bulk exchange (a base, a beast, a start item)
        try:
            reading = read_offers(client.exchange(price_file.league, exchange_body(item_id)), rates)
        except (TradeBlocked, BudgetExceeded) as error:
            raise ReadStopped(_why_stopped(error)) from error
        except TradeError:
            return None  # the site refused this one item (not a block): the name keeps the price it has
        return None if reading is None else exchange_entry(reading, price_file.league, day, item_id)

    return deepen_with_trade(price_file, [name for name in wanted if name in ids], read, below)


def _why_stopped(error: TradeError) -> str:
    """The reason a trade reading stopped, in the words a price mark and the run's output print."""
    if isinstance(error, BudgetExceeded):
        return "the request budget of the run was spent"
    if isinstance(error, TradeBlocked):
        return "the trade site blocked the run"
    return "the trade site could not be read"


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


def _read_wanted(path: str | None) -> list[str]:
    """Names from a text file, one per line; blank lines and `#` comment lines are skipped."""
    if path is None:
        return []
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    names = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return [canonical_price_name(name) for name in names]


if __name__ == "__main__":
    sys.exit(main())
