"""Moments of the total cost of a proper policy whose actions consume other runs (`extra_inputs`).

An action at state s costs c_s; then, for every input copy y (independent, started at y, run by the
same policy until a goal, paying again on every retry) its whole run cost A_y is added; then the
outcome j is drawn with p_sj. So the mean V solves (I - M) V = c with M[s, j] = p_sj plus one per
copy M[s, y] += 1 (V = 0 at a goal). The row sums of M can exceed 1, so M need not be a contraction;
the total cost has a finite mean exactly when the spectral radius rho(M) is below 1.

Solving. The dependency graph has an edge from s to every outcome and every input. Its strongly
connected components (iterative Tarjan) come out dependencies first; each is solved with a dense
`numpy.linalg.solve`, the already-solved values of the components below moved to the right-hand side.

Certificate. With V^ the computed solution, r = c - (I - M) V^ the residual and
rounding_i = (terms_i + 3) eps (V^_i + (M V^)_i + c_i) the allowance for the float arithmetic that forms
it (terms_i is the number of outcomes plus input copies of state i), let
e = max_i (|r_i| + rounding_i) / c_i. The exact residual r' satisfies |r'| <= e c. If e < 1 and V^ > 0
then (I - M) V^ = c - r' >= (1 - e) c > 0, so M V^ < V^ componentwise and the Collatz-Wielandt bound gives
rho(M) < 1; then (I - M)^-1 >= 0 and |V - V^| = |(I - M)^-1 r'| <= e (I - M)^-1 c = e V, so
V in [V^ / (1 + e), V^ / (1 - e)]. Otherwise (e >= 1, a non-positive or non-finite value, a singular
component) there is no certified positive solution and `NotSubcritical` is raised. The returned error
is e.

Second moment. With m1 the mean, c the cost of the action at s, a_i the m1 of its i-th input copy
and r = sum_j p_sj m1_j, the total of one step is X + T_next with X = c + sum_i A_i, all runs
independent, so E[T^2] = E[X^2] + 2 E[X] E[T_next] + E[T_next^2] and (I - M) m2 = rhs with
rhs_s = c^2 + 2 c (sum a + r) + 2 sum_{i<j} a_i a_j + 2 r sum a (the E[A_i^2] and E[T_next^2] parts are
M m2). The right-hand side is a polynomial of degree at most 2 in the true m1 values with
nonnegative coefficients, and the true m1 is m1^ times a factor in [1 / (1 + e1), 1 / (1 - e1)], so
the true right-hand side lies in rhs^ * [1 / (1 + e1)^2, 1 / (1 - e1)^2]. With e2 the error of the
second solve and rho the allowance for the float arithmetic building rhs^ the true second moment
lies in m2 * [(1 - rho) / ((1 + e1)^2 (1 + e2)), (1 + rho) / ((1 - e1)^2 (1 - e2))]. The variance
interval is [lo(m2) - hi(m1)^2, hi(m2) - lo(m1)^2] clipped at zero.

Donor counts. The expected number of visits of every state is row 0 of (I - M)^-1: N solves
(I - M)^T N = e_0, by the same components in the opposite order. The runs started at an input state y
number sum_s N_s copies(s, y). With r' = e_0 - (I - M)^T N^ the error of N^ is
(I - M)^-T r', of 1-norm at most kappa ||r'||_1, where kappa = ||(I - M)^-1 1||_inf <= max_i V_i / c_min
(because c >= c_min 1 and V = (I - M)^-1 c) and V_i <= V^_i / (1 - e).
"""

import math
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ._chain import Chain
from ._moments import real_costs

EPS = sys.float_info.epsilon
MIN_COST_ROUNDING = 1e-14  # relative allowance for the float arithmetic building the second right-hand side
MIN_COUNT_ROUNDING = 1e-12  # relative allowance for summing visits into a donor count


class NotSubcritical(Exception):
    """The system has no certified positive solution: the total cost has an infinite (or undecided) mean."""


def bracket(value: float, error: float) -> tuple[float, float]:
    """`[value / (1 + error), value / (1 - error)]`, infinite above when the error is 1 or more."""
    high = value / (1.0 - error) if error < 1.0 else math.inf
    return value / (1.0 + error), high


@dataclass(frozen=True, slots=True)
class _System:
    """The matrix M by rows and columns over the expanded states, and its components (dependencies first)."""

    size: int
    nodes: tuple[int, ...]
    rows: tuple[tuple[tuple[int, float], ...], ...]
    cols: tuple[tuple[tuple[int, float], ...], ...]
    terms: tuple[int, ...]
    comps: tuple[tuple[int, ...], ...]
    comp_of: tuple[int, ...]


def _system(chain: Chain) -> _System:
    """Outcome edges of the states that can finish, input edges of every expanded state."""
    size = len(chain.states)
    expanded = [a is not None for a in chain.action]
    rows: list[tuple[tuple[int, float], ...]] = [() for _ in range(size)]
    terms = [0] * size
    for i in range(size):
        if not expanded[i]:
            continue
        merged: dict[int, float] = {}
        if chain.can_finish[i]:
            for j, p in chain.succ[i]:
                if expanded[j]:
                    merged[j] = merged.get(j, 0.0) + p
        for y in chain.inputs[i]:
            if expanded[y]:
                merged[y] = merged.get(y, 0.0) + 1.0
        rows[i] = tuple(merged.items())
        terms[i] = len(chain.succ[i]) + len(chain.inputs[i])
    columns: list[list[tuple[int, float]]] = [[] for _ in range(size)]
    for i, edges in enumerate(rows):
        for j, coef in edges:
            columns[j].append((i, coef))
    nodes = tuple(i for i in range(size) if expanded[i])
    comps, comp_of = _components(size, nodes, rows)
    return _System(
        size,
        nodes,
        tuple(rows),
        tuple(tuple(c) for c in columns),
        tuple(terms),
        comps,
        comp_of,
    )


def _components(
    size: int, nodes: Sequence[int], rows: Sequence[Sequence[tuple[int, float]]]
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    """Strongly connected components, iterative Tarjan; each comes out after everything it depends on."""
    index = [-1] * size
    low = [0] * size
    on_stack = [False] * size
    comp_of = [-1] * size
    stack: list[int] = []
    comps: list[tuple[int, ...]] = []
    counter = 0
    for root in nodes:
        if index[root] != -1:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack[root] = True
        work = [(root, 0)]
        while work:
            v, k = work[-1]
            if k < len(rows[v]):
                work[-1] = (v, k + 1)
                w = rows[v][k][0]
                if index[w] == -1:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack[w] = True
                    work.append((w, 0))
                elif on_stack[w]:
                    low[v] = min(low[v], index[w])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
            if low[v] == index[v]:
                members = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp_of[w] = len(comps)
                    members.append(w)
                    if w == v:
                        break
                comps.append(tuple(members))
    return tuple(comps), tuple(comp_of)


def _proper_system(chain: Chain) -> _System:
    if not chain.proper:
        raise ValueError("the moments of a policy that cannot always finish are not defined here")
    return _system(chain)


def _sweep(
    system: _System,
    edges: Sequence[Sequence[tuple[int, float]]],
    order: Sequence[Sequence[int]],
    base: Sequence[float],
) -> list[float]:
    """Solve x_j - sum_{(k, coef) in edges[j]} coef x_k = base[j], component by component in `order`."""
    values = [0.0] * system.size
    for comp in order:
        if len(comp) == 1:
            j = comp[0]
            own = 0.0
            rest = [base[j]]
            for k, coef in edges[j]:
                if k == j:
                    own += coef
                else:
                    rest.append(coef * values[k])
            pivot = 1.0 - own
            if pivot <= 0.0:
                raise NotSubcritical(f"state {j} needs at least as much of itself as it yields")
            values[j] = math.fsum(rest) / pivot
            if not math.isfinite(values[j]):
                raise NotSubcritical("a value is not finite")
            continue
        local = {j: k for k, j in enumerate(comp)}
        matrix = np.eye(len(comp))
        rhs = np.empty(len(comp))
        for j in comp:
            row = local[j]
            rest = [base[j]]
            for k, coef in edges[j]:
                if k in local:
                    matrix[row, local[k]] -= coef
                else:
                    rest.append(coef * values[k])
            rhs[row] = math.fsum(rest)
        try:
            with np.errstate(all="ignore"):
                solution = np.linalg.solve(matrix, rhs)
        except np.linalg.LinAlgError:
            raise NotSubcritical("a component is singular") from None
        if not np.all(np.isfinite(solution)):
            raise NotSubcritical("a value is not finite")
        for j, value in zip(comp, solution, strict=True):
            values[j] = float(value)
    return values


def _solve(system: _System, costs: Sequence[float]) -> tuple[list[float], float]:
    for i in system.nodes:
        if not (math.isfinite(costs[i]) and costs[i] > 0.0):
            raise ValueError(f"cost of state {i} must be finite and above zero, got {costs[i]!r}")
    values = _sweep(system, system.rows, system.comps, costs)
    worst = 0.0
    for i in system.nodes:
        ahead = math.fsum(coef * values[j] for j, coef in system.rows[i])
        residual = costs[i] - values[i] + ahead
        rounding = (system.terms[i] + 3) * EPS * (values[i] + ahead + costs[i])
        worst = max(worst, (abs(residual) + rounding) / costs[i])
        if not values[i] > 0.0:
            raise NotSubcritical("a value is not positive")
    if not worst < 1.0:
        raise NotSubcritical("the residual is as large as the costs")
    return values, worst


def solve_costs(chain: Chain, costs: Sequence[float]) -> tuple[list[float], float]:
    """Mean total cost of every state when state i pays `costs[i]` per execution, and its error bound.

    Goals have value 0. Raises `NotSubcritical` when the mean is infinite or not certified.
    """
    return _solve(_proper_system(chain), costs)


def mean_and_variance(
    chain: Chain,
) -> tuple[tuple[float, float, float], tuple[float, float, float], list[float]]:
    """`(mean, variance, m1)`, the first two as `(value, low, high)`, for a proper policy."""
    system = _proper_system(chain)
    costs = real_costs(chain)
    m1, e1 = _solve(system, costs)
    second = [0.0] * len(costs)
    degree = 0
    for s in system.nodes:
        c = costs[s]
        feeds = [m1[y] for y in chain.inputs[s]]
        ahead = math.fsum(p * m1[j] for j, p in chain.succ[s])
        total = math.fsum(feeds)
        pairs = 0.0
        running = 0.0
        for a in feeds:
            pairs += a * running
            running += a
        second[s] = c * c + 2.0 * c * (total + ahead) + 2.0 * pairs + 2.0 * ahead * total
        degree = max(degree, len(chain.succ[s]) + 2 * len(chain.inputs[s]))
    m2, e2 = _solve(system, second)

    rho = max(MIN_COST_ROUNDING, (8 + degree) * EPS)
    second_low = m2[0] * (1.0 - rho) / ((1.0 + e1) ** 2 * (1.0 + e2))
    second_high = m2[0] * (1.0 + rho) / ((1.0 - e1) ** 2 * (1.0 - e2))
    mean_low, mean_high = bracket(m1[0], e1)
    variance = max(0.0, m2[0] - m1[0] ** 2)
    var_low = max(0.0, second_low - mean_high**2)
    var_high = max(second_high - mean_low**2, variance)
    return (m1[0], mean_low, mean_high), (variance, var_low, var_high), m1


def expected_uses(
    chain: Chain, values: Sequence[float], error: float
) -> dict[int, tuple[float, float, float]]:
    """Expected number of runs started at every input state, as `(value, low, high)`.

    `values` and `error` are the mean cost of every state and its bound from `solve_costs` with the
    real costs. The count at y is `sum_s N_s copies(s, y)` with N the expected visits of every state.
    """
    system = _proper_system(chain)
    if chain.goal[0]:
        return {}
    base = [0.0] * system.size
    base[0] = 1.0
    visits = _sweep(system, system.cols, tuple(reversed(system.comps)), base)

    l1 = 0.0
    for j in system.nodes:
        terms = [visits[s] * coef for s, coef in system.cols[j]]
        residual = base[j] - visits[j] + math.fsum(terms)
        rounding = (len(terms) + 3) * EPS * (base[j] + abs(visits[j]) + math.fsum(abs(t) for t in terms))
        l1 += abs(residual) + rounding
    costs = real_costs(chain)
    if error < 1.0:
        kappa = max(values[i] for i in system.nodes) / (1.0 - error) / min(costs[i] for i in system.nodes)
        slack = kappa * l1
    else:
        slack = math.inf

    users: dict[int, list[tuple[int, int]]] = {}
    for s in system.nodes:
        for y, copies in Counter(chain.inputs[s]).items():
            users.setdefault(y, []).append((s, copies))
    uses = {}
    for y in sorted(users):
        value = math.fsum(visits[s] * copies for s, copies in users[y])
        spread = max(copies for _, copies in users[y]) * slack
        relative = max(MIN_COUNT_ROUNDING, (len(users[y]) + 3) * EPS) * value
        uses[y] = (value, max(0.0, value - spread - relative), value + spread + relative)
    return uses


def _branching(chain: Chain, system: _System) -> bool:
    return any(
        system.comp_of[y] >= 0 and system.comp_of[y] == system.comp_of[s]
        for s in system.nodes
        for y in chain.inputs[s]
    )


def branching(chain: Chain) -> bool:
    """True when some input edge lies inside a strongly connected component of the dependency graph.

    A component that feeds itself through an input (donors that need each other, an output recycled as
    a donor, an action that lists its own state) makes the cost of an attempt depend on a run of the
    same component; the dependency graph is made of the outcome edges of the states that can finish
    and the input edges of every expanded state.
    """
    return _branching(chain, _system(chain))


def input_starts_in_order(chain: Chain) -> list[int]:
    """The distinct input states, ordered so that a run's own inputs are listed before the run.

    If the run from y reaches (through outcomes) a state that uses input y', then y' comes before y.
    Inputs that are goals or stuck come first. Raises `ValueError` for a branching chain, which has no
    such order.
    """
    system = _system(chain)
    if _branching(chain, system):
        raise ValueError("inputs that feed themselves have no order")
    wanted = {y for ins in chain.inputs for y in ins}
    order = sorted(y for y in wanted if system.comp_of[y] < 0)
    for comp in system.comps:
        order.extend(sorted(y for y in comp if y in wanted))
    return order
