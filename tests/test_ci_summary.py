"""The summary check of the CI run (ticket #165): green only when every shard of every system ran and passed."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "ci_summary.py"
spec = importlib.util.spec_from_file_location("ci_summary", SCRIPT)
ci_summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_summary)

DATA_SKIP = "the real game data is not in the cache: missing"
COE_SKIP = "no local Craft of Exile copy"


def write_shard(results, system, number, *, tests=3, selected=None, collected=6, skips=(), failures=0, seconds=2.0):
    """A shard folder as the job uploads it: `tests` test cases, the first `len(skips)` skipped, then `failures` failed."""
    folder = results / f"results-{system}-{number}"
    folder.mkdir(parents=True)
    cases = []
    for index in range(tests):
        body = ""
        if index < len(skips):
            body = f'<skipped type="pytest.skip" message="{skips[index]}"/>'
        elif index < len(skips) + failures:
            body = '<failure message="boom"/>'
        cases.append(f'<testcase classname="t" name="test_{system}_{number}_{index}" time="1.0">{body}</testcase>')
    xml = f'<testsuites><testsuite name="pytest" tests="{tests}" time="{seconds}">{"".join(cases)}</testsuite></testsuites>'
    (folder / "junit.xml").write_text(xml, encoding="utf-8")
    report = {"shard": number, "shards": 2, "collected": collected, "selected": tests if selected is None else selected}
    (folder / "shard.json").write_text(json.dumps(report), encoding="utf-8")
    recorded = {
        "tests": {f"t::test_{system}_{number}_{index}": 1.0 + index for index in range(tests)},
        "groups": {f"t_{number}": {"seconds": 2.0 * number if system.startswith("u") else 4.0 * number, "tests": tests}},
    }
    (folder / "durations.json").write_text(json.dumps(recorded), encoding="utf-8")


def full_run(results, **options):
    for system in ("ubuntu-latest", "windows-latest"):
        for number in (1, 2):
            write_shard(results, system, number, **options)


def run(results, tmp_path, *extra):
    merged = tmp_path / "merged.json"
    code = ci_summary.main(
        [str(results), "--shards", "2", "--systems", "ubuntu-latest,windows-latest", "--merged-durations", str(merged), *extra]
    )
    return code, merged


def test_every_shard_of_every_system_present_and_green_passes_and_reports_the_totals(tmp_path, capsys):
    results = tmp_path / "results"
    full_run(results)

    code, merged = run(results, tmp_path)

    out = capsys.readouterr().out
    assert code == 0
    assert "all shards passed" in out
    assert "| ubuntu-latest | 2/2 | 6 | 6 | 0 | 0 |" in out
    assert json.loads(merged.read_text(encoding="utf-8")) == {
        "t_1": {"seconds": 3.0, "tests": 3},  # the mean of 2 s on one system and 4 s on the other
        "t_2": {"seconds": 6.0, "tests": 3},
    }
    assert "`t::test_windows-latest_1_2`" in out  # the slowest tests are listed


def test_a_shard_that_left_no_files_fails_the_run(tmp_path, capsys):
    results = tmp_path / "results"
    full_run(results)
    for leftover in (results / "results-windows-latest-2").iterdir():
        leftover.unlink()

    code, _ = run(results, tmp_path)

    assert code == 1
    assert "windows-latest shard 2/2: no result files" in capsys.readouterr().out


def test_a_failed_test_fails_the_run(tmp_path, capsys):
    results = tmp_path / "results"
    full_run(results)
    (results / "results-ubuntu-latest-1").rename(tmp_path / "gone")
    write_shard(results, "ubuntu-latest", 1, failures=1)

    code, _ = run(results, tmp_path)

    assert code == 1
    assert "ubuntu-latest shard 1: 1 test(s) failed or errored" in capsys.readouterr().out


def test_a_shard_that_ran_other_tests_than_it_was_given_fails_the_run(tmp_path, capsys):
    results = tmp_path / "results"
    full_run(results)
    (results / "results-ubuntu-latest-2").rename(tmp_path / "gone")
    write_shard(results, "ubuntu-latest", 2, tests=2, selected=3)

    code, _ = run(results, tmp_path)

    assert code == 1
    assert "ran 2 tests but was given 3" in capsys.readouterr().out


def test_shards_whose_tests_do_not_add_up_to_the_collected_ones_fail_the_run(tmp_path, capsys):
    results = tmp_path / "results"
    full_run(results, collected=7)

    code, _ = run(results, tmp_path)

    assert code == 1
    assert "in all but 7 were collected" in capsys.readouterr().out


def test_a_skip_for_lack_of_data_fails_the_run_and_another_skip_is_only_counted(tmp_path, capsys):
    results = tmp_path / "results"
    full_run(results, skips=(COE_SKIP,))

    code, _ = run(results, tmp_path)

    out = capsys.readouterr().out
    assert code == 0
    assert "| ubuntu-latest | 2/2 | 6 | 4 | 2 | 0 |" in out
    assert f"4 x {COE_SKIP}" in out

    other = tmp_path / "other"
    full_run(other, skips=(COE_SKIP, DATA_SKIP))

    code, _ = run(other, tmp_path)

    assert code == 1
    assert "skipped for lack of data" in capsys.readouterr().out


@pytest.mark.parametrize("result", ["failure", "cancelled"])
def test_a_workflow_that_did_not_end_in_success_fails_the_run(tmp_path, capsys, result):
    results = tmp_path / "results"
    full_run(results)

    code, _ = run(results, tmp_path, "--job-result", result)

    assert code == 1
    assert f"ended as '{result}'" in capsys.readouterr().out


def test_a_run_that_collected_fewer_tests_than_the_floor_fails(tmp_path, capsys):
    results = tmp_path / "results"
    full_run(results)

    code, _ = run(results, tmp_path, "--min-tests", "7")

    assert code == 1
    assert "only 6 tests were collected, at least 7 are expected" in capsys.readouterr().out
