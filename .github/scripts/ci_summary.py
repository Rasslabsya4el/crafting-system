"""The one check of the CI run (ticket #165): green only when every shard of every system passed.

Reads the folder the shard jobs uploaded, one subfolder `results-<system>-<shard>` each with `junit.xml`,
`shard.json` (what `--shard-report` wrote) and `durations.json` (what `--record-durations` wrote), and prints a
Markdown report; the same text goes to `$GITHUB_STEP_SUMMARY` when that is set. Exit 1 when:

- a shard of a system is missing, or has no result files (the job died, was cancelled or timed out);
- a test failed or errored;
- a shard ran another number of tests than it was given, or the shards of a system together do not add up to
  the tests collected (a test dropped or run twice), or two shards disagree on what the suite is;
- fewer tests collected than `--min-tests` (an empty run is not a pass);
- a test skipped for lack of the game data (a skip reason that says it is not in the cache).

Other skips are counted and listed by reason. `--merged-durations FILE` writes the seconds and the number of tests
of every group, the mean over the systems, for `tests/shard_durations.json` (see `docs/ci.md`).

Standard library only: it runs on the bare runner.
"""

import argparse
import collections
import json
import os
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DATA_SKIP_MARK = "not in the cache"
TOP_TESTS = 15


def read_shard(folder: Path) -> dict | None:
    """The numbers of one shard, or None when its files are not there."""
    try:
        suite = ET.parse(folder / "junit.xml").getroot()
        if suite.tag == "testsuites":
            suite = suite[0]
        report = json.loads((folder / "shard.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, ET.ParseError, IndexError):
        return None
    cases = suite.findall("testcase")
    skips = collections.Counter()
    for case in cases:
        for skipped in case.findall("skipped"):
            skips[(skipped.get("message") or "").strip()] += 1
    return {
        "report": report,
        "tests": len(cases),
        "failed": sum(1 for case in cases if case.find("failure") is not None or case.find("error") is not None),
        "skipped": sum(skips.values()),
        "skips": skips,
        "seconds": float(suite.get("time") or 0),
    }


def read_durations(folder: Path) -> dict:
    try:
        recorded = json.loads((folder / "durations.json").read_text(encoding="utf-8"))
        return {"tests": recorded["tests"], "groups": recorded["groups"]}
    except (OSError, ValueError, KeyError):
        return {"tests": {}, "groups": {}}


def check(results: Path, systems: list[str], shards: int, min_tests: int = 1) -> tuple[list[str], list[str], dict, dict]:
    """(problems, report lines, mean seconds per test, mean seconds and tests per group) of the whole run."""
    problems: list[str] = []
    lines = ["| system | shards | tests | passed | skipped | failed | slowest shard |", "|---|---|---|---|---|---|---|"]
    collected_by_system: dict[str, int] = {}
    skips = collections.Counter()
    recorded_by_system: dict[str, dict] = {}

    for system in systems:
        found = {}
        for number in range(1, shards + 1):
            folder = results / f"results-{system}-{number}"
            shard = read_shard(folder) if folder.is_dir() else None
            if shard is None:
                problems.append(f"{system} shard {number}/{shards}: no result files (the job did not finish)")
                continue
            found[number] = shard
            seen = recorded_by_system.setdefault(system, {"tests": {}, "groups": {}})
            for kind, values in read_durations(folder).items():
                seen[kind].update(values)
        if not found:
            continue
        shard_report = {number: shard["report"] for number, shard in found.items()}
        collected = {report["collected"] for report in shard_report.values()}
        if len(collected) != 1:
            problems.append(f"{system}: the shards collected different numbers of tests: {sorted(collected)}")
        collected_by_system[system] = max(collected)
        if max(collected) < min_tests:
            problems.append(f"{system}: only {max(collected)} tests were collected, at least {min_tests} are expected")
        for number, shard in found.items():
            if shard["tests"] != shard["report"]["selected"]:
                problems.append(
                    f"{system} shard {number}: ran {shard['tests']} tests but was given {shard['report']['selected']}"
                )
            if shard["failed"]:
                problems.append(f"{system} shard {number}: {shard['failed']} test(s) failed or errored")
        if len(found) == shards and sum(r["selected"] for r in shard_report.values()) != max(collected):
            problems.append(
                f"{system}: the shards were given {sum(r['selected'] for r in shard_report.values())} tests "
                f"in all but {max(collected)} were collected"
            )
        total = sum(shard["tests"] for shard in found.values())
        skipped = sum(shard["skipped"] for shard in found.values())
        failed = sum(shard["failed"] for shard in found.values())
        slowest = max(shard["seconds"] for shard in found.values())
        lines.append(
            f"| {system} | {len(found)}/{shards} | {total} | {total - skipped - failed} | {skipped} | {failed} "
            f"| {slowest / 60:.1f} min |"
        )
        for shard in found.values():
            skips.update(shard["skips"])

    if len(set(collected_by_system.values())) > 1:
        problems.append(f"the systems collected different numbers of tests: {collected_by_system}")
    for reason, count in skips.items():
        if DATA_SKIP_MARK in reason:
            problems.append(f"{count} test(s) skipped for lack of data: {reason}")

    if skips:
        lines += ["", "Skips by reason (all systems):", ""]
        lines += [f"- {count} x {reason or '(no reason)'}" for reason, count in skips.most_common()]

    recorded = list(recorded_by_system.values())
    tests = [seen["tests"] for seen in recorded]
    mean = {
        nodeid: statistics.fmean(seen[nodeid] for seen in tests if nodeid in seen)
        for nodeid in sorted({nodeid for seen in tests for nodeid in seen})
    }
    groups = [seen["groups"] for seen in recorded]
    mean_groups = {
        group: {
            "seconds": round(statistics.fmean(seen[group]["seconds"] for seen in groups if group in seen), 3),
            "tests": max(seen[group]["tests"] for seen in groups if group in seen),
        }
        for group in sorted({group for seen in groups for group in seen})
    }
    return problems, lines, mean, mean_groups


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", type=Path, help="folder holding the results-<system>-<shard> folders")
    parser.add_argument("--shards", type=int, required=True, help="shards per system")
    parser.add_argument("--systems", required=True, help="comma-separated system names as in the folder names")
    parser.add_argument("--merged-durations", type=Path, help="write the mean seconds and tests per group here")
    parser.add_argument("--min-tests", type=int, default=1, help="fail when fewer tests were collected")
    parser.add_argument("--job-result", default="success", help="result of the shard jobs as the workflow knows it")
    args = parser.parse_args(argv)

    problems, lines, mean, mean_groups = check(args.results, args.systems.split(","), args.shards, args.min_tests)
    if args.job_result != "success":
        problems.append(f"the shard jobs ended as '{args.job_result}'")
    if args.merged_durations is not None:
        args.merged_durations.parent.mkdir(parents=True, exist_ok=True)
        args.merged_durations.write_text(
            json.dumps(mean_groups, indent=1, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )  # fmt: skip
        top = sorted(mean.items(), key=lambda pair: -pair[1])[:TOP_TESTS]
        lines += ["", f"Slowest {len(top)} tests (mean over the systems):", ""]
        lines += [f"- {sec:.1f} s  `{nodeid}`" for nodeid, sec in top]

    verdict = "FAILED" if problems else "all shards passed"
    text = "\n".join([f"## CI summary: {verdict}", "", *lines, *([""] + [f"- PROBLEM: {p}" for p in problems] if problems else [])])
    print(text)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
