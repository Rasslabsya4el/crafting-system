"""Command line of the rules layer: `python -m crafting_system.rules stale`.

`stale` lists the claims whose `patch_verified` is older than the patch in `PIN.json`, one line each
with the url to re-read; nothing is changed. After `data pin` moves the pin, these are the claims
step 6 of the patch update still has to check. `--pin-file` and `--claims` read another pin file
or claims folder (for a rehearsal on a copy).

A registry or pin file that cannot be used prints `error: <message>` to stderr and exits 1; wrong
usage exits 2 (argparse).
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from crafting_system.data import PIN_FILE, DataError

from .registry import RegistryError
from .stale import stale_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m crafting_system.rules", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    stale = commands.add_parser("stale", help="list the claims not verified on the pinned patch")
    stale.add_argument("--pin-file", type=Path, default=PIN_FILE, help="the pin file to compare with (default: PIN.json)")
    stale.add_argument("--claims", type=Path, default=None, help="a claims folder (default: the shipped claims)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:  # argparse exits on --help (0) and on wrong usage (2)
        return stop.code if isinstance(stop.code, int) else 1
    try:
        print(stale_report(args.claims, args.pin_file))
    except (RegistryError, DataError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
