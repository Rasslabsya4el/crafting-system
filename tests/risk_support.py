"""Shared helpers for the risk tests (not collected as tests): a seeded simulator and exact oracles.

The simulator and every oracle here are written independently of `crafting_system.risk`: the
simulator walks the policy one random outcome at a time, the oracles use exact `Fraction`
arithmetic on a probability mass function. Nothing here imports `risk`.
"""

import math
import random
from bisect import bisect_left, bisect_right
from fractions import Fraction
from itertools import accumulate

from crafting_system.solver import Action

GOAL = "goal"


def is_goal(state):
    return state == GOAL


def geometric_policy(a, b, cost):
    """One state `S` whose only action costs `cost` and ends in the goal with weight a, else loops (weight b)."""
    return {"S": Action("try", cost, (("goal", a), ("S", b)))}


def decimal(level):
    """The level as the decimal the caller meant (0.9 is 9/10, not its binary neighbour)."""
    return Fraction(repr(level))


# ---------------------------------------------------------------- simulation (TEST ONLY)


def compile_policy(policy):
    """Per state: the cost, the successors and their cumulative integer weights (for one `bisect` per step)."""
    compiled = {}
    for state, action in policy.items():
        targets = tuple(target for target, _ in action.outcomes)
        cumulative = tuple(accumulate(weight for _, weight in action.outcomes))
        compiled[state] = (action.cost, targets, cumulative, cumulative[-1])
    return compiled


def simulate_once(compiled, start, goal_test, rng, step_cap):
    """Total cost paid until a goal; `math.inf` when the walk reaches a state with no action or hits the cap."""
    state, total = start, 0.0
    for _ in range(step_cap):
        if goal_test(state):
            return total
        step = compiled.get(state)
        if step is None:
            return math.inf
        cost, targets, cumulative, whole = step
        total += cost
        state = targets[bisect_right(cumulative, rng.random() * whole)]
    return math.inf


def simulate(policy, start, goal_test, *, runs, seed, step_cap=10_000):
    """Sorted total costs of `runs` independent walks, from a generator seeded with `seed`."""
    rng = random.Random(seed)
    compiled = compile_policy(policy)
    return Sample(sorted(simulate_once(compiled, start, goal_test, rng, step_cap) for _ in range(runs)))


class Sample:
    """A sorted Monte Carlo sample of total costs (`math.inf` for a failed walk) and its plain estimators."""

    def __init__(self, costs):
        self.costs = costs
        self.n = len(costs)
        self.finite = [c for c in costs if math.isfinite(c)]

    def success(self):
        return len(self.finite) / self.n

    def success_standard_error(self):
        p = self.success()
        return math.sqrt(p * (1 - p) / self.n)

    def mean(self):
        return sum(self.finite) / self.n

    def mean_standard_error(self):
        mean = self.mean()
        return math.sqrt(sum((c - mean) ** 2 for c in self.finite) / (self.n - 1) / self.n)

    def variance(self):
        mean = self.mean()
        return sum((c - mean) ** 2 for c in self.finite) / (self.n - 1)

    def cdf_at(self, x):
        """Empirical P(C <= x)."""
        return bisect_right(self.costs, x) / self.n

    def cdf_below(self, x):
        """Empirical P(C < x)."""
        return bisect_left(self.costs, x) / self.n

    def tail_mean(self, level):
        """Mean of the worst (1 - level) share of the sample, splitting the atom at the cut."""
        share = (1 - level) * self.n
        whole = int(share)
        worst = sum(self.costs[self.n - whole :])
        if share > whole:
            worst += (share - whole) * self.costs[self.n - whole - 1]
        return worst / share

    def tail_mean_standard_error(self, level):
        """Standard error of `tail_mean`: std of (C - t)+ over sqrt(n) (1 - level), t the sample quantile."""
        cut = self.costs[math.ceil(level * self.n) - 1]
        excess = [max(c - cut, 0.0) for c in self.costs]
        mean = sum(excess) / self.n
        spread = math.sqrt(sum((e - mean) ** 2 for e in excess) / (self.n - 1))
        return spread / (math.sqrt(self.n) * (1 - level))


# ---------------------------------------------------------------- exact oracles


def geometric_quantile_steps(p, level):
    """Smallest k with 1 - (1-p)^k >= level, found by exact search (p, level are Fractions)."""
    q = 1 - p
    k = max(1, math.ceil(math.log(1 - float(level)) / math.log(float(q))) - 2)
    while 1 - q**k < level:
        k += 1
    while k > 1 and 1 - q ** (k - 1) >= level:
        k -= 1
    return k


def geometric_cvar(p, cost, level):
    """CVaR of `cost` times a geometric count: t + c q^k / (p (1 - level)) at t = c k (k the quantile)."""
    k = geometric_quantile_steps(p, level)
    return cost * k + cost * (1 - p) ** k / (p * (1 - level))


def geometric_moments(p, cost):
    return cost / p, cost**2 * (1 - p) / p**2


def pmf_quantile(pmf, level):
    """Smallest value x with P(C <= x) >= level, for a dict value -> Fraction."""
    running = Fraction(0)
    for x in sorted(pmf):
        running += pmf[x]
        if running >= level:
            return x
    raise ValueError("level not reached by the pmf")


def pmf_cvar(pmf, level):
    """CVaR by atom splitting: (sum over x > t of x P(x) + t (F(t) - level)) / (1 - level)."""
    t = pmf_quantile(pmf, level)
    cdf = sum(pr for x, pr in pmf.items() if x <= t)
    upper = sum(x * pr for x, pr in pmf.items() if x > t)
    return (upper + t * (cdf - level)) / (1 - level)


def pmf_moments(pmf):
    mean = sum(x * pr for x, pr in pmf.items())
    second = sum(x * x * pr for x, pr in pmf.items())
    return mean, second - mean * mean


def convolve(left, right):
    out = {}
    for x, px in left.items():
        for y, py in right.items():
            out[x + y] = out.get(x + y, 0) + px * py
    return out


def geometric_pmf(p, cost, tail):
    """The pmf of `cost` times a geometric count, cut where the remaining mass is below `tail`."""
    pmf, q, k = {}, 1 - p, 1
    while q ** (k - 1) >= tail:
        pmf[cost * k] = q ** (k - 1) * p
        k += 1
    return pmf


def path_pmf(table, start, goal_test=is_goal):
    """Exact cost distribution of an acyclic policy, by enumerating every path with Fractions.

    `table` maps a state to an `Action`; each float cost enters as its exact binary value.
    """
    pmf = {}

    def walk(state, paid, prob):
        if goal_test(state):
            pmf[paid] = pmf.get(paid, 0) + prob
            return
        action = table[state]
        total = sum(weight for _, weight in action.outcomes)
        for successor, weight in action.outcomes:
            walk(successor, paid + Fraction(action.cost), prob * Fraction(weight, total))

    walk(start, Fraction(0), Fraction(1))
    return pmf
