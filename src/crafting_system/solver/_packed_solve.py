"""The packed solve: policy iteration on a packed graph, merged exactly first, certified at the end (ticket #374).

`solve_packed(graph)` is the solve of `research/312/prune_analysis.py` made a product piece (ADR-0063 point 1):

1. MERGE. The exact classes of the graph (`_packed_merge`) and the quotient, one state per class.
2. PROPER STATES. A state has a finite value only if some policy reaches the goal with certainty. The set Y of such states
   is the greatest set in which every state has an action whose outcomes all lie in Y and from which the goal is reached:
   found by shortest-path sweeps over the actions that stay in Y, shrinking Y until it is stable.
3. START POLICY. The sweeps also give each state of Y the cost of its luckiest path to the goal; the action that starts
   the cheapest such path lowers that distance with positive chance in every step, so the policy is proper.
4. POLICY ITERATION. Each action has its self-loop compiled out (`cost / leave`, outcomes renormalised, as the object
   solver does: no `1 - p` in floats). A policy is evaluated by one linear solve: dense up to `dense_limit` states of the
   policy, else BiCGSTAB; then every state takes the action of least Q, an action replacing the current one only when it
   is better by more than the rounding of the sum (so the iteration cannot cycle on noise).
5. CERTIFICATE. `certify` computes, on the graph as given and for the candidate values, the residuals of the Bellman
   operator and from them the relative error bound of `solver/_certify.py`, here per state: with g(s) the cheapest
   action cost at s, k(s) the cost of the greedy action, e(s) = (TV - V)+ and d(s) = (V - TV)+ (each widened by the
   float64 rounding of the sum, (m + 2) eps of it, m the terms of the sum), the values satisfy
   a_lo V <= V* <= a_hi V with a_lo = min g/(g + d) and a_hi = max k/(k - e) (infinite when some e >= k).
   The operator is the one WITHOUT the self-loop compiled out, so the certificate is also an independent check of the
   merge and of the solve: it is run on the unmerged graph with the class values copied back to the members.

The bound may exceed `tolerance` when the values are large next to the cheapest action (rounding amplification, as in
`_certify.py`); the loop stops when the residuals reach the tolerance or the rounding floor.
"""

import math
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from ._certify import ConvergenceError
from ._packed import PackedGraph, expand_ranges, kernel_any, kernel_min, kernel_sums
from ._packed_merge import exact_classes, identity_classes, quotient

EPS = sys.float_info.epsilon
INF = math.inf
DENSE_LIMIT = 1500  # policies of at most this many states are evaluated by a dense solve, larger ones by BiCGSTAB
CHUNK_EDGES = 4_000_000


@dataclass(frozen=True, slots=True)
class Certificate:
    """What `certify` found: `bound` is the relative error of the values (infinite when no upper side could be shown)."""

    bound: float
    lower: float
    upper: float
    residual: float  # max over states of max(e, d) / g, rounding allowance not included
    at_floor: bool  # every residual is within the rounding allowance of its state


@dataclass(frozen=True, slots=True, eq=False)
class PackedSolution:
    """What `solve_packed` returns, all in the numbering of the graph given.

    `value[s]`: the expected remaining cost of state `s` (0 for goals, infinity for states with no proper policy).
    `action[s]`: the index of the action of `s` in the graph that the policy takes (-1 for goals and dead states); it is
    the cheapest action of `s` whose distribution over classes is the one chosen for the class of `s`.
    `error_bound`: the certified relative bound (see the module docstring).
    `classes`, `quotient`, `cls`, `class_action`: the merge (`class_action[c]` is an action index of `quotient`).
    `info`: counts and seconds for a report.
    """

    value: np.ndarray
    action: np.ndarray
    error_bound: float
    classes: int
    quotient: PackedGraph
    cls: np.ndarray
    class_action: np.ndarray
    info: dict = field(default_factory=dict)


class Work:
    """Arrays derived once from a graph and shared by the passes."""

    def __init__(self, graph: PackedGraph) -> None:
        self.g = graph
        self.n = graph.n
        self.A = graph.num_actions
        self.act_state = graph.action_state()
        self.ksize = graph.kernel_sizes()
        self.asize = self.ksize[graph.act_kernel] if self.A else np.zeros(0, dtype=np.int64)
        self.cum = np.concatenate(([0], np.cumsum(self.asize))).astype(np.int64)
        self.has = np.diff(graph.act_ptr) > 0
        self.rows = graph.act_ptr[:-1][self.has]

    def state_reduce(self, ufunc, per_action: np.ndarray, empty: float) -> np.ndarray:
        out = np.full(self.n, empty)
        if self.A:
            out[self.has] = ufunc.reduceat(per_action, self.rows)
        return out

    def state_min(self, per_action: np.ndarray) -> np.ndarray:
        return self.state_reduce(np.minimum, per_action, INF)

    def state_argmin(self, per_action: np.ndarray, best: np.ndarray) -> np.ndarray:
        """The first action of every state that reaches `best` (-1 for a state without actions)."""
        out = np.full(self.n, -1, dtype=np.int64)
        if self.A:
            hit = np.where(per_action == best[self.act_state], np.arange(self.A), self.A)
            found = np.minimum.reduceat(hit, self.rows)
            found[found >= self.A] = -1
            out[self.has] = found
        return out

    def action_chunks(self):
        a0 = 0
        while a0 < self.A:
            a1 = int(np.searchsorted(self.cum, self.cum[a0] + CHUNK_EDGES, side="right")) - 1
            a1 = min(max(a1, a0 + 1), self.A)
            yield a0, a1
            a0 = a1

    def nonself_sums(self, f: np.ndarray) -> np.ndarray:
        """For every action: the sum of `prob * f[successor]` over the successors other than its own state."""
        g = self.g
        out = np.empty(self.A)
        for a0, a1 in self.action_chunks():
            kernels = g.act_kernel[a0:a1]
            sizes = self.asize[a0:a1]
            idx = expand_ranges(g.k_ptr[kernels], sizes)
            dst = g.k_succ[idx]
            terms = g.k_prob[idx] * f[dst]
            terms[dst == np.repeat(self.act_state[a0:a1], sizes)] = 0.0
            out[a0:a1] = np.add.reduceat(terms, self.cum[a0:a1] - self.cum[a0])
        return out


def certify(graph: PackedGraph, value: np.ndarray, solved: np.ndarray, work: Work | None = None) -> Certificate:
    """The certificate of the module docstring for candidate `value` on the states `solved` (the others are dead)."""
    work = work or Work(graph)
    n, goal = work.n, graph.goal
    targets = ~goal & solved
    if not targets.any():
        return Certificate(0.0, 1.0, 1.0, 0.0, True)
    v = np.where(solved, value, 0.0)
    bad = kernel_any(graph, ~solved)
    ok = ~bad[graph.act_kernel]
    sums = kernel_sums(graph, v)
    q = np.where(ok, graph.act_cost + sums[graph.act_kernel], INF)
    tv = work.state_min(q)
    if not np.all(np.isfinite(tv[targets])):
        return Certificate(INF, 0.0, INF, INF, False)
    greedy = work.state_argmin(q, tv)
    k_mu = np.where(greedy >= 0, graph.act_cost[np.maximum(greedy, 0)], 1.0)
    g = work.state_min(np.where(ok, graph.act_cost, INF))
    terms = work.state_reduce(np.maximum, np.where(ok, work.asize + 1, 0).astype(np.float64), 0.0)
    rho = (terms + 2.0) * EPS
    delta = rho / (1.0 - rho) * np.where(np.isfinite(tv), tv, 0.0)
    e0 = np.maximum(tv - v, 0.0)[targets]
    d0 = np.maximum(v - tv, 0.0)[targets]
    delta, g, k_mu = delta[targets], g[targets], k_mu[targets]
    e, d = e0 + delta, d0 + delta
    lower = float(np.min(g / (g + d)))
    upper = INF if np.any(e >= k_mu) else float(np.max(k_mu / (k_mu - e)))
    bound = max(1.0 - lower, upper - 1.0)
    residual = float(np.max(np.maximum(e0, d0) / g))
    return Certificate(bound, lower, upper, residual, bool(np.all(np.maximum(e0, d0) <= delta)))


# ---- proper states and the start policy -----------------------------------------------------------------------------


def proper_states(work: Work, alive: np.ndarray, effective: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """`(Y, ok, distance, policy)`: the states with a proper policy, the actions that stay in Y, the luckiest-path costs, a proper policy."""
    g = work.g
    inside = np.ones(work.n, dtype=bool)
    while True:
        stray = kernel_any(g, ~inside)
        ok = alive & ~stray[g.act_kernel]
        cost = np.where(ok, effective, INF)
        distance = np.where(g.goal, 0.0, INF)
        while True:
            lowest = kernel_min(g, distance)
            candidate = cost + lowest[g.act_kernel]
            best = work.state_min(candidate)
            nearer = np.minimum(distance, best)
            if np.array_equal(nearer, distance):
                break
            distance = nearer
        found = np.isfinite(distance) & inside
        if np.array_equal(found, inside):
            break
        inside = found
    policy = work.state_argmin(candidate, best)
    policy[g.goal | ~inside | ~np.isfinite(best)] = -1
    return inside, ok, distance, policy


# ---- evaluating a policy ---------------------------------------------------------------------------------------------


STAGNATION = 150  # BiCGSTAB iterations without the residual halving after which the solve gives up and returns its best iterate


def _bicgstab(matvec: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x0: np.ndarray, tol: float, max_iter: int):
    """BiCGSTAB for `matvec(x) = b`: returns `(x, relative residual, iterations)`; the best iterate seen."""
    with np.errstate(all="ignore"):
        return _bicgstab_run(matvec, b, x0, tol, max_iter)


def _bicgstab_run(matvec, b, x0, tol, max_iter):
    x = x0.copy()
    r = b - matvec(x)
    bnorm = max(float(np.linalg.norm(b)), 1e-300)
    rnorm = float(np.linalg.norm(r))
    best_x, best = x.copy(), rnorm
    r_hat = r.copy()
    rho = alpha = omega = 1.0
    v = np.zeros_like(b)
    p = np.zeros_like(b)
    it = since = 0
    marked = rnorm
    while it < max_iter and rnorm > tol * bnorm:
        it += 1
        since += 1
        if best < 0.5 * marked:
            marked, since = best, 0
        elif since >= STAGNATION:
            break
        rho_new = float(r_hat @ r)
        if rho_new == 0.0 or omega == 0.0:  # breakdown: restart the recurrence from the current iterate
            r_hat, rho, alpha, omega = r.copy(), 1.0, 1.0, 1.0
            v[:] = 0.0
            p[:] = 0.0
            rho_new = float(r_hat @ r)
            if rho_new == 0.0:
                break
        beta = (rho_new / rho) * (alpha / omega)
        p = r + beta * (p - omega * v)
        v = matvec(p)
        denominator = float(r_hat @ v)
        if denominator == 0.0:
            omega = 0.0
            continue
        alpha = rho_new / denominator
        s = r - alpha * v
        if float(np.linalg.norm(s)) <= tol * bnorm:
            x = x + alpha * p
            r = s
            rnorm = float(np.linalg.norm(r))
            if rnorm < best:
                best_x, best = x.copy(), rnorm
            break
        t = matvec(s)
        tt = float(t @ t)
        if tt == 0.0:
            x = x + alpha * p
            r = s
            rnorm = float(np.linalg.norm(r))
            if rnorm < best:
                best_x, best = x.copy(), rnorm
            break
        omega = float(t @ s) / tt
        x = x + alpha * p + omega * s
        r = s - omega * t
        rho = rho_new
        rnorm = float(np.linalg.norm(r))
        if rnorm < best:
            best_x, best = x.copy(), rnorm
    return best_x, best / bnorm, it


def evaluate_policy(
    work: Work, leave: np.ndarray, policy: np.ndarray, start: np.ndarray, dense_limit: int, tol: float, info: dict
) -> np.ndarray:
    """The values of the proper `policy` (action index per state, -1 for the states outside): a full-length vector."""
    g = work.g
    states = np.flatnonzero(policy >= 0)
    m = len(states)
    values = np.zeros(work.n)
    if m == 0:
        return values
    chosen = policy[states]
    kernels = g.act_kernel[chosen]
    sizes = work.ksize[kernels]
    idx = expand_ranges(g.k_ptr[kernels], sizes)
    dst = g.k_succ[idx]
    weight = g.k_prob[idx] / np.repeat(leave[chosen], sizes)
    weight[dst == np.repeat(states, sizes)] = 0.0
    rhs = g.act_cost[chosen] / leave[chosen]
    position = np.full(work.n, m, dtype=np.int64)
    position[states] = np.arange(m)
    column = position[dst]
    if m <= dense_limit:
        row = np.repeat(np.arange(m), sizes)
        inside = column < m
        matrix = np.bincount(row[inside] * m + column[inside], weights=weight[inside], minlength=m * m).reshape(m, m)
        matrix = np.eye(m) - matrix
        try:
            solved = np.linalg.solve(matrix, rhs)
            for _ in range(2):  # iterative refinement: a stiff system loses digits in one solve
                residual = rhs - matrix @ solved
                if not np.max(np.abs(residual)) > 4 * EPS * np.max(np.abs(rhs)):
                    break
                solved = solved + np.linalg.solve(matrix, residual)
        except np.linalg.LinAlgError as error:
            raise ConvergenceError("the policy is improper: its linear system is singular", INF) from error
        info["linear_dense"] = info.get("linear_dense", 0) + 1
    else:
        offsets = np.concatenate(([0], np.cumsum(sizes)[:-1]))
        extended = np.zeros(m + 1)

        def matvec(x: np.ndarray) -> np.ndarray:
            extended[:m] = x
            return x - np.add.reduceat(weight * extended[column], offsets)

        solved, residual, iterations = _bicgstab(matvec, rhs, start[states], tol, 5_000)
        info["linear_iterations"] = info.get("linear_iterations", 0) + iterations
        info["linear_residual"] = residual
    if not np.all(np.isfinite(solved)):
        raise ConvergenceError("the evaluation of a policy did not give finite values", INF)
    values[states] = solved
    return values


# ---- the solve on a graph ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, eq=False)
class Core:
    value: np.ndarray
    solved: np.ndarray
    action: np.ndarray
    certificate: Certificate


def solve_graph(
    graph: PackedGraph,
    *,
    tolerance: float = 1e-10,
    dense_limit: int = DENSE_LIMIT,
    max_rounds: int = 500,
    progress: Callable[[str], None] | None = None,
    info: dict | None = None,
) -> Core:
    """Policy iteration on `graph` itself (no merge): see the module docstring, steps 2 to 5."""
    say = progress or (lambda _text: None)
    info = {} if info is None else info
    began = time.perf_counter()
    work = Work(graph)
    n = work.n
    leave = work.nonself_sums(np.ones(n)) if work.A else np.zeros(0)
    alive = leave > 0.0
    with np.errstate(divide="ignore"):
        effective = np.where(alive, graph.act_cost / np.where(alive, leave, 1.0), INF)
    inside, ok, distance, policy = proper_states(work, alive, effective)
    say(f"proper states: {int(inside.sum()):,} of {n:,} ({time.perf_counter() - began:.1f} s)")
    value = np.where(inside, np.where(np.isfinite(distance), distance, 0.0), 0.0)
    terms = work.state_reduce(np.maximum, work.asize.astype(np.float64) + 1.0, 0.0)
    noise = (terms + 2.0) * EPS
    rounds = 0
    while rounds < max_rounds:
        rounds += 1
        value = evaluate_policy(work, leave, policy, value, dense_limit, 1e-13, info)
        sums = work.nonself_sums(value)
        q = np.where(ok, (graph.act_cost + sums) / np.where(alive, leave, 1.0), INF)
        best = work.state_min(q)
        current = np.where(policy >= 0, q[np.maximum(policy, 0)], 0.0)
        better = (policy >= 0) & (best < current - noise * current)
        say(f"policy iteration {rounds}: {int(better.sum()):,} states improve ({time.perf_counter() - began:.1f} s)")
        if not better.any():
            break
        policy = np.where(better, work.state_argmin(q, best), policy)
    info["rounds"] = rounds
    certificate = certify(graph, value, inside, work)
    refinements = 0
    while not (certificate.residual <= tolerance or certificate.at_floor) and refinements < 3:
        refinements += 1
        value = evaluate_policy(work, leave, policy, value, dense_limit, 1e-15, info)
        certificate = certify(graph, value, inside, work)
    info["refinements"] = refinements
    if not (certificate.residual <= tolerance or certificate.at_floor):
        raise ConvergenceError(
            f"the policy iteration on {n:,} states did not reach the tolerance {tolerance} "
            f"(residual {certificate.residual:.3g} of the cheapest cost)",
            certificate.bound,
        )
    say(f"certificate on the quotient: bound {certificate.bound:.3g} ({time.perf_counter() - began:.1f} s)")
    value = np.where(inside, value, INF)
    return Core(value, inside, np.where(inside & ~graph.goal, policy, -1), certificate)


def solve_packed(
    graph: PackedGraph,
    *,
    tolerance: float = 1e-10,
    dense_limit: int = DENSE_LIMIT,
    max_rounds: int = 500,
    merge: bool = True,
    progress: Callable[[str], None] | None = None,
) -> PackedSolution:
    """Minimise the mean cost to a goal from every state of `graph`: merged exactly, solved, certified on the unmerged graph.

    `tolerance` is the stopping threshold on the residual of the Bellman operator relative to the cheapest action of a state
    (as `solve`'s); raises `ConvergenceError` when the iteration cannot reach it (nor the rounding floor).
    """
    say = progress or (lambda _text: None)
    info: dict = {"states": graph.n, "actions": graph.num_actions, "kernels": graph.num_kernels, "edges_stored": graph.num_edges}
    began = time.perf_counter()
    classes = exact_classes(graph, say) if merge else identity_classes(graph)
    reduced, kernel_map = quotient(graph, classes)
    info.update(
        classes=classes.count, merge_rounds=classes.rounds, merge_seconds=round(time.perf_counter() - began, 2),
        quotient_actions=reduced.num_actions, quotient_edges_stored=reduced.num_edges,
    )
    say(f"merged {graph.n:,} states into {classes.count:,} classes, {reduced.num_actions:,} actions ({info['merge_seconds']} s)")
    mark = time.perf_counter()
    core = solve_graph(reduced, tolerance=tolerance, dense_limit=dense_limit, max_rounds=max_rounds, progress=say, info=info)
    info["solve_seconds"] = round(time.perf_counter() - mark, 2)
    cls = classes.cls
    value = core.value[cls]
    solved = core.solved[cls]
    mark = time.perf_counter()
    certificate = certify(graph, value, solved)
    info["certify_seconds"] = round(time.perf_counter() - mark, 2)
    info["quotient_bound"] = core.certificate.bound
    if not (certificate.residual <= tolerance or certificate.at_floor):
        raise ConvergenceError(
            f"the values of the merged graph do not satisfy the Bellman equation of the whole graph "
            f"(residual {certificate.residual:.3g} of the cheapest cost): the merge or the solve is wrong",
            certificate.bound,
        )
    action = lift_policy(graph, reduced, kernel_map, cls, core.action)
    info["seconds"] = round(time.perf_counter() - began, 2)
    return PackedSolution(value, action, certificate.bound, classes.count, reduced, cls, core.action, info)


def lift_policy(graph: PackedGraph, reduced: PackedGraph, kernel_map: np.ndarray, cls: np.ndarray, class_action: np.ndarray) -> np.ndarray:
    """The action of every state of `graph`: its cheapest action that falls in the distribution chosen for its class."""
    n = graph.n
    out = np.full(n, -1, dtype=np.int64)
    if not graph.num_actions:
        return out
    chosen_class = np.where(class_action >= 0, reduced.act_kernel[np.maximum(class_action, 0)], -1)
    chosen = chosen_class[cls]
    act_state = graph.action_state()
    match = kernel_map[graph.act_kernel] == chosen[act_state]
    cost = np.where(match, graph.act_cost, INF)
    has = np.diff(graph.act_ptr) > 0
    rows = graph.act_ptr[:-1][has]
    best = np.full(n, INF)
    best[has] = np.minimum.reduceat(cost, rows)
    hit = np.where(cost == best[act_state], np.arange(graph.num_actions), graph.num_actions)
    first = np.full(n, graph.num_actions)
    first[has] = np.minimum.reduceat(hit, rows)
    wanted = (chosen >= 0) & np.isfinite(best)
    out[wanted] = first[wanted]
    return out


def policy_reach(graph: PackedGraph, action: np.ndarray, start: int) -> np.ndarray:
    """The states reachable from `start` by the policy `action` (sorted state numbers, `start` and goals included)."""
    seen = np.zeros(graph.n, dtype=bool)
    seen[start] = True
    frontier = np.array([start], dtype=np.int64)
    ksize = graph.kernel_sizes()
    while len(frontier):
        frontier = frontier[action[frontier] >= 0]
        if not len(frontier):
            break
        kernels = np.unique(graph.act_kernel[action[frontier]])  # a kernel is shared by many states: expand it once
        idx = expand_ranges(graph.k_ptr[kernels], ksize[kernels])
        successors = np.unique(graph.k_succ[idx])
        frontier = successors[~seen[successors]].astype(np.int64)
        seen[frontier] = True
    return np.flatnonzero(seen)
