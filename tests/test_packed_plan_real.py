"""The packed solver against the object solver on real routes (ticket #374, ADR-0063 point 1).

ADR-0063's acceptance: "the packed solve is cross-checked against the object solver on R05, R08, R10, R12 and R13 to 1e-9
relative". R13, R12, R10 and R05 are checked here, each planned twice on the real 3.29.3.3 dump at the committed prices:
`solver="object"` (the production plan: bound pruning, the object solver) and `solver="packed"` (every offer after the twins
are merged, walked into arrays, merged exactly, solved by policy iteration, certified). R08 takes minutes per plan and is
cross-checked in a heavy run (`.github/scripts/packed_routes.py check --route r08`, result in the pull request).
R04, R14 and S02 are in `test_packed_heavy.py`.

These tests need the cached dump and skip cleanly without it.
"""

from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import _packed, make_plan
from crafting_system.cli._packed import PackedPolicy
from crafting_system.cli._reach import policy_states
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
ROUTES = {
    "R13": "r13-life-resist-belt",
    "R12": "r12-lightning-amulet",
    "R10": "r10-fractured-boots",
    "R05": "r05-strength-ring",
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=list(ROUTES))
def both(request, data):
    """(route id, object plan, packed plan) of one route."""
    target = load_target(ROOT / "examples" / "targets" / f"{ROUTES[request.param]}.yaml", data)
    prices = load_price_file(PRICES)
    return (
        request.param,
        make_plan(data, target, prices, solver="object"),
        make_plan(data, target, prices, solver="packed"),
    )


def test_the_packed_mean_cost_equals_the_object_solvers_to_1e_9(both):
    _, reference, packed = both

    assert packed.mean_remaining == pytest.approx(reference.mean_remaining, rel=1e-9)


def test_the_packed_values_carry_a_certified_error_bound(both):
    _, _, packed = both

    assert packed.solution.error_bound < 1e-6
    assert isinstance(packed.policy, PackedPolicy)


def test_the_packed_policy_reaches_the_goal_and_is_greedy_on_its_own_values(both):
    _, _, packed = both

    reached = policy_states(packed.start, packed.policy, packed.is_goal)
    assert packed.start in reached
    for state in reached:
        if packed.is_goal(state):
            continue
        action = packed.policy[state]
        assert action.cost > 0 and action.outcomes
        total = sum(outcome.weight for outcome in action.outcomes)
        stay = sum(outcome.weight for outcome in action.outcomes if outcome.state == state)
        leave = total - stay
        value = (
            action.cost * total
            + sum(outcome.weight * packed.solution.values[outcome.state] for outcome in action.outcomes if outcome.state != state)
        ) / leave
        assert value == pytest.approx(packed.solution.values[state], rel=1e-8)


def test_the_risk_on_the_merged_chain_agrees_with_the_mean(both):
    _, reference, packed = both

    assert packed.risk is not None
    assert packed.risk.success_probability.value == pytest.approx(1.0)
    assert packed.risk.mean.value == pytest.approx(reference.mean_remaining, rel=1e-6)
    assert packed.risk.p50.value <= packed.risk.p90.value


def test_a_graph_over_the_limit_is_solved_packed_and_a_small_one_by_the_object_solver(data, monkeypatch):
    target = load_target(ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml", data)
    prices = load_price_file(PRICES)

    small = make_plan(data, target, prices)  # "auto": 35,726 transitions is under the limit
    assert not isinstance(small.policy, PackedPolicy)

    monkeypatch.setattr(_packed, "OBJECT_SOLVER_EDGES", 1_000)
    big = make_plan(data, target, prices)  # the same graph, now over the limit

    assert isinstance(big.policy, PackedPolicy)
    assert big.mean_remaining == pytest.approx(small.mean_remaining, rel=1e-9)


def test_an_unknown_solver_is_refused(data):
    target = load_target(ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml", data)

    with pytest.raises(ValueError, match="solver must be one of"):
        make_plan(data, target, load_price_file(PRICES), solver="gpu")
