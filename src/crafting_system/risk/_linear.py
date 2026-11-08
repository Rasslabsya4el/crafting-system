"""The dense solves that a number of the risk report depends on: each is measured, none is believed (tickets #642, #584, #615).

The system is `x = rhs + off x` with `off >= 0` and no entry on its diagonal: a state's own chance to stay has been divided out of its
row (`pivot = chance to leave`, a sum of positive terms, never `1 - p`). That is the whole point. A state that stays with chance
`1 - 1e-13` has `1 - p = 1e-13 +- 1e-16` in the matrix `I - M`, and a dense solve of that matrix is good to three digits; the same
system with the self-loop divided out has entries of size one, and `numpy.linalg.solve` is good to the last digit (the inverse of
`I - P` in #615 against `Fraction` elimination).

What is measured is the componentwise backward error of the answer (`backward_error`, the same measure `cli/_route_flow._backward_error` uses): the
largest over the states of `|rhs - (x - off x)|` against the size of the terms it is made of, `|x| + |off| |x| + |rhs|`. It is the size of the
relative change of the system that would make `x` exact, small exactly for an answer as good as floats allow and about one for a wrong one. A plain
`|b - A x| / |b|` cannot get below the rounding of the terms when the answer is far larger than `b`, and so it refuses an answer that is as good as
floats allow.

The solve is refined while the backward error falls (`REFINEMENTS` times at most, one more solve with the same matrix each): a stiff system loses
digits in one solve and gets them back in the next. What is left is the caller's to say: `solve` gives the error with the answer, and the caller
refuses above a tolerance it states.
"""

import math
import sys

import numpy as np

EPS = sys.float_info.epsilon
REFINEMENTS = 4
SAID_ABOVE = 1e-4  # a relative error above this is said to the reader: the report prints a cost to more digits than that supports
REFUSED_ABOVE = 1e-2  # above this a number is not shown: a cost not known to within one in a hundred is not one a reader can plan with
SETTLED = 8 * EPS  # a backward error this small is the rounding of the product itself: a further step cannot lower it


def backward_error(off: np.ndarray, rhs: np.ndarray, x: np.ndarray) -> float:
    """The componentwise backward error of `x` in `x = rhs + off x`: `max |rhs - (x - off x)| / (|x| + |off| |x| + |rhs|)`; infinite if it is not a number."""
    if not len(rhs):
        return 0.0
    with np.errstate(all="ignore"):
        scale = np.abs(x) + np.abs(off) @ np.abs(x) + np.abs(rhs)
        error = np.abs(rhs - (x - off @ x)) / np.where(scale > 0.0, scale, 1.0)
    return float(np.max(error)) if np.all(np.isfinite(error)) else float("inf")


def solve(off: np.ndarray, rhs: np.ndarray) -> tuple[np.ndarray, float] | None:
    """`(x, backward error)` for `x = rhs + off x`, refined while the error falls; `None` when the matrix is singular in floats."""
    n = len(rhs)
    if not n:
        return np.zeros(0), 0.0
    matrix = np.eye(n) - off
    with np.errstate(all="ignore"):
        try:
            x = np.linalg.solve(matrix, rhs)
        except np.linalg.LinAlgError:
            return None
        best = backward_error(off, rhs, x)
        for _ in range(REFINEMENTS):
            if best <= SETTLED:
                break
            try:
                better = x + np.linalg.solve(matrix, rhs - (x - off @ x))
            except np.linalg.LinAlgError:
                break
            error = backward_error(off, rhs, better)
            if not error < best:
                break
            x, best = better, error
    return x, best


def forward_estimate(off: np.ndarray, rhs: np.ndarray, x: np.ndarray, error: float) -> float:
    """An ESTIMATE of the relative error of `x` (against the exact answer) for a system whose `I - off` is an M-matrix, from its backward error `error`.

    It is not a rigorous bound: the factor is found by one more solve with the same matrix in floats, and that solve has its own rounding (on a system stiff
    enough to lose every digit the factor itself is wrong). The `n + 3` units of `EPS` added to it cover the rounding of the product that measured `error`,
    not that of the solve. It is what the certified ranges and the limits of `risk/` widen by; where the arithmetic is nearer its end than the tolerances
    (`REFUSED_ABOVE`), the figure is refused instead.

    With `s = |x| + |off| |x| + |rhs|` the residual is at most `error s` in each state, and the exact `(I - off)^-1` is not negative, so the
    error of `x` is at most `error (I - off)^-1 s`: one more solve with the same matrix gives it, and it is divided by the state's own value. This is
    the backward error times the condition the system really has, state by state, not a guess at it. The rounding of the product that measured
    `error` is added to it (`n + 3` units of `EPS`). Infinite when the system is singular in floats or a state with value zero is fed.
    """
    if not len(rhs):
        return 0.0
    with np.errstate(all="ignore"):
        scale = np.abs(x) + np.abs(off) @ np.abs(x) + np.abs(rhs)
        try:
            reach = np.linalg.solve(np.eye(len(rhs)) - off, scale)
        except np.linalg.LinAlgError:
            return float("inf")
        seen = np.abs(x) > 0.0
        if np.any(reach[~seen] > 0.0):
            return float("inf")
        bound = (error + (len(rhs) + 3) * EPS) * float(np.max(reach[seen] / np.abs(x[seen]), initial=0.0))
    return bound if math.isfinite(bound) else float("inf")
