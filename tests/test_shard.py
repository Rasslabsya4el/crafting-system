"""The split of the suite over CI jobs (ticket #165): the plan is a partition, it is the same on every shard,
a parametrized module-scoped fixture keeps its tests together, and the stored seconds balance the shards."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import shard_support

TESTS = Path(__file__).resolve().parent


def test_parse_shard_reads_i_over_n_from_one():
    assert shard_support.parse_shard("3/8") == (3, 8)
    assert shard_support.parse_shard(" 1/1 ") == (1, 1)


@pytest.mark.parametrize("text", ["0/4", "5/4", "3", "a/b", "1/", "-1/4", "1/2/3"])
def test_parse_shard_refuses_what_is_not_a_shard_of_the_run(text):
    with pytest.raises(ValueError, match="--shard"):
        shard_support.parse_shard(text)


def test_a_group_is_the_module_and_the_index_of_each_wide_fixture_value():
    assert shard_support.group_name("tests/test_a.py::test_x", {}) == "tests/test_a.py"
    assert shard_support.group_name("tests/test_a.py::test_x[R05]", {"solved": 2}) == "tests/test_a.py[solved#2]"
    assert (
        shard_support.group_name("tests/test_a.py::test_x[1-2]", {"b": 1, "a": 0}) == "tests/test_a.py[a#0,b#1]"
    )


def test_a_group_costs_its_stored_time_plus_the_median_test_for_each_test_it_gained():
    members = {"g": ["a", "b", "c", "d"], "h": ["e"], "new": ["f", "g"]}
    stored = {"g": (10.0, 3), "h": (100.0, 1), "old": (5.0, 1)}  # per test: 3.33, 100, 5; the median is 5

    seconds = shard_support.group_seconds(members, stored)

    assert seconds == {"g": 10.0 + 1 * 5.0, "h": 100.0, "new": 2 * 5.0}


def test_without_any_stored_time_every_test_costs_the_same():
    seconds = shard_support.group_seconds({"g": ["a", "b"], "h": ["c"]}, {})

    assert seconds == {"g": 2 * shard_support.UNKNOWN_SECONDS, "h": shard_support.UNKNOWN_SECONDS}


def test_the_stored_file_is_read_by_group_and_a_missing_name_is_no_file(tmp_path):
    path = tmp_path / "d.json"
    path.write_text(json.dumps({"tests/a.py": {"seconds": 1.5, "tests": 4}}), encoding="utf-8")

    assert shard_support.read_durations(path) == {"tests/a.py": (1.5, 4)}
    assert shard_support.read_durations(None) == {}


def test_the_recording_sums_the_seconds_of_each_group_and_names_every_test():
    spent = {"a.py::t1": 1.0, "a.py::t2[x]": 2.0, "b.py::t3[R05]": 4.0}
    groups = {"a.py::t1": "a.py", "a.py::t2[x]": "a.py", "b.py::t3[R05]": "b.py[solved#2]"}

    recorded = shard_support.recording(spent, groups)

    assert recorded["groups"] == {"a.py": {"seconds": 3.0, "tests": 2}, "b.py[solved#2]": {"seconds": 4.0, "tests": 1}}
    assert recorded["tests"] == spent


def test_the_longest_groups_go_first_each_to_the_shard_with_the_least_time():
    seconds = {"a": 10.0, "b": 9.0, "c": 5.0, "d": 4.0, "e": 3.0, "f": 3.0}

    plan = shard_support.assign(seconds, 3)

    assert plan == {"a": 1, "b": 2, "c": 3, "d": 3, "e": 2, "f": 3}
    loads = [sum(seconds[name] for name, shard in plan.items() if shard == number) for number in (1, 2, 3)]
    assert max(loads) - min(loads) <= max(seconds.values())


def test_the_plan_does_not_depend_on_the_order_the_groups_come_in():
    seconds = {f"g{number}": float(number % 5) for number in range(40)}
    shuffled = dict(reversed(list(seconds.items())))

    assert shard_support.assign(seconds, 7) == shard_support.assign(shuffled, 7)


def test_more_shards_than_groups_leave_some_shards_empty_and_every_group_placed():
    plan = shard_support.assign({"a": 1.0, "b": 1.0}, 5)

    assert sorted(plan) == ["a", "b"]
    assert sorted(plan.values()) == [1, 2]


# --- the pytest wiring, on a small project of its own -------------------------------------------------------


MODULE_WITH_A_ROUTE = '''
import pytest

@pytest.fixture(scope="module", params=["R10", "R11", "R05"])
def solved(request):
    return request.param

def test_one(solved):
    pass

def test_two(solved):
    pass

def test_three():
    pass

@pytest.mark.parametrize("who", ["a@b"])
def test_at(who):
    pass
'''
PLAIN_MODULE = "def test_a():\n    pass\n\ndef test_b():\n    pass\n"


@pytest.fixture
def project(tmp_path):
    """A copy of the shared conftest with two test modules, so the options run against nothing else."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(TESTS / "conftest.py", root / "conftest.py")
    shutil.copy(TESTS / "shard_support.py", root / "shard_support.py")
    (root / "test_route.py").write_text(MODULE_WITH_A_ROUTE, encoding="utf-8")
    (root / "test_plain.py").write_text(PLAIN_MODULE, encoding="utf-8")
    return root


def run_pytest(root, *args):
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "--rootdir", str(root), *args],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False, timeout=120,
    )  # fmt: skip
    return done


def selected(root, index, count, *extra):
    done = run_pytest(root, "--collect-only", "--shard", f"{index}/{count}", *extra)
    assert done.returncode == 0, done.stdout + done.stderr
    return {line for line in done.stdout.splitlines() if "::" in line}


def test_the_shards_together_hold_every_test_exactly_once(project):
    everything = {
        line for line in run_pytest(project, "--collect-only").stdout.splitlines() if "::" in line
    }
    parts = [selected(project, index, 3) for index in (1, 2, 3)]

    assert len(everything) == 3 * 2 + 1 + 1 + 2
    assert set().union(*parts) == everything
    assert sum(len(part) for part in parts) == len(everything)


def test_the_tests_of_one_value_of_a_module_scoped_fixture_stay_on_one_shard(project):
    parts = [selected(project, index, 3) for index in (1, 2, 3)]

    for value in ("R10", "R11", "R05"):
        homes = {number for number, part in enumerate(parts) if any(f"[{value}]" in line for line in part)}
        assert len(homes) == 1
        (home,) = homes
        assert {line for line in parts[home] if f"[{value}]" in line} == {
            f"test_route.py::test_one[{value}]", f"test_route.py::test_two[{value}]",
        }  # fmt: skip


def test_the_stored_seconds_put_the_slow_group_alone_on_a_shard(project):
    durations = project / "durations.json"
    seconds = {"test_plain.py": {"seconds": 1000.0, "tests": 2}, "test_route.py": {"seconds": 1.0, "tests": 2}}
    seconds |= {f"test_route.py[solved#{index}]": {"seconds": 1.0, "tests": 2} for index in range(3)}
    durations.write_text(json.dumps(seconds), encoding="utf-8")

    first = selected(project, 1, 2, "--shard-durations", str(durations))
    second = selected(project, 2, 2, "--shard-durations", str(durations))

    assert first == {"test_plain.py::test_a", "test_plain.py::test_b"}
    assert len(second) == 8


def test_a_run_with_the_shard_and_the_record_writes_the_report_and_the_seconds_of_what_ran(project):
    done = run_pytest(
        project, "--shard", "1/2", "--shard-report", "report.json", "--record-durations", "seen.json",
    )  # fmt: skip

    assert done.returncode == 0, done.stdout + done.stderr
    report = json.loads((project / "report.json").read_text(encoding="utf-8"))
    seen = json.loads((project / "seen.json").read_text(encoding="utf-8"))
    assert (report["slot"], report["slots"], report["collected"]) == (1, 2, 10)
    assert report["selected"] == len(seen["tests"]) > 0
    assert all(seconds >= 0 for seconds in seen["tests"].values())
    assert sum(entry["tests"] for entry in seen["groups"].values()) == report["selected"]


def test_a_bad_shard_is_a_usage_error_and_without_the_option_nothing_is_dropped(project):
    bad = run_pytest(project, "--collect-only", "--shard", "9/2")
    plain = run_pytest(project, "--collect-only")

    assert bad.returncode != 0
    assert "--shard" in bad.stdout + bad.stderr
    assert "10 tests collected" in plain.stdout
