"""Free actions counted apart from the grid (ticket #349, ADR-0026).

The planner gives an action that consumes nothing (an unveil, a pick) a cost of `FREE_ACTION_SHARE` (1e-6) of the cheapest offer that costs
something, because the solver needs a positive cost on every action. The budget DP steps by the cheapest action, so a policy that holds
such an action got a step of that epsilon: `max_bins` bins covered a few Chaos of a route that costs hundreds, and the 0.9 quantile and the
CVaR came back unresolved.

The caller names its free cost (`evaluate(free_cost=...)`); a state whose action costs at most that is a free state. Let C be the real cost,
C0 the cost with the free states paying nothing, and E = C - C0 what they pay, at most `f` per visit (f the largest cost of a free state),
so E <= f N for N the number of visits of free states. Then C0 <= C <= C0 + E on every path, and

* the grid is set by the paying states alone, with the free states at 0 bins on both the lower and the upper chain; they are folded away
  (`_fold`), so the DP moves mass only through paying states;
* N has a distribution of its own, found by the same DP with the paying states folded away and 1 bin on each free state. The smallest `n`
  with P(N > n) <= `FREE_TAIL` bounds the extra cost: E <= t = f n except with probability `FREE_TAIL`;
* quantiles: F_C(x) <= F_C0(x) and F_C(x) >= F_C0(x - t) - FREE_TAIL, so the quantile at level L lies between the lower chain's quantile at L
  and the upper chain's at L + FREE_TAIL, plus t;
* CVaR is monotone and subadditive, and CVaR_L(E) <= E[E] / (1 - L), so it lies between the lower chain's and the upper chain's plus
  E[E] / (1 - L) with E[E] <= f E[N] from the solver;
* mean, variance, success probability are the solver's, with the real costs, as before.

The allowance t and the tail are in `GridInfo.free_allowance` and `free_tail`, and the quantile and CVaR intervals already contain them.
When a free component or a paying component is too large to fold, or the count of free visits does not settle in `COUNT_BINS`, there is no
such grid and the caller keeps the ordinary one.
"""

import math
from collections.abc import Sequence

from ._budget import run_budget, tail_mean
from ._chain import UNIT_TOLERANCE, Chain
from ._fold import fold_free
from ._moments import interval

FREE_TAIL = 1e-9  # the probability with which the free states may pay more than `free_allowance`
COUNT_BINS = 100_000  # the most free visits the count DP follows
PAID_CHARGE = 1e-3  # a paying state is charged this share of the free cost when the solver counts the free visits (it needs a positive cost)


def is_free(cost: float, free_cost: float) -> bool:
    """Whether an action of this cost is free: at most the free cost, up to the relative tolerance of the grid."""
    return cost <= free_cost * (1.0 + UNIT_TOLERANCE)


def free_states(chain: Chain, free_cost: float) -> list[int]:
    """The states that can finish whose action is free."""
    return [i for i in chain.finishing_states() if is_free(chain.action[i].cost, free_cost)]


def free_allowance(chain: Chain, free: Sequence[int]) -> tuple[float, int] | None:
    """`(f, n)`: the largest cost of a free state and a count of free visits that is exceeded with probability at most `FREE_TAIL`.

    `None` when the paying states cannot be folded away or the count does not settle in `COUNT_BINS`.
    """
    largest = max(chain.action[i].cost for i in free)
    bins = [0] * len(chain.states)
    for i in free:
        bins[i] = 1
    folded = fold_free(chain, bins)  # the paying states have 0 bins here and are folded away
    if folded is None:
        return None
    run = run_budget(
        folded.chain, bins, target=1.0 - FREE_TAIL, tail_mass=FREE_TAIL, max_bins=COUNT_BINS, initial=folded.initial, goal_mass=folded.goal_mass
    )
    visits = run.first_reaching(1.0 - FREE_TAIL + run.delta)
    return None if visits is None else (largest, visits)


def free_means(
    chain: Chain,
    free: Sequence[int],
    step: float,
    low_bins: Sequence[int],
    high_bins: Sequence[int],
    solve_costs,
) -> tuple[float, float, float]:
    """`(mean of the lower chain, mean of the upper chain, E[E])` as certified ends: a lower, an upper, an upper.

    The solver needs a positive cost on every state, so a free state is charged `f` on both chains and the charge is given back from an
    upper bound of `f E[N]`: the mean of a chain on which a free state costs `f` and a paying state `PAID_CHARGE f`, which is at least
    `f E[N]` and at most `f E[N] + PAID_CHARGE f E[paying visits]`, a millionth of the mean or less since `f` is a millionth of the cheapest cost.
    """
    largest = max(chain.action[i].cost for i in free)
    free_set = set(free)
    finishing = chain.finishing_states()
    size = len(chain.states)
    low_costs, high_costs, count_costs = [0.0] * size, [0.0] * size, [0.0] * size
    for i in finishing:
        if i in free_set:
            low_costs[i] = high_costs[i] = count_costs[i] = largest
        else:
            low_costs[i], high_costs[i], count_costs[i] = low_bins[i] * step, high_bins[i] * step, PAID_CHARGE * largest
    counted, counted_error = solve_costs(chain, count_costs)
    owed = interval(counted[0], counted_error)[1]
    low_mean, low_error = solve_costs(chain, low_costs)
    if list(low_bins) == list(high_bins):
        high_mean, high_error = low_mean, low_error
    else:
        high_mean, high_error = solve_costs(chain, high_costs)
    return max(interval(low_mean[0], low_error)[0] - owed, 0.0), interval(high_mean[0], high_error)[1], owed


def quantile(level: float, step: float, low_run, high_run, allowance: float) -> tuple[float, float, float]:
    """`(value, low, high)` of the quantile at `level` of the real cost; `high` is infinite when the upper run did not reach the level."""
    k_low = low_run.first_reaching(level - low_run.delta)
    low = (low_run.bins if k_low is None else k_low) * step
    asked = level + FREE_TAIL + high_run.delta
    k_high = high_run.first_reaching(asked) if asked < 1.0 else None
    if k_high is None:
        return math.inf, low, math.inf
    high = k_high * step + allowance
    return (low + high) / 2.0, low, high


def cvar(
    level: float, step: float, low_run, high_run, mean_low: float, mean_high: float, extra: float
) -> tuple[float, float, float]:
    """`(value, low, high)` of the CVaR at `level` of the real cost; `extra` is an upper bound of E[E]."""
    below = tail_mean(low_run, step, level, mean_low)
    if below is None:
        return math.inf, low_run.bins * step, math.inf
    low = max(below[0] - below[2], below[1])
    above = tail_mean(high_run, step, level, mean_high)
    if above is None:
        return math.inf, low, math.inf
    high = above[0] + above[2] + extra / (1.0 - level)
    return (low + high) / 2.0, low, high
