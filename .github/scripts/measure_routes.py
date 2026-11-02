"""The routes step of the measurement chain (ticket #399): one benchmark route per job, then one summary table.

`run --route ID --out DIR` solves one benchmark route the way `benchmark --heavy` does (`run_route` of
`crafting_system.cli._benchmark`, with the game data and the prices of the checkout) and writes `DIR/route-ID.json`:
`{"route", "seconds", "peak_mb", "entry"}`, where `entry` is that route's entry of `benchmark.json`.

`summary --dir DIR --out DIR2` reads every `route-*.json` under DIR and writes `DIR2/summary.md` (one table, the rows
in BENCHMARK_ORDER, a route with no file shown as `missing`) and `DIR2/headline.txt` (one line of Russian for the diary).

Only `run` imports the crafting package, so `summary` needs nothing but the standard library.
"""

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

PRICES = "tests/fixtures/prices/routes-allflame-2026-10-31.json"  # from the project root; the prices the bloat step and the heavy route tests use
BENCHMARK_ORDER = ["R12", "R10", "R11", "R05", "R13", "R08", "R09", "R04", "R14", "V01"]
COLUMNS = [
    "route",
    "seconds",
    "peak MB",
    "solver mean",
    "solver p50",
    "solver p90",
    "success probability",
    "given route mean",
    "solver not dearer",
    "error",
]
MISSING = "missing"
DASH = "—"
ERROR_CHARS = 120


def _peak_mb() -> float | None:
    """The peak memory of this process in MB: ru_maxrss is kilobytes on Linux; None where `resource` is missing."""
    try:
        import resource
    except ImportError:
        return None
    if sys.platform != "linux":
        return None
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def run_route_file(route_id: str, out: Path) -> int:
    """Solve one benchmark route and write `out/route-ID.json`; 2 when there is no such benchmark route."""
    from crafting_system.cli._benchmark import BENCHMARKS, run_route
    from crafting_system.cli._inputs import write_json
    from crafting_system.config import find_project_root, load_config
    from crafting_system.data import load_game_data
    from crafting_system.prices import load_price_file

    bench = next((item for item in BENCHMARKS if item.id == route_id), None)
    if bench is None:
        known = ", ".join(item.id for item in BENCHMARKS)
        print(f"Error: no benchmark route {route_id!r} (the routes are {known})", file=sys.stderr)
        return 2
    config = load_config(os.environ)
    game = load_game_data(cache_dir=config.cache_dir)
    root = find_project_root()
    began = time.monotonic()
    # a CI checkout has no price file of its own; a route with its own start (V01) reads the price file its target names
    prices = load_price_file(root / PRICES) if bench.start is None else None
    entry, _ = run_route(bench, game, root, config, prices, None, heavy=True)
    seconds = time.monotonic() - began
    path = out / f"route-{route_id}.json"
    write_json(path, {"route": route_id, "seconds": seconds, "peak_mb": _peak_mb(), "entry": entry})
    print(f"{route_id}: {seconds:.1f} s, written to {path}")
    return 0


def read_routes(folder: Path) -> list[dict]:
    """Every `route-*.json` under `folder`; a file that cannot be read is named on stderr and skipped."""
    records = []
    for path in sorted(folder.rglob("route-*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"Warning: {path} not read: {error}", file=sys.stderr)
            continue
        if isinstance(record, dict) and "route" in record:
            records.append(record)
    return records


def _value(item):
    """An estimate may be written as an object (its `value`) or a list (its first item); a number is itself."""
    if isinstance(item, Mapping):
        return item.get("value")
    if isinstance(item, (list, tuple)):
        return item[0] if item else None
    return item


def _num(item) -> str:
    value = _value(item)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return DASH
    return f"{value:.1f}"


def _percent(item) -> str:
    value = _value(item)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return DASH
    return f"{value * 100:.1f}%"


def _yes_no(item) -> str:
    if item is None:
        return DASH
    return "yes" if item else "no"


def _error_text(item) -> str:
    if not item:
        return DASH
    text = " ".join(str(item).split()).replace("|", "\\|")
    return text if len(text) <= ERROR_CHARS else text[: ERROR_CHARS - 3] + "..."


def _row(route: str, record: Mapping | None) -> list[str]:
    if record is None:
        return [route, *([DASH] * 8), MISSING]
    entry = record.get("entry") or {}
    solver = entry.get("solver") or {}
    given = entry.get("given_route") or {}
    return [
        route,
        _num(record.get("seconds")),
        _num(record.get("peak_mb")),
        _num(solver.get("mean")),
        _num(solver.get("p50")),
        _num(solver.get("p90")),
        _percent(solver.get("success")),
        _num(given.get("mean")),
        _yes_no(entry.get("solver_not_dearer")),
        _error_text(entry.get("error")),
    ]


def _headline(by_id: Mapping[str, Mapping]) -> str:
    """The Russian line for the diary: routes solved, the longest one, and how often the solver is not dearer."""
    solved = [by_id[route] for route in BENCHMARK_ORDER if route in by_id and (by_id[route].get("entry") or {}).get("solver")]
    timed = [record for record in solved if isinstance(record.get("seconds"), (int, float))]
    if timed:
        longest = max(timed, key=lambda record: record["seconds"])
        slowest = f"самый долгий {longest['route']} — {longest['seconds'] / 60:.1f} мин"
    else:
        slowest = "самый долгий —"
    compared = [record for record in solved if (record.get("entry") or {}).get("solver_not_dearer") is not None]
    cheaper = sum(1 for record in compared if record["entry"]["solver_not_dearer"])
    return (
        f"Маршрутов посчитано: {len(solved)} из {len(BENCHMARK_ORDER)}; {slowest}; "
        f"решатель не дороже гайда на {cheaper} из {len(compared)}."
    )


def build_summary(rows: Iterable[Mapping]) -> tuple[str, str]:
    """The Markdown summary table and the headline line, from the route records (a route with no record is `missing`).

    A route counts as solved when its entry has a solver result; the "not dearer" count runs over the solved routes that
    have a given route to compare with.
    """
    by_id = {record["route"]: record for record in rows if record.get("route") in BENCHMARK_ORDER}
    lines = [
        "# routes",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "|".join("---" for _ in COLUMNS) + "|",
    ]
    lines += ["| " + " | ".join(_row(route, by_id.get(route))) + " |" for route in BENCHMARK_ORDER]
    return "\n".join(lines) + "\n", _headline(by_id)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="solve one benchmark route and write route-ID.json")
    run.add_argument("--route", required=True, metavar="ID", help="one of " + ", ".join(BENCHMARK_ORDER))
    run.add_argument("--out", required=True, type=Path, metavar="DIR", help="where to write route-ID.json")
    summary = commands.add_parser("summary", help="write summary.md and headline.txt from every route-*.json")
    summary.add_argument("--dir", required=True, type=Path, metavar="DIR", help="folder searched for route-*.json")
    summary.add_argument("--out", required=True, type=Path, metavar="DIR2", help="where to write the two files")
    args = parser.parse_args(argv)

    if args.command == "run":
        return run_route_file(args.route, args.out)
    table, headline = build_summary(read_routes(args.dir))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.md").write_text(table, encoding="utf-8", newline="\n")
    (args.out / "headline.txt").write_text(headline + "\n", encoding="utf-8", newline="\n")
    print(f"Summary written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
