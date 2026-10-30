"""Command line of the data layer: `python -m crafting_system.data fetch|verify`.

`fetch` downloads the pinned repoe-fork files into the cache folder (only what is missing or
wrong) and checks their hashes; `verify` re-checks the cache without any network. One line per
file goes to stdout. A `DataError` prints `error: <message>` to stderr and exits 1; wrong usage
exits 2 (argparse). The later cli module wraps this.
"""

import argparse
import sys
from collections.abc import Sequence

from .errors import DataError
from .fetch import OpenUrl, fetch, verify_cache
from .pin import PIN, RepoePin


def _line(name: str, status: str, size: int, sha256: str) -> str:
    return f"{name}: {status}, {size} bytes, sha256 {sha256[:12]}"


def main(argv: Sequence[str] | None = None, *, pin: RepoePin = PIN, open_url: OpenUrl | None = None) -> int:
    """Run the command and return the exit code; `pin` and `open_url` are for tests and later callers."""
    parser = argparse.ArgumentParser(
        prog="python -m crafting_system.data",
        description="Fetch and check the pinned repoe-fork game data.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="download the pinned files into the cache folder and check their hashes")
    commands.add_parser("verify", help="check the cached files against the pin, offline")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:  # argparse exits on --help (0) and on wrong usage (2)
        return stop.code if isinstance(stop.code, int) else 1

    try:
        if args.command == "fetch":
            for result in fetch(pin, open_url=open_url):
                print(_line(result.name, result.status, result.size, result.sha256))
        else:
            verify_cache(pin)
            for pinned in pin.files:
                print(_line(pinned.name, "ok", pinned.size, pinned.sha256))
    except DataError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
