"""The steps of a policy: the states it can reach, grouped as the route view shows them.

A step stands for a set of compressed states only when the policy takes the same action in all of
them and they have the same chances into the same steps: look-alike states that need different
actions, or that lead on differently, branch. The steps are the coarsest such grouping (a
bisimulation), found by partition refinement: start from the blocks "same action label and cost" (or
"no action, same reason"), then split a block until its states agree on the exact chance (a
`Fraction` of integer weights, summed per target) into every block, a goal counting as one target.

Because the grouping is a bisimulation, every state of a step has the same chance into each target,
so the steps form a small Markov chain of their own. Its fundamental matrix N = (I - Q)^-1 over the
steps that have an action and can reach a goal gives, from the start, the expected uses of a step's
action (`N[start][step]`), the chance a run ever enters it (`N[start][step] / N[step][step]`) and,
from every step, the expected cost still to pay (`N` times the costs per use). A step with no action is
entered with the chance of stepping into it from the others.

An edge to another step is a `forward` edge when it moves toward the goal and a `miss` when it does
not: when the item it lands in is no dearer to finish than the use is expected to leave it (the
expected cost still to pay at the step, less the cost of the use). A step number (the order of
discovery) says nothing about that. An edge to a step with no action is a miss (the run stops there),
and so is every edge of a restart (`is_restart`), which goes back to the start.

The inverse is `numpy.linalg.inv`, O(n^3) in the number of steps (not of states) and fast in C.
Above `MAX_STEPS` steps the chain is not solved: `Flow.measured` is False, `uses` and `reached` are
None (the first step is reached for sure), and an edge is `forward` when the target is nearer to a
goal, counted in edges, than the step is.

A step from which no run can ever reach a goal (it loops forever, or every way out ends in a step with
no action) has `uses = inf`; its `reached` is 1.0 for the first step and None for the others (the
chance of entering it is not computed). Pure, no I/O, deterministic.
"""

import math
from collections import deque
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

import numpy as np

from crafting_system.solver import Action

from ._reach import policy_states

MAX_STEPS = 1500  # above this many steps the chain of steps is not solved (see the module docstring)
_GOAL = -1  # the target "a goal state" while blocks are numbered from 0


@dataclass(frozen=True)
class Edge[S]:
    """Where the outcomes of a step's action lead.

    `kind`: "forward" to a step that is cheaper to finish from, "miss" to one that is not (or that has
    no action), "again" to the same step, "goal" the target reached (`to` is then None). `chance` is
    the chance per use of the action, the same in all states of the step; `states` are the states the
    outcomes land in (goal states for "goal").
    """

    kind: Literal["forward", "miss", "again", "goal"]
    to: int | None
    chance: float
    states: tuple[S, ...]


@dataclass(frozen=True)
class Step[S]:
    """One step of the route.

    `states`: the compressed states it stands for, in breadth-first order. `action`: the one action
    the policy takes in all of them, None when there is none here (a dead end of a policy, a gap of a
    given route) and then `reason` says why (from the `reasons` of `build_flow`). `edges`: one per
    distinct target (step or goal), the goal first, then by step number; empty without an action.
    `uses`: the expected number of uses of the action in one run from the start (None without an
    action, or when the flow is not `measured`). `reached`: the chance a run ever enters the step.
    """

    number: int
    states: tuple[S, ...]
    action: Action[S] | None
    reason: str | None
    edges: tuple[Edge[S], ...]
    uses: float | None
    reached: float | None


@dataclass(frozen=True)
class Flow[S]:
    """The steps (numbered from 1, the start's step first) and the step of every reachable non-goal state.

    `measured`: whether `uses` and `reached` were computed (False above `MAX_STEPS` steps).
    """

    steps: tuple[Step[S], ...]
    step_of: Mapping[S, int]
    measured: bool = True


def build_flow[S: Hashable](
    start: S,
    policy: Mapping[S, Action[S]],
    is_goal: Callable[[S], bool],
    reasons: Mapping[S, str] | None = None,
    is_restart: Callable[[Action[S]], bool] | None = None,
) -> Flow[S]:
    """The steps of `policy` from `start`; `reasons` says why a reachable non-goal state has no entry in `policy`.

    A start that is a goal gives an empty flow. Steps are numbered in the order their first state is
    met breadth-first from `start`. `is_restart` says which actions go back to the start: all their
    edges to other steps are misses.
    """
    if is_goal(start):
        return Flow((), {})
    reasons = reasons or {}
    states = [s for s in policy_states(start, policy, is_goal) if not is_goal(s)]

    outs: dict[S, list[tuple[S, Fraction]]] = {}  # per state: successor -> exact chance, merged, in outcome order
    for state in states:
        if state in policy:
            chances: dict[S, Fraction] = {}
            total = sum(weight for _, weight in policy[state].outcomes)
            for successor, weight in policy[state].outcomes:
                if weight > 0:
                    chances[successor] = chances.get(successor, Fraction(0)) + Fraction(weight, total)
            outs[state] = list(chances.items())
        else:
            outs[state] = []

    block = _refine(states, policy, reasons, outs, is_goal)
    count = max(block.values()) + 1

    members: list[list[S]] = [[] for _ in range(count)]
    for state in states:
        members[block[state]].append(state)

    def target(successor: S) -> int:
        return _GOAL if is_goal(successor) else block[successor]

    edge_chance: list[dict[int, Fraction]] = []  # per block, from its first state
    edge_states: list[dict[int, list[S]]] = []
    for index in range(count):
        chances = {}
        landing: dict[int, list[S]] = {}
        for k, state in enumerate(members[index]):
            for successor, chance in outs[state]:
                where = target(successor)
                if k == 0:
                    chances[where] = chances.get(where, Fraction(0)) + chance
                if successor not in landing.setdefault(where, []):
                    landing[where].append(successor)
        edge_chance.append(chances)
        edge_states.append(landing)

    has_action = [members[i][0] in policy for i in range(count)]
    costs = [policy[members[i][0]].cost if has_action[i] else 0.0 for i in range(count)]
    uses, reached, rank, limit = _visits(count, has_action, costs, edge_chance)
    restarting = [has_action[i] and is_restart is not None and is_restart(policy[members[i][0]]) for i in range(count)]

    steps = []
    for index in range(count):
        first = members[index][0]
        edges = []
        for where in sorted(edge_chance[index], key=lambda t: (t != _GOAL, t)):
            if where == _GOAL:
                edges.append(Edge("goal", None, float(edge_chance[index][where]), tuple(edge_states[index][where])))
                continue
            if where == index:
                kind = "again"
            elif not restarting[index] and has_action[where] and rank[where] <= limit[index]:
                kind = "forward"
            else:
                kind = "miss"
            edges.append(Edge(kind, where + 1, float(edge_chance[index][where]), tuple(edge_states[index][where])))
        steps.append(
            Step(
                number=index + 1,
                states=tuple(members[index]),
                action=policy.get(first),
                reason=None if first in policy else reasons.get(first),
                edges=tuple(edges),
                uses=uses[index],
                reached=reached[index],
            )
        )
    return Flow(tuple(steps), {state: block[state] + 1 for state in states}, count <= MAX_STEPS)


def _refine[S: Hashable](
    states: list[S],
    policy: Mapping[S, Action[S]],
    reasons: Mapping[S, str],
    outs: Mapping[S, list[tuple[S, Fraction]]],
    is_goal: Callable[[S], bool],
) -> dict[S, int]:
    """State -> block number (from 0, by first appearance in `states`): the coarsest stable partition."""

    def number(keys: list[Hashable]) -> dict[S, int]:
        ids: dict[Hashable, int] = {}
        return {state: ids.setdefault(key, len(ids)) for state, key in zip(states, keys)}

    block = number(
        [
            ("action", policy[s].label, policy[s].cost) if s in policy else ("none", reasons.get(s))
            for s in states
        ]
    )
    count = len(set(block.values()))
    while True:
        keys: list[Hashable] = []
        for state in states:
            into: dict[int, Fraction] = {}
            for successor, chance in outs[state]:
                where = _GOAL if is_goal(successor) else block[successor]
                into[where] = into.get(where, Fraction(0)) + chance
            keys.append((block[state], tuple(sorted(into.items()))))
        refined = number(keys)
        refined_count = len(set(refined.values()))
        if refined_count == count:  # a refinement that splits nothing is the fixpoint
            return block
        block, count = refined, refined_count


def _visits(
    count: int, has_action: list[bool], costs: list[float], edge_chance: list[dict[int, Fraction]]
) -> tuple[list[float | None], list[float | None], list[float], list[float]]:
    """Expected uses and the chance of ever entering, per step, and what tells `forward` from `miss`.

    The third list ranks the steps: the expected cost still to pay, or, above `MAX_STEPS` steps, the fewest
    edges to a goal; infinite for a step that cannot reach a goal. The fourth is, per step, the highest rank
    a target may have for the edge to be forward: the rank the use is expected to leave (the cost still to pay
    less the cost of the use, or one edge less), minus infinity for a step that cannot finish.
    """
    # Steps that can finish: an edge to a goal, or to a step that can. A step with no action cannot.
    entering: list[list[int]] = [[] for _ in range(count)]  # per step: the steps with an edge into it
    can_finish = [False] * count
    distance = [math.inf] * count  # fewest edges to a goal
    queue: deque[int] = deque()
    for i in range(count):
        if has_action[i] and _GOAL in edge_chance[i]:
            can_finish[i] = True
            distance[i] = 1.0
            queue.append(i)
        for t in edge_chance[i]:
            if t != _GOAL:
                entering[t].append(i)
    while queue:
        t = queue.popleft()
        for i in entering[t]:
            if has_action[i] and not can_finish[i]:
                can_finish[i] = True
                distance[i] = distance[t] + 1.0
                queue.append(i)

    transient = [i for i in range(count) if has_action[i] and can_finish[i]]
    position = {i: k for k, i in enumerate(transient)}
    size = len(transient)
    uses: list[float | None] = [None] * count
    reached: list[float | None] = [None] * count
    for i in range(count):
        if has_action[i] and not can_finish[i]:
            uses[i] = math.inf
    reached[0] = 1.0
    if count > MAX_STEPS:  # the steps that finish are not told apart by uses: only by their distance
        return uses, reached, distance, [d - 1.0 if math.isfinite(d) else -math.inf for d in distance]
    if 0 not in position:  # the first step is a dead end, or a trap: nothing else of the flow is a run's business
        return uses, reached, distance, [d - 1.0 if math.isfinite(d) else -math.inf for d in distance]

    matrix = np.eye(size)
    for i in transient:
        r = position[i]
        for t, chance in edge_chance[i].items():
            c = position.get(t)
            if t != _GOAL and c is not None:
                matrix[r, c] -= float(chance)
    inverse = np.linalg.inv(matrix)
    row = inverse[position[0]]
    to_pay = inverse @ np.array([costs[i] for i in transient])
    rank = [math.inf] * count
    limit = [-math.inf] * count
    for i in transient:
        k = position[i]
        uses[i] = float(row[k])
        reached[i] = min(1.0, max(0.0, float(row[k] / inverse[k, k])))
        rank[i] = float(to_pay[k])
        left = rank[i] - costs[i]
        limit[i] = left + 1e-9 * max(1.0, abs(left))
    for a in range(count):
        if has_action[a] or a == 0:
            continue
        stepped = sum(float(row[position[i]]) * float(edge_chance[i][a]) for i in transient if a in edge_chance[i])
        reached[a] = min(1.0, max(0.0, stepped))
    return uses, reached, rank, limit
