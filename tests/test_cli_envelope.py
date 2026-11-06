"""The envelope search on random graphs (ticket #377, OR-12, OR-13): the exact optimum, a smaller expansion for a strong bound, and a control that fails.

The search (`cli/_envelope.py`) is generic, so it is tested on random stochastic shortest path graphs with cycles and a restart
(`tests/envelope_support.py`), where the optimum is known by a dense solve that shares no code with it:

* with a lower bound `alpha * V*` (and `alpha * Q*` for every offer) for `alpha` from 1 (perfect) to 0 (no information), the mean the search ends
  with is the dense optimum, and the plan it names is an optimal action at every state it reaches;
* the strong bound expands fewer states than the full graph reaches and builds fewer kernels than there are (state, offer) pairs; the weak bound
  expands at least as many and still ends exact;
* the control: a lower bound raised above the exact value at some offers (`planted`) makes the search end on a plan that costs more than the optimum, and the same check
  that passes for `alpha <= 1` catches it. A test of the cut that no wrong cut could fail would prove nothing;
* the bound it reports, `lower`, never passes the exact value and does not fall from round to round; a net ends the search with the best plan it can
  execute and says it is not exact; a given start item has no restart to fall back on, and then a net ends it with an error that says so.

The crafting problem on a real route (the plan and the mean against the full walk) is `tests/test_cli_envelope_real.py`.
"""

import math

import numpy as np
import pytest
from envelope_support import ExplicitProblem, dense_optimum, q_value, random_graph

from crafting_system.cli._envelope import Net, NoPolicy, Search, resident_mb
from crafting_system.solver import policy_reach, solve_packed

SEEDS = range(12)
SIZE = 60
TOLERANCE = 1e-8


def run(seed: int, alpha: float, planted: float = 0.0, **options):
    graph = random_graph(seed, SIZE)
    value, _ = dense_optimum(graph)
    problem = ExplicitProblem(graph, value, alpha, planted)
    search = Search(problem, **options)
    return graph, value, problem, search.run()


def answer(result):
    """The mean the graph the search ended with is solved to, and the offer it takes at each state its policy reaches."""
    solved = solve_packed(result.graph, merge=False)
    reach = policy_reach(result.graph, solved.action, 0)
    plan = {result.states[i]: int(result.graph.act_tag[solved.action[i]]) for i in reach.tolist() if solved.action[i] >= 0}
    return float(solved.value[0]), plan


def check_exact(graph, value, result) -> None:
    """The ends of the search are the dense optimum: the mean, and an optimal offer at every state the plan reaches."""
    assert result.exact
    mean, plan = answer(result)
    assert mean == pytest.approx(value[0], rel=TOLERANCE)
    for state, offer in plan.items():
        assert q_value(graph, value, state, offer) <= value[state] * (1 + TOLERANCE), (state, offer)
    assert result.lower <= value[0] * (1 + 1e-12)
    assert result.lower == pytest.approx(value[0], rel=1e-6)  # pinned: LB = UB


@pytest.mark.parametrize("alpha", [1.0, 0.98, 0.7, 0.3, 0.0])
@pytest.mark.parametrize("seed", SEEDS)
def test_the_search_returns_the_exact_optimum(seed, alpha):
    graph, value, problem, result = run(seed, alpha)
    check_exact(graph, value, result)
    history = result.stats.lower_history
    assert all(a <= b * (1 + 1e-9) + 1e-12 for a, b in zip(history, history[1:])), history  # a consistent bound only rises
    assert history[-1] <= value[0] * (1 + 1e-9)


def test_a_strong_bound_expands_fewer_states_than_the_full_graph():
    expanded = realized = reachable = pairs = 0
    for seed in SEEDS:
        graph, value, problem, result = run(seed, 0.99)
        check_exact(graph, value, result)
        full = graph.reachable()
        assert result.stats.expanded <= len(full)
        expanded += result.stats.expanded
        reachable += len(full)
        realized += result.stats.realized
        pairs += sum(len(graph.actions[s]) for s in full)
        assert len(set(problem.asked)) == len(problem.asked)  # a kernel is built once per (state, offer)
    assert expanded < 0.75 * reachable, (expanded, reachable)
    assert realized < 0.6 * pairs, (realized, pairs)


def test_a_weak_bound_expands_more_and_is_still_exact():
    strong = weak = 0
    for seed in SEEDS:
        graph, value, _, near = run(seed, 0.99)
        _, _, _, far = run(seed, 0.05)
        check_exact(graph, value, far)
        strong += near.stats.expanded
        weak += far.stats.expanded
        assert far.stats.expanded <= len(graph.reachable())
    assert weak > strong


def test_no_information_at_all_still_ends_on_the_optimum():
    for seed in SEEDS:
        graph, value, _, result = run(seed, 0.0)
        check_exact(graph, value, result)


def test_a_lower_bound_above_the_exact_value_is_caught():
    """The control: the check that every run above passes fails when the bound is planted above the exact value."""
    wrong = 0
    for seed in SEEDS:
        graph, value, _, result = run(seed, 1.0, planted=1.5)
        try:
            check_exact(graph, value, result)
        except AssertionError:
            wrong += 1
    assert wrong >= 3, wrong  # the cut believes a state costs more than it does, and ends on a dearer plan or a lower bound above the optimum


def test_a_lower_bound_a_little_above_the_exact_value_is_caught_too():
    wrong = sum(_fails(seed, 1.0, 0.3) for seed in SEEDS)
    assert wrong >= 1, wrong


def _fails(seed: int, alpha: float, planted: float) -> bool:
    graph, value, _, result = run(seed, alpha, planted)
    try:
        check_exact(graph, value, result)
    except AssertionError:
        return True
    return False


def test_an_incumbent_gives_an_upper_bound_from_the_first_round_and_changes_nothing():
    for seed in SEEDS:
        graph = random_graph(seed, SIZE)
        value, _ = dense_optimum(graph)
        result = Search(ExplicitProblem(graph, value, 0.9), incumbent=lambda s, g=graph: [g.mover[s]]).run()
        check_exact(graph, value, result)
        first = result.stats.first_upper
        assert first is not None
        assert first >= value[0] * (1 - 1e-9)  # the policy of the incumbent (with a restart at every tip) can be executed: it costs no less than the optimum


def test_a_net_ends_the_search_on_an_executable_plan_and_says_it_is_not_exact():
    stopped = refused = 0
    for seed in SEEDS:
        graph = random_graph(seed, SIZE)
        value, _ = dense_optimum(graph)
        try:
            result = Search(ExplicitProblem(graph, value, 0.5), net=Net(states=20)).run()
        except NoPolicy as error:  # stopped before any policy that can be executed closed: no plan, and the error says why
            assert "limit is 20" in str(error)
            refused += 1
            continue
        if result.exact:
            continue
        stopped += 1
        assert result.stopped and "limit is 20" in result.stopped
        mean, _ = answer(result)
        assert math.isfinite(mean)
        assert result.lower <= value[0] * (1 + 1e-9)
        assert mean >= value[0] * (1 - 1e-9)  # a policy that can be executed costs at least the optimum
    assert stopped >= 3, (stopped, refused)


def test_a_given_start_item_has_no_restart_so_a_stopped_search_says_there_is_no_plan():
    graph = random_graph(3, SIZE)
    value, _ = dense_optimum(graph)
    problem = ExplicitProblem(graph, value, 0.5, restart=None)
    with pytest.raises(NoPolicy, match="no restart"):
        Search(problem, net=Net(states=8)).run()


def test_a_net_of_seconds_and_of_memory_stops_between_rounds():
    graph = random_graph(5, SIZE)
    value, _ = dense_optimum(graph)
    with pytest.raises(NoPolicy, match="time limit of 0 seconds"):  # stopped after the first round, before the start was looked at
        Search(ExplicitProblem(graph, value, 0.5), net=Net(seconds=0.0)).run()
    if resident_mb() is None:
        pytest.skip("the memory of this process cannot be read here, so the memory net is silent")
    with pytest.raises(NoPolicy, match="MB"):
        Search(ExplicitProblem(graph, value, 0.5), net=Net(memory_mb=0.001)).run()


def test_a_goal_at_the_start_is_solved_at_once():
    graph = random_graph(1, SIZE)
    value, _ = dense_optimum(graph)
    graph.goal.add(0)
    problem = ExplicitProblem(graph, np.zeros_like(value), 1.0)
    result = Search(problem).run()
    assert result.exact and result.stats.expanded == 0 and answer(result)[0] == 0.0
