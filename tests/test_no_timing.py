"""No test asserts on timing (ADR-0014): speed is recorded by a separate benchmark command.

Parses every file under `tests/` and fails on an import of `time` or `timeit`, a `benchmark`
fixture, or a `pytest.mark.timeout` mark. Names are assembled from pieces where needed so this
file does not trip its own scan.
"""

import ast
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent

TIMING_MODULES = {"time", "timeit"}
BENCH_FIXTURE = "bench" + "mark"


def find_timing_use(source: str) -> list[str]:
    """One line per timing import, benchmark fixture or timeout mark in `source`."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in TIMING_MODULES:
                    found.append(f"line {node.lineno}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and (node.module or "").split(".")[0] in TIMING_MODULES:
                found.append(f"line {node.lineno}: imports from {node.module}")
        elif isinstance(node, ast.arg):
            if node.arg == BENCH_FIXTURE:
                found.append(f"line {node.lineno}: uses the {BENCH_FIXTURE} fixture")
        elif isinstance(node, ast.Constant):
            if node.value == BENCH_FIXTURE:
                found.append(f"line {node.lineno}: names the {BENCH_FIXTURE} fixture")
        elif isinstance(node, ast.Attribute) and node.attr == "timeout":
            owner = node.value
            if (isinstance(owner, ast.Attribute) and owner.attr == "mark") or (
                isinstance(owner, ast.Name) and owner.id == "mark"
            ):
                found.append(f"line {node.lineno}: uses the timeout mark")
    return found


@pytest.mark.parametrize(
    "source",
    [
        "import time",
        "import time as t",
        "import os, time",
        "import timeit",
        "import timeit as ti",
        "from time import sleep",
        "from time import perf_counter as pc",
        "from timeit import timeit",
        "def test_x():\n    import time\n",
        "def test_x(benchmark):\n    pass\n",
        "def test_x(tmp_path, benchmark, other):\n    pass\n",
        "def test_x(*, benchmark):\n    pass\n",
        "async def test_x(benchmark):\n    pass\n",
        "class TestX:\n    def test_x(self, benchmark):\n        pass\n",
        "import pytest\n@pytest.mark.usefixtures('benchmark')\ndef test_x():\n    pass\n",
        "def test_x(request):\n    request.getfixturevalue('benchmark')\n",
        "import pytest\n@pytest.mark.timeout(5)\ndef test_x():\n    pass\n",
        "import pytest\npytestmark = pytest.mark.timeout(5)\n",
        "from pytest import mark\n@mark.timeout(5)\ndef test_x():\n    pass\n",
    ],
)
def test_timing_use_is_reported(source):
    assert len(find_timing_use(source)) >= 1


@pytest.mark.parametrize(
    "source",
    [
        "import os\nimport datetime\nfrom pathlib import Path",
        "def test_x(tmp_path):\n    assert True\n",
        "from crafting_system import time_budget",
        "from . import time",
        "import pytest\n@pytest.mark.parametrize('a', [1])\ndef test_x(a):\n    pass\n",
        "timeout = 5\nbenchmark_name = 'x'\n",
        "import timezone_helpers",
        "",
    ],
)
def test_ordinary_test_code_is_not_reported(source):
    assert find_timing_use(source) == []


def test_real_tests_use_no_timing():
    problems = []
    for path in sorted(TESTS_DIR.rglob("*.py")):
        for problem in find_timing_use(path.read_text(encoding="utf-8")):
            problems.append(f"{path.relative_to(TESTS_DIR).as_posix()}: {problem}")

    assert problems == []


def test_the_scan_covers_the_real_test_files():
    names = {path.name for path in TESTS_DIR.rglob("*.py")}

    assert {"test_layering.py", "test_config.py", "test_no_timing.py"} <= names
