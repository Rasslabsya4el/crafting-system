"""Pool the tallies of a long simulation that ran on several runners, and judge the pool (ticket #555).

    PYTHONPATH=tests python -m naive_crafter merge <folder> [--route R13]

`tests/test_naive_crafter_routes.py` run with `NAIVE_RUNS`, `NAIVE_SEED` and `NAIVE_OUT` leaves one `naive-<route>-<seed>.json` per
route and runner: the exact mean and the exact spend of each step (from `risk.evaluate`'s side, the same on every runner) and the tally of that
runner's plays. This reads every such file under the folder (a downloaded run keeps one sub-folder per runner), adds the tallies of a route,
and prints the verdict on the mean and on each step with the pooled standard error (`tally.verdict_on`, 4 standard errors). It exits 1 when
any verdict disagrees, so a long simulation fails the way a short one does. It imports nothing of the planner.
"""

import argparse
import json
import sys
from pathlib import Path

from . import tally as t


def merge_folder(folder: Path, route: str | None = None) -> tuple[list[t.Verdict], dict[str, int]]:
    """The verdicts of the pooled tallies in a folder, and the number of plays pooled per route."""
    documents: dict[str, list[dict]] = {}
    for path in sorted(folder.rglob("naive-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if route is None or document["route"] == route:
            documents.setdefault(document["route"], []).append(document)
    verdicts: list[t.Verdict] = []
    plays: dict[str, int] = {}
    for name, found in sorted(documents.items()):
        exact_mean, exact_spend = found[0]["exact_mean"], found[0]["exact_spend"]
        if any(abs(d["exact_mean"] - exact_mean) > 1e-9 * max(1.0, abs(exact_mean)) or d["exact_spend"].keys() != exact_spend.keys() for d in found):
            raise SystemExit(f"{name}: the runners computed different exact sides, so their tallies are not of one thing")
        pooled = t.Tally()
        for document in found:
            pooled = pooled.merge(t.Tally.from_dict(document["tally"]))
        plays[name] = pooled.n
        verdicts.append(t.verdict_on(f"{name}, the mean cost of the given route ({pooled.n} plays)", exact_mean, pooled.mean_se()))
        for label, spent in exact_spend.items():
            verdicts.append(t.verdict_on(f"{name}, step {label!r}", spent, pooled.spend_mean_se(label)))
    return verdicts, plays


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="naive_crafter")
    commands = parser.add_subparsers(dest="command", required=True)
    merge = commands.add_parser("merge", help="pool the tallies of a long simulation and judge the pool")
    merge.add_argument("folder", type=Path)
    merge.add_argument("--route", default=None, help="only this route id (R05, R10, R11, R13)")
    arguments = parser.parse_args(argv)
    verdicts, plays = merge_folder(arguments.folder, arguments.route)
    if not verdicts:
        print(f"no naive-*.json under {arguments.folder}", file=sys.stderr)
        return 2
    for verdict in verdicts:
        print(("ok       " if verdict.agrees else "DISAGREES") + " " + str(verdict))
    print(f"plays pooled per route: {plays}")
    return 0 if all(verdict.agrees for verdict in verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
