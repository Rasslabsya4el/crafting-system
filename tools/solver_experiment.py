"""Run the bounded ordinary-action helmet solver experiment.

Usage: ``python -m tools.solver_experiment --output out/solver/helmet.json``.
An invalid or absent committed input exits with status 2.  A measured graph or
solver limit writes a JSON report with ``status=complexity_limit`` and exits 0.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from craftoracle.solver import ExperimentInputError, ExperimentLimits, run_helmet_experiment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--max-edges", type=int, default=2_000_000)
    parser.add_argument("--build-seconds", type=float, default=120.0)
    parser.add_argument("--solve-seconds", type=float, default=120.0)
    parser.add_argument("--max-iterations", type=int, default=10_000)
    parser.add_argument("--residual", type=float, default=1e-10)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        report = run_helmet_experiment(
            ROOT,
            limits=ExperimentLimits(
                max_states=args.max_states,
                max_edges=args.max_edges,
                build_seconds=args.build_seconds,
                solve_seconds=args.solve_seconds,
                max_iterations=args.max_iterations,
                residual=args.residual,
            ),
        )
    except ExperimentInputError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(f"{report['status']}: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
