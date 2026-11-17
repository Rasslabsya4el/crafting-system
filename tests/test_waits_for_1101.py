"""The lists of tests that wait for #1101 (`conftest.WAITS_FOR_1101`, `conftest.RERECORD_FOR_1101`, #886) match tests that exist.

A pattern of `WAITS_FOR_1101` is an xfail that is not run, so nothing else would notice one that names a test renamed or moved away. The
files the patterns name are collected (`pytest --collect-only`, in a process of its own: collection runs no test and plans nothing), and each
pattern must match at least one collected node id, exactly as `conftest._mark_waits_for_1101` matches them.
"""

import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

import pytest
from conftest import RERECORD_FOR_1101, WAITS_FOR_1101

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (*WAITS_FOR_1101, *RERECORD_FOR_1101)


@pytest.fixture(scope="module")
def collected() -> list[str]:
    files = sorted({pattern.partition("::")[0] for pattern in PATTERNS})
    for file in files:
        assert (ROOT / file).is_file(), file
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *files],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    return [line.strip() for line in result.stdout.splitlines() if "::" in line]


@pytest.mark.parametrize("pattern", PATTERNS)
def test_each_pattern_matches_a_collected_test(pattern, collected):
    assert any(fnmatchcase(node, pattern) for node in collected), pattern
