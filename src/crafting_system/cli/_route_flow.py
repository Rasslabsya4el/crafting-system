"""The steps of a policy: the states it can reach, grouped as the route view shows them.

A step stands for a set of compressed states only when the policy takes the same action in all of
them and they have the same chances into the same steps: look-alike states that need different
actions, or that lead on differently, branch. The steps are the coarsest such grouping (a
bisimulation), found by partition refinement: start from the blocks "same action label and cost" (or
"no action, same reason"), then split a block until its states agree on the exact chance (a
`Fraction` of integer weights, summed per target) into every block, a goal counting as one target.

Because the grouping is a bisimulation, every state of a step has the same chance into each target,
so the steps form a small Markov chain of their own. Its fundamental matrix N = (I - Q)^-1 over the
steps that have an action gives, from the start, the expected uses of a step's action
(`N[start][step]`) and the chance a run ever enters it (`N[start][step] / N[step][step]`); a step
with no action is entered with the chance of stepping into it from the others. The inverse is the
dense `_reach._invert`, O(n^3) in the number of steps (not of states), with no cap: a policy has as
many steps as distinct actions-in-context it uses, tens at most.

A step from which no run can ever finish (it cannot reach a goal or a step with no action) has
`uses = inf`; its `reached` is 1.0 for the first step and None for the others (the chance of entering
it is not computed). Pure, no I/O, deterministic.
"""

import math
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from crafting_system.solver import Action

from ._reach import _invert, policy_states

_GOAL = -1  # the target "a goal state" while blocks are numbered from 0


@dataclass(frozen=True)
class Edge[S]:
    """Where the outcomes of a step's action lead.

    `kind`: "next" to a later step, "back" to an earlier one, "again" to the same step, "goal" the
    target reached (`to` is then None). `chance` is the chance per use of the action, the same in all
    states of the step; `states` are the states the outcomes land in (goal states for "goal").
    """

    kind: Literal["next", "back", "again", "goal"]
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
    action). `reached`: the chance a run ever enters the step.
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
    """The steps (numbered from 1, the start's step first) and the step of every reachable non-goal state."""

    steps: tuple[Step[S], ...]
    step_of: Mapping[S, int]


def build_flow[S: Hashable](
    start: S,
    policy: Mapping[S, Action[S]],
    is_goal: Callable[[S], bool],
    reasons: Mapping[S, str] | None = None,
) -> Flow[S]:
    """The steps of `policy` from `start`; `reasons` says why a reachable non-goal state has no entry in `policy`.

    A start that is a goal gives an empty flow. Steps are numbered in the order their first state is
    met breadth-first from `start`.
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
    uses, reached = _visits(count, has_action, edge_chance)

    steps = []
    for index in range(count):
        first = members[index][0]
        edges = []
        for where in sorted(edge_chance[index], key=lambda t: (t != _GOAL, t)):
            if where == _GOAL:
                edges.append(Edge("goal", None, float(edge_chance[index][where]), tuple(edge_states[index][where])))
                continue
            kind = "again" if where == index else "next" if where > index else "back"
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
    return Flow(tuple(steps), {state: block[state] + 1 for state in states})


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
    count: int, has_action: list[bool], edge_chance: list[dict[int, Fraction]]
) -> tuple[list[float | None], list[float | None]]:
    """Expected uses and the chance of ever entering, per step, on the chain of steps."""
    # Steps that can finish: an edge to a goal or to a step with no action, or to a step that can.
    can_finish = [
        has_action[i] and (_GOAL in edge_chance[i] or any(not has_action[t] for t in edge_chance[i] if t != _GOAL))
        for i in range(count)
    ]
    changed = True
    while changed:
        changed = False
        for i in range(count):
            if has_action[i] and not can_finish[i] and any(can_finish[t] for t in edge_chance[i] if t != _GOAL):
                can_finish[i] = True
                changed = True

    transient = [i for i in range(count) if has_action[i] and can_finish[i]]
    position = {i: k for k, i in enumerate(transient)}
    size = len(transient)
    uses: list[float | None] = [None] * count
    reached: list[float | None] = [None] * count
    for i in range(count):
        if has_action[i] and not can_finish[i]:
            uses[i] = math.inf
    reached[0] = 1.0
    if 0 not in position:  # the first step is a dead end, or a trap: nothing else of the flow is a run's business
        return uses, reached

    matrix = [[0.0] * size + [1.0 if r == c else 0.0 for c in range(size)] for r in range(size)]
    for i in transient:
        r = position[i]
        matrix[r][r] += 1.0
        for t, chance in edge_chance[i].items():
            c = position.get(t)
            if t != _GOAL and c is not None:
                matrix[r][c] -= float(chance)
    inverse = _invert(matrix, size)
    row = inverse[position[0]]
    for i in transient:
        k = position[i]
        uses[i] = row[k]
        reached[i] = min(1.0, max(0.0, row[k] / inverse[k][k]))
    for a in range(count):
        if has_action[a] or a == 0:
            continue
        stepped = sum(row[position[i]] * float(edge_chance[i][a]) for i in transient if a in edge_chance[i])
        reached[a] = min(1.0, max(0.0, stepped))
    return uses, reached
