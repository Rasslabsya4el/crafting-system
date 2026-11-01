"""Solving one strongly connected component with its downstream values fixed."""

import math
from array import array
from dataclasses import dataclass

from ._certify import own_multipliers, relative_error, rounding_allowance
from ._graph import Graph

IMPROVEMENT = 1e-12  # policy iteration switches action only on a relative gain this large
MAX_POLICY_ITERATIONS = 100


@dataclass(slots=True)
class Bellman:
    """The component's Bellman operator, in flat arrays (12 bytes per transition).

    Local state `l` owns the retained actions `astart[l]:astart[l + 1]`; an action `a` is
    identified by that index. Its backup is `base[a] + sum(prob[t] * V[inside[t]])` over the
    transitions `tptr[a]:tptr[a + 1]`, where `base` holds the effective cost plus the fixed
    contribution of the successors and inputs outside the component and `inside` the local
    positions of the successors and inputs inside. `prob` holds p for an outcome and kappa for
    an input; kappa may be 1 or more, so for a `branching` component (an input inside) the
    matrix is not a contraction. `has_exit` is about outcomes only: an input never reaches the
    goal. `ids[a]` is the global action id.
    """

    states: list[int]
    astart: list[int]
    ids: array
    base: array
    has_exit: bytearray
    tptr: array
    inside: array
    prob: array
    g: float  # smallest constant term (effective cost + fixed downstream part) of a retained action
    terms: int  # largest number of terms in one Bellman sum
    low_d: float  # min(1, lo of the exit successors and outside inputs)
    high_d: float  # max(1, hi of the exit successors and outside inputs)
    branching: bool = False  # some action takes an input from inside the component


def build_bellman[S](
    graph: Graph[S],
    alive: list[bool],
    component: list[int],
    value: list[float],
    lo: list[float],
    hi: list[float],
) -> Bellman:
    local = {state: position for position, state in enumerate(component)}
    targets, probs, tstart, cost = graph.targets, graph.probs, graph.tstart, graph.cost
    inputs, kappas, istart = graph.inputs, graph.kappa, graph.istart
    ids, base, has_exit = array("i"), array("d"), bytearray()
    tptr, inside, prob = array("q", [0]), array("i"), array("d")
    astart = [0]
    g, terms, low_d, high_d = math.inf, 1, 1.0, 1.0
    branching = False
    for state in component:
        for k in graph.state_actions[state]:
            if not alive[k]:
                continue
            constant = cost[k]
            exits = False
            low, high = tstart[k], tstart[k + 1]
            for j, p in zip(targets[low:high], probs[low:high]):
                position = local.get(j)
                if position is None:
                    constant += p * value[j]
                    exits = True
                    if lo[j] < low_d:
                        low_d = lo[j]
                    if hi[j] > high_d:
                        high_d = hi[j]
                else:
                    inside.append(position)
                    prob.append(p)
            ilow, ihigh = istart[k], istart[k + 1]
            if ihigh > ilow:  # the inputs, after the outcomes: input-free arithmetic is untouched
                for y, kappa in zip(inputs[ilow:ihigh], kappas[ilow:ihigh]):
                    position = local.get(y)
                    if position is None:
                        constant += kappa * value[y]
                        if lo[y] < low_d:
                            low_d = lo[y]
                        if hi[y] > high_d:
                            high_d = hi[y]
                    else:
                        inside.append(position)
                        prob.append(kappa)
                        branching = True
            if constant < g:
                g = constant
            terms = max(terms, 1 + high - low + ihigh - ilow)
            ids.append(k)
            base.append(constant)
            has_exit.append(exits)
            tptr.append(len(inside))
        astart.append(len(ids))
    return Bellman(
        component, astart, ids, base, has_exit, tptr, inside, prob, g, terms, low_d, high_d, branching
    )


def backup_single(bellman: Bellman) -> tuple[float, int]:
    """One Bellman backup of an acyclic single state: its value and the cheapest action id."""
    best, best_id = math.inf, -1
    for q, k in zip(bellman.base, bellman.ids):
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
    """The best backup of local state `local` and the index of its action."""
    best, best_a = math.inf, -1
    tptr, base, inside, prob = bellman.tptr, bellman.base, bellman.inside, bellman.prob
    first, last = bellman.astart[local], bellman.astart[local + 1]
    start = tptr[first]
    for a in range(first, last):
        end = tptr[a + 1]
        q = base[a]
        if end - start == 1:
            q += prob[start] * values[inside[start]]
        elif end > start:
            for j, p in zip(inside[start:end], prob[start:end]):
                q += p * values[j]
        start = end
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
    """A proper initial policy (an action index per local state) and the order of states, closest to an exit first.

    States with an action that leaves the component rank 0. A state gets the first action that
    has a successor of lower rank, so following it always has a chance to get nearer an exit.
    """
    size = len(bellman.states)
    astart, tptr, inside = bellman.astart, bellman.tptr, bellman.inside
    ends = [0] * (size + 1)  # the actions that lead to local state j: leads[ends[j]:ends[j + 1]]
    for j in inside:
        ends[j + 1] += 1
    for j in range(size):
        ends[j + 1] += ends[j]
    cursor = ends[:size]
    leads = array("i", bytes(4 * len(inside)))
    owner = array("i", bytes(4 * len(bellman.ids)))
    for local in range(size):
        for a in range(astart[local], astart[local + 1]):
            owner[a] = local
            for j in inside[tptr[a] : tptr[a + 1]]:
                leads[cursor[j]] = a
                cursor[j] += 1
    policy = [-1] * size
    order = []
    for local in range(size):
        for a in range(astart[local], astart[local + 1]):
            if bellman.has_exit[a]:
                policy[local] = a
                order.append(local)
                break
    head = 0
    while head < len(order):
        j = order[head]
        head += 1
        for a in leads[ends[j] : ends[j + 1]]:
            local = owner[a]
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
        low, high = bellman.tptr[a], bellman.tptr[a + 1]
        for j, p in zip(bellman.inside[low:high], bellman.prob[low:high]):
            row[j] -= p
        row[size] = bellman.base[a]
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
    q = bellman.base[a]
    low, high = bellman.tptr[a], bellman.tptr[a + 1]
    for j, p in zip(bellman.inside[low:high], bellman.prob[low:high]):
        q += p * values[j]
    return q


def solve_cyclic(
    bellman: Bellman, tolerance: float, direct_solve_limit: int, max_sweeps: int
) -> CyclicResult:
    """Policy iteration for small components, then Gauss-Seidel sweeps until certified.

    A branching component (an input inside) is solved by the sweeps alone, from zeros, over all
    local states in index order: the attractor policy may be supercritical there (the matrix is
    not a contraction), while the iterate rises monotonically from 0 and stays at most the least
    fixed point, so it is a safe lower bound at every sweep. A critical or supercritical component
    (infinite value) does not converge: it is returned with `converged` False when `max_sweeps`
    run out, when the iterate overflows, or when it stops with no upper certificate.

    Stops when the iteration's own relative error (the residuals `e`, `d` against `g`) is at most
    `tolerance`, or when both residuals are already at the rounding floor `delta` (more sweeps
    could not improve the reported bound by more than a factor of about two); otherwise returns the best certified candidate seen, with `converged` False. The
    reported multipliers also carry the operator mismatch `delta` (see `_certify`), so the reported
    error can exceed `tolerance`; with no upper certificate the upper multiplier is infinite.
    """
    rho = rounding_allowance(bellman.terms)
    size = len(bellman.states)
    branching = bellman.branching
    if branching:
        policy, order = [], range(size)
    else:
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
            choice = [bellman.ids[a] for a in greedy]
            best = CyclicResult(list(candidate), choice, lower, upper, stop)
        return stop

    if size <= direct_solve_limit and not branching:
        solved = _policy_iteration(bellman, policy)
        if solved is not None:
            values = solved
            if examine(values):
                return best  # type: ignore[return-value]
    for _ in range(max_sweeps):
        for local in order:
            values[local] = _backup(bellman, values, local)[0]
        if branching and best is not None and not math.isfinite(max(values)):
            return best  # type: ignore[return-value]  # the iterate overflowed: infinite, not certified
        if examine(values):
            if branching and best.upper == math.inf:  # type: ignore[union-attr]
                best.converged = False  # type: ignore[union-attr]  # stopped with no upper certificate
            return best  # type: ignore[return-value]
    return best  # type: ignore[return-value]
