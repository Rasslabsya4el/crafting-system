"""The coarse grid: a step above the cheapest action, for a policy whose cost scale is far above it (ticket #190).

The ordinary grid needs a step D that does not exceed the cheapest action, so that every action costs a
whole bin on the lower chain. A policy that mixes a cheap orb (Transmutation, 0.0058 Chaos) with a long
spam of dearer ones (Alteration, 0.1001) and a restart (10 Chaos) has a mean of thousands of Chaos, and
200,000 bins of the cheapest action's size cover a fraction of it.

What the grid needs is not a step below every cost but a step at which the *visited* actions round well.
An action that is not a whole multiple of D costs `floor` bins on the lower chain (0 when it is cheaper
than D) and `ceil` bins on the upper chain, so along any path the two chains differ by one bin per visit
of such an action, and the expected gap between them is

    gap(D) = D * sum over states i that are not whole multiples of D of the expected visits of i.

The expected visits come from one dense solve of the chain (each state's own chance of staying divided out, its
error measured: `expected_visits_checked`). R13 has 57,830 visits of a 0.1001 action and 50 to 1,000 of each cheaper one: D = 0.1001 makes the first exact and leaves a gap of about 115
Chaos on a mean of 6,300. So the step is searched among `cost / m` of the costs that matter, the
coarsest one whose gap is within `GAP_TARGET` of the mean (the least work); if none, the one with the
least gap when that is within `GAP_LIMIT` of the mean; otherwise there is no coarse grid and the
caller keeps the ordinary one. The step is not below `horizon / max_bins`, with the horizon the one-sided
Chebyshev bound mean + sd sqrt(L / (1 - L)) on the highest level L asked: the grid then covers it.

The coarse grid is tried only when the highest level asked certainly lies beyond what the ordinary grid
covers (`beyond_ordinary_grid`, a Paley-Zygmund lower bound on the quantile from the mean and the variance),
so a policy whose ordinary grid already resolves the levels keeps its results bit for bit.

The lower chain has free states (cost 0 bins): `_fold` replaces them by their exit distributions.
"""

import math

import numpy as np

from . import _linear
from ._chain import UNIT_TOLERANCE, Chain

DENSE_STATES = 2500  # the visits are one dense solve and the DP is dense: at most this many states that can finish
GAP_TARGET = 0.02  # the coarsest step whose expected gap is at most this share of the mean
GAP_LIMIT = 0.1  # no coarse grid if even the best step leaves a gap above this share of the mean
COSTS_TRIED = 12  # the costs, by share of the mean, whose fractions are tried as steps
PARTS_TRIED = 64  # step = cost / m for m up to this
DENSE_WORK = 1e11  # the most multiply-adds (bins to the horizon times cells of the matrix) of one dense run: a minute or so


def expected_visits_checked(chain: Chain) -> tuple[list[int], np.ndarray, float] | None:
    """`(states that can finish, expected visits of each from the start, a bound on their relative error)`, or `None` (too many states, a visit count
    the floats lose, or an error above `REFUSED_ABOVE`).

    The system is not `I - P` as the chain gives it: a state that stays with chance 1 - 1e-13 has `1 - p = 1e-13 +- 1e-16` there, and a dense solve of that
    is good to three digits (#615). Each state's row is divided by the chance to leave it (`leave`, the sum of its other chances, goals and lost mass
    included: no `1 - p`), `w` solves `(I - P')^T w = e_start` with `P'[s, t] = P[s, t] / leave[s]` and no diagonal, and the visits are `w / leave`. The
    solve is refined and its componentwise backward error measured (`_linear.solve`); the bound on the relative error is that error times the condition
    the system has (`_linear.forward_bound`), and it is what the caller widens its interval by.
    """
    states = chain.finishing_states()
    if not states or len(states) > DENSE_STATES:
        return None
    position = {s: k for k, s in enumerate(states)}
    n = len(states)
    leave = np.array([math.fsum(p for j, p in chain.succ[s] if j != s) for s in states])
    if not np.all(leave > 0.0):  # a state that leaves with chance rounded to 0: the visits are not finite in floats
        return None
    off = np.zeros((n, n))  # P'[s, t]
    for s in states:
        for j, p in chain.succ[s]:
            if j != s and j in position:
                off[position[s], position[j]] += p / leave[position[s]]
    start = np.zeros(n)
    start[position[0]] = 1.0
    transposed = np.ascontiguousarray(off.T)
    found = _linear.solve(transposed, start)
    if found is None:
        return None
    w, error = found
    bound = _linear.forward_bound(transposed, start, w, error)
    if not bound <= _linear.REFUSED_ABOVE or not np.all(np.isfinite(w)):
        return None
    return states, w / leave, bound


def expected_visits(chain: Chain) -> tuple[list[int], np.ndarray] | None:
    """The states that can finish and the expected number of visits of each from the start; `None` if too many or not known (`expected_visits_checked`)."""
    found = expected_visits_checked(chain)
    return None if found is None else found[:2]


def whole_multiples(costs: np.ndarray, step: float) -> np.ndarray:
    """Which costs are a whole multiple of `step` (at least one), by the rule `_evaluate._cost_bins` uses."""
    ratio = costs / step
    nearest = np.rint(ratio)
    return (nearest >= 1) & (np.abs(ratio - nearest) <= UNIT_TOLERANCE * ratio)


def choose_step(
    chain: Chain, mean: float, variance: float, level: float, max_bins: int
) -> tuple[float, float] | None:
    """`(step, expected gap)` of the coarse grid, or `None` when the ordinary grid has to do."""
    found = expected_visits(chain)
    if found is None:
        return None
    states, visits = found
    cost = np.array([chain.action[s].cost for s in states])
    distinct, inverse = np.unique(cost, return_inverse=True)
    weight = np.bincount(inverse, weights=visits)  # expected visits per distinct cost
    horizon = mean + math.sqrt(variance * level / (1.0 - level))
    floor = horizon / max_bins
    share = weight * distinct
    tried = distinct[np.argsort(share)[::-1][:COSTS_TRIED]]
    best: tuple[float, float] | None = None  # the least gap
    coarse: tuple[float, float] | None = None  # the coarsest step within GAP_TARGET
    for base in tried:
        for parts in range(1, PARTS_TRIED + 1):
            step = float(base) / parts
            if step < floor:
                break
            if horizon / step * len(states) * (len(states) + 4) > DENSE_WORK:
                continue
            gap = step * float(weight[~whole_multiples(distinct, step)].sum())
            if best is None or gap < best[1]:
                best = (step, gap)
            if gap <= GAP_TARGET * mean and (coarse is None or step > coarse[0]):
                coarse = (step, gap)
    if coarse is not None:
        return coarse
    if best is not None and best[1] <= GAP_LIMIT * mean:
        return best
    return None


def quantile_lower_bound(mean: float, variance: float, level: float) -> float:
    """A certified lower bound on the `level` quantile of a cost that is never negative (Paley-Zygmund).

    P(C > t mean) >= (1 - t)^2 mean^2 / E[C^2], so when that is above 1 - level the quantile is above t mean.
    """
    ratio = (1.0 - level) * (variance + mean * mean) / (mean * mean)
    return mean * (1.0 - math.sqrt(ratio)) * (1.0 - 1e-9) if ratio < 1.0 else 0.0


def quantile_upper_bound(mean: float, variance: float, level: float) -> float:
    """A certified upper bound on the `level` quantile of a cost that is never negative (one-sided Chebyshev, Cantelli)."""
    return mean + math.sqrt(variance * level / (1.0 - level))


def may_exceed_ordinary_grid(mean: float, variance: float, level: float, c_min: float, max_bins: int) -> bool:
    """Whether the `level` quantile is not certain to lie inside the `max_bins` bins that a step of at most `c_min` covers.

    The ordinary grid may well reach it (the bound is loose); `beyond_ordinary_grid` is the test of when it certainly cannot.
    """
    return quantile_upper_bound(mean, variance, level) > max_bins * c_min


def beyond_ordinary_grid(mean: float, variance: float, level: float, c_min: float, max_bins: int) -> bool:
    """Whether the `level` quantile certainly lies past the `max_bins` bins that a step of at most `c_min` covers."""
    return quantile_lower_bound(mean, variance, level) > max_bins * c_min * (1.0 + UNIT_TOLERANCE)
