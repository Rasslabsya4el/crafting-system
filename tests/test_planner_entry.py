"""The planner's one entry, called with no command line (ticket #880): `plan_target(data, target, prices, settings)` on R12's fixture.

Done when (the ticket): a test calls the planner's entry directly and gets the same plan the command prints. The command is run once on
R12 (`cli_support.run`); the entry is then called with the settings that run had, and its plan must give the same text report and the same
JSON policy, line for line, but for the two run times. The other tests pin what the entry is: `plan_with_starts` under one name, with
the planner's own defaults, and a plan that cannot be finished when nobody presents it (issue #882).
"""

import dataclasses
import inspect
import json

import pytest
from cli_support import R12, TODAY, price_file, read_json
from cli_support import run as run_command
from targets_support import DATA

import crafting_system.planner as planner
from crafting_system.budget import Budget
from crafting_system.cli import build_report, policy_document, render_text
from crafting_system.config import load_config
from crafting_system.planner import BUDGET_SECONDS, Plan, PlanSettings, make_plan, plan_target, plan_with_starts
from crafting_system.planner import _presenter
from crafting_system.targets import load_target

RUN_TIME = "Run time: "  # the one line of the text that holds seconds
TIMINGS = "timings_seconds"  # the one object of the JSON that holds seconds


def without_times(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.startswith(RUN_TIME)]


def settings_of_the_command() -> PlanSettings:
    """What `cli_support.run` makes the command ask of the planner: the settings file's defaults, the fixed day, the default aim and no net."""
    config = load_config({})
    return PlanSettings(
        recipe_starts=config.recipe_starts,
        price_source=config.price_source,
        price_gap_percent=config.price_gap_percent,
        today=TODAY,
        budget=Budget(aim_seconds=BUDGET_SECONDS, seconds=None, memory_mb=None),
        strands=config.memory_strands,
    )


def test_the_entry_gives_the_plan_the_command_prints_on_r12(tmp_path, capsys):
    code, out = run_command(tmp_path, prices=price_file())
    printed = capsys.readouterr().out
    assert code == 0

    plan = plan_target(DATA, load_target(R12, DATA), price_file(), settings_of_the_command())

    assert isinstance(plan, Plan)
    report = build_report(plan, DATA)
    text = render_text(report, None, target_name=R12.name)
    assert without_times(text) == without_times(printed)[: len(without_times(text))]  # the command then says where it wrote its files
    assert [line for line in without_times(printed)[len(without_times(text)) :] if line] == [
        f"JSON policy written to {out}",
        f"Route view written to {out.parent / (R12.stem + '.route.html')}",
    ]
    document = json.loads(json.dumps(policy_document(report, None, target_name=R12.name)))  # as the file holds it
    written = read_json(out)
    assert document.keys() == written.keys() and TIMINGS in written
    assert {key: value for key, value in document.items() if key != TIMINGS} == {key: value for key, value in written.items() if key != TIMINGS}


def test_the_entry_is_the_start_choice_with_the_settings_passed_by_name(monkeypatch):
    seen = {}

    def spy(data, target, prices, **fields):
        seen.update(data=data, target=target, prices=prices, fields=fields)
        return "the plan"

    monkeypatch.setattr(planner._entry, "plan_with_starts", spy)
    settings = PlanSettings(
        recipe_starts=False, start_price=7.0, price_source="trade", price_gap_percent=35.0, today=TODAY,
        budget=Budget(aim_seconds=None, seconds=5.0, memory_mb=None), strands=True, solver="envelope", judges_route=True,
    )  # fmt: skip

    assert plan_target("data", "target", "prices", settings) == "the plan"
    assert (seen["data"], seen["target"], seen["prices"]) == ("data", "target", "prices")
    assert seen["fields"] == vars(settings)  # every setting, each under its own name, and nothing else


def test_the_defaults_of_the_settings_are_the_planners_own():
    """A caller that gives no settings gets what `plan_with_starts` and `make_plan` do by themselves."""
    start_choice = inspect.signature(plan_with_starts).parameters
    one_plan = inspect.signature(make_plan).parameters
    for field in dataclasses.fields(PlanSettings):
        own = start_choice[field.name] if field.name in start_choice else one_plan[field.name]
        assert field.default == own.default, field.name


def test_with_recipe_starts_off_the_entry_is_the_plan_of_the_targets_own_item():
    target = load_target(R12, DATA)

    plan = plan_target(DATA, target, price_file(), PlanSettings(recipe_starts=False))
    direct = make_plan(DATA, target, price_file())

    assert plan.starts is None and direct.starts is None
    assert plan.mean_remaining == direct.mean_remaining and plan.limits == direct.limits
    assert plan.risk.p90 == direct.risk.p90


def test_a_plan_is_not_finished_when_no_presenter_is_named(monkeypatch):
    """Issue #882: the page's maths tells part of `Plan.limits`, so a plan with no presenter is an error, never a plan with fewer limits."""
    monkeypatch.setattr(_presenter, "_SOURCE", None)

    with pytest.raises(RuntimeError, match="no presenter of plans is named"):
        plan_target(DATA, load_target(R12, DATA), price_file())


def test_a_caller_that_presents_nothing_says_so_and_gets_the_other_limits(monkeypatch):
    target = load_target(R12, DATA)
    shown = plan_target(DATA, target, price_file())
    monkeypatch.setattr(_presenter, "_SOURCE", None)
    planner.present_with(lambda plan: ())

    bare = plan_target(DATA, target, price_file())

    assert set(bare.limits) <= set(shown.limits) and bare.mean_remaining == shown.mean_remaining
