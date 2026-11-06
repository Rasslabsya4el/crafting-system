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
from .trade_http import TradeError, Transport
from .trade_pricing import merge_trade_prices, stale_trade_warnings


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


def _read_wanted(path: str | None) -> list[str]:
    """Names from a text file, one per line; blank lines and `#` comment lines are skipped."""
    if path is None:
        return []
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    names = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return [canonical_price_name(name) for name in names]


if __name__ == "__main__":
    sys.exit(main())
