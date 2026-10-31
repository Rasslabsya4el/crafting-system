"""Reachable-state generation, exact self-loop elimination and the proper-policy analysis."""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from ._model import Action, Model
from ._scc import strongly_connected_components


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
    cost: list[float] = field(default_factory=list)  # effective cost: cost * (W / L)
    succ: list[list[int]] = field(default_factory=list)  # non-self successors, merged
    prob: list[list[float]] = field(default_factory=list)  # w_j / L
    state_actions: list[list[int]] = field(default_factory=list)


def build_graph[S](model: Model[S], starts: Iterable[S]) -> Graph[S]:
    """Explore from `starts` once, calling `model.actions` once per non-goal state.

    Integers first: W is the total weight, L the weight that leaves the state. The effective cost
    is `cost * (W / L)` and the probabilities are `w_j / L`; `1 - p_self` is never computed in floats.
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
            try:
                factor = total / leave  # int / int is correctly rounded, however large
            except OverflowError:
                factor = math.inf
            effective = action.cost * factor
            if not math.isfinite(effective):
                raise ValueError(
                    f"effective cost overflows float64 for action {action.label!r} in state {state!r}"
                )
            ids.append(len(graph.owner))
            graph.owner.append(i)
            graph.original.append(action)
            graph.cost.append(effective)
            graph.succ.append(list(merged))
            graph.prob.append([weight / leave for weight in merged.values()])
        i += 1
    return graph


def proper_states[S](graph: Graph[S]) -> tuple[list[bool], list[bool]]:
    """The states with a proper policy, and the actions that never risk a dead state.

    The set is the greatest fixpoint Y of: goals, plus states with an action whose successors all
    lie in Y and at least one is already reached (least fixpoint inside). Backward reachability
    alone would keep an action that can fall into a dead state, which costs infinity. Returns
    `(alive, in_y)`: `alive[k]` is True for retained actions, `in_y[s]` for finite states, and
    `alive[k]` holds exactly when the owner of `k` and every successor of `k` are in Y.

    Whether a state is in Y depends only on the states it can reach, so the strongly connected
    components of the state graph are settled sink-first and a component only meets final answers
    downstream. A state alone is decided on the spot; a cycle is settled by `_settle_cycle`.
    """
    n_states = len(graph.states)
    adjacency: list[list[int]] = [[] for _ in range(n_states)]
    pred: list[list[int]] = [[] for _ in range(n_states)]
    for k, successors in enumerate(graph.succ):
        adjacency[graph.owner[k]].extend(successors)
        for j in successors:
            pred[j].append(k)
    alive = [False] * len(graph.owner)
    in_y = [False] * n_states
    cycle = _Cycle(graph, pred, alive, in_y)
    for cid, component in enumerate(strongly_connected_components(adjacency, range(n_states))):
        if len(component) > 1:  # self-loops are compiled out, so one state alone has no cycle
            cycle.settle(component, cid)
            continue
        state = component[0]
        if graph.goal[state]:
            in_y[state] = True
            continue
        for k in graph.state_actions[state]:
            if all(in_y[j] for j in graph.succ[k]):
                alive[k] = True
                in_y[state] = True
    return alive, in_y


_CLIMB = 24  # steps up the forest `_Cycle._rehang` spends per candidate witness


class _Cycle[S]:
    """Settles one cyclic component: safety peel and reachability, repaired instead of redone.

    Every member starts in Y. An action is alive while its owner and all its successors are in Y;
    a member with no alive action leaves Y, which kills the actions into it (the peel, a worklist
    touching each edge once). The remaining members must also reach the outside of the component
    (final members of Y) through alive actions, or they leave Y too. Each reached member keeps the
    alive action `witness` and the successor `parent` it leans on, a forest rooted outside the
    component. When the peel kills a witness, that member and then its children are first tried
    for another witness found by a short climb (`_rehang`); only what cannot be rehung one by one
    is searched again, and the rest keeps its proof. The first reachability pass is one sweep.

    The cost is linear when the removals come from the peel or from small subtrees. A cut that
    lands high in a big proof tree, mended again and again by alternatives that sit deeper than
    `_CLIMB` steps, still costs the size of the tree each time, so it stays quadratic there
    (decremental reachability has no known linear algorithm).
    """

    def __init__(
        self, graph: Graph[S], pred: list[list[int]], alive: list[bool], in_y: list[bool]
    ) -> None:
        count = len(graph.states)
        self.graph = graph
        self.pred = pred
        self.alive = alive
        self.in_y = in_y
        self.live = [0] * count  # alive actions of each member
        self.comp = [-1] * count  # component id of members of cycles
        self.witness = [-1] * count  # alive action it reaches through; -1 = not reached
        self.parent = [-1] * count  # successor that action leans on; -1 = outside the component
        self.stamp = [0] * count
        self.first = [0] * count  # actions of a member before this index are dead for good
        self.round = 0

    def settle(self, members: list[int], cid: int) -> None:
        graph, alive, in_y, live, comp = self.graph, self.alive, self.in_y, self.live, self.comp
        for s in members:
            comp[s] = cid
            in_y[s] = True
        for s in members:
            for k in graph.state_actions[s]:
                if all(in_y[j] for j in graph.succ[k]):  # members count as in Y, outside is final
                    alive[k] = True
                    live[s] += 1
        queue = [s for s in members if live[s] == 0]
        for s in queue:
            in_y[s] = False
        self._peel(queue)  # nothing is reached yet, so no witness can be cut
        self._reach_all(members, cid)
        queue = [s for s in members if in_y[s] and self.witness[s] < 0]
        for s in queue:
            in_y[s] = False
        while queue:
            cut = self._peel(queue)
            queue = self._repair(cut, cid)

    def _peel(self, queue: list[int]) -> list[int]:
        """Remove `queue` and whatever then has no alive action; return reached members cut loose."""
        graph, alive, in_y, live, witness, pred = (
            self.graph, self.alive, self.in_y, self.live, self.witness, self.pred,
        )
        owner = graph.owner
        cut: list[int] = []
        while queue:
            s = queue.pop()
            for k in graph.state_actions[s]:
                alive[k] = False
            for k in pred[s]:
                if alive[k]:
                    alive[k] = False
                    o = owner[k]
                    live[o] -= 1
                    if not in_y[o]:
                        continue
                    if live[o] == 0:
                        in_y[o] = False
                        queue.append(o)
                    elif witness[o] == k:
                        cut.append(o)
        return cut

    def _reach_all(self, members: list[int], cid: int) -> None:
        """Mark every member that reaches the outside of the cycle through alive actions."""
        graph, alive, comp, witness, parent = (
            self.graph, self.alive, self.comp, self.witness, self.parent,
        )
        frontier = []
        for s in members:
            if self.in_y[s]:
                for k in graph.state_actions[s]:
                    if alive[k] and any(comp[j] != cid for j in graph.succ[k]):
                        witness[s], parent[s] = k, -1
                        frontier.append(s)
                        break
        self._spread(frontier)

    def _spread(self, frontier: list[int]) -> None:
        """Reverse reachability from `frontier` over alive actions, to members not yet reached."""
        owner, alive, witness, parent, pred = (
            self.graph.owner, self.alive, self.witness, self.parent, self.pred,
        )
        while frontier:
            j = frontier.pop()
            for k in pred[j]:
                if alive[k]:
                    o = owner[k]
                    if witness[o] < 0:
                        witness[o], parent[o] = k, j
                        frontier.append(o)

    def _rehang(self, o: int, cid: int, token: int) -> bool:
        """Give the cut member `o` a new witness without a search, when one is cheap to prove.

        A way out of the component always works. A successor inside works when climbing from it
        up the forest, a few steps at most, reaches a root without meeting a member stamped
        `token` (those are cut, or hang below a cut member, and have no proof yet; `o` itself is
        stamped, so a successor below `o` is refused). Running out of steps refuses too.
        """
        graph, alive, comp, parent, stamp = (
            self.graph, self.alive, self.comp, self.parent, self.stamp,
        )
        actions = graph.state_actions[o]
        first = self.first[o]
        while first < len(actions) and not alive[actions[first]]:
            first += 1  # an action never comes back to life: a state with many does not rescan
        self.first[o] = first
        for at in range(first, len(actions)):
            k = actions[at]
            if alive[k]:
                for j in graph.succ[k]:
                    if comp[j] != cid:
                        self.witness[o], parent[o] = k, -1
                        return True
                    steps, up = 0, j
                    while up != -1 and stamp[up] != token and steps < _CLIMB:
                        up = parent[up]
                        steps += 1
                    if up == -1:
                        self.witness[o], parent[o] = k, j
                        return True
        return False

    def _repair(self, cut: list[int], cid: int) -> list[int]:
        """Mend the proofs of the members whose witness died; return those left unreached.

        Cut members are stamped first, then each is rehung if it can. One that cannot hands its
        children in the forest the same trial, and so on down: only the part of the subtree that
        cannot be rehung one by one is searched again, from the members that kept their proof.
        """
        graph, alive, in_y, comp, witness, parent, pred, stamp = (
            self.graph, self.alive, self.in_y, self.comp, self.witness, self.parent, self.pred,
            self.stamp,
        )
        owner = graph.owner
        self.round += 1
        token = self.round
        roots = [o for o in cut if in_y[o]]
        for o in roots:
            stamp[o] = token
        unmended: list[int] = []
        for o in roots:
            if self._rehang(o, cid, token):
                stamp[o] = 0
            else:
                unmended.append(o)
        i = 0
        while i < len(unmended):
            s = unmended[i]
            i += 1
            for k in pred[s]:
                o = owner[k]
                if witness[o] == k and parent[o] == s and in_y[o] and stamp[o] != token:
                    stamp[o] = token
                    if self._rehang(o, cid, token):
                        stamp[o] = 0
                    else:
                        unmended.append(o)
        for s in unmended:
            witness[s] = -1
        frontier = []
        for s in unmended:  # lean on a member that kept its proof
            for k in graph.state_actions[s]:
                if alive[k]:
                    for j in graph.succ[k]:
                        if comp[j] != cid or witness[j] >= 0:
                            witness[s], parent[s] = k, (j if comp[j] == cid else -1)
                            frontier.append(s)
                            break
                    if witness[s] >= 0:
                        break
        self._spread(frontier)
        lost = [s for s in unmended if witness[s] < 0]
        for s in lost:
            in_y[s] = False
        return lost
