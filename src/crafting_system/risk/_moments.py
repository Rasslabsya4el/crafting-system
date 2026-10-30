"""Mean and variance of the total cost of a proper policy, through the solver's public API.

The policy gives one action per state, so `solve` has no choice to make and returns the expected
remaining cost of the chain: (I - Q) m = c. Two further solves on the same chain, with other
per-state cost vectors, give the other numbers the risk report needs.

Second moment. With m1 the mean (m1 = 0 at a goal) and p_sj the move probabilities,
(I - Q) m2 = c*c + 2 c * (Q m1), so the second solve uses the cost vector
c_s^2 + 2 c_s sum_j p_sj m1_j (positive, since c_s > 0).

Certified intervals. `solve` certifies V (1 - e) <= V* <= V (1 + e) per state. The vector built
from the computed m1 differs from the true one by a factor in [1 - e1, 1 + e1] (the c*c part is
exact), plus the rounding of the float arithmetic that builds it, allowed as `rho` relative.
Mean values are linear and monotone in the cost vector, so with a = (1 - e1)(1 - rho) and
b = (1 + e1)(1 + rho) the true second moment lies in m2 * [a (1 - e2), b (1 + e2)] where e2 is
the error of the second solve. The variance interval is [lo(m2) - hi(m1)^2, hi(m2) - lo(m1)^2]
clipped at zero. An infinite error bound gives [0, inf] ends; the value is still returned.
"""

import math
import sys
from collections.abc import Sequence

from ..solver import Action, TabularModel, solve
from ._chain import Chain

EPS = sys.float_info.epsilon
MIN_COST_ROUNDING = 1e-14  # relative allowance for the float arithmetic building the second cost vector


def interval(value: float, error: float) -> tuple[float, float]:
    """`[value (1 - error), value (1 + error)]`, clipped at zero below and infinite when the error is."""
    low = value * (1.0 - error) if error < 1.0 else 0.0
    high = value * (1.0 + error) if math.isfinite(error) else math.inf
    return max(low, 0.0), high


def solve_costs(chain: Chain, costs: Sequence[float]) -> tuple[list[float], float]:
    """Mean remaining cost of every state when state i pays `costs[i]` per step, and its error bound."""
    table = {
        chain.states[i]: [Action(a.label, costs[i], a.outcomes)]
        for i in chain.finishing_states()
        for a in [chain.action[i]]
    }
    goals = [chain.states[i] for i, flag in enumerate(chain.goal) if flag]
    solution = solve(TabularModel(goals, table), [chain.states[0]])
    values = [solution.values.get(state, 0.0) for state in chain.states]
    return values, solution.error_bound


def real_costs(chain: Chain) -> list[float]:
    return [a.cost if a is not None else 0.0 for a in chain.action]


def mean_and_variance(
    chain: Chain,
) -> tuple[tuple[float, float, float], tuple[float, float, float], list[float]]:
    """`(mean, variance, m1)`, the first two as `(value, low, high)`, for a proper policy."""
    costs = real_costs(chain)
    m1, e1 = solve_costs(chain, costs)
    second = [0.0] * len(costs)
    for i in chain.finishing_states():
        ahead = math.fsum(p * m1[j] for j, p in chain.succ[i])
        second[i] = costs[i] * costs[i] + 2.0 * costs[i] * ahead
    m2, e2 = solve_costs(chain, second)

    degree = max((len(edges) for edges in chain.succ), default=0)
    rho = max(MIN_COST_ROUNDING, (8 + degree) * EPS)
    a = (1.0 - e1) * (1.0 - rho)
    b = (1.0 + e1) * (1.0 + rho)
    mean_low, mean_high = interval(m1[0], e1)
    second_low = max(0.0, m2[0] * a * (1.0 - e2)) if e2 < 1.0 and a > 0.0 else 0.0
    second_high = m2[0] * b * (1.0 + e2) if math.isfinite(e1 + e2) else math.inf
    variance = max(0.0, m2[0] - m1[0] ** 2)
    var_low = max(0.0, second_low - mean_high**2)
    var_high = second_high - mean_low**2
    return (
        (m1[0], mean_low, mean_high),
        (variance, var_low, max(var_high, variance)),
        m1,
    )
