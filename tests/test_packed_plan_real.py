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
from limits_support import notes, only

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


def test_every_policy_evaluated_by_bicgstab_gives_the_values_of_the_dense_solve_with_a_true_residual_that_small(both, data, monkeypatch):
    """#584: R13 and R05 with `dense_limit` lowered to 0 (their merged policies have 13 states or fewer), so that BiCGSTAB runs on every evaluation: the values are the dense solve's, and the residual the solver reports is the true one."""
    route, _, dense = both
    if route not in ("R13", "R05"):
        pytest.skip("R13 and R05 are the routes of the ticket")
    infos = []
    real = _packed.solve_packed

    def lowered(graph, **keywords):
        solved = real(graph, dense_limit=0, **keywords)
        infos.append(solved.info)
        return solved

    monkeypatch.setattr(_packed, "solve_packed", lowered)
    target = load_target(ROOT / "examples" / "targets" / f"{ROUTES[route]}.yaml", data)

    iterated = make_plan(data, target, load_price_file(PRICES), solver="packed")

    iterated_infos = [info for info in infos if info.get("linear_iterations", 0) > 0]
    assert iterated_infos or route == "R05"  # BiCGSTAB did run (R05's policy is one state that the start already solves, with no step of its own)
    assert all(info["linear_residual"] <= 1e-10 for info in iterated_infos)  # the true relative residual of the last evaluation of each solve
    assert iterated.mean_remaining == pytest.approx(dense.mean_remaining, rel=1e-9)
    assert all(iterated.solution.values[state] == pytest.approx(value, rel=1e-8) for state, value in dense.solution.values.items())


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


def test_a_long_chain_gets_its_moments_from_the_packed_solve_with_the_same_numbers(data, monkeypatch):
    from crafting_system.risk import _moments

    target = load_target(ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml", data)
    prices = load_price_file(PRICES)
    reference = make_plan(data, target, prices, solver="object")

    monkeypatch.setattr(_moments, "PACKED_FROM_EDGES", 0)
    again = make_plan(data, target, prices, solver="object")

    assert again.risk.mean.value == pytest.approx(reference.risk.mean.value, rel=1e-9)
    assert again.risk.variance.value == pytest.approx(reference.risk.variance.value, rel=1e-7)
    assert again.risk.p50.value == pytest.approx(reference.risk.p50.value, rel=1e-9)
    assert again.risk.p90.value == pytest.approx(reference.risk.p90.value, rel=1e-9)


def test_a_merged_chain_too_long_for_the_quantile_dp_keeps_exact_moments_and_says_so(data, monkeypatch):
    import math

    from crafting_system.cli import _plan

    target = load_target(ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml", data)
    prices = load_price_file(PRICES)
    reference = make_plan(data, target, prices, solver="packed")

    monkeypatch.setattr(_plan, "RISK_QUANTILE_TRANSITIONS", 0)
    cut = make_plan(data, target, prices, solver="packed")

    assert cut.risk.success_probability.value == 1.0
    assert cut.risk.mean.value == pytest.approx(reference.risk.mean.value, rel=1e-12)
    assert cut.risk.variance.value == pytest.approx(reference.risk.variance.value, rel=1e-12)
    assert math.isinf(cut.risk.p90.value) and math.isinf(cut.risk.cvar.value)
    assert only(cut.limits, "risk").what == "Not computed: the median cost, the cost 9 runs in 10 stay under, and the average of the worst tenth" and notes(reference.limits) == []  # G19


@pytest.fixture(scope="module")
def reads(both, data):
    """(route id, the given route read on the object plan, the same route read on the packed plan): each read once, the object one of R13 takes about 10 minutes (#622)."""
    from crafting_system.cli import evaluate_route, load_route

    route_id, reference, packed = both
    route_path = ROOT / "examples" / "routes" / f"{ROUTES[route_id]}.yaml"
    return (
        route_id,
        evaluate_route(reference, load_route(route_path, reference, data), data),
        evaluate_route(packed, load_route(route_path, packed, data), data),
    )


def test_a_given_routes_p90_read_on_the_packed_graph_equals_the_object_evaluation(reads, request):
    """Ticket #70, the percentile half of the test below. R13 fails it since the Magic start of #576 (PR #607): see #622."""
    route_id, by_object, by_graph = reads
    if route_id == "R13":
        request.applymarker(
            pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="#622: the object read of R13's given route leaves p90 unresolved (infinite) where the packed read gives about 28,429; it fails loudly the day #622 is fixed, delete this mark then",
            )
        )

    assert len(by_graph.gaps) == len(by_object.gaps)
    if by_object.gaps:
        pytest.skip("a route with a gap never finishes with certainty: it has no p90 to compare")
    assert by_graph.risk.p90.value == pytest.approx(by_object.risk.p90.value, rel=1e-6)


def test_a_given_route_read_on_the_packed_graph_equals_the_object_evaluation(reads):
    """Ticket #70: `evaluate_route` on a packed plan reads the route in the walked graph; same mean, gaps and first divergence."""
    _, by_object, by_graph = reads

    assert by_graph.risk.success_probability.value == pytest.approx(by_object.risk.success_probability.value, abs=1e-9)
    assert len(by_graph.gaps) == len(by_object.gaps)
    if not by_object.gaps:
        assert by_graph.risk.mean.value == pytest.approx(by_object.risk.mean.value, rel=1e-6)
    assert (by_graph.divergence is None) == (by_object.divergence is None)
    if by_object.divergence is not None:
        assert by_graph.divergence.route_action == by_object.divergence.route_action
        assert by_graph.divergence.solver_action == by_object.divergence.solver_action
    assert len(by_graph.divergences) == len(by_object.divergences)  # every divergence, not only the first (ticket #554)
    assert {(d.state, d.solver_action, d.route_action) for d in by_graph.divergences} == {
        (d.state, d.solver_action, d.route_action) for d in by_object.divergences
    }


def test_the_divergences_of_a_given_route_read_on_the_packed_graph_have_the_chances_of_the_object_evaluation(both, reads, data):
    """Ticket #554: the divergence lines of `benchmark` (every state where the guide and the planner part, each with its chance under both policies) are the same on a packed plan."""
    from crafting_system.cli._benchmark_divergence import divergences_of

    _, reference, packed = both
    _, object_result, graph_result = reads

    by_object = divergences_of(reference, object_result, data)
    by_graph = divergences_of(packed, graph_result, data)

    assert by_graph["count"] == by_object["count"]
    rows = lambda block: {row["description"]: row for row in block["shown"]}  # noqa: E731
    assert set(rows(by_graph)) == set(rows(by_object))
    for description, row in rows(by_object).items():
        for field in ("planner_chance", "route_chance"):
            found = rows(by_graph)[description][field]
            assert (found is None) == (row[field] is None)
            if found is not None:
                assert found == pytest.approx(row[field], abs=1e-6)
