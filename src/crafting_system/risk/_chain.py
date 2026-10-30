"""The absorbing chain a fixed policy induces, and the facts about it the metrics need.

States are discovered breadth first from the start through the policy. A goal absorbs and is never
expanded, even when the policy lists it. A reachable non-goal state with no policy entry is
stuck: whatever reaches it fails. `can_finish` marks the states from which the policy graph
reaches a goal (reverse reachability); mass that moves to any other state, a stuck state or a
trapped recurrent class such as a state whose only outcome is itself, is lost. When every
reachable state can finish the policy is proper (the goal is reached with probability exactly 1,
a combinatorial fact, not a float one) and the total cost is finite almost surely.
"""

import math
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from math import gcd

from ..solver import Action

UNIT_TOLERANCE = 1e-12  # a cost within this relative distance of a multiple of the unit counts as one
UNIT_DENOMINATOR = 10**6


@dataclass(frozen=True, slots=True)
class Chain[S]:
    """Reachable states by index; index 0 is the start.

    `action[i]` is the policy action of an expanded state and `None` for a goal or a stuck state.
    `succ[i]` lists `(index, probability)` per distinct successor of an expanded state (zero
    weights dropped, repeats merged, probability = weight / total weight).
    """

    states: tuple[S, ...]
    goal: tuple[bool, ...]
    action: tuple[Action[S] | None, ...]
    succ: tuple[tuple[tuple[int, float], ...], ...]
    can_finish: tuple[bool, ...]

    @property
    def proper(self) -> bool:
        return all(self.can_finish)

    def finishing_states(self) -> list[int]:
        """Indices of the expanded states that can still reach a goal: the ones the budget DP moves mass through."""
        return [i for i, a in enumerate(self.action) if a is not None and self.can_finish[i]]


def build_chain[S](
    policy: Mapping[S, Action[S]], start: S, is_goal: Callable[[S], bool]
) -> Chain[S]:
    index: dict[S, int] = {start: 0}
    states: list[S] = [start]
    goal: list[bool] = [False]
    action: list[Action[S] | None] = [None]
    succ: list[tuple[tuple[int, float], ...]] = [()]
    queue = deque([0])
    while queue:
        i = queue.popleft()
        if is_goal(states[i]):
            goal[i] = True
            continue
        chosen = policy.get(states[i])
        if chosen is None:
            continue
        merged: dict[int, int] = {}
        total = 0
        for target, weight in chosen.outcomes:
            if weight == 0:
                continue
            total += weight
            if target not in index:
                index[target] = len(states)
                states.append(target)
                goal.append(False)
                action.append(None)
                succ.append(())
                queue.append(index[target])
            merged[index[target]] = merged.get(index[target], 0) + weight
        action[i] = chosen
        succ[i] = tuple((j, weight / total) for j, weight in merged.items())

    reverse: list[list[int]] = [[] for _ in states]
    for i, edges in enumerate(succ):
        for j, _ in edges:
            reverse[j].append(i)
    can_finish = list(goal)
    queue = deque(i for i, flag in enumerate(goal) if flag)
    while queue:
        j = queue.popleft()
        for i in reverse[j]:
            if not can_finish[i]:
                can_finish[i] = True
                queue.append(i)
    return Chain(tuple(states), tuple(goal), tuple(action), tuple(succ), tuple(can_finish))


def exact_unit(costs: Iterable[float]) -> float | None:
    """A step u such that every cost is a whole multiple of u (within 1e-12 relative), or `None`.

    Each cost is read as the fraction with denominator at most 10**6 that is closest to it; if
    that fraction is not within 1e-12 relative of the cost there is no unit. The unit is the
    greatest common divisor of the fractions.
    """
    fractions = []
    for cost in costs:
        fraction = Fraction(cost).limit_denominator(UNIT_DENOMINATOR)
        if abs(cost - fraction) > UNIT_TOLERANCE * cost:
            return None
        fractions.append(fraction)
    if not fractions:
        return None
    common = math.lcm(*(f.denominator for f in fractions))
    divisor = gcd(*(int(f * common) for f in fractions))
    return float(Fraction(divisor, common))
