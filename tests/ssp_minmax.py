"""Random min-max models and independent oracles for the variants tests (not collected as tests).

`random_game(seed)` returns a `Game`: states `0..size-1` are not goals, the goal is `size`, and
`table[s]` lists the actions of state `s` as `(label, cost, variants)` with every variant a list of
`(state, weight)`. Every variant gives the goal a positive weight, so every policy of the controller
and every choice of nature is proper and each model has a finite value everywhere.

The oracles do not use the solver: `brute_pessimistic` tries EVERY stationary policy of the
controller and, for each, EVERY stationary choice of the variants (nature), takes the worst, then
the best policy; `brute_optimistic` lets nature help (the best choice of variant). Each policy
is evaluated by a linear solve. `backup` is the pessimistic Bellman operator, for the identity.
"""

import itertools
import random
from dataclasses import dataclass

import numpy as np

from crafting_system.solver import Action, TabularModel, VariantAction


@dataclass(frozen=True)
class Game:
    size: int
    table: tuple  # state -> tuple of (label, cost, tuple of variants (tuples of (state, weight)))

    @property
    def goal(self):
        return self.size


def random_game(seed, *, max_states=4, max_actions=3, max_variants=3):
    rng = random.Random(seed)
    size = rng.randint(2, max_states)
    table = []
    for state in range(size):
        actions = []
        for index in range(rng.randint(1, max_actions)):
            variants = []
            for _ in range(rng.randint(1, max_variants)):
                weights = [rng.randint(0, 5) for _ in range(size + 1)]
                weights[size] += 1  # the goal is always reachable
                variants.append(tuple((target, w) for target, w in enumerate(weights) if w))
            actions.append((f"{state}.{index}", round(rng.uniform(0.5, 3.0), 3), tuple(variants)))
        table.append(tuple(actions))
    return Game(size, tuple(table))


def to_game_model(game, *, plain_if_single=True):
    """A `TabularModel` of the game; an action with one variant is a plain `Action` (a mix of both kinds)."""
    rows = {}
    for state, actions in enumerate(game.table):
        rows[state] = [
            Action(label, cost, variants[0])
            if plain_if_single and len(variants) == 1
            else VariantAction(label, cost, variants)
            for label, cost, variants in actions
        ]
    return TabularModel([game.goal], rows)


def _evaluate(game, policy, choice):
    """The cost vector of the policy (state -> action) with nature's choice (state -> variant)."""
    size = game.size
    matrix = np.eye(size + 1)
    cost = np.zeros(size + 1)
    for state in range(size):
        label, c, variants = game.table[state][policy[state]]
        variant = variants[choice[state]]
        total = sum(w for _, w in variant)
        cost[state] = c
        for target, w in variant:
            matrix[state, target] -= w / total
    matrix[size] = 0.0
    matrix[size, size] = 1.0
    return np.linalg.solve(matrix, cost)


def _brute(game, pessimistic):
    size = game.size
    best = np.full(size + 1, np.inf)
    for policy in itertools.product(*[range(len(game.table[s])) for s in range(size)]):
        ranges = [range(len(game.table[s][policy[s]][2])) for s in range(size)]
        if pessimistic:
            value = np.full(size + 1, -np.inf)
            for choice in itertools.product(*ranges):
                value = np.maximum(value, _evaluate(game, policy, choice))
        else:
            value = np.full(size + 1, np.inf)
            for choice in itertools.product(*ranges):
                value = np.minimum(value, _evaluate(game, policy, choice))
        best = np.minimum(best, value)
    return best


def brute_pessimistic(game):
    return _brute(game, True)


def brute_optimistic(game):
    return _brute(game, False)


def backup(game, value):
    """The pessimistic Bellman operator on a value vector (goal 0): min over actions of cost + max over variants."""
    out = np.zeros(game.size + 1)
    for state in range(game.size):
        best = np.inf
        for _, cost, variants in game.table[state]:
            worst = max(sum(w * value[t] for t, w in variant) / sum(w for _, w in variant) for variant in variants)
            best = min(best, cost + worst)
        out[state] = best
    return out


def smallest_cost(game):
    return min(cost for actions in game.table for _, cost, _ in actions)
