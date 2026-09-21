"""Offline checks for the frozen Craft of Exile probability kernel."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.coe_validation import CASES


ROOT = Path(__file__).parents[1]
RUNNER = ROOT / "tools" / "coe_offline.cjs"
PACKAGE = ROOT / "sources" / "raw" / "coe" / "package.js"


def _kernel(payload: dict) -> dict:
    if not PACKAGE.exists():
        pytest.skip("frozen CoE package cache is absent")
    completed = subprocess.run(
        ["node", str(RUNNER)],
        cwd=ROOT,
        input=json.dumps({"command": "kernel", **payload}),
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def _pool() -> list[dict]:
    return [
        {"aid": "A", "weight": 1, "modgroups": ["A"]},
        {"aid": "B", "weight": 1, "modgroups": ["B"]},
        {"aid": "C", "weight": 2, "modgroups": ["C"]},
    ]


def test_cached_kernel_reproduces_synthetic_two_draw_values() -> None:
    single_required = _kernel(
        {"pool": _pool(), "requirements": [["A"]], "draws": 2}
    )
    both_required = _kernel(
        {"pool": _pool(), "requirements": [["A"], ["C"]], "draws": 2}
    )
    assert single_required["probability"] == pytest.approx(7 / 12)
    assert both_required["probability"] == pytest.approx(5 / 12)


def test_cached_kernel_reproduces_synthetic_single_draw_value() -> None:
    result = _kernel({"pool": _pool(), "requirements": [["A"]], "draws": 1})
    assert result["probability"] == pytest.approx(1 / 4)


def test_runner_rejects_missing_source_and_invalid_kernel_input(tmp_path: Path) -> None:
    missing = subprocess.run(
        ["node", str(RUNNER), "--package", str(tmp_path / "missing.js")],
        cwd=ROOT,
        input=json.dumps({"command": "kernel", "pool": _pool(), "requirements": [["A"]], "draws": 1}),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert missing.returncode != 0
    assert "missing CoE package source" in missing.stderr

    if not PACKAGE.exists():
        pytest.skip("frozen CoE package cache is absent")
    invalid = subprocess.run(
        ["node", str(RUNNER)],
        cwd=ROOT,
        input=json.dumps({"command": "kernel", "pool": _pool(), "requirements": [], "draws": 1}),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert invalid.returncode != 0
    assert "requirements" in invalid.stderr


def test_case_manifest_is_the_twelve_assigned_inputs() -> None:
    assert [(case.id, case.base, case.action) for case in CASES] == [
        ("C01", "Royal Burgonet", "chaos"),
        ("C02", "Royal Burgonet", "essence"),
        ("C03", "Royal Burgonet", "exalted"),
        ("C04", "Simple Robe", "alchemy"),
        ("C05", "Simple Robe", "alteration"),
        ("C06", "Iron Ring", "chaos"),
        ("C07", "Iron Ring", "alchemy"),
        ("C08", "Iron Ring", "regal"),
        ("C09", "Paua Amulet", "chaos"),
        ("C10", "Paua Amulet", "alteration"),
        ("C11", "Iron Greaves", "alchemy"),
        ("C12", "Iron Greaves", "regal"),
    ]
