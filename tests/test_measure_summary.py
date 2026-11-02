"""The report of the measurement chain (ticket #399): every step's summary under one heading, as measure-report."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "measure_summary.py"
spec = importlib.util.spec_from_file_location("measure_summary", SCRIPT)
measure_summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_summary)

ALL_RESULTS = {
    "bloat": "success",
    "routes": "failure",
    "coverage": "success",
    "repeats": "success",
    "mutation": "cancelled",
}


def test_report_has_the_summary_of_a_present_step_and_no_summary_for_a_missing_one(tmp_path):
    (tmp_path / "measure-bloat").mkdir()
    (tmp_path / "measure-bloat" / "summary.md").write_text("# bloat\n\n| part | merged |\n|---|---|\n", encoding="utf-8")
    # routes has no artifact at all: its heading stays, with the fixed line under it

    report = measure_summary.build_report(tmp_path, ALL_RESULTS)

    assert report.startswith("# Measurement week report\n\n## bloat (success)\n\n# bloat\n\n| part | merged |\n|---|---|\n\n")
    assert "## routes (failure)\n\nNo summary.\n\n" in report
    assert report.index("## bloat (success)") < report.index("## routes (failure)") < report.index("## coverage (success)")


def test_report_has_a_heading_for_every_step_in_order(tmp_path):
    report = measure_summary.build_report(tmp_path, ALL_RESULTS)

    headings = [line for line in report.splitlines() if line.startswith("## ")]
    assert headings == [
        "## bloat (success)",
        "## routes (failure)",
        "## coverage (success)",
        "## repeats (success)",
        "## mutation (cancelled)",
    ]
    assert report.count("No summary.") == 5
