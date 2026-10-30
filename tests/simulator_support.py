"""Shared helpers for the simulator tests (not collected as tests): fake actions, a chain oracle, a cache.

The fake actions are objects with
`outcomes(data, item)` returning an object with `sample(rng)`, which is all the simulator asks of an
action. Their items are real fixture amulets told apart by the mod they carry: the goal item holds
the marker mod `TARGET`, the other states hold other mods or none.
"""

import math
import statistics
from fractions import Fraction

from actions_support import DATA, RESIST, TARGET, amulet, roll

from crafting_system.simulator import Step

DEAD_MOD = "LifeLeechPermyriadSuffix1"

# one real item per state name of the fake chains
ITEMS = {
    "S": amulet(),
    "T": amulet(roll(RESIST)),
    "goal": amulet(roll(TARGET)),
    "dead": amulet(roll(DEAD_MOD)),
}
STATE_OF = {item: state for state, item in ITEMS.items()}

# five standard errors as a two-sided confidence: an interval at this level misses the truth about once in 1.7 million
FIVE_SIGMA = 2 * statistics.NormalDist().cdf(5.0) - 1


def holds_target(item) -> bool:
    return any(entry.mod_id == TARGET for entry in item.mods)


class Draw:
    """A sampler: one of the listed items, with probability proportional to its integer weight."""

    def __init__(self, items, weights):
        self.items, self.weights, self.total = items, weights, sum(weights)

    def sample(self, rng):
        point = rng.random() * self.total
        for item, weight in zip(self.items, self.weights, strict=True):
            point -= weight
            if point < 0.0:
                return item
        return self.items[-1]


class FakeAction:
    """An action whose result depends only on the state of the item: `row` is ((state, weight), ...)."""

    def __init__(self, row):
        self.row = tuple(row)

    def outcomes(self, data, item):
        return Draw([ITEMS[state] for state, _ in self.row], [weight for _, weight in self.row])


def chain_policy(chain):
    """A policy for `chain`, a dict state -> (cost, ((next state, weight), ...)): item -> Step or None."""
    steps = {ITEMS[state]: Step(FakeAction(row), cost) for state, (cost, row) in chain.items()}
    return steps.get


def solve_chain(chain, reward):
    """Exact expected accumulated reward from each state of `chain`, by Gaussian elimination in Fractions.

    `reward(state, cost, row)` is what one visit of `state` earns. A state of the rows that is not a
    key of `chain` (the goal, a dead end) is absorbing and earns nothing. Cost 1 per visit gives the
    expected number of steps; the cost itself the expected total paid; the weight going to "goal"
    the success probability. Written from the definition, independent of any solver in the package.
    """
    states = list(chain)
    index = {state: i for i, state in enumerate(states)}
    size = len(states)
    matrix = [[Fraction(0)] * (size + 1) for _ in states]
    for state, (cost, row) in chain.items():
        i, total = index[state], sum(weight for _, weight in row)
        matrix[i][i] += 1
        matrix[i][size] = Fraction(reward(state, cost, row))
        for target, weight in row:
            if target in index:
                matrix[i][index[target]] -= Fraction(weight) / total
    for column in range(size):
        pivot = next(r for r in range(column, size) if matrix[r][column] != 0)
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        matrix[column] = [x / matrix[column][column] for x in matrix[column]]
        for r in range(size):
            if r != column and matrix[r][column] != 0:
                factor = matrix[r][column]
                matrix[r] = [a - factor * b for a, b in zip(matrix[r], matrix[column], strict=True)]
    return {state: matrix[index[state]][size] for state in states}


def paid(state, cost, row):
    return Fraction(cost)


def one_step(state, cost, row):
    return Fraction(1)


def steps_mean_and_sd(chain, start):
    """Exact mean and sd of the number of steps from `start`: E[X^2] solves x2 = 1 + 2 sum P x1 + sum P x2."""
    mean = solve_chain(chain, one_step)

    def second(state, cost, row):
        total = sum(weight for _, weight in row)
        return 1 + 2 * sum(Fraction(weight) / total * mean.get(target, 0) for target, weight in row)

    second_moment = solve_chain(chain, second)
    return float(mean[start]), math.sqrt(float(second_moment[start] - mean[start] ** 2))


def reaches_goal(state, cost, row):
    total = sum(weight for _, weight in row)
    return Fraction(sum(weight for target, weight in row if target == "goal"), total)


class Memoized:
    """An action that remembers its `outcomes`, to make the long real-action runs affordable.

    What a reroll can leave behind depends only on the base, the item level, the rarity and the
    fractured mods of the item (the documented `retained` item of `Outcomes`), so building it once
    per such item changes no result; the sampler is still called on every step.
    """

    def __init__(self, action):
        self.action, self.cache = action, {}

    def outcomes(self, data, item):
        key = (item.base_id, item.item_level, item.rarity, item.fractured_mods, item.influences, item.corrupted)
        if key not in self.cache:
            self.cache[key] = self.action.outcomes(data, item)
        return self.cache[key]


__all__ = [
    "DATA", "DEAD_MOD", "FIVE_SIGMA", "ITEMS", "STATE_OF", "Draw", "FakeAction", "Memoized",
    "chain_policy", "holds_target", "one_step", "paid", "reaches_goal", "solve_chain", "steps_mean_and_sd",
]  # fmt: skip
