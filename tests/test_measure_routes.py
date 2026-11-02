"""The routes step of the measurement chain (ticket #399): the summary table and headline of hand-made route records.

No game data and no network: `build_summary` only reads the records it is given.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "measure_routes.py"
spec = importlib.util.spec_from_file_location("measure_routes", SCRIPT)
measure_routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_routes)

FULL = {
    "route": "R10",
    "seconds": 90.0,
    "peak_mb": 512.3,
    "entry": {
        "error": None,
        "solver": {"success": 0.0288, "mean": 123.46, "p50": 100.04, "p90": 200.0, "seconds": 1.2},
        "given_route": {"success": 0.03, "mean": 130.0, "p50": 101.0, "p90": 205.0, "gaps": 0},
        "solver_not_dearer": True,
    },
}
FAILED = {
    "route": "R05",
    "seconds": 3.0,
    "peak_mb": None,
    "entry": {
        "error": "no price for 'Chaos|Orb'\nline two",
        "solver": None,
        "given_route": None,
        "solver_not_dearer": None,
    },
}


def _rows(table: str) -> list[list[str]]:
    """The table's body rows as lists of cells (the header and the separator line left out)."""
    lines = [line for line in table.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in line.strip("|").split(" | ")] for line in lines[2:]]


def test_table_has_the_nine_routes_in_order_with_missing_ones_marked():
    table, _ = measure_routes.build_summary([FULL, FAILED])

    assert table.startswith("# routes\n")
    rows = _rows(table)
    assert [row[0] for row in rows] == measure_routes.BENCHMARK_ORDER
    assert len(rows) == 9
    missing = ["R12"] + ["—"] * 8 + ["missing"]
    assert rows[measure_routes.BENCHMARK_ORDER.index("R12")] == missing
    assert [row[0] for row in rows if row[-1] == "missing"] == ["R12", "R11", "R13", "R08", "R09", "R04", "R14"]


def test_full_row_shows_rounded_numbers_and_percent():
    table, _ = measure_routes.build_summary([FULL, FAILED])
    row = next(row for row in _rows(table) if row[0] == "R10")

    assert row == [
        "R10",  # route
        "90.0",  # seconds
        "512.3",  # peak MB
        "123.5",  # solver mean
        "100.0",  # solver p50
        "200.0",  # solver p90
        "2.9%",  # success probability, as a percentage
        "130.0",  # given route mean
        "yes",  # solver not dearer
        "—",  # error
    ]


def test_failed_row_has_dashes_for_no_solver_and_the_error_text():
    table, _ = measure_routes.build_summary([FULL, FAILED])
    row = next(row for row in _rows(table) if row[0] == "R05")

    assert row[:9] == ["R05", "3.0", "—", "—", "—", "—", "—", "—", "—"]
    assert row[9] == "no price for 'Chaos\\|Orb' line two"


def test_headline_counts_only_the_solved_routes():
    _, headline = measure_routes.build_summary([FULL, FAILED])

    assert headline == "Маршрутов посчитано: 1 из 9; самый долгий R10 — 1.5 мин; решатель не дороже гайда на 1 из 1."
    assert "\n" not in headline and len(headline) <= 200


def test_headline_with_no_records():
    _, headline = measure_routes.build_summary([])

    assert headline == "Маршрутов посчитано: 0 из 9; самый долгий —; решатель не дороже гайда на 0 из 0."
