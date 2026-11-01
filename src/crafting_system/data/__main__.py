"""Command line of the data layer: `python -m crafting_system.data fetch|verify|diff|pin|elevated`.

`fetch` downloads the pinned repoe-fork files into the cache folder (only what is missing or
wrong) and checks their hashes; `verify` re-checks the cache without any network. One line per
file goes to stdout.

`diff OLD NEW` prints what changed between two versions of the game data: each of OLD and NEW is
the word `pinned` (the active pin, checked against the hashes in `PIN.json`), a full 40-character
repoe-fork commit, or a game version name such as `3.29.4.1` (resolved to the newest export of
that version through the GitHub API, see `resolve`; the export taken is printed). A commit that
is not the pin is downloaded once and its hashes are learned (see `candidate`); the command that
moves the pin to it is printed after the diff. Only files that are missing or wrong are
downloaded, and the diff covers mods, weights, families, tags, bench options, essences and
fossils. After the diff comes the impact report (see `impact`): the targets, routes, claims and
tests of this checkout that name something that changed; `--no-impact` leaves it out, and a copy
of the package without a checkout around it prints none.

`pin TARGET [VERSION]` moves the pin: TARGET is a commit or a game version name. It learns the
commit (reusing the files and manifest `diff` stored, downloading only a commit never seen),
files them under the version's cache folder so no second download follows, checks them with
`fetch`, and only then rewrites `PIN.json`. A commit without VERSION takes the version from the
commit message (`Export <version>`) on GitHub.

`elevated COE_FOLDER` rebuilds `elevated.json`, the link from each top-tier influence mod to its Elevated mod, from Craft of Exile's
`poec_data.json` in COE_FOLDER (git-ignored third-party data, `sources/raw/coe/` of the main checkout) and the cached pinned `mods.json`
(see `elevated`); it prints how many mods it linked and how many table entries it could not.

A `DataError` prints `error: <message>` to stderr and exits 1; wrong usage exits 2 (argparse).
The later cli module wraps this.
"""

import argparse
import dataclasses
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .candidate import MANIFEST_NAME, candidate_pin
from .diff import diff_game_data
from .elevated import ELEVATED_FILE, build_elevated, parse_poec_data, render_elevated
from .errors import DataError, FetchError, RawFormatError
from .fetch import OpenUrl, fetch, read_verified_files, verify_cache, version_folder
from .impact import compute_impact, find_repo_root, render_impact
from .load import load_game_data
from .model import GameData
from .normalize import MODS_FILE
from .pin import PIN, PIN_FILE, RepoePin, is_commit, write_pin
from .resolve import Export, export_of_commit, is_version_name, resolve_version

PINNED = "pinned"
PIN_COMMAND = "python -m crafting_system.data pin"


def _line(name: str, status: str, size: int, sha256: str) -> str:
    return f"{name}: {status}, {size} bytes, sha256 {sha256[:12]}"


def _version(text: str) -> str:
    """An argument of `diff`: `pinned`, a commit (capitals allowed, as the lowercase form) or a version name."""
    if text == PINNED or is_version_name(text):
        return text
    if is_commit(text.lower()):
        return text.lower()
    raise argparse.ArgumentTypeError(
        f"{text!r} is not a version: use the word '{PINNED}', a full 40-character repoe-fork commit "
        "(hex digits) or a game version name like 3.29.3.3"
    )


def _target(text: str) -> str:
    """The TARGET of `pin`: a version name, or a commit (capitals allowed, as the lowercase form)."""
    if is_version_name(text):
        return text
    if is_commit(text.lower()):
        return text.lower()
    raise argparse.ArgumentTypeError(
        f"{text!r} is not a pin target: use a full 40-character repoe-fork commit (hex digits) "
        "or a game version name like 3.29.3.3"
    )


def _version_name(text: str) -> str:
    if is_version_name(text):
        return text
    raise argparse.ArgumentTypeError(f"{text!r} is not a game version name: use dot-separated numbers like 3.29.3.3")


@dataclass(frozen=True)
class _Side:
    """One side of a diff: `PINNED` or a commit, and the version name the user gave for it (if they did)."""

    spec: str
    name: str | None = None


def _export_line(export: Export) -> str:
    return f"Export of {export.version}: commit {export.commit}, committed {export.date}"


def _side(text: str, pin: RepoePin, open_url: OpenUrl | None) -> _Side:
    """What an argument of `diff` stands for; a version name goes through the GitHub API (several exports can share one)."""
    if text in (PINNED, pin.commit):
        return _Side(PINNED)
    if is_commit(text):
        return _Side(text)
    export = resolve_version(text, open_url=open_url)
    print(_export_line(export))
    # the export of the pin's own commit is the pin: its hashes come from code, never from a manifest
    return _Side(PINNED) if export.commit == pin.commit else _Side(export.commit, text)


def _load_version(side: _Side, pin: RepoePin, open_url: OpenUrl | None) -> tuple[GameData, str, RepoePin | None]:
    """(the data, its label in the diff header, the learned pin if the side is a commit that is not the pin)."""
    commit = side.spec
    if commit == PINNED:
        fetch(pin, open_url=open_url)
        return load_game_data(pin), f"{pin.version} ({pin.commit[:8]})", None
    learned = candidate_pin(commit, pin, open_url=open_url)
    fetch(learned, open_url=open_url)
    try:
        data = load_game_data(learned)
    except RawFormatError as error:
        raise RawFormatError(
            f"{error} (the files of commit {commit} are in {version_folder(commit)}; "
            "delete that folder to download the commit again)"
        ) from error
    label = f"{side.name} ({commit[:8]})" if side.name else f"commit {commit[:12]}"
    return data, label, learned


def _diff(old: _Side, new: _Side, pin: RepoePin, open_url: OpenUrl | None, *, impact: bool) -> None:
    old_data, old_label, old_learned = _load_version(old, pin, open_url)
    new_data, new_label, new_learned = _load_version(new, pin, open_url)
    text = diff_game_data(old_data, new_data, old_label=old_label, new_label=new_label)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:  # a console that cannot show a character gets an escape, not a crash
        reconfigure(errors="backslashreplace")
    print(text)
    root = find_repo_root() if impact else None
    if root is not None:
        print()
        print(render_impact(compute_impact(old_data, new_data, root), old_label, new_label))
    for side, learned in ((old, old_learned), (new, new_learned)):
        if learned is not None:
            print(f"\nTo move the pin to this export: {PIN_COMMAND} {learned.commit} {side.name or '<version>'}")


def _pin(target: str, version: str | None, pin: RepoePin, pin_file: Path, open_url: OpenUrl | None) -> None:
    """Move the pin to `target` (a commit or a version name): the files in place and checked, then `pin_file`."""
    if is_commit(target):
        commit = target
    else:
        export = resolve_version(target, open_url=open_url)
        print(_export_line(export))
        commit, version = export.commit, target
    if commit == pin.commit:
        raise DataError(f"commit {commit} is already the pin (version {pin.version})")
    if version is None:
        named = export_of_commit(commit, open_url)
        if named is None:
            raise DataError(
                f"the message of commit {commit} names no export version: pass VERSION, "
                f"{PIN_COMMAND} {commit} <version>"
            )
        version = named.version

    new_pin = dataclasses.replace(candidate_pin(commit, pin, open_url=open_url), version=version)
    moved = _file_under_version(commit, version)
    try:
        for result in fetch(new_pin, open_url=open_url):
            print(_line(result.name, result.status, result.size, result.sha256))
        write_pin(new_pin, pin_file)
    except BaseException:
        _put_back(moved, commit, version)  # the commit stays learned, so a rerun downloads nothing
        raise
    _drop_learned(commit)
    print(f"{pin_file} was written: the pin is now version {version}, commit {commit}")


def _file_under_version(commit: str, version: str) -> list[str]:
    """Move the files `diff` stored under the commit into the cache folder of `version`; the names moved.

    Without a second download: a file of an older export of the same version name in that folder is
    replaced, and `fetch` repairs whatever is still wrong. The learned manifest stays in the commit's
    folder until the pin is written (`_drop_learned`), so a failure can put everything back.
    """
    source, target = version_folder(commit), version_folder(version)
    moved: list[str] = []
    try:
        target.mkdir(parents=True, exist_ok=True)
        for path in sorted(source.iterdir()):
            if path.name != MANIFEST_NAME:
                os.replace(path, target / path.name)
                moved.append(path.name)
    except OSError as error:
        _put_back(moved, commit, version)
        raise FetchError(f"could not move the cache files {source} to {target}: {error}") from error
    return moved


def _put_back(moved: list[str], commit: str, version: str) -> None:
    """Undo `_file_under_version` as far as the disk lets us; a failure here is ignored, the first error matters."""
    source, target = version_folder(commit), version_folder(version)
    for name in moved:
        try:
            os.replace(target / name, source / name)
        except OSError:
            pass


def _drop_learned(commit: str) -> None:
    """The pin is written: the commit's own folder, with its learned manifest, is no longer needed."""
    folder = version_folder(commit)
    try:
        (folder / MANIFEST_NAME).unlink(missing_ok=True)
        folder.rmdir()
    except OSError:
        pass  # something else is in it: leave it


def _elevated(coe_folder: Path, output: Path, pin: RepoePin) -> None:
    """Write the Elevated mapping of Craft of Exile's table in `coe_folder` against the pinned export, and print the tally."""
    try:
        raw = (coe_folder / "poec_data.json").read_bytes()
    except OSError as error:
        raise DataError(f"cannot read poec_data.json in {coe_folder}: {error}") from error
    mods = json.loads(read_verified_files(pin)[MODS_FILE])
    document = build_elevated(
        parse_poec_data(raw.decode("utf-8")), mods, repoe_version=pin.version, poec_data_sha256=hashlib.sha256(raw).hexdigest()
    )
    if not document["elevated"]:
        raise DataError(
            f"no top-tier mod of Craft of Exile's Elevated table could be linked to a mod of the pinned export {pin.version}; "
            f"{output} was not written (is the folder Craft of Exile's data of a patch near this export?)"
        )
    partial = output.with_name(output.name + ".partial")  # a run cut short must not leave a truncated mapping behind
    partial.write_text(render_elevated(document), encoding="utf-8", newline="\n")
    os.replace(partial, output)
    entries =sum(row["entries"] for row in document["unresolved"])
    print(f"{output}: {len(document['elevated'])} top-tier mods linked to an Elevated mod; {len(document['unresolved'])} kinds of table entry ({entries} keys) not linked")


def main(
    argv: Sequence[str] | None = None,
    *,
    pin: RepoePin = PIN,
    open_url: OpenUrl | None = None,
    pin_file: Path = PIN_FILE,
) -> int:
    """Run the command and return the exit code; `pin`, `open_url` and `pin_file` are for tests and later callers."""
    parser = argparse.ArgumentParser(
        prog="python -m crafting_system.data",
        description="Fetch and check the pinned repoe-fork game data, compare two versions of it, and move the pin.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="download the pinned files into the cache folder and check their hashes")
    commands.add_parser("verify", help="check the cached files against the pin, offline")
    compare = commands.add_parser(
        "diff",
        help="print what changed between two versions of the data",
        description=(
            "Print what changed from OLD to NEW in mods, weights, families, tags, bench options, essences "
            f"and fossils. Each of OLD and NEW is the word '{PINNED}' (the active pin), a full "
            "40-character repoe-fork commit, or a game version name like 3.29.4.1 (the newest export of "
            "that version, found through the GitHub API and printed). A commit that is not the pin is "
            "downloaded once and its hashes are learned. The diff is followed by an impact report (the "
            "targets, routes, claims and tests of this checkout that name something that changed; "
            "--no-impact leaves it out) and the command that moves the pin to the new export."
        ),
    )
    compare.add_argument("old", type=_version, metavar="OLD", help=f"'{PINNED}', a repoe-fork commit or a version name")
    compare.add_argument("new", type=_version, metavar="NEW", help=f"'{PINNED}', a repoe-fork commit or a version name")
    compare.add_argument(
        "--no-impact", action="store_true", help="leave out the report of what the change touches in this repo"
    )
    move = commands.add_parser(
        "pin",
        help="move the pin to a commit or a game version",
        description=(
            "Move the pin (the file PIN.json) to TARGET, a full 40-character repoe-fork commit or a game "
            "version name like 3.29.4.1 (the newest export of that version, found through the GitHub API "
            "and printed). The files `diff` already downloaded for the commit are reused: they are filed "
            "under the version's cache folder and checked, and a commit never seen is downloaded once. "
            "PIN.json is written last, after the files are checked. For a commit, VERSION names the game "
            "version; without it the version is read from the commit's message (`Export <version>`) on "
            "GitHub."
        ),
    )
    move.add_argument("target", type=_target, metavar="TARGET", help="a repoe-fork commit or a game version name")
    move.add_argument(
        "version", type=_version_name, nargs="?", metavar="VERSION", help="the game version of a commit (3.29.4.1)"
    )
    elevated = commands.add_parser(
        "elevated",
        help="rebuild elevated.json (top-tier influence mod -> Elevated mod) from Craft of Exile's data",
        description=(
            "Read poec_data.json from COE_FOLDER (Craft of Exile's data, git-ignored) and the cached pinned mods.json, "
            "link every top-tier influence mod of Craft of Exile's Elevated table to its mod in the export, and write "
            "src/crafting_system/data/elevated.json (or --output). Run it again whenever the pin moves."
        ),
    )
    elevated.add_argument("coe_folder", type=Path, metavar="COE_FOLDER", help="the folder holding poec_data.json")
    elevated.add_argument("--output", type=Path, default=ELEVATED_FILE, help="the file to write (default: elevated.json beside the package)")
    try:
        args = parser.parse_args(argv)
        if args.command == "diff":
            # the active pin's own commit is the pin: its hashes come from code, never from a manifest
            old, new = (PINNED if text == pin.commit else text for text in (args.old, args.new))
            if old == new:
                parser.error(f"OLD and NEW are the same version ({old}): there is nothing to compare")
        elif args.command == "pin" and is_version_name(args.target) and args.version not in (None, args.target):
            parser.error(f"TARGET {args.target} is a version name, but VERSION says {args.version}: give only one")
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
        elif args.command == "pin":
            _pin(args.target, args.version, pin, pin_file, open_url)
        elif args.command == "elevated":
            _elevated(args.coe_folder, args.output, pin)
        else:
            sides = (_side(old, pin, open_url), _side(new, pin, open_url))
            if sides[0].spec == sides[1].spec:  # two names of one export
                parser.error(f"OLD and NEW are the same version ({args.old}, {args.new}): there is nothing to compare")
            _diff(*sides, pin, open_url, impact=not args.no_impact)
    except SystemExit as stop:  # a usage error found only after a version name was resolved
        return stop.code if isinstance(stop.code, int) else 1
    except (DataError, ValueError) as error:  # ValueError: a broken crafting.toml or CRAFTING_CONFIG
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
