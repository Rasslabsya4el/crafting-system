"""Command line for the price file: `python -m crafting_system.prices fetch|check`.

This is the one place that reads the clock (`datetime.now(UTC)`); the library functions take
`now` and `today` from here.
"""

import argparse
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from ..config import load_config
from .poe_ninja import GetJson, SourceError, fetch_price_file, http_get_json
from .price_file import (
    PriceFileNotFound,
    default_overrides_path,
    default_price_file_path,
    load_prices,
    missing_prices,
    stale_warning,
    write_price_file,
)


def main(
    argv: Sequence[str] | None = None,
    *,
    get_json: GetJson | None = None,
    today: date | None = None,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    """Run one command; returns the exit code. `get_json`, `today`, `now` and `env` are for tests."""
    parser = argparse.ArgumentParser(prog="python -m crafting_system.prices")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="fetch poe.ninja prices into the price file")
    fetch.add_argument("--league", help="league id (default: the current league poe.ninja lists)")
    fetch.add_argument("--wanted-file", help="text file, one resource name per line")
    check = commands.add_parser("check", help="report a stale price file and unpriced names")
    check.add_argument("--wanted-file", help="text file, one resource name per line")
    args = parser.parse_args(argv)

    try:
        config = load_config(env)
        wanted = _read_wanted(args.wanted_file)
        price_path = default_price_file_path(config)
        overrides_path = default_overrides_path(config)
        if args.command == "fetch":
            instant = now if now is not None else datetime.now(UTC)
            result = fetch_price_file(
                get_json if get_json is not None else http_get_json, instant, wanted, args.league
            )
            write_price_file(price_path, result.price_file)
            print(f"League {result.price_file.league}: {len(result.price_file.prices)} prices written to {price_path}")
            for warning in result.warnings:
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
    except (SourceError, PriceFileNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


def _read_wanted(path: str | None) -> list[str]:
    """Names from a text file, one per line; blank lines and `#` comment lines are skipped."""
    if path is None:
        return []
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


if __name__ == "__main__":
    sys.exit(main())
