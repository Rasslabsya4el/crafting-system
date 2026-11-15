"""The certificate of the packed solve on a plan of very many steps (ticket #867, causes 2 and 3), and what a search with a gap does with it.

The certificate divides each state's residual by the cost of a step, so its bound is the error of a value times the steps the plan takes
(`V / g`). Two things then refuse a plan whose values are right:

* *The evaluation's own error* (cause 2). A linear solve leaves about 1e-13 of the value; on a plan worth 10^7 steps that is 1e-6. `corrected`
  takes the residual of the policy's equation with every sum rounded once and adds the correction it gives: the residual falls to the rounding
  of the values. (The family's `basic-orbs/medium`: a lower graph of 73,390 states worth 7e6 steps, 4.0e-6 before, 9.6e-10 with two corrections.)
* *Float64 itself* (cause 3). A value is stored to `eps V`, so a plan of more than about 10^9 steps cannot be certified to 1e-6 by any solver
  in float64. A search that stops at a gap takes each figure with its certified error, so it needs that error only small next to the gap:
  `refuse_above` moves the refusal, the certificate stays the same and stays sound. (The family's `growing-3-fossils/large`: a first plan of
  1.09e8 Chaos over steps of 0.008; `start-vendor-recipe/large`: a bound of 4.3e9 over steps of 0.0023.)

LONG: state 0 pays 1 and reaches the goal (2) with weight 1 of `N = 2^32`, else state 1; state 1 pays 1 and goes back. `V(0) = 2 N - 1`,
`V(1) = 2 N`: 8.6e9 steps. `4 eps V = 7.6e-6` of a step.
"""

import sys

import numpy as np
import pytest
from test_envelope_gap_stop import Hand
from test_solver_packed_long_sum_certificate import TOTAL, WIDE_VALUE, build, wide

from crafting_system.planner._envelope import GAP_SHARE, BoundError, Search, figure_error
from crafting_system.solver import ConvergenceError
from crafting_system.solver._packed_solve import ACCEPT_BOUND, Work, certify, corrected, solve_graph, solve_packed

EPS = sys.float_info.epsilon
N = 2**32
LONG_VALUE = np.array([2.0 * N - 1.0, 2.0 * N, 0.0])


def long_graph():
    return build((False, [(1.0, [(2, 1), (1, N - 1)])]), (False, [(1.0, [(0, 1)])]), (True, []))


# ---- cause 2: the evaluation's error, times the steps ------------------------------------------------------------------------------------


def test_a_correction_takes_an_error_of_the_values_down_to_their_rounding():
    graph = wide()
    work = Work(graph)
    solved = np.ones(graph.n, dtype=bool)
    policy = np.where(graph.goal, -1, np.arange(graph.n) - (np.arange(graph.n) > 1))  # one action a state: state 0 has action 0, state i >= 2 action i - 1
    leave = work.shared_sums(np.ones(graph.n))
    off = WIDE_VALUE * (1.0 + 1e-12 * np.cos(np.arange(graph.n)))  # an error of 1e-12 of each value: 1.8e-6 of a step

    before = certify(graph, off, solved)
    better = corrected(work, leave, policy, off, 2000, {})
    after = certify(graph, better, solved)

    assert before.bound > ACCEPT_BOUND  # refused: the residual is 1e-12 V against a cost of 1
    assert np.max(np.abs(off[2:] / WIDE_VALUE[2:] - 1.0)) > 9e-13 and better == pytest.approx(WIDE_VALUE, rel=1e-10)
    assert after.bound < 1e-8 and after.bound == pytest.approx(4 * EPS * 2 * TOTAL, rel=1.0)  # the allowance of a sum rounded once, and little else
    assert np.all(np.abs(better[2:] / WIDE_VALUE[2:] - 1.0) <= after.bound)  # and the bound holds of the values worked by hand


def test_a_correction_is_not_made_where_its_sums_cannot_be_taken():
    graph = wide()
    work = Work(graph)
    policy = np.where(graph.goal, -1, np.arange(graph.n) - (np.arange(graph.n) > 1))
    value = WIDE_VALUE.copy()
    value[5] = np.inf

    assert corrected(work, work.shared_sums(np.ones(graph.n)), policy, value, 2000, {}) is None


# ---- cause 3: more steps than float64 can certify to 1e-6 --------------------------------------------------------------------------------


def test_a_plan_of_ten_to_the_ten_steps_is_refused_at_the_exact_bound_and_taken_with_its_error_above_it():
    with pytest.raises(ConvergenceError) as refused:
        solve_graph(long_graph())
    assert ACCEPT_BOUND < refused.value.error_bound < 1e-4  # the rounding of the values: about 4 eps V

    core = solve_graph(long_graph(), refuse_above=1e-3)

    bound = core.certificate.bound
    assert bound == refused.value.error_bound  # the same certificate: only the refusal moved
    assert core.value[0] * (1.0 - bound) <= LONG_VALUE[0] <= core.value[0] * (1.0 + bound)  # the figures a caller takes hold of the exact value
    assert core.value[1] * (1.0 - bound) <= LONG_VALUE[1] <= core.value[1] * (1.0 + bound)


def test_a_bound_above_the_refusal_is_still_refused():
    with pytest.raises(ConvergenceError):
        solve_graph(long_graph(), refuse_above=2e-6)


def test_the_error_a_search_takes_its_figures_at_is_a_share_of_its_gap_and_the_exact_one_without_a_gap():
    assert figure_error(0.01, 0.0) == GAP_SHARE * 0.01 == 1e-3
    assert figure_error(0.0, 0.0) == ACCEPT_BOUND and figure_error(0.01, None) == ACCEPT_BOUND  # the exact search
    assert figure_error(1e-6, 0.0) == ACCEPT_BOUND  # never below what an exact answer is taken at
    assert (1.0 + GAP_SHARE * 0.01) / (1.0 - GAP_SHARE * 0.01) <= 1.01  # two figures at that error leave the stop inside the gap


def long_world() -> Hand:
    # the start item is given; the bound is the exact value (a perfect bound: the first plan is the only plan)
    return Hand(
        goal={2}, costs={1: 1.0, 2: 1.0}, actions={0: {1: {2: 1, 1: N - 1}}, 1: {2: {0: 1}}, 2: {}},
        la={(0, 1): 2.0 * N - 1.0, (1, 2): 2.0 * N}, lb={0: 2.0 * N - 1.0, 1: 2.0 * N, 2: 0.0},
    )  # fmt: skip


def test_the_exact_search_refuses_a_plan_it_cannot_certify_to_the_exact_bound():
    with pytest.raises(ConvergenceError):
        Search(long_world()).run()


def test_a_search_with_a_gap_returns_that_plan_with_both_figures_around_its_exact_cost():
    result = Search(long_world(), gap=0.01, gap_after=0.0).run()

    exact = 2.0 * N - 1.0
    assert not result.exact and result.within == 0.01 and result.stopped is None  # not said to be exact: the solver's error is above 1e-6
    assert result.stats.upper_refused == 0  # the plan in hand was solved to a figure in every round
    assert result.lower <= exact <= result.upper  # hand-worked: both figures hold of the exact cost
    assert result.upper <= 1.01 * result.lower and result.upper / result.lower - 1.0 < 1e-4


# ---- the guard of the bound allows for an error above 1e-6, and for nothing else ---------------------------------------------------------
#
# ONE: the start (0) has one offer, which costs 100 and finishes (goal 9). No plan costs less than 100.


def one_offer(bound: float = 100.0) -> Hand:
    return Hand(goal={9}, costs={1: 100.0}, actions={0: {1: {9: 1}}, 9: {}}, la={(0, 1): 100.0}, lb={0: bound, 9: 0.0})


def test_a_bound_lowered_by_a_certified_error_above_the_exact_one_may_stand_that_much_above_its_offers():
    # a bound whose solve is certified to e is lowered by e, and can still be (1 + e) / (1 - e) above the least of its offers: 100.1 at e = 5e-4
    with pytest.raises(BoundError):
        Search(one_offer(100.1), gap=0.01, gap_after=0.0).run()  # no error said: the 1e-5 of a bound certified to 1e-6
    exact_error = one_offer(100.1)
    exact_error.bound_error = 1e-6
    with pytest.raises(BoundError):
        Search(exact_error, gap=0.01, gap_after=0.0).run()

    loose = one_offer(100.1)
    loose.bound_error = 5e-4
    result = Search(loose, gap=0.01, gap_after=0.0).run()  # allowed: 1e-5 + 3 * 5e-4 of the offer and as much of the root's bound, 100.30
    assert result.exact and result.lower == pytest.approx(100.0, rel=1e-9)  # the one plan, at its cost of 100

    wrong = one_offer(100.5)  # 0.5% above its only offer: no error of 5e-4 explains it
    wrong.bound_error = 5e-4
    with pytest.raises(BoundError):
        Search(wrong, gap=0.01, gap_after=0.0).run()


@pytest.mark.parametrize("certified, falls", [(5e-4, False), (1e-9, True)])
def test_a_root_that_falls_within_the_certified_errors_of_its_solves_is_no_fall_of_the_bound(monkeypatch, certified, falls):
    # every solve answers 0.03% low (99.97 for 100): inside a certified error of 5e-4, a fall of the bound when the solve is certified to 1e-9
    import dataclasses

    from crafting_system.planner import _envelope

    solve = _envelope.solve_graph

    def low(*args, **kwargs):
        core = solve(*args, **kwargs)
        return dataclasses.replace(core, value=core.value * (1.0 - 3e-4), certificate=dataclasses.replace(core.certificate, bound=certified))

    monkeypatch.setattr(_envelope, "solve_graph", low)
    search = Search(one_offer(), gap=0.01, gap_after=0.0)
    if falls:
        with pytest.raises(BoundError, match="fell"):
            search.run()
        return
    result = search.run()
    assert search.stats.largest_fall == pytest.approx(3e-4, rel=1e-6)  # the figure is still recorded as it is
    assert result.lower == pytest.approx(99.97 * (1.0 - 5e-4), rel=1e-12) and result.lower <= 100.0 <= result.upper


# ---- `refuse_above` through the callers of the solve --------------------------------------------------------------------------------------


def test_the_merged_solve_takes_the_refusal_of_its_caller_and_gives_the_error_with_the_values():
    with pytest.raises(ConvergenceError):
        solve_packed(long_graph())
    with pytest.raises(ConvergenceError):
        solve_packed(long_graph(), refuse_above=2e-6)

    solved = solve_packed(long_graph(), refuse_above=1e-3)

    assert ACCEPT_BOUND < solved.error_bound < 1e-4
    assert solved.value[0] * (1.0 - solved.error_bound) <= LONG_VALUE[0] <= solved.value[0] * (1.0 + solved.error_bound)


def test_the_walks_solve_and_the_bounds_solve_pass_the_refusal_on(monkeypatch):
    from types import SimpleNamespace

    from crafting_system.planner import _packed, _pattern_bound

    seen = []

    class Asked(Exception):
        pass

    def record(graph, **kwargs):
        seen.append(kwargs.get("refuse_above"))
        raise Asked

    monkeypatch.setattr(_packed, "solve_packed", record)
    with pytest.raises(Asked):
        _packed.solve_walked(None, None, SimpleNamespace(graph=long_graph()), refuse_above=1e-3)
    with pytest.raises(Asked):
        _packed.solve_walked(None, None, SimpleNamespace(graph=long_graph()))
    assert seen == [1e-3, None]  # None: the solver's own 1e-6, the exact search

    import inspect

    source = inspect.getsource(_pattern_bound.pattern_lower_bound)
    assert "solve_packed(graph, progress=None, refuse_above=refuse_above)" in source
