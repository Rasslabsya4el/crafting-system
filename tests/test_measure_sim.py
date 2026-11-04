"""The simulation check of the measurement chain (ticket #399, piece G): pooling of the parts, the summary table and the trial scale.

No game data and no network: `pool`, `build_summary` and `runs_for` only read the records they are given.
"""

import importlib.util
import math
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "measure_sim.py"
spec = importlib.util.spec_from_file_location("measure_sim", SCRIPT)
measure_sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_sim)


def _kind(costs, exact=None, successes=None, stopped=0, unfinished=0, infinite=False):
    """One kind of one part, as `measure_sim.py run` writes it: the sums of the run totals, not the list."""
    return {
        "exact_mean": exact,
        "exact_infinite": infinite,
        "n": len(costs),
        "successes": len(costs) if successes is None else successes,
        "stopped": stopped,
        "unfinished": unfinished,
        "sum": float(sum(costs)),
        "sumsq": float(sum(c * c for c in costs)),
    }


def _part(route, part, parts, kinds):
    return {"route": route, "part": part, "parts": parts, "kinds": kinds}


def _z_row(route, kind, z):
    """A pooled row whose z is exactly `z`: its standard error is read from a first pooling, then the exact mean is set from it."""
    costs = [8.0, 12.0, 8.0, 12.0]
    first = measure_sim.pool([_part(route, 1, 1, {kind: _kind(costs)})])[(route, kind)]
    exact = first["mean"] - z * first["se"]
    return measure_sim.pool([_part(route, 1, 1, {kind: _kind(costs, exact=exact)})])[(route, kind)]


# --- pool ---------------------------------------------------------------------------------------


def test_pool_sums_the_parts_and_takes_the_exact_mean_of_part_1():
    part1 = _part("R10", 1, 2, {"solver": _kind([8.0, 10.0, 12.0], exact=9.0)})
    part2 = _part("R10", 2, 2, {"solver": _kind([9.0, 11.0, 13.0, 7.0], exact=99.0)})

    row = measure_sim.pool([part2, part1])[("R10", "solver")]  # the parts given out of order

    assert row["n"] == 7
    assert row["successes"] == 7
    assert row["parts_seen"] == 2
    assert row["mean"] == pytest.approx(70.0 / 7)  # 10.0
    # the sample variance over all seven totals: (728 - 7 * 10^2) / 6
    assert row["var"] == pytest.approx(28.0 / 6)
    assert row["se"] == pytest.approx(math.sqrt(28.0 / 6 / 7))
    assert row["exact"] == 9.0  # the first non-null exact mean, the one of part 1
    assert row["z"] == pytest.approx((10.0 - 9.0) / math.sqrt(28.0 / 6 / 7))


def test_pool_leaves_out_a_part_that_failed():
    part1 = _part("R10", 1, 2, {"solver": _kind([8.0, 10.0, 12.0], exact=10.0)})
    failed = _part("R10", 2, 2, {"solver": {"exact_mean": None, "error": "boom"}})

    row = measure_sim.pool([part1, failed])[("R10", "solver")]

    assert row["n"] == 3
    assert row["parts_seen"] == 1
    assert row["mean"] == pytest.approx(10.0)


def test_pool_gives_no_z_when_there_is_no_exact_mean():
    part1 = _part("R04", 1, 1, {"guide": _kind([8.0, 12.0, 8.0, 12.0], exact=None, stopped=3)})

    row = measure_sim.pool([part1])[("R04", "guide")]

    assert row["exact"] is None
    assert row["z"] is None
    assert row["stopped"] == 3


def test_pool_marks_an_infinite_exact_mean_and_gives_no_z():
    # a guide with gaps: its exact given mean is infinite, run_route writes null for it
    part1 = _part("R04", 1, 1, {"guide": _kind([8.0, 12.0], exact=None, stopped=3, infinite=True)})

    row = measure_sim.pool([part1])[("R04", "guide")]

    assert row["exact_infinite"] is True
    assert row["exact"] is None
    assert row["z"] is None


def test_summary_shows_an_infinite_exact_mean_and_lists_it():
    part1 = _part("R04", 1, 1, {"guide": _kind([8.0, 12.0], exact=None, stopped=3, infinite=True)})

    table, _ = measure_sim.build_summary(list(measure_sim.pool([part1]).values()))

    row = next(line for line in table.splitlines() if line.startswith("| R04 | guide"))
    assert row == "| R04 | guide | inf | 10.00 ± 2.00 | — | 2 | 2 | 3 | 0 | 1 of 1 |"
    not_finite = table.split("**exact mean not finite**", 1)[1].split("**stopped or unfinished runs**", 1)[0]
    assert "R04 guide" in not_finite


# --- runs_for: the runs of a part and the trial scale ----------------------------------------------


def test_runs_per_part_are_5000_except_r04_and_r14():
    assert measure_sim.runs_for("R10") == 5000
    assert measure_sim.runs_for("R04") == 300
    assert measure_sim.runs_for("R14") == 300


@pytest.mark.parametrize(
    ("route", "scale", "expected"),
    [
        ("R10", 0.02, 100),  # 5000 * 0.02
        ("R04", 0.02, 20),  # 300 * 0.02 = 6, raised to the minimum of 20
        ("R14", 0.5, 150),  # 300 * 0.5
        ("R12", 0.0001, 20),  # far below the minimum
        ("R10", 0.0123, 62),  # 61.5 rounds up
        ("R10", 1.0, 5000),  # no scale: the base count
    ],
)
def test_trial_scale_rounds_up_to_at_least_20(route, scale, expected):
    assert measure_sim.runs_for(route, scale) == expected


# --- build_summary ------------------------------------------------------------------------------


def test_summary_lists_disagreeing_and_watched_rows_and_the_stopped_guide():
    rows = [
        _z_row("R10", "solver", 7.0),  # disagree
        _z_row("R12", "solver", 4.0),  # watch
        measure_sim.pool([_part("R04", 1, 1, {"guide": _kind([8.0, 12.0], exact=None, stopped=3)})])[("R04", "guide")],
    ]

    table, _ = measure_sim.build_summary(rows)

    disagree = table.split("**disagree**", 1)[1].split("**watch**", 1)[0]
    watch = table.split("**watch**", 1)[1].split("stopped", 1)[0]
    stopped = table.split("stopped or unfinished", 1)[1]
    assert "R10" in disagree and "solver" in disagree
    assert "R12" not in disagree
    assert "R12" in watch and "solver" in watch
    assert "R10" not in watch
    assert "R04" in stopped and "guide" in stopped


def test_summary_table_has_routes_in_order_and_missing_ones_as_dashes():
    rows = [_z_row("R10", "solver", 1.0)]

    table, _ = measure_sim.build_summary(rows)

    body = [line for line in table.splitlines() if line.startswith("| ") and not line.startswith("| route ")]
    assert [line.split(" | ")[0].lstrip("| ") for line in body] == measure_sim.ROUTE_ORDER
    r11 = next(line for line in body if line.startswith("| R11 "))
    assert r11 == "| R11 | — | — | — | — | — | — | — | — | — |"


def test_summary_headline_counts_the_routes_and_the_two_lists():
    rows = [
        _z_row("R10", "solver", 7.0),
        _z_row("R12", "solver", 4.0),
        measure_sim.pool([_part("R04", 1, 1, {"guide": _kind([8.0, 12.0], exact=None, stopped=3)})])[("R04", "guide")],
    ]

    _, headline = measure_sim.build_summary(rows)

    assert headline == (
        "Проверка симуляцией: маршрутов 3; расхождений (|z|>5): 1; под наблюдением (3<|z|≤5): 1; "
        "самое большое |z| = 7.00 у R10 solver."
    )
    assert "\n" not in headline


def test_summary_headline_with_no_rows():
    _, headline = measure_sim.build_summary([])

    assert headline == (
        "Проверка симуляцией: маршрутов 0; расхождений (|z|>5): 0; под наблюдением (3<|z|≤5): 0; "
        "самое большое |z| = —."
    )
