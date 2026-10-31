"""Two bounds around one policy: `solve` on an optimistic and a pessimistic model (ADR-0023).

The optimistic model offers at least what the problem offers, so its value is below the optimum;
the pessimistic model offers at most that, so its best policy is a policy of the problem and its
value is above that policy's cost: `V- <= V* <= J(pi) <= V+`. `solve` returns values with
`V(1 - e) <= V* <= V(1 + e)`, so the certified lower bound is `V-(1 - e-)` and the upper bound
`V+(1 + e+)`. Both are rounded outward, so float rounding never moves a bound inward.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ._model import Action, Model
from ._solve import solve

INF = math.inf


@dataclass(frozen=True, slots=True)
class Bounds[S]:
    """What `solve_bounds` returns.

    `lower` holds, for every state of the optimistic solution, a certified lower bound on the
    optimum, and `upper` holds, for every state of the pessimistic solution, a certified upper
    bound on the cost of `policy` (and so on the optimum). Goals have 0.0 on both sides and a state
    with no proper policy in a model has `math.inf` on that side. `policy` is the pessimistic
    solution's policy, unchanged. `gap` is the worst `gap_at` over the starts. `optimistic_error`
    and `pessimistic_error` are the two `Solution.error_bound`s.
    """

    lower: Mapping[S, float]
    upper: Mapping[S, float]
    policy: Mapping[S, Action[S]]
    gap: float
    optimistic_error: float
    pessimistic_error: float

    def gap_at(self, state: S) -> float:
        """The certified relative gap `upper / lower - 1` of a state present in both bounds.

        Rules: both sides 0 gives 0.0; lower 0 below a positive upper gives `math.inf`; both
        `math.inf` gives 0.0 (the value is infinite and certified, since the optimistic model
        already offers everything); an infinite upper over a finite lower gives `math.inf`;
        otherwise the quotient is rounded up and the gap is never negative. The gap bounds the real
        error of the policy: `J(pi) / V* - 1 <= gap`. Raises `KeyError` for a state missing from
        either side.
        """
        return _gap(self.lower[state], self.upper[state])


def solve_bounds[S](
    optimistic: Model[S],
    pessimistic: Model[S],
    starts: Iterable[S],
    *,
    tolerance: float = 1e-10,
    direct_solve_limit: int = 64,
    max_sweeps: int = 100_000,
) -> Bounds[S]:
    """Solve both models from `starts` with the same options and certify the interval.

    If `optimistic is pessimistic` the model is solved once and its one solution serves both sides.
    The models are not otherwise checked, except that a state present in both bounds with its lower
    bound above its upper bound raises `ValueError`: no pair of an optimistic and a pessimistic
    model can do that, so the two models are not such a pair.
    """
    starts = list(starts)
    options = {"tolerance": tolerance, "direct_solve_limit": direct_solve_limit, "max_sweeps": max_sweeps}
    below = solve(optimistic, starts, **options)
    above = below if optimistic is pessimistic else solve(pessimistic, starts, **options)
    lower = {state: _lower_bound(value, below.error_bound) for state, value in below.values.items()}
    upper = {state: _upper_bound(value, above.error_bound) for state, value in above.values.items()}
    for state, low in lower.items():
        if state in upper and low > upper[state]:
            raise ValueError(
                f"state {state!r} has a lower bound {low!r} above its upper bound {upper[state]!r}: "
                "the two models are not an optimistic and a pessimistic pair"
            )
    gap = max((_gap(lower[state], upper[state]) for state in starts), default=0.0)
    return Bounds(lower, upper, above.policy, gap, below.error_bound, above.error_bound)


def _lower_bound(value: float, error: float) -> float:
    """`value * (1 - error)` rounded down; 0.0 and `math.inf` stay as they are."""
    if value == 0.0 or value == INF:
        return value
    factor = math.nextafter(1.0 - error, -INF) if error < 1.0 else 0.0
    if factor <= 0.0:
        return 0.0
    return max(0.0, math.nextafter(value * factor, -INF))


def _upper_bound(value: float, error: float) -> float:
    """`value * (1 + error)` rounded up; 0.0 and `math.inf` stay as they are."""
    if value == 0.0 or value == INF:
        return value
    if error == INF:
        return INF
    return math.nextafter(value * math.nextafter(1.0 + error, INF), INF)


def _gap(lower: float, upper: float) -> float:
    """The gap rules of `Bounds.gap_at` for one pair of bounds with `lower <= upper`."""
    if upper == 0.0:
        return 0.0
    if lower == 0.0:
        return INF
    if upper == INF:
        return 0.0 if lower == INF else INF
    return max(0.0, math.nextafter(upper / lower, INF) - 1.0)
