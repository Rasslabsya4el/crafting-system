"""The launcher of one CI shard (ticket #165): its slots run side by side, nothing is dropped or run twice, and what it
writes is what the summary check reads."""

import importlib.util
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / ".github" / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_shard = load_script("run_shard")
ci_summary = load_script("ci_summary")

ROUTE_MODULE = '''
import pytest

@pytest.fixture(scope="module", params=["R10", "R11", "R05"])
def solved(request):
    return request.param

def test_one(solved):
    pass

def test_two(solved):
    pass
'''
PLAIN_MODULE = "def test_a():\n    pass\n\ndef test_b():\n    pass\n\ndef test_c():\n    pass\n"
TOTAL = 3 * 2 + 3


def test_a_shard_runs_its_own_slots_in_order_and_no_other():
    assert run_shard.slot_numbers(1, 8, 4) == [1, 2, 3, 4]
    assert run_shard.slot_numbers(3, 8, 4) == [9, 10, 11, 12]
    assert run_shard.slot_numbers(8, 8, 4) == [29, 30, 31, 32]
    with pytest.raises(ValueError, match="shard 9"):
        run_shard.slot_numbers(9, 8, 4)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(TESTS / "conftest.py", root / "conftest.py")
    shutil.copy(TESTS / "shard_support.py", root / "shard_support.py")
    (root / "test_route.py").write_text(ROUTE_MODULE, encoding="utf-8")
    (root / "test_plain.py").write_text(PLAIN_MODULE, encoding="utf-8")
    return root


def launch(root, shard, out, *pytest_args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "run_shard.py"), "--shard", shard, "--procs", "2", "--out", out,
         "--", "-p", "no:cacheprovider", "-q", "--rootdir", str(root), *pytest_args],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False, timeout=240,
    )  # fmt: skip


def test_two_shards_of_two_slots_run_every_test_once_and_the_summary_accepts_them(project, tmp_path, capsys):
    results = tmp_path / "results"
    for shard in (1, 2):
        done = launch(project, f"{shard}/2", str(results / f"results-linux-{shard}"))
        assert done.returncode == 0, done.stdout + done.stderr

    ran = []
    for shard in (1, 2):
        suite = ET.parse(results / f"results-linux-{shard}" / "junit.xml").getroot()[0]
        ran += [f"{case.get('classname')}::{case.get('name')}" for case in suite.findall("testcase")]
        report = json.loads((results / f"results-linux-{shard}" / "shard.json").read_text(encoding="utf-8"))
        assert report["collected"] == TOTAL
        assert report["selected"] == int(suite.get("tests"))
    assert len(ran) == len(set(ran)) == TOTAL

    code = ci_summary.main([str(results), "--shards", "2", "--systems", "linux"])
    assert code == 0
    assert f"| linux | 2/2 | {TOTAL} | {TOTAL} | 0 | 0 |" in capsys.readouterr().out


def test_a_failing_test_in_any_slot_fails_the_shard_and_the_summary(project, tmp_path, capsys):
    (project / "test_plain.py").write_text(PLAIN_MODULE + "\ndef test_broken():\n    assert False\n", encoding="utf-8")
    results = tmp_path / "results"
    codes = [launch(project, f"{shard}/2", str(results / f"results-linux-{shard}")).returncode for shard in (1, 2)]

    assert sorted(codes) == [0, 1] or codes == [1, 1]
    assert ci_summary.main([str(results), "--shards", "2", "--systems", "linux"]) == 1
    assert "failed or errored" in capsys.readouterr().out


def test_more_slots_than_groups_leave_a_slot_empty_without_failing_the_shard(project, tmp_path):
    done = launch(project, "1/1", str(tmp_path / "out"))
    one_group = project / "only"
    one_group.mkdir()
    shutil.copy(project / "conftest.py", one_group / "conftest.py")
    shutil.copy(project / "shard_support.py", one_group / "shard_support.py")
    (one_group / "test_plain.py").write_text(PLAIN_MODULE, encoding="utf-8")
    alone = launch(one_group, "1/1", str(tmp_path / "alone"))

    assert done.returncode == 0, done.stdout + done.stderr
    assert alone.returncode == 0, alone.stdout + alone.stderr
    report = json.loads((tmp_path / "alone" / "shard.json").read_text(encoding="utf-8"))
    assert (report["collected"], report["selected"]) == (3, 3)
