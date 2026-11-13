"""The one linear solve of the planner: the policy's values, the route page's visits and chances, and the risk's moments (ticket #841, C6 of #812).

`solver/_packed_solve.evaluate_policy`, `cli/_route_flow` and `risk/_inputs`, `risk/_coarse` all solve `x = b + T x` here. `T` has no entry on its
diagonal and none below zero: a state's own chance to stay has been divided out of its row (the row is divided by the chance to leave the state, a sum
of positive terms, never `1 - p`), so a stiff self-loop costs no digits. Where `T`'s rows are chances, the share of a row that leaves the system (to a
goal, a dead state, or a state already solved) is its `exit`, a sum of positive terms too; `I - T` is then `diag(exit + T 1) - T` exactly.

What is measured, never believed (tickets #584, #642, #699):

* The componentwise backward error of an answer (`backward_error`): `max |b - (x - T x)| / (|x| + T |x| + |b|)`, the size of the relative change of
  the system that would make `x` exact. It is small for an answer as good as floats allow and about one for a wrong one.
* The forward error, the relative error of `x` itself, which is what a reader needs (`forward_estimate`): the backward error times how much the
  system amplifies it. Two estimates are made and the smaller is kept: `max |r| / b` over the states, which holds for any `T >= 0` with `(I - T)^-1 >= 0`
  and `b >= 0` (`|x - x^| = (I - T)^-1 |r| <= e (I - T)^-1 b = e x`), and is pessimistic by the ratio of `x` to `b` where the answer is far larger than
  its right-hand side; and the backward error times the amplification measured by one more solve with the same method, `max ((I - T)^-1 s) / |x|`
  with `s = |x| + T |x| + |b|` (an estimate: that solve has its own rounding). Neither is a certificate; the callers that certify (`certify`,
  `risk/_inputs`) prove their own bounds from the same pieces.

How a system is solved (`solve`). Dense, refined, for at most `DENSE_LIMIT` states; else BiCGSTAB until it converges or first stagnates (`stalled`: the
best residual has not halved for `STALL` times the run's own pace, nor for as long as its progress took). A run whose recurrence claims its aim while its
true residual is above ten times it is started again from its iterate with a fresh recurrence (the drift of #584, not a stagnation; R04 and R14 reach
1e-16 so), at most `BICGSTAB_RESTARTS` times. An answer is taken when its forward estimate is
within `tol`. Otherwise the exact solve by the cycles of the chain (`_packed_chain.ChainSolver`: the components inverted without a subtraction, by
`gth_inverse`, and the rows many states share cut and put back) is made, whatever the number of states, refined while its backward error falls, and
taken when that error is within `accept`. Only when the exact solve cannot be made (its cost does not fit the memory of a run, or the caller has none)
does the iteration go on from its best iterate, and the best answer found is returned with its measures for the caller to judge. No count of states and
no count of iterations decides an answer (OR-12): `BICGSTAB_ITERATIONS` is a stop-and-say-so rail.

`gth_inverse` is the Grassmann-Taksar-Heyman elimination (#700): a state is eliminated with the sum of its other chances to leave (its exit plus its row
to the states still in), never `1 - p`, so a ring gone round 1e16 times is inverted to the rounding of its sums. It is blocked: the Schur complements
of halves are products of matrices that are not negative, made by BLAS.

Nothing here knows the game. Uses numpy, so it is a `_packed*.py` file (ADR-0010 amended).
"""

import math
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

EPS = sys.float_info.epsilon
DENSE_LIMIT = 1500  # systems of at most this many states are solved dense, larger ones by BiCGSTAB (a speed choice: both are measured alike)
ACCEPT_ERROR = 1e-6  # the forward error an approximate answer (dense or iterate) is taken at; above it the exact solve by the cycles is made
ACCEPT_BACKWARD = 1e-10  # the backward error an exact solve, or an answer when no exact solve can be made, is still taken at (the caller says the rest)
REFINEMENTS = 4  # steps of refinement of a direct solve (each a residual and one more solve), taken only while the backward error falls
SETTLED = 8 * EPS  # a backward error this small is the rounding of the product itself: a further step cannot lower it
STALL = 6  # a BiCGSTAB run has stagnated when its best residual has not halved for this many times its own pace (iterations per halving so far), nor for as long as its progress took
BICGSTAB_ITERATIONS = 4_000  # a rail on one run (stop and say so), not what decides an answer
BICGSTAB_RESTARTS = 3  # further runs from the iterate: when its recurrence drifted from the true residual, or after a stagnation when the exact solve cannot be made
AMPLIFICATION_TOL = 1e-3  # the relative residual the iteration aims at when it measures the amplification: a factor known to 0.1% is plenty


class Terms:
    """The terms of `x = b + T x` a caller gives `solve`: `T v` (`apply`), `T` as a dense matrix (`dense`, asked only at most `DENSE_LIMIT` states)
    and the exact solver by the cycles of the chain (`exact`: an object with `solve(b)`, or None when the caller has none; it may raise
    `_packed_chain.CyclesTooTangled` or `MemoryError` when its cost does not fit). A subclass overrides what it has."""

    n: int

    def apply(self, v: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def dense(self) -> np.ndarray:
        raise NotImplementedError

    def exact(self):
        return None


@dataclass(frozen=True, slots=True)
class Solved:
    """What `solve` found. `x` is None when nothing could be computed at all.

    `how`: "dense", "iterate" or "exact". `backward`: the componentwise backward error of `x`; `forward`: the estimate of its relative error
    (`forward_estimate`); `residual`: the normwise true residual `|b - (x - T x)| / |b|`; `iterations`: BiCGSTAB's; `stagnated`: the iteration
    stopped at a stagnation, not at its tolerance. `iterate`: `(backward, residual, forward)` of an approximate answer the exact solve replaced or
    tried to; `why`: why the exact solve was not made or not taken, `cost` what it needed (`rows`, `cells`, `allowed` of `CyclesTooTangled`).
    """

    x: np.ndarray | None
    how: str
    backward: float
    forward: float
    residual: float
    iterations: int = 0
    stagnated: bool = False
    iterate: tuple[float, float, float] | None = None
    why: str | None = None
    cost: dict = field(default_factory=dict)
    cut_rows: int = 0
    singular: bool = False  # the exact solve found a part of the chain that never leaves it (a closed class): the system has no answer

    @property
    def good(self) -> bool:
        """The answer is taken without a word: its forward estimate is within `ACCEPT_ERROR`, or it is the exact solve within `ACCEPT_BACKWARD`."""
        return self.x is not None and (self.forward <= ACCEPT_ERROR or (self.how == "exact" and self.backward <= ACCEPT_BACKWARD))


# ---- the measures ----------------------------------------------------------------------------------------------------------------------------------


def _scale_and_residual(apply: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    with np.errstate(all="ignore"):
        scale = np.abs(x) + apply(np.abs(x)) + np.abs(b)
        residual = b - (x - apply(x))
    return scale, residual


def backward_error(apply: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x: np.ndarray) -> float:
    """The componentwise backward error of `x` in `x = b + T x` (`apply(v) = T v`, `T >= 0`): `max |b - (x - T x)| / (|x| + T |x| + |b|)`; infinite if it is not a number.

    A plain `|b - A x| / |b|` cannot get below the rounding of the terms when the answer is far larger than `b` (a policy that rerolls a hundred
    million times), and refuses an answer that is as good as floats allow; this one is the relative change of the system that makes `x` exact.
    """
    if not len(b):
        return 0.0
    scale, residual = _scale_and_residual(apply, b, x)
    with np.errstate(all="ignore"):
        error = np.abs(residual) / np.where(scale > 0.0, scale, 1.0)
    return float(np.max(error)) if np.all(np.isfinite(error)) else math.inf


def normwise_residual(apply: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x: np.ndarray) -> float:
    """`|b - (x - T x)| / |b|` (2-norms): what BiCGSTAB aims at, kept for the reader of `info`."""
    with np.errstate(all="ignore"):
        value = float(np.linalg.norm(b - (x - apply(x)))) / max(float(np.linalg.norm(b)), 1e-300)
    return value if math.isfinite(value) else math.inf


def amplification(apply: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x: np.ndarray, solve_with: Callable[[np.ndarray], np.ndarray | None]) -> float:
    """`max over the states of ((I - T)^-1 s) / |x|`, `s = |x| + T |x| + |b|`: how many times the system amplifies a backward error into the error of `x`,
    state by state. Infinite when it cannot be shown, or a state of value 0 is fed.

    `y = solve_with(s)` is one more solve with the same method, and it is checked, not believed: with `d` the largest share of `s` that `(I - T) y`
    falls short of it (its residual plus the rounding of the product), `y >= 0` and `d <= 1/2` give `(I - T)^-1 s <= y / (1 - d)`, as `(I - T)^-1` is not
    negative (`(I - T) y >= (1 - d) s`). So an approximate `y` (an iterate) gives a bound too, and a solve that failed gives none.
    """
    if not len(b):
        return 0.0
    with np.errstate(all="ignore"):
        scale = np.abs(x) + apply(np.abs(x)) + np.abs(b)
        try:
            reach = solve_with(scale)
        except (np.linalg.LinAlgError, MemoryError):
            return math.inf
        if reach is None or not np.all(np.isfinite(reach)) or np.any(reach < 0.0):
            return math.inf
        ahead = apply(reach)
        lack = np.maximum(scale - (reach - ahead), 0.0) + 8 * EPS * (reach + ahead + scale)
        short = np.where(scale > 0.0, lack / np.where(scale > 0.0, scale, 1.0), np.where(reach > 0.0, math.inf, 0.0))
        d = float(np.max(short))
        if not d <= 0.5:
            return math.inf
        seen = np.abs(x) > 0.0
        if np.any(reach[~seen] > 0.0):
            return math.inf
        value = float(np.max(reach[seen] / np.abs(x[seen]), initial=0.0)) / (1.0 - d)
    return value if math.isfinite(value) else math.inf


def rhs_bound(apply: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x: np.ndarray) -> float:
    """`max |b - (x - T x)| / b` over the states, plus the rounding of the product (`8 eps` of the scale): the relative error of `x` when `b >= 0` and
    `(I - T)^-1 >= 0` (module text). Infinite where a residual meets `b = 0`, or when `b` has an entry below 0."""
    if not len(b):
        return 0.0
    if np.any(b < 0.0):
        return math.inf
    scale, residual = _scale_and_residual(apply, b, x)
    with np.errstate(all="ignore"):
        error = np.abs(residual) + 8 * EPS * scale
        share = np.where(b > 0.0, error / np.where(b > 0.0, b, 1.0), np.where(error == 0.0, 0.0, math.inf))
    value = float(np.max(share))
    return value if math.isfinite(value) else math.inf


def forward_estimate(
    apply: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x: np.ndarray, backward: float, solve_with: Callable[[np.ndarray], np.ndarray | None], tol: float = 0.0
) -> float:
    """The estimate of the relative error of `x` (module text): the smaller of `rhs_bound` and `backward` times the measured `amplification`. The
    amplification costs one more solve and is measured only when `rhs_bound` is above `tol`."""
    first = rhs_bound(apply, b, x)
    if first <= tol:
        return first
    if not math.isfinite(backward):
        return first
    second = (backward + 8 * EPS) * amplification(apply, b, x, solve_with)
    return min(first, second if math.isfinite(second) else math.inf)


# ---- the subtraction-free inverse ------------------------------------------------------------------------------------------------------------------


def gth_inverse(off: np.ndarray, exit: np.ndarray) -> np.ndarray:
    """`(diag(exit + off 1) - off)^-1` for `off >= 0` (its diagonal is not read) and `exit >= 0`, with no subtraction: `off` is `k x k` or a stack
    `batch x k x k` (`exit` then `batch x k`). Infinite or not a number where a part of the chain never leaves (a closed class: no exit).

    Halves 1 and 2: the first is inverted with the exits `exit_1 + off_12 1` (its rows' mass into the second half leaves it); the Schur complement
    of the second, `S = diag(...) - off_22 - off_21 N_11 off_12`, has the entries off its diagonal `off_22 + off_21 N_11 off_12` and the exits
    `exit_2 + off_21 N_11 exit_1` (`S 1` computed as positive terms: `N_11 (exit_1 + off_12 1) = 1`), and is inverted the same way; then
    `N_12 = N_11 off_12 N_22`, `N_21 = N_22 off_21 N_11`, `N_11 + N_12 off_21 N_11`. A state alone is `1 / exit`.
    """
    single = off.ndim == 2
    matrix = np.array(off[None] if single else off, dtype=np.float64, copy=True)
    leave = np.array(exit[None] if single else exit, dtype=np.float64, copy=True)
    k = matrix.shape[-1]
    if k:
        matrix[:, np.arange(k), np.arange(k)] = 0.0
    with np.errstate(all="ignore"):
        inverse = _gth(matrix, leave)
    return inverse[0] if single else inverse


def _gth(off: np.ndarray, exit: np.ndarray) -> np.ndarray:
    k = off.shape[-1]
    if k == 1:
        return (1.0 / exit)[..., None]
    h = k // 2
    b11, b12, b21, b22 = off[:, :h, :h], off[:, :h, h:], off[:, h:, :h], off[:, h:, h:]
    e1, e2 = exit[:, :h], exit[:, h:]
    n11 = _gth(b11, e1 + b12.sum(axis=-1))
    left = b21 @ n11  # off_21 N_11
    schur = b22 + left @ b12
    schur[:, np.arange(k - h), np.arange(k - h)] = 0.0
    n22 = _gth(schur, e2 + (left @ e1[..., None])[..., 0])
    n12 = (n11 @ b12) @ n22
    out = np.empty_like(off)
    out[:, :h, :h] = n11 + n12 @ left
    out[:, :h, h:] = n12
    out[:, h:, :h] = n22 @ left
    out[:, h:, h:] = n22
    return out


# ---- dense ----------------------------------------------------------------------------------------------------------------------------------------


def dense(off: np.ndarray, b: np.ndarray, exit: np.ndarray | None = None, transpose: bool = False, tol: float | None = None) -> tuple[np.ndarray, float, float, str] | None:
    """`(x, backward, forward, how)` for `x = b + off x` (or `x = b + off^T x` when `transpose`), dense; None when it is singular in floats.

    LU (`numpy.linalg.solve`), refined while the backward error falls. When its forward estimate is above `tol` and the rows' `exit` are given (rows
    of chances: `off 1 + exit = 1`), the system is inverted by `gth_inverse` instead (`how` "gth"), which a ring gone round 1e16 times does not defeat,
    and refined the same way; the better answer by the forward estimate is kept.
    """
    n = len(b)
    tol = ACCEPT_ERROR if tol is None else tol
    if not n:
        return np.zeros(0), 0.0, 0.0, "lu"
    matrix_of = off.T if transpose else off

    def apply(v: np.ndarray) -> np.ndarray:
        return matrix_of @ v

    system = np.eye(n) - matrix_of
    found = None
    with np.errstate(all="ignore"):
        try:
            x = np.linalg.solve(system, b)
        except np.linalg.LinAlgError:
            x = None
        if x is not None and np.all(np.isfinite(x)):
            x, error = refine(apply, b, x, lambda r: np.linalg.solve(system, r))
            forward = forward_estimate(apply, b, x, error, lambda s: np.linalg.solve(system, s), tol)
            found = (x, error, forward, "lu")
    if exit is not None and (found is None or not found[2] <= tol):
        inverse = gth_inverse(off, exit)
        if np.all(np.isfinite(inverse)):
            use = inverse.T if transpose else inverse
            with np.errstate(all="ignore"):
                x = use @ b
                error = backward_error(apply, b, x)
                if not error <= ACCEPT_BACKWARD:  # (a solve that kept the structure is refined only when it lost digits: see `refine`)
                    x, error = refine(apply, b, x, lambda r: use @ r)
                forward = forward_estimate(apply, b, x, error, lambda s: use @ s, tol)
            if found is None or forward < found[2] or not math.isfinite(found[2]):
                found = (x, error, forward, "gth")
    return found


def refine(apply: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x: np.ndarray, solve_with: Callable[[np.ndarray], np.ndarray]) -> tuple[np.ndarray, float]:
    """`x` refined (`x + solve_with(b - (x - T x))`) while its backward error falls, at most `REFINEMENTS` times, and that error.

    The residual is formed as `b - (x - T x)`, whose rounding is the scale of the terms times the epsilon; the next solve amplifies it by the condition of
    the system. So a refinement takes an answer to that rounding times the condition, and no further: it repairs a solve that lost more (an LU of a stiff
    system), but it would spoil one that kept the structure (the cycles of the chain inverted without a subtraction, `gth_inverse`, are good to the
    rounding of their sums whatever the condition: a ring gone round 1e9 times is 2e-13 off, and one refinement takes it to 7e-6 while its backward error
    falls from 2e-15 to 1e-16). Such a solve is refined only when its backward error is above what it is taken at (`solve`, `dense`).
    """
    best = backward_error(apply, b, x)
    for _ in range(REFINEMENTS):
        if best <= SETTLED:
            break
        with np.errstate(all="ignore"):
            try:
                better = x + solve_with(b - (x - apply(x)))
            except np.linalg.LinAlgError:
                break
        error = backward_error(apply, b, better)
        if not error < best:
            break
        x, best = better, error
    return x, best


# ---- BiCGSTAB --------------------------------------------------------------------------------------------------------------------------------------


def bicgstab(matvec: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x0: np.ndarray, tol: float, max_iter: int | None = None) -> tuple[np.ndarray, float, int, bool]:
    """BiCGSTAB for `matvec(x) = b`: `(x, true relative residual, iterations, stagnated)`.

    The residual returned is the TRUE one, `|b - A x| / |b|` of the iterate returned, made by one more product: the residual of the method's own
    recurrence drifts from it on a stiff system (it can be 1e-21 while the iterate is wrong by a factor of 1e16, tickets #584 and #600), so it only
    decides when the method stops. The iterate returned is the better, by the true residual, of the best the recurrence saw and the start.
    `stagnated`: the run stopped because its best residual stopped halving at its own pace (`STALL`), not at `tol` or at `max_iter`.
    """
    with np.errstate(all="ignore"):
        x, iterations, first, _, stagnated = _bicgstab_run(matvec, b, x0, tol, BICGSTAB_ITERATIONS if max_iter is None else max_iter)
        bnorm = max(float(np.linalg.norm(b)), 1e-300)
        true = float(np.linalg.norm(b - matvec(x)))
        if not true <= first:  # the recurrence ended on an iterate worse than the start (or not a number)
            x, true = x0.copy(), first
        return x, true / bnorm, iterations, stagnated


def stalled(it: int, marked_at: int, marks: int) -> bool:
    """Whether a run at iteration `it`, whose best residual halved `marks` times by the iteration `marked_at`, has stagnated: it has gone without halving
    again both `STALL` times its own pace (`marked_at / marks` iterations per halving, 1 before the first) and as long as all its progress took.

    The second half keeps a run that converges through a pause: R04 and R14 pause for a dozen steps on their way to a residual of 1e-16 in about a
    hundred, and stopping them there sent their evaluations to the exact solve (21 s each on R14). A stiff run, whose progress stops after a few early
    halvings, still stops a few steps after them (#671)."""
    return it - marked_at >= max(STALL * max(1.0, marked_at / max(marks, 1)), marked_at)


def _bicgstab_run(matvec, b, x0, tol, max_iter):
    """`(best iterate by the recurrence, iterations, true norm of b - A x0, the relative residual the recurrence claims for it, stagnated)`.

    Stagnation is read from the run itself: the best residual halved `marks` times by the iteration `marked_at`, so its pace is `marked_at / marks`
    iterations per halving (1 before the first); a run that goes `STALL` times its pace without halving has stagnated.
    """
    x = x0.copy()
    r = b - matvec(x)
    bnorm = max(float(np.linalg.norm(b)), 1e-300)
    rnorm = float(np.linalg.norm(r))
    first = rnorm
    best_x, best = x.copy(), rnorm
    r_hat = r.copy()
    rho = alpha = omega = 1.0
    v = np.zeros_like(b)
    p = np.zeros_like(b)
    it = 0
    marked, marked_at, marks = rnorm, 0, 0
    while it < max_iter and rnorm > tol * bnorm:
        while best <= 0.5 * marked:
            marked, marked_at, marks = 0.5 * marked, it, marks + 1
        if stalled(it, marked_at, marks):
            return best_x, it, first, best / bnorm, True
        it += 1
        rho_new = float(r_hat @ r)
        if rho_new == 0.0 or omega == 0.0:  # breakdown: restart the recurrence from the current iterate
            r_hat, rho, alpha, omega = r.copy(), 1.0, 1.0, 1.0
            v[:] = 0.0
            p[:] = 0.0
            rho_new = float(r_hat @ r)
            if rho_new == 0.0:
                break
        beta = (rho_new / rho) * (alpha / omega)
        p = r + beta * (p - omega * v)
        v = matvec(p)
        denominator = float(r_hat @ v)
        if denominator == 0.0:
            omega = 0.0
            continue
        alpha = rho_new / denominator
        s = r - alpha * v
        if float(np.linalg.norm(s)) <= tol * bnorm:
            x = x + alpha * p
            r = s
            rnorm = float(np.linalg.norm(r))
            if rnorm < best:
                best_x, best = x.copy(), rnorm
            break
        t = matvec(s)
        tt = float(t @ t)
        if tt == 0.0:
            x = x + alpha * p
            r = s
            rnorm = float(np.linalg.norm(r))
            if rnorm < best:
                best_x, best = x.copy(), rnorm
            break
        omega = float(t @ s) / tt
        x = x + alpha * p + omega * s
        r = s - omega * t
        rho = rho_new
        rnorm = float(np.linalg.norm(r))
        if rnorm < best:
            best_x, best = x.copy(), rnorm
    return best_x, it, first, best / bnorm, False


# ---- the solve -------------------------------------------------------------------------------------------------------------------------------------


def _answer(terms: Terms, b: np.ndarray, x: np.ndarray, how: str, solve_with, tol: float, **extra) -> Solved:
    error = backward_error(terms.apply, b, x)
    forward = forward_estimate(terms.apply, b, x, error, solve_with, tol)
    return Solved(x, how, error, forward, normwise_residual(terms.apply, b, x), **extra)


def solve(
    terms: Terms,
    b: np.ndarray,
    *,
    x0: np.ndarray | None = None,
    tol: float | None = None,
    accept: float | None = None,
    dense_limit: int = DENSE_LIMIT,
    iterate_tol: float = 1e-13,
    info: dict | None = None,
) -> Solved:
    """`x = b + T x` (module text): dense or iterated, the exact solve by the cycles when that answer's forward estimate is above `tol` (default `ACCEPT_ERROR`;
    `accept`, the backward error an exact answer is taken at, default `ACCEPT_BACKWARD`).

    `x0` starts the iteration; `iterate_tol` is the relative residual it aims at. `info` (optional) counts `matvecs`. The answer returned is the best
    found, with its measures; `Solved.good` says whether it is taken without a word, the caller says the rest.
    """
    n = len(b)
    tol = ACCEPT_ERROR if tol is None else tol
    accept = ACCEPT_BACKWARD if accept is None else accept
    if not n:
        return Solved(np.zeros(0), "dense", 0.0, 0.0, 0.0)

    def matvec(v: np.ndarray) -> np.ndarray:
        if info is not None:
            info["matvecs"] = info.get("matvecs", 0) + 1
        return v - terms.apply(v)

    candidate: Solved | None = None
    best_iterate = None
    if n <= dense_limit:
        system = np.eye(n) - terms.dense()
        with np.errstate(all="ignore"):
            try:
                x = np.linalg.solve(system, b)
            except np.linalg.LinAlgError:
                x = None
        if x is not None and np.all(np.isfinite(x)):
            x, _ = refine(terms.apply, b, x, lambda r: np.linalg.solve(system, r))
            candidate = _answer(terms, b, x, "dense", lambda s: np.linalg.solve(system, s), tol)
    else:
        start = np.zeros(n) if x0 is None else np.where(np.isfinite(x0), x0, 0.0)
        x, residual, iterations, stagnated = bicgstab(matvec, b, start, iterate_tol)
        for _ in range(BICGSTAB_RESTARTS):  # a run whose recurrence claimed its aim while the TRUE residual did not reach it (#584): a fresh recurrence from there
            if stagnated or residual <= 10 * iterate_tol or iterations >= BICGSTAB_ITERATIONS:
                break
            x, residual, more, stagnated = bicgstab(matvec, b, x, iterate_tol)
            iterations += more
        best_iterate = x

        def again(s: np.ndarray) -> np.ndarray:
            return bicgstab(matvec, s, np.zeros(n), AMPLIFICATION_TOL)[0]

        candidate = _answer(terms, b, x, "iterate", again, tol, iterations=iterations, stagnated=stagnated)
    if candidate is not None and candidate.forward <= tol:
        return candidate

    from ._packed_chain import CyclesTooTangled  # (the chain imports `gth_inverse` from here)

    why, cost, exact = None, {}, None
    try:
        solver = terms.exact()
        if solver is None:
            why = "no exact solve by the cycles of the chain is available here"
        else:
            with np.errstate(all="ignore"):
                x = solver.solve(b)
                if not backward_error(terms.apply, b, x) <= accept:  # (only a solve that lost digits is refined: see `refine`)
                    x, _ = refine(terms.apply, b, x, solver.solve)
            exact = _answer(terms, b, x, "exact", solver.solve, tol, cut_rows=int(getattr(solver, "q", 0)))
    except (CyclesTooTangled, MemoryError, np.linalg.LinAlgError) as stopped:
        why = str(stopped) or "the memory of the run, or a block of the chain that is singular in floats, stopped it"
        cost = {"rows": stopped.rows, "cells": stopped.cells, "allowed": stopped.allowed} if isinstance(stopped, CyclesTooTangled) else {}
    iterate = None if candidate is None else (candidate.backward, candidate.residual, candidate.forward)
    iterations = 0 if candidate is None else candidate.iterations
    if exact is not None and not np.all(np.isfinite(exact.x)):  # the subtraction-free inverse of a class with no way out is infinite
        why = "a part of the chain never leaves it (a closed class): the system is singular and has no answer"
        return Solved(None, "none", math.inf, math.inf, math.inf, iterations, False, iterate, why, {}, exact.cut_rows, True)
    if exact is not None and np.all(np.isfinite(exact.x)):
        if exact.backward <= accept or candidate is None or exact.forward < candidate.forward:
            return Solved(exact.x, "exact", exact.backward, exact.forward, exact.residual, iterations, False, iterate, None if exact.backward <= accept else f"the exact solve by the cycles of the chain reached only a backward error of {exact.backward:.3g}", {}, exact.cut_rows)
        why = f"the exact solve by the cycles of the chain reached only a backward error of {exact.backward:.3g}"
    if best_iterate is not None and candidate is not None and candidate.stagnated:
        # no exact solve: the iteration goes on from its best iterate with a fresh recurrence, as the old restarts did
        x = best_iterate
        for _ in range(BICGSTAB_RESTARTS):
            x, residual, more, stagnated = bicgstab(matvec, b, x, iterate_tol)
            iterations += more
            if not stagnated:
                break

        def again(s: np.ndarray) -> np.ndarray:
            return bicgstab(matvec, s, np.zeros(n), AMPLIFICATION_TOL)[0]

        further = _answer(terms, b, x, "iterate", again, tol, iterations=iterations, stagnated=stagnated)
        if further.forward < candidate.forward or (further.forward == candidate.forward and further.backward < candidate.backward):
            candidate = further
    if candidate is None:
        return Solved(None, "none", math.inf, math.inf, math.inf, iterations, False, iterate, why, cost)
    return Solved(candidate.x, candidate.how, candidate.backward, candidate.forward, candidate.residual, max(iterations, candidate.iterations), candidate.stagnated, iterate, why, cost)
