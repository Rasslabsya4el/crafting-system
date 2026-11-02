"""The coverage report of the measurement chain (ticket #399, step 3): pure functions and the three files it writes."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "measure_coverage_report.py"
spec = importlib.util.spec_from_file_location("measure_coverage_report", SCRIPT)
measure_coverage_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_coverage_report)

# Line numbers below are the lines of this source (line 1 is `def top():`).
SOURCE = '''\
def top():
    return 1


class Box:
    def method(self):
        x = 1
        return x

    def unused(self):
        """Only a docstring."""
        y = 2


def outer():
    def inner():
        return 3
    return inner()
'''


def test_functions_never_entered_lists_only_the_functions_no_line_of_which_ran():
    # top runs (2), method runs (7), outer runs (16 and 18), the docstring line 11 ran but is not a statement,
    # unused has its one statement (12) not run, and inner (17) is not run.
    executed = {2, 7, 8, 11, 16, 18}

    assert measure_coverage_report.functions_never_entered(SOURCE, executed) == [
        ("Box.unused", 10),
        ("outer.inner", 16),
    ]


def test_a_docstring_plus_one_line_is_entered_only_by_that_line():
    # Only the statement after the docstring (line 12) makes `unused` entered; the docstring line 11 does not.
    without_statement = measure_coverage_report.functions_never_entered(SOURCE, {11})
    with_statement = measure_coverage_report.functions_never_entered(SOURCE, {12})

    assert ("Box.unused", 10) in without_statement
    assert ("Box.unused", 10) not in with_statement


def test_file_rows_sort_by_missing_statements_descending_then_path():
    cov = {
        "files": {
            "src/a.py": {"summary": {"num_statements": 10, "missing_lines": 2, "percent_covered": 80.0}},
            "src/c.py": {"summary": {"num_statements": 8, "missing_lines": 4, "percent_covered": 50.0}},
            "src/b.py": {"summary": {"num_statements": 5, "missing_lines": 4, "percent_covered": 20.0}},
        }
    }

    assert measure_coverage_report.file_rows(cov) == [
        ("src/b.py", 5, 4, 20.0),
        ("src/c.py", 8, 4, 50.0),
        ("src/a.py", 10, 2, 80.0),
    ]


MOD_SOURCE = "def used():\n    return 1\ndef unused():\n    return 2\n"


def test_main_writes_the_summary_headline_and_uncovered_list(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "mod.py").write_text(MOD_SOURCE, encoding="utf-8")
    (root / "src" / "other.py").write_text("x = 1\n", encoding="utf-8")

    cov = {
        "files": {
            "src/mod.py": {
                "executed_lines": [1, 2],
                "missing_lines": [3, 4],
                "summary": {"num_statements": 4, "missing_lines": 2, "percent_covered": 50.0},
            },
            "src/other.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "summary": {"num_statements": 1, "missing_lines": 0, "percent_covered": 100.0},
            },
        },
        "totals": {"num_statements": 5, "missing_lines": 2, "percent_covered": 60.0},
    }
    json_path = tmp_path / "coverage.json"
    json_path.write_text(json.dumps(cov), encoding="utf-8")

    exits = tmp_path / "in"
    exits.mkdir()
    (exits / "exit-1.txt").write_text("0\n", encoding="utf-8")
    (exits / "exit-3.txt").write_text("1\n", encoding="utf-8")

    out = tmp_path / "out"
    code = measure_coverage_report.main(
        ["--json", str(json_path), "--root", str(root), "--exits", str(exits), "--out", str(out)]
    )

    assert code == 0
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "# coverage" in summary.splitlines()
    assert "60.0" in summary
    assert "Functions never entered: 1 (in 1 file)" in summary
    assert "- 3: 1" in summary
    assert "all slots passed" not in summary
    assert "| src/mod.py | 4 | 2 | 50.0 |" in summary

    headline = (out / "headline.txt").read_text(encoding="utf-8").strip()
    assert headline == "Покрытие кода тестами: 60.0%; функций, в которые не заходит ни один тест: 1 (в 1 файлах)."

    uncovered = (out / "uncovered-functions.txt").read_text(encoding="utf-8").splitlines()
    assert uncovered == ["src/mod.py:3 unused"]
