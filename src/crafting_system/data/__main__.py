"""Command line of the data layer: `python -m crafting_system.data fetch|verify|diff`.

`fetch` downloads the pinned repoe-fork files into the cache folder (only what is missing or
wrong) and checks their hashes; `verify` re-checks the cache without any network. One line per
file goes to stdout.

`diff OLD NEW` prints what changed between two versions of the game data: each of OLD and NEW is
the word `pinned` (the active pin, checked against the hashes in code) or a full 40-character
repoe-fork commit. A commit that is not the pin is downloaded once and its hashes are learned
(see `candidate`); the lines to paste into `PIN` to move to it are printed after the diff. Only
files that are missing or wrong are downloaded, and the diff covers mods, weights, families,
tags, bench options, essences and fossils.

A `DataError` prints `error: <message>` to stderr and exits 1; wrong usage exits 2 (argparse).
The later cli module wraps this.
"""

import argparse
import sys
from collections.abc import Sequence

from .candidate import candidate_pin, pin_lines
from .diff import diff_game_data
from .errors import DataError, RawFormatError
from .fetch import OpenUrl, fetch, verify_cache, version_folder
from .load import load_game_data
from .model import GameData
from .pin import PIN, RepoePin, is_commit

PINNED = "pinned"


def _line(name: str, status: str, size: int, sha256: str) -> str:
    return f"{name}: {status}, {size} bytes, sha256 {sha256[:12]}"


def _version(text: str) -> str:
    """An argument of `diff`: the word `pinned` or a commit (capitals allowed), as the lowercase form."""
    if text == PINNED:
        return text
    if is_commit(text.lower()):
        return text.lower()
    raise argparse.ArgumentTypeError(
        f"{text!r} is not a version: use the word '{PINNED}' or a full 40-character repoe-fork commit (hex digits)"
    )


def _load_version(version: str, pin: RepoePin, open_url: OpenUrl | None) -> tuple[GameData, str, RepoePin | None]:
    """(the data, its label in the diff header, the learned pin if `version` is a commit that is not the pin)."""
    if version == PINNED:
        fetch(pin, open_url=open_url)
        return load_game_data(pin), f"{pin.version} ({pin.commit[:8]})", None
    learned = candidate_pin(version, pin, open_url=open_url)
    fetch(learned, open_url=open_url)
    try:
        data = load_game_data(learned)
    except RawFormatError as error:
        raise RawFormatError(
            f"{error} (the files of commit {version} are in {version_folder(version)}; "
            "delete that folder to download the commit again)"
        ) from error
    return data, f"commit {version[:12]}", learned


def _diff(old: str, new: str, pin: RepoePin, open_url: OpenUrl | None) -> None:
    old_data, old_label, old_learned = _load_version(old, pin, open_url)
    new_data, new_label, new_learned = _load_version(new, pin, open_url)
    text = diff_game_data(old_data, new_data, old_label=old_label, new_label=new_label)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:  # a console that cannot show a character gets an escape, not a crash
        reconfigure(errors="backslashreplace")
    print(text)
    for learned in (old_learned, new_learned):
        if learned is not None:
            print(f"\nPin lines for commit {learned.commit} (paste into PIN in pin.py, with its new version):")
            print(
                "(hashes recorded from the first download of this commit; "
                "check them against another source before trusting)"
            )
            print(pin_lines(learned))


def main(argv: Sequence[str] | None = None, *, pin: RepoePin = PIN, open_url: OpenUrl | None = None) -> int:
    """Run the command and return the exit code; `pin` and `open_url` are for tests and later callers."""
    parser = argparse.ArgumentParser(
        prog="python -m crafting_system.data",
        description="Fetch and check the pinned repoe-fork game data, and compare two versions of it.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="download the pinned files into the cache folder and check their hashes")
    commands.add_parser("verify", help="check the cached files against the pin, offline")
    compare = commands.add_parser(
        "diff",
        help="print what changed between two versions of the data",
        description=(
            "Print what changed from OLD to NEW in mods, weights, families, tags, bench options, essences "
            f"and fossils. Each of OLD and NEW is the word '{PINNED}' (the active pin) or a full "
            "40-character repoe-fork commit. A commit that is not the pin is downloaded once and its "
            "hashes are learned; the lines to paste into PIN are printed after the diff."
        ),
    )
    compare.add_argument("old", type=_version, metavar="OLD", help=f"'{PINNED}' or a repoe-fork commit")
    compare.add_argument("new", type=_version, metavar="NEW", help=f"'{PINNED}' or a repoe-fork commit")
    try:
        args = parser.parse_args(argv)
        if args.command == "diff":
            # the commit of the active pin is the pin: its hashes come from code, never from a manifest
            old, new = (PINNED if version == pin.commit else version for version in (args.old, args.new))
            if old == new:
                parser.error(f"OLD and NEW are the same version ({old}): there is nothing to compare")
    except SystemExit as stop:  # argparse exits on --help (0) and on wrong usage (2)
        return stop.code if isinstance(stop.code, int) else 1

    try:
        if args.command == "fetch":
            for result in fetch(pin, open_url=open_url):
                print(_line(result.name, result.status, result.size, result.sha256))
        elif args.command == "verify":
            verify_cache(pin)
            for pinned in pin.files:
                print(_line(pinned.name, "ok", pinned.size, pinned.sha256))
        else:
            _diff(old, new, pin, open_url)
    except (DataError, ValueError) as error:  # ValueError: a broken crafting.toml or CRAFTING_CONFIG
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
