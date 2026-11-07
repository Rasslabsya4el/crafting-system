"""Run `benchmark --heavy` on some of the benchmark routes only, so that a heavy run can split the routes over its runners (ticket #554).

    python .github/scripts/benchmark_routes.py R12,R10,R11 OUT_DIR

writes `OUT_DIR/benchmark.json` for those routes and prints the summary, exactly as `python -m crafting_system.cli benchmark --heavy` does for all of them.
"""

import sys


def main(argv: list[str]) -> int:
    from crafting_system.cli import _benchmark

    wanted = [name for name in argv[0].split(",") if name]
    known = [bench.id for bench in _benchmark.BENCHMARKS]
    unknown = [name for name in wanted if name not in known]
    if unknown:
        print(f"no benchmark route {', '.join(unknown)}; the routes are {', '.join(known)}", file=sys.stderr)
        return 2
    _benchmark.BENCHMARKS = tuple(bench for bench in _benchmark.BENCHMARKS if bench.id in wanted)
    return _benchmark.benchmark_main(["--heavy", "--out", argv[1]], command="crafting-system")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
