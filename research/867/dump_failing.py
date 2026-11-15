"""Run one case of the generated family as the benchmark does and keep every graph the solver refuses to certify (ticket #867).

    python research/867/dump_failing.py CASE OUT_DIR [PLAN_SECONDS]

A measurement script, not planner code: it wraps `solver._packed_solve.solve_graph` (the one solve of the envelope search, of the bound's model and
of the final solve), and on a `ConvergenceError` writes the graph, the options of the call and the names of the calling functions to
`OUT_DIR/graphs/<case>.<n>.pkl.gz` (at most `KEEP` per calling function). The case then goes on as the benchmark runs it
(`family_bench.py one --mode plan --aim-seconds 60 --gap 0.01`), so its record lies beside the graphs. A heavy run, one case a runner.
"""

import gzip
import pickle
import runpy
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEEP = 2  # graphs kept per calling function
EDGE_LIMIT = 40_000_000  # a graph with more stored edges is only described


def main() -> None:
    case, out = sys.argv[1], Path(sys.argv[2])
    seconds = sys.argv[3] if len(sys.argv) > 3 else "600"
    (out / "graphs").mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / ".github" / "scripts"))
    import crafting_system.planner._envelope as envelope
    import crafting_system.solver._packed_solve as packed_solve
    from crafting_system.solver import ConvergenceError

    real = packed_solve.solve_graph
    kept: dict[str, int] = {}
    count = [0]

    def wrapped(graph, **options):
        try:
            return real(graph, **options)
        except ConvergenceError as error:
            callers = [frame.name for frame in traceback.extract_stack()[-6:-1]]
            kind = callers[-1]
            kept[kind] = kept.get(kind, 0) + 1
            count[0] += 1
            print(f"REFUSED {case} #{count[0]} by {callers}: {graph.n:,} states, {graph.num_edges:,} edges: {str(error)[:300]}", flush=True)
            if kept[kind] <= KEEP and graph.num_edges <= EDGE_LIMIT:
                name = out / "graphs" / f"{case.replace('/', '__')}.{count[0]}.pkl.gz"
                with gzip.open(name, "wb", compresslevel=3) as file:
                    pickle.dump({"graph": graph, "kw": {k: v for k, v in options.items() if k not in ("info", "progress")}, "error": str(error), "callers": callers}, file)
            raise

    envelope.solve_graph = wrapped
    packed_solve.solve_graph = wrapped
    sys.argv = ["family_bench.py", "one", "--case", case, "--mode", "plan", "--out", str(out), "--aim-seconds", "60", "--gap", "0.01", "--plan-seconds", seconds]
    runpy.run_path(str(ROOT / ".github" / "scripts" / "family_bench.py"), run_name="__main__")


if __name__ == "__main__":
    main()
