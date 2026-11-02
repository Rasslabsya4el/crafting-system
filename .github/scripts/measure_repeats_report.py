"""Step 4 of the measurement chain (ticket #399): the report of the five repeats of the whole suite.

`python3 .github/scripts/measure_repeats_report.py --in in --out out --trial false`

`--in` holds one folder per artifact `measure-rep-<k>-<os>-<shard>`, each the `out/` of one shard job of
`run_shard.py`: `slot-N/` folders (`junit.xml`, `durations.json`, `shard.json`, `pytest.log`) and the merged
`junit.xml`, `shard.json` and `durations.json` at the top. Writes into `--out`:

- `summary.md`: English, for the main chat: the repeats and systems seen, the tests per repeat, the flaky tests,
  the slots over 25 minutes, the 15 slowest groups;
- `flaky.txt`: every flaky test, one line each;
- `shard_durations.json`: the mean over the repeats of the seconds and tests of every group, in the format of
  `tests/shard_durations.json` (to be committed later, not by this step);
- `headline.txt`: one line of Russian for the diary.

Trial (`--trial true`): Ubuntu only, shard 1 of 8. The merged results of each repeat go through
`ci_summary.check`, which returns the seconds and tests of every group; its pass or fail is ignored, and the
durations come from the shards that were there. Standard library only: `ci_summary.py` is loaded by path.
"""

import argparse
import collections
import importlib.util
import json
import re
import shutil
import statistics
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSTEMS = ["ubuntu-latest", "windows-latest"]
FULL_SHARDS = 8
SLOW_SECONDS = 1500  # 25 minutes: the CI slot limit (ci.yml runs its shards with --timeout 25)
NO_RESULT = "no result (over 40 min?)"  # a slot with no pytest summary line: killed at the 40-minute limit
TOP_GROUPS = 15
FLAKY_ROWS = 60  # the summary shows this many flaky tests; flaky.txt holds all of them
FOLDER = re.compile(r"measure-rep-(\d+)-(.+)-(\d+)")
LOG_TIME = re.compile(r"in (\d+(?:\.\d+)?)s")
MERGED_FILES = ("junit.xml", "shard.json", "durations.json")


def load_ci_summary():
    spec = importlib.util.spec_from_file_location("ci_summary", HERE / "ci_summary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def outcome(case) -> str:
    """passed, failed (a failure or an error child) or skipped, for one junit testcase element."""
    if case.find("failure") is not None or case.find("error") is not None:
        return "failed"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def flaky(outcomes_by_repeat: dict) -> bool:
    """True when one test on one system has different outcomes in the repeats it ran in."""
    return len(set(outcomes_by_repeat.values())) > 1


def slot_seconds(log_text: str) -> float | None:
    """The seconds of the last line `... in 238.68s ...` of a slot's log; None when there is no such line."""
    seconds = None
    for line in log_text.splitlines():
        match = LOG_TIME.search(line)
        if match is not None:
            seconds = float(match.group(1))
    return seconds


def mean_durations(runs: list[dict]) -> dict:
    """The mean over the runs of each group's seconds and tests, in the format of tests/shard_durations.json.

    A group counts in the runs that hold it. The tests of a group are a count, so their mean is rounded to a whole number.
    """
    result = {}
    for group in sorted({name for run in runs for name in run}):
        rows = [run[group] for run in runs if group in run]
        result[group] = {
            "seconds": round(statistics.fmean(row["seconds"] for row in rows), 3),
            "tests": round(statistics.fmean(row["tests"] for row in rows)),
        }
    return result


def find_repeats(indir: Path) -> dict:
    """{repeat k: {(os, shard): folder}} for the artifact folders `measure-rep-<k>-<os>-<shard>` under `indir`."""
    repeats = collections.defaultdict(dict)
    if indir.is_dir():
        for folder in sorted(indir.iterdir()):
            match = FOLDER.fullmatch(folder.name)
            if match is not None and folder.is_dir():
                repeats[int(match.group(1))][(match.group(2), int(match.group(3)))] = folder
    return dict(sorted(repeats.items()))


def read_cases(folder: Path) -> list[tuple[str, str]]:
    """(test id, outcome) of every test in the slots of one artifact; the test id is classname::name."""
    cases = []
    for path in sorted(folder.glob("slot-*/junit.xml")):
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            continue
        for case in root.iter("testcase"):
            cases.append((f"{case.get('classname', '')}::{case.get('name', '')}", outcome(case)))
    return cases


def read_slot_times(folder: Path) -> list[tuple[int, float | None]]:
    """(slot number, seconds or None) of every slot of one artifact."""
    times = []
    for log in sorted(folder.glob("slot-*/pytest.log")):
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        times.append((int(log.parent.name.split("-")[1]), slot_seconds(text)))
    return times


def md_cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: list[list]) -> list[str]:
    if not rows:
        return ["none"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(md_cell(cell) for cell in row) + " |" for row in rows]
    return lines


def build_summary(*, trial, repeat_numbers, systems, artifact_count, cases_by, flaky_rows, slow, top_groups) -> str:
    mode = "trial (Ubuntu, shard 1 of 8)" if trial else "full (Ubuntu and Windows, shards 1 to 8)"
    lines = [
        "# repeats",
        "",
        f"Mode: {mode}. Repeats seen: {', '.join(map(str, repeat_numbers)) or 'none'}. "
        f"Systems: {', '.join(systems)}. Artifacts read: {artifact_count}.",
        "",
        "## Tests per repeat",
        "",
    ]
    lines += table(
        ["repeat", "system", "tests", "failed", "skipped"],
        [
            [k, os_name, len(cases), sum(r == "failed" for _, r in cases), sum(r == "skipped" for _, r in cases)]
            for (k, os_name), cases in sorted(cases_by.items())
        ],
    )
    lines += ["", f"## Flaky tests: {len(flaky_rows)}", ""]
    lines += table(
        ["test", "system"] + [f"r{k}" for k in repeat_numbers],
        [
            [test, os_name] + [outs.get(k, "-") for k in repeat_numbers]
            for test, os_name, outs in flaky_rows[:FLAKY_ROWS]
        ],
    )
    if len(flaky_rows) > FLAKY_ROWS:
        lines.append(f"The first {FLAKY_ROWS} of {len(flaky_rows)}; all are in flaky.txt.")
    lines += ["", f"## Slots over 25 minutes: {len(slow)}", ""]
    lines += table(
        ["system", "repeat", "slot", "seconds"],
        [
            [os_name, k, slot, f"{seconds:.1f}" if seconds is not None else NO_RESULT]
            for os_name, k, slot, seconds in slow
        ],
    )
    lines += ["", f"## {TOP_GROUPS} slowest groups (mean over the repeats)", ""]
    lines += table(
        ["group", "seconds", "tests"],
        [[group, row["seconds"], row["tests"]] for group, row in top_groups],
    )
    return "\n".join(lines) + "\n"


def run(indir: Path, outdir: Path, trial: bool) -> str:
    """Writes the four files into `outdir` and returns the headline."""
    systems = ["ubuntu-latest"] if trial else SYSTEMS
    shards = 1 if trial else FULL_SHARDS
    repeats = find_repeats(indir)
    ci_summary = load_ci_summary()

    cases_by = collections.defaultdict(list)  # (repeat, os) -> [(test id, outcome)]
    slots = []  # (os, repeat, slot number, seconds or None)
    runs = []  # the merged groups of each repeat
    artifact_count = 0
    with tempfile.TemporaryDirectory() as scratch:
        for k, folders in repeats.items():
            stage = Path(scratch) / f"r{k}"
            for (os_name, shard), folder in folders.items():
                artifact_count += 1
                target = stage / f"results-{os_name}-{shard}"
                target.mkdir(parents=True)
                for name in MERGED_FILES:
                    if (folder / name).is_file():
                        shutil.copy(folder / name, target / name)
                cases_by[(k, os_name)].extend(read_cases(folder))
                slots.extend((os_name, k, number, seconds) for number, seconds in read_slot_times(folder))
            _, _, _, groups = ci_summary.check(stage, systems, shards)
            runs.append(groups)
    durations = mean_durations(runs)

    per_test = collections.defaultdict(dict)  # (test id, os) -> {repeat: outcome}
    for (k, os_name), cases in cases_by.items():
        for test_id, result in cases:
            per_test[(test_id, os_name)][k] = result
    flaky_rows = sorted(
        ((test, os_name, outs) for (test, os_name), outs in per_test.items() if flaky(outs)),
        key=lambda row: (row[0], row[1]),
    )
    slow = sorted(
        (row for row in slots if row[3] is None or row[3] > SLOW_SECONDS),
        key=lambda row: (row[0], row[1], row[2]),
    )
    top_groups = sorted(durations.items(), key=lambda item: (-item[1]["seconds"], item[0]))[:TOP_GROUPS]
    repeat_numbers = list(repeats)

    summary = build_summary(
        trial=trial, repeat_numbers=repeat_numbers, systems=systems, artifact_count=artifact_count,
        cases_by=cases_by, flaky_rows=flaky_rows, slow=slow, top_groups=top_groups,
    )  # fmt: skip
    flaky_text = "".join(
        f"{os_name}  {test}  " + "  ".join(f"r{k}={outs[k]}" for k in repeat_numbers if k in outs) + "\n"
        for test, os_name, outs in flaky_rows
    )
    headline = (
        f"Повторов: {len(repeat_numbers)}; нестабильных тестов: {len(flaky_rows)}; "
        f"групп дольше 25 минут: {len(slow)}; новый файл длительностей готов."
    )

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.md").write_text(summary, encoding="utf-8", newline="\n")
    (outdir / "flaky.txt").write_text(flaky_text, encoding="utf-8", newline="\n")
    (outdir / "shard_durations.json").write_text(
        json.dumps(durations, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (outdir / "headline.txt").write_text(headline + "\n", encoding="utf-8", newline="\n")
    return headline


def parse_bool(text: str) -> bool:
    if text.strip().lower() not in ("true", "false"):
        raise argparse.ArgumentTypeError(f"expected true or false, got {text!r}")
    return text.strip().lower() == "true"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="indir", type=Path, required=True, help="one folder per measure-rep artifact")
    parser.add_argument("--out", type=Path, required=True, help="where the four report files go")
    parser.add_argument("--trial", type=parse_bool, required=True, help="true: Ubuntu only, shard 1 of 8")
    args = parser.parse_args(argv)
    print(run(args.indir, args.out, args.trial))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
