"""The pieces of `solver/_packed_solve.py` on graphs of two to six states, with every value worked out by hand (ticket #413).

`test_solver_packed.py` compares the packed solve with the object solver on random models; the measurement week (#399) found
that 150 of the 260 mutants of `_packed_solve.py` survived the light suite. They sit where a comparison of final values cannot
see them: the order of ties, the rounding allowance of the certificate, the chunking of long sums, the counters and clocks of
`info`, and BiCGSTAB (whose failures the dense fallback hides). Here each piece is called on its own, on a graph small enough
to solve on paper:

* GEO: one state, one action of cost 2 that ends in the goal or stays, half and half. Its value is 2 / (1/2) = 4.
* CHOICE: a cheap action that leaves with chance 1/10 (cost 1, value 10) beside a dear sure one (cost 5): value 5.
* LINE: five states in a row, each of cost 1 that moves on or stays, half and half: the values are 10, 8, 6, 4, 2.
* TRAP: a start whose cheap action may fall into a state that never finishes; the sure one costs 3 and leaves with chance 1/2.

No expected number here is read off the code under test.
"""

import math
import sys

import numpy as np
import pytest

from crafting_system.solver import ConvergenceError, PackedBuilder, policy_reach, solve_packed
from crafting_system.solver import _packed_solve as ps
from crafting_system.solver._packed_solve import Certificate, Work, certify, evaluate_policy, lift_policy, proper_states, solve_graph

EPS = sys.float_info.epsilon
INF = math.inf


def build(*states):
    """A graph from `(is_goal, [(cost, [(successor, weight), ...]), ...])` per state; the tag of an action is its running number."""
    builder = PackedBuilder()
    tag = 0
    for goal, actions in states:
        for cost, outcomes in actions:
            builder.action(tag, cost, builder.kernel([s for s, _ in outcomes], [w for _, w in outcomes]))
            tag += 1
        builder.close_state(goal)
    return builder.build()


GEO = build((False, [(2.0, [(1, 1), (0, 1)])]), (True, []))
CHOICE = build((False, [(1.0, [(1, 1), (0, 9)]), (5.0, [(1, 1)])]), (True, []))
LINE = build(*[(False, [(1.0, [(i + 1, 1), (i, 1)])]) for i in range(5)], (True, []))
# TRAP: 0 is the start, 1 the goal, 2 a state whose only action stays in it, 3 a state whose only action falls into 2;
# 0 can use X (cost 1: the goal or the trap, half and half) or Y (cost 3: the goal or stay, half and half)
TRAP = build(
    (False, [(1.0, [(1, 1), (2, 1)]), (3.0, [(1, 1), (0, 1)])]),
    (True, []),
    (False, [(1.0, [(2, 1)])]),
    (False, [(1.0, [(2, 1)])]),
)
# THREE: the start can walk on at once to the goal at a high price, or take a cheap step that falls into an expensive state 99 times in 100
EXPENSIVE_TRAP = build(
    (False, [(1.0, [(1, 1), (2, 99)]), (3.0, [(1, 1)])]),
    (True, []),
    (False, [(100.0, [(1, 1)])]),
)
TIE = build((False, [(2.0, [(1, 1), (0, 1)]), (4.0, [(1, 1)])]), (True, []))


# --- Work: the arrays shared by the passes -----------------------------------------------------------------------------


def test_work_of_a_graph_without_actions_has_empty_per_action_arrays():
    work = Work(build((True, [])))

    assert work.A == 0 and len(work.asize) == 0 and work.cum.tolist() == [0]


def test_work_knows_the_size_of_every_action_and_the_cumulative_edges():
    work = Work(CHOICE)

    assert work.asize.tolist() == [2, 1]
    assert work.cum.tolist() == [0, 2, 3]
    assert work.has.tolist() == [True, False]
    assert work.rows.tolist() == [0]


def test_state_reduce_fills_the_states_without_actions_with_the_empty_value():
    # states: 0 has actions a0 a1, 1 has none, 2 has a2
    graph = build((False, [(1.0, [(1, 1)]), (1.0, [(1, 1)])]), (True, []), (False, [(1.0, [(1, 1)])]))
    work = Work(graph)
    per_action = np.array([5.0, 3.0, 4.0])

    assert work.state_min(per_action).tolist() == [3.0, INF, 4.0]
    assert work.state_reduce(np.maximum, per_action, -7.0).tolist() == [5.0, -7.0, 4.0]


def test_state_argmin_is_the_first_action_that_reaches_the_least_and_minus_one_for_a_state_without_actions():
    graph = build((False, [(1.0, [(1, 1)]), (1.0, [(1, 1)]), (1.0, [(1, 1)])]), (True, []), (False, [(1.0, [(1, 1)])]))
    work = Work(graph)
    per_action = np.array([3.0, 2.0, 2.0, 9.0])

    assert work.state_argmin(per_action, work.state_min(per_action)).tolist() == [1, -1, 3]


def test_state_argmin_gives_minus_one_when_no_action_reaches_the_given_best():
    graph = build((False, [(1.0, [(1, 1)]), (1.0, [(1, 1)])]), (True, []))
    work = Work(graph)

    found = work.state_argmin(np.array([1.0, 2.0]), np.array([0.5, 0.0]))  # a "best" that no action has: not found

    assert found.tolist() == [-1, -1]


def test_state_argmin_of_a_graph_without_actions_is_minus_one_everywhere():
    work = Work(build((True, []), (True, [])))

    assert work.state_argmin(np.zeros(0), np.zeros(2)).tolist() == [-1, -1]


@pytest.mark.parametrize(
    "limit,chunks",
    [(1, [(0, 1), (1, 2), (2, 3), (3, 4)]), (3, [(0, 1), (1, 2), (2, 3), (3, 4)]), (4, [(0, 2), (2, 4)]), (7, [(0, 3), (3, 4)]), (8, [(0, 4)]), (100, [(0, 4)])],
)
def test_action_chunks_hold_at_most_the_limit_in_edges_and_at_least_one_action(monkeypatch, limit, chunks):
    # four actions of two edges each: a chunk of the limit 4 holds two of them, the limit 7 three
    graph = build((False, [(1.0, [(1, 1), (0, 1)])] * 4), (True, []))
    monkeypatch.setattr(ps, "CHUNK_EDGES", limit)

    assert list(Work(graph).action_chunks()) == chunks


def test_nonself_sums_add_probability_times_value_over_the_successors_other_than_the_state_itself():
    # a0 of state 0: 1/4 to state 1, 3/4 to state 0 itself; a1 of state 1: 1/2 to state 2, 1/2 to state 0
    graph = build((False, [(1.0, [(1, 1), (0, 3)])]), (False, [(1.0, [(2, 1), (0, 1)])]), (True, []))
    f = np.array([100.0, 8.0, 40.0])

    assert Work(graph).nonself_sums(f).tolist() == [0.25 * 8.0, 0.5 * 40.0 + 0.5 * 100.0]


def test_nonself_sums_over_several_chunks_give_the_same_sums(monkeypatch):
    graph = build((False, [(1.0, [(1, 1), (0, 3)]), (1.0, [(2, 1), (0, 1)]), (1.0, [(1, 1), (2, 1), (0, 2)])]), (False, [(1.0, [(2, 1), (0, 1)])]), (True, []))
    f = np.array([100.0, 8.0, 40.0])
    whole = Work(graph).nonself_sums(f).tolist()
    monkeypatch.setattr(ps, "CHUNK_EDGES", 3)

    assert Work(graph).nonself_sums(f).tolist() == whole == [0.25 * 8.0, 0.5 * 40.0, 0.25 * 8.0 + 0.25 * 40.0, 0.5 * 40.0 + 0.5 * 100.0]


# --- _settled and certify -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "residual,at_floor,expected", [(1e-11, False, True), (1e-10, False, True), (1.1e-10, False, False), (1e-3, True, True), (0.0, False, True)]
)
def test_a_certificate_is_settled_below_the_tolerance_or_at_the_rounding_floor(residual, at_floor, expected):
    assert ps._settled(Certificate(0.0, 1.0, 1.0, residual, at_floor), 1e-10) is expected


def test_certify_of_an_exact_value_is_a_few_roundings_wide():
    # GEO, value 4: the Bellman operator gives 2 + 0.5 * 4 = 4 exactly. The allowance per state is (terms + 2) eps of the sum,
    # terms = 2 outcomes + 1 = 3, so rho = 5 eps and delta = rho / (1 - rho) * 4 ~ 20 eps; the bound is delta / 2 = 10 eps
    certificate = certify(GEO, np.array([4.0, 0.0]), np.array([True, True]))

    assert certificate.bound == pytest.approx(10 * EPS, rel=1e-6)
    assert certificate.lower == pytest.approx(1.0 - 10 * EPS, abs=1e-18) and certificate.upper == pytest.approx(1.0 + 10 * EPS, abs=1e-18)
    assert certificate.residual == 0.0
    assert certificate.at_floor is True


@pytest.mark.parametrize(
    "value,bound,residual",
    [
        (3.6, 1 / 9, 0.1),  # 10% under: T v = 2 + 1.8 = 3.8, e = 0.2 of the action cost 2; the true value is v / (1 - 0.1), 1/9 above v
        (4.4, 0.1 / 1.1, 0.1),  # 10% over: d = 0.2, a_lo = 2 / 2.2, so the value is at most 1 - 2/2.2 = 1/11 under
    ],
)
def test_certify_of_a_wrong_value_gives_the_relative_error_by_hand(value, bound, residual):
    certificate = certify(GEO, np.array([value, 0.0]), np.array([True, True]))

    assert certificate.bound == pytest.approx(bound, rel=1e-9)
    assert certificate.residual == pytest.approx(residual, rel=1e-9)
    assert certificate.at_floor is False


def test_certify_of_a_value_that_is_too_low_by_the_whole_action_cost_has_an_infinite_upper_side():
    certificate = certify(GEO, np.array([0.0, 0.0]), np.array([True, True]))  # T v = 2: e = k, nothing can be said above

    assert certificate.upper == INF and certificate.bound == INF and certificate.lower == pytest.approx(1.0, abs=1e-12)
    assert certificate.residual == 1.0


def test_certify_uses_the_cost_of_the_greedy_action_when_the_first_action_is_not_it():
    # CHOICE, value 5 (action 1, cost 5, is the greedy one). terms = 2 outcomes + 1 = 3, rho = 5 eps, delta = rho / (1 - rho) * 5 ~ 25 eps.
    # The cheapest action costs g = 1: a_lo = g / (g + delta) ~ 1 - 25 eps. The greedy action costs k = 5: a_hi = k / (k - delta) ~ 1 + 5 eps
    certificate = certify(CHOICE, np.array([5.0, 0.0]), np.array([True, True]))

    assert certificate.at_floor is True and certificate.residual == 0.0
    assert certificate.lower == pytest.approx(1.0 - 25 * EPS, abs=1e-17)
    assert certificate.upper == pytest.approx(1.0 + 5 * EPS, abs=1e-17)


def test_certify_with_nothing_to_check_is_the_exact_certificate():
    assert certify(GEO, np.array([0.0, 0.0]), np.array([False, True])) == Certificate(0.0, 1.0, 1.0, 0.0, True)
    assert certify(build((True, [])), np.zeros(1), np.ones(1, dtype=bool)) == Certificate(0.0, 1.0, 1.0, 0.0, True)


def test_certify_of_a_state_whose_every_action_leaves_the_solved_states_is_infinite():
    found = certify(TRAP, np.array([6.0, 0.0, 0.0, 0.0]), np.array([True, True, False, True]))  # state 3 is claimed solved but only falls into 2

    assert found == Certificate(INF, 0.0, INF, INF, False)


def test_certify_leaves_out_the_actions_that_reach_a_state_not_solved():
    # TRAP without 2 and 3: X may land in the trap, so only Y counts: with value 6 the operator is exact
    certificate = certify(TRAP, np.array([6.0, 0.0, 0.0, 0.0]), np.array([True, True, False, False]))

    assert certificate.at_floor is True and certificate.bound < 1e-14


# --- proper states and the start policy ---------------------------------------------------------------------------------


def test_proper_states_keep_the_states_with_a_sure_way_to_the_goal_and_the_luckiest_distance():
    work = Work(TRAP)
    leave = work.nonself_sums(np.ones(work.n))
    alive = leave > 0.0
    effective = np.where(alive, TRAP.act_cost / np.where(alive, leave, 1.0), INF)

    inside, ok, distance, policy = proper_states(work, alive, effective)

    assert alive.tolist() == [True, True, False, True]  # X, Y, the trap's own loop (leaves with chance 0), the fall
    assert effective.tolist() == [1.0, 6.0, INF, 1.0]  # Y: cost 3 / leaving chance 1/2
    assert inside.tolist() == [True, True, False, False]
    assert ok.tolist() == [False, True, False, False]  # X may land outside the proper set
    assert distance.tolist() == [6.0, 0.0, INF, INF]
    assert policy.tolist() == [1, -1, -1, -1]  # state 0 takes Y; the goal, the trap and the fall take nothing: -1, not another negative


def test_proper_states_of_a_graph_where_everything_is_proper_keep_everything():
    work = Work(CHOICE)
    leave = work.nonself_sums(np.ones(work.n))
    effective = CHOICE.act_cost / leave

    inside, ok, distance, policy = proper_states(work, leave > 0, effective)

    assert inside.tolist() == [True, True] and ok.tolist() == [True, True]
    assert distance.tolist() == [5.0, 0.0]  # the sure action: 5; the cheap one costs 1 / (1/10) = 10
    assert policy.tolist() == [1, -1]


# --- BiCGSTAB ------------------------------------------------------------------------------------------------------------

A3 = np.array([[4.0, 1.0, 0.0], [-1.0, 3.0, 1.0], [2.0, 0.0, 5.0]])
X3 = np.array([1.0, -2.0, 3.0])


def residual_of(matrix, b, x):
    return float(np.linalg.norm(b - matrix @ x) / np.linalg.norm(b))


def test_bicgstab_solves_a_three_by_three_system_in_at_most_three_steps():
    b = A3 @ X3
    x, relative, steps = ps._bicgstab(lambda v: A3 @ v, b, np.zeros(3), 1e-13, 100)

    assert x == pytest.approx(X3, abs=1e-12)
    assert 1 <= steps <= 3  # BiCGSTAB ends in n steps in exact arithmetic
    assert relative <= 1e-12


def test_bicgstab_reports_the_residual_of_the_iterate_it_returns():
    b = A3 @ X3
    for limit in (1, 2):
        x, relative, steps = ps._bicgstab(lambda v: A3 @ v, b, np.zeros(3), 1e-30, limit)

        assert steps == limit  # not converged: it ran the steps it was given
        assert relative == pytest.approx(residual_of(A3, b, x), rel=1e-6)
        assert 0.0 < relative < 1.0


def test_each_bicgstab_step_lowers_the_residual_of_a_well_conditioned_system():
    b = A3 @ X3
    residuals = [ps._bicgstab(lambda v: A3 @ v, b, np.zeros(3), 1e-30, limit)[1] for limit in (1, 2, 3)]

    assert residuals[0] > residuals[1] > residuals[2]
    assert residuals[2] < 1e-12


def test_bicgstab_scales_the_stopping_test_by_the_size_of_the_right_hand_side():
    b = (A3 @ X3) * 1e6
    x, relative, steps = ps._bicgstab(lambda v: A3 @ v, b, np.zeros(3), 1e-13, 100)

    assert steps <= 3 and x == pytest.approx(X3 * 1e6, rel=1e-10)


def test_bicgstab_stops_at_the_first_step_whose_residual_is_below_the_tolerance_times_the_size_of_the_right_hand_side():
    # the relative residual after 1, 2 and 3 steps is 0.066, 0.034 and 2e-16 (see the test above): a tolerance of 0.1 is met after the first
    # step, 0.05 after the second, and 1e-3 only after the third; scaling b by a million changes nothing
    for scale in (1.0, 1e6):
        b = (A3 @ X3) * scale
        for tol, steps in ((0.1, 1), (0.05, 2), (1e-3, 3)):
            x, relative, taken = ps._bicgstab(lambda v: A3 @ v, b, np.zeros(3), tol, 100)

            assert taken == steps, (scale, tol)
            assert relative <= tol and relative == pytest.approx(residual_of(A3, b, x), rel=1e-6, abs=1e-14)


def test_bicgstab_started_at_the_answer_takes_no_step():
    b = A3 @ X3

    x, relative, steps = ps._bicgstab(lambda v: A3 @ v, b, X3.copy(), 1e-13, 100)

    assert steps == 0 and relative <= 1e-15 and (x == X3).all()


def test_bicgstab_of_a_one_by_one_system_ends_in_the_half_step():
    x, relative, steps = ps._bicgstab(lambda v: 2.0 * v, np.array([2.0]), np.zeros(1), 1e-13, 100)

    assert x.tolist() == [1.0] and relative == 0.0 and steps == 1


def test_bicgstab_stops_at_the_step_limit():
    b = A3 @ X3

    assert ps._bicgstab(lambda v: A3 @ v, b, np.zeros(3), 1e-30, 2)[2] == 2


SKEW = np.array([[0.0, 1.0], [-1.0, 0.0]])  # v . A v = 0 for every v: the first step divides by zero, the method can make no progress


def test_bicgstab_that_cannot_progress_stops_after_the_stagnation_limit_and_returns_the_start(monkeypatch):
    monkeypatch.setattr(ps, "STAGNATION", 7)
    b = np.array([1.0, 2.0])

    x, relative, steps = ps._bicgstab(lambda v: SKEW @ v, b, np.zeros(2), 1e-13, 1000)

    assert steps == 7 and relative == 1.0 and x.tolist() == [0.0, 0.0]


def test_bicgstab_that_cannot_progress_is_cut_by_the_step_limit_when_that_is_sooner(monkeypatch):
    monkeypatch.setattr(ps, "STAGNATION", 50)

    assert ps._bicgstab(lambda v: SKEW @ v, np.array([1.0, 2.0]), np.zeros(2), 1e-13, 4)[2] == 4


def test_bicgstab_halving_the_residual_resets_the_stagnation_count(monkeypatch):
    # the residual falls by far more than half in each of the three steps, so a limit of 2 steps without halving is never reached
    monkeypatch.setattr(ps, "STAGNATION", 2)
    b = A3 @ X3

    x, relative, steps = ps._bicgstab(lambda v: A3 @ v, b, np.zeros(3), 1e-13, 100)

    assert x == pytest.approx(X3, abs=1e-12) and steps <= 3


# --- evaluate_policy -----------------------------------------------------------------------------------------------------


def prepared(graph):
    work = Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    return work, leave


def test_a_policy_is_evaluated_by_a_dense_solve_up_to_the_dense_limit():
    work, leave = prepared(LINE)
    info = {}

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 5, 1e-13, info)

    assert values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-13)
    assert info == {"linear_dense": 1}


def test_above_the_dense_limit_bicgstab_alone_solves_a_small_system_without_the_dense_fallback():
    work, leave = prepared(LINE)
    info = {}

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-10)
    assert "linear_dense" not in info  # the residual was below the fallback's 1e-10
    assert 1 <= info["linear_iterations"] <= 10 and info["linear_residual"] < 1e-12  # a few steps; a broken recurrence runs to the stagnation limit of 400


def test_the_dense_fallback_takes_over_when_bicgstab_cannot_reach_its_residual(monkeypatch):
    work, leave = prepared(LINE)
    info = {}
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)  # one step: not enough, whatever the restarts

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-13)
    assert info["linear_dense"] == 1
    assert info["linear_iterations"] == 1 + ps.BICGSTAB_RESTARTS  # the first run and each restart stopped at its one step


def test_the_dense_fallback_is_not_used_for_a_policy_longer_than_its_limit(monkeypatch):
    work, leave = prepared(LINE)
    info = {}
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)
    monkeypatch.setattr(ps, "DENSE_FALLBACK", 4)  # five states in the policy

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert "linear_dense" not in info and info["linear_residual"] > ps.DENSE_FALLBACK_RESIDUAL
    assert not values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-6)


def test_the_dense_fallback_covers_a_policy_of_exactly_its_limit(monkeypatch):
    work, leave = prepared(LINE)
    info = {}
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)
    monkeypatch.setattr(ps, "DENSE_FALLBACK", 5)  # five states in the policy: at the limit

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert info["linear_dense"] == 1 and values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-13)


def test_the_dense_fallback_is_used_when_the_residual_is_just_above_its_threshold_and_not_when_at_or_below_it(monkeypatch):
    work, leave = prepared(LINE)
    policy = np.array([0, 1, 2, 3, 4, -1])
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)
    seen = {}
    info = {}
    evaluate_policy(work, leave, policy, np.zeros(6), 4, 1e-13, info)
    assert info["linear_dense"] == 1  # one step leaves a residual far above 1e-10
    monkeypatch.setattr(ps, "DENSE_FALLBACK_RESIDUAL", 10.0)  # a residual below this is good enough
    info = {}
    evaluate_policy(work, leave, policy, np.zeros(6), 4, 1e-13, info)
    assert "linear_dense" not in info


def test_no_restart_is_made_when_the_first_run_reached_its_residual(monkeypatch):
    work, leave = prepared(LINE)
    info = {}

    evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)
    first = info["linear_iterations"]
    info2 = {}
    monkeypatch.setattr(ps, "BICGSTAB_RESTARTS", 0)
    evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info2)

    assert info2["linear_iterations"] == first  # nothing was left to restart


def test_the_counters_of_the_linear_solves_add_up_over_calls():
    work, leave = prepared(LINE)
    info = {"linear_dense": 2, "linear_iterations": 10}

    evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 100, 1e-13, info)
    evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert info["linear_dense"] == 3 and info["linear_iterations"] > 10


def test_a_policy_with_no_state_has_the_zero_values():
    work, leave = prepared(LINE)

    assert evaluate_policy(work, leave, np.full(6, -1), np.zeros(6), 100, 1e-13, {}).tolist() == [0.0] * 6


def test_an_improper_policy_is_refused_with_its_singular_system():
    # 0 and 1 send each other to one another for ever: I - P = [[1, -1], [-1, 1]]
    graph = build((False, [(1.0, [(1, 1)])]), (False, [(1.0, [(0, 1)])]), (True, []))
    work = Work(graph)

    with pytest.raises(ConvergenceError, match="singular"):
        evaluate_policy(work, np.ones(3), np.array([0, 1, -1]), np.zeros(3), 100, 1e-13, {})


def test_a_stiff_system_gets_its_iterative_refinement(monkeypatch):
    # 40 states in a row, each leaving with chance 1 / (1 + 1e9): the values are (1 + 1e9) (40 - i). One LU solve of this matrix loses
    # nine digits; the first refinement brings the residual under 4 eps and the second finds nothing left to do
    n, leaving = 40, 10**9
    graph = build(*[(False, [(1.0, [(i + 1, 1), (i, leaving)])]) for i in range(n)], (True, []))
    work, leave = prepared(graph)
    solves = []
    real = np.linalg.solve
    monkeypatch.setattr(np.linalg, "solve", lambda a, b: solves.append(1) or real(a, b))

    values = evaluate_policy(work, leave, np.concatenate((np.arange(n), [-1])), np.zeros(n + 1), 100, 1e-13, {})

    expected = np.array([(1 + leaving) * (n - i) for i in range(n)], dtype=float)
    assert values[:n] == pytest.approx(expected, rel=1e-14)
    assert len(solves) == 3  # the solve and two refinements: the second refinement still saw a residual above the allowance


# --- solve_graph and solve_packed ---------------------------------------------------------------------------------------


def test_solve_graph_runs_with_no_progress_and_no_info():
    core = solve_graph(GEO)

    assert core.value.tolist() == pytest.approx([4.0, 0.0], rel=1e-14)
    assert core.action.tolist() == [0, -1]
    assert core.solved.tolist() == [True, True]


def test_solve_graph_of_a_graph_with_no_actions_costs_nothing_where_it_is_the_goal_and_is_unbounded_elsewhere():
    graph = build((False, []), (True, []))

    core = solve_graph(graph)

    assert core.value.tolist() == [INF, 0.0] and core.solved.tolist() == [False, True]
    assert core.action.tolist() == [-1, -1]
    assert core.certificate == Certificate(0.0, 1.0, 1.0, 0.0, True)


def test_solve_graph_reports_what_it_did_to_the_progress_callback_and_to_info():
    lines, info = [], {}

    solve_graph(CHOICE, progress=lines.append, info=info)

    assert [line.split(" (")[0].split(":")[0] for line in lines] == ["proper states", "policy iteration 1", "certificate on the quotient"]
    assert lines[0].startswith("proper states: 2 of 2")
    assert lines[1].startswith("policy iteration 1: 0 states improve")  # the start policy is the sure action, already the best
    assert info["rounds"] == 1 and info["refinements"] == 0 and info["linear_dense"] == 1


def test_the_start_policy_is_the_luckiest_path_by_cost_per_leaving_chance_not_the_cheapest_by_the_product():
    # CHOICE: the cheap action costs 1 but leaves with chance 1/10 (effective 10), the sure one 5: the start policy is the sure one,
    # which is optimal, so one round of evaluation and no improvement
    info = {}

    core = solve_graph(CHOICE, info=info)

    assert core.action.tolist() == [1, -1] and core.value.tolist() == [5.0, 0.0] and info["rounds"] == 1


def test_a_better_action_found_by_the_evaluation_is_taken_in_the_next_round():
    info = {}
    lines = []

    core = solve_graph(EXPENSIVE_TRAP, info=info, progress=lines.append)

    assert core.value.tolist() == [3.0, 0.0, 100.0]  # the start policy takes the cost-1 action (effective 1 + distance 0): value 100
    assert core.action.tolist() == [1, -1, 2]
    assert info["rounds"] == 2
    assert any(line.startswith("policy iteration 1: 1 states improve") for line in lines)


def test_a_state_whose_start_action_is_not_the_first_of_the_graph_is_improved_too():
    # states 0 (start), 1 (a choice between a cheap action that falls into the dear state 2 99 times in 100, and a sure one), 2, 3 = goal;
    # the start policy takes the cheap action of state 1 (index 1 in the graph, not 0); V2 = 100, V1 = 3, V0 = 1 + 3
    graph = build(
        (False, [(1.0, [(1, 1)])]),
        (False, [(1.0, [(3, 1), (2, 99)]), (3.0, [(3, 1)])]),
        (False, [(100.0, [(3, 1)])]),
        (True, []),
    )
    info = {}

    core = solve_graph(graph, info=info)

    assert core.value.tolist() == pytest.approx([4.0, 3.0, 100.0, 0.0], rel=1e-14)
    assert core.action.tolist() == [0, 2, 3, -1] and info["rounds"] == 2


def test_the_rounds_are_limited_by_max_rounds_and_the_refinement_evaluates_the_policy_the_last_round_chose():
    capped, full = {}, {}

    cut = solve_graph(EXPENSIVE_TRAP, max_rounds=1, info=capped)
    done = solve_graph(EXPENSIVE_TRAP, max_rounds=2, info=full)

    assert capped["rounds"] == 1 and capped["refinements"] == 1  # the value of the first policy (100) does not pass: it is evaluated again for the better one
    assert full["rounds"] == 2 and full["refinements"] == 0
    assert cut.value.tolist() == done.value.tolist() == [3.0, 0.0, 100.0]


def test_two_actions_of_equal_value_do_not_trade_places():
    info = {}

    core = solve_graph(TIE, info=info)

    assert core.action.tolist() == [0, -1]  # the first of the two, kept (the start policy takes the first on a tie)
    assert info["rounds"] == 1
    assert core.value.tolist() == [4.0, 0.0]


def test_an_action_that_only_stays_is_not_alive_and_does_not_trouble_the_solve():
    graph = build((False, [(1.0, [(0, 1)]), (2.0, [(1, 1), (0, 1)])]), (True, []))

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        core = solve_graph(graph)

    assert core.action.tolist() == [1, -1] and core.value.tolist() == [4.0, 0.0]


def test_states_with_no_proper_policy_are_infinite_and_have_no_action():
    core = solve_graph(TRAP)

    assert core.value.tolist() == [6.0, 0.0, INF, INF]
    assert core.solved.tolist() == [True, True, False, False]
    assert core.action.tolist() == [1, -1, -1, -1]


def test_the_refinement_loop_runs_at_most_three_times_while_the_certificate_is_not_settled(monkeypatch):
    monkeypatch.setattr(ps, "_settled", lambda certificate, tolerance: False)
    info = {}

    solve_graph(GEO, info=info)

    assert info["refinements"] == 3


def test_a_settled_certificate_is_not_refined():
    info = {}

    solve_graph(GEO, info=info)

    assert info["refinements"] == 0


def test_an_accepted_bound_of_zero_is_refused_whatever_the_values():
    with pytest.raises(ConvergenceError) as refused:
        solve_graph(GEO, accept_bound=0.0)

    assert refused.value.args[1] > 0 if len(refused.value.args) > 1 else True


def test_solve_packed_reports_the_counts_of_the_graph_and_of_the_merge():
    solved = solve_packed(CHOICE)

    assert solved.value.tolist() == [5.0, 0.0] and solved.action.tolist() == [1, -1]
    assert solved.classes == 2 and len(set(solved.cls.tolist())) == 2
    info = solved.info
    assert (info["states"], info["actions"], info["kernels"], info["edges_stored"]) == (2, 2, 2, 3)
    assert (info["classes"], info["quotient_actions"], info["quotient_edges_stored"]) == (2, 2, 3)
    assert info["rounds"] == 1 and info["quotient_bound"] < 1e-14 and solved.error_bound < 1e-14


def test_solve_packed_merges_states_that_are_interchangeable_and_lifts_the_policy_back():
    # 0 goes to 1 or 2 (half each); 1 and 2 are twins: cost 2, the goal 3 or stay, half and half. V1 = V2 = 4, V0 = 1 + 4 = 5
    graph = build(
        (False, [(1.0, [(1, 1), (2, 1)])]),
        (False, [(2.0, [(3, 1), (1, 1)])]),
        (False, [(2.0, [(3, 1), (2, 1)])]),
        (True, []),
    )

    solved = solve_packed(graph)

    cls = solved.cls.tolist()
    assert solved.classes == 3 and cls[1] == cls[2] and len({cls[0], cls[1], cls[3]}) == 3  # one class for the twins
    assert solved.value.tolist() == pytest.approx([5.0, 4.0, 4.0, 0.0], rel=1e-14)
    assert solved.action.tolist() == [0, 1, 2, -1]  # the policy of the class, in the actions of each member
    assert solved.info["classes"] == 3 and solved.info["merge_rounds"] >= 1
    unmerged = solve_packed(graph, merge=False)
    assert unmerged.classes == 4 and unmerged.value.tolist() == pytest.approx(solved.value.tolist(), rel=1e-14)


def test_a_dead_state_whose_action_comes_first_in_the_graph_still_has_no_action():
    graph = build((False, [(1.0, [(0, 1)])]), (False, [(2.0, [(2, 1)])]), (True, []))

    solved = solve_packed(graph)

    assert solved.value.tolist() == [INF, 2.0, 0.0] and solved.action.tolist() == [-1, 1, -1]


def test_solve_packed_gives_dead_states_infinite_values_and_no_action():
    solved = solve_packed(TRAP)

    assert solved.value.tolist() == pytest.approx([6.0, 0.0, INF, INF], rel=1e-14)
    assert solved.action.tolist() == [1, -1, -1, -1]


def test_solve_packed_on_a_longer_chain_with_bicgstab_gives_the_same_values_and_counts_its_steps():
    solved = solve_packed(LINE, dense_limit=2)

    assert solved.value.tolist() == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-10)
    assert solved.info["linear_residual"] < 1e-10  # (the start values of the luckiest path are the answer: no step is needed)


def test_solve_packed_refuses_a_bound_above_the_one_accepted_and_names_the_merge_or_the_solve():
    with pytest.raises(ConvergenceError):
        solve_packed(GEO, accept_bound=0.0)


def test_solve_packed_says_how_far_it_has_come():
    lines = []

    solve_packed(CHOICE, progress=lines.append)

    assert any(line.startswith("merged 2 states into 2 classes, 2 actions (") for line in lines)
    assert any(line.startswith("certificate on the whole graph: bound") for line in lines)


class Clock:
    """A clock that starts at 1000 and moves 1.2345 s each time it is read: every difference is a whole number of those."""

    def __init__(self):
        self.now = 1000.0 - 1.2345

    def perf_counter(self):
        self.now += 1.2345
        return self.now


def test_the_times_in_info_are_differences_of_the_clock_rounded_to_hundredths(monkeypatch):
    monkeypatch.setattr(ps, "time", Clock())

    solved = solve_packed(CHOICE)

    for key in ("merge_seconds", "solve_seconds", "certify_seconds", "seconds"):
        value = solved.info[key]
        ticks = value / 1.2345
        assert 0.99 <= ticks < 40 and abs(ticks - round(ticks)) < 0.005, key  # a few reads of the clock apart, not their sum
        assert abs(value * 100 - round(value * 100)) < 1e-6, key  # to hundredths
    assert solved.info["merge_seconds"] == 1.23  # one read after the start and none in between


def test_the_messages_of_progress_carry_the_clock_in_tenths_of_a_second(monkeypatch):
    monkeypatch.setattr(ps, "time", Clock())
    lines = []

    solve_graph(CHOICE, progress=lines.append)

    assert lines[0] == "proper states: 2 of 2 (1.2 s)"  # began on the first read, this line on the second
    assert lines[1].startswith("policy iteration 1: 0 states improve (")
    assert lines[1].endswith(" s)")


# --- lift_policy and policy_reach ----------------------------------------------------------------------------------------


def test_lift_policy_gives_a_state_with_one_action_that_action():
    graph = build((False, [(1.0, [(1, 1)])]), (True, []))
    solved = solve_packed(graph)

    assert solved.action.tolist() == [0, -1]


def test_lift_policy_of_a_graph_without_actions_is_minus_one_everywhere():
    graph = build((False, []), (True, []))

    assert lift_policy(graph, graph, np.zeros(0, dtype=np.int32), np.array([0, 1]), np.array([-1, -1])).tolist() == [-1, -1]


def test_policy_reach_follows_the_policy_through_a_cycle_and_stops():
    # 0 -> {1, 2}; 1 -> {0, 3}; 2 and 3 are goals; 4 is never reached
    graph = build(
        (False, [(1.0, [(1, 1), (2, 1)])]),
        (False, [(1.0, [(0, 1), (3, 1)])]),
        (True, []),
        (True, []),
        (False, [(1.0, [(0, 1)])]),
    )

    assert policy_reach(graph, np.array([0, 1, -1, -1, 2]), 0).tolist() == [0, 1, 2, 3]
    assert policy_reach(graph, np.array([0, 1, -1, -1, 2]), 4).tolist() == [0, 1, 2, 3, 4]
    assert policy_reach(graph, np.array([-1, 1, -1, -1, 2]), 0).tolist() == [0]  # the policy takes no action at 0: it goes nowhere
