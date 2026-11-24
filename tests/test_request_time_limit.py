"""A user may ask for the time one request takes (#1577, OR-40): the planner's entry takes the request's time limit within the machine's own,
the site's request carries it in its key, and the answer says what limit the plan ran under. Every figure here is a setting handed in by hand;
nothing reads the clock (the run's net itself is `tests/test_budget.py`'s)."""

import dataclasses

import pytest
from cli_support import R12, price_file
from targets_support import DATA
from web_support import API, FixtureWorld, client, r12_target, wait_until_done

import crafting_system.planner._entry as entry
from crafting_system.budget import Budget
from crafting_system.config import load_config
from crafting_system.planner import PlanError, PlanSettings, plan_target, request_budget
from crafting_system.targets import load_target
from crafting_system.web import RequestError, parse_request

MACHINE = Budget(aim_seconds=60.0, seconds=7200.0, memory_mb=12288.0, gap=0.01)  # a machine whose own limit is two hours


def test_a_request_asks_less_time_than_the_machine_gives_and_keeps_the_rest_of_its_budget():
    asked = request_budget(MACHINE, 1800)

    assert asked == dataclasses.replace(MACHINE, seconds=1800.0)  # the aim, the memory net and the proof gap are the machine's


def test_a_request_may_ask_exactly_the_machines_limit_and_none_keeps_it():
    assert request_budget(MACHINE, 7200.0) == MACHINE
    assert request_budget(MACHINE, None) is MACHINE


def test_a_request_past_the_machines_limit_is_refused_in_words():
    with pytest.raises(PlanError, match="7,201 s, is past this machine's own limit of 7,200 s"):
        request_budget(MACHINE, 7201)


@pytest.mark.parametrize("seconds", [0, -5, float("inf"), float("nan"), True, "600", 10**400])
def test_a_time_limit_that_is_no_number_of_seconds_above_zero_is_refused(seconds):
    with pytest.raises(PlanError, match="a number of seconds above zero"):
        request_budget(MACHINE, seconds)


def test_a_machine_with_no_time_limit_takes_any_request_and_no_budget_gives_one_of_the_request_alone():
    assert request_budget(dataclasses.replace(MACHINE, seconds=None), 86_400).seconds == 86_400.0
    assert request_budget(None, 300) == Budget(aim_seconds=None, seconds=300.0, memory_mb=None, gap=0.0)


def test_a_run_counted_in_states_takes_no_time_limit():
    with pytest.raises(PlanError, match="counted in states"):
        request_budget(Budget.in_states(1000), 60)


def test_the_entry_runs_under_the_requests_limit(monkeypatch):
    seen = {}

    def plan_with_starts(*args, **kwargs):
        seen["budget"] = kwargs["budget"]
        raise PlanError("stop here: the budget is what this test reads")

    monkeypatch.setattr(entry, "plan_with_starts", plan_with_starts)
    target = load_target(R12, DATA)
    with pytest.raises(PlanError, match="stop here"):
        plan_target(DATA, target, price_file(), PlanSettings(budget=MACHINE, time_limit_seconds=900))
    assert seen["budget"] == dataclasses.replace(MACHINE, seconds=900.0)

    with pytest.raises(PlanError, match="past this machine's own limit"):
        plan_target(DATA, target, price_file(), PlanSettings(budget=MACHINE, time_limit_seconds=9000))


class TwoHourWorld(FixtureWorld):
    """The fixture world on a machine whose own time limit is two hours."""

    @property
    def budget(self) -> Budget:  # type: ignore[override]
        return MACHINE


def two_hour_world() -> TwoHourWorld:
    return TwoHourWorld(DATA, price_file(), load_config({}))


def test_the_requests_limit_is_filled_in_and_keyed():
    world = two_hour_world()
    plain = parse_request({"target": r12_target()}, "poe1", world)
    spelled = parse_request({"target": r12_target(), "settings": {"time_limit_seconds": 7200}}, "poe1", world)
    shorter = parse_request({"target": r12_target(), "settings": {"time_limit_seconds": 1800}}, "poe1", world)

    assert plain.document["settings"]["time_limit_seconds"] == 7200.0  # the machine's limit, filled in
    assert spelled.key == plain.key  # naming the machine's own limit is the same request
    assert shorter.document["settings"]["time_limit_seconds"] == 1800.0
    assert shorter.key != plain.key  # another time limit is another request: its plan may differ


@pytest.mark.parametrize(("seconds", "words"), [(7201, "past this machine's own limit of 7,200 s"), (0, "above zero"), ("long", "above zero")])
def test_a_request_whose_limit_cannot_be_had_is_refused_at_once(seconds, words):
    with pytest.raises(RequestError, match=f"settings.time_limit_seconds: .*{words}"):
        parse_request({"target": r12_target(), "settings": {"time_limit_seconds": seconds}}, "poe1", two_hour_world())


def test_the_answer_says_the_time_limit_it_ran_under():
    # the fixture world has no time limit of its own, so any limit may be asked; R12's fixture plans in well under it
    with client() as (http, service):
        job = wait_until_done(http, http.post(f"{API}/jobs", json={"target": r12_target(), "settings": {"time_limit_seconds": 3600}}).json()["id"])
        route = http.get(job["route"]["url"]).json()

    assert job["state"] == "done", job
    assert route["request"]["settings"]["time_limit_seconds"] == 3600.0
    assert route["summary"]["time_limit_seconds"] == 3600.0
