"""Run `benchmark --heavy` on some of the benchmark routes only, so that a heavy run can split the routes over its runners (ticket #554).

    python .github/scripts/benchmark_routes.py R12,R10,R11 OUT_DIR [PRICE_FILE]

writes `OUT_DIR/benchmark.json` for those routes and prints the summary, as `python -m crafting_system.cli benchmark --heavy` does for all
of them. A CI checkout has no price file of its own, so the routes with the plain start item are priced from the committed snapshot of
the other heavy routes (`tests/fixtures/prices/routes-allflame-2026-11-10.json`, as `measure_routes.py` does; the optional third argument names another
price file from the project root, to put two snapshots side by side, #616) and a route that starts from a
vendor recipe (V01) reads the price file its target names; the latter is written to `OUT_DIR/start/benchmark.json`.

At that default snapshot R08 and R09 are not expected to finish: the pruned search (`solve_pruned`) does not end inside a runner's 25 minutes at the prices of
the newer snapshots (measured at 2026-11-07, the Prismatic Fossil at 5.87 Chaos, not 0.2; it is 20.15 in the default of 2026-11-10, not measured there), where it took 53 seconds at the old ones (#702). Run them with the older snapshot
(the third argument, `tests/fixtures/prices/routes-allflame-2026-10-31.json`) until #702 is fixed; their verdicts are then measured at the old prices (#703).
"""

import sys
from pathlib import Path

PRICES = "tests/fixtures/prices/routes-allflame-2026-11-10.json"


def main(argv: list[str]) -> int:
    from crafting_system.cli import _benchmark, _packed
    from crafting_system.config import find_project_root
    from crafting_system.prices import load_price_file

    _packed.PROGRESS = lambda text: print(text, flush=True)  # each phase of the packed solver and of the divergences as it ends
    wanted = [name for name in argv[0].split(",") if name]
    every = _benchmark.BENCHMARKS
    known = [bench.id for bench in every]
    unknown = [name for name in wanted if name not in known]
    if unknown:
        print(f"no benchmark route {', '.join(unknown)}; the routes are {', '.join(known)}", file=sys.stderr)
        return 2
    chosen = [bench for bench in every if bench.id in wanted]
    out = Path(argv[1])
    code = 0
    for folder, group, prices in (
        (out, [bench for bench in chosen if bench.start is None], load_price_file(find_project_root() / (argv[2] if len(argv) > 2 else PRICES))),
        (out / "start", [bench for bench in chosen if bench.start is not None], None),
    ):
        if group:
            _benchmark.BENCHMARKS = tuple(group)
            code = max(code, _benchmark.benchmark_main(["--heavy", "--out", str(folder)], command="crafting-system", prices=prices))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
