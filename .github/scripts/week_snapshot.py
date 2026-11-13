"""Write a price snapshot of a league as it stood on an earlier day, from poe.ninja's daily exchange rows (#838).

    python .github/scripts/week_snapshot.py --league Allflame --start 2026-07-24 --as-of 2026-07-31 \
        --previous Mirage --previous-start 2026-03-06 \
        --template tests/fixtures/prices/routes-allflame-2026-11-10.json \
        --template tests/fixtures/prices/routes-allflame-2026-10-31.json \
        --out tests/fixtures/prices/routes-allflame-2026-07-31.json --cache .claude/scratch/838-cache

The rule of each price is `crafting_system.prices.week_snapshot`. The templates give the names (the first one wins for a stand-in);
`--spends` adds every name a method in scope spends (`crafting_system.prices.spends`, #885; it reads the game data), and
`--wanted-file` the names of a text file, one per line. The lower essence tiers come out priced from the vendor upgrade recipe;
the leagues' first days are poe.ninja's (`/poe1/api/data/dumps`, `minDate`). Anonymous, read-only, one paced request at a time, a
few hundred requests; every answer is kept under `--cache`, so a second run reads the same rows. A 404 is "no history of this
item": the next step of the rule takes over. Any other failure (a rate limit, the network) stops the run and nothing is written,
so no price becomes a stand-in because a request failed.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from crafting_system.prices import load_price_file, write_price_file  # noqa: E402
from crafting_system.prices.http_json import SourceError, http_get_json, paced  # noqa: E402
from crafting_system.prices.ninja_history import exchange_history_readings  # noqa: E402
from crafting_system.prices.week_snapshot import build_snapshot  # noqa: E402

MISSING = "404"  # what the cache keeps for an answer of "no such item"
EVER = (date(2000, 1, 1), date(2100, 1, 1))  # every row; `reading_on` takes the week it needs


class Stopped(Exception):
    """A request failed for another reason than 404: the run stops rather than price the name from a later step."""


def cached(get, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)

    def keep(path: Path, data) -> None:
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(temp, path)  # whole or not at all: a run killed mid-write leaves no half answer

    def get_json(url: str):
        path = folder / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None  # not cached, or unreadable: asked again
        else:
            if data == MISSING:
                raise SourceError(f"HTTP 404 from {url} (cached)")
            return data
        try:
            data = get(url)
        except SourceError as error:
            if not str(error).startswith("HTTP 404"):
                raise Stopped(str(error)) from error
            keep(path, MISSING)
            raise
        keep(path, data)
        return data

    return get_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--league", required=True)
    parser.add_argument("--start", required=True, type=date.fromisoformat, help="the league's first day")
    parser.add_argument("--as-of", required=True, type=date.fromisoformat, help="the day the snapshot is of")
    parser.add_argument("--previous", help="the previous league, for the bulk names the league has no row for")
    parser.add_argument("--previous-start", type=date.fromisoformat, help="the previous league's first day")
    parser.add_argument("--template", action="append", required=True, help="an earlier snapshot whose names are priced (repeatable)")
    parser.add_argument("--spends", action="store_true", help="also price every name a method in scope spends (reads the game data)")
    parser.add_argument("--wanted-file", help="also price the names of this text file, one per line (# starts a comment line)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache", required=True)
    args = parser.parse_args()
    if (args.previous is None) != (args.previous_start is None):
        parser.error("--previous and --previous-start go together")

    get_json = cached(paced(http_get_json, time.monotonic, time.sleep), Path(args.cache))

    def rows_of(league: str, slug: str):
        return exchange_history_readings(get_json, league, slug, *EVER)

    templates = [(Path(path).name, load_price_file(Path(path))) for path in args.template]
    previous = None if args.previous is None else (args.previous, args.previous_start)
    wanted: list[str] = []
    if args.spends:
        from crafting_system.data import load_game_data  # noqa: PLC0415  (only this option needs the game data)
        from crafting_system.prices.spends import spent_names  # noqa: PLC0415

        wanted += spent_names(load_game_data())
    if args.wanted_file:
        lines = Path(args.wanted_file).read_text(encoding="utf-8-sig").splitlines()
        wanted += [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    try:
        snapshot, notes = build_snapshot(templates, rows_of, args.league, args.start, args.as_of, previous, wanted)
    except (Stopped, ValueError) as error:
        raise SystemExit(f"stopped, nothing written: {error}") from None
    for note in notes:
        print("  ", note)
    write_price_file(Path(args.out), snapshot)
    kinds: dict[str, int] = {}
    for entry in snapshot.prices.values():
        kinds[entry.source] = kinds.get(entry.source, 0) + 1
    stand_ins = sum(": stand-in, " in note for note in notes)
    unpriced = sum(": no price, " in note for note in notes)
    print(f"wrote {args.out}: {len(snapshot.prices)} prices ({', '.join(f'{n} {s}' for s, n in sorted(kinds.items()))}), {stand_ins} stand-ins, {unpriced} wanted names without a price")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
