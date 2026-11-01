"""The budget DP as dense matrix-vector products, for a policy whose mass cycles through few bin costs.

The same DP as `_run_plain` and `_Dp` in `_budget.py` (the distribution of the total cost in whole
bins, every state that can finish paying a positive whole number of bins `k`), organised for a
chain with many states, many successors per state and long runs of bins. There the entry based
engine expands every (bin, state) entry along every onward edge: R13 (191 states that can
finish, about 97 successors each, 140,000 bins to p90, almost all the mass cycling through one
class of 132 one-bin states) is 3e9 edge expansions. Here the states that can finish are numbered
`0..n-1` and sorted by their bin cost `k`, so the states of one cost class are a contiguous slice.
The chain is one dense matrix of n rows: the onward probabilities (n columns) and four more
columns, the probability of a goal (`absorbed`), of a stuck or trapped state (`lost`), of either
a goal or onward (`stay`) and of onward only. The pending mass is a ring buffer `ring[W, n]`,
one row per bin ahead, with W one more than the longest move so that a move never lands on the
row being read. A bin is processed by one product `row[class slice] @ matrix[class slice]` per
cost class: the first n entries are added to the ring at bin `b + k`, the next ones are the
absorbed mass added to `pmf[b + k]`, the lost mass, and the mass that would land above the cap
`max_bins`, which is not stored but counted as unresolved. So the work is one small product per
bin and cost class, whatever the number of edges.

The result equals the plain bin by bin DP up to the float rounding of the order of additions:
the same stop rules (cap, nothing left in flight, `target` met with the rounding allowance,
`tail_mass`), the same cumulative distribution, the same `unresolved`, summed from its parts
(`fsum`) and exactly 0.0 when nothing is left. The run may start from several states at once:
`initial` holds (state, mass) pairs at bin 0 and `goal_mass` is mass already absorbed there. What
is left of 1 is lost at bin 0.

The ring has `(longest move + 1) * n` cells and the matrix `n * (n + 4)`: `fits_dense` says
whether the engine takes the chain, and `run_dense` raises `ValueError` when it does not.
"""

from collections.abc import Sequence
from math import fsum

import numpy as np

from ._budget import BudgetRun, _grown, rounding_allowance
from ._chain import Chain

DENSE_LIMIT = 50_000_000  # the most cells the ring buffer (and the matrix) may have
LOST_FLOOR = 1e-15  # a smaller remainder of the starting mass is float noise, not lost mass


def _capped_costs(chain: Chain, bin_cost: Sequence[int], max_bins: int) -> tuple[list[int], dict[int, int]]:
    finishing = chain.finishing_states()
    lowest = min((bin_cost[i] for i in finishing), default=1)
    if lowest < 1:
        raise ValueError(f"every state that can finish must cost at least one bin, got {lowest!r}")
    return finishing, {i: min(bin_cost[i], max_bins + 1) for i in finishing}  # a move past the cap overflows, however long


def _cells(states: int, costs: dict[int, int]) -> int:
    width = max(costs.values(), default=1) + 1
    return max(width * states, states * (states + 4))


def fits_dense(chain: Chain, bin_cost: Sequence[int], max_bins: int) -> bool:
    """Whether `run_dense` takes the chain: its ring buffer, `(longest move + 1) * n` cells, is within the limit."""
    finishing, costs = _capped_costs(chain, bin_cost, max_bins)
    return _cells(len(finishing), costs) <= DENSE_LIMIT


def run_dense(
    chain: Chain,
    bin_cost: Sequence[int],
    *,
    initial: Sequence[tuple[int, float]],
    goal_mass: float = 0.0,
    target: float | None,
    tail_mass: float,
    max_bins: int,
) -> BudgetRun:
    """Run the DP with `bin_cost[i]` whole bins per step in state i, from `initial` at bin 0.

    `initial` is (state index, mass) pairs of states that can finish; `goal_mass` is already
    absorbed at bin 0. `target` and `tail_mass` are as in `run_budget`.
    """
    finishing, costs = _capped_costs(chain, bin_cost, max_bins)
    n = len(finishing)
    if _cells(n, costs) > DENSE_LIMIT:
        raise ValueError(f"the dense engine needs {_cells(n, costs)} cells for {n} states, the limit is {DENSE_LIMIT}")
    order = sorted(finishing, key=lambda i: (costs[i], i))
    position = {state: p for p, state in enumerate(order)}
    width = costs[order[-1]] + 1 if order else 2

    matrix = np.zeros((n, n + 4))
    for p, i in enumerate(order):
        goal = 0.0
        gone = 0.0
        onward: list[float] = []
        for j, prob in chain.succ[i]:
            if chain.goal[j]:
                goal += prob
            elif chain.can_finish[j]:
                if j not in position:
                    raise ValueError(f"state {j!r} can finish but is not expanded: the dense engine cannot move its mass")
                matrix[p, position[j]] = prob
                onward.append(prob)
            else:
                gone += prob
        total = fsum(onward)
        matrix[p, n : n + 4] = goal, gone, goal + total, total
    classes: list[tuple[int, int, int, np.ndarray, np.ndarray, bool, bool]] = []
    low = 0
    while low < n:
        k = costs[order[low]]
        high = low
        while high < n and costs[order[high]] == k:
            high += 1
        block = matrix[low:high]
        classes.append((k, low, high, block, np.empty(n + 4), bool(block[:, n + 3].any()), bool(block[:, n].any())))
        low = high

    ring = np.zeros((width, n))
    pending: set[int] = set()
    for state, mass in initial:
        if state not in position:
            raise ValueError(f"initial state {state!r} cannot finish: it is not a state the dense engine moves")
        ring[0, position[state]] += mass
        if mass > 0.0:
            pending.add(0)
    pmf = np.zeros(1024)
    pmf[0] = goal_mass
    pmf_end = 1  # one past the last bin an absorbing move has reached
    remainder = 1.0 - goal_mass - fsum(mass for _, mass in initial)
    lost_total = remainder if remainder > LOST_FLOOR else 0.0
    cdf: list[float] = []
    overflow = 0.0
    running = 0.0
    b = 0
    while True:
        if b < pmf_end:
            running += float(pmf[b])
        cdf.append(running)
        if b >= max_bins or (not pending and b + 1 >= pmf_end):
            break
        if target is not None:
            if running >= target + rounding_allowance(b):
                break
        elif 1.0 - lost_total - running <= tail_mass:
            break
        if b in pending:
            pending.remove(b)
            row = ring[b % width]
            for k, lo, hi, block, v, onward_any, absorbed_any in classes:
                np.dot(row[lo:hi], block, out=v)
                reached, gone, stay, moving = v[n:].tolist()
                lost_total += gone
                ahead = b + k
                if ahead > max_bins:
                    overflow += stay
                    continue
                if absorbed_any and reached:
                    if ahead >= pmf.size:
                        pmf = _grown(pmf, ahead + 1)
                    pmf[ahead] += reached
                    if ahead >= pmf_end:
                        pmf_end = ahead + 1
                if onward_any and moving:
                    ring[ahead % width] += v[:n]
                    pending.add(ahead)
            row.fill(0.0)
        b += 1
    unresolved = fsum((fsum(ring.sum(axis=1).tolist()), fsum(pmf[b + 1 : pmf_end].tolist()), overflow))
    return BudgetRun(cdf, unresolved)
