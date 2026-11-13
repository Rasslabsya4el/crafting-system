"""The packed solve: policy iteration on a packed graph, merged exactly first, certified at the end (ticket #374).

`solve_packed(graph)` is the solve of `research/312/prune_analysis.py` made a product piece (ADR-0063 point 1):

1. MERGE. The exact classes of the graph (`_packed_merge`) and the quotient, one state per class.
2. PROPER STATES. A state has a finite value only if some policy reaches the goal with certainty. The set Y of such states
   is the greatest set in which every state has an action whose outcomes all lie in Y and from which the goal is reached:
   found by shortest-path sweeps over the actions that stay in Y, shrinking Y until it is stable.
3. START POLICY. The sweeps also give each state of Y the cost of its luckiest path to the goal; the action that starts
   the cheapest such path lowers that distance with positive chance in every step, so the policy is proper.
4. POLICY ITERATION. Each action has its self-loop compiled out (`cost / leave`, outcomes renormalised, as the object
   solver does: no `1 - p` in floats). A policy is evaluated by the one linear solve of the planner (`_packed_linear.solve`, #841): dense up to
   `dense_limit` states of the policy, else BiCGSTAB to its first stagnation, an answer taken by what bounds its error (its forward estimate), never
   by a residual alone or by the method's own claim (tickets #584, #699). A stiff system, which neither follows, is solved exactly by the cycles of
   the policy's chain (`_packed_chain.ChainSolver`, ticket #621), whatever the number of its states: its cost is the cells of the rows that many
   states share, and a run whose memory does not hold them says so (`info["linear_limit"]`, or `ConvergenceError`) instead of a count of states deciding; then every state takes the action of least Q, an action replacing the current one only when it
   is better by more than the rounding of the sum (so the iteration cannot cycle on noise).
5. CERTIFICATE. `certify` computes, on the graph as given and for the candidate values, the residuals of the Bellman
   operator and from them the relative error bound of `solver/_certify.py`, here per state: with g(s) the cheapest
   action cost at s, k(s) the cost of the greedy action, e(s) = (TV - V)+ and d(s) = (V - TV)+ (each widened by the
   float64 rounding of the sum, (m + 2) eps of it, m the terms of the sum), the values satisfy
   a_lo V <= V* <= a_hi V with a_lo = min g/(g + d) and a_hi = max k/(k - e) (infinite when some e >= k).
   g and k are the margins of h = 0; `certify` also measures d and e against the margins of the cost ahead (ticket #769),
   so that a state whose actions are all free (an unveil, a pick) is measured against the paid step after them and not
   against its own epsilon, which its rounding alone exceeds; each side takes the better of the two. When neither reaches the
   bound asked, it is measured again on the operator with the self-loops divided out, as the solve divides them (`_divided`,
   #585, #841): a state that stays with chance 1 - 1e-12 is then certified to its own condition, not to `1 / leave`.
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

from ._certify import ACCEPT_BOUND, AHEAD_FIRST, AHEAD_LIMIT, AHEAD_WEIGHT, ConvergenceError, lowered, widen  # noqa: F401  (ACCEPT_BOUND, AHEAD_*: read here, by tests, and shared with the object solver, #842)
from ._packed import PackedGraph, expand_ranges, kernel_any, kernel_min, kernel_sums
from . import _packed_linear
from ._packed_chain import ChainSolver
from ._packed_linear import DENSE_LIMIT, backward_error  # noqa: F401  (DENSE_LIMIT: the default of `solve_graph`, read by callers; backward_error: by tests)
from ._packed_merge import exact_classes, identity_classes, quotient

EPS = sys.float_info.epsilon
INF = math.inf
CHUNK_EDGES = 4_000_000
HEAVY_SELF = 0.5  # an action whose kernel puts more than this chance on its own state is summed edge by edge: taking the own term off a shared sum would lose digits
SHARE_MIN = 64  # a kernel with fewer edges than this is summed edge by edge for the action too (nothing to save), as the own term of its shared sum would be a rounding


@dataclass(frozen=True, slots=True)
class Certificate:
    """What `certify` found: `bound` is the relative error of the values (infinite when no upper side could be shown)."""

    bound: float
    lower: float
    upper: float
    residual: float  # max over states of max(e, d) / max(g, the margin of the cost ahead), rounding allowance not included
    at_floor: bool  # every residual is within the rounding allowance of its state
    own_bound: float | None = None  # the bound measured against each state's own cheapest cost alone (h = 0, the certificate before #769)
    own_cost: float | None = None  # the cheapest action cost of the state that sets `own_bound` (a free action's epsilon on R24)
    window: int = 0  # the steps of the cost ahead that the bound given is measured against (0: each state's own cost; -1: the operator with the self-loops divided out, `_divided`)


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


def _own_text(certificate: Certificate) -> str:
    """What the certificate against each state's own cheapest cost alone gives, when that is not the bound given (#769)."""
    if certificate.own_bound is None or certificate.window == 0:
        return ""
    if certificate.window < 0:
        return f" (measured with each action's chance to stay divided out; with it kept: {certificate.own_bound:.3g})"
    return (
        f" (measured against the cost of the next {certificate.window} steps; against each state's own cheapest cost alone: {certificate.own_bound:.3g}, "
        f"set at a state whose cheapest action costs {certificate.own_cost:.3g}; the cost ahead is measured over at most {AHEAD_LIMIT} steps)"
    )


def _settled(certificate: Certificate, tolerance: float) -> bool:
    """Whether the residual is within `tolerance` of its margin (the cheapest cost, or the cost ahead where that is larger), or at the rounding floor: more evaluation cannot help."""
    return certificate.residual <= tolerance or certificate.at_floor


def _shares(error: np.ndarray, margin: np.ndarray, carried: np.ndarray | bool = True) -> np.ndarray:
    """`error / margin` per state, for an error that is at least 0: infinite where the margin is not positive, except where both are 0 and `carried`
    says that is nothing to carry (`error <= t * margin` holds there for every `t`)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        share = error / np.where(margin > 0.0, margin, 1.0)
    return np.where(margin > 0.0, share, np.where((error == 0.0) & (margin == 0.0) & carried, 0.0, INF))


def _sides(d: np.ndarray, e: np.ndarray, gamma: np.ndarray, kappa: np.ndarray, escapes: Callable[[np.ndarray], np.ndarray]) -> tuple[float, float, np.ndarray]:
    """`(lower, upper, share)` of the module docstring for the margins `gamma` (every action) and `kappa` (the greedy one): `lower = 1 / (1 + max d / gamma)`,
    `upper = 1 / (1 - max e / kappa)`; `share` is each state's larger share.

    The upper side also proves the greedy policy proper: `V - h` falls by `kappa - e` a step, so a run spends a finite time where that is positive.
    A state with `e = kappa = 0` (a free action into the goal, value 0) falls by nothing; it is carried only if the policy leads it, with positive
    chance, to the goal or to a state where `kappa > e` (`escapes`, given the states of zero margin); otherwise it may lie in a closed class that
    never finishes (a free cycle with the values 0), and nothing can be said above."""
    zero = (e == 0.0) & (kappa == 0.0)
    low, high = _shares(d, gamma), _shares(e, kappa, escapes(zero) if zero.any() else False)
    t_low, t_high = float(np.max(low)), float(np.max(high))
    lower = 1.0 / (1.0 + t_low) if math.isfinite(t_low) else 0.0
    upper = 1.0 / (1.0 - t_high) if t_high < 1.0 else INF
    return lower, upper, np.maximum(low, high)


def certify(graph: PackedGraph, value: np.ndarray, solved: np.ndarray, work: Work | None = None, wanted: float = ACCEPT_BOUND) -> Certificate:
    """The certificate of the module docstring for candidate `value` on the states `solved` (the others are dead).

    Both sides are measured against a margin. With `h` any vector that is at least 0 and is 0 at the goals and at the states outside `solved`, every
    action `a` of a state `s` satisfies `c_a + P_a h - h[s] >= gamma[s] := (T h - h)[s]`, so for every proper policy `nu`, `(I - P_nu)^-1 gamma <= V^nu - h
    <= V^nu`. A residual `d <= t gamma` then gives `V* >= V / (1 + t)`; on the upper side `kappa := T_mu h - h` of the greedy policy `mu`, with
    `e < kappa` everywhere, proves `mu` proper (`V - h` falls by `kappa - e > 0` a step) and gives `V^mu <= V / (1 - max e / kappa)`. `gamma` and `kappa`
    are taken lowered by the rounding of their sums and of the subtraction, so the inequalities hold of the exact numbers.

    `h = 0` gives `gamma = g` and `kappa = k`, the cost of the cheapest and of the greedy action: the certificate before #769, kept as `own_bound`. It
    fails at a state whose actions are all free (an unveil, a pick: ADR-0026), whose rounding `(m + 2) eps V` alone is far larger than its own epsilon.
    The certificate also takes `h` = the cost ahead (`_ahead`): `w / L` times the sum of the cheapest `j`-step costs `C_j = T^j 0` for `j = 1..L`.
    Since `c_a + P_a C_j >= C_(j+1)`, its margin is at least `(1 - w) c_a + (w / L) (C_(L+1) - g)`: at a free state the paid step ahead, at a paid
    state at least `1 - w` of its own cost. Each side takes the better of the two (both are bounds). The cost ahead is measured only when the own
    cost does not give a bound within `wanted` (the bound the caller accepts), and over the windows of `AHEAD_FIRST` to `AHEAD_LIMIT` steps.
    """
    work = work or Work(graph)
    n, goal = work.n, graph.goal
    targets = ~goal & solved
    if not targets.any():
        return Certificate(0.0, 1.0, 1.0, 0.0, True)
    v = np.where(solved, value, 0.0)
    bad = kernel_any(graph, ~solved)
    ok = ~bad[graph.act_kernel]

    def backup(f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """`(q, Tf)`: every action's cost plus its expected `f` (infinite for an action that may leave the solved states), and their least per state."""
        q = np.where(ok, graph.act_cost + kernel_sums(graph, f)[graph.act_kernel], INF)
        return q, work.state_min(q)

    q, tv = backup(v)
    if not np.all(np.isfinite(tv[targets])):
        return Certificate(INF, 0.0, INF, INF, False)
    greedy = np.maximum(work.state_argmin(q, tv), 0)
    g_all = work.state_min(np.where(ok, graph.act_cost, INF))
    terms = work.state_reduce(np.maximum, np.where(ok, work.asize + 1, 0).astype(np.float64), 0.0)
    rho = (terms + 2.0) * EPS
    grow = rho / (1.0 - rho)  # a computed sum of nonnegative terms is within this share of itself from the exact one
    delta = grow * np.where(np.isfinite(tv), tv, 0.0)
    e0 = np.maximum(tv - v, 0.0)[targets]
    d0 = np.maximum(v - tv, 0.0)[targets]
    e, d = e0 + delta[targets], d0 + delta[targets]
    g, k = g_all[targets], graph.act_cost[greedy][targets]

    policy = np.full(n, -1, dtype=np.int64)
    policy[targets] = greedy[targets]

    def escapes(zero: np.ndarray) -> np.ndarray:
        """Whether each target state of zero margin reaches the goal or a state of positive margin under the greedy policy with positive chance."""
        seeds = goal.copy()
        seeds[np.flatnonzero(targets)[~zero]] = True
        return reaches_goal(work, policy, seeds)[targets]

    _, _, own_share = _sides(d, e, g, k, escapes)
    with np.errstate(divide="ignore", invalid="ignore"):  # h = 0, in the expressions of #374, so that a plan that certified keeps its numbers to the bit
        own_lower = float(np.min(g / (g + d)))
        own_upper = INF if np.any(e >= k) else float(np.max(k / (k - e)))
    own_lower = own_lower if own_lower == own_lower else 0.0  # (0 / 0 at a state of cost 0 and residual 0: no measure, V* >= 0 is all it says)
    own_upper = own_upper if own_upper == own_upper else INF
    step, total, steps = np.where(targets, g_all, 0.0), np.where(targets, g_all, 0.0), 1

    def ahead(window: int) -> np.ndarray:
        """`h` of the window: `w / L` times the cheapest costs of the next 1..L steps, the steps already taken kept."""
        nonlocal step, total, steps
        while steps < window:
            step = np.where(targets, backup(step)[1], 0.0)
            total += step
            steps += 1
        return total * (AHEAD_WEIGHT / window)

    def measure(h: np.ndarray) -> tuple[float, float, int, np.ndarray]:
        qh, th = backup(h)
        r, ht = grow[targets], h[targets]
        gamma, kappa = lowered(th[targets], ht, r), lowered(qh[greedy][targets], ht, r)
        lower, upper, share = _sides(d, e, gamma, kappa, escapes)
        return lower, upper, int(np.sum(~np.isfinite(share))), gamma

    best = widen(ahead, measure, (own_lower, own_upper, g, 0), wanted, min(AHEAD_LIMIT, int(targets.sum())))
    lower, upper, margin, used = best
    bound = max(1.0 - lower, upper - 1.0)
    own_bound = max(1.0 - own_lower, own_upper - 1.0)
    residual = float(np.max(_shares(np.maximum(e0, d0), np.maximum(margin, g))))  # (max(gamma, g) = max(max(gamma, 0), g): g >= 0)
    setter = int(np.argmax(own_share))
    at_floor = bool(np.all(np.maximum(e0, d0) <= delta[targets]))
    if not bound <= wanted:
        divided = _divided(graph, work, v, targets, ok)
        if divided is not None and divided[0] < bound:
            bound, lower, upper, residual, at_floor = divided
            used = -1
    return Certificate(bound, lower, upper, residual, at_floor, own_bound, float(g[setter]), used)


def _divided(graph: PackedGraph, work: Work, v: np.ndarray, targets: np.ndarray, ok: np.ndarray) -> tuple[float, float, float, float, bool] | None:
    """`(bound, lower, upper, residual, at_floor)` of the certificate of `certify` on the operator with every action's self-loop divided out (#585, #841).

    Each action `a` of a state `s` is replaced by the action that repeats it until it leaves `s`: cost `c_a / leave_a`, chances `p_a[s, t] / leave_a`
    for `t != s` (`leave_a`, the chance to leave, a sum of positive terms). Every stationary policy has the same values in both (a run of the one is a
    run of the other with the stays at `s` counted), so the optimum is the same and the bounds of `certify` (`h = 0`) hold of it. The rounding of the
    sum and of `leave_a` is `(2 m + 4) eps` of a backup (`m` its terms), and the margins `c / leave` are taken lowered by it. A state that stays with
    chance `1 - 1e-12` then has a margin of its whole value, not `1e-12` of it: it is certified to its own condition, not to `1 / leave` (the solve
    itself divides the self-loops out the same way). None when no action of a target state leaves it.
    """
    leave = work.shared_sums(np.ones(work.n))
    alive = ok & (leave > 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        cost = np.where(alive, graph.act_cost / np.where(alive, leave, 1.0), INF)
        q = np.where(alive, (graph.act_cost + work.shared_sums(v)) / np.where(alive, leave, 1.0), INF)
    tv = work.state_min(q)
    if not np.all(np.isfinite(tv[targets])):
        return None
    greedy = np.maximum(work.state_argmin(q, tv), 0)
    terms = work.state_reduce(np.maximum, np.where(alive, work.asize + 1, 0).astype(np.float64), 0.0)
    rho = (2.0 * terms + 4.0) * EPS
    grow = rho / (1.0 - rho)
    delta = (grow * tv)[targets]
    e0, d0 = np.maximum(tv - v, 0.0)[targets], np.maximum(v - tv, 0.0)[targets]
    e, d = e0 + delta, d0 + delta
    g = (work.state_min(cost) * (1.0 - grow))[targets]
    k = (cost[greedy] * (1.0 - grow))[targets]
    policy = np.full(work.n, -1, dtype=np.int64)
    policy[targets] = greedy[targets]

    def escapes(zero: np.ndarray) -> np.ndarray:
        seeds = graph.goal.copy()
        seeds[np.flatnonzero(targets)[~zero]] = True
        return reaches_goal(work, policy, seeds)[targets]

    lower, upper, _ = _sides(d, e, g, k, escapes)
    bound = max(1.0 - lower, upper - 1.0)
    residual = float(np.max(_shares(np.maximum(e0, d0), g)))
    return bound, lower, upper, residual, bool(np.all(np.maximum(e0, d0) <= delta))


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


def reaches_goal(work: Work, policy: np.ndarray, seeds: np.ndarray | None = None) -> np.ndarray:
    """The states that reach a goal (or one of `seeds`, when given) with positive chance under `policy` (-1: no action): a goal reaches itself, a state with no action only if it is one.

    Reverse search from the goals over the kernels the policy uses (each once, however many states share it), so a pass costs the edges of the distinct
    kernels and not those of every state.
    """
    g, n = work.g, work.n
    reached = (g.goal if seeds is None else seeds).copy()
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


def policy_terms(work: Work, leave: np.ndarray, chosen: np.ndarray, states: np.ndarray, position: np.ndarray) -> tuple[Callable[[np.ndarray], np.ndarray], dict]:
    """`(T, counts)`: `T(v)[s]` is the sum over the successors `t != s` of the policy's state `s` of `p[s, t] / leave[s] * v[t]` (a successor outside the policy is 0).

    The sum is made once for each distinct kernel the policy uses, not once for each state (the states of one key share the kernel of a reroll with its
    thousands of outcomes), less the own term for a state that is among its kernel's successors; the states `Work.edgewise` names, whose own term is too
    large to take off a sum, keep their edges. `counts` are the edges held (`policy_edges`, `shared_edges`).
    """
    g, m = work.g, len(states)
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
    kernels_e = g.act_kernel[chosen[by_edges]]
    sizes_e = work.ksize[kernels_e]
    idx_e = expand_ranges(g.k_ptr[kernels_e], sizes_e)
    edge_weight = g.k_prob[idx_e] / np.repeat(leave[chosen[by_edges]], sizes_e)
    edge_weight[g.k_succ[idx_e] == np.repeat(states[by_edges], sizes_e)] = 0.0
    edge_column = position[g.k_succ[idx_e]]
    edge_offsets = np.concatenate(([0], np.cumsum(sizes_e)[:-1]))
    extended = np.zeros(m + 1)

    def terms(v: np.ndarray) -> np.ndarray:
        extended[:m] = v
        out = np.zeros(m)
        if len(shared):
            out[shared] = (np.add.reduceat(shared_prob * extended[shared_column], shared_offsets)[slot] - own * v[shared]) / divisor
        if len(by_edges):
            out[by_edges] = np.add.reduceat(edge_weight * extended[edge_column], edge_offsets)
        return out

    return terms, {"policy_edges": len(edge_weight), "shared_edges": len(shared_prob)}


def policy_solver(work: Work, leave: np.ndarray, chosen: np.ndarray, position: np.ndarray, progress: Callable[[str], None] | None = None) -> ChainSolver:
    """The solver of `(I - P) x = b` by the cycles of the policy's chain (`_packed_chain.ChainSolver`), built without expanding a shared kernel state by state.

    A kernel of at least `SHARE_MIN` edges that two or more states of the policy take is one row `K` for all of them (the Woodbury step puts it back once);
    every other state keeps its own row, at most the edges the graph stores for it. The chances `Q` are the kernel's own, the own term included, restricted
    to the states of the policy; what goes elsewhere (a goal, a state outside the policy) is the row's leak, a sum of positive terms.
    """
    g, m = work.g, len(chosen)
    kernels = g.act_kernel[chosen]
    size = work.ksize[kernels]
    pooled = (np.bincount(kernels, minlength=g.num_kernels)[kernels] >= 2) & (size >= SHARE_MIN)
    own_rows = np.flatnonzero(~pooled)
    idx = expand_ranges(g.k_ptr[kernels[own_rows]], size[own_rows])
    owner = np.repeat(own_rows, size[own_rows])
    target = position[g.k_succ[idx]]
    prob = g.k_prob[idx]
    inside = target < m
    leak = np.bincount(owner[~inside], weights=prob[~inside], minlength=m)  # a sum of positive terms
    ptr = np.concatenate(([0], np.cumsum(np.bincount(owner[inside], minlength=m))))
    shared_of = np.full(m, -1, dtype=np.int64)
    shared: list[tuple[np.ndarray, np.ndarray, float]] = []
    if pooled.any():
        used, group = np.unique(kernels[pooled], return_inverse=True)
        shared_of[pooled] = group
        for k in used.tolist():
            span = slice(int(g.k_ptr[k]), int(g.k_ptr[k]) + int(work.ksize[k]))
            cols, vals = position[g.k_succ[span]], g.k_prob[span]
            keep = cols < m
            shared.append((cols[keep], vals[keep], float(np.sum(vals[~keep]))))
    return ChainSolver(m, ptr, target[inside], prob[inside], leave[chosen], leak, shared_of, shared, progress=progress)


class _PolicyTerms(_packed_linear.Terms):
    """The policy's system `x[s] = cost[s] / leave[s] + sum over t != s of (p[s, t] / leave[s]) x[t]` for the one linear solve (`_packed_linear`).

    Up to `dense_limit` states it is held as a dense matrix; above, as `policy_terms` (each kernel summed once, memory O(edges)). Its exact solve is the
    one by the cycles of the policy's chain (`policy_solver`).
    """

    def __init__(self, work: Work, leave: np.ndarray, chosen: np.ndarray, states: np.ndarray, position: np.ndarray, dense: bool, info: dict) -> None:
        self.work, self.leave, self.chosen, self.position = work, leave, chosen, position
        self.n = m = len(states)
        if dense:
            g = work.g
            kernels = g.act_kernel[chosen]
            sizes = work.ksize[kernels]
            idx = expand_ranges(g.k_ptr[kernels], sizes)
            dst = g.k_succ[idx]
            weight = g.k_prob[idx] / np.repeat(leave[chosen], sizes)
            weight[dst == np.repeat(states, sizes)] = 0.0
            row = np.repeat(np.arange(m), sizes)
            column = position[dst]
            inside = column < m
            self._off = np.bincount(row[inside] * m + column[inside], weights=weight[inside], minlength=m * m).reshape(m, m)
            self.apply = self._off.__matmul__
        else:
            self._off = None
            self.apply, counts = policy_terms(work, leave, chosen, states, position)
            info["policy_states"], info["policy_edges"], info["shared_edges"] = m, counts["policy_edges"], counts["shared_edges"]

    def dense(self) -> np.ndarray:
        return self._off

    def exact(self):
        return policy_solver(self.work, self.leave, self.chosen, self.position)


def evaluate_policy(
    work: Work, leave: np.ndarray, policy: np.ndarray, start: np.ndarray, dense_limit: int, tol: float, info: dict
) -> np.ndarray:
    """The values of the proper `policy` (action index per state, -1 for the states outside): a full-length vector.

    The system is `x[s] - sum over t != s of (p[s, t] / leave[s]) x[t] = cost[s] / leave[s]`, solved by the one linear solve (`_packed_linear.solve`,
    ticket #841): dense up to `dense_limit` states, else BiCGSTAB (aiming at the relative residual `tol`, from `start`) until it converges or first
    stagnates. What is taken is judged by what bounds its error, never by a residual alone (#699): the forward estimate (the residual against the
    right-hand side, or the componentwise backward error times the amplification measured by one more solve). Above `ACCEPT_ERROR` the exact solve by
    the cycles of the policy's chain is made, whatever the number of states (`policy_solver`: components inverted without a subtraction, the rows many
    states share cut and put back by the Woodbury identity, then refined while the backward error falls). It costs the cells of the cut rows, not a
    count of states; when they do not fit in `_packed_chain.WOODBURY_CELLS` the approximate answer stays, accepted only if its backward error is
    within `ACCEPT_BOUND` (the certificate that follows bounds the error of the values), else `ConvergenceError` says what the exact solve would have
    cost. `info["linear_limit"]` holds what remained.
    """
    states = np.flatnonzero(policy >= 0)
    m = len(states)
    values = np.zeros(work.n)
    if m == 0:
        return values
    chosen = policy[states]
    position = np.full(work.n, m, dtype=np.int64)
    position[states] = np.arange(m)
    rhs = work.g.act_cost[chosen] / leave[chosen]
    terms = _PolicyTerms(work, leave, chosen, states, position, m <= dense_limit, info)
    began = _tick()
    found = _packed_linear.solve(terms, rhs, x0=start[states], dense_limit=dense_limit, iterate_tol=tol, info=info)
    if found.how == "dense":
        info["linear_dense"] = info.get("linear_dense", 0) + 1
    if found.how != "dense" or found.iterations:
        info["linear_iterations"] = info.get("linear_iterations", 0) + found.iterations
    if found.iterate is not None:
        info["linear_residual_iterate"] = found.iterate[1]
        info["linear_forward_iterate"] = found.iterate[2]
    if found.how == "exact":
        info["linear_cycles"] = info.get("linear_cycles", 0) + 1
        info["linear_cut_rows"] = found.cut_rows
        info["seconds_cycles"] = info.get("seconds_cycles", 0.0) + _tick() - began
        if found.iterate is not None:
            info["linear_replaced"] = info.get("linear_replaced", 0) + 1
    if found.x is None or not np.all(np.isfinite(found.x)):
        raise ConvergenceError(f"the policy is improper: its linear system is singular ({found.why})" if found.x is None else "the evaluation of a policy did not give finite values", INF)
    info["linear_backward_error"], info["linear_forward"], info["linear_residual"] = found.backward, found.forward, found.residual
    if not found.good:
        if not found.backward <= ACCEPT_BOUND:  # a stop-and-say-so rail: an answer this far off is not one the certificate could accept
            raise ConvergenceError(
                f"the evaluation of a policy of {m:,} states did not reach a backward error of {ACCEPT_BOUND:g} (it is {found.backward:.3g}) "
                f"and the exact solve by its cycles could not be made: {found.why}",
                INF,
            )
        if found.residual >= info.get("linear_limit", {}).get("residual", 0.0):  # (the worst of the evaluations of a solve is the one that is said)
            # taken as it is; the certificate that follows bounds the error of the values. `amplification`: the forward estimate over the backward error
            amplification = max(1.0, found.forward / found.backward) if found.backward > 0.0 and math.isfinite(found.forward) else max(1.0, float(np.max(np.abs(found.x))) / max(float(np.max(np.abs(rhs))), 1e-300))
            info["linear_limit"] = {"states": m, "residual": found.residual, "amplification": amplification, "why": found.why, **found.cost}
    values[states] = found.x
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
    certificate = certify(graph, value, inside, work, accept_bound)
    info["seconds_certify"] = _tick() - mark
    refinements = 0
    while not _settled(certificate, tolerance) and refinements < 3:
        refinements += 1
        value = evaluate_policy(work, leave, policy, value, dense_limit, 1e-15, info)
        certificate = certify(graph, value, inside, work, accept_bound)
    info["refinements"] = refinements
    if not certificate.bound <= accept_bound:  # also false for an infinite or undefined bound
        raise ConvergenceError(
            f"the policy iteration on {n:,} states certifies only a relative bound of {certificate.bound:.3g} "
            f"(asked: tolerance {tolerance}, accepted: {accept_bound}; residual {certificate.residual:.3g} of its margin){_own_text(certificate)}",
            certificate.bound,
        )
    info["quotient_own_bound"], info["quotient_own_cost"] = certificate.own_bound, certificate.own_cost
    say(f"certificate on the quotient: bound {certificate.bound:.3g}{_own_text(certificate)} ({time.perf_counter() - began:.1f} s)")
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
    certificate = certify(graph, value, solved, wanted=accept_bound)
    info["certify_seconds"] = round(time.perf_counter() - mark, 2)
    info["quotient_bound"] = core.certificate.bound
    if not certificate.bound <= accept_bound:
        raise ConvergenceError(
            f"the values of the merged graph do not satisfy the Bellman equation of the whole graph to {accept_bound} "
            f"(bound {certificate.bound:.3g}, residual {certificate.residual:.3g} of its margin): the merge or the solve is wrong",
            certificate.bound,
        )
    info["own_bound"], info["own_cost"] = certificate.own_bound, certificate.own_cost
    say(f"certificate on the whole graph: bound {certificate.bound:.3g}{_own_text(certificate)} ({info['certify_seconds']} s)")
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
