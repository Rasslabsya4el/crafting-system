"""The one linear solve (`solver/_packed_linear.py`, ticket #841): its pieces on systems small enough to solve by hand, and the stiff chains of
#700, #699 and #671 against `Fraction` elimination.

* The subtraction-free inverse (GTH, #700): a two-state ring gone round 1e10, 1e13 and 1e16 times matches `Fraction` elimination to 1e-12, where a
  dense LU inverse of `I - P` is 8e-8 off at 1e10 and singular at 1e16.
* The choice of a solve by what bounds its error (#699): an iterate with a residual of 1e-10 on a system whose answer is 1e10 times its right-hand
  side goes to the exact solve by the cycles, and the values are then those of `Fraction` elimination.
* Stagnation read from the run (#671): a stiff policy of 100,000 states reaches the exact solve at the iteration's first stagnation, one run, not
  4,000 iterations and three restarts.
* BiCGSTAB itself (moved here from `test_solver_packed_light.py`): its stopping steps against the textbook recurrence worked in `Fraction`s.

No expected number here is read off the code under test.
"""

import math
import sys
from fractions import Fraction

import numpy as np
import pytest

from crafting_system.solver import PackedBuilder
from crafting_system.solver import _packed_linear as lin
from crafting_system.solver import _packed_solve as ps
from crafting_system.solver._packed_chain import ChainSolver, CyclesTooTangled

EPS = sys.float_info.epsilon


def solve_exactly(rows: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    """Gauss-Jordan elimination in `Fraction`s."""
    n = len(rhs)
    table = [[*rows[i], rhs[i]] for i in range(n)]
    for c in range(n):
        pivot = next(r for r in range(c, n) if table[r][c] != 0)
        table[c], table[pivot] = table[pivot], table[c]
        table[c] = [v / table[c][c] for v in table[c]]
        for r in range(n):
            if r != c and table[r][c] != 0:
                table[r] = [a - table[r][c] * b for a, b in zip(table[r], table[c])]
    return [table[i][n] for i in range(n)]


def relative(found: float, exact: Fraction) -> float:
    return float(abs(Fraction(float(found)) - exact) / abs(exact))


# --- the subtraction-free inverse --------------------------------------------------------------------------------------------------------------------


def test_the_inverse_of_a_two_state_chain_is_the_one_worked_by_hand():
    # off = [[0, 1/2], [1/4, 0]], exits 1/2 and 3/4: I - P = [[1, -1/2], [-1/4, 1]], determinant 7/8, inverse 8/7 [[1, 1/2], [1/4, 1]]
    inverse = lin.gth_inverse(np.array([[0.0, 0.5], [0.25, 0.0]]), np.array([0.5, 0.75]))

    assert inverse == pytest.approx(np.array([[8 / 7, 4 / 7], [2 / 7, 8 / 7]]), rel=1e-15)


def test_the_diagonal_given_is_not_read_and_a_state_alone_is_one_over_its_exit():
    with_diagonal = lin.gth_inverse(np.array([[0.9, 0.5], [0.25, 0.3]]), np.array([0.5, 0.75]))  # the diagonal is the exits' business

    assert with_diagonal == pytest.approx(np.array([[8 / 7, 4 / 7], [2 / 7, 8 / 7]]), rel=1e-15)
    assert lin.gth_inverse(np.array([[0.0]]), np.array([0.25])).tolist() == [[4.0]]


def test_a_stack_of_components_is_inverted_each_as_alone_and_a_closed_class_has_no_finite_inverse():
    rng = np.random.default_rng(5)
    off = rng.random((6, 5, 5)) * (rng.random((6, 5, 5)) < 0.6)
    exit = rng.random((6, 5)) * 0.3 + 0.01
    stacked = lin.gth_inverse(off, exit)
    for k in range(6):
        b = off[k] - np.diag(np.diag(off[k]))
        matrix = np.diag(b.sum(axis=1) + exit[k]) - b
        assert stacked[k] == pytest.approx(np.linalg.inv(matrix), rel=1e-12)
    closed = lin.gth_inverse(np.array([[0.0, 1.0], [1.0, 0.0]]), np.array([0.0, 0.0]))  # two states that send each other on for ever
    assert not np.all(np.isfinite(closed))


@pytest.mark.parametrize("size", [3, 17, 64, 301])
def test_a_random_chain_is_inverted_as_lu_inverts_it_when_it_is_far_from_stiff(size):
    rng = np.random.default_rng(size)
    off = rng.random((size, size)) * (rng.random((size, size)) < 0.2)
    np.fill_diagonal(off, 0.0)
    exit = rng.random(size) * 0.5 + 0.05
    total = off.sum(axis=1) + exit
    off, exit = off / total[:, None], exit / total

    assert lin.gth_inverse(off, exit) == pytest.approx(np.linalg.inv(np.eye(size) - off), rel=1e-11, abs=1e-14)


def ring_rows(weight: int):
    """The ring of #700: A (cost 1) and B (cost 2) send each other on with `weight` against 1 into the goal. `(off, exit, costs, exact values)`."""
    p = Fraction(weight, weight + 1)
    exact = [(1 + 2 * p) / (1 - p * p), (2 + p) / (1 - p * p)]  # x_A = 1 + p x_B, x_B = 2 + p x_A
    off = np.array([[0.0, float(p)], [float(p), 0.0]])
    return off, np.array([float(1 - p)] * 2), np.array([1.0, 2.0]), exact


@pytest.mark.parametrize("weight", [10**10, 10**13, 10**16])
def test_a_ring_gone_round_up_to_1e16_times_is_inverted_to_the_rounding_of_its_sums(weight):
    off, exit, costs, exact = ring_rows(weight)

    values = lin.gth_inverse(off, exit) @ costs

    assert relative(values[0], exact[0]) <= 1e-12 and relative(values[1], exact[1]) <= 1e-12
    if weight == 10**10:  # the dense LU inverse of I - P, for the record: the cancellation in 1 - p costs it 8 digits
        assert relative(np.linalg.solve(np.eye(2) - off, costs)[0], exact[0]) > 1e-9


# --- the measures -------------------------------------------------------------------------------------------------------------------------------------


OFF = np.array([[0.0, 0.5], [0.25, 0.0]])
RHS = np.array([1.0, 2.0])
EXACT = np.array([2.0 / 0.875, 2.0 + 2.0 / 0.875 / 4.0])  # x0 = 1 + x1 / 2 and x1 = 2 + x0 / 4


def test_the_backward_error_is_the_rounding_for_a_good_answer_and_about_one_for_a_wrong_one():
    assert lin.backward_error(OFF.__matmul__, RHS, EXACT) <= 4 * EPS
    assert lin.backward_error(OFF.__matmul__, RHS, EXACT + 1.0) > 0.1
    assert lin.backward_error(OFF.__matmul__, RHS, np.array([math.nan, 1.0])) == math.inf


def test_the_forward_estimate_holds_the_true_error_of_an_answer_and_is_tiny_for_a_good_one():
    solve_with = lambda s: np.linalg.solve(np.eye(2) - OFF, s)  # noqa: E731
    assert lin.forward_estimate(OFF.__matmul__, RHS, EXACT, lin.backward_error(OFF.__matmul__, RHS, EXACT), solve_with) < 1e-14
    for wrong in (1e-9, 1e-6, 1e-3):  # an answer off by a known relative amount: the estimate must cover it
        perturbed = EXACT * np.array([1.0 + wrong, 1.0 - wrong])
        measured = lin.backward_error(OFF.__matmul__, RHS, perturbed)
        assert lin.forward_estimate(OFF.__matmul__, RHS, perturbed, measured, solve_with) >= wrong
        assert lin.rhs_bound(OFF.__matmul__, RHS, perturbed) >= wrong


def test_the_amplification_of_a_ring_is_the_number_of_rounds_and_a_state_of_value_zero_fed_has_none():
    # x = c + T x on the ring at weight w: x is about w times c, and the scale s = |x| + T|x| + |c| is about 2 x, so (I - T)^-1 s is about 2 w x
    off, _, costs, _ = ring_rows(10**6)
    x = np.linalg.solve(np.eye(2) - off, costs)

    found = lin.amplification(off.__matmul__, costs, x, lambda s: np.linalg.solve(np.eye(2) - off, s))

    assert 1e6 < found < 4e6
    assert lin.amplification(OFF.__matmul__, RHS, np.array([0.0, 1.0]), lambda s: np.linalg.solve(np.eye(2) - OFF, s)) == math.inf  # a state of value 0, fed
    assert lin.amplification(OFF.__matmul__, RHS, EXACT, lambda s: np.zeros(2)) == math.inf  # a solve that failed proves nothing
    assert lin.amplification(OFF.__matmul__, RHS, EXACT, lambda s: 0.4 * np.linalg.solve(np.eye(2) - OFF, s)) == math.inf  # (I - T) y is 0.4 s: short by more than half


# --- BiCGSTAB ------------------------------------------------------------------------------------------------------------------------------------------

A3 = np.array([[4.0, 1.0, 0.0], [-1.0, 3.0, 1.0], [2.0, 0.0, 5.0]])
X3 = np.array([1.0, -2.0, 3.0])


def bicgstab3(matvec, b, x0, tol, limit):
    """`(x, relative residual, steps)` of `lin.bicgstab`."""
    x, residual, steps, _ = lin.bicgstab(matvec, b, x0, tol, limit)
    return x, residual, steps


def residual_of(matrix, b, x):
    return float(np.linalg.norm(b - matrix @ x) / np.linalg.norm(b))


def test_bicgstab_solves_a_three_by_three_system_in_at_most_three_steps():
    b = A3 @ X3
    x, relative_residual, steps = bicgstab3(lambda v: A3 @ v, b, np.zeros(3), 1e-13, 100)

    assert x == pytest.approx(X3, abs=1e-12)
    assert 1 <= steps <= 3  # BiCGSTAB ends in n steps in exact arithmetic
    assert relative_residual <= 1e-12


def test_bicgstab_reports_the_residual_of_the_iterate_it_returns():
    b = A3 @ X3
    for limit in (1, 2):
        x, relative_residual, steps = bicgstab3(lambda v: A3 @ v, b, np.zeros(3), 1e-30, limit)

        assert steps == limit  # not converged: it ran the steps it was given
        assert relative_residual == pytest.approx(residual_of(A3, b, x), rel=1e-6)
        assert 0.0 < relative_residual < 1.0


def test_each_bicgstab_step_lowers_the_residual_of_a_well_conditioned_system():
    b = A3 @ X3
    residuals = [bicgstab3(lambda v: A3 @ v, b, np.zeros(3), 1e-30, limit)[1] for limit in (1, 2, 3)]

    assert residuals[0] > residuals[1] > residuals[2]
    assert residuals[2] < 1e-12


def test_bicgstab_scales_the_stopping_test_by_the_size_of_the_right_hand_side():
    b = (A3 @ X3) * 1e6
    x, _, steps = bicgstab3(lambda v: A3 @ v, b, np.zeros(3), 1e-13, 100)

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


def test_bicgstab_stops_at_the_first_half_or_whole_step_whose_residual_is_below_the_tolerance_times_the_size_of_the_right_hand_side(monkeypatch):
    # the stopping steps and the residuals they leave are those of the reference above (not read off the module); a tolerance just above
    # and just below each of them is tried, and 0.3, which only the first half step (x + alpha p) meets before the whole step is made
    # scaling b by a million changes nothing. (The second step halves nothing, 0.066 to 0.068: no stagnation is read from one step.)
    monkeypatch.setattr(lin, "STALL", 100)
    reference = reference_residuals(A3, A3 @ X3)
    tolerances = [0.3] + [factor * value for _, value in reference if value > 1e-12 for factor in (0.99, 1.01)]  # (not 0: a float residual is never 0)
    seen_steps = set()
    for scale in (1.0, 1e6):
        b = (A3 @ X3) * scale
        for tol in tolerances:
            expected_steps, expected_residual = next((step, value) for step, value in reference if value <= tol)
            x, relative_residual, taken = bicgstab3(lambda v: A3 @ v, b, np.zeros(3), tol, 100)

            assert taken == expected_steps, (scale, tol)
            assert relative_residual == pytest.approx(expected_residual, rel=1e-6, abs=1e-14), (scale, tol)
            assert relative_residual <= tol and relative_residual == pytest.approx(residual_of(A3, b, x), rel=1e-6, abs=1e-14)
            seen_steps.add(taken)
    assert seen_steps == {1, 2, 3}  # the tolerances reach every number of steps: the test is not one-sided


def test_bicgstab_started_at_the_answer_takes_no_step():
    b = A3 @ X3

    x, relative_residual, steps = bicgstab3(lambda v: A3 @ v, b, X3.copy(), 1e-13, 100)

    assert steps == 0 and relative_residual <= 1e-15 and (x == X3).all()


def test_bicgstab_of_a_one_by_one_system_ends_in_the_half_step():
    x, relative_residual, steps = bicgstab3(lambda v: 2.0 * v, np.array([2.0]), np.zeros(1), 1e-13, 100)

    assert x.tolist() == [1.0] and relative_residual == 0.0 and steps == 1


def test_bicgstab_stops_at_the_step_limit():
    b = A3 @ X3

    assert bicgstab3(lambda v: A3 @ v, b, np.zeros(3), 1e-30, 2)[2] == 2


SKEW = np.array([[0.0, 1.0], [-1.0, 0.0]])  # v . A v = 0 for every v: the first step divides by zero, the method can make no progress


def test_bicgstab_that_never_halves_its_residual_has_stagnated_after_stall_steps_and_returns_the_start(monkeypatch):
    monkeypatch.setattr(lin, "STALL", 7)  # with no flat to measure against, the run's first flat may last 7 x 7 steps

    x, relative_residual, steps, stagnated = lin.bicgstab(lambda v: SKEW @ v, np.array([1.0, 2.0]), np.zeros(2), 1e-13, 1000)

    assert steps == 49 and stagnated and relative_residual == 1.0 and x.tolist() == [0.0, 0.0]


def test_bicgstab_that_cannot_progress_is_cut_by_the_step_limit_when_that_is_sooner_and_that_is_no_stagnation(monkeypatch):
    monkeypatch.setattr(lin, "STALL", 50)

    _, _, steps, stagnated = lin.bicgstab(lambda v: SKEW @ v, np.array([1.0, 2.0]), np.zeros(2), 1e-13, 4)

    assert steps == 4 and not stagnated


def test_a_run_has_stagnated_when_its_flat_is_stall_times_the_longest_flat_it_came_out_of(monkeypatch):
    monkeypatch.setattr(lin, "STALL", 6)
    # no flat yet (a warm start of R14 that sits at 7.1e-6 for its first 6 steps, then falls to 1e-14 by step 28): 6 x 6 = 36 steps, not 6
    assert not lin.stalled(6, 0, 0) and not lin.stalled(35, 0, 0) and lin.stalled(36, 0, 0)
    # fast falls with flats of at most 3 steps, the last halving at step 10, then flat (R14: 1.4e-2 to 7.5e-6 by step 10, 5e-14 by 25): a flat
    # under 6 counts as 6, so 36 steps after step 10, where a pace of under a step per halving stopped it at step 14
    assert not lin.stalled(14, 10, 3) and not lin.stalled(45, 10, 3) and lin.stalled(46, 10, 3)
    # a run that came out of a flat of 15 steps waits 6 x 15 = 90 steps on its next one
    assert not lin.stalled(129, 40, 15) and lin.stalled(130, 40, 15)
    # (the 100,000 stiff states of #671, at 0.94 from step 2 on, are the first case: they reach the exact solve at step 36, in the test below)


# --- the solve: dense, iterate, exact ------------------------------------------------------------------------------------------------------------------


class DenseTerms(lin.Terms):
    """A small system given as a matrix; `exact` is LU of it (a stand-in for the cycles of the chain) or None."""

    def __init__(self, off: np.ndarray, exact: bool = True, tangled: bool = False):
        self.off, self.n, self._exact, self._tangled = off, len(off), exact, tangled

    def apply(self, v):
        return self.off @ v

    def dense(self):
        return self.off

    def exact(self):
        if self._tangled:
            raise CyclesTooTangled("putting back 3 distinct cut rows of 5 states needs 123 cells, past the 100 the memory of a run allows", 3, 123, 100)
        if not self._exact:
            return None
        system = np.eye(self.n) - self.off

        class Exact:
            q = 0

            def solve(self, b):
                return np.linalg.solve(system, b)

        return Exact()


def line(n: int) -> np.ndarray:
    """`n` states in a row, each passing on all of what leaves it: x_i = 1 + x_(i+1), so x_i = n - i."""
    off = np.zeros((n, n))
    off[np.arange(n - 1), np.arange(1, n)] = 1.0
    return off


def test_a_small_system_is_solved_dense_and_taken_on_its_forward_estimate():
    found = lin.solve(DenseTerms(line(5)), np.ones(5))

    assert found.how == "dense" and found.good and found.x.tolist() == pytest.approx([5.0, 4.0, 3.0, 2.0, 1.0], rel=1e-15)
    assert found.forward <= 1e-13 and found.backward <= 1e-15 and found.iterate is None  # (the rounding of 8 eps times an amplification of about 10)


def test_above_the_dense_limit_the_iterate_is_taken_when_its_forward_estimate_is_small():
    found = lin.solve(DenseTerms(line(5)), np.ones(5), dense_limit=4)

    assert found.how == "iterate" and found.good and found.x.tolist() == pytest.approx([5.0, 4.0, 3.0, 2.0, 1.0], rel=1e-10)
    assert 1 <= found.iterations <= 10 and not found.stagnated


def test_an_iterate_whose_forward_estimate_is_above_the_tolerance_goes_to_the_exact_solve_at_once(monkeypatch):
    monkeypatch.setattr(lin, "BICGSTAB_ITERATIONS", 1)  # one step: far from the answer

    found = lin.solve(DenseTerms(line(5)), np.ones(5), dense_limit=4)

    assert found.how == "exact" and found.good and found.x.tolist() == pytest.approx([5.0, 4.0, 3.0, 2.0, 1.0], rel=1e-15)
    assert found.iterations == 1 and found.iterate is not None and found.iterate[2] > lin.ACCEPT_ERROR  # no restart: the exact solve was made at once


def test_when_the_exact_solve_does_not_fit_its_cost_is_said_and_the_best_iterate_is_returned_not_taken(monkeypatch):
    monkeypatch.setattr(lin, "BICGSTAB_ITERATIONS", 1)

    found = lin.solve(DenseTerms(line(5), tangled=True), np.ones(5), dense_limit=4)

    assert found.how == "iterate" and not found.good and "needs 123 cells" in found.why
    assert found.cost == {"rows": 3, "cells": 123, "allowed": 100}


def test_a_stagnated_iterate_with_no_exact_solve_goes_on_from_its_best_iterate(monkeypatch):
    real = lin.bicgstab
    first = []

    def once(matvec, b, x0, tol, max_iter=None):
        if tol == 1e-13 and not first:
            first.append(1)
            return x0.copy(), 1.0, 2, True  # the first run stagnates at once, where it started
        return real(matvec, b, x0, tol, max_iter)

    monkeypatch.setattr(lin, "bicgstab", once)

    found = lin.solve(DenseTerms(line(5), exact=False), np.ones(5), dense_limit=4)

    assert found.how == "iterate" and found.good and found.x.tolist() == pytest.approx([5.0, 4.0, 3.0, 2.0, 1.0], rel=1e-10)
    assert "no exact solve" in found.why and found.iterations >= 3  # the stagnated run's two steps and the run that went on


def test_a_run_whose_recurrence_drifted_from_its_true_residual_is_started_again_not_sent_to_the_exact_solve(monkeypatch):
    # the first run stops by its recurrence (no stagnation) with a TRUE residual of 1e-6, far above ten times the aim of 1e-13: the drift of #584.
    # Main restarted such a run, and R04 and R14 reach 1e-16 so; sending it to the exact solve instead cost R14 20 s an evaluation (heavy run 43371506754)
    real = lin.bicgstab
    starts = []

    def drifted(matvec, b, x0, tol, max_iter=None):
        if tol != 1e-13:
            return real(matvec, b, x0, tol, max_iter)
        starts.append(x0.copy())
        if len(starts) == 1:
            x = np.array([5.0, 4.0, 3.0, 2.0, 1.0]) * (1.0 + 1e-6)
            return x, 1e-6, 7, False
        return real(matvec, b, x0, tol, max_iter)

    monkeypatch.setattr(lin, "bicgstab", drifted)

    found = lin.solve(DenseTerms(line(5)), np.ones(5), dense_limit=4)

    assert found.how == "iterate" and found.good and found.iterate is None  # no exact solve was made
    assert len(starts) == 2 and starts[1].tolist() == pytest.approx([5.0 * (1 + 1e-6), 4.0 * (1 + 1e-6), 3.0 * (1 + 1e-6), 2.0 * (1 + 1e-6), 1.0 + 1e-6])
    assert found.x.tolist() == pytest.approx([5.0, 4.0, 3.0, 2.0, 1.0], rel=1e-12) and found.iterations >= 7


# --- stiff chains of the planner: #700, #699, #671 -----------------------------------------------------------------------------------------------------


def ring_graph(weight: int):
    """`(graph, policy)`: A (cost 1) and B (cost 2) send each other on with `weight` against 1 into the goal (state 2)."""
    builder = PackedBuilder()
    builder.action(0, 1.0, builder.kernel([1, 2], [weight, 1]))
    builder.close_state(False)
    builder.action(1, 2.0, builder.kernel([0, 2], [weight, 1]))
    builder.close_state(False)
    builder.close_state(True)
    return builder.build(), np.array([0, 1, -1])


def skeel(weight: int) -> float:
    """The Skeel condition `|| |A^-1| |A| |x| || / ||x||` of the ring's system, in floats from its exact entries."""
    p = weight / (weight + 1)
    a = np.array([[1.0, -p], [-p, 1.0]])
    inverse = np.array([[1.0, p], [p, 1.0]]) / (2.0 / (weight + 1) - 1.0 / (weight + 1) ** 2)  # 1 - p^2 = (2 w + 1) / (w + 1)^2
    x = np.array([float(v) for v in ring_rows(weight)[3]])
    return float(np.max(np.abs(inverse) @ np.abs(a) @ np.abs(x)) / np.max(np.abs(x)))


@pytest.mark.parametrize("weight", [10**10, 10**13, 10**16])
@pytest.mark.parametrize("dense_limit", [0, 100])
def test_the_evaluation_of_a_ring_matches_fraction_elimination_and_its_bound_is_its_condition_times_the_rounding(weight, dense_limit):
    graph, policy = ring_graph(weight)
    work = ps.Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    info: dict = {}

    values = ps.evaluate_policy(work, leave, policy, np.zeros(work.n), dense_limit, 1e-13, info)

    exact = ring_rows(weight)[3]
    error = max(relative(values[0], exact[0]), relative(values[1], exact[1]))
    assert error <= 1e-12  # #700: an LU inverse was 8e-8 off at 1e10
    assert info["linear_cycles"] == 1  # neither LU nor BiCGSTAB follows the ring: its forward estimate sends it to the cycles
    assert info["linear_forward"] <= 64 * EPS * skeel(weight)  # the estimate is the rounding times the condition the system really has, not more


def two_loops_and_a_dear_state(rounds: int, dear_cost: float):
    """`(graph, policy)`: states a and b send each other on with the weight `rounds` against 1 for the goal (cost 1 each), `c` costs `dear_cost` and finishes."""
    builder = PackedBuilder()
    builder.action(0, 1.0, builder.kernel([1, 3], [rounds, 1]))
    builder.close_state(False)
    builder.action(1, 1.0, builder.kernel([0, 3], [rounds, 1]))
    builder.close_state(False)
    builder.action(2, dear_cost, builder.kernel([3], [1.0]))
    builder.close_state(False)
    builder.close_state(True)
    return builder.build(), np.array([0, 1, 2, -1])


def test_an_iterate_with_a_residual_of_1e_10_on_a_system_whose_answer_is_1e10_times_its_right_hand_side_goes_to_the_exact_solve(monkeypatch):
    """#699: the residual is 1e-10 of the largest right-hand side and the iterate is 1e-5 off; its residual alone would have taken it."""
    rounds, dear = 10**10, 1e5
    graph, policy = two_loops_and_a_dear_state(rounds, dear)
    work = ps.Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    exact = [Fraction(rounds + 1), Fraction(rounds + 1), Fraction(dear)]  # x = 1 + rounds / (rounds + 1) x
    moved = np.array([1.0, 1.0, 0.0]) * (1e-10 * dear * rounds)  # along the direction the system hardly feels

    def stalled(matvec, rhs, x0, tol, max_iter=None):
        if tol != 1e-13:  # (the iteration that measures the amplification is left as it is)
            return real(matvec, rhs, x0, tol, max_iter)
        x = np.array([float(v) for v in exact]) + moved
        return x, float(np.linalg.norm(rhs - matvec(x)) / np.linalg.norm(rhs)), 1, True

    real = lin.bicgstab
    monkeypatch.setattr(lin, "bicgstab", stalled)
    info: dict = {}

    values = ps.evaluate_policy(work, leave, policy, np.zeros(work.n), 0, 1e-13, info)

    assert info["linear_residual_iterate"] == pytest.approx(1e-10, rel=0.5)  # the iterate the old rule took (its residual was within 1e-10)
    assert info["linear_forward_iterate"] > 1e-6 and info["linear_cycles"] == 1
    assert max(relative(values[i], exact[i]) for i in range(3)) <= 1e-12  # the exact values, not the iterate 1e-5 off


def stiff_rings(blocks: int, ring_weight: int):
    """`(graph, policy)`: `blocks` rings of three states (each going round with `ring_weight` against 1 into the block's reroll) and three shared rerolls
    that send a run to a random ring or, one time in a hundred, to the goal (the policy of `test_solver_packed_stiff.py`, at any size)."""
    builder = PackedBuilder()
    goal = 4 * blocks
    kernels = []
    for k in range(3):
        weights = [1 + (i * (k + 2)) % 7 for i in range(blocks)]
        kernels.append(builder.kernel([3 * i for i in range(blocks)] + [goal], weights + [sum(weights) // 99 + 1]))
    tag = 0
    for j in range(blocks):
        for r in range(3):
            builder.action(tag, float(1 + j % 5), builder.kernel([3 * j + (r + 1) % 3, 3 * blocks + j], [ring_weight, 1]))
            builder.close_state(False)
            tag += 1
    for j in range(blocks):
        builder.action(tag, 2.0, kernels[j % 3])
        builder.close_state(False)
        tag += 1
    builder.close_state(True)
    return builder.build(), np.append(np.arange(4 * blocks), -1)


def test_a_stiff_policy_of_100000_states_reaches_the_exact_solve_at_the_first_stagnation_of_the_iteration():
    """#671: one run of BiCGSTAB, stopped where it first stagnates; before, 4,000 iterations a run and three restarts were spent first."""
    graph, policy = stiff_rings(25_000, 10**13)
    work = ps.Work(graph)
    leave = work.nonself_sums(np.ones(work.n))
    runs = []
    real = lin._bicgstab_run

    def spy(matvec, b, x0, tol, max_iter):
        found = real(matvec, b, x0, tol, max_iter)
        runs.append((tol, found[1], found[4]))
        return found

    lin._bicgstab_run, kept = spy, lin._bicgstab_run
    info: dict = {}
    try:
        values = ps.evaluate_policy(work, leave, policy, np.zeros(work.n), ps.DENSE_LIMIT, 1e-13, info)
    finally:
        lin._bicgstab_run = kept

    assert info["policy_states"] == 100_000 and info["linear_cycles"] == 1 and info["linear_cut_rows"] == 3
    main = [(iterations, stagnated) for tol, iterations, stagnated in runs if tol == 1e-13]
    assert len(main) == 1 and main[0][1]  # one run, which stopped at its first stagnation: no restart before the exact solve
    assert info["linear_iterations"] == main[0][0] <= 200
    assert info["linear_backward_error"] <= 1e-13 and np.all(np.isfinite(values)) and np.all(values[:-1] > 0.0)


# --- the transposed solve by the cycles ----------------------------------------------------------------------------------------------------------------


def test_the_transposed_solve_by_the_cycles_is_the_transpose_of_the_solve():
    # a chain of 9 states: 0..5 take their own rows, 6, 7 and 8 take one shared row (a reroll), so the Woodbury step is made
    rng = np.random.default_rng(3)
    n = 9
    own = {s: (rng.choice(n, size=3, replace=False), rng.random(3)) for s in range(6)}
    shared_cols, shared_vals = np.array([0, 2, 4, 7]), np.array([0.3, 0.2, 0.25, 0.15])
    q = np.zeros((n, n))
    leak = np.zeros(n)
    ptr, col, weight = [0], [], []
    for s in range(6):
        cols, vals = own[s]
        vals = vals / vals.sum() * 0.9  # 0.1 of each row leaks out of the chain
        q[s, cols] += vals
        leak[s] = 0.1
        col.extend(cols.tolist())
        weight.extend(vals.tolist())
        ptr.append(len(col))
    for s in (6, 7, 8):
        q[s, shared_cols] += shared_vals
        leak[s] = 0.1
        ptr.append(len(col))
    leave = 1.0 - np.diag(q)
    leak_shared = 1.0 - shared_vals.sum()
    shared_of = np.array([-1] * 6 + [0, 0, 0])
    solver = ChainSolver(n, np.array(ptr), np.array(col), np.array(weight), leave, leak, shared_of, [(shared_cols, shared_vals, leak_shared)])
    p = (q - np.diag(np.diag(q))) / leave[:, None]
    b = rng.random(n)

    assert solver.q == 1
    assert solver.solve(b) == pytest.approx(np.linalg.solve(np.eye(n) - p, b), rel=1e-12)
    assert solver.solve_transposed(b) == pytest.approx(np.linalg.solve((np.eye(n) - p).T, b), rel=1e-12)
