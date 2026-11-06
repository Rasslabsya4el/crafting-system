"""The steps of a policy: one step per player action, with the exact mixture of the chances of its states.

A step is the set of states on which the policy takes the same action, found by its label and nothing else
(OR-18): states with different actions branch, and neither a different chance nor a detail the search does not
track splits one action into several steps. States with no action (a dead end of a policy, a gap of a given
route) are steps too, one per reason. Steps are numbered in the order their first state is met breadth-first.

The chances of a step (OR-20). The states of one step need not have the same chance for an outcome, so the step
shows the mixture of them: for an outcome, the sum over the step's states of (expected visits of the state x
its exact chance, a `Fraction` of integer weights) divided by the expected visits of the step. The weights are the
expected visits from the start under the policy itself: row `start` of N = (I - Q)^-1, where Q holds the chances
among the states that have an action and can reach a goal. They are found by one dense linear solve over those
states (float64, `numpy.linalg.solve`, cost O(n^3) in the number of states, with no limit on n); the chances
they weigh stay exact fractions until the weighted sum. From the same N come the uses of a step (the sum of the
visits of its states, so `sum(uses x cost)` is the mean cost of the policy) and, for a step with an action, the
chance a run ever enters it. A step with no action is entered with the chance of stepping into it from the
visited states. A state from which no run can ever reach a goal (it loops forever, or every way out ends in a
state with no action) has no visits: a step whose states are all of that kind has `uses = inf` and the plain
mean of its states as its chances; in a step that also has states that can finish, only those are counted.

Two things are stated, not hidden (ADR OR-12, OR-13), and both leave the chances and uses exact:

* `Flow.measured` is False when the matrix cannot be solved in floats (a chance per use so small that it is lost in
  the float): the uses and visits are then not known, and the chances of a step with several states are the plain
  mean of them.
* `Flow.entered` is False when the policy has more than `ENTRY_STATES` states that can finish: the chance a run
  enters a step needs one more solve per step, and it is left out (`Step.reached` is None for every step but the
  first, which is reached for sure). Uses, costs and chances do not depend on it.
  TODO(#459): carry both as a `Limit` with its guarantee, once that record exists.

An edge groups the outcomes that lead to the same place: a goal, or the next step. `kind`: "goal", "failure"
(the item lost a wanted mod, the action is a restart, or the item lands in a step that restarts or that has no
action: it is thrown away or the route stops), "again" (the same step, nothing lost), "forward" (any other step).
Nothing is decided by what the item still costs to finish (PRES-6). Whether a use loses a wanted mod is told by
the caller (`failed`), which keeps this module free of the compressed state. Pure, no I/O, deterministic.
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

ENTRY_STATES = 1000  # the chance of entering a step is solved once per step when the policy has at most this many states that can finish
_GOAL = -1  # the target "a goal state" while blocks are numbered from 0


@dataclass(frozen=True)
class Edge[S]:
    """Where some outcomes of a step's action lead.

    `kind`: "goal" the target reached (`to` is then None), "failure" a wanted mod lost, a restart, or a landing
    in a step that restarts or has no action, "again" the same step with nothing lost, "forward" any other step.
    `chance` is the chance per use of the action, mixed over the step's states by their expected visits; `states` are
    the states the outcomes land in (goal states for "goal"); `pairs` are the `(state, landing state)` pairs
    behind the edge, in the step's breadth-first order; `lost` is everything `failed` said some of them loses (the wanted
    mods, sorted), empty when no use of the edge loses any.
    """

    kind: Literal["forward", "failure", "again", "goal"]
    to: int | None
    chance: float
    states: tuple[S, ...]
    pairs: tuple[tuple[S, S], ...] = ()
    lost: tuple = ()


@dataclass(frozen=True)
class Step[S]:
    """One step of the route.

    `states`: the compressed states it stands for, in breadth-first order. `weights`: the expected visits of each
    of them from the start, the weights of the mixture (all 1.0 when the flow is not `measured`, or when none
    of the states can finish). `action`: the action of the step's first state, the label every state shares; None
    when there is no action here and then `reason` says why (from the `reasons` of `build_flow`). `cost`: the
    cost per use, the mean over the states by their weights (the same number for every state of one offer).
    `edges`: one per distinct (target, whether a wanted mod is lost) pair, the goal first, then by step number; empty without an
    action. `uses`: the expected number of uses of the action in one run from the start (None without an
    action, or when the flow is not `measured`). `reached`: the chance a run ever enters the step.
    """

    number: int
    states: tuple[S, ...]
    action: Action[S] | None
    reason: str | None
    edges: tuple[Edge[S], ...]
    uses: float | None
    reached: float | None
    weights: tuple[float, ...] = ()
    cost: float = 0.0


@dataclass(frozen=True)
class Flow[S]:
    """The steps (numbered from 1, the start's step first) and the step of every reachable non-goal state.

    `measured`: whether the expected visits were computed (False when the chain cannot be solved in floats).
    `entered`: whether `Step.reached` was computed (False above `ENTRY_STATES` states, see the module text).
    """

    steps: tuple[Step[S], ...]
    step_of: Mapping[S, int]
    measured: bool = True
    entered: bool = True


def build_flow[S: Hashable](
    start: S,
    policy: Mapping[S, Action[S]],
    is_goal: Callable[[S], bool],
    reasons: Mapping[S, str] | None = None,
    is_restart: Callable[[Action[S]], bool] | None = None,
    failed: Callable[[S, S], tuple] | None = None,
) -> Flow[S]:
    """The steps of `policy` from `start`; `reasons` says why a reachable non-goal state has no entry in `policy`.

    A start that is a goal gives an empty flow. `is_restart` says which actions go back to the start: all their
    edges are failures. `failed(state, landing)` says what a use that takes `state` to `landing` loses of the
    wanted mods: a tuple of sortable items (the leaves of the target it stops meeting), empty for nothing. Outcomes that
    lead to the same step are one edge, except that those which lose a wanted mod are apart from those which do not.
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

    numbers: dict[Hashable, int] = {}
    block = {
        state: numbers.setdefault(
            ("action", policy[state].label) if state in policy else ("none", reasons.get(state)), len(numbers)
        )
        for state in states
    }
    count = len(numbers)
    members: list[list[S]] = [[] for _ in range(count)]
    for state in states:
        members[block[state]].append(state)
    has_action = [members[i][0] in policy for i in range(count)]
    restarting = [has_action[i] and is_restart is not None and is_restart(policy[members[i][0]]) for i in range(count)]

    visits, position, solved, inverse = _visits(start, states, policy, outs, is_goal)
    reached = _entered(start, members, outs, position, visits, inverse)
    entered = inverse is not None or start not in position

    steps = []
    for index in range(count):
        group = members[index]
        weights = [visits.get(state, 0.0) for state in group] if solved else [0.0] * len(group)
        mixing = weights if math.fsum(weights) > 0.0 else [1.0] * len(group)  # nobody can finish here, or unmeasured: the plain mean
        total = math.fsum(mixing)
        shares: dict[tuple[int, bool], list[float]] = {}
        pairs: dict[tuple[int, bool], list[tuple[S, S]]] = {}
        gone: dict[tuple[int, bool], set] = {}
        for state, weight in zip(group, mixing, strict=True):
            for successor, chance in outs[state]:
                where = _GOAL if is_goal(successor) else block[successor]
                lost = failed(state, successor) if where != _GOAL and not restarting[index] and failed is not None else ()  # a restart is one failure whatever it throws away
                key = (where, bool(lost))
                shares.setdefault(key, []).append(weight * float(chance))
                pairs.setdefault(key, []).append((state, successor))
                gone.setdefault(key, set()).update(lost)
        edges = []
        for where, lost in sorted(shares, key=lambda key: (key[0] != _GOAL, key[0], key[1])):
            if where == _GOAL:
                kind = "goal"
            elif restarting[index] or lost or not has_action[where] or restarting[where]:
                kind = "failure"
            elif where == index:
                kind = "again"
            else:
                kind = "forward"
            landing = tuple(dict.fromkeys(successor for _, successor in pairs[(where, lost)]))
            edges.append(
                Edge(
                    kind,
                    None if where == _GOAL else where + 1,
                    math.fsum(shares[(where, lost)]) / total,
                    landing,
                    tuple(dict.fromkeys(pairs[(where, lost)])),
                    tuple(sorted(gone[(where, lost)])),
                )
            )
        if has_action[index]:
            finishing = [visits[state] for state in group if state in visits]
            uses = math.inf if not any(state in position for state in group) else (math.fsum(finishing) if solved else None)
            cost = math.fsum(w * policy[state].cost for state, w in zip(group, mixing, strict=True)) / total
        else:
            uses, cost = None, 0.0
        steps.append(
            Step(
                number=index + 1,
                states=tuple(group),
                action=policy.get(group[0]),
                reason=None if group[0] in policy else reasons.get(group[0]),
                edges=tuple(edges) if has_action[index] else (),
                uses=uses,
                reached=reached[index],
                weights=tuple(mixing),
                cost=cost,
            )
        )
    return Flow(tuple(steps), {state: block[state] + 1 for state in states}, solved, entered)


def _can_finish[S: Hashable](
    states: list[S], policy: Mapping[S, Action[S]], outs: Mapping[S, list[tuple[S, Fraction]]], is_goal: Callable[[S], bool]
) -> set[S]:
    """The states with an action from which some run reaches a goal through states that have an action."""
    entering: dict[S, list[S]] = {}
    finishing: set[S] = set()
    queue: deque[S] = deque()
    for state in states:
        if state not in policy:
            continue
        for successor, _ in outs[state]:
            if is_goal(successor):
                if state not in finishing:
                    finishing.add(state)
                    queue.append(state)
            else:
                entering.setdefault(successor, []).append(state)
    while queue:
        target = queue.popleft()
        for state in entering.get(target, ()):
            if state not in finishing:
                finishing.add(state)
                queue.append(state)
    return finishing


def _visits[S: Hashable](
    start: S,
    states: list[S],
    policy: Mapping[S, Action[S]],
    outs: Mapping[S, list[tuple[S, Fraction]]],
    is_goal: Callable[[S], bool],
) -> tuple[dict[S, float], dict[S, int], bool, np.ndarray | None]:
    """The expected visits from `start` of each state that can finish, their numbering, whether they were solved, and N.

    The visits are row `start` of N = (I - Q)^-1 over the states with an action that can reach a goal. N itself
    (the whole inverse) is returned when there are at most `ENTRY_STATES` such states, else the row is found by one
    solve of (I - Q)^T v = e_start. The numbering is empty when the start is not one of them (it has no action, or
    cannot finish): then nothing else is a run's business.
    """
    finishing = _can_finish(states, policy, outs, is_goal)
    transient = [s for s in states if s in finishing]
    position = {s: k for k, s in enumerate(transient)}
    if start not in position:
        return {}, {}, True, None
    matrix = np.eye(len(transient))
    for state in transient:
        for successor, chance in outs[state]:
            if successor in position:
                matrix[position[state], position[successor]] -= float(chance)
    try:
        with np.errstate(all="ignore"):
            if len(transient) <= ENTRY_STATES:
                inverse = np.linalg.inv(matrix)
                row = inverse[position[start]]
            else:
                inverse = None
                base = np.zeros(len(transient))
                base[position[start]] = 1.0
                row = np.linalg.solve(matrix.T, base)
    except np.linalg.LinAlgError:  # a chance per use so small that 1 - q is 1 in floats: nothing to say about visits
        return {}, position, False, None
    if not np.all(np.isfinite(row)) or np.any(row < -1e-9):
        return {}, position, False, None
    return {state: max(0.0, float(row[position[state]])) for state in transient}, position, True, inverse


def _entered[S: Hashable](
    start: S,
    members: list[list[S]],
    outs: Mapping[S, list[tuple[S, Fraction]]],
    position: Mapping[S, int],
    visits: Mapping[S, float],
    inverse: np.ndarray | None,
) -> list[float | None]:
    """The chance a run ever enters each step: 1 for the first, None for the others when `inverse` (N) is not there.

    For a step A of states that can finish, the first state of A a run meets is a with chance H(a), and the visits
    of N split by it: N[start, b] = sum over a in A of H(a) N[a, b], so H = N[start, A] N[A, A]^-1 and the chance is
    its sum. A step of states that cannot finish (a dead end, a gap) is entered from the states that can: its
    chance is the expected number of such steps into it, since a run never comes back from it. A step that has
    both kinds of state is left unmeasured (None).
    """
    count = len(members)
    result: list[float | None] = [None] * count
    result[0] = 1.0
    if inverse is None or start not in position:
        return result
    row = inverse[position[start]]
    for index in range(1, count):
        group = members[index]
        inside = [position[state] for state in group if state in position]
        if start in group:
            result[index] = 1.0
        elif inside and len(inside) == len(group):
            try:
                with np.errstate(all="ignore"):
                    first = np.linalg.solve(inverse[np.ix_(inside, inside)].T, row[inside])
            except np.linalg.LinAlgError:
                continue
            value = float(first.sum())
            result[index] = min(1.0, max(0.0, value)) if math.isfinite(value) else None
        elif not inside:
            aim = set(group)
            value = math.fsum(
                visits[state] * float(chance) for state in visits for successor, chance in outs[state] if successor in aim
            )
            result[index] = min(1.0, max(0.0, value))
    return result
