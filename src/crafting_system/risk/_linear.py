"""The dense solves that a number of the risk report depends on: each is measured, none is believed (tickets #642, #584, #615); since #841 they are the
one linear solve of the planner (`solver/_packed_linear.py`), read here with the risk's own tolerances.

The system is `x = rhs + off x` with `off >= 0` and no entry on its diagonal: a state's own chance to stay has been divided out of its
row (`pivot = chance to leave`, a sum of positive terms, never `1 - p`). That is the whole point. A state that stays with chance
`1 - 1e-13` has `1 - p = 1e-13 +- 1e-16` in the matrix `I - M`, and a dense solve of that matrix is good to three digits; the same
system with the self-loop divided out has entries of size one, and `numpy.linalg.solve` is good to the last digit (the inverse of
`I - P` in #615 against `Fraction` elimination). When the rows are chances and the share of each that leaves the component is given (`exit`), a
component whose LU answer is not good enough is inverted without a subtraction (`gth_inverse`, #700): a ring of states gone round 1e13 times then
costs no digits either.

What is measured is the componentwise backward error of the answer (`backward_error`): the largest over the states of `|rhs - (x - off x)|` against
the size of the terms it is made of, `|x| + |off| |x| + |rhs|`. The solve is refined while it falls (`_packed_linear.refine`). What is left is the
caller's to say: `solve` gives the error with the answer, and the caller refuses above a tolerance it states.
"""

import math

import numpy as np

from ..solver import linear_solve as _packed_linear

EPS, REFINEMENTS, SETTLED = _packed_linear.EPS, _packed_linear.REFINEMENTS, _packed_linear.SETTLED  # (read by the risk's tests and callers)

SAID_ABOVE = 1e-4  # a relative error above this is said to the reader: the report prints a cost to more digits than that supports
REFUSED_ABOVE = 1e-2  # above this a number is not shown: a cost not known to within one in a hundred is not one a reader can plan with


def backward_error(off: np.ndarray, rhs: np.ndarray, x: np.ndarray) -> float:
    """The componentwise backward error of `x` in `x = rhs + off x`: `max |rhs - (x - off x)| / (|x| + |off| |x| + |rhs|)`; infinite if it is not a number."""
    return _packed_linear.backward_error(off.__matmul__, rhs, x)


def solve(off: np.ndarray, rhs: np.ndarray, exit: np.ndarray | None = None, transpose: bool = False) -> tuple[np.ndarray, float] | None:
    """`(x, backward error)` for `x = rhs + off x` (`off^T` when `transpose`), refined while the error falls; `None` when the matrix is singular in floats.

    `exit` (rows of chances: `off 1 + exit = 1`) lets a component that LU does not solve well be inverted without a subtraction (`_packed_linear.dense`).
    """
    found = _packed_linear.dense(off, rhs, exit, transpose)
    return None if found is None else (found[0], found[1])


def forward_estimate(off: np.ndarray, rhs: np.ndarray, x: np.ndarray, error: float) -> float:
    """An ESTIMATE of the relative error of `x` (against the exact answer) for a system whose `I - off` is an M-matrix, from its backward error `error`.

    With `s = |x| + |off| |x| + |rhs|` the residual is at most `error s` in each state, and the exact `(I - off)^-1` is not negative, so the error of
    `x` is at most `error (I - off)^-1 s`: one more solve with the same matrix gives it (`_packed_linear.amplification`, which checks that solve against
    its own residual), and it is divided by the state's own value. It is not rigorous: that solve has its own rounding, and the `n + 3` units of `EPS`
    added to `error` cover the rounding of the product that measured it, not that of the solve. Infinite when the system is singular in floats or a
    state with value zero is fed.
    """
    if not len(rhs):
        return 0.0
    matrix = np.eye(len(rhs)) - off
    found = (error + (len(rhs) + 3) * EPS) * _packed_linear.amplification(off.__matmul__, rhs, x, lambda s: np.linalg.solve(matrix, s))
    return found if math.isfinite(found) else float("inf")
