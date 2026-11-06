"""What the steps of the route page cannot show is a limit of the plan (ticket #466, rebuild 6a; OR-12, OR-13; records of ticket #459).

The steps are made from the policy's item states with the expected visits of each (`_route_flow`). Two things can keep the page from showing
all of it, and each is a `Limit` of kind `step-numbers` in `Plan.limits`, written by `flow_limits` when the plan is finished, with a
guarantee that says what the page then cannot promise:

* the visits could not be solved to a relative residual of 1e-9 (a chance per use lost in the float, or a sparse solve that did not converge):
  the page leaves out how often a step is used and what it costs, and a step that joins states shows their plain mean;
* the policy has more than `ENTRY_STATES` states that can finish: the share of runs that ever enter a step is left out.

A test per source, as in `tests/test_cli_limits.py`: each fails when `Plan` stops writing the limit. Then the three surfaces, and a given route's
own section.
"""

from html import escape

import pytest
from cli_support import R12, price_file
from limits_support import of_kind, only
from targets_support import DATA, EXAMPLES

from crafting_system.cli import build_report, evaluate_route, make_plan, parse_route, policy_document, render_text
from crafting_system.cli import _route_flow
from crafting_system.cli._limits import GROUPS, SHOWN_LABELS, STEPS, limit_text
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, given_route_input, route_input
from crafting_system.targets import load_target

ROUTE = EXAMPLES.parents[0] / "routes" / "r12-lightning-amulet.yaml"


@pytest.fixture
def unsolvable(monkeypatch):
    """The visits of every chain cannot be solved: the one place the numbers can still stop."""
    solved = _route_flow._visits

    def stuck(*arguments):
        visits, _, _, position = solved(*arguments)
        return visits * 0.0, False, None, position

    monkeypatch.setattr(_route_flow, "_visits", stuck)


def made():
    return make_plan(DATA, load_target(R12, DATA), price_file())


def test_a_plan_whose_visits_were_solved_and_whose_entry_chances_were_computed_has_no_such_limit():
    plan = made()

    assert not of_kind(plan.limits, STEPS)
    assert STEPS in [kind for kind, _ in GROUPS]


def test_visits_that_could_not_be_solved_are_a_limit_that_says_what_the_page_then_leaves_out(unsolvable):
    limit = only(made().limits, STEPS)

    assert limit.what == "How often a step is used is not shown" and "relative residual of 1e-9" in limit.why
    assert limit.guarantee.startswith("The plan is the cheapest among the methods offered.")  # `claim`: an approximate answer says "within the stated gap"
    assert "plain mean of those states" in limit.guarantee and limit.approximate  # what the page cannot promise (OR-13)
    assert "relative residual" not in limit.guarantee  # the guarantee is in player words


def test_a_policy_with_more_states_than_the_entry_limit_is_a_limit_that_keeps_every_other_number(monkeypatch):
    monkeypatch.setattr(_route_flow, "ENTRY_STATES", 0)

    limit = only(made().limits, STEPS)

    assert limit.what == "How often a run enters a step is not shown" and "made for at most 0 states" in limit.why
    assert "only the share of runs that ever enter a step is missing" in limit.guarantee and limit.approximate


def test_the_text_the_json_and_the_page_show_the_limit_in_the_same_words(unsolvable):
    plan = made()
    limit = only(plan.limits, STEPS)
    report = build_report(plan, DATA)

    text = render_text(report)
    document = policy_document(report)
    page = render_page(Page("x", (build_section(route_input(plan), DATA),)))

    assert limit_text(limit) in text
    assert [entry for entry in document["limits"] if entry["kind"] == STEPS] == [
        {"kind": STEPS, "what": limit.what, "why": limit.reason(), "guarantee": limit.guarantee, "count": 0, "labels": [], "names": []}
    ]
    assert escape(limit_text(limit, SHOWN_LABELS)) in page and "What the steps show" in page


def test_a_given_route_says_its_own_limit_in_its_section_and_the_plans_stays_in_the_planners(unsolvable):
    plan = made()
    route = parse_route(ROUTE.read_text(encoding="utf-8"), plan, DATA, "route.yaml")
    result = evaluate_route(plan, route, DATA)

    own = build_section(given_route_input(plan, route, result), DATA, prefix="g-", anchor="given", route_field=False).goal
    planners = build_section(route_input(plan), DATA).goal

    assert [field.label for field in own.leaves_out] == ["What the steps show"]  # the plan's other limits are said once, in the planner's section
    assert "What the steps show" in [field.label for field in planners.leaves_out]
    assert len(planners.leaves_out) > 1
