"""A fixed policy with the states that behave alike made one (ticket #717).

Two states of a policy whose actions cost the same, and whose outcomes fall on the same blocks of states in the same proportions, have the
same distribution of the cost still to pay; so do the states those outcomes lead to, and so on. Such states are one block (the coarsest
partition with that property, found by refining it until it stops moving), and one state of each block stands for it: the lumped policy has
the cost distribution of the policy, the odds, the mean, the variance, the quantiles and the CVaR included, and the budget DP runs over the
blocks instead of over every state. A route of an item with many mods (R13's Alteration spam, 2,887 states) has a handful of blocks.

A goal is a block of its own; so are the stuck states (no policy entry, the mass that reaches one is lost). A policy whose actions consume other
items (`extra_inputs`) is left as it is: its cost is not a function of the block the action leads to.
"""

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import gcd

from ..solver import Action


@dataclass(frozen=True, slots=True)
class Lumped[S]:
    """`policy`, `start` and `is_goal` to give `evaluate` in place of the original ones."""

    policy: Mapping[S, Action[S]]
    start: S
    is_goal: Callable[[S], bool]


def lump[S](policy: Mapping[S, Action[S]], start: S, is_goal: Callable[[S], bool]) -> Lumped[S]:
    """The policy on one state per block of states that behave alike; the arguments themselves when no two states do."""
    unchanged = Lumped(policy, start, is_goal)
    index: dict[S, int] = {start: 0}
    states: list[S] = [start]
    actions: list[Action[S] | None] = []
    goal: list[bool] = []
    queue = deque([0])
    while queue:
        i = queue.popleft()
        state = states[i]
        chosen = None
        if is_goal(state):
            goal.append(True)
        else:
            goal.append(False)
            chosen = policy.get(state)
            if chosen is not None:
                if chosen.extra_inputs:
                    return unchanged
                for target, weight in chosen.outcomes:
                    if weight > 0 and target not in index:
                        index[target] = len(states)
                        states.append(target)
                        queue.append(index[target])
        actions.append(chosen)
    count = len(states)
    edges: list[tuple[tuple[int, int], ...]] = [
        tuple((index[target], weight) for target, weight in a.outcomes if weight > 0) if a is not None else () for a in actions
    ]

    kinds: dict[tuple, int] = {}
    block = [0] * count
    for i in range(count):
        kind = ("goal",) if goal[i] else ("stuck",) if actions[i] is None else ("act", actions[i].cost)
        block[i] = kinds.setdefault(kind, len(kinds))
    blocks = len(kinds)
    while True:
        signatures: dict[tuple, int] = {}
        refined = [0] * count
        for i in range(count):
            merged: dict[int, int] = {}
            for j, weight in edges[i]:
                merged[block[j]] = merged.get(block[j], 0) + weight
            divisor = 0
            for weight in merged.values():
                divisor = gcd(divisor, weight)
            shape = tuple(sorted((b, weight // divisor) for b, weight in merged.items())) if divisor else ()
            refined[i] = signatures.setdefault((block[i], shape), len(signatures))
        block = refined
        if len(signatures) == blocks:
            break
        blocks = len(signatures)
    if blocks == count:
        return unchanged

    stand: dict[int, int] = {}  # block -> the first state (in discovery order, so the start for its own block) that stands for it
    for i in range(count):
        stand.setdefault(block[i], i)
    lumped: dict[S, Action[S]] = {}
    for b, i in stand.items():
        chosen = actions[i]
        if chosen is None:
            continue
        merged: dict[int, int] = {}
        for j, weight in edges[i]:
            merged[stand[block[j]]] = merged.get(stand[block[j]], 0) + weight
        lumped[states[i]] = Action(chosen.label, chosen.cost, tuple((states[j], weight) for j, weight in merged.items()))
    goals = frozenset(states[i] for b, i in stand.items() if goal[i])
    return Lumped(lumped, start, goals.__contains__)
