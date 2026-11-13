"""`make_plan(solver="envelope")` on the fixture world's R12 (ticket #377, OR-12, OR-13): the same plan and mean as the packed walk, the limit in every surface.

* the mean and the policy equal `solver="packed"`'s (the full walk) to 1e-9, and the plan reaches the goal;
* the limit that says which cut ran and what it guarantees is in `Plan.limits`, in the text report, in the JSON policy and on the route page, the way the
  other limits are (`tests/test_cli_limits.py`); a plan solved by another solver carries none;
* a net given to `make_plan` ends the search, and the plan says it is not shown to be the best, with its bounds;
* a time budget never brings the ladder's approximate answer (under a budget the search stops at a proved gap, `tests/test_envelope_gap_stop_plan.py`, #826) and an
  abstraction the bound cannot be built for is a `PlanError`, not a silent walk.

The walk-free bound needs no game dump, so this runs on the committed fixture pool. Real routes (R05, R13) are `tests/test_cli_envelope_real.py`.
"""

import dataclasses
import json
import re
from html import escape

import pytest
from cli_support import R12, price_file
from coarse_support import CRAFTS, REMOVE
from coarse_support import DATA as COARSE
from targets_support import DATA
from test_cli_approximate import PRICES as APPROX_PRICES
from test_cli_approximate import TARGET as APPROX_TARGET

from crafting_system.cli import build_report, make_plan, policy_document, render_text
from crafting_system.planner._envelope import Net
from crafting_system.planner._envelope_plan import EnvelopeInfo, certificate_gap, certificate_gap_text, certificate_text
from crafting_system.planner._limits import SHOWN_LABELS, SOLVE, limit_text
from crafting_system.planner._plan import PlanError
from crafting_system.cli._route_html import render_page
from crafting_system.planner._offers import offer_of
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


def test_a_stopped_search_prints_the_certificate_next_to_the_point_answer(coarse):
    """#499: the `Limit` of a net stop carries [LB, U], the gap, the bound used and that it bounds the whole graph; the plan stays the answer."""
    target, prices, full = coarse
    stopped = make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", net=Net(states=96))
    info = stopped.packed.info["envelope"]
    (cut,) = search_limit(stopped)
    text = limit_text(cut)
    assert f"it costs {info.upper:,.2f} Chaos on average" in text  # the point answer comes first and is the exact mean of the plan kept
    assert f"[{info.lower:,.2f}, {info.upper:,.2f}]" in text
    gap = certificate_gap(info)
    assert gap == pytest.approx(info.upper / info.lower - 1.0) and f"{gap:.2%}" in text
    assert info.lower <= full.mean_remaining * (1 + 1e-9) <= info.upper * (1 + 1e-9)
    assert "including the ones the search did not look at" in text and "rarity" in text  # the bound used, and what it bounds
    assert "never prices a step above its true cost" in text and "not because it was checked on every item the crafting can reach" in text  # LB rests on the build of the bound, not on a check of every tip
    assert not re.search(r"graph|lower bound|lower end|optimistic", text, re.I)  # player words (#481)
    assert "about" not in text and " to " not in text.split("[")[1].split("]")[0]  # never an interval answer (OR-11)
    report = build_report(stopped, COARSE)
    assert text in render_text(report)  # the text report, and the JSON policy, say it in the same words
    assert any(entry["guarantee"] == cut.guarantee for entry in policy_document(report)["limits"])


def test_a_finished_search_prints_no_certificate(both):
    _, envelope = both
    (cut,) = search_limit(envelope)
    assert "[" not in limit_text(cut) and "best possible cost" not in limit_text(cut) and "exact" in cut.guarantee


def test_a_nearly_closed_stop_prints_figures_that_differ_and_a_gap_that_is_not_zero():
    """The R14 case (run 42331454969: LB 5784.48786466286, U 5784.4886922212545, gap 1.4e-7): two decimals and a percent printed
    "[5,784.49, 5,784.49]" and "0.00%", which reads as a proved plan."""
    info = EnvelopeInfo(False, "the time limit of 25 seconds was reached", 5784.48786466286, 5784.4886922212545, 8, 93884, 91531, 99106, 296729, 0, True, None, 1969, 12.8, 40.6, None)
    text = certificate_text(info)
    print(text.split(" The lower end")[0])
    assert "[5,784.49, 5,784.49]" not in text and "[5,784.488, 5,784.489]" in text
    assert "at most 0.000014% more than the best possible cost." in text and "less one" not in text and "0.00%" not in text
    assert certificate_gap_text(1.4306511020301116e-07) == "0.000014%" and certificate_gap_text(0.0) == "0%"
    assert certificate_gap_text(0.003681416052256692) == "0.37%" and certificate_gap_text(0.0005) == "0.050%" and certificate_gap_text(0.3206) == "32.06%"  # R04 and R05 keep their format


def test_a_lower_figure_rounded_just_above_the_plan_is_clipped_to_it():
    info = EnvelopeInfo(False, "the time limit of 1 seconds was reached", 10.0000000001, 10.0, 2, 5, 3, 3, 4, 0, True, None, 9, 0.0, 0.0, None)
    assert "[10.00, 10.00]" in certificate_text(info) and "costs less than 10.00 on average" in certificate_text(info)


def test_the_guarantee_of_a_stopped_search_is_in_player_words_like_every_limit(coarse):
    """The rule of `test_cli_limits` (no internal name in a guarantee) holds for the stopped-search limit too, not only for the finished one."""
    target, prices, _ = coarse
    stopped = make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", net=Net(states=96), with_risk=False)
    (cut,) = search_limit(stopped)
    assert cut.guarantee.endswith(".") and cut.guarantee[0].isupper()
    assert not re.search(r"[a-z]+-[a-z]+-?[a-z]*|_|`|#\d|ticket|ADR|OR-\d|kind=", cut.guarantee), cut.guarantee
    assert not re.search(r"graph|lower bound|lower end|optimistic|walk|pattern|kernel|state", cut.guarantee, re.I), cut.guarantee


def test_the_gap_is_not_stated_when_the_lower_end_is_not_above_zero():
    info = EnvelopeInfo(False, "time limit", 0.0, 12.0, 3, 10, 5, 6, 9, 0, False, None, 4, 0.0, 0.0, None)
    assert certificate_gap(info) is None and "No gap can be stated" in certificate_text(info)


def test_a_net_that_stops_before_any_plan_exists_is_an_error_that_says_so(coarse):
    target, prices, _ = coarse
    with pytest.raises(PlanError, match="before any policy that can be executed was found"):
        make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", net=Net(seconds=0.0), with_risk=False)  # the time net ends the first plan's chain at the start (#826: a state net waits for the first round, and by then the first plan exists)


def test_a_time_budget_never_makes_the_envelope_search_answer_by_the_ladder_of_coarse_levels():
    target = load_target(R12, DATA)
    plan = make_plan(DATA, target, price_file(), solver="envelope", budget=0.0, with_risk=False)
    assert plan.approximation is None and plan.packed.info["envelope"].exact  # R12's first plan is proved the cheapest in its first round, whatever the budget


def test_an_unknown_solver_is_still_refused():
    with pytest.raises(ValueError, match="solver must be one of auto, object, packed, envelope"):
        make_plan(DATA, load_target(R12, DATA), price_file(), solver="fast")


def test_a_target_the_bound_cannot_be_built_for_is_a_plan_error(monkeypatch):
    from crafting_system.actions import OutOfScopeError
    from crafting_system.planner import _envelope_plan

    def refuse(*_args, **_kwargs):
        raise OutOfScopeError("a goal with a roll limit has no members")

    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", refuse)
    with pytest.raises(PlanError, match="the envelope search cannot answer this target: a goal with a roll limit"):
        make_plan(DATA, load_target(R12, DATA), price_file(), solver="envelope", with_risk=False)


def test_a_bound_that_falls_is_a_plan_error_not_a_silent_answer(monkeypatch):
    from crafting_system.planner import _plan
    from crafting_system.planner._envelope_plan import BoundError

    def refuse(*_args, **_kwargs):
        raise BoundError("the lower bound fell by 3.00% from one round of the search to the next")

    monkeypatch.setattr(_plan, "envelope_result", refuse)
    with pytest.raises(PlanError, match="the envelope search cannot answer this target: the lower bound fell"):
        make_plan(DATA, load_target(R12, DATA), price_file(), solver="envelope", with_risk=False)
