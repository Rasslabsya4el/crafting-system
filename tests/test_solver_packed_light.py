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
from fractions import Fraction

import numpy as np
import pytest

from crafting_system.solver import ConvergenceError, PackedBuilder, policy_reach, solve_packed
from crafting_system.solver import _packed_solve as ps
from crafting_system.solver._packed_chain import CyclesTooTangled
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


def reference_residuals(matrix, b, steps=4):
    """The relative residuals BiCGSTAB (van der Vorst's recurrence) has after each half step and each whole step, in exact `Fraction`s.

    Written from the textbook and not from the module: `[(iteration, relative residual), ...]` in the order the module can stop at them
    (after the first half of step k it has the residual of `s`, after the whole step that of `r`); the list ends where `s` or `r` is zero.
    """
    exact = [[Fraction(float(entry)) for entry in row] for row in matrix]

    def times(vector):
        return [sum(a * x for a, x in zip(row, vector)) for row in exact]

    def dot(u, v):
        return sum(p * q for p, q in zip(u, v))

    def size(vector):
        return math.sqrt(float(dot(vector, vector)))

    r = [Fraction(float(entry)) for entry in b]
    bnorm = size(r)
    rhat, v, p = list(r), [Fraction(0)] * len(r), [Fraction(0)] * len(r)
    rho = alpha = omega = Fraction(1)
    found = []
    for step in range(1, steps + 1):
        rho_new = dot(rhat, r)
        beta = (rho_new / rho) * (alpha / omega)
        p = [ri + beta * (pi - omega * vi) for ri, pi, vi in zip(r, p, v)]
        v = times(p)
        alpha = rho_new / dot(rhat, v)
        s = [ri - alpha * vi for ri, vi in zip(r, v)]
        found.append((step, size(s) / bnorm))
        if not any(s):
            break
        t = times(s)
        omega = dot(t, s) / dot(t, t)
        r = [si - omega * ti for si, ti in zip(s, t)]
        rho = rho_new
        found.append((step, size(r) / bnorm))
        if not any(r):
            break
    return found


def test_the_reference_residuals_are_the_ones_worked_out_by_hand_for_the_three_by_three_system():
    # A3 x = b with x = (1, -2, 3): b = (2, -4, 17), |b| = sqrt(309) = 17.58. The half step of the first iteration leaves |s| / |b| = 0.280, the
    # whole step 0.0660, the second half step 0.0682, the second whole step 0.0340, and the third half step solves the system (3 unknowns)
    b = A3 @ X3
    assert b.tolist() == [2.0, -4.0, 17.0]
    found = reference_residuals(A3, b)

    assert [step for step, _ in found] == [1, 1, 2, 2, 3]
    assert [round(value, 3) for _, value in found[:4]] == [0.280, 0.066, 0.068, 0.034] and found[4][1] == 0.0


def test_bicgstab_stops_at_the_first_half_or_whole_step_whose_residual_is_below_the_tolerance_times_the_size_of_the_right_hand_side():
    # the stopping steps and the residuals they leave are those of the reference above (not read off the module); a tolerance just above
    # and just below each of them is tried, and 0.3, which only the first half step (x + alpha p) meets before the whole step is made
    # scaling b by a million changes nothing
    reference = reference_residuals(A3, A3 @ X3)
    tolerances = [0.3] + [factor * value for _, value in reference if value > 1e-12 for factor in (0.99, 1.01)]  # (not 0: a float residual is never 0)
    seen_steps = set()
    for scale in (1.0, 1e6):
        b = (A3 @ X3) * scale
        for tol in tolerances:
            expected_steps, expected_residual = next((step, value) for step, value in reference if value <= tol)
            x, relative, taken = ps._bicgstab(lambda v: A3 @ v, b, np.zeros(3), tol, 100)

            assert taken == expected_steps, (scale, tol)
            assert relative == pytest.approx(expected_residual, rel=1e-6, abs=1e-14), (scale, tol)
            assert relative <= tol and relative == pytest.approx(residual_of(A3, b, x), rel=1e-6, abs=1e-14)
            seen_steps.add(taken)
    assert seen_steps == {1, 2, 3}  # the tolerances reach every number of steps: the test is not one-sided


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


def random_policy_graph(seed):
    """A graph of 4 to 8 states, one action each (cost 0.5 to 3, two to four outcomes of weights 1 to 3), the last state the goal: the policy takes every action."""
    import random

    rng = random.Random(seed)
    size = rng.randint(4, 8)
    states = []
    for _ in range(size):
        targets = rng.sample([*range(size + 1)], rng.randint(2, 4))
        states.append((False, [(round(rng.uniform(0.5, 3.0), 3), [(t, rng.choice([1, 2, 3])) for t in targets])]))
    states.append((True, []))
    return build(*states), np.append(np.arange(size), -1)


# random policies on which the recurrence of BiCGSTAB claimed a residual of 1e-13 and the values it returned were wrong (found by trying 400 seeds, #584)
DRIFTING_SEEDS = [86, 184, 308, 326, 337, 366, 395]


@pytest.mark.parametrize("seed", DRIFTING_SEEDS)
def test_the_recurrence_residual_of_bicgstab_is_tiny_and_the_true_residual_is_not_on_a_system_where_it_drifts(seed):
    graph, policy = random_policy_graph(seed)
    work = Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    seen = []
    info = {}
    real_run = ps._bicgstab_run

    def spy(*arguments):
        found = real_run(*arguments)
        seen.append(found)
        return found

    ps._bicgstab_run, kept = spy, ps._bicgstab_run
    try:
        values = evaluate_policy(work, leave, policy, np.zeros(work.n), 0, 1e-13, info)  # dense_limit 0: every policy by BiCGSTAB
    finally:
        ps._bicgstab_run = kept
    assert np.all(np.isfinite(values))
    claimed = [claim for *_, claim in seen]
    assert min(claimed) < 1e-10  # a run that the recurrence said had converged
    assert info["linear_residual"] <= 1e-10 or info["linear_backward_error"] <= 1e-10  # what was taken is good on one of the true measures, whatever the recurrence said
    assert ("linear_cycles" in info) == (info.get("linear_residual_iterate", 0.0) > 1e-10)  # an iterate that was not good was replaced by the exact solve


def tangled(*_arguments, **_keywords):
    raise CyclesTooTangled("putting back 3 distinct cut rows of 5 states needs 123 cells, past the 100 the memory of a run allows")


def test_a_policy_whose_true_residual_stays_large_is_never_returned_when_the_exact_solve_cannot_be_made(monkeypatch):
    work, leave = prepared(LINE)
    monkeypatch.setattr(ps, "policy_solver", tangled)  # the cycles do not fit in the memory of the run
    monkeypatch.setattr(ps, "_bicgstab", lambda matvec, b, x0, tol, limit: (x0 + 1e6, 0.5, 1))  # an iterate whose TRUE residual is 0.5

    with pytest.raises(ConvergenceError, match="true residual") as refused:
        evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 0, 1e-13, {})

    assert "needs 123 cells" in str(refused.value)  # what it would have cost, from the method, not a count of states


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
    assert info["linear_dense"] == 1 and "linear_iterations" not in info and "linear_cycles" not in info
    assert info["linear_backward_error"] <= 1e-14  # measured, though no iteration was made


def test_above_the_dense_limit_bicgstab_alone_solves_a_small_system_without_the_dense_fallback():
    work, leave = prepared(LINE)
    info = {}

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-10)
    assert "linear_cycles" not in info  # the residual was below the fallback's 1e-10
    assert 1 <= info["linear_iterations"] <= 10 and info["linear_residual"] < 1e-12  # a few steps; a broken recurrence runs to the stagnation limit of 400


def test_the_exact_solve_by_the_cycles_takes_over_when_bicgstab_cannot_reach_its_residual(monkeypatch):
    work, leave = prepared(LINE)
    info = {}
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)  # one step: not enough, whatever the restarts

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-13)
    assert info["linear_cycles"] == 1 and "linear_dense" not in info
    assert info["linear_iterations"] == 1 + ps.BICGSTAB_RESTARTS  # the first run and each restart stopped at its one step


def test_after_the_exact_solve_replaces_an_iterate_the_residual_reported_is_that_of_the_values_taken(monkeypatch):
    work, leave = prepared(LINE)
    info = {}
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)  # one step: far from the answer

    evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert info["linear_cycles"] == 1 and info["linear_residual_iterate"] > ps.DENSE_FALLBACK_RESIDUAL  # the iterate thrown away
    assert info["linear_residual"] <= 1e-14 and info["linear_backward_error"] <= 1e-14  # the exact values taken: not the iterate's residual


def test_a_policy_whose_exact_solve_does_not_fit_and_whose_true_residual_is_large_is_refused_not_returned(monkeypatch):
    work, leave = prepared(LINE)
    info = {}
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)
    monkeypatch.setattr(ps, "policy_solver", tangled)

    with pytest.raises(ConvergenceError, match="true residual"):
        evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert "linear_cycles" not in info and info["linear_residual"] > ps.ACCEPT_BOUND  # a garbage iterate is never handed to the policy improvement (#584)


def test_a_policy_whose_exact_solve_does_not_fit_keeps_an_iterate_whose_true_residual_is_small_and_says_why(monkeypatch):
    work, leave = prepared(LINE)
    info = {}
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)
    monkeypatch.setattr(ps, "policy_solver", tangled)
    monkeypatch.setattr(ps, "ACCEPT_BOUND", 10.0)  # the residual after one step is below this

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert "linear_cycles" not in info and info["linear_residual"] > ps.DENSE_FALLBACK_RESIDUAL  # the residual the caller sees is the true one
    assert info["linear_limit"]["states"] == 5 and "needs 123 cells" in info["linear_limit"]["why"]  # what remained, from the cost of the method
    assert np.all(np.isfinite(values))


def test_no_count_of_states_decides_whether_a_stiff_evaluation_is_solved_or_refused(monkeypatch):
    work, leave = prepared(LINE)
    info = {}
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)
    monkeypatch.setattr(ps, "DENSE_FALLBACK", 0)  # the old count (6,000), here zero: it is not read

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 4, 1e-13, info)

    assert info["linear_cycles"] == 1 and values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-13)


def test_the_exact_solve_is_used_when_the_residual_is_just_above_its_threshold_and_not_when_at_or_below_it(monkeypatch):
    work, leave = prepared(LINE)
    policy = np.array([0, 1, 2, 3, 4, -1])
    monkeypatch.setattr(ps, "BICGSTAB_ITERATIONS", 1)
    seen = {}
    info = {}
    evaluate_policy(work, leave, policy, np.zeros(6), 4, 1e-13, info)
    assert info["linear_cycles"] == 1  # one step leaves a residual far above 1e-10
    monkeypatch.setattr(ps, "DENSE_FALLBACK_RESIDUAL", 10.0)  # a residual below this is good enough
    info = {}
    evaluate_policy(work, leave, policy, np.zeros(6), 4, 1e-13, info)
    assert "linear_cycles" not in info


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


def test_a_stiff_system_is_solved_to_the_exact_values():
    # 300 states in a row, each leaving with chance 1 / (1 + 1e14): the values are (1 + 1e14) (300 - i), exact whole numbers (state i
    # costs 1 and moves on with weight 1 against 1e14 for staying, so V_i = (1 + 1e14) + V_{i+1}). The error of one LU solve of this matrix
    # depends on the BLAS in use (about 7e-15 where the first version of this test was written), and a refinement can only be told from no
    # refinement by a bound tighter than that; so the bound here is loose on purpose, 1e-13 of each value (some 15 times the one-solve error
    # seen), and the refinement itself is tested on a solver whose error is set by the test, in the next test
    n, leaving = 300, 10**14
    graph = build(*[(False, [(1.0, [(i + 1, 1), (i, leaving)])]) for i in range(n)], (True, []))
    work, leave = prepared(graph)

    values = evaluate_policy(work, leave, np.concatenate((np.arange(n), [-1])), np.zeros(n + 1), 1000, 1e-13, {})

    for i in range(n):
        exact = Fraction((1 + leaving) * (n - i))
        assert abs(Fraction(float(values[i])) - exact) <= Fraction(1, 10**13) * exact, i


def test_the_dense_solve_is_refined_twice_and_each_correction_is_added_with_its_sign(monkeypatch):
    monkeypatch.setattr(ps, "DENSE_FALLBACK_RESIDUAL", 1e-6)  # (a backward error of 1e-9 is good enough here: the exact solve by the cycles is not to take over)
    # A solver that returns (1 + d) times the true solution, d = 1e-3, whatever the BLAS: one solve leaves the error d, a correction
    # solved by the same (1 + d) solver makes it d^2 = 1e-6 and a second one d^3 = 1e-9. The values (10, 8, 6, 4, 2 of LINE) must be
    # within 1e-8 of the exact ones: no refinement (1e-3), one (1e-6) or a correction of the wrong sign (2e-3, 2e-6 ...) fail
    work, leave = prepared(LINE)
    real, delta = np.linalg.solve, 1e-3
    monkeypatch.setattr(np.linalg, "solve", lambda a, b: (1.0 + delta) * real(a, b))

    values = evaluate_policy(work, leave, np.array([0, 1, 2, 3, 4, -1]), np.zeros(6), 100, 1e-13, {})

    assert values == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-8, abs=1e-12)
    assert abs(values[0] - 10.0) > 1e-10  # (and the stub did act: the refinement is not exact either, d^3 is left)


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

    # the error carries the certified bound: GEO's value 4 is exact, so it is the rounding width 10 eps of `test_certify_of_an_exact_value...`
    assert refused.value.error_bound == pytest.approx(10 * EPS, rel=1e-6)


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


# --- the thresholds of the policy evaluation and of the solve, with `_bicgstab` and `certify` replaced -----------------------------------
#
# A threshold that a comparison of final values cannot see (the values are the same whichever side of it a residual falls) is tested on the
# calls it makes: `_bicgstab` is replaced by a function that returns the true values of LINE with the residual the test says, and `certify`
# by one that returns the bound the test says.

LINE_POLICY = np.array([0, 1, 2, 3, 4, -1])
LINE_VALUES = np.array([10.0, 8.0, 6.0, 4.0, 2.0])


def stub_bicgstab(monkeypatch, residual):
    """`_bicgstab` that returns the values of LINE (a fresh array each time), the residual given and one iteration; the calls are noted."""
    calls = []

    def fake(matvec, rhs, start, tol, limit):
        calls.append((start.copy(), tol, limit))
        return LINE_VALUES.copy() * (1.0 + len(calls)), residual, 1  # (a different array each call, so that a restart is seen to start from the last)

    monkeypatch.setattr(ps, "_bicgstab", fake)
    return calls


@pytest.mark.parametrize(
    "residual,runs",
    [
        (9.5e-13, 1),  # below 10 tol: reached, no restart
        (10 * 1e-13, 1),  # exactly 10 tol (the same expression as in the module): reached
        (10.5e-13, 1 + ps.BICGSTAB_RESTARTS),  # a little above: not reached, every restart is made
        (1e-10, 1 + ps.BICGSTAB_RESTARTS),
        (0.5, 1 + ps.BICGSTAB_RESTARTS),
    ],
)
def test_a_run_that_leaves_a_residual_up_to_ten_times_the_tolerance_is_not_started_again(monkeypatch, residual, runs):
    work, leave = prepared(LINE)
    calls = stub_bicgstab(monkeypatch, residual)
    info = {}

    evaluate_policy(work, leave, LINE_POLICY, np.zeros(6), 4, 1e-13, info)

    assert len(calls) == runs
    assert info["linear_iterations"] == runs  # one iteration for each run, summed
    assert all(tol == 1e-13 and limit == ps.BICGSTAB_ITERATIONS for _, tol, limit in calls)
    assert calls[0][0].tolist() == [0.0] * 5  # the first run starts from the values given
    for before, (start, _, _) in zip(range(1, len(calls)), calls[1:]):  # each restart starts from the iterate of the run before it
        assert start.tolist() == (LINE_VALUES * (1.0 + before)).tolist()


@pytest.mark.parametrize(
    "residual,dense",
    [(0.5 * ps.DENSE_FALLBACK_RESIDUAL, False), (ps.DENSE_FALLBACK_RESIDUAL, False), (ps.DENSE_FALLBACK_RESIDUAL * (1 + 1e-9), True), (1e-3, True)],
)
def test_the_exact_solve_is_made_for_a_residual_above_its_threshold_and_not_at_it(monkeypatch, residual, dense):
    work, leave = prepared(LINE)
    stub_bicgstab(monkeypatch, residual)
    info = {}

    values = evaluate_policy(work, leave, LINE_POLICY, np.zeros(6), 4, 1e-13, info)

    assert ("linear_cycles" in info) is dense
    assert (info["linear_residual"] <= 1e-14) if dense else (info["linear_residual"] == residual)  # the residual of the values taken
    if dense:
        assert info["linear_residual_iterate"] == residual
        assert values.tolist() == pytest.approx([10.0, 8.0, 6.0, 4.0, 2.0, 0.0], rel=1e-13)  # the dense solve replaced the stub's values
    else:
        assert values[:5].tolist() == (LINE_VALUES * (1.0 + 1 + ps.BICGSTAB_RESTARTS)).tolist()  # the stub's last iterate, kept


def stub_certify(monkeypatch, quotient_bound, whole_bound):
    """`certify` that is settled and gives `quotient_bound` when called by `solve_graph` (with a `work`), `whole_bound` for the whole graph."""

    def fake(graph, value, solved, work=None):
        return Certificate(quotient_bound if work is not None else whole_bound, 1.0, 1.0, 0.0, True)

    monkeypatch.setattr(ps, "certify", fake)


ACCEPTED = 0.5  # a power of two, so that "just above" is one step of the float above it


@pytest.mark.parametrize(
    "bound,accepted",
    [(0.25, True), (ACCEPTED, True), (math.nextafter(ACCEPTED, 1.0), False), (1.0, False), (INF, False), (math.nan, False)],
)
def test_solve_graph_accepts_a_bound_up_to_the_one_accepted_and_refuses_the_next_float(monkeypatch, bound, accepted):
    stub_certify(monkeypatch, bound, 0.0)

    if accepted:
        assert solve_graph(GEO, accept_bound=ACCEPTED).certificate.bound == bound
    else:
        with pytest.raises(ConvergenceError, match="certifies only a relative bound") as refused:
            solve_graph(GEO, accept_bound=ACCEPTED)
        assert refused.value.error_bound == bound or (math.isnan(bound) and math.isnan(refused.value.error_bound))


@pytest.mark.parametrize(
    "bound,accepted",
    [(0.25, True), (ACCEPTED, True), (math.nextafter(ACCEPTED, 1.0), False), (1.0, False), (INF, False), (math.nan, False)],
)
def test_solve_packed_accepts_a_bound_of_the_whole_graph_up_to_the_one_accepted_and_refuses_the_next_float(monkeypatch, bound, accepted):
    stub_certify(monkeypatch, 0.0, bound)  # the quotient's certificate is perfect: only the check on the whole graph can refuse

    if accepted:
        assert solve_packed(GEO, accept_bound=ACCEPTED).error_bound == bound
    else:
        with pytest.raises(ConvergenceError, match="do not satisfy the Bellman equation of the whole graph") as refused:
            solve_packed(GEO, accept_bound=ACCEPTED)
        assert refused.value.error_bound == bound or (math.isnan(bound) and math.isnan(refused.value.error_bound))


# The rounding allowance of the step that improves a policy: an action takes the place of the current one only when its Q is lower by more
# than (terms + 2) eps of the current Q, `terms` being the most outcomes of an action of the state plus one. State 0 has the action X (cost 1/2,
# the goal or state 2, half and half), which the start policy takes (cheapest luckiest path), and the action Y (cost y, the goal). The values
# are set by the test: state 2 is worth 1, so X has Q = 1/2 + 1/2 * 1 = 1 and Y has Q = y. X has two outcomes, so terms = 3 and the
# allowance is 5 eps of 1: Y replaces X only for y < 1 - 5 eps (all these numbers are exact in float, 1 - k eps / 2 being a float below 1).
# A gap of 4 or 4.5 eps is under the allowance of 5 (a smaller allowance, from the fewest outcomes of the state, 4 eps, or from a smaller
# constant, would let it through), 5 is exactly at it (the rule is strict), 5.5 and 6 are over it (a larger one, 6 eps, would refuse them).


@pytest.mark.parametrize("gap,improves", [(1, False), (4, False), (4.5, False), (5, False), (5.5, True), (6, True), (7, True), (40, True)])
def test_an_action_replaces_the_current_one_only_when_better_by_more_than_the_rounding_of_its_sum(monkeypatch, gap, improves):
    cost_y = 1.0 - gap * EPS
    graph = build(
        (False, [(0.5, [(1, 1), (2, 1)]), (cost_y, [(1, 1)])]),
        (True, []),
        (False, [(1.0, [(1, 1)])]),
    )
    monkeypatch.setattr(ps, "evaluate_policy", lambda work, leave, policy, start, dense_limit, tol, info: np.array([1.0, 0.0, 1.0]))
    info = {}

    core = solve_graph(graph, info=info)

    assert core.action.tolist() == [1 if improves else 0, -1, 2]  # (action numbers: X 0, Y 1, the action of state 2 is the third, 2)
    assert info["rounds"] == (2 if improves else 1)


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


def test_a_state_with_one_action_takes_it_through_solve_packed():
    graph = build((False, [(1.0, [(1, 1)])]), (True, []))
    solved = solve_packed(graph)

    assert solved.action.tolist() == [0, -1]


def lift_world():
    """States 0 and 1 are one class (0) and state 2 the goal (class 1).

    State 0 has a0 (cost 3, kernel P), a1 and a2 (cost 2, kernels Q and Q2, two copies of one distribution) and state 1 has a3 (cost 7,
    kernel R). `kernel_map` sends P to the class distribution 0 and Q, Q2 and R to the class distribution 1. The quotient has the one live class
    with its two distributions, so its action 0 is the class distribution 0 and its action 1 the class distribution 1.
    """
    builder = PackedBuilder()
    p = builder.kernel([2], [1])
    q = builder.kernel([2, 0], [1, 1])
    q2 = builder.kernel([2, 0], [1, 1])
    builder.action(0, 3.0, p)
    builder.action(1, 2.0, q)
    builder.action(2, 2.0, q2)
    builder.close_state(False)
    r = builder.kernel([2, 1], [1, 1])
    builder.action(3, 7.0, r)
    builder.close_state(False)
    builder.close_state(True)
    reduced = PackedBuilder()
    reduced.action(0, 3.0, reduced.kernel([1], [1]))
    reduced.action(1, 2.0, reduced.kernel([1, 0], [1, 1]))
    reduced.close_state(False)
    reduced.close_state(True)
    return builder.build(), reduced.build(), np.array([0, 1, 1, 1], dtype=np.int32), np.array([0, 0, 1])


def test_lift_policy_gives_each_state_its_cheapest_action_in_the_distribution_chosen_for_its_class_the_first_on_a_tie():
    graph, reduced, kernel_map, cls = lift_world()

    lifted = lift_policy(graph, reduced, kernel_map, cls, np.array([1, -1]))  # the class takes its action 1: the class distribution 1

    # state 0: a1 and a2 are in the distribution and cost 2 each: the first, a1; a0 (distribution 0) is not taken. State 1: a3, its only action
    # (the dear one: 7 is no reason to leave the distribution of the class). The goal: no action
    assert lifted.tolist() == [1, 3, -1]


def test_lift_policy_takes_the_other_distribution_when_the_class_does_and_gives_no_action_to_a_state_that_has_none_in_it():
    graph, reduced, kernel_map, cls = lift_world()

    lifted = lift_policy(graph, reduced, kernel_map, cls, np.array([0, -1]))  # the class distribution 0: only a0 of state 0 is in it

    assert lifted.tolist() == [0, -1, -1]  # state 1 has no action in the distribution: it is left without one, not given another


def test_lift_policy_gives_no_action_to_the_states_of_a_class_that_takes_none():
    graph, reduced, kernel_map, cls = lift_world()

    assert lift_policy(graph, reduced, kernel_map, cls, np.array([-1, -1])).tolist() == [-1, -1, -1]


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
