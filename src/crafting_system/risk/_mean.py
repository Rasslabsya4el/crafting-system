"""The mean cost of a fixed policy with a certified interval: what the interval driver needs of `evaluate`, without its DP.

The chain and the linear systems are those of `evaluate` (`_chain`, `_moments`, `_inputs`), so the number is the one
`evaluate(...).mean` gives; the budget DP for quantiles and CVaR is not run.
"""

import math
from collections.abc import Callable, Mapping

from ..solver import Action
from . import _inputs, _moments
from ._chain import build_chain
from ._report import STUCK, SUBCRITICAL, UNDECIDED, Estimate, Expected

INFINITE = Estimate(math.inf, math.inf, math.inf)
ZERO = Estimate(0.0, 0.0, 0.0)


def no_mean(stopped: _inputs.NotSubcritical | None) -> Expected:
    """The infinite total with its cause: `STUCK` when nothing was raised (the chain cannot finish), else what `stopped` says."""
    if stopped is None:
        return Expected(INFINITE, STUCK)
    return Expected(INFINITE, UNDECIDED if isinstance(stopped, _inputs.Undecided) else SUBCRITICAL)


def policy_mean[S](policy: Mapping[S, Action[S]], start: S, is_goal: Callable[[S], bool]) -> Expected:
    """Expected total cost of `policy` from `start`: an `Expected` of `Estimate(value, low, high)`, all infinite when it is not finite.

    A policy that can get stuck (a reachable state with no entry) or loops without a way out has no finite mean (cause `STUCK`); one that
    needs more runs than it makes (`NotSubcritical`) neither (`SUBCRITICAL`); one whose mean the arithmetic could not certify (`Undecided`)
    is `UNDECIDED` (M7, #512).
    """
    chain = build_chain(policy, start, is_goal)
    if chain.goal[0]:
        return Expected(ZERO)
    if not chain.can_finish[0] or not chain.proper:
        return no_mean(None)
    costs = _moments.real_costs(chain)
    if chain.has_inputs:
        try:
            values, error = _inputs.solve_costs(chain, costs)
        except _inputs.NotSubcritical as stopped:
            return no_mean(stopped)
        low, high = _inputs.bracket(values[0], error)
    else:
        values, error = _moments.solve_costs(chain, costs)
        low, high = _moments.interval(values[0], error)
    return Expected(Estimate(values[0], low, high))
