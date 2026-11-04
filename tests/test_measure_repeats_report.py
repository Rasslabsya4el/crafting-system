"""The report of the five repeats of the suite (ticket #399, step 4 of the measurement chain) on small hand-made input."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "measure_repeats_report.py"
spec = importlib.util.spec_from_file_location("measure_repeats_report", SCRIPT)
measure_repeats_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_repeats_report)

flaky = measure_repeats_report.flaky
slot_seconds = measure_repeats_report.slot_seconds
mean_durations = measure_repeats_report.mean_durations


def test_a_test_passing_in_one_repeat_and_failing_in_another_is_flaky():
    assert flaky({1: "passed", 2: "failed"})


def test_a_test_skipped_in_both_repeats_is_not_flaky():
    assert not flaky({1: "skipped", 2: "skipped"})


def test_a_test_with_one_outcome_in_every_repeat_is_not_flaky():
    assert not flaky({1: "failed", 2: "failed", 3: "failed"})


def test_slot_seconds_reads_the_pytest_summary_line():
    log = "tests/test_a.py ..\n1446 passed, 29671 deselected in 238.68s (0:03:58)\n"
    assert slot_seconds(log) == 238.68


def test_slot_seconds_takes_the_last_matching_line():
    assert slot_seconds("in 3s\nmiddle\n1446 passed in 12.5s\n") == 12.5


def test_slot_seconds_is_none_for_a_log_with_no_summary_line():
    assert slot_seconds("tests/test_a.py ..\nKilled after 40 minutes\n") is None


def test_mean_durations_averages_seconds_and_tests_over_the_runs():
    first = {"tests/test_a.py": {"seconds": 10.0, "tests": 4}, "tests/test_b.py": {"seconds": 1.0, "tests": 2}}
    second = {"tests/test_a.py": {"seconds": 12.0, "tests": 4}}
    assert mean_durations([first, second]) == {
        "tests/test_a.py": {"seconds": 11.0, "tests": 4},
        "tests/test_b.py": {"seconds": 1.0, "tests": 2},
    }


def write_shard(folder: Path, cases: str, seconds: float, slot_log: str) -> None:
    """One artifact folder as the shard job uploads it: the merged files at the top and one slot."""
    folder.mkdir(parents=True)
    suite = f'<testsuites><testsuite name="pytest" time="{seconds}">{cases}</testsuite></testsuites>'
    (folder / "junit.xml").write_text(suite, encoding="utf-8")
    (folder / "shard.json").write_text(json.dumps({"collected": 2, "selected": 2}), encoding="utf-8")
    groups = {"tests/test_a.py": {"seconds": seconds, "tests": 2}}
    (folder / "durations.json").write_text(json.dumps({"tests": {}, "groups": groups}), encoding="utf-8")
    slot = folder / "slot-1"
    slot.mkdir()
    (slot / "junit.xml").write_text(suite, encoding="utf-8")
    (slot / "pytest.log").write_text(slot_log, encoding="utf-8")


def test_the_report_of_two_hand_made_repeats_in_trial(tmp_path):
    passed = '<testcase classname="tests.test_a" name="test_x"/>'
    failed = '<testcase classname="tests.test_a" name="test_x"><failure message="boom"/></testcase>'
    other = '<testcase classname="tests.test_a" name="test_y"/>'
    indir = tmp_path / "in"
    write_shard(indir / "measure-rep-1-ubuntu-latest-1", passed + other, 10.0, "2 passed in 1600.0s (0:26:40)\n")
    write_shard(indir / "measure-rep-2-ubuntu-latest-1", failed + other, 20.0, "killed\n")
    outdir = tmp_path / "out"

    headline = measure_repeats_report.run(indir, outdir, trial=True)

    assert headline == (
        "Повторов: 2; нестабильных тестов: 1; групп дольше 25 минут: 2; новый файл длительностей готов."
    )
    assert (outdir / "headline.txt").read_text(encoding="utf-8").strip() == headline
    durations = json.loads((outdir / "shard_durations.json").read_text(encoding="utf-8"))
    assert durations == {"tests/test_a.py": {"seconds": 15.0, "tests": 2}}
    assert "tests.test_a::test_x" in (outdir / "flaky.txt").read_text(encoding="utf-8")
    summary = (outdir / "summary.md").read_text(encoding="utf-8")
    assert summary.startswith("# repeats\n")
    assert "no result (over 40 min?)" in summary
