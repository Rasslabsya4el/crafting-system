"""Collect fresh local pytest and offline CoE evidence into one JSON document."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import subprocess
import sys
import time
import xml.etree.ElementTree as element_tree
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
PYTEST_TIMEOUT_SECONDS = 2 * 60
COE_TIMEOUT_SECONDS = 3 * 60


def _relative(path: Path, output_dir: Path) -> str:
    return path.relative_to(output_dir).as_posix()


def _resolve_output_dir(output_dir: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved_output = output_dir.resolve()
    try:
        resolved_output.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError("evidence output directory must be within repository") from error
    return resolved_output


def command_record(
    name: str,
    argv: list[str],
    *,
    exit_code: int | None,
    duration_seconds: float,
    output_dir: Path,
    timed_out: bool = False,
) -> dict[str, Any]:
    """Build one schema command entry after its stdout and stderr logs are written."""
    record: dict[str, Any] = {
        "name": name,
        "argv": argv,
        "exit_code": exit_code,
        "duration_minutes": duration_seconds / 60,
        "stdout_file": _relative(output_dir / f"{name}.stdout.log", output_dir),
        "stderr_file": _relative(output_dir / f"{name}.stderr.log", output_dir),
    }
    if timed_out:
        record["timed_out"] = True
    return record


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _junit_file(case: element_tree.Element) -> str:
    explicit_file = case.get("file")
    if explicit_file:
        return explicit_file
    classname = case.get("classname", "")
    parts = classname.split(".")
    for index, part in enumerate(parts):
        if part.startswith("test_"):
            return "/".join(parts[:index + 1]) + ".py"
    return classname.replace(".", "/") + ".py" if classname else ""


def execute_command(
    name: str,
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    output_dir: Path,
) -> dict[str, Any]:
    """Run exactly one local check and retain its logs, including timeout output."""
    started = time.monotonic()
    timed_out = False
    exit_code: int | None
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        exit_code = None
        stdout = _as_text(error.stdout)
        stderr = _as_text(error.stderr)
        if stderr:
            stderr += "\n"
        stderr += f"timed out after {timeout_seconds / 60:g} minutes"
    except OSError as error:
        exit_code = None
        stderr = f"process startup failed: {error}"
    duration_seconds = time.monotonic() - started
    (output_dir / f"{name}.stdout.log").write_text(stdout, encoding="utf-8")
    (output_dir / f"{name}.stderr.log").write_text(stderr, encoding="utf-8")
    return command_record(
        name,
        argv,
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        output_dir=output_dir,
        timed_out=timed_out,
    )


def _case_message(case: element_tree.Element, status: str) -> str | None:
    if status == "passed":
        return None
    child = next((entry for entry in case if entry.tag == status), None)
    if child is None:
        return None
    return child.get("message") or (child.text.strip() if child.text else None)


def parse_junit(path: Path) -> dict[str, Any]:
    """Parse testcase nodes directly so nested testsuite summaries cannot double-count."""
    root = element_tree.parse(path).getroot()
    cases: list[dict[str, Any]] = []
    for case in root.iter("testcase"):
        if case.find("error") is not None:
            status = "error"
        elif case.find("failure") is not None:
            status = "failure"
        elif case.find("skipped") is not None:
            status = "skipped"
        else:
            status = "passed"
        try:
            duration_seconds = float(case.get("time", "0"))
        except ValueError as error:
            raise ValueError(f"testcase {case.get('name', '<unnamed>')} has invalid time") from error
        if not math.isfinite(duration_seconds) or duration_seconds < 0:
            raise ValueError(f"testcase {case.get('name', '<unnamed>')} has non-finite or negative time")
        cases.append({
            "name": case.get("name", ""),
            "classname": case.get("classname", ""),
            "file": _junit_file(case),
            "status": status,
            "duration_minutes": duration_seconds / 60,
            "message": _case_message(case, status),
        })
    if not cases:
        raise ValueError("JUnit XML contains no testcase elements")
    failures = sum(case["status"] == "failure" for case in cases)
    errors = sum(case["status"] == "error" for case in cases)
    skipped = sum(case["status"] == "skipped" for case in cases)
    return {
        "tests": len(cases),
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "passed": len(cases) - failures - errors - skipped,
        "duration_minutes": sum(case["duration_minutes"] for case in cases),
        "cases": cases,
    }


def parse_coe_comparison(path: Path) -> dict[str, Any]:
    """Read the fresh CoE comparison artifact and derive its displayed maximum."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("cases"), list):
        raise ValueError("comparison JSON must contain a cases list")
    cases = document["cases"]
    differences: list[float] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"comparison case {index} is not an object")
        try:
            difference = float(case["relative_difference"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"comparison case {index} has invalid relative_difference") from error
        if not math.isfinite(difference):
            raise ValueError(f"comparison case {index} has non-finite relative_difference")
        differences.append(abs(difference))
    if not cases:
        raise ValueError("comparison JSON contains no cases")
    source_hashes = document.get("source_hashes", {})
    if not isinstance(source_hashes, dict):
        raise ValueError("comparison source_hashes must be an object")
    return {
        "case_count": len(cases),
        "cases": cases,
        "max_abs_relative_difference": max(differences, default=0.0),
        "source_hashes": source_hashes,
    }


def git_metadata(root: Path) -> tuple[str, bool]:
    """Read local revision metadata; evidence is still useful when git metadata is absent."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True, timeout=15,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, check=True, timeout=15,
        ).stdout.strip())
        return commit, dirty
    except (OSError, subprocess.SubprocessError):
        return "unavailable", True


def _clear_stale_artifacts(output_dir: Path) -> None:
    """A failed check must never be represented by a previous run's XML or comparison."""
    for path in (
        output_dir / "pytest.xml",
        output_dir / "pytest.stdout.log",
        output_dir / "pytest.stderr.log",
        output_dir / "coe" / "comparison.json",
        output_dir / "coe" / "comparison.tsv",
        output_dir / "coe.stdout.log",
        output_dir / "coe.stderr.log",
    ):
        path.unlink(missing_ok=True)


def _pytest_report(command: dict[str, Any], xml_path: Path) -> dict[str, Any]:
    if command.get("timed_out"):
        return _empty_pytest("failed", "pytest command timed out; no prior XML was reused")
    if not xml_path.exists():
        return _empty_pytest("unavailable", "pytest XML is missing after the command")
    try:
        report = parse_junit(xml_path)
    except (OSError, ValueError, element_tree.ParseError, json.JSONDecodeError) as error:
        return _empty_pytest("unavailable", f"pytest XML is unparseable: {error}")
    report["status"] = "passed" if command.get("exit_code") == 0 and not report["failures"] and not report["errors"] else "failed"
    if report["status"] == "failed":
        report["reason"] = "pytest command failed or reported failing test cases"
    return report


def _empty_pytest(status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "tests": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "passed": 0,
        "duration_minutes": 0.0,
        "cases": [],
        "reason": reason,
    }


def _coe_report(command: dict[str, Any], comparison_path: Path) -> dict[str, Any]:
    if command.get("timed_out"):
        return _empty_coe("failed", "CoE command timed out; no prior comparison was reused")
    if not comparison_path.exists():
        return _empty_coe("unavailable", "CoE comparison JSON is missing after the command")
    try:
        report = parse_coe_comparison(comparison_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _empty_coe("unavailable", f"CoE comparison JSON is unparseable: {error}")
    report["status"] = "passed" if command.get("exit_code") == 0 else "failed"
    if report["status"] == "failed":
        report["reason"] = "CoE command failed after writing comparison evidence"
    return report


def _empty_coe(status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "case_count": 0,
        "cases": [],
        "max_abs_relative_difference": None,
        "source_hashes": {},
        "reason": reason,
    }


def collect_evidence(output_dir: Path, *, root: Path = ROOT) -> dict[str, Any]:
    """Run the two requested local checks sequentially and always write proof.json."""
    root = root.resolve()
    output_dir = _resolve_output_dir(output_dir, root)
    output_dir.mkdir(parents=True, exist_ok=True)
    coe_dir = output_dir / "coe"
    coe_dir.mkdir(exist_ok=True)
    _clear_stale_artifacts(output_dir)

    pytest_xml = output_dir / "pytest.xml"
    pytest_command = execute_command(
        "pytest",
        [sys.executable, "-m", "pytest", "-q", "--basetemp=.pytest_tmp", f"--junitxml={pytest_xml}"],
        cwd=root,
        timeout_seconds=PYTEST_TIMEOUT_SECONDS,
        output_dir=output_dir,
    )
    pytest_report = _pytest_report(pytest_command, pytest_xml)

    coe_command = execute_command(
        "coe",
        [sys.executable, "-m", "tools.coe_validation", "--output-dir", str(coe_dir)],
        cwd=root,
        timeout_seconds=COE_TIMEOUT_SECONDS,
        output_dir=output_dir,
    )
    coe_report = _coe_report(coe_command, coe_dir / "comparison.json")
    commit, dirty = git_metadata(root)
    proof = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_commit": commit,
        "working_tree_dirty": dirty,
        "commands": [pytest_command, coe_command],
        "pytest": pytest_report,
        "coe": coe_report,
        "artifacts": {
            "pytest_xml": _relative(pytest_xml, output_dir),
            "pytest_log": "pytest.stdout.log",
            "coe_json": "coe/comparison.json",
        },
    }
    (output_dir / "proof.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return proof


def exit_code_for(proof: dict[str, Any]) -> int:
    return 0 if proof["pytest"]["status"] == "passed" and proof["coe"]["status"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "out" / "evidence")
    args = parser.parse_args(argv)
    return exit_code_for(collect_evidence(args.output_dir))


if __name__ == "__main__":
    sys.exit(main())
