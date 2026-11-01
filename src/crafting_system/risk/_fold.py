"""Free states folded away, so the budget DP on a coarse grid moves mass only through paying states.

On a grid of step D an action cheaper than D has no whole bin to pay: its state costs 0 bins and
is free. The budget DP needs every state it moves mass through to cost at least one bin, so each
free state is eliminated: an edge into it is replaced by its exit distribution, the probability to
leave the free set for the first time at each target (a paying state, a goal, or a state that
cannot finish, where the mass is lost). The exits are the solution of (I - P_ZZ) X = P_Z,out for
the free set Z. They are found per strongly connected component of the free-to-free graph, sinks
first (Tarjan, no recursion: a free path can be thousands of states long), and a component that
loops is solved by a subtraction-free GTH elimination (as in `solver._sparse`, which risk may not import), where a row keeps its
probabilities inside the component and its `leak`, here a dict from each target outside to the
probability of reaching it. Eliminating k divides by d = the sum of the other positive entries of
its row plus its leak (never 1 - p_kk), so a self-loop of 1 - 1e-15 costs no accuracy. A component
larger than `FOLD_LIMIT` states is not folded (`None`): the exit dicts of a big dense component
would cost more than a finer grid.
"""

import heapq
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from ._chain import Chain

FOLD_LIMIT = 1500  # states of the largest free component that is still folded


@dataclass(frozen=True, slots=True)
class Folded:
    """A chain without free states and where the start's mass sits at bin 0.

    `chain` has the indices of the input; a free state has no action and no successors, and the
    rows of the paying states lead to paying states, goals and states that cannot finish.
    `initial` is the mass of the paying states at bin 0 (sorted by index) and `goal_mass` the mass
    already at a goal there; the rest of the start's mass is lost.
    """

    chain: Chain
    initial: tuple[tuple[int, float], ...]
    goal_mass: float


def fold_free(chain: Chain, bins: Sequence[int]) -> Folded | None:
    """Fold away the finishing states whose `bins` are 0; `None` when a free component passes `FOLD_LIMIT`."""
    finishing = chain.finishing_states()
    free = {i for i in finishing if bins[i] == 0}
    if not free:
        return Folded(chain, ((0, 1.0),), 0.0)
    exits = _exit_distributions(chain, free)
    if exits is None:
        return None
    action = list(chain.action)
    succ = list(chain.succ)
    for i in finishing:
        if i in free:
            action[i] = None
            succ[i] = ()
        else:
            succ[i] = _expand(chain.succ[i], exits)
    if 0 in free:
        dist = exits[0]
        initial = tuple(sorted((t, p) for t, p in dist.items() if chain.can_finish[t] and not chain.goal[t]))
        goal_mass = math.fsum(p for t, p in dist.items() if chain.goal[t])
    elif 0 in finishing:
        initial, goal_mass = ((0, 1.0),), 0.0
    else:
        initial, goal_mass = (), 1.0 if chain.goal[0] else 0.0
    return Folded(replace(chain, action=tuple(action), succ=tuple(succ)), initial, goal_mass)


def _expand(edges: tuple[tuple[int, float], ...], exits: dict[int, dict[int, float]]) -> tuple[tuple[int, float], ...]:
    """The row with every edge into a free state replaced by that state's exit distribution."""
    row: dict[int, float] = {}
    for j, p in edges:
        if j in exits:
            for t, q in exits[j].items():
                row[t] = row.get(t, 0.0) + p * q
        else:
            row[j] = row.get(j, 0.0) + p
    return tuple(sorted((t, p) for t, p in row.items() if p > 0.0))


def _components(chain: Chain, free: set[int]) -> list[list[int]]:
    """The strongly connected components of the free-to-free graph, sinks first (iterative Tarjan)."""
    edges = {i: [j for j, _ in chain.succ[i] if j in free] for i in free}
    index: dict[int, int] = {}
    low: dict[int, int] = {}
    stack: list[int] = []
    on_stack: set[int] = set()
    found: list[list[int]] = []
    for root in sorted(free):
        if root in index:
            continue
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(edges[root]))]
        while work:
            node, successors = work[-1]
            for j in successors:
                if j not in index:
                    index[j] = low[j] = len(index)
                    stack.append(j)
                    on_stack.add(j)
                    work.append((j, iter(edges[j])))
                    break
                if j in on_stack:
                    low[node] = min(low[node], index[j])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    found.append(component)
    return found


def _exit_distributions(chain: Chain, free: set[int]) -> dict[int, dict[int, float]] | None:
    """For every free state, the first non-free state it reaches by probability; `None` past `FOLD_LIMIT`."""
    components = _components(chain, free)
    if any(len(c) > FOLD_LIMIT for c in components):
        return None
    exits: dict[int, dict[int, float]] = {}
    for component in components:
        inside = set(component)
        rows: dict[int, dict[int, float]] = {z: {} for z in component}
        leaks: dict[int, dict[int, float]] = {z: {} for z in component}
        for z in component:
            row, leak = rows[z], leaks[z]
            for j, p in chain.succ[z]:
                if j in inside:
                    row[j] = p
                elif j in exits:  # a free component done before this one
                    for t, q in exits[j].items():
                        leak[t] = leak.get(t, 0.0) + p * q
                else:
                    leak[j] = leak.get(j, 0.0) + p
        if len(component) == 1 and component[0] not in rows[component[0]]:
            exits[component[0]] = leaks[component[0]]
            continue
        solved = _eliminate(rows, leaks)
        if solved is None:
            return None
        exits.update(solved)
    return exits


def _eliminate(
    rows: dict[int, dict[int, float]], leaks: dict[int, dict[int, float]]
) -> dict[int, dict[int, float]] | None:
    """GTH elimination of one component in a minimum-degree order, then the exits by back substitution."""
    preds: dict[int, set[int]] = {k: set() for k in rows}
    for r, row in rows.items():
        for j in row:
            if j != r:
                preds[j].add(r)

    def degree(k: int) -> int:
        return len(preds[k]) * (len(rows[k]) - (k in rows[k]))

    heap = [(degree(k), k) for k in rows]
    heapq.heapify(heap)
    done: set[int] = set()
    steps: list[tuple[int, float, dict[int, float], dict[int, float]]] = []
    while heap:
        cost, k = heapq.heappop(heap)
        if k in done or cost != degree(k):
            continue  # eliminated, or stale: a fresher entry was pushed when the degree changed
        row_k, leak_k = rows[k], leaks[k]
        row_k.pop(k, None)
        d = sum(row_k.values()) + sum(leak_k.values())
        if not d > 0.0:
            return None
        done.add(k)
        steps.append((k, d, row_k, leak_k))
        for j in row_k:
            preds[j].discard(k)
        touched = set(row_k)
        for r in preds[k]:
            row_r, leak_r = rows[r], leaks[r]
            factor = row_r.pop(k) / d
            for j, p in row_k.items():
                if j in row_r:
                    row_r[j] += factor * p
                else:
                    row_r[j] = factor * p
                    if j != r:
                        preds[j].add(r)
            for t, q in leak_k.items():
                leak_r[t] = leak_r.get(t, 0.0) + factor * q
            touched.add(r)
        for t in touched:
            heapq.heappush(heap, (degree(t), t))
    exits: dict[int, dict[int, float]] = {}
    for k, d, row_k, leak_k in reversed(steps):
        total = dict(leak_k)
        for j, p in row_k.items():
            for t, q in exits[j].items():
                total[t] = total.get(t, 0.0) + p * q
        exits[k] = {t: v / d for t, v in total.items()}
    return exits
