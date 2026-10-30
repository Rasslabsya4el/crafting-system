"""The certified relative error bound of a candidate value vector.

What the bound is. For a component with its downstream values D fixed at the candidate values, a
policy mu has Bellman operator T_mu(V) = k_mu + P_mu V, where k_mu = c' + P_out D is the constant
term: the effective cost plus the fixed contribution of the successors outside the component
(sum of p_j * D(j)). T is the minimum over actions. Let g be the smallest constant term k over the
component's retained actions (above zero), and for a candidate V:

    e = max over states of (T V - V)^+        d = max over states of (V - T V)^+

Since T_mu(a V) = a T_mu(V) + (1 - a) k_mu, only a lower bound on k is needed, in both directions:

* Upper side: if e < g, the greedy policy mu (argmin of the same computed T V) is proper and
  V* <= J_mu <= V * g / (g - e). Proof: for U = a V with a >= 1, T_mu U = a T_mu V - (a - 1) k_mu
  <= a V + a e - (a - 1) g, so a = g / (g - e) gives T_mu U <= U, and a supersolution bounds the
  cost of mu from above. If e >= g there is no upper certificate yet.
* Lower side (always): for a <= 1, T(a V) >= a T V + (1 - a) g, so a = g / (g + d) gives
  a V <= T(a V), a subsolution, hence a V <= V*.

So the component's own multipliers are l_own = g / (g + d) and u_own = g / (g - e), and its own
relative error is max(1 - l_own, u_own - 1).

Across components. Every state keeps multipliers lo, hi with lo * V <= V* <= hi * V (goals: 1, 1).
Scaling the downstream values by a >= 1 scales a component's solution by at most a, and by a <= 1 by
at least a. So a component whose exit successors have multipliers (lo_j, hi_j) gets
l_d = min(1, min lo_j), u_d = max(1, max hi_j) and, for its states,

    lo = l_d * l_own * (1 - rho)        hi = u_d * u_own * (1 + rho)

where rho = (m + 2) * epsilon allows for float64 rounding: m is the largest number of terms in a
Bellman sum of the component, all terms are positive, so each sum has relative error below that.
An acyclic single state has l_own = u_own = 1 (one exact backup) plus the same rho. The reported
`error_bound` is the maximum over finite states of max(1 - lo, hi - 1).

Known weakness: g is the smallest constant term in the component, so the bound is loose when these
constant terms span many orders of magnitude inside one component (a cheap action whose successors
are also cheap), and a value much larger than g cannot reach a tolerance below about epsilon * V / g.
"""

import sys

EPSILON = sys.float_info.epsilon


class ConvergenceError(RuntimeError):
    """A component could not reach the tolerance within `max_sweeps`.

    `error_bound` is the best certified relative bound reached so far (infinity when no upper
    certificate was ever found).
    """

    def __init__(self, message: str, error_bound: float) -> None:
        super().__init__(message)
        self.error_bound = error_bound


def rounding_allowance(terms: int) -> float:
    """Relative rounding allowance rho for a Bellman sum of at most `terms` positive terms."""
    return (terms + 2) * EPSILON


def own_multipliers(g: float, e: float, d: float) -> tuple[float, float]:
    """`(l_own, u_own)` of a candidate with residuals `e` and `d` (u_own is infinity if e >= g)."""
    lower = g / (g + d)
    upper = g / (g - e) if e < g else float("inf")
    return lower, upper


def relative_error(lower: float, upper: float) -> float:
    """The relative error implied by multipliers `lower <= 1 <= upper`."""
    return max(1.0 - lower, upper - 1.0)
