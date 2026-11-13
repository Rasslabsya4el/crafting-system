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
   policy, else BiCGSTAB, whose result is taken on its TRUE residual and its componentwise backward error (`_bicgstab`, `backward_error`; never on
   the method's own claim: ticket #584). A stiff system, which the iteration cannot follow, is solved exactly by the cycles of the policy's chain
   (`_packed_chain.ChainSolver`, ticket #621), whatever the number of its states: its cost is the cells of the rows that many states share, and a
   run whose memory does not hold them says so (`info["linear_limit"]`, or `ConvergenceError`) instead of a count of states deciding; then every state takes the action of least Q, an action replacing the current one only when it
   is better by more than the rounding of the sum (so the iteration cannot cycle on noise).
5. CERTIFICATE. `certify` computes, on the graph as given and for the candidate values, the residuals of the Bellman
   operator and from them the relative error bound of `solver/_certify.py`, here per state: with g(s) the cheapest
   action cost at s, k(s) the cost of the greedy action, e(s) = (TV - V)+ and d(s) = (V - TV)+ (each widened by the
   float64 rounding of the sum, (m + 2) eps of it, m the terms of the sum), the values satisfy
   a_lo V <= V* <= a_hi V with a_lo = min g/(g + d) and a_hi = max k/(k - e) (infinite when some e >= k).
   g and k are the margins of h = 0; `certify` also measures d and e against the margins of the cost ahead (ticket #769),
   so that a state whose actions are all free (an unveil, a pick) is measured against the paid step after them and not
   against its own epsilon, which its rounding alone exceeds; each side takes the better of the two.
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
from ._packed_chain import ChainSolver, CyclesTooTangled
from ._packed_merge import exact_classes, identity_classes, quotient

EPS = sys.float_info.epsilon
INF = math.inf
ACCEPT_BOUND = 1e-6  # a certified relative bound above this raises `ConvergenceError` (the rounding of long sums gives 5e-8 on R04, 7e-8 on S02)
DENSE_LIMIT = 1500  # policies of at most this many states are evaluated by a dense solve, larger ones by BiCGSTAB
CHUNK_EDGES = 4_000_000
HEAVY_SELF = 0.5  # an action whose kernel puts more than this chance on its own state is summed edge by edge: taking the own term off a shared sum would lose digits
AHEAD_FIRST = 2  # the first window of the cost ahead that `certify` also measures a state's error against (#769): a free step and the paid one after it; it doubles while the bound is above the one wanted (`certify`). It decides no answer, only how tight the bound is
AHEAD_LIMIT = 64  # the longest window of the cost ahead: a stop-and-say-so rail (OR-12) on its cost, one sweep of the graph a step; the refusal names it
AHEAD_WEIGHT = 0.5  # w of `certify`'s cost ahead: a paid state keeps at least 1 - w of its own cost as its margin, a free state gets w / L of the paid steps in its window
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
    window: int = 0  # the steps of the cost ahead that the bound given is measured against (0: each state's own cost, `certify`)


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
    return (
        f" (measured against the cost of the next {certificate.window} steps; against each state's own cheapest cost alone: {certificate.own_bound:.3g}, "
        f"set at a state whose cheapest action costs {certificate.own_cost:.3g}; the cost ahead is measured over at most {AHEAD_LIMIT} steps)"
    )


def _settled(certificate: Certificate, tolerance: float) -> bool:
    """Whether the residual is within `tolerance` of its margin (the cheapest cost, or the cost ahead where that is larger), or at the rounding floor: more evaluation cannot help."""
    return certificate.residual <= tolerance or certificate.at_floor


def _shares(error: np.ndarray, margin: np.ndarray) -> np.ndarray:
    """`error / margin` per state, for an error that is at least 0: 0 where the error is 0 and the margin is not negative (nothing to carry), infinite
    where a positive error meets a margin that is not positive or a negative margin meets anything (no `t >= 0` makes `error <= t * margin` there)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        share = error / np.where(margin > 0.0, margin, 1.0)
    return np.where(margin > 0.0, share, np.where((error == 0.0) & (margin == 0.0), 0.0, INF))


def _sides(d: np.ndarray, e: np.ndarray, gamma: np.ndarray, kappa: np.ndarray) -> tuple[float, float, np.ndarray]:
    """`(lower, upper, share)` of the module docstring for the margins `gamma` (every action) and `kappa` (the greedy one): `lower = 1 / (1 + max d / gamma)`,
    `upper = 1 / (1 - max e / kappa)` (infinite unless every `e < kappa`, which is also what proves the greedy policy proper); `share` is each state's larger share."""
    low, high = _shares(d, gamma), _shares(e, kappa)
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

    def lowered(sum_: np.ndarray, h: np.ndarray) -> np.ndarray:
        """`sum_ - h` less the rounding of the sum (`grow` of it) and of the subtraction: at most the exact difference."""
        s, h, r = sum_[targets], h[targets], grow[targets]
        return s - r * s - h - 2.0 * EPS * (s + h)

    own_lower, own_upper, own_share = _sides(d, e, g, k)
    best = (own_lower, own_upper, g, 0)
    last = max(1.0 - own_lower, own_upper - 1.0)
    window, step, total, steps = AHEAD_FIRST, np.where(targets, g_all, 0.0), np.where(targets, g_all, 0.0), 1
    longest = min(AHEAD_LIMIT, int(targets.sum()))  # a window as long as the states are many cannot meet a paid step it has not met
    while not max(1.0 - best[0], best[1] - 1.0) <= wanted and window // 2 < longest:  # (the last window tried is the first at least `longest`)
        # The cost ahead is measured only when each state's own cost does not carry the bound wanted, so a plan that certifies on it keeps its
        # numbers. The window doubles while the bound is above `wanted` and the doubling does not make it clearly worse: a run of free steps with
        # epsilon costs gives the same margin to every window until the window reaches the paid step after it, and then a far larger one.
        while steps < window:
            step = np.where(targets, backup(step)[1], 0.0)
            total += step
            steps += 1
        h = total * (AHEAD_WEIGHT / window)
        qh, th = backup(h)
        gamma, kappa = lowered(th, h), lowered(qh[greedy], h)
        lower, upper, _ = _sides(d, e, gamma, kappa)
        if lower > best[0] or upper < best[1]:
            best = (max(lower, best[0]), min(upper, best[1]), np.maximum(gamma, 0.0), window)
        now = max(1.0 - lower, upper - 1.0)
        if window > AHEAD_FIRST and not now <= 2.0 * last:
            break
        last = now
        window *= 2
    lower, upper, margin, used = best
    bound = max(1.0 - lower, upper - 1.0)
    own_bound = max(1.0 - own_lower, own_upper - 1.0)
    residual = float(np.max(_shares(np.maximum(e0, d0), np.maximum(margin, g))))
    setter = int(np.argmax(own_share))
    return Certificate(bound, lower, upper, residual, bool(np.all(np.maximum(e0, d0) <= delta[targets])), own_bound, float(g[setter]), used)


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
DENSE_FALLBACK = 6_000  # no longer read here (ticket #621: the exact solve by the cycles of the chain has no count of states); `cli/_route_flow._linear` still imports it
DENSE_FALLBACK_RESIDUAL = 1e-10


def _bicgstab(matvec: Callable[[np.ndarray], np.ndarray], b: np.ndarray, x0: np.ndarray, tol: float, max_iter: int):
    """BiCGSTAB for `matvec(x) = b`: returns `(x, relative residual, iterations)`.

    The residual returned is the TRUE one, `|b - A x| / |b|` of the iterate returned, made by one more product. The residual of the
    method's own recurrence is not that: on a stiff system it drifts from the true one, can be 1e-21 while the iterate is wrong by
    a factor of 1e16 (tickets #584 and #600), and so it only decides when the method stops. The iterate returned is the better, by
    the true residual, of the best the recurrence saw and the start `x0` (whose residual is true: it is `b - A x0`). Every caller
    reads this number and nothing else; it is the one place a solve is checked.
    """
    with np.errstate(all="ignore"):
        x, iterations, first, _ = _bicgstab_run(matvec, b, x0, tol, max_iter)
        bnorm = max(float(np.linalg.norm(b)), 1e-300)
        true = float(np.linalg.norm(b - matvec(x)))
        if not true <= first:  # the recurrence ended on an iterate worse than the start (or not a number)
            x, true = x0.copy(), first
        return x, true / bnorm, iterations


def _bicgstab_run(matvec, b, x0, tol, max_iter):
    """`(best iterate by the recurrence, iterations, true norm of b - A x0, the relative residual the recurrence claims for that iterate)`."""
    x = x0.copy()
    r = b - matvec(x)
    bnorm = max(float(np.linalg.norm(b)), 1e-300)
    rnorm = float(np.linalg.norm(r))
    first = rnorm
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
    return best_x, it, first, best / bnorm


def bicgstab_checked(matvec, b: np.ndarray, x0: np.ndarray, tol: float):
    """BiCGSTAB with restarts: `(x, true relative residual, iterations)` (the module text of `_bicgstab` says which residual).

    A run that stalls, or stops on a recurrence residual that is not the true one, starts again from its best iterate with a fresh
    recurrence (`b - A x` made anew), at most `BICGSTAB_RESTARTS` times, until the true residual is within 10 `tol`.
    """
    x, residual, iterations = _bicgstab(matvec, b, x0, tol, BICGSTAB_ITERATIONS)
    for _ in range(BICGSTAB_RESTARTS):
        if residual <= 10 * tol:
            break
        x, residual, more = _bicgstab(matvec, b, x, tol, BICGSTAB_ITERATIONS)
        iterations += more
    return x, residual, iterations


SETTLED = 8 * EPS  # a backward error this small is the rounding of the product itself: a further refinement step cannot lower it
REFINEMENTS = 4  # steps of refinement of the solve by the cycles of the chain (each is a residual and one more solve)


def backward_error(terms: Callable[[np.ndarray], np.ndarray], rhs: np.ndarray, x: np.ndarray) -> float:
    """The componentwise backward error of `x` in `x = rhs + T x`, `T` the sum of the chances to other states (not the own one) over `leave`.

    `max over s of |rhs[s] - (x[s] - T(x)[s])| / (|x[s]| + T(|x|)[s] + |rhs[s]|)`: the size of the relative change of the system that would make `x`
    exact, small exactly for an answer as good as floats allow and about 1 for a wrong one. `T` has no negative entry, so `T(|x|)` is the sum of the
    absolute terms. A plain `|rhs - A x| / |rhs|` cannot get below the rounding of the terms when the answer is far larger than the right-hand side (a
    policy that rerolls a hundred million times), and refuses an answer that is as good as floats allow. Infinite if it is not a number.
    """
    if not len(rhs):
        return 0.0
    with np.errstate(all="ignore"):
        scale = np.abs(x) + terms(np.abs(x)) + np.abs(rhs)
        error = np.abs(rhs - (x - terms(x))) / np.where(scale > 0.0, scale, 1.0)
    return float(np.max(error)) if np.all(np.isfinite(error)) else INF


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


def evaluate_policy(
    work: Work, leave: np.ndarray, policy: np.ndarray, start: np.ndarray, dense_limit: int, tol: float, info: dict
) -> np.ndarray:
    """The values of the proper `policy` (action index per state, -1 for the states outside): a full-length vector.

    The system is `x[s] - sum over t != s of (p[s, t] / leave[s]) x[t] = cost[s] / leave[s]`. A dense solve takes it as it is up to `dense_limit` states,
    else BiCGSTAB on `policy_terms` (memory O(edges), never O(states^2)). What is taken is judged on its TRUE residual, never on a number a method
    claims of itself: `|b - A x| / |b|` of the iterate (one more product), and the componentwise backward error of `backward_error`
    (`info["linear_backward_error"]`), which is what a stiff system can reach (the first cannot get below the rounding of the terms when the answer is
    far larger than the right-hand side).

    An iterate is good when its true residual is within `DENSE_FALLBACK_RESIDUAL`, a dense solve when its backward error is. The backward error of an
    iterate is NOT what makes it good: it is a measure of the system's relative change, and the error of the values is that times the condition of `I - P`,
    which the ratio of the answer to the right-hand side (`info["linear_error_floor"]`, a lower bound named as one) only bounds from below. Otherwise (a stiff
    system: BiCGSTAB cannot follow a cycle that a run goes round millions of times, and an iterate that it does follow is good to a backward error of 1e-15
    and to 1e-4 as an answer) the exact solve is made by the cycles of the policy's chain, whatever the number of states (`policy_solver`: components
    inverted whole, the rows many states share cut and put back by the Woodbury identity, then refined while the backward error falls). It costs the cells
    of the cut rows, not a count of states; when they do not fit in `_packed_chain.WOODBURY_CELLS` the iterate stays, accepted only if its true residual is
    within `ACCEPT_BOUND` (the certificate that follows bounds the error of the values), else `ConvergenceError` says what the exact solve would have cost.
    `info["linear_limit"]` holds what remained, derived from that cost.
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
    residual: float | None = None

    if m <= dense_limit:
        kernels = g.act_kernel[chosen]
        sizes = work.ksize[kernels]
        idx = expand_ranges(g.k_ptr[kernels], sizes)
        dst = g.k_succ[idx]
        weight = g.k_prob[idx] / np.repeat(leave[chosen], sizes)
        weight[dst == np.repeat(states, sizes)] = 0.0
        row = np.repeat(np.arange(m), sizes)
        column = position[dst]
        inside = column < m
        off = np.bincount(row[inside] * m + column[inside], weights=weight[inside], minlength=m * m).reshape(m, m)
        matrix = np.eye(m) - off
        try:
            solved = np.linalg.solve(matrix, rhs)
            for _ in range(2):  # iterative refinement: a stiff system loses digits in one solve
                correction = rhs - matrix @ solved
                if not np.max(np.abs(correction)) > 4 * EPS * np.max(np.abs(rhs)):
                    break
                solved = solved + np.linalg.solve(matrix, correction)
        except np.linalg.LinAlgError as error:
            raise ConvergenceError("the policy is improper: its linear system is singular", INF) from error
        info["linear_dense"] = info.get("linear_dense", 0) + 1

        def terms(v: np.ndarray) -> np.ndarray:
            return off @ v

    else:
        terms, counts = policy_terms(work, leave, chosen, states, position)
        info["policy_states"], info["policy_edges"], info["shared_edges"] = m, counts["policy_edges"], counts["shared_edges"]

        def matvec(x: np.ndarray) -> np.ndarray:
            info["matvecs"] = info.get("matvecs", 0) + 1
            return x - terms(x)

        solved, residual, iterations = bicgstab_checked(matvec, rhs, start[states], tol)
        info["linear_iterations"] = info.get("linear_iterations", 0) + iterations
        info["linear_residual"] = residual  # the true one, |rhs - A x| / |rhs| (of the exact values instead, once they replace the iterate)

    scale = max(float(np.max(np.abs(rhs))), 1e-300)

    def floor_of(x: np.ndarray, backward: float) -> float:
        """A LOWER bound on the error an answer can have, not the error: its backward error times how many times larger than the right-hand side it is.

        The error of an answer is its backward error times the condition of `I - P`, and the ratio of this answer to this right-hand side is only the least that
        condition can be (a stiff state that feeds a stiff state squares it: a ratio of 1e5 at a backward error of 1e-15 is 1e-10 here and can be 1e-5 off).
        It is kept as `info["linear_error_floor"]` for the reader of a limit; no decision of this function rests on it.
        """
        return backward * max(1.0, float(np.max(np.abs(x))) / scale)

    error = backward_error(terms, rhs, solved)
    info["linear_backward_error"], info["linear_error_floor"] = error, floor_of(solved, error)
    # what is judged: the true residual of an iterate (a measured quantity, and the old test), the backward error of a direct solve (stable by the division of the self-loops)
    judged = error if residual is None else residual
    if not judged <= DENSE_FALLBACK_RESIDUAL:
        # the iterate (or the dense solve) is not good: the exact solve by the cycles of the chain, whatever the number of states
        if residual is not None:
            info["linear_residual_iterate"] = residual
        reason, cost = None, {}
        try:
            began = _tick()
            solver = policy_solver(work, leave, chosen, position)
            exact = solver.solve(rhs)
            exact_error = backward_error(terms, rhs, exact)
            for _ in range(REFINEMENTS):
                if exact_error <= SETTLED:
                    break
                better = exact + solver.solve(rhs - (exact - terms(exact)))
                better_error = backward_error(terms, rhs, better)
                if not better_error < exact_error:
                    break
                exact, exact_error = better, better_error
            info["linear_cycles"] = info.get("linear_cycles", 0) + 1
            info["linear_cut_rows"] = solver.q
            info["seconds_cycles"] = info.get("seconds_cycles", 0.0) + _tick() - began
        except (CyclesTooTangled, MemoryError, np.linalg.LinAlgError) as stopped:
            exact, exact_error, reason = None, INF, (str(stopped) or "the memory of the run, or a block of the chain that is singular in floats, stopped it")
            cost = {"rows": stopped.rows, "cells": stopped.cells, "allowed": stopped.allowed} if isinstance(stopped, CyclesTooTangled) else {}
        accepted = False
        if exact is not None:
            with np.errstate(all="ignore"):  # the residual that goes with the values taken, not with the iterate thrown away
                taken = float(np.linalg.norm(rhs - (exact - terms(exact))) / max(float(np.linalg.norm(rhs)), 1e-300))
            accepted = exact_error <= DENSE_FALLBACK_RESIDUAL
            if accepted or (taken < residual if residual is not None else exact_error < error):  # a direct solve that is backward stable is taken over an iterate
                solved, error = exact, exact_error
                info["linear_replaced"] = info.get("linear_replaced", 0) + 1
                info["linear_backward_error"], info["linear_error_floor"], info["linear_residual"] = error, floor_of(solved, error), taken
                residual = taken if residual is not None else None
                judged = error if residual is None else residual
            if not accepted:
                reason = f"the exact solve by the cycles of the chain reached only a backward error of {exact_error:.3g}"
        if not accepted and not judged <= DENSE_FALLBACK_RESIDUAL:
            if not judged <= ACCEPT_BOUND:  # a stop-and-say-so rail: a residual this large is not a value the certificate could accept
                raise ConvergenceError(
                    f"the evaluation of a policy of {m:,} states did not reach a true residual of {ACCEPT_BOUND:g} (it is {judged:.3g}) "
                    f"and the exact solve by its cycles could not be made: {reason}",
                    INF,
                )
            if judged >= info.get("linear_limit", {}).get("residual", 0.0):  # (the worst of the evaluations of a solve is the one that is said)
                # accepted as it is; the certificate that follows bounds the error of the values. `amplification`: how many times the answer is the right-hand side,
                # the least the condition of the system can be (so the error is the residual times at least that, in the worst case: not a bound, a reason to say it)
                amplification = max(1.0, float(np.max(np.abs(solved))) / scale)
                info["linear_limit"] = {"states": m, "residual": judged, "amplification": amplification, "why": reason, **cost}
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
