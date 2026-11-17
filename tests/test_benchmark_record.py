"""The heavy benchmark's record of two runs and its "no worse than" check (#1109), on hand-written records.

A route's ceiling is its higher recorded cost plus the larger of the two runs' spread and 1% of that cost (`TOLERANCE_FLOOR`, the proof gap).
"""

import pytest

from crafting_system.benchmark_record import (
    FAIL,
    NO_PLAN,
    NOT_RECORDED,
    NOT_RUN,
    PASS,
    PLANNED,
    TOLERANCE_FLOOR,
    UNSTABLE,
    RouteRecord,
    check_run,
    failed,
    make_record,
    merge_documents,
    record_of_plan,
    render_check,
)


def planned(mean: float) -> dict:
    return record_of_plan(mean, mean * 0.9, 300.0, 4000.0, "stopped: the time limit")


def unplanned(stop: str = "stopped after 600 s: no plan found yet") -> dict:
    return record_of_plan(None, None, None, None, stop)


def run(**routes: dict) -> dict:
    """A `benchmark.json` of a run with --net, holding only what the record reads."""
    return {"machine": {"cpu": "x"}, "ran_at": "2026-11-17T10:00:00+00:00", "prices": None, "budget": None,
            "routes": [{"id": name, "error": record["stop"] if record["mean"] is None else None, "record": record} for name, record in routes.items()]}


RECORD = make_record(
    run(R05=planned(90.0), R10=planned(40.0), R11=unplanned(), R12=planned(41.0)),
    run(R05=planned(100.0), R10=planned(40.0), R11=unplanned(), R12=unplanned()),
)


def verdict_of(new: dict, name: str):
    return next(verdict for verdict in check_run(RECORD, new) if verdict.route == name)


def test_the_spread_and_the_ceiling_of_two_runs():
    r05, r10 = RECORD["routes"]["R05"], RECORD["routes"]["R10"]
    assert r05["state"] == PLANNED and r05["spread"] == pytest.approx(10.0) and r05["spread_share"] == pytest.approx(10.0 / 90.0)
    assert r05["ceiling"] == pytest.approx(110.0)  # the spread is above 1% of 100
    assert r10["spread"] == 0.0 and r10["ceiling"] == pytest.approx(40.0 * (1 + TOLERANCE_FLOOR))  # the floor where the runs agree
    assert RECORD["routes"]["R11"]["state"] == NO_PLAN and RECORD["routes"]["R11"]["ceiling"] is None
    assert RECORD["routes"]["R12"]["state"] == UNSTABLE and RECORD["routes"]["R12"]["ceiling"] is None


def test_a_route_within_the_tolerance_passes():
    verdict = verdict_of(run(R05=planned(109.0)), "R05")
    assert verdict.outcome == PASS and "within the ceiling of 110.00 c" in verdict.why
    assert verdict_of(run(R10=planned(40.3)), "R10").outcome == PASS
    assert verdict_of(run(R05=planned(60.0)), "R05").outcome == PASS  # cheaper is never worse


def test_a_route_above_the_tolerance_fails():
    verdict = verdict_of(run(R05=planned(110.5)), "R05")
    assert verdict.outcome == FAIL and "above the ceiling of 110.00 c" in verdict.why
    assert verdict_of(run(R10=planned(40.5)), "R10").outcome == FAIL
    assert failed(check_run(RECORD, run(R05=planned(100.0), R10=planned(40.5))))


def test_no_plan_where_the_record_has_one_fails():
    verdict = verdict_of(run(R05=unplanned("stopped after 600 s: the memory limit")), "R05")
    assert verdict.outcome == FAIL and "no plan (stopped after 600 s: the memory limit)" in verdict.why


def test_a_route_with_no_recorded_plan_or_an_unstable_one_passes_whatever_it_gives():
    assert verdict_of(run(R11=unplanned()), "R11").outcome == PASS
    assert "now a plan of 600.00 c" in verdict_of(run(R11=planned(600.0)), "R11").why
    assert verdict_of(run(R12=unplanned()), "R12").outcome == PASS
    assert verdict_of(run(R12=planned(1000.0)), "R12").outcome == PASS


def test_a_route_missing_from_the_run_fails_and_a_route_not_recorded_is_told():
    """A runner killed for its memory or its timeout writes no entry: its routes fail, they do not pass by being absent."""
    verdicts = check_run(RECORD, run(R05=planned(95.0), R99=planned(1.0)))
    outcomes = {verdict.route: verdict.outcome for verdict in verdicts}
    assert outcomes == {"R05": PASS, "R10": NOT_RUN, "R11": NOT_RUN, "R12": NOT_RUN, "R99": NOT_RECORDED}
    assert failed(verdicts)
    assert render_check(verdicts).splitlines()[0] == "R05: PASS: 95.00 c, within the ceiling of 110.00 c"


def test_a_check_of_some_routes_only_asks_for_those():
    verdicts = check_run(RECORD, run(R05=planned(95.0)), routes=["R05"])
    assert [(verdict.route, verdict.outcome) for verdict in verdicts] == [("R05", PASS)] and not failed(verdicts)
    with pytest.raises(ValueError, match="does not hold R99"):
        check_run(RECORD, run(R05=planned(95.0)), routes=["R99"])


def test_a_file_that_is_not_a_record_or_a_run_without_the_net_is_refused():
    with pytest.raises(ValueError, match="not a record of the heavy benchmark"):
        check_run({"routes": {}}, run())
    with pytest.raises(ValueError, match="R05 has no record: the run was not made with --net"):
        check_run(RECORD, {"routes": [{"id": "R05", "error": None, "record": None}]})


def test_a_record_needs_both_runs_of_every_route_asked_for():
    with pytest.raises(ValueError, match="R12 is not in both runs"):
        make_record(run(R05=planned(1.0)), run(R05=planned(1.0), R12=planned(1.0)), routes=["R05", "R12"])


def test_a_split_run_is_merged_and_a_route_in_two_parts_is_refused():
    merged = merge_documents([run(R05=planned(1.0)), run(R10=planned(2.0))])
    assert [entry["id"] for entry in merged["routes"]] == ["R05", "R10"] and merged["machine"] == [{"cpu": "x"}]
    with pytest.raises(ValueError, match="R05 is in more than one part"):
        merge_documents([run(R05=planned(1.0)), run(R05=planned(2.0))])


def test_an_entry_with_an_error_and_no_record_counts_as_no_plan():
    document = {"routes": [{"id": "R05", "error": "a bad price", "record": None}]}
    assert RouteRecord(planned(1.0), planned(1.0)).state == PLANNED
    assert verdict_of(document, "R05").why.startswith("no plan (a bad price)")
