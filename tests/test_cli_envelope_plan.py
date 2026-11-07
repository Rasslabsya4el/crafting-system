"""`make_plan(solver="envelope")` on the fixture world's R12 (ticket #377, OR-12, OR-13): the same plan and mean as the packed walk, the limit in every surface.

* the mean and the policy equal `solver="packed"`'s (the full walk) to 1e-9, and the plan reaches the goal;
* the limit that says which cut ran and what it guarantees is in `Plan.limits`, in the text report, in the JSON policy and on the route page, the way the
  other limits are (`tests/test_cli_limits.py`); a plan solved by another solver carries none;
* a net given to `make_plan` ends the search, and the plan says it is not shown to be the best, with its bounds;
* `solver="envelope"` ignores a time budget (it is always exact) and an abstraction the bound cannot be built for is a `PlanError`, not a silent walk.

The walk-free bound needs no game dump, so this runs on the committed fixture pool. Real routes (R05, R13) are `tests/test_cli_envelope_real.py`.
"""

import dataclasses
import json
from html import escape

import pytest
from cli_support import R12, price_file
from coarse_support import CRAFTS, REMOVE
from coarse_support import DATA as COARSE
from targets_support import DATA
from test_cli_approximate import PRICES as APPROX_PRICES
from test_cli_approximate import TARGET as APPROX_TARGET

from crafting_system.cli import build_report, make_plan, policy_document, render_text
from crafting_system.cli._envelope import Net
from crafting_system.cli._limits import SHOWN_LABELS, SOLVE, limit_text
from crafting_system.cli._plan import PlanError
from crafting_system.cli._route_html import render_page
from crafting_system.cli._offers import offer_of
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.prices import PriceEntry
from crafting_system.targets import load_target, parse_target


@pytest.fixture(scope="module")
def both():
    target = load_target(R12, DATA)
    return make_plan(DATA, target, price_file(), solver="packed"), make_plan(DATA, target, price_file(), solver="envelope")


def search_limit(plan):
    return [limit for limit in plan.limits if limit.kind == SOLVE and limit.what.startswith("The search")]


def test_the_envelope_plan_has_the_packed_plans_mean_and_policy(both):
    full, envelope = both
    assert envelope.mean_remaining == pytest.approx(full.mean_remaining, rel=1e-9)
    for state, action in envelope.policy.items():
        assert envelope.solution.values[state] == pytest.approx(full.solution.values[state], rel=1e-9)
        assert full.policy[state].label == action.label or envelope.solution.values[state] == pytest.approx(full.solution.values[state], rel=1e-9)
    assert envelope.packed is not None and envelope.packed.info["envelope"].exact
    assert envelope.risk is None or envelope.risk.mean.value == pytest.approx(full.risk.mean.value, rel=1e-6)


def test_the_limit_is_in_the_plan_the_text_the_json_and_the_page_and_only_in_an_envelope_plan(both):
    full, envelope = both
    assert not search_limit(full)
    (cut,) = search_limit(envelope)
    assert "The plan is the cheapest among the methods offered." in cut.guarantee
    report = build_report(envelope, DATA)
    assert limit_text(cut) in render_text(report)
    assert any(entry["what"] == cut.what and entry["guarantee"] == cut.guarantee for entry in policy_document(report)["limits"])
    page = render_page(Page("x", (build_section(route_input(envelope), DATA),)))
    assert escape(limit_text(cut, SHOWN_LABELS)) in page


@pytest.fixture(scope="module")
def coarse():
    """The coarse fixture of `test_cli_approximate` (about 200 states), its start item bought for 5 Chaos so that a restart exists."""
    names = set()
    for action in (*CRAFTS, REMOVE):
        names |= set(offer_of(action, action.label(COARSE), COARSE).resources)
    prices = dataclasses.replace(APPROX_PRICES, prices={name: PriceEntry(2.0, "test") for name in names})
    keys = json.dumps(["chaos-orb", "remove-crafted-mods", *(craft.label(COARSE) for craft in CRAFTS)])
    text = APPROX_TARGET.replace("start: given", "start: bought") + f"actions: {keys}\n"
    target = parse_target(text, COARSE, source="t.yaml")
    return target, prices, make_plan(COARSE, target, prices, start_price=5.0, solver="packed", with_risk=False)


def test_a_mid_sized_plan_is_the_full_walks(coarse):
    target, prices, full = coarse
    plan = make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", with_risk=False)
    assert plan.mean_remaining == pytest.approx(full.mean_remaining, rel=1e-9)
    info = plan.packed.info["envelope"]
    assert info.exact and info.expanded <= info.touched <= len(full.solution.values)
    for state in plan.policy:
        assert plan.solution.values[state] == pytest.approx(full.solution.values[state], rel=1e-9)


def test_a_net_in_make_plan_stops_the_search_and_the_plan_says_so(coarse):
    target, prices, full = coarse
    exact = full.mean_remaining
    stopped = make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", net=Net(states=96), with_risk=False)
    info = stopped.packed.info["envelope"]
    assert not info.exact and "limit is 96" in info.stopped
    (cut,) = search_limit(stopped)
    assert "The search was stopped" in cut.what and "not shown to be the best" in cut.guarantee
    assert info.lower <= exact * (1 + 1e-9) <= info.upper * (1 + 1e-9)
    assert stopped.mean_remaining == info.upper


def test_a_net_that_stops_before_any_plan_exists_is_an_error_that_says_so(coarse):
    target, prices, _ = coarse
    with pytest.raises(PlanError, match="before any policy that can be executed was found"):
        make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", net=Net(states=1), with_risk=False)


def test_a_time_budget_is_ignored_by_the_envelope_search():
    target = load_target(R12, DATA)
    plan = make_plan(DATA, target, price_file(), solver="envelope", budget=0.0, with_risk=False)
    assert plan.approximation is None and plan.packed.info["envelope"].exact


def test_an_unknown_solver_is_still_refused():
    with pytest.raises(ValueError, match="solver must be one of auto, object, packed, envelope"):
        make_plan(DATA, load_target(R12, DATA), price_file(), solver="fast")


def test_a_target_the_bound_cannot_be_built_for_is_a_plan_error(monkeypatch):
    from crafting_system.actions import OutOfScopeError
    from crafting_system.cli import _envelope_plan

    def refuse(*_args, **_kwargs):
        raise OutOfScopeError("a goal with a roll limit has no members")

    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", refuse)
    with pytest.raises(PlanError, match="the envelope search cannot answer this target: a goal with a roll limit"):
        make_plan(DATA, load_target(R12, DATA), price_file(), solver="envelope", with_risk=False)


def test_a_bound_that_falls_is_a_plan_error_not_a_silent_answer(monkeypatch):
    from crafting_system.cli import _plan
    from crafting_system.cli._envelope_plan import BoundError

    def refuse(*_args, **_kwargs):
        raise BoundError("the lower bound fell by 3.00% from one round of the search to the next")

    monkeypatch.setattr(_plan, "envelope_result", refuse)
    with pytest.raises(PlanError, match="the envelope search cannot answer this target: the lower bound fell"):
        make_plan(DATA, load_target(R12, DATA), price_file(), solver="envelope", with_risk=False)
