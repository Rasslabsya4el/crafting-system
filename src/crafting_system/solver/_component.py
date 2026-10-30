"""Solving one strongly connected component with its downstream values fixed."""

import math
from dataclasses import dataclass

from ._certify import own_multipliers, relative_error, rounding_allowance
from ._graph import Graph

IMPROVEMENT = 1e-12  # policy iteration switches action only on a relative gain this large
MAX_POLICY_ITERATIONS = 100


@dataclass(slots=True)
class Bellman:
    """The component's Bellman operator.

    For local state `l` and its `a`-th retained action, the backup is
    `base[l][a] + sum(prob * V[j] for j, prob in zip(inside[l][a], prob[l][a]))` where `base`
    holds the effective cost plus the fixed contribution of the successors outside the component.
    """

    states: list[int]
    ids: list[list[int]]
    base: list[list[float]]
    inside: list[list[list[int]]]
    prob: list[list[list[float]]]
    has_exit: list[list[bool]]
    g: float  # smallest constant term (effective cost + fixed downstream part) of a retained action
    terms: int  # largest number of terms in one Bellman sum
    low_d: float  # min(1, lo of the exit successors)
    high_d: float  # max(1, hi of the exit successors)


def build_bellman[S](
    graph: Graph[S],
    alive: list[bool],
    component: list[int],
    value: list[float],
    lo: list[float],
    hi: list[float],
) -> Bellman:
    local = {state: position for position, state in enumerate(component)}
    bellman = Bellman(component, [], [], [], [], [], math.inf, 1, 1.0, 1.0)
    for state in component:
        ids, base, inside, prob, has_exit = [], [], [], [], []
        for k in graph.state_actions[state]:
            if not alive[k]:
                continue
            constant = graph.cost[k]
            here: list[int] = []
            weights: list[float] = []
            exits = False
            for j, p in zip(graph.succ[k], graph.prob[k]):
                position = local.get(j)
                if position is None:
                    constant += p * value[j]
                    exits = True
                    bellman.low_d = min(bellman.low_d, lo[j])
                    bellman.high_d = max(bellman.high_d, hi[j])
                else:
                    here.append(position)
                    weights.append(p)
            bellman.g = min(bellman.g, constant)
            bellman.terms = max(bellman.terms, 1 + len(graph.succ[k]))
            ids.append(k)
            base.append(constant)
            inside.append(here)
            prob.append(weights)
            has_exit.append(exits)
        bellman.ids.append(ids)
        bellman.base.append(base)
        bellman.inside.append(inside)
        bellman.prob.append(prob)
        bellman.has_exit.append(has_exit)
    return bellman


def backup_single(bellman: Bellman) -> tuple[float, int]:
    """One Bellman backup of an acyclic single state: its value and the cheapest action id."""
    best, best_id = math.inf, -1
    for q, k in zip(bellman.base[0], bellman.ids[0]):
        if q < best:
            best, best_id = q, k
    return best, best_id


@dataclass(slots=True)
class CyclicResult:
    values: list[float]
    choice: list[int]  # global action id per local state
    lower: float  # l_own
    upper: float  # u_own
    converged: bool


def _backup(bellman: Bellman, values: list[float], local: int) -> tuple[float, int]:
    best, best_a = math.inf, -1
    inside, prob = bellman.inside[local], bellman.prob[local]
    for a, q in enumerate(bellman.base[local]):
        for j, p in zip(inside[a], prob[a]):
            q += p * values[j]
        if q < best:
            best, best_a = q, a
    return best, best_a


def _certify(bellman: Bellman, values: list[float]) -> tuple[float, float, float, list[int]]:
    """Residuals `(e, d)` of `values`, the largest backup `max T V`, and the greedy action indices."""
    e = d = top = 0.0
    greedy = []
    for local, current in enumerate(values):
        best, best_a = _backup(bellman, values, local)
        greedy.append(best_a)
        if best > top:
            top = best
        gap = best - current
        if gap > e:
            e = gap
        elif -gap > d:
            d = -gap
    return e, d, top, greedy


def _attractor(bellman: Bellman) -> tuple[list[int], list[int]]:
    """A proper initial policy and the order of states, closest to an exit first.

    States with an action that leaves the component rank 0. A state gets the first action that
    has a successor of lower rank, so following it always has a chance to get nearer an exit.
    """
    size = len(bellman.states)
    preds: list[list[tuple[int, int]]] = [[] for _ in range(size)]
    for local in range(size):
        for a, here in enumerate(bellman.inside[local]):
            for j in here:
                preds[j].append((local, a))
    policy = [-1] * size
    order = []
    for local in range(size):
        for a, exits in enumerate(bellman.has_exit[local]):
            if exits:
                policy[local] = a
                order.append(local)
                break
    head = 0
    while head < len(order):
        j = order[head]
        head += 1
        for local, a in preds[j]:
            if policy[local] == -1:
                policy[local] = a
                order.append(local)
    return policy, order


def _evaluate(bellman: Bellman, policy: list[int]) -> list[float] | None:
    """Solve (I - P) V = base for a fixed policy by Gaussian elimination with partial pivoting."""
    size = len(policy)
    rows = []
    for local in range(size):
        row = [0.0] * (size + 1)
        row[local] = 1.0
        a = policy[local]
        for j, p in zip(bellman.inside[local][a], bellman.prob[local][a]):
            row[j] -= p
        row[size] = bellman.base[local][a]
        rows.append(row)
    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(rows[r][column]))
        if rows[pivot][column] == 0.0:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        top = rows[column]
        for r in range(column + 1, size):
            factor = rows[r][column] / top[column]
            if factor:
                row = rows[r]
                for c in range(column, size + 1):
                    row[c] -= factor * top[c]
    values = [0.0] * size
    for r in range(size - 1, -1, -1):
        row = rows[r]
        total = row[size]
        for c in range(r + 1, size):
            total -= row[c] * values[c]
        values[r] = total / row[r]
    if not all(math.isfinite(v) and v > 0.0 for v in values):
        return None
    return values


def _policy_iteration(bellman: Bellman, policy: list[int]) -> list[float] | None:
    values = None
    for _ in range(MAX_POLICY_ITERATIONS):
        values = _evaluate(bellman, policy)
        if values is None:
            return None
        changed = False
        for local in range(len(policy)):
            current = _q(bellman, values, local, policy[local])
            best, best_a = _backup(bellman, values, local)
            if best < current * (1.0 - IMPROVEMENT):
                policy[local] = best_a
                changed = True
        if not changed:
            return values
    return values


def _q(bellman: Bellman, values: list[float], local: int, a: int) -> float:
    q = bellman.base[local][a]
    for j, p in zip(bellman.inside[local][a], bellman.prob[local][a]):
        q += p * values[j]
    return q


def solve_cyclic(
    bellman: Bellman, tolerance: float, direct_solve_limit: int, max_sweeps: int
) -> CyclicResult:
    """Policy iteration for small components, then Gauss-Seidel sweeps until certified.

    Stops when the iteration's own relative error (the residuals `e`, `d` against `g`) is at most
    `tolerance`, or when both residuals are already at the rounding floor `delta` (more sweeps
    could not improve the reported bound by more than a factor of about two); otherwise returns the best certified candidate seen, with `converged` False. The
    reported multipliers also carry the operator mismatch `delta` (see `_certify`), so the reported
    error can exceed `tolerance`; with no upper certificate the upper multiplier is infinite.
    """
    rho = rounding_allowance(bellman.terms)
    size = len(bellman.states)
    policy, order = _attractor(bellman)
    if len(order) != size:  # cannot happen: every state of the finite set can reach an exit
        raise RuntimeError("internal error: a component state has no path to an exit")
    values = [0.0] * size
    best_error = math.inf
    best: CyclicResult | None = None

    def examine(candidate: list[float]) -> bool:
        nonlocal best_error, best
        e, d, top, greedy = _certify(bellman, candidate)
        delta = rho * top
        iteration = relative_error(*own_multipliers(bellman.g, e, d))
        lower, upper = own_multipliers(bellman.g, e + delta, d + delta)
        error = relative_error(lower, upper)
        stop = iteration <= tolerance or (e <= delta and d <= delta)  # or at the rounding floor
        if stop or best is None or error < best_error:
            best_error = error
            choice = [bellman.ids[local][a] for local, a in enumerate(greedy)]
            best = CyclicResult(list(candidate), choice, lower, upper, stop)
        return stop

    if size <= direct_solve_limit:
        solved = _policy_iteration(bellman, policy)
        if solved is not None:
            values = solved
            if examine(values):
                return best  # type: ignore[return-value]
    for _ in range(max_sweeps):
        for local in order:
            values[local] = _backup(bellman, values, local)[0]
        if examine(values):
            return best  # type: ignore[return-value]
    return best  # type: ignore[return-value]
