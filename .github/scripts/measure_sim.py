"""The simulation check of the measurement chain (ticket #399, piece G): the planner's computed mean cost against a large simulation.

    python .github/scripts/measure_sim.py run     --route ID --part K --parts P --out DIR [--runs-scale S]
    python .github/scripts/measure_sim.py summary --dir DIR  --out DIR2

`run` builds the plan of one benchmark route the way `run_route` does (`state_bloat.plan_of`, without the risk run) and writes
`DIR/sim-ID-K.json` = `{"route", "part", "parts", "kinds"}`, where `kinds` holds, per kind:

* `solver`: the solver's policy played on concrete items with random dice (`verify`, the function behind `--verify`); `exact_mean`
  is its computed mean with the start price, as `--verify` compares it;
* `guide`, `guide_completed`: the given route the benchmark has as written, and its completed route if it has one, played through
  `simulate_route`; `exact_mean` is the exact given mean as `run_route` computes it (on the same plan), from part 1 only (other parts write null).

Each kind holds the sums of its runs (`n`, `successes`, `stopped`, `unfinished`, `sum` and `sumsq` of the run totals), not the list.
A kind that raises writes `"error"` instead and the rest go on; the run exits 1 when any kind failed.

`summary --dir DIR --out DIR2` pools the parts of every route and kind (`pool`) and writes `DIR2/summary.md` (`build_summary`)
and `DIR2/headline.txt` (one line of Russian for the diary).

Only `run` imports the crafting package, so `summary` needs nothing but the standard library.
"""

import argparse
import dataclasses
import importlib.util
import math
import os
import sys
import types
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

PRICES = "tests/fixtures/prices/routes-allflame-2026-10-31.json"  # from the project root; the prices the bloat and routes steps use
HERE = Path(__file__).resolve().parent
ROUTE_ORDER = ["R12", "R10", "R11", "R05", "R13", "R08", "R09", "R04", "R14", "V01"]
KIND_ORDER = ["solver", "guide", "guide_completed"]
RUNS_PER_PART = {"R04": 300, "R14": 300}  # the long routes play fewer runs per part; every other route plays DEFAULT_RUNS
DEFAULT_RUNS = 5000
MIN_TRIAL_RUNS = 20
SEED_BASE = 1000  # part K plays with the seed 1000 + K
DISAGREE = 5.0  # |z| above this is a disagreement
WATCH = 3.0  # |z| above this (and up to DISAGREE) is watched
DASH = "—"
COLUMNS = [
    "route",
    "kind",
    "exact mean",
    "simulated mean ± SE",
    "z",
    "runs",
    "successes",
    "stopped",
    "unfinished",
    "parts",
]
PARAGRAPH = (
    "Each route's computed mean cost is compared with the mean of a large simulation. `solver` plays the solver's policy on "
    "concrete items with random dice (`verify`) and is compared with the computed mean of the plan, start price included. "
    "`guide` plays the given route the guide wrote, and `guide_completed` the same route with a last restart rule (`simulate_route`); "
    "both are compared with the exact given-route mean the benchmark computes. The runs of all parts are pooled. "
    "z = (simulated mean - exact mean) / standard error: about 0 when the simulation agrees with the computation; "
    "|z| above 5 is a disagreement, |z| between 3 and 5 is watched. Stopped and unfinished runs ended without the goal "
    "(for a guide, a gap of the route: no rule covers the state, or the game refuses the action)."
)


# --- pooling and the summary --------------------------------------------------------------------


def runs_for(route: str, scale: float = 1.0) -> int:
    """The runs one part of `route` plays: its base count times `scale`, rounded up, and at least MIN_TRIAL_RUNS."""
    base = RUNS_PER_PART.get(route, DEFAULT_RUNS)
    return max(MIN_TRIAL_RUNS, math.ceil(round(base * scale, 9)))  # round(): 5000 * 0.02 must be 100, not 100.00000000000001


def pool(parts: Sequence[Mapping]) -> dict[tuple[str, str], dict]:
    """The pooled row of every (route, kind) of the parts: sums of the runs, the mean, variance, SE and z against the exact mean.

    The exact mean is the first non-null `exact_mean` in part order (normally part 1's). A kind that failed in a part adds no runs
    and is not counted in `parts_seen`; its exact mean still counts.
    """
    rows: dict[tuple[str, str], dict] = {}
    for part in sorted(parts, key=lambda item: int(item["part"])):
        for kind, record in part["kinds"].items():
            row = rows.setdefault(
                (part["route"], kind),
                {
                    "route": part["route"], "kind": kind, "exact": None, "n": 0, "successes": 0, "stopped": 0,
                    "unfinished": 0, "sum": 0.0, "sumsq": 0.0, "parts_seen": 0, "parts": part["parts"],
                    "exact_infinite": False,
                },
            )  # fmt: skip
            if row["exact"] is None and record.get("exact_mean") is not None:
                row["exact"] = float(record["exact_mean"])
            row["exact_infinite"] = row["exact_infinite"] or bool(record.get("exact_infinite"))
            if "error" in record:
                continue
            row["parts_seen"] += 1
            for key in ("n", "successes", "stopped", "unfinished"):
                row[key] += int(record[key])
            row["sum"] += float(record["sum"])
            row["sumsq"] += float(record["sumsq"])
    for row in rows.values():
        _finish(row)
    return rows


def _finish(row: dict) -> None:
    """The mean, variance, standard error and z of a pooled row; None where the numbers do not exist (no runs, one run, no exact mean)."""
    n = row["n"]
    row["mean"] = row["sum"] / n if n else None
    row["var"] = row["se"] = row["z"] = None
    if n > 1:
        row["var"] = max((row["sumsq"] - n * row["mean"] ** 2) / (n - 1), 0.0)
        row["se"] = math.sqrt(row["var"] / n)
        if row["exact"] is not None and row["se"] > 0:
            row["z"] = (row["mean"] - row["exact"]) / row["se"]


def _fmt(value: float | None, digits: int = 2) -> str:
    return DASH if value is None else f"{value:.{digits}f}"


def _row_cells(row: Mapping | None, route: str) -> list[str]:
    if row is None:
        return [route, DASH, DASH, DASH, DASH, DASH, DASH, DASH, DASH, DASH]
    mean = _fmt(row["mean"])
    if row["mean"] is not None:
        mean = f"{mean} ± {_fmt(row['se'])}" if row["se"] is not None else f"{mean} ± {DASH}"
    exact = "inf" if row["exact_infinite"] and row["exact"] is None else _fmt(row["exact"])
    return [
        route,
        row["kind"],
        exact,
        mean,
        _fmt(row["z"]),
        str(row["n"]),
        str(row["successes"]),
        str(row["stopped"]),
        str(row["unfinished"]),
        f"{row['parts_seen']} of {row['parts']}",
    ]


def _line(row: Mapping) -> str:
    return f"{row['route']} {row['kind']}"


def build_summary(rows: Iterable[Mapping]) -> tuple[str, str]:
    """The text of `summary.md` and the headline line, from the pooled rows (`pool(parts).values()`).

    The table has the routes in ROUTE_ORDER; a route's kinds are the ones it has rows for (`guide_completed` only where the benchmark
    has a completed route), and a route with no rows is one row of dashes.
    """
    known = [row for row in rows if row["route"] in ROUTE_ORDER]
    by_key = {(row["route"], row["kind"]): row for row in known}
    table = []
    for route in ROUTE_ORDER:
        kinds = [kind for kind in KIND_ORDER if (route, kind) in by_key]
        if not kinds:
            table.append(_row_cells(None, route))
        table += [_row_cells(by_key[(route, kind)], route) for kind in kinds]
    checked = [row for row in known if row["z"] is not None]
    disagree = [row for row in checked if abs(row["z"]) > DISAGREE]
    watch = [row for row in checked if WATCH < abs(row["z"]) <= DISAGREE]
    stopped = [row for row in known if row["stopped"] or row["unfinished"]]
    infinite = [row for row in known if row["exact_infinite"]]
    lines = [
        "# simulation check",
        "",
        PARAGRAPH,
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "|".join("---" for _ in COLUMNS) + "|",
        *("| " + " | ".join(cells) + " |" for cells in table),
        "",
        "**disagree** (|z| > 5):",
        *_bullets([f"{_line(row)}: z = {row['z']:.2f}" for row in disagree]),
        "",
        "**watch** (3 < |z| ≤ 5):",
        *_bullets([f"{_line(row)}: z = {row['z']:.2f}" for row in watch]),
        "",
        "**exact mean not finite** (the route has gaps: no z):",
        *_bullets([f"{_line(row)}: the exact mean is infinite" for row in infinite]),
        "",
        "**stopped or unfinished runs**:",
        *_bullets([f"{_line(row)}: stopped {row['stopped']}, unfinished {row['unfinished']}" for row in stopped]),
    ]
    headline = _headline(known, checked)
    return "\n".join(lines) + "\n", headline


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- none"]


def _headline(known: Sequence[Mapping], checked: Sequence[Mapping]) -> str:
    disagree = sum(1 for row in checked if abs(row["z"]) > DISAGREE)
    watch = sum(1 for row in checked if WATCH < abs(row["z"]) <= DISAGREE)
    routes = len({row["route"] for row in known})
    if checked:
        top = max(checked, key=lambda row: abs(row["z"]))
        largest = f"самое большое |z| = {abs(top['z']):.2f} у {_line(top)}."
    else:
        largest = "самое большое |z| = —."
    return (
        f"Проверка симуляцией: маршрутов {routes}; расхождений (|z|>5): {disagree}; "
        f"под наблюдением (3<|z|≤5): {watch}; {largest}"
    )


# --- run: one part of one route ------------------------------------------------------------------


def _load_sibling(name: str):
    """A module of this folder, loaded by path (as the tests load the scripts): `state_bloat` for its `plan_of`."""
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sums(report) -> dict:
    costs = report.costs
    return {
        "n": report.runs,
        "successes": report.successes,
        "stopped": report.stopped,
        "unfinished": report.unfinished,
        "sum": sum(costs),
        "sumsq": sum(cost * cost for cost in costs),
    }


def _finite(value: float | None) -> float | None:
    """A number JSON can hold; an infinite or missing mean is written as null."""
    if value is None or not math.isfinite(value):
        return None
    return float(value)


def _exact_of(totals: Mapping | None) -> tuple[float | None, bool]:
    """(exact mean, infinite) of a route entry of `run_route`: run_route writes a null mean for an infinite one (its gaps)."""
    if totals is None:
        return None, False
    mean = totals.get("mean")
    return _finite(mean), mean is None or (isinstance(mean, float) and math.isinf(mean))  # null in an entry read back, inf in one in hand


def _message(error: BaseException) -> str:
    return str(error) or type(error).__name__


_NO_RISK = types.SimpleNamespace(p90=types.SimpleNamespace(value=math.nan))  # see `run_part`: verify reads only `risk.p90.value`


def run_part(route_id: str, part: int, parts: int, out: Path, runs_scale: float = 1.0) -> int:
    """Play one part of one benchmark route and write `out/sim-ID-K.json`; 2 for a bad argument, 1 when a kind failed."""
    from crafting_system.cli._benchmark import BENCHMARKS, _given_route
    from crafting_system.cli._inputs import write_json
    from crafting_system.cli._route import evaluate_route, load_route
    from crafting_system.cli._route_sim import simulate_route
    from crafting_system.cli._verify import verify
    from crafting_system.config import find_project_root, load_config
    from crafting_system.data import load_game_data
    from crafting_system.prices import load_price_file

    bench = next((item for item in BENCHMARKS if item.id == route_id), None)
    if bench is None:
        known = ", ".join(item.id for item in BENCHMARKS)
        print(f"Error: no benchmark route {route_id!r} (the routes are {known})", file=sys.stderr)
        return 2
    if not 1 <= part <= parts:
        print(f"Error: part {part} is not one of 1..{parts}", file=sys.stderr)
        return 2
    config = load_config(os.environ)
    game = load_game_data(cache_dir=config.cache_dir)
    root = find_project_root()
    # a CI checkout has no price file of its own; a route with its own start (V01) reads the price file its target names
    prices = load_price_file(root / PRICES) if bench.start is None else None
    runs = runs_for(route_id, runs_scale)
    seed = SEED_BASE + part
    path = out / f"sim-{route_id}-{part}.json"
    document: dict = {"route": route_id, "part": part, "parts": parts, "kinds": {}}
    failed = False

    def record(kind: str, body: dict) -> None:
        nonlocal failed
        failed = failed or "error" in body
        document["kinds"][kind] = body
        write_json(path, document)  # written after every kind, so a later failure keeps the earlier ones

    plan = None
    plan_error = "no plan"
    try:
        plan = _load_sibling("state_bloat").plan_of(bench, game, root, config, prices, "auto")
    except Exception as error:
        plan_error = _message(error)

    # the guide as written (bench.route; V01 has none) and the completed route (bench.completed; most routes have none)
    guides = [(kind, path) for kind, path in (("guide", bench.route), ("guide_completed", bench.completed)) if path is not None]
    exact: dict[str, tuple[float | None, bool]] = {kind: (None, False) for kind, _ in guides}
    exact_note = None
    if part == 1 and guides and plan is not None:
        # the exact given means, first and on this very plan, as `run_route` computes them (`evaluate_route`, `_given_route`
        # with the start price added): like for like with the simulation below, and no second plan in memory
        for kind, route_path in guides:
            try:
                result = evaluate_route(plan, load_route(root / route_path, plan, game), game)
                exact[kind] = _exact_of(_given_route(plan, result, game, plan.start_price.chaos))
            except Exception as error:
                exact_note = _message(error)

    try:
        if plan is None:
            raise RuntimeError(plan_error)
        # `verify` reports the computed p90 next to the mean; the plan was made without the risk run (its grid on R04 and R14
        # takes a runner's memory), so it gets a stand-in whose p90 is NaN: only the mean is compared here
        checked = plan if plan.risk is not None else dataclasses.replace(plan, risk=_NO_RISK)
        check = verify(game, checked, runs=runs, seed=seed)
        infinite = math.isinf(check.computed_mean)
        record("solver", {"exact_mean": _finite(check.computed_mean), "exact_infinite": infinite, **_sums(check.report)})
    except Exception as error:
        record("solver", {"exact_mean": None, "exact_infinite": False, "error": _message(error)})

    for kind, route_path in guides:
        mean, infinite = exact[kind]
        extra = {"exact_note": exact_note} if mean is None and not infinite and exact_note else {}
        try:
            if plan is None:
                raise RuntimeError(plan_error)
            route = load_route(root / route_path, plan, game)
            report = simulate_route(game, plan, route, runs=runs, seed=seed)
            record(kind, {"exact_mean": mean, "exact_infinite": infinite, **extra, **_sums(report)})
        except Exception as error:
            record(kind, {"exact_mean": mean, "exact_infinite": infinite, **extra, "error": _message(error)})

    print(f"{route_id} part {part}/{parts}: {runs} runs per kind, written to {path}")
    return 1 if failed else 0


# --- summary -------------------------------------------------------------------------------------


def read_parts(folder: Path) -> list[dict]:
    """Every `sim-*.json` under `folder`; a file that cannot be read is named on stderr and skipped."""
    import json

    parts = []
    for path in sorted(folder.rglob("sim-*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"Warning: {path} not read: {error}", file=sys.stderr)
            continue
        if isinstance(record, dict) and "route" in record and isinstance(record.get("kinds"), dict):
            parts.append(record)
    return parts


def summarize(folder: Path, out: Path) -> int:
    table, headline = build_summary(list(pool(read_parts(folder)).values()))
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.md").write_text(table, encoding="utf-8", newline="\n")
    (out / "headline.txt").write_text(headline + "\n", encoding="utf-8", newline="\n")
    print(f"Summary written to {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="play one part of one benchmark route and write sim-ID-K.json")
    run.add_argument("--route", required=True, metavar="ID", help="one of " + ", ".join(ROUTE_ORDER))
    run.add_argument("--part", required=True, type=int, metavar="K", help="this part, 1 to --parts")
    run.add_argument("--parts", required=True, type=int, metavar="P", help="how many parts the route is split into")
    run.add_argument("--out", required=True, type=Path, metavar="DIR", help="where to write sim-ID-K.json")
    run.add_argument("--runs-scale", type=float, default=1.0, metavar="S", help="multiply the runs per part (trial: 0.02; at least 20 runs)")
    summary = commands.add_parser("summary", help="pool the parts and write summary.md and headline.txt")
    summary.add_argument("--dir", required=True, type=Path, metavar="DIR", help="folder searched for sim-*.json")
    summary.add_argument("--out", required=True, type=Path, metavar="DIR2", help="where to write the two files")
    args = parser.parse_args(argv)

    if args.command == "run":
        return run_part(args.route, args.part, args.parts, args.out, args.runs_scale)
    return summarize(args.dir, args.out)


if __name__ == "__main__":
    sys.exit(main())
