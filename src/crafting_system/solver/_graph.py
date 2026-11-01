"""Reachable-state generation, exact self-loop elimination and the finite-state analysis.

The analysis (`proper_states`) finds the states with a proper policy, then the structurally
infinite ones among them (the mass-closed pre-check, ADR-0022 guard 1).

An action may also take other states as inputs (ADR-0022): their values are paid on every attempt.
Inputs are edges of the dependency graph (they order the components) but not of the outcome graph
(only outcomes can reach the goal).

The graph is stored in flat typed arrays (about 28 bytes per transition stored and about 55 at the
peak of a solve, against about 250 for lists of lists and the caller's `Action` objects), so that 2 * 10^7 transitions fit in memory.
"""

import math
from array import array
from collections.abc import Iterable
from dataclasses import dataclass, field

from ._model import Action, Model, Outcome
from ._scc import strongly_connected_components

_WEIGHT_LIMIT = 1 << 64  # weights at or above this do not fit the `Q` array and are kept apart


class _Rows:
    """Read-only view: row `r` of a flat array cut by `offsets` (`data[offsets[r]:offsets[r + 1]]`)."""

    __slots__ = ("offsets", "data")

    def __init__(self, offsets: array, data: array) -> None:
        self.offsets = offsets
        self.data = data

    def __len__(self) -> int:
        return len(self.offsets) - 1

    def __getitem__(self, row: int) -> array:
        offsets = self.offsets
        return self.data[offsets[row] : offsets[row + 1]]

    def __iter__(self):
        offsets, data = self.offsets, self.data
        for row in range(len(offsets) - 1):
            yield data[offsets[row] : offsets[row + 1]]


class _Ranges:
    """Read-only view: the actions of state `s` are `range(first[s], first[s + 1])`."""

    __slots__ = ("first",)

    def __init__(self, first: array) -> None:
        self.first = first

    def __len__(self) -> int:
        return len(self.first) - 1

    def __getitem__(self, state: int) -> range:
        first = self.first
        return range(first[state], first[state + 1])


@dataclass(slots=True)
class Graph[S]:
    """The reachable states and every action with its self-loop compiled out.

    States are numbered in discovery order. Actions are numbered globally, grouped by state:
    `state_actions[s]` is the range of the ids of state `s`'s actions and `owner[k]` the state of
    action `k`. An action that can never leave its state is dropped (infinite cost). The
    transitions of all actions lie in one flat array in action order: action `k` owns
    `tstart[k]:tstart[k + 1]`, so the transitions of a state are one contiguous run as well.

    * `targets`, `probs`: the non-self successors of each action (merged) and `w_j / L`;
    * `succ[k]`: the successors of action `k`, a copy-slice of `targets`;
    * `cost`: effective cost `cost * (W / L)`; `cost0`: the action's own cost;
    * `weights`: the true integer weight of each transition; an action with a weight of 2^64 or
      more keeps its weights in `big_weights[k]` instead; `self_loop[k] = (position, weight)`
      is the self-loop that was compiled out and where it stood among the merged outcomes;
    * `inputs`, `kappa`, `copies`: the distinct input states of each action, `copies * W / L` (the
      retry pays the inputs again, so the factor is that of the cost; it may exceed 1) and the
      number of copies; action `k` owns `istart[k]:istart[k + 1]` of these three and `need[k]` is
      the slice of `inputs`. An action that has its own state as an input is dropped.

    The caller's `Action` objects are not kept: `original_action` rebuilds the one asked for.
    """

    states: list[S] = field(default_factory=list)
    goal: list[bool] = field(default_factory=list)
    first: array = field(default_factory=lambda: array("q"))
    owner: array = field(default_factory=lambda: array("i"))
    label: list = field(default_factory=list)
    cost: array = field(default_factory=lambda: array("d"))
    cost0: array = field(default_factory=lambda: array("d"))
    tstart: array = field(default_factory=lambda: array("q", [0]))
    targets: array = field(default_factory=lambda: array("i"))
    probs: array = field(default_factory=lambda: array("d"))
    weights: array = field(default_factory=lambda: array("Q"))
    big_weights: dict = field(default_factory=dict)
    self_loop: dict = field(default_factory=dict)
    istart: array = field(default_factory=lambda: array("q", [0]))
    inputs: array = field(default_factory=lambda: array("i"))
    kappa: array = field(default_factory=lambda: array("d"))
    copies: array = field(default_factory=lambda: array("q"))
    succ: _Rows = field(init=False)
    need: _Rows = field(init=False)
    state_actions: _Ranges = field(init=False)

    def __post_init__(self) -> None:
        self.succ = _Rows(self.tstart, self.targets)
        self.need = _Rows(self.istart, self.inputs)
        self.state_actions = _Ranges(self.first)

    def original_action(self, k: int) -> Action[S]:
        """The action `k` as it was offered: true weights, self-loop included.

        Equal to the caller's action except that repeated successors are merged into one outcome
        (at the first position, with the summed weight), zero-weight outcomes are dropped, and a
        repeated input comes back grouped at the position of its first occurrence.
        """
        low, high = self.tstart[k], self.tstart[k + 1]
        weights = self.big_weights.get(k)
        if weights is None:
            weights = self.weights[low:high]
        states = self.states
        outcomes = [Outcome(states[j], int(w)) for j, w in zip(self.targets[low:high], weights)]
        loop = self.self_loop.get(k)
        if loop is not None:
            outcomes.insert(loop[0], Outcome(states[self.owner[k]], loop[1]))
        low, high = self.istart[k], self.istart[k + 1]
        needed = tuple(
            states[y] for y, count in zip(self.inputs[low:high], self.copies[low:high])
            for _ in range(count)
        )
        return Action(self.label[k], self.cost0[k], tuple(outcomes), needed)

    def state_offsets(self) -> array:
        """`offsets` for the state-level successor lists: a state's transitions are one run."""
        tstart = self.tstart
        return array("q", (tstart[k] for k in self.first))

    def dependency_graph(self) -> tuple[array, array]:
        """`(offsets, edges)` of the state graph with the outcome edges and the input edges.

        A state's edges are one contiguous run: for each of its actions, the outcomes, then the
        inputs. Without inputs this is the outcome graph itself, `(state_offsets(), targets)`.
        """
        if not self.inputs:
            return self.state_offsets(), self.targets
        tstart, istart, first, targets, inputs = (
            self.tstart, self.istart, self.first, self.targets, self.inputs,
        )
        offsets, edges = array("q", [0]), array("i")
        for state in range(len(self.states)):
            for k in range(first[state], first[state + 1]):
                edges.extend(targets[tstart[k] : tstart[k + 1]])
                edges.extend(inputs[istart[k] : istart[k + 1]])
            offsets.append(len(edges))
        return offsets, edges


def build_graph[S](model: Model[S], starts: Iterable[S]) -> Graph[S]:
    """Explore from `starts` once, calling `model.actions` once per non-goal state.

    Integers first: W is the total weight, L the weight that leaves the state. The effective cost
    is `cost * (W / L)` and the probabilities are `w_j / L`; `1 - p_self` is never computed in floats.
    """
    graph: Graph[S] = Graph()
    index: dict[S, int] = {}
    states, first, owner, label = graph.states, graph.first, graph.owner, graph.label
    cost, cost0, tstart, targets = graph.cost, graph.cost0, graph.tstart, graph.targets
    probs, weights = graph.probs, graph.weights
    istart, inputs, kappa, copies_of = graph.istart, graph.inputs, graph.kappa, graph.copies

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
        first.append(len(owner))
        if model.is_goal(state):
            graph.goal.append(True)
            i += 1
            continue
        graph.goal.append(False)
        for action in tuple(model.actions(state)):
            merged: dict[int, int] = {}
            loop_at = -1
            for successor, weight in action.outcomes:
                if weight:
                    j = intern(successor)
                    if j == i and loop_at < 0:
                        loop_at = len(merged)
                    merged[j] = merged.get(j, 0) + weight
            total = sum(merged.values())
            loop_weight = merged.pop(i, 0)
            leave = total - loop_weight
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
            copies: dict[int, int] = {}
            if action.extra_inputs:
                if any(index.get(needed) == i for needed in action.extra_inputs):
                    continue  # needs a copy of its own state to make one: infinite, never useful
                for needed in action.extra_inputs:
                    j = intern(needed)
                    copies[j] = copies.get(j, 0) + 1
            kappas = []
            for count in copies.values():
                try:
                    pay = count * total / leave  # the retry pays the inputs again
                except OverflowError:
                    pay = math.inf
                if not math.isfinite(pay):
                    raise ValueError(
                        f"input weight overflows float64 for action {action.label!r} in state {state!r}"
                    )
                kappas.append(pay)
            k = len(owner)
            owner.append(i)
            label.append(action.label)
            cost.append(effective)
            cost0.append(action.cost)
            targets.extend(merged)
            probs.extend([weight / leave for weight in merged.values()])
            if max(merged.values()) < _WEIGHT_LIMIT:
                weights.extend(merged.values())
            else:
                weights.extend([0] * len(merged))
                graph.big_weights[k] = tuple(merged.values())
            if loop_weight:
                graph.self_loop[k] = (loop_at, loop_weight)
            tstart.append(len(targets))
            inputs.extend(copies)
            kappa.extend(kappas)
            copies_of.extend(copies.values())
            istart.append(len(inputs))
        i += 1
    first.append(len(owner))
    return graph


class _Leads:
    """For each member of one cyclic component, the actions of members that lead to it.

    `[s]` is a copy-slice of action ids. An action leads to a member by an outcome and, with
    `with_inputs`, by an input as well (once for each such edge).
    """

    __slots__ = ("local", "offsets", "actions")

    def __init__(self, graph: Graph, members: list[int], local: dict[int, int], with_inputs: bool):
        targets, tstart, first = graph.targets, graph.tstart, graph.first
        inputs, istart = graph.inputs, graph.istart
        with_inputs = with_inputs and len(inputs) > 0
        offsets = [0] * (len(members) + 1)
        for s in members:
            for j in targets[tstart[first[s]] : tstart[first[s + 1]]]:
                position = local.get(j)
                if position is not None:
                    offsets[position + 1] += 1
            if with_inputs:
                for j in inputs[istart[first[s]] : istart[first[s + 1]]]:
                    position = local.get(j)
                    if position is not None:
                        offsets[position + 1] += 1
        for position in range(len(members)):
            offsets[position + 1] += offsets[position]
        cursor = offsets[:-1]
        actions = array("i", bytes(4 * offsets[-1]))
        for s in members:
            for k in range(first[s], first[s + 1]):
                for j in targets[tstart[k] : tstart[k + 1]]:
                    position = local.get(j)
                    if position is not None:
                        actions[cursor[position]] = k
                        cursor[position] += 1
                if with_inputs:
                    for j in inputs[istart[k] : istart[k + 1]]:
                        position = local.get(j)
                        if position is not None:
                            actions[cursor[position]] = k
                            cursor[position] += 1
        self.local = local
        self.offsets = array("q", offsets)
        self.actions = actions

    def __getitem__(self, state: int) -> array:
        position = self.local[state]
        return self.actions[self.offsets[position] : self.offsets[position + 1]]


class _Reverse(_Leads):
    """The actions of members that lead to each member of one cyclic component, by any edge.

    Only these matter while the component is settled: an action owned by a state outside it is
    not retained yet (components are settled sink-first), so it is never alive. The safety peel
    follows every edge, since an action dies with any of its outcomes or inputs. `.out` is the
    view of the outcome edges alone, which is what reaching the goal follows; with no inputs in
    the graph it is this very object.
    """

    __slots__ = ("_out",)

    def __init__(self, graph: Graph, members: list[int]) -> None:
        local = {state: position for position, state in enumerate(members)}
        super().__init__(graph, members, local, True)
        self._out = _Leads(graph, members, local, False) if len(graph.inputs) else None

    @property
    def out(self) -> _Leads:
        return self if self._out is None else self._out


def proper_states[S](
    graph: Graph[S], banned: Iterable[int] = frozenset()
) -> tuple[list[bool], list[bool]]:
    """The states with a proper policy, and the actions that never risk a dead state.

    The set is the greatest fixpoint Y of: goals, plus states with an action whose successors all
    lie in Y and at least one is already reached (least fixpoint inside). Backward reachability
    alone would keep an action that can fall into a dead state, which costs infinity. Returns
    `(alive, in_y)`: `alive[k]` is True for retained actions, `in_y[s]` for finite states, and
    `alive[k]` holds exactly when the owner of `k`, every successor of `k` and every input of `k`
    are in Y. An input of a dead state is dead too (death runs along input edges), but only
    outcomes count for reaching the goal.

    A state in `banned` (state indices) starts outside Y: its actions are not alive, nor is any
    action that has it as an outcome or an input, and the death spreads from there exactly as
    from any state without a retained action.

    A finite state with a proper policy can still cost infinity when every policy needs as much
    of what it makes as it makes (ADR-0022). The structural cases are decided here, by the
    mass-closed pre-check `_mass_closed` (ADR guard 1): the states it finds are banned and the
    analysis is made again, until none is left. What it does not see (a component critical
    through its weights, or one that is supercritical only for some policies) is left to the
    value ceiling and the value iteration of `solve_cyclic`. With no inputs in the graph the
    pre-check is skipped and the result is that of `_settle` alone.
    """
    banned = frozenset(banned)
    while True:
        alive, in_y = _settle(graph, banned)
        if not graph.inputs:
            return alive, in_y
        closed = _mass_closed(graph, alive, in_y)
        if not closed:
            return alive, in_y
        banned |= closed


def _settle[S](graph: Graph[S], banned: frozenset[int]) -> tuple[list[bool], list[bool]]:
    """One pass of the finite-state analysis (see `proper_states`), with `banned` outside Y.

    Whether a state is in Y depends only on the states it can reach, so the strongly connected
    components of the dependency graph (outcomes and inputs) are settled sink-first and a
    component only meets final answers downstream. A state alone is decided on the spot; a cycle
    is settled by `_Cycle.settle`.
    """
    n_states = len(graph.states)
    targets, tstart, need = graph.targets, graph.tstart, graph.need
    has_inputs = len(graph.inputs) > 0
    alive = [False] * len(graph.owner)
    in_y = [False] * n_states
    cycle = _Cycle(graph, alive, in_y, banned)
    offsets, edges = graph.dependency_graph()
    components = strongly_connected_components(offsets, edges, range(n_states))
    for cid, component in enumerate(components):
        if len(component) > 1:  # self-loops are compiled out, so one state alone has no cycle
            cycle.settle(component, cid)
            continue
        state = component[0]
        if banned and state in banned:
            continue
        if graph.goal[state]:
            in_y[state] = True
            continue
        for k in graph.state_actions[state]:
            if all(in_y[j] for j in targets[tstart[k] : tstart[k + 1]]) and (
                not has_inputs or all(in_y[y] for y in need[k])
            ):
                alive[k] = True
                in_y[state] = True
    return alive, in_y


def _mass_closed[S](graph: Graph[S], alive: list[bool], in_y: list[bool]) -> set[int]:
    """The greatest set D of non-goal states of Y in which every alive action sends mass >= 1 into D.

    The mass of an action into D is an exact integer test: the weight of its non-self outcomes
    that lie in D plus `W` times the copies of its inputs that lie in D, against `L`, the weight
    of its non-self outcomes (`W` is `L` plus the self-loop weight). Over `L` it is the row sum
    of `M` in `V = c + M V`; every policy restricted to D then has all row sums at least 1, so
    `rho(M) >= 1` and its value is infinite (ADR-0022, guard 1). It must run on the settled Y:
    a state outside Y is no mass and an action that touches one is not alive.

    A linear worklist, not repeated passes. Each alive action keeps its current mass. The first
    pass counts it against all of Y and collects the owners that already fail; only if there are
    any are the predecessor lists built (lazily, from the alive actions of the survivors), and a
    state that leaves D subtracts its contribution from every alive action pointing at it, by
    outcome or by input, and drops the owner of any action whose mass falls below `L`. Python
    integers throughout: weights reach 2^64 and beyond, where floats would round.
    """
    n_states = len(graph.states)
    first, owner, goal, self_loop = graph.first, graph.owner, graph.goal, graph.self_loop
    targets, tstart, weights, big = graph.targets, graph.tstart, graph.weights, graph.big_weights
    inputs, istart, copies = graph.inputs, graph.istart, graph.copies
    candidates = [s for s in range(n_states) if in_y[s] and not goal[s]]
    cand = bytearray(n_states)
    for s in candidates:
        cand[s] = 1
    in_d = bytearray(cand)
    need = [0] * len(owner)  # L of each alive action of a candidate
    mass = [0] * len(owner)  # its current mass into D

    def parts(k):
        """Outcome states and weights of `k` (true integers), `L` and `W`."""
        low, high = tstart[k], tstart[k + 1]
        w = big.get(k)
        if w is None:
            w = weights[low:high]
        leave = sum(w)
        loop = self_loop.get(k)
        return targets[low:high], w, leave, leave + (loop[1] if loop is not None else 0)

    failing: list[int] = []
    for s in candidates:
        for k in range(first[s], first[s + 1]):
            if alive[k]:
                outs, w, leave, total = parts(k)
                low, high = istart[k], istart[k + 1]
                got = sum(x for j, x in zip(outs, w) if cand[j])
                got += total * sum(c for y, c in zip(inputs[low:high], copies[low:high]) if cand[y])
                need[k], mass[k] = leave, got
                if got < leave:
                    failing.append(s)
                    break
    if not failing:
        return set(candidates)  # nobody falls: all of Y (less the goals) is closed
    for s in failing:
        in_d[s] = 0
    pred: dict[int, list[tuple[int, int]]] = {}  # state -> (action, its contribution)
    for s in candidates:
        if in_d[s]:
            for k in range(first[s], first[s + 1]):
                if alive[k]:
                    outs, w, _, total = parts(k)
                    for j, x in zip(outs, w):
                        if cand[j]:
                            pred.setdefault(j, []).append((k, x))
                    low, high = istart[k], istart[k + 1]
                    for y, c in zip(inputs[low:high], copies[low:high]):
                        if cand[y]:
                            pred.setdefault(y, []).append((k, total * c))
    queue = failing
    while queue:
        for k, amount in pred.get(queue.pop(), ()):
            o = owner[k]
            if in_d[o]:
                mass[k] -= amount
                if mass[k] < need[k]:
                    in_d[o] = 0
                    queue.append(o)
    return {s for s in candidates if in_d[s]}


_CLIMB = 24  # steps up the forest `_Cycle._rehang` spends per candidate witness


class _Cycle[S]:
    """Settles one cyclic component: safety peel and reachability, repaired instead of redone.

    Every member starts in Y, except the banned ones (they start out, with no alive action). An action is alive while its owner, all its successors and all its
    inputs are in Y; a member with no alive action leaves Y, which kills the actions into it by
    an outcome or an input edge (the peel, a worklist touching each edge once). The remaining
    members must also reach the outside of the component (final members of Y) through alive
    actions and outcome edges only, or they leave Y too (an input never reaches the goal). Each
    reached member keeps the alive action `witness` and the successor `parent` it leans on, a
    forest rooted outside the component. When the peel kills a witness, that member and then its
    children are first tried for another witness found by a short climb (`_rehang`); only what
    cannot be rehung one by one is searched again, and the rest keeps its proof. The first
    reachability pass is one sweep.

    The cost is linear when the removals come from the peel or from small subtrees. A cut that
    lands high in a big proof tree, mended again and again by alternatives that sit deeper than
    `_CLIMB` steps, still costs the size of the tree each time, so it stays quadratic there
    (decremental reachability has no known linear algorithm).
    """

    def __init__(
        self, graph: Graph[S], alive: list[bool], in_y: list[bool], banned: frozenset[int]
    ) -> None:
        count = len(graph.states)
        self.graph = graph
        self.banned = banned  # members that start outside Y (and never come in)
        self.pred: _Reverse | None = None  # set for the component being settled
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
        banned = self.banned
        for s in members:
            comp[s] = cid
            in_y[s] = not banned or s not in banned
        self.pred = _Reverse(graph, members)
        for s in members:
            if banned and s in banned:
                continue  # no action of a banned member is alive
            for k in graph.state_actions[s]:
                # members count as in Y, outside is final
                if all(in_y[j] for j in graph.succ[k]) and (
                    not graph.inputs or all(in_y[y] for y in graph.need[k])
                ):
                    alive[k] = True
                    live[s] += 1
        queue = [s for s in members if live[s] == 0]
        for s in queue:
            in_y[s] = False  # a banned member is here too: it has nothing alive, and is out already
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
        """Reverse reachability from `frontier` over alive actions and outcome edges only."""
        owner, alive, witness, parent = (
            self.graph.owner, self.alive, self.witness, self.parent,
        )
        pred = self.pred.out
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
        pred = pred.out  # the forest hangs on outcome edges
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
