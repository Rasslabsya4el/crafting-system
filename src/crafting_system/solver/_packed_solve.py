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
from time import perf_counter as _tick  # for the seconds in `info`: the clock the progress lines read is `time.perf_counter`, which a test replaces
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from ._certify import ConvergenceError
from ._packed import PackedGraph, expand_ranges, kernel_any, kernel_min, kernel_sums
from ._packed_merge import exact_classes, identity_classes, quotient

EPS = sys.float_info.epsilon
INF = math.inf
ACCEPT_BOUND = 1e-6  # a certified relative bound above this raises `ConvergenceError` (the rounding of long sums gives 5e-8 on R04, 7e-8 on S02)
DENSE_LIMIT = 1500  # policies of at most this many states are evaluated by a dense solve, larger ones by BiCGSTAB
CHUNK_EDGES = 4_000_000
HEAVY_SELF = 0.5  # an action whose kernel puts more than this chance on its own state is summed edge by edge: taking the own term off a shared sum would lose digits
SHARE_MIN = 64  # a kernel with fewer edges than this is summed edge by edge for the action too (nothing to save), as the own term of its shared sum would be a rounding


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

    def __init__(self, graph: PackedGraph, self_mass: np.ndarray | None = None) -> None:
        self.g = graph
        self._self_mass = self_mass
        self._edgewise: np.ndarray | None = None
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


    @property
    def self_mass(self) -> np.ndarray:
        """For every action: the chance that its kernel gives its own state (0 where the state is not among the successors). A caller that knows it from
        building the kernels passes it to `Work`; otherwise it is found here, edge by edge, once."""
        if self._self_mass is None:
            out = np.zeros(self.A)
            g = self.g
            for a0, a1 in self.action_chunks():
                sizes = self.asize[a0:a1]
                idx = expand_ranges(g.k_ptr[g.act_kernel[a0:a1]], sizes)
                own = g.k_succ[idx] == np.repeat(self.act_state[a0:a1], sizes)
                out[a0:a1] = np.add.reduceat(np.where(own, g.k_prob[idx], 0.0), self.cum[a0:a1] - self.cum[a0])
            self._self_mass = out
        return self._self_mass

    @property
    def edgewise(self) -> np.ndarray:
        """The actions whose sum over the successors other than the state is made edge by edge: the kernel puts more than `HEAVY_SELF` on the state, or
        has fewer than `SHARE_MIN` edges and puts something on it. The sum of every other action is its kernel's, shared (less the own term if any)."""
        if self._edgewise is None:
            mass = self.self_mass
            self._edgewise = (mass > 0.0) & ((mass > HEAVY_SELF) | (self.asize < SHARE_MIN)) if self.A else np.zeros(0, dtype=bool)
        return self._edgewise

    def edgewise_sums(self, actions: np.ndarray, f: np.ndarray) -> np.ndarray:
        """`nonself_sums(f)` of the given actions only, in the order given."""
        g = self.g
        sizes_all = self.asize[actions]
        cum = np.concatenate(([0], np.cumsum(sizes_all))).astype(np.int64)
        out = np.empty(len(actions))
        a0 = 0
        while a0 < len(actions):
            a1 = int(np.searchsorted(cum, cum[a0] + CHUNK_EDGES, side="right")) - 1
            a1 = min(max(a1, a0 + 1), len(actions))
            chosen = actions[a0:a1]
            sizes = sizes_all[a0:a1]
            idx = expand_ranges(g.k_ptr[g.act_kernel[chosen]], sizes)
            dst = g.k_succ[idx]
            terms = g.k_prob[idx] * f[dst]
            terms[dst == np.repeat(self.act_state[chosen], sizes)] = 0.0
            out[a0:a1] = np.add.reduceat(terms, cum[a0:a1] - cum[a0])
            a0 = a1
        return out

    def shared_sums(self, f: np.ndarray) -> np.ndarray:
        """`nonself_sums(f)` with each kernel summed once, however many actions share it (R04: a reroll's thousands of outcomes are one kernel for every
        state of a key). An action whose kernel holds its own state has the own term taken off the shared sum, unless `edgewise` says to sum it as
        `nonself_sums` does. Equal to `nonself_sums` to the rounding of the sums (the own term is at most `HEAVY_SELF` of the kernel)."""
        if not self.A:
            return np.empty(0)
        out = kernel_sums(self.g, f)[self.g.act_kernel]
        mass = self.self_mass
        light = np.flatnonzero((mass > 0.0) & ~self.edgewise)
        if len(light):
            out[light] -= mass[light] * f[self.act_state[light]]
        wise = np.flatnonzero(self.edgewise)
        if len(wise):
            out[wise] = self.edgewise_sums(wise, f)
        return out


def _settled(certificate: Certificate, tolerance: float) -> bool:
    """Whether the residual is within `tolerance` of the cheapest cost, or at the rounding floor: more evaluation cannot help."""
    return certificate.residual <= tolerance or certificate.at_floor


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


def reaches_goal(work: Work, policy: np.ndarray) -> np.ndarray:
    """The states that reach a goal with positive chance under `policy` (-1: no action): a goal reaches itself, a state with no action only if it is one.

    Reverse search from the goals over the kernels the policy uses (each once, however many states share it), so a pass costs the edges of the distinct
    kernels and not those of every state.
    """
    g, n = work.g, work.n
    reached = g.goal.copy()
    states = np.flatnonzero(policy >= 0)
    if not len(states):
        return reached
    kernels, slot = np.unique(g.act_kernel[policy[states]], return_inverse=True)
    sizes = work.ksize[kernels]
    dst = g.k_succ[expand_ranges(g.k_ptr[kernels], sizes)]
    owner = np.repeat(np.arange(len(kernels)), sizes)
    by_dst = np.argsort(dst, kind="stable")
    owner_of = owner[by_dst]
    edge_ptr = np.searchsorted(dst[by_dst], np.arange(n + 1))  # the edges into state s: edge_ptr[s]:edge_ptr[s + 1] of `owner_of`
    by_slot = np.argsort(slot, kind="stable")
    user_ptr = np.searchsorted(slot[by_slot], np.arange(len(kernels) + 1))  # the states using kernel k: by_slot[user_ptr[k]:user_ptr[k + 1]]
    seen = np.zeros(len(kernels), dtype=bool)
    frontier = np.flatnonzero(reached)
    while len(frontier):
        into = expand_ranges(edge_ptr[frontier], edge_ptr[frontier + 1] - edge_ptr[frontier])
        hit = np.unique(owner_of[into])
        hit = hit[~seen[hit]]
        seen[hit] = True
        users = states[by_slot[expand_ranges(user_ptr[hit], user_ptr[hit + 1] - user_ptr[hit])]]
        frontier = users[~reached[users]]
        reached[frontier] = True
    return reached


def warm_policy(
    work: Work, alive: np.ndarray, effective: np.ndarray, start: np.ndarray, info: dict, value: np.ndarray | None = None, leave: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`(inside, ok, policy)` from a policy given for the states (an action index of this graph, or -1), proved proper on `inside`.

    Where the given policy has no action for a state (or one of another state, or one that leaves the states with a proper policy), the action that is
    cheapest under `value` is taken, if `value` is given: the last round's values name the action that the state is going to take far more often than the cheapest
    path's does. That is a guess like the rest of the start. Then the policy is proved proper, as a finite Markov chain's properness is: every state reaches
    the goal with certainty iff every state reaches it with positive chance (otherwise some closed class holds no goal), and the policy's actions stay inside the
    set. So:

    1. The states `inside0` that have an alive action (and the goals) are the only candidates for Y, the set of states with a proper policy. If the
       policy, taken where its action stays inside `inside0`, reaches the goal from every one of them, it is proper on `inside0`, so `inside0` is Y and no
       search for Y is needed. This is the case that a warm start is for.
    2. Otherwise Y is found as `proper_states` finds it, and the policy is kept at the states of Y that reach the goal under it with positive chance; at every
       other state of Y the policy is replaced by the cheapest path's, which lowers the path cost to the goal with positive chance at each step. The result is
       proper: a state that kept its action still reaches the goal by the states that reach it (they all kept theirs); a replaced state follows the strictly
       falling cheapest-path costs until it meets a state that kept its action or the goal. (The mix of two policies that is not proper is the one that is not
       checked: this one is.)

    `info["warm"]` says which: "kept" (1), or "repaired" with `info["warm_replaced"]` the number of states whose action was not the guess (2).
    """
    g = work.g
    own = work.act_state
    has_alive = np.zeros(work.n, dtype=bool)
    has_alive[own[alive]] = True
    asked = (start >= 0) & (start < work.A)
    asked[asked] = own[start[asked]] == np.flatnonzero(asked)  # an action of another state is no action of this one
    sums = None if value is None or leave is None else work.shared_sums(np.where(np.isfinite(value), value, 0.0))

    def given(ok: np.ndarray, inside: np.ndarray) -> np.ndarray:
        kept = asked & inside & ~g.goal
        kept[kept] = ok[start[kept]]
        policy = np.where(kept, start, -1)
        if sums is not None and (inside & ~g.goal & (policy < 0)).any():
            q = np.where(ok, (g.act_cost + sums) / np.where(alive, leave, 1.0), INF)
            best = work.state_min(q)
            cheapest_now = work.state_argmin(q, best)
            cheapest_now[~np.isfinite(best) | ~inside | g.goal] = -1
            policy = np.where(policy >= 0, policy, cheapest_now)
        return policy

    inside = g.goal | has_alive
    ok = alive & ~kernel_any(g, ~inside)[g.act_kernel]
    policy = given(ok, inside)
    wanted = inside & ~g.goal
    if reaches_goal(work, policy)[wanted].all():
        info["warm"] = "kept"
        return inside, ok, policy
    inside, ok, _, cheapest = proper_states(work, alive, effective)
    kept = given(ok, inside)
    policy = np.where(kept >= 0, kept, cheapest)
    stuck = inside & ~g.goal & ~reaches_goal(work, policy)
    info["warm"] = "repaired"
    info["warm_replaced"] = int((inside & ~g.goal & ((kept < 0) | stuck)).sum())
    return inside, ok, np.where(stuck, cheapest, policy)


# ---- evaluating a policy ---------------------------------------------------------------------------------------------


STAGNATION = 400  # BiCGSTAB iterations without the best residual halving after which the run stops and returns its best iterate
BICGSTAB_ITERATIONS = 4_000  # per run (the research solve of #312 used 4,000 and converged on R04 and R14)
BICGSTAB_RESTARTS = 3  # further runs from the best iterate when one did not reach the tolerance
DENSE_FALLBACK = 6_000  # policies of at most this many states fall back to the dense solve when BiCGSTAB did not converge
DENSE_FALLBACK_RESIDUAL = 1e-10


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
    """The values of the proper `policy` (action index per state, -1 for the states outside): a full-length vector.

    The system is `x[s] - sum over t != s of (p[s, t] / leave[s]) x[t] = cost[s] / leave[s]`. A dense solve takes it as it is. For BiCGSTAB the product
    `sum p[s, t] x[t]` is made once for each distinct kernel the policy uses, not once for each state (the states of one key share the kernel of a
    reroll with its thousands of outcomes), less the own term for a state that is among its kernel's successors; the states `Work.edgewise` names,
    whose own term is too large to take off a sum, keep their edges.
    """
    g = work.g
    states = np.flatnonzero(policy >= 0)
    m = len(states)
    values = np.zeros(work.n)
    if m == 0:
        return values
    chosen = policy[states]
    position = np.full(work.n, m, dtype=np.int64)
    position[states] = np.arange(m)
    rhs = g.act_cost[chosen] / leave[chosen]

    def rows(picked: np.ndarray):
        """For the policy's states `picked` (indexes into `states`): the edges each keeps, as (offsets, columns, weights)."""
        kernels = g.act_kernel[chosen[picked]]
        sizes = work.ksize[kernels]
        idx = expand_ranges(g.k_ptr[kernels], sizes)
        dst = g.k_succ[idx]
        weight = g.k_prob[idx] / np.repeat(leave[chosen[picked]], sizes)
        weight[dst == np.repeat(states[picked], sizes)] = 0.0
        return np.concatenate(([0], np.cumsum(sizes)[:-1])), position[dst], weight, sizes

    def dense() -> np.ndarray:
        _, column, weight, sizes = rows(np.arange(m))
        row = np.repeat(np.arange(m), sizes)
        inside = column < m
        matrix = np.bincount(row[inside] * m + column[inside], weights=weight[inside], minlength=m * m).reshape(m, m)
        matrix = np.eye(m) - matrix
        try:
            found = np.linalg.solve(matrix, rhs)
            for _ in range(2):  # iterative refinement: a stiff system loses digits in one solve
                residual = rhs - matrix @ found
                if not np.max(np.abs(residual)) > 4 * EPS * np.max(np.abs(rhs)):
                    break
                found = found + np.linalg.solve(matrix, residual)
        except np.linalg.LinAlgError as error:
            raise ConvergenceError("the policy is improper: its linear system is singular", INF) from error
        info["linear_dense"] = info.get("linear_dense", 0) + 1
        return found

    if m <= dense_limit:
        solved = dense()
    else:
        wise = work.edgewise[chosen]
        by_edges = np.flatnonzero(wise)
        shared = np.flatnonzero(~wise)
        kernels, slot = np.unique(g.act_kernel[chosen[shared]], return_inverse=True)
        sizes = work.ksize[kernels]
        idx = expand_ranges(g.k_ptr[kernels], sizes)
        shared_column = position[g.k_succ[idx]]
        shared_prob = g.k_prob[idx]
        shared_offsets = np.concatenate(([0], np.cumsum(sizes)[:-1]))
        own = work.self_mass[chosen[shared]]
        divisor = leave[chosen[shared]]
        edge_offsets, edge_column, edge_weight, _ = rows(by_edges)
        extended = np.zeros(m + 1)

        def matvec(x: np.ndarray) -> np.ndarray:
            info["matvecs"] = info.get("matvecs", 0) + 1
            extended[:m] = x
            out = x.copy()
            if len(shared):
                out[shared] -= (np.add.reduceat(shared_prob * extended[shared_column], shared_offsets)[slot] - own * x[shared]) / divisor
            if len(by_edges):
                out[by_edges] -= np.add.reduceat(edge_weight * extended[edge_column], edge_offsets)
            return out

        solved, residual, iterations = _bicgstab(matvec, rhs, start[states], tol, BICGSTAB_ITERATIONS)
        for _ in range(BICGSTAB_RESTARTS):  # a stalled run starts again from its best iterate with a fresh recurrence
            if residual <= 10 * tol:
                break
            solved, residual, more = _bicgstab(matvec, rhs, solved, tol, BICGSTAB_ITERATIONS)
            iterations += more
        info["linear_iterations"] = info.get("linear_iterations", 0) + iterations
        info["linear_residual"] = residual
        info["policy_states"], info["policy_edges"], info["shared_edges"] = m, len(edge_weight), len(shared_prob)
        if residual > DENSE_FALLBACK_RESIDUAL and m <= DENSE_FALLBACK:  # a stiff system: the dense solve is slow but sure
            solved = dense()
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
    accept_bound: float = ACCEPT_BOUND,
    progress: Callable[[str], None] | None = None,
    info: dict | None = None,
    start_policy: np.ndarray | None = None,
    start_value: np.ndarray | None = None,
    self_mass: np.ndarray | None = None,
) -> Core:
    """Policy iteration on `graph` itself (no merge): see the module docstring, steps 2 to 5.

    `start_policy` (an action index of the graph for each state, -1 where none) and `start_value` (a vector of values to start the first evaluation
    from) warm-start the iteration with those of a nearby graph, as the envelope search does round after round. The policy need not be proper on this
    graph: `warm_policy` keeps it where it is and replaces it where it is not, and proves the result proper. The answer does not depend on the start
    (the same fixed point, to the certified error), only the work. `self_mass[a]` is the chance that action `a`'s kernel gives the state of `a` (see
    `Work.self_mass`), for a caller that knows it from building the kernels.
    """
    say = progress or (lambda _text: None)
    info = {} if info is None else info
    began = time.perf_counter()
    clock = _tick()
    work = Work(graph, self_mass)
    n = work.n
    info["seconds_work"] = _tick() - clock
    if not work.A:  # nothing can be done anywhere: the goals cost nothing and the rest never finish
        solved = graph.goal.copy()
        return Core(np.where(solved, 0.0, INF), solved, np.full(n, -1, dtype=np.int64), Certificate(0.0, 1.0, 1.0, 0.0, True))
    leave = work.shared_sums(np.ones(n))
    alive = leave > 0.0
    with np.errstate(divide="ignore"):
        effective = np.where(alive, graph.act_cost / np.where(alive, leave, 1.0), INF)
    mark = _tick()
    if start_policy is None:
        inside, ok, distance, policy = proper_states(work, alive, effective)
        value = np.where(inside, np.where(np.isfinite(distance), distance, 0.0), 0.0)
    else:
        inside, ok, policy = warm_policy(work, alive, effective, np.asarray(start_policy), info, start_value, leave)
        value = np.zeros(n) if start_value is None else np.where(inside & np.isfinite(start_value), start_value, 0.0)
    info["seconds_proper"] = _tick() - mark
    say(f"proper states: {int(inside.sum()):,} of {n:,} ({time.perf_counter() - began:.1f} s)")
    terms = work.state_reduce(np.maximum, work.asize.astype(np.float64) + 1.0, 0.0)
    noise = (terms + 2.0) * EPS
    rounds = 0
    while rounds < max_rounds:
        rounds += 1
        mark = _tick()
        value = evaluate_policy(work, leave, policy, value, dense_limit, 1e-13, info)
        info["seconds_evaluate"] = info.get("seconds_evaluate", 0.0) + _tick() - mark
        mark = _tick()
        sums = work.shared_sums(value)
        q = np.where(ok, (graph.act_cost + sums) / np.where(alive, leave, 1.0), INF)
        best = work.state_min(q)
        current = np.where(policy >= 0, q[np.maximum(policy, 0)], 0.0)
        better = (policy >= 0) & (best < current - noise * current)
        say(f"policy iteration {rounds}: {int(better.sum()):,} states improve ({time.perf_counter() - began:.1f} s)")
        info["seconds_improve"] = info.get("seconds_improve", 0.0) + _tick() - mark
        if not better.any():
            break
        policy = np.where(better, work.state_argmin(q, best), policy)
    info["rounds"] = rounds
    mark = _tick()
    certificate = certify(graph, value, inside, work)
    info["seconds_certify"] = _tick() - mark
    refinements = 0
    while not _settled(certificate, tolerance) and refinements < 3:
        refinements += 1
        value = evaluate_policy(work, leave, policy, value, dense_limit, 1e-15, info)
        certificate = certify(graph, value, inside, work)
    info["refinements"] = refinements
    if not certificate.bound <= accept_bound:  # also false for an infinite or undefined bound
        raise ConvergenceError(
            f"the policy iteration on {n:,} states certifies only a relative bound of {certificate.bound:.3g} "
            f"(asked: tolerance {tolerance}, accepted: {accept_bound}; residual {certificate.residual:.3g} of the cheapest cost)",
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
    accept_bound: float = ACCEPT_BOUND,
    merge: bool = True,
    progress: Callable[[str], None] | None = None,
) -> PackedSolution:
    """Minimise the mean cost to a goal from every state of `graph`: merged exactly, solved, certified on the unmerged graph.

    `tolerance` is the stopping threshold on the residual of the Bellman operator relative to the cheapest action of a state
    (as `solve`'s): the evaluation of the policy is refined while it is above it and not at the rounding floor. The certified
    bound of the result (`error_bound`) may exceed `tolerance` by the rounding of the sums, but a bound above `accept_bound`
    (or none) raises `ConvergenceError`.
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
    core = solve_graph(
        reduced, tolerance=tolerance, dense_limit=dense_limit, max_rounds=max_rounds, accept_bound=accept_bound, progress=say, info=info
    )
    info["solve_seconds"] = round(time.perf_counter() - mark, 2)
    cls = classes.cls
    value = core.value[cls]
    solved = core.solved[cls]
    mark = time.perf_counter()
    certificate = certify(graph, value, solved)
    info["certify_seconds"] = round(time.perf_counter() - mark, 2)
    info["quotient_bound"] = core.certificate.bound
    if not certificate.bound <= accept_bound:
        raise ConvergenceError(
            f"the values of the merged graph do not satisfy the Bellman equation of the whole graph to {accept_bound} "
            f"(bound {certificate.bound:.3g}, residual {certificate.residual:.3g} of the cheapest cost): the merge or the solve is wrong",
            certificate.bound,
        )
    say(f"certificate on the whole graph: bound {certificate.bound:.3g} ({info['certify_seconds']} s)")
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
