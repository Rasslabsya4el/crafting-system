"""TEST ORACLE: the pure-Python budget DP as it was before #82 (kept verbatim to check the fast one against).

The budget DP: the distribution of the total cost on a grid, for the chain of a fixed policy.

Costs are floats, so cost is counted in whole steps of a grid step D. Every state that can still
finish pays a positive whole number of bins `k`, which makes the dependency of (state, bins paid)
on earlier bins acyclic even when the state graph has cycles. The DP is forward and rolling:
`pending[b]` holds the mass of each state that has paid exactly `b` bins and not yet moved. Bin
`b` is popped, and each state's mass moves `k` bins ahead: the part that reaches a goal is added
to the absorbed mass `pmf[b + k]`, the part that stays on a state that can still finish goes to
`pending[b + k]`, and the part that goes to a stuck or trapped state is lost. Mass that would land
above the cap `max_bins` is not stored; it is counted as unresolved. A bin is processed once, so
the work is O(bins * edges) and the memory O(window * states) for the pending window (the
longest move, in bins) plus O(bins) floats for the cumulative distribution that quantiles and
CVaR are read from.

The run stops when the target is met (proper policy: the cumulative absorbed mass reaches the
highest asked level plus the rounding allowance; otherwise: the mass still in flight is at most
`tail_mass`), when the cap is reached, or when no mass is left. It never truncates silently:
`unresolved` is the probability still in flight at the stop, so the absorbed mass and the
absorbed mass plus the unresolved mass bracket the success probability of the chain.

Rounding. The cumulative F is a running float sum, so each F(i) carries an error of a few eps per
bin run. `delta = 1e-12 + 4 eps bins` is the allowance: "level L reached" means F >= L - delta at
the low end of an interval and F >= L + delta at the high end. All bounds therefore hold up to
ties within delta in probability.
"""

import sys
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum

from crafting_system.risk._chain import Chain

EPS = sys.float_info.epsilon
BASE_DELTA = 1e-12


def rounding_allowance(bins: int) -> float:
    return BASE_DELTA + 4.0 * EPS * bins


@dataclass(frozen=True, slots=True)
class BudgetRun:
    """`cdf[i]` is P(grid cost <= i bins) for i = 0..bins; `unresolved` is the mass still in flight."""

    cdf: list[float]
    unresolved: float

    @property
    def bins(self) -> int:
        return len(self.cdf) - 1

    @property
    def absorbed(self) -> float:
        return self.cdf[-1]

    @property
    def delta(self) -> float:
        return rounding_allowance(self.bins)

    def first_reaching(self, threshold: float) -> int | None:
        """The first bin count whose cumulative mass is at least `threshold`, or `None` if the run never got there."""
        i = bisect_left(self.cdf, threshold)
        return i if i < len(self.cdf) else None


def run_budget(
    chain: Chain,
    bin_cost: Sequence[int],
    *,
    target: float | None,
    tail_mass: float,
    max_bins: int,
) -> BudgetRun:
    """Run the DP with `bin_cost[i]` whole bins per step in state i.

    `target` is the highest level to certify (a proper policy) or `None` to run until the mass
    in flight is at most `tail_mass`.
    """
    moves: dict[int, tuple[float, list[tuple[int, float]], float, float]] = {}
    for i in chain.finishing_states():
        absorbed = 0.0
        onward: list[tuple[int, float]] = []
        lost = 0.0
        for j, p in chain.succ[i]:
            if chain.goal[j]:
                absorbed += p
            elif chain.can_finish[j]:
                onward.append((j, p))
            else:
                lost += p
        moves[i] = (absorbed, onward, lost, absorbed + fsum(p for _, p in onward))

    pending: dict[int, dict[int, float]] = {0: {0: 1.0}}
    pmf = [0.0]
    cdf: list[float] = []
    overflow = 0.0
    lost_total = 0.0
    running = 0.0
    b = 0
    while True:
        if b < len(pmf):
            running += pmf[b]
        cdf.append(running)
        if b >= max_bins or (not pending and b + 1 >= len(pmf)):
            break
        if target is not None:
            if running >= target + rounding_allowance(b):
                break
        elif 1.0 - lost_total - running <= tail_mass:
            break
        for i, mass in pending.pop(b, {}).items():
            absorbed, onward, lost, stay = moves[i]
            lost_total += mass * lost
            ahead = b + bin_cost[i]
            if ahead > max_bins:
                overflow += mass * stay
                continue
            if absorbed:
                if ahead >= len(pmf):
                    pmf.extend([0.0] * (ahead + 1 - len(pmf)))
                pmf[ahead] += mass * absorbed
            if onward:
                slot = pending.setdefault(ahead, {})
                for j, p in onward:
                    slot[j] = slot.get(j, 0.0) + mass * p
        b += 1
    unresolved = fsum(m for slot in pending.values() for m in slot.values()) + fsum(pmf[b + 1 :]) + overflow
    return BudgetRun(cdf, unresolved)


def tail_mean(run: BudgetRun, step: float, level: float, mean: float) -> tuple[float, float, float] | None:
    """`(cvar, t, allowance)` of the grid cost at `level`, or `None` when the run never reached the level.

    Rockafellar-Uryasev: CVaR = t + (E[X] - E[min(X, t)]) / (1 - level) at t, the quantile, with
    E[min(X, t)] = step * sum_{i < k} (1 - F(i)) for t = k * step (atoms at t are handled). `mean`
    is E[X]. `allowance` is the outward widening for the rounding of F, delta * (t + E[X]) / (1 - level).
    """
    k = run.first_reaching(level - run.delta)
    if k is None:
        return None
    t = k * step
    clipped = step * fsum(1.0 - run.cdf[i] for i in range(k))
    allowance = run.delta * (t + mean) / (1.0 - level)
    return t + (mean - clipped) / (1.0 - level), t, allowance
