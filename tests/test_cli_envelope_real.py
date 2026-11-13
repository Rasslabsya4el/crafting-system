"""The envelope search on real routes (ticket #377, ADR-0063 point 4, OR-12): the full walk's plan and mean, from a smaller expansion.

R05 and R13 are planned twice on the real 3.29.3.3 dump at the committed prices: `solver="packed"` (the full walk, every state) and `solver="envelope"`
(the walk-free bound of #497 and the search of `planner/_envelope.py`). The two give the same mean to 1e-9, the same action at every state the envelope's plan
reaches, and the envelope's plan reaches no state it has not expanded. R13's bound is its exact cost (100%), so the search expands 191 of 2,887 states.
R04 and R14 are compared in heavy runs (`.github/scripts/envelope_routes.py`; the numbers are in the pull request).

The control: R13's bound is raised above the exact cost at some keys and the same comparison fails, so a wrong cut cannot pass.

Needs the cached dump; skips cleanly without it (CI fetches it, ticket #165). Nothing here asserts a time (ADR-0014).
"""

import dataclasses
import sys
from html import escape
from pathlib import Path

import numpy as np
import pytest
from abstraction_support import real_game_data

from crafting_system.cli import make_plan

from crafting_system.planner import _plan
from crafting_system.planner._envelope import Net
from crafting_system.planner._plan import add_risk
from crafting_system.planner._envelope_plan import BoundError, certificate_gap, envelope_result, route_incumbent
from crafting_system.planner._limits import SHOWN_LABELS, SOLVE, limit_text
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.cli._route import load_route
from crafting_system.planner._pattern_bound import pattern_lower_bound
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
ROUTES = {"R05": "r05-strength-ring", "R13": "r13-life-resist-belt"}
TARGET_R13 = ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml"
TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=list(ROUTES))
def both(request, data):
    """(route id, full walk, envelope plan) of one route."""
    target = load_target(ROOT / "examples" / "targets" / f"{ROUTES[request.param]}.yaml", data)
    prices = load_price_file(PRICES)
    return (
        request.param,
        make_plan(data, target, prices, solver="packed", with_risk=False),
        make_plan(data, target, prices, solver="envelope", with_risk=False),
    )


def test_the_envelope_plan_has_the_full_walks_mean(both):
    _, full, envelope = both
    assert envelope.mean_remaining == pytest.approx(full.mean_remaining, rel=TOLERANCE)
    assert envelope.start == full.start


def test_the_envelope_plan_takes_the_full_walks_action_at_every_state_it_reaches(both):
    _, full, envelope = both
    assert len(envelope.policy) > 1
    for state, action in envelope.policy.items():
        assert state in full.policy, "the envelope plan reaches a state the full plan does not"
        assert action.label == full.policy[state].label
        assert envelope.solution.values[state] == pytest.approx(full.solution.values[state], rel=TOLERANCE)


def test_the_envelope_expands_fewer_states_than_the_walk_and_says_which_cut_ran(both):
    route, full, envelope = both
    info = envelope.packed.info["envelope"]
    assert info.exact and info.stopped is None and info.keys_missing == 0
    assert info.lower <= full.mean_remaining * (1 + 1e-9)
    assert info.lower == pytest.approx(full.mean_remaining, rel=1e-6)  # LB = UB: the mean is pinned
    assert info.expanded < len(full.solution.values)
    if route == "R13":  # its bound is its exact cost: the search looks at the policy and little else
        assert info.expanded <= len(full.solution.values) // 10
    assert any(limit.what.startswith("The search expanded only what could matter") for limit in envelope.limits)


@pytest.fixture(scope="module")
def stopped(data, both):
    """(route id, the full walk's exact mean, the plan of a search that a state net stopped).

    R05 needs no help: its search does not close before the net (60 states known: two rounds). R13's start is bought, so a restart exists, but restarting at every tip never reaches the goal: until the
    search has closed a chain to it, U is infinite and a stop is an error (#582). So it is given the guide's completed route as the
    first executable policy, and the net stops it after the first round.
    """
    route, full, _ = both
    target = load_target(ROOT / "examples" / "targets" / f"{ROUTES[route]}.yaml", data)
    prices = load_price_file(PRICES)
    options = {"net": Net(states=1)}
    if route == "R13":
        unsolved = make_plan(data, target, prices, solve_it=False)
        options["incumbent"] = route_incumbent(load_route(ROOT / "examples" / "routes" / "r13-life-resist-belt.yaml", unsolved, data), data)
    else:
        options["net"] = Net(states=60)  # 5 stops after one expansion: with the offers' floors the first offers it builds reach no goal, so no plan exists yet (#626)
    return route, full.mean_remaining, make_plan(data, target, prices, solver="envelope", with_risk=False, **options)


def test_the_route_page_of_a_stopped_search_shows_the_same_certificate(stopped, data):
    _, _, stopped_plan = stopped
    plan = add_risk(stopped_plan)  # the page shows the percentiles, which the fixture left out
    (cut,) = [limit for limit in plan.limits if limit.kind == SOLVE and limit.what.startswith("The search was stopped")]
    page = render_page(Page("x", (build_section(route_input(plan), data),)))
    assert escape(limit_text(cut, SHOWN_LABELS)) in page


def test_a_stopped_search_on_a_real_route_certifies_the_exact_cost_between_its_bounds(stopped):
    """#499: LB <= the exact value <= U; the gap is printed with them, next to the plan's own mean, and names the bound and what it bounds."""
    route, exact, plan = stopped
    info = plan.packed.info["envelope"]
    assert not info.exact and info.stopped and info.keys_missing == 0
    assert info.lower <= exact * (1 + 1e-9) <= info.upper * (1 + 1e-9)
    assert plan.mean_remaining == info.upper  # the plan and its mean stay the answer
    (cut,) = [limit for limit in plan.limits if limit.kind == SOLVE and limit.what.startswith("The search was stopped")]
    text = limit_text(cut)
    gap = certificate_gap(info)
    assert gap is not None and gap == pytest.approx(info.upper / info.lower - 1.0) and gap > 0.0
    assert f"[{info.lower:,.2f}, {info.upper:,.2f}]" in text and f"{gap:.2%}" in text
    assert "including the ones the search did not look at" in text
    print(f"{route}: exact {exact:,.4f}, certificate [{info.lower:,.4f}, {info.upper:,.4f}], gap {gap:.4%}")  # visible with -s


def test_a_bound_raised_above_the_exact_cost_at_some_keys_is_caught(data, monkeypatch):
    """The control on a real route: the comparison that every run above passes fails for a wrong bound (one key in four raised tenfold)."""
    if str(ROOT / "research" / "312") not in sys.path:
        sys.path.append(str(ROOT / "research" / "312"))
    import exact_classes as E

    with pytest.MonkeyPatch.context() as patch:  # the research model reads its own price file; both sides are priced from the same one (#838)
        patch.setattr(E, "PRICES", PRICES)
        _, _, _, abstraction, start, priced, _ = E.build_model(TARGET_R13, "twins", True, False)
    bound = pattern_lower_bound(abstraction, start, priced)
    monkeypatch.setattr(_plan, "unopened_listing", lambda data, start: None)  # the research model starts from the item with no mods: the plan without the draw of a bought item's mods (ADR-0064)
    exact = make_plan(data, load_target(TARGET_R13, data), load_price_file(PRICES), solver="packed", with_risk=False).mean_remaining
    sound = envelope_result(abstraction, start, priced, bound=bound)
    assert sound.solution.values[start] == pytest.approx(exact, rel=TOLERANCE)
    factor = 1.0 + 9.0 * (np.arange(len(bound.value)) % 4 == 0)  # one key in four; the keys moved by one when R13's Normal start state went (#576): `== 1` raised none the search looks at
    wrong = dataclasses.replace(bound, value=bound.value * factor)
    with pytest.raises(BoundError, match="lower bound"):  # the guard sees this bound is not consistent as the search looks further ...
        envelope_result(abstraction, start, priced, bound=wrong)
    planted = envelope_result(abstraction, start, priced, bound=wrong, guard=False)  # ... and with the guard off the comparison with the full walk is what catches it
    assert abs(planted.solution.values[start] - exact) > 1e-3 * exact, "the planted bound did not change the answer: the comparison cannot fail"
    assert planted.info["envelope"].lower > exact  # and the bound it reports is above the exact cost, which no sound bound is
