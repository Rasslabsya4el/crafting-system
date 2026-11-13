"""The guard of the envelope search (ticket #539, OR-12, OR-13): a bound that is the cause is refused as a `BoundError`, whichever way it would have failed.

A lower bound raised above the exact value is not a lower bound, and the search would cut on it. Before this ticket the only guard was a check of the
whole run at its end (the bound must not fall from one round to the next), so a bound that made the lower graph unsolvable ended in a
`ConvergenceError` ("the policy is improper: its linear system is singular") before the guard spoke; on R13, 3 of 4 planted bounds did (the fourth was refused,
the real routes are `tests/test_cli_envelope_real.py`). Now the search checks the bound where it can see a fault, as it goes:

* at each state it expands, the bound of the state must not be above the least bound of the actions there (a consistent bound solves the model's own equation,
  so the state's bound is at most the cheapest of its actions' backups); the planted bound breaks this at the keys it raises;
* after each round, `L(root)` must not have fallen (a consistent bound only rises);
* a `ConvergenceError` of a sound bound is not the bound's doing and is left as it is: a free action (cost 0) and a cost ratio of 1e14 between the cheapest
  action and the values give "certifies only a relative bound" on a perfect bound, and an improper policy of a sound bound stays an improper policy.

The synthetic graphs are those of `tests/test_cli_envelope.py`.
"""

import pytest
from envelope_support import ExplicitProblem, dense_optimum, random_graph

from crafting_system.planner import _envelope
from crafting_system.planner._envelope import FALL_LIMIT, Search
from crafting_system.planner._envelope_plan import BoundError
from crafting_system.solver._certify import ConvergenceError

SEEDS = range(12)
SIZE = 60


def problem(seed: int, alpha: float = 1.0, planted: float = 0.0):
    graph = random_graph(seed, SIZE)
    value, _ = dense_optimum(graph)
    return graph, value, ExplicitProblem(graph, value, alpha, planted)


def test_a_planted_bound_never_ends_in_a_wrong_answer_or_a_convergence_error():
    refused = 0
    for seed in SEEDS:
        graph, value, planted = problem(seed, 1.0, planted=1.5)
        try:
            result = Search(planted).run()
        except BoundError:
            refused += 1
            continue
        assert result.stats.largest_fall <= FALL_LIMIT  # a run the guard let through saw no fall ...
        assert result.lower <= value[0] * (1 + 1e-9)  # ... and its bound is not above the optimum
    assert refused >= 6, refused  # the same runs that fall without the guard (`test_cli_envelope.py`)


def test_a_state_whose_bound_is_above_all_its_actions_is_refused_where_it_is_expanded():
    graph, value, sound = problem(3)

    class Raised(ExplicitProblem):
        def lower(self, state):
            return super().lower(state) * (4.0 if state == 0 else 1.0)

    search = Search(Raised(graph, value, 1.0))
    with pytest.raises(BoundError, match="not consistent"):
        search.run()
    assert search.stats.rounds <= 1  # no solve was needed to see it


def test_a_convergence_error_on_a_graph_whose_tips_are_not_consistent_is_a_bound_error(monkeypatch):
    """The root is consistent, so nothing is refused when it is expanded; the tips it reaches are raised, and the solve of their graph fails: the tips are looked at."""
    graph, value, _ = problem(5)

    class RaisedTips(ExplicitProblem):
        def lower(self, state):
            return super().lower(state) * (1.0 if state == 0 else 4.0)

    real = _envelope.solve_graph
    calls = []

    def fail_on_the_second(graph, **kwargs):
        calls.append(graph.n)
        if len(calls) == 2:
            raise ConvergenceError("the policy is improper: its linear system is singular", float("inf"))
        return real(graph, **kwargs)

    monkeypatch.setattr(_envelope, "solve_graph", fail_on_the_second)
    with pytest.raises(BoundError, match="not consistent") as refused:
        Search(RaisedTips(graph, value, 1.0)).run()
    assert isinstance(refused.value.__context__, ConvergenceError) and len(calls) == 2  # the failure it was raised from is kept


def test_a_bound_that_falls_is_refused_at_the_round_it_falls():
    """A bound that is consistent state by state but above the exact cost (each state's bound and its offers' scaled together, as a wrong declared block
    invariance would do) breaks only when the exact action replaces the fake one: the root's bound then falls."""

    class Scaled(ExplicitProblem):
        def _scale(self, state):
            return 1.0 + 0.8 * ((state * 31) % 7) / 7.0

        def lower(self, state):
            return super().lower(state) * self._scale(state)

        def candidates(self, state):
            return [(la * self._scale(state), offer) for la, offer in super().candidates(state)]

    refused = 0
    for seed in SEEDS:
        graph, value, _ = problem(seed)
        search = Search(Scaled(graph, value, 1.0))
        try:
            search.run()
        except BoundError as error:
            assert "fell" in str(error) and "consistent bound never does" in str(error)
            assert search.stats.largest_fall > FALL_LIMIT
            refused += 1
    assert refused >= 3, refused


def test_the_guard_can_be_turned_off_for_the_tests_that_plant_a_bound():
    _, _, planted = problem(2, 1.0, planted=1.5)
    result = Search(planted, guard=False).run()
    assert result.exact


def test_a_sound_bound_is_never_refused():
    for seed in SEEDS:
        for alpha in (1.0, 0.5, 0.0):
            _, value, sound = problem(seed, alpha)
            result = Search(sound).run()
            assert result.stats.largest_fall <= 1e-9 and result.lower <= value[0] * (1 + 1e-9)


def test_an_improper_policy_of_a_sound_bound_stays_a_convergence_error(monkeypatch):
    _, _, sound = problem(4)
    calls = []
    real = _envelope.solve_graph

    def fail_on_the_third(graph, **kwargs):
        calls.append(graph.n)
        if len(calls) == 3:
            raise ConvergenceError("the policy is improper: its linear system is singular", float("inf"))
        return real(graph, **kwargs)

    monkeypatch.setattr(_envelope, "solve_graph", fail_on_the_third)
    with pytest.raises(ConvergenceError, match="improper") as caught:
        Search(sound).run()
    assert not isinstance(caught.value, BoundError) and len(calls) == 3


def free_cycle(graph) -> bool:
    """Whether offer 3 alone can keep a run away from the goals forever: a set of states that all have it and that its outcomes never leave."""
    closed = {s for s in range(graph.n) if s not in graph.goal and 3 in graph.actions[s]}
    while True:
        kept = {s for s in closed if all(t in closed for t in graph.actions[s][3])}
        if kept == closed:
            return bool(closed)
        closed = kept


def test_a_free_action_is_certified_and_only_a_free_cycle_is_a_convergence_error_not_a_bound_error():
    """An action of cost exactly 0. The certificate measures a state's error against the cost ahead as well as its own (#769), so a free action certifies
    when a paid step lies ahead of it. Where the free action can keep a run from the goals forever (here a free self-loop), that run costs 0 and no
    residual can bound the values from below: a `ConvergenceError` (a limit of the solver, not of the bound), never a `BoundError`."""
    certified = failed = 0
    for seed in SEEDS:
        graph = random_graph(seed, SIZE)
        graph.costs[3] = 0.0
        value, _ = dense_optimum(graph)
        try:
            Search(ExplicitProblem(graph, value, 1.0)).run()
            certified += 1
        except ConvergenceError as error:
            assert not isinstance(error, BoundError) and "certifies only" in str(error)
            assert free_cycle(graph), seed
            failed += 1
    assert certified >= 6 and failed >= 1, (certified, failed)  # before #769 none certified: the free state's own cost was 0


def test_a_cost_ratio_of_1e14_between_the_cheapest_action_and_the_values_is_a_convergence_error_not_a_bound_error():
    graph = random_graph(34, SIZE)
    graph.costs = [cost * (1e-7 if offer % 2 else 1e7) / 6 for offer, cost in enumerate(graph.costs)]
    value, _ = dense_optimum(graph)
    with pytest.raises(ConvergenceError, match="certifies only a relative bound"):
        Search(ExplicitProblem(graph, value, 1.0)).run()
