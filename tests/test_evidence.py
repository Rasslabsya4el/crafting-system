"""Known-answer checks for the fresh local evidence collector."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools import collect_evidence


def test_parse_junit_counts_testcases_once_not_nested_suite_totals(tmp_path: Path) -> None:
    xml = tmp_path / "pytest.xml"
    xml.write_text(
        """<testsuites tests="8" failures="2">
        <testsuite name="outer" tests="4"><testsuite name="inner" tests="4">
        <testcase name="ok_one" classname="tests.test_alpha" time="0.6" />
        <testcase name="ok_two" classname="tests.test_alpha" file="tests/test_alpha.py" time="1.2" />
        <testcase name="bad" classname="tests.test_beta" time="0.3"><failure message="expected 4">trace</failure></testcase>
        <testcase name="later" classname="tests.test_beta" time="0"><skipped message="not installed" /></testcase>
        </testsuite></testsuite></testsuites>""",
        encoding="utf-8",
    )

    report = collect_evidence.parse_junit(xml)

    assert (report["tests"], report["passed"], report["failures"], report["errors"], report["skipped"]) == (4, 2, 1, 0, 1)
    assert report["cases"][0] == {
        "name": "ok_one",
        "classname": "tests.test_alpha",
        "file": "tests.test_alpha",
        "status": "passed",
        "duration_minutes": pytest.approx(0.01),
        "message": None,
    }
    assert report["cases"][2]["message"] == "expected 4"
    assert report["cases"][3]["status"] == "skipped"


def test_parse_junit_records_error_case_separately(tmp_path: Path) -> None:
    xml = tmp_path / "pytest.xml"
    xml.write_text(
        '<testsuite><testcase name="boom" classname="tests.test_error" time="60"><error message="setup failed">detail</error></testcase></testsuite>',
        encoding="utf-8",
    )

    report = collect_evidence.parse_junit(xml)

    assert (report["tests"], report["passed"], report["failures"], report["errors"], report["skipped"]) == (1, 0, 0, 1, 0)
    assert report["cases"][0]["status"] == "error"
    assert report["cases"][0]["message"] == "setup failed"
    assert report["cases"][0]["duration_minutes"] == pytest.approx(1)


def test_parse_coe_comparison_derives_maximum_absolute_difference(tmp_path: Path) -> None:
    path = tmp_path / "comparison.json"
    path.write_text(
        json.dumps({"source_hashes": {"package": "abc"}, "cases": [
            {"id": "one", "relative_difference": -0.02},
            {"id": "two", "relative_difference": 0.03},
        ]}),
        encoding="utf-8",
    )

    report = collect_evidence.parse_coe_comparison(path)

    assert report["case_count"] == 2
    assert report["max_abs_relative_difference"] == pytest.approx(0.03)
    assert report["source_hashes"] == {"package": "abc"}
    assert report["cases"][0]["relative_difference"] == -0.02


def test_execute_command_records_timeout_and_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(["python", "-m", "pytest"], 120, output=b"partial", stderr=b"late")

    monkeypatch.setattr(collect_evidence.subprocess, "run", timeout)

    record = collect_evidence.execute_command(
        "pytest", ["python", "-m", "pytest"], cwd=tmp_path, timeout_seconds=120, output_dir=tmp_path,
    )

    assert record["exit_code"] is None
    assert record["timed_out"] is True
    assert (tmp_path / "pytest.stdout.log").read_text(encoding="utf-8") == "partial"
    assert "late" in (tmp_path / "pytest.stderr.log").read_text(encoding="utf-8")
    assert "timed out after 2 minutes" in (tmp_path / "pytest.stderr.log").read_text(encoding="utf-8")


def test_collect_marks_missing_pytest_artifact_unavailable_after_failed_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    output = root / "out" / "evidence"

    def failed_command(name: str, argv: list[str], **kwargs: object) -> dict[str, object]:
        output_dir = kwargs["output_dir"]
        assert isinstance(output_dir, Path)
        (output_dir / f"{name}.stdout.log").write_text("failed", encoding="utf-8")
        (output_dir / f"{name}.stderr.log").write_text("failure", encoding="utf-8")
        return collect_evidence.command_record(name, argv, exit_code=1, duration_seconds=1, output_dir=output_dir)

    monkeypatch.setattr(collect_evidence, "execute_command", failed_command)
    monkeypatch.setattr(collect_evidence, "git_metadata", lambda _: ("commit", False))

    proof = collect_evidence.collect_evidence(output, root=root)

    assert proof["pytest"]["status"] == "unavailable"
    assert "missing" in proof["pytest"]["reason"]
    assert proof["coe"]["status"] == "unavailable"
    assert proof["commands"][0]["exit_code"] == 1


def test_collect_replaces_stale_artifacts_and_keeps_timeout_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    output = root / "out" / "evidence"
    coe = output / "coe"
    coe.mkdir(parents=True)
    (output / "pytest.xml").write_text('<testsuite><testcase name="stale" /></testsuite>', encoding="utf-8")
    (coe / "comparison.json").write_text(json.dumps({"cases": [{"relative_difference": 0.01}]}), encoding="utf-8")

    def timed_out(name: str, argv: list[str], **kwargs: object) -> dict[str, object]:
        output_dir = kwargs["output_dir"]
        assert isinstance(output_dir, Path)
        (output_dir / f"{name}.stdout.log").write_text("", encoding="utf-8")
        (output_dir / f"{name}.stderr.log").write_text("timed out", encoding="utf-8")
        return collect_evidence.command_record(
            name, argv, exit_code=None, duration_seconds=120, output_dir=output_dir, timed_out=True,
        )

    monkeypatch.setattr(collect_evidence, "execute_command", timed_out)
    monkeypatch.setattr(collect_evidence, "git_metadata", lambda _: ("commit", False))

    proof = collect_evidence.collect_evidence(output, root=root)

    assert proof["pytest"]["status"] == "failed"
    assert "timed out" in proof["pytest"]["reason"]
    assert proof["pytest"]["tests"] == 0
    assert proof["coe"]["status"] == "failed"
    assert proof["coe"]["case_count"] == 0
    assert collect_evidence.exit_code_for(proof) == 1


def test_collect_marks_invalid_fresh_coe_json_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    output = root / "out" / "evidence"

    def invalid_coe(name: str, argv: list[str], **kwargs: object) -> dict[str, object]:
        output_dir = kwargs["output_dir"]
        assert isinstance(output_dir, Path)
        (output_dir / f"{name}.stdout.log").write_text("", encoding="utf-8")
        (output_dir / f"{name}.stderr.log").write_text("", encoding="utf-8")
        if name == "pytest":
            (output_dir / "pytest.xml").write_text('<testsuite><testcase name="ok" /></testsuite>', encoding="utf-8")
        else:
            coe_dir = output_dir / "coe"
            coe_dir.mkdir(exist_ok=True)
            (coe_dir / "comparison.json").write_text("not JSON", encoding="utf-8")
        return collect_evidence.command_record(name, argv, exit_code=0, duration_seconds=1, output_dir=output_dir)

    monkeypatch.setattr(collect_evidence, "execute_command", invalid_coe)
    monkeypatch.setattr(collect_evidence, "git_metadata", lambda _: ("commit", False))

    proof = collect_evidence.collect_evidence(output, root=root)

    assert proof["pytest"]["status"] == "passed"
    assert proof["coe"]["status"] == "unavailable"
    assert "unparseable" in proof["coe"]["reason"]


def test_collect_runs_literal_commands_writes_logs_and_preserves_failed_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    output = root / "out" / "evidence"
    commands: list[tuple[str, list[str]]] = []

    def fake_command(name: str, argv: list[str], **kwargs: object) -> dict[str, object]:
        commands.append((name, argv))
        output_dir = kwargs["output_dir"]
        assert isinstance(output_dir, Path)
        (output_dir / f"{name}.stdout.log").write_text(f"{name} output", encoding="utf-8")
        (output_dir / f"{name}.stderr.log").write_text(f"{name} error", encoding="utf-8")
        if name == "pytest":
            (output_dir / "pytest.xml").write_text(
                '<testsuite><testcase name="broken" classname="tests.test_x"><failure message="nope" /></testcase></testsuite>',
                encoding="utf-8",
            )
            return collect_evidence.command_record(name, argv, exit_code=1, duration_seconds=3, output_dir=output_dir)
        coe_dir = output_dir / "coe"
        coe_dir.mkdir(exist_ok=True)
        (coe_dir / "comparison.json").write_text(
            json.dumps({"source_hashes": {"data": "def"}, "cases": [{"id": "C1", "relative_difference": -0.02}]}),
            encoding="utf-8",
        )
        return collect_evidence.command_record(name, argv, exit_code=0, duration_seconds=6, output_dir=output_dir)

    monkeypatch.setattr(collect_evidence, "execute_command", fake_command)
    monkeypatch.setattr(collect_evidence, "git_metadata", lambda _: ("commit", True))

    proof = collect_evidence.collect_evidence(output, root=root)

    assert commands[0][0] == "pytest"
    assert commands[0][1][1:5] == ["-m", "pytest", "-q", "--basetemp=.pytest_tmp"]
    assert commands[1][0] == "coe"
    assert commands[1][1][1:3] == ["-m", "tools.coe_validation"]
    assert proof["pytest"]["status"] == "failed"
    assert proof["pytest"]["failures"] == 1
    assert proof["coe"] == {
        "status": "passed",
        "case_count": 1,
        "cases": [{"id": "C1", "relative_difference": -0.02}],
        "max_abs_relative_difference": pytest.approx(0.02),
        "source_hashes": {"data": "def"},
    }
    assert proof["working_tree_dirty"] is True
    assert (output / "pytest.stdout.log").read_text(encoding="utf-8") == "pytest output"
    assert (output / "proof.json").exists()
    assert collect_evidence.exit_code_for(proof) == 1


def test_output_directory_must_stay_within_worktree(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(ValueError, match="within repository"):
        collect_evidence.collect_evidence(tmp_path / "outside", root=root)
