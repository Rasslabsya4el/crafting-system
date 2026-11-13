"""The certified relative error bound of a candidate value vector.

What the bound is. For a component with its downstream values D fixed at the candidate values, a
policy mu has Bellman operator T_mu(V) = k_mu + P_mu V, where k_mu = c' + P_out D is the constant
term: the effective cost plus the fixed contribution of the successors outside the component
(sum of p_j * D(j)). T is the minimum over actions. Let g be the smallest constant term k over the
component's retained actions (above zero), and for a candidate V:

    e = max over states of (T V - V)^+        d = max over states of (V - T V)^+  (computed)

Since T_mu(a V) = a T_mu(V) + (1 - a) k_mu, only a lower bound on k is needed, in both directions:

* Operator mismatch. The computed operator T~ differs from the exact one: the effective cost and
  every probability w / L are rounded, and so is every sum, so |T~V - TV|(s) <= rho * TV(s) with
  rho = (m + 2) * epsilon (m is defined below). That mismatch enters the residuals exactly like
  e and d, and the expected number of visits amplifies it. So the certificate is taken with
  e' = e + delta and d' = d + delta, where delta = rho * max over states of TV, and e', d' stand
  for e, d below. Example: a loop that leaves with chance 1 in 10^9 has a rounded exit
  probability off by 1e-16 relative, a true error near 1e-8, far above any residual the iteration
  shows; delta covers it.
* Upper side: if e' < g, the greedy policy mu (argmin of the same computed T V) is proper and
  V* <= J_mu <= V * g / (g - e). Proof: for U = a V with a >= 1, T_mu U = a T_mu V - (a - 1) k_mu
  <= a V + a e - (a - 1) g, so a = g / (g - e) gives T_mu U <= U, and a supersolution bounds the
  cost of mu from above. If e >= g there is no upper certificate yet.
* Lower side (always): for a <= 1, T(a V) >= a T V + (1 - a) g, so a = g / (g + d) gives
  a V <= T(a V), a subsolution, hence a V <= V*.

So the component's own multipliers are l_own = g / (g + d') and u_own = g / (g - e'), and its own
relative error is max(1 - l_own, u_own - 1).

Stopping uses the iteration alone: the loop stops when the relative error computed from e and d
(without delta) is at most `tolerance`. So a model whose rounding amplification delta / g (about
epsilon * value / g) exceeds `tolerance` still terminates, and the reported `error_bound`, which
includes delta, may then be larger than `tolerance`; it is infinite when e' >= g. The loop also stops
when e <= delta and d <= delta: the residuals are at the rounding floor and the reported bound cannot
improve by more than about a factor of two (soundness is untouched, only the moment to stop).

Across components. Every state keeps multipliers lo, hi with lo * V <= V* <= hi * V (goals: 1, 1).
Scaling the downstream values by a >= 1 scales a component's solution by at most a, and by a <= 1 by
at least a. So a component whose exit successors have multipliers (lo_j, hi_j) gets
l_d = min(1, min lo_j), u_d = max(1, max hi_j) and, for its states,

    lo = l_d * l_own * (1 - rho)        hi = u_d * u_own * (1 + rho)

where rho = (m + 2) * epsilon allows for float64 rounding: m is the largest number of terms in a
Bellman sum of the component, all terms are positive, so each sum has relative error below that.
An acyclic single state has l_own = u_own = 1 (one exact backup) plus the same rho. The reported
`error_bound` is the maximum over finite states of max(1 - lo, hi - 1).

Known weakness of g alone: g is the smallest constant term in the component, so the bound is loose when
these constant terms span many orders of magnitude inside one component (a cheap action whose
successors are also cheap), and a value much larger than g cannot reach a tolerance below about
epsilon * V / g. A free action (an unveil, a pick: ADR-0026, cost `FREE_ACTION_SHARE` of the cheapest
paid one) inside a cycle makes g that epsilon. So when the bound on g is above `ACCEPT_BOUND`, each
state's error is also measured against the cost ahead (#769, #842: `sides`, `widen`, and `certify` of
`_packed_solve` for the argument): for any `h >= 0` that is 0 outside the states measured, every action
pays at least `gamma = T h - h`, and `d <= t gamma` gives `V* >= V / (1 + t)` (`(V + t h) / (1 + t)` is a
subsolution); the greedy policy's `kappa = T_mu h - h` with `e <= t kappa` gives `V* <= V / (1 - t)`
(`(V - t h) / (1 - t)` is a supersolution of `T_mu`). With `h = 0` these are the multipliers above, per
state. `h` is `w / L` times the cheapest `j`-step costs for `j = 1..L`: its margin at a free state is the
paid step after it. Both bounds hold, so each side takes the better.
"""

import math
import sys
from collections.abc import Callable, Sequence

EPSILON = sys.float_info.epsilon
INF = math.inf
ACCEPT_BOUND = 1e-6  # a certified relative bound above this: the packed solve raises `ConvergenceError`, and either solver measures the cost ahead (the rounding of long sums gives 5e-8 on R04, 7e-8 on S02)
AHEAD_FIRST = 2  # the first window of the cost ahead that a state's error is also measured against (#769): a free step and the paid one after it; it doubles while the bound is above the one wanted (`widen`). It decides no answer, only how tight the bound is
AHEAD_LIMIT = 64  # the longest window of the cost ahead: a stop-and-say-so rail (OR-12) on its cost, one sweep of the graph a step; the packed solve's refusal names it
AHEAD_WEIGHT = 0.5  # w of the cost ahead: a paid state keeps at least 1 - w of its own cost as its margin, a free state gets w / L of the paid steps in its window


class ConvergenceError(RuntimeError):
    """A component could not reach the tolerance within `max_sweeps` (its sparse direct solve, if any, included).

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
    """`(l_own, u_own)` of a candidate with residuals `e` and `d` (u_own is infinity if e >= g; l_own is 0 at g = d = 0, where it says nothing)."""
    lower = g / (g + d) if g + d > 0.0 else 0.0
    upper = g / (g - e) if e < g else float("inf")
    return lower, upper


def relative_error(lower: float, upper: float) -> float:
    """The relative error implied by multipliers `lower <= 1 <= upper`."""
    return max(1.0 - lower, upper - 1.0)


# ---- the margin of the cost ahead (#769, #842), shared by the packed solve and the object solver ------------------------
# (standard library only, ADR-0063's amendment of ADR-0010: the packed solve passes numpy arrays, the object solver lists)


def lowered(sum_, h, grow):
    """`sum_ - h` less the rounding of the sum (`grow` of it: a computed sum of nonnegative terms is within that share of the exact one) and of the
    subtraction: at most the exact difference. Plain arithmetic, so it takes floats or arrays alike."""
    return sum_ - grow * sum_ - h - 2.0 * EPSILON * (sum_ + h)


def widen[H, M](
    ahead: Callable[[int], H],
    measure: Callable[[H], tuple[float, float, int, M]],
    best: tuple[float, float, M, int],
    wanted: float,
    longest: int,
) -> tuple[float, float, M, int]:
    """The better, on each side, of `best` (`(lower, upper, margin, 0)`: the bound on each state's own cost) and of the cost ahead over windows of
    `AHEAD_FIRST`, twice that, ... steps: `(lower, upper, margin, window)` of the window that last made either side better.

    `ahead(L)` is `h = (w / L) (C_1 + ... + C_L)`, `C_j = T^j 0` the cheapest `j`-step cost (0 outside the states measured), and `measure(h)` is
    `(lower, upper, stuck, gamma)`: the multipliers of the module docstring against `gamma = T h - h` and the greedy `kappa`, both lowered for
    rounding, with `stuck` the number of states without a margin. The cost ahead is measured only while the bound is above `wanted`, so a plan
    that certifies on its own costs keeps its numbers to the bit. The window doubles while the doubling does not make the bound clearly worse: a
    run of free steps with epsilon costs gives the same margin to every window until the window reaches the paid step after it, and then a far
    larger one. The last window tried is the first at least `longest` (a window as long as the states are many cannot meet a paid step it has
    not met)."""
    window, last, last_stuck = AHEAD_FIRST, INF, 0
    while not max(1.0 - best[0], best[1] - 1.0) <= wanted and window // 2 < longest:
        lower, upper, stuck, gamma = measure(ahead(window))
        if lower > best[0] or upper < best[1]:
            best = (max(lower, best[0]), min(upper, best[1]), gamma, window)
        now = max(1.0 - lower, upper - 1.0)
        if window > AHEAD_FIRST and not (now <= 2.0 * last if math.isfinite(now) else stuck < last_stuck):
            break  # worse than twice the last window's bound, or no bound and no fewer states without a margin (a free cycle: no window helps)
        last, last_stuck = now, stuck
        window *= 2
    return best


def _share(error: float, margin: float, carried: bool) -> float:
    if margin > 0.0:
        return error / margin
    return 0.0 if error == 0.0 and margin == 0.0 and carried else INF


def sides(
    d: Sequence[float], e: Sequence[float], gamma: Sequence[float], kappa: Sequence[float], escapes: Callable[[list[bool]], list[bool]]
) -> tuple[float, float, int]:
    """`(lower, upper, stuck)` for the margins `gamma` (every action) and `kappa` (the greedy one), per state in lists: `lower = 1 / (1 + max d /
    gamma)`, `upper = 1 / (1 - max e / kappa)`, `stuck` the states where either share is infinite (the list form of `_packed_solve._sides`).

    The upper side also proves the greedy policy proper: `V - h` falls by `kappa - e` a step, so a run spends a finite time where that is positive.
    A state with `e = kappa = 0` (a free action out of the component, value 0) falls by nothing; it is carried only if `escapes` (given the states of
    zero margin) says the policy leads it, with positive chance, out or to a state where `kappa > e`; otherwise it may lie in a closed class
    that never finishes (a free cycle with the values 0), and nothing can be said above."""
    zero = [ei == 0.0 and ki == 0.0 for ei, ki in zip(e, kappa)]
    carried = escapes(zero) if any(zero) else zero
    low = [_share(di, gi, True) for di, gi in zip(d, gamma)]
    high = [_share(ei, ki, ci) for ei, ki, ci in zip(e, kappa, carried)]
    t_low, t_high = max(low), max(high)
    lower = 1.0 / (1.0 + t_low) if math.isfinite(t_low) else 0.0
    upper = 1.0 / (1.0 - t_high) if t_high < 1.0 else INF
    return lower, upper, sum(1 for a, b in zip(low, high) if not math.isfinite(max(a, b)))
