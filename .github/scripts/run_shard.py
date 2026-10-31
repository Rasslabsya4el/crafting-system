"""Run one CI shard of the suite on several processes at once (ticket #165).

`python .github/scripts/run_shard.py --shard 3/8 --procs 4 --out out -- <pytest arguments>`

The suite is planned over `shards * procs` slots (`pytest --shard SLOT/TOTAL`, see `tests/shard_support.py`); this
runs the `procs` slots of shard 3, each in its own pytest process, and writes into `--out` what the summary check
reads: `junit.xml` (all tests of the shard), `shard.json` (collected and selected counts) and `durations.json`
(seconds per test). A slot is a whole number of groups, so a module's fixtures, a route solved for one, are built
once in one process. The logs of the slots are printed one after the other when all are done.

Exit 0 only when every slot finished and passed (a slot with no tests, pytest's exit code 5, counts as passed).
Standard library only.
"""

import argparse
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

NO_TESTS = 5  # pytest's exit code for "no tests were collected"


def slot_numbers(shard: int, shards: int, procs: int) -> list[int]:
    """The slots (counted from 1, out of shards * procs) that shard `shard` of `shards` runs."""
    if not 1 <= shard <= shards:
        raise ValueError(f"shard {shard} is not from 1 to {shards}")
    return [(shard - 1) * procs + k for k in range(1, procs + 1)]


def merge(out: Path, slot_dirs: list[Path]) -> bool:
    """junit.xml, shard.json and durations.json of the shard from its slots; False when a slot left no files."""
    suites, reports, durations = [], [], {"tests": {}, "groups": {}}
    for folder in slot_dirs:
        try:
            suite = ET.parse(folder / "junit.xml").getroot()
            suites.append(suite[0] if suite.tag == "testsuites" else suite)
            reports.append(json.loads((folder / "shard.json").read_text(encoding="utf-8")))
            recorded = json.loads((folder / "durations.json").read_text(encoding="utf-8"))
            durations["tests"].update(recorded["tests"])
            durations["groups"].update(recorded["groups"])
        except (OSError, ValueError, KeyError, ET.ParseError, IndexError):
            return False
    collected = {report["collected"] for report in reports}
    if len(collected) != 1:
        return False
    root = ET.Element("testsuites")
    merged = ET.SubElement(root, "testsuite", name="pytest")
    for suite in suites:
        merged.extend(suite.findall("testcase"))
    cases = merged.findall("testcase")
    for attribute, tag in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped")):
        merged.set(attribute, str(sum(1 for case in cases if case.find(tag) is not None)))
    merged.set("tests", str(len(cases)))
    merged.set("time", f"{max(float(suite.get('time') or 0) for suite in suites):.3f}")
    ET.ElementTree(root).write(out / "junit.xml", encoding="utf-8", xml_declaration=True)
    (out / "shard.json").write_text(
        json.dumps({"collected": collected.pop(), "selected": sum(report["selected"] for report in reports)}) + "\n",
        encoding="utf-8",
    )
    (out / "durations.json").write_text(json.dumps(durations, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shard", required=True, help="I/N: this is shard I of N")
    parser.add_argument("--procs", type=int, required=True, help="pytest processes at once")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=25, help="minutes before the slots are killed")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="after --: the arguments for every pytest process")
    args = parser.parse_args(argv)

    index, shards = (int(part) for part in args.shard.split("/"))
    slots = slot_numbers(index, shards, args.procs)
    total = shards * args.procs
    extra = args.pytest_args[1:] if args.pytest_args[:1] == ["--"] else args.pytest_args
    args.out.mkdir(parents=True, exist_ok=True)

    running = []
    for slot in slots:
        folder = args.out / f"slot-{slot}"
        folder.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable, "-m", "pytest", *extra, "--shard", f"{slot}/{total}",
            "--junitxml", str(folder / "junit.xml"), "--shard-report", str(folder / "shard.json"),
            "--record-durations", str(folder / "durations.json"),
        ]  # fmt: skip
        log = (folder / "pytest.log").open("w", encoding="utf-8")
        running.append((slot, folder, log, subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)))

    deadline = time.monotonic() + args.timeout * 60
    codes = {}
    for slot, _, _, process in running:
        try:
            codes[slot] = process.wait(timeout=max(1.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            for _, _, _, other in running:
                other.kill()
            codes[slot] = -1
    for _, _, log, process in running:
        process.wait()
        log.close()

    ok = True
    for slot, folder, _, _ in running:
        text = (folder / "pytest.log").read_text(encoding="utf-8", errors="replace")
        print(f"::group::slot {slot}/{total} (exit {codes[slot]})")
        print(text)
        print("::endgroup::")
        report = folder / "shard.json"
        empty = report.is_file() and json.loads(report.read_text(encoding="utf-8")).get("selected") == 0
        if codes[slot] != 0 and not (codes[slot] == NO_TESTS and empty):
            print(f"slot {slot}/{total} failed (exit code {codes[slot]})")
            ok = False
    if not merge(args.out, [folder for _, folder, _, _ in running]):
        print("a slot left no result files", file=sys.stderr)
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
