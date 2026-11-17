"""The heavy benchmark's record of the default-on plans, and the check of a new run against it (#1109).

    python .github/scripts/heavy_benchmark.py record FIRST_DIR SECOND_DIR RECORD.json
    python .github/scripts/heavy_benchmark.py check RECORD.json RUN_DIR

Each DIR holds the `benchmark.json` files of one run of `benchmark_routes.py ... --net` (any depth: one per runner, with their `start` and
`own` folders). `record` writes the record of two runs (`crafting_system.benchmark_record.make_record`) and prints each route's two costs and
spread; `check` prints each route's verdict against the record and exits 1 when a route fails. The rule is the module's text.
"""

import json
import sys
from pathlib import Path


def run_of(folder: Path) -> dict:
    from crafting_system.benchmark_record import merge_documents

    files = sorted(folder.rglob("benchmark.json"))
    return merge_documents(json.loads(path.read_text(encoding="utf-8")) for path in files)


def cost(figure: float | None) -> str:
    return "no plan" if figure is None else f"{figure:,.2f} c"


def main(argv: list[str]) -> int:
    from crafting_system.benchmark_record import check_run, failed, make_record, render_check

    if len(argv) == 4 and argv[0] == "record":
        record = make_record(run_of(Path(argv[1])), run_of(Path(argv[2])))
        Path(argv[3]).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        for name, route in record["routes"].items():
            first, second = route["runs"]
            share = "" if route["spread_share"] is None else f", spread {route['spread_share']:.2%}"
            ceiling = "" if route["ceiling"] is None else f", ceiling {cost(route['ceiling'])}"
            print(f"{name}: {cost(first['mean'])} / {cost(second['mean'])} ({route['state']}{share}{ceiling})")
        print(f"Record written to {argv[3]}")
        return 0
    if len(argv) == 3 and argv[0] == "check":
        verdicts = check_run(json.loads(Path(argv[1]).read_text(encoding="utf-8")), run_of(Path(argv[2])))
        print(render_check(verdicts))
        return 1 if failed(verdicts) else 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
