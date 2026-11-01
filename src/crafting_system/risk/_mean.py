"""The mean cost of a fixed policy with a certified interval: what the interval driver needs of `evaluate`, without its DP.

The chain and the linear systems are those of `evaluate` (`_chain`, `_moments`, `_inputs`), so the number is the one
`evaluate(...).mean` gives; the budget DP for quantiles and CVaR is not run.
"""

import math
from collections.abc import Callable, Mapping

from ..solver import Action
from . import _inputs, _moments
from ._chain import build_chain
from ._report import Estimate

INFINITE = Estimate(math.inf, math.inf, math.inf)
ZERO = Estimate(0.0, 0.0, 0.0)


def policy_mean[S](policy: Mapping[S, Action[S]], start: S, is_goal: Callable[[S], bool]) -> Estimate:
    """Expected total cost of `policy` from `start`: `Estimate(value, low, high)`, all infinite when it is not finite.

    A policy that can get stuck (a reachable state with no entry), loops without a way out, or needs more runs than it
    makes (`NotSubcritical`) has no finite mean.
    """
    chain = build_chain(policy, start, is_goal)
    if chain.goal[0]:
        return ZERO
    if not chain.can_finish[0] or not chain.proper:
        return INFINITE
    costs = _moments.real_costs(chain)
    if chain.has_inputs:
        try:
            values, error = _inputs.solve_costs(chain, costs)
        except _inputs.NotSubcritical:
            return INFINITE
        low, high = _inputs.bracket(values[0], error)
    else:
        values, error = _moments.solve_costs(chain, costs)
        low, high = _moments.interval(values[0], error)
    return Estimate(values[0], low, high)
