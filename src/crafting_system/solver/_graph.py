"""Reachable-state generation, exact self-loop elimination and the proper-policy analysis."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from ._model import Action, Model


@dataclass(slots=True)
class Graph[S]:
    """The reachable states and every action with its self-loop compiled out.

    States are numbered in discovery order. Actions are numbered globally; `owner[k]` is the state
    the action belongs to. An action that can never leave its state is dropped (infinite cost).
    """

    states: list[S] = field(default_factory=list)
    goal: list[bool] = field(default_factory=list)
    owner: list[int] = field(default_factory=list)
    original: list[Action[S]] = field(default_factory=list)
    cost: list[float] = field(default_factory=list)  # effective cost: cost * W / L
    succ: list[list[int]] = field(default_factory=list)  # non-self successors, merged
    prob: list[list[float]] = field(default_factory=list)  # w_j / L
    state_actions: list[list[int]] = field(default_factory=list)


def build_graph[S](model: Model[S], starts: Iterable[S]) -> Graph[S]:
    """Explore from `starts` once, calling `model.actions` once per non-goal state.

    Integers first: W is the total weight, L the weight that leaves the state. The effective cost
    is `cost * W / L` and the probabilities are `w_j / L`; `1 - p_self` is never computed in floats.
    """
    graph: Graph[S] = Graph()
    index: dict[S, int] = {}
    states = graph.states

    def intern(state: S) -> int:
        found = index.get(state)
        if found is None:
            found = index[state] = len(states)
            states.append(state)
        return found

    for start in starts:
        intern(start)
    i = 0
    while i < len(states):  # the list grows while it is walked: a breadth-first queue
        state = states[i]
        ids: list[int] = []
        graph.state_actions.append(ids)
        if model.is_goal(state):
            graph.goal.append(True)
            i += 1
            continue
        graph.goal.append(False)
        for action in tuple(model.actions(state)):
            if action.extra_inputs:
                raise NotImplementedError(
                    "multi-input actions need the branching solver, B3 (ADR-0011)"
                )
            merged: dict[int, int] = {}
            for successor, weight in action.outcomes:
                if weight:
                    j = intern(successor)
                    merged[j] = merged.get(j, 0) + weight
            total = sum(merged.values())
            leave = total - merged.pop(i, 0)
            if leave == 0:
                continue  # repeats forever at a positive cost: infinite, never useful
            ids.append(len(graph.owner))
            graph.owner.append(i)
            graph.original.append(action)
            graph.cost.append(action.cost * total / leave)
            graph.succ.append(list(merged))
            graph.prob.append([weight / leave for weight in merged.values()])
        i += 1
    return graph


def proper_states[S](graph: Graph[S]) -> tuple[list[bool], list[bool]]:
    """The states with a proper policy, and the actions that never risk a dead state.

    The set is the greatest fixpoint Y of: goals, plus states with an action whose successors all
    lie in Y and at least one is already reached (least fixpoint inside). Backward reachability
    alone would keep an action that can fall into a dead state, which costs infinity. Returns
    `(alive, in_y)`: `alive[k]` is True for retained actions, `in_y[s]` for finite states.
    """
    n_states = len(graph.states)
    pred: list[list[int]] = [[] for _ in range(n_states)]
    for k, successors in enumerate(graph.succ):
        for j in successors:
            pred[j].append(k)
    alive = [True] * len(graph.owner)
    in_y = [True] * n_states
    while True:
        reached = list(graph.goal)
        stack = [s for s in range(n_states) if graph.goal[s]]
        while stack:
            j = stack.pop()
            for k in pred[j]:
                if alive[k]:
                    owner = graph.owner[k]
                    if not reached[owner]:
                        reached[owner] = True
                        stack.append(owner)
        removed = [s for s in range(n_states) if in_y[s] and not reached[s]]
        if not removed:
            return alive, in_y
        for s in removed:
            in_y[s] = False
            for k in graph.state_actions[s]:
                alive[k] = False
            for k in pred[s]:
                alive[k] = False
