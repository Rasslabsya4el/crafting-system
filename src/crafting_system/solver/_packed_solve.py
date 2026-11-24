"""The packed solve: policy iteration on a packed graph, merged exactly first, certified at the end (ticket #374).

`solve_packed(graph)` is the solve of `research/312/prune_analysis.py` made a product piece (ADR-0063 point 1):

1. MERGE. The exact classes of the graph (`_packed_merge`) and the quotient, one state per class.
2. PROPER STATES. A state has a finite value only if some policy reaches the goal with certainty. The set Y of such states
   is the greatest set in which every state has an action whose outcomes all lie in Y and from which the goal is reached:
   found by shortest-path sweeps over the actions that stay in Y (a long path by one pass, `_cheapest_paths`), shrinking Y until it is stable.
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
   float64 rounding of the sum, (m + 2) eps of it, m the terms of the sum; `4 eps` when that does not reach the bound asked and the sums are
   taken again rounded once, `_packed.kernel_sums_rounded_once`, #867), the values satisfy
   a_lo V <= V* <= a_hi V with a_lo = min g/(g + d) and a_hi = max k/(k - e) (infinite when some e >= k).
   g and k are the margins of h = 0; `certify` also measures d and e against the margins of the cost ahead (ticket #769),
   so that a state whose actions are all free (an unveil, a pick) is measured against the paid step after them and not
   against its own epsilon, which its rounding alone exceeds; each side takes the better of the two. When neither reaches the
   bound asked, it is measured again on the operator with the self-loops divided out, as the solve divides them (`_divided`,
   #585, #841): a state that stays with chance 1 - 1e-12 is then certified to its own condition, not to `1 / leave`.
   The operator is the one WITHOUT the self-loop compiled out, so the certificate is also an independent check of the
   merge and of the solve: it is run on the unmerged graph with the class values copied back to the members. Where that float measure
   refuses what the quotient's certified (a class whose members hand the run to each other is a cycle of many states here and one state with
   a divided-out self-loop there: R17's seed round, 1.7e12 c, 0.00092 on the quotient and 0.0737 here, #1412), the merge is checked exact in
   integers instead (`_packed_merge.lumps_exactly`) and the quotient's certificate is carried to the members (`Certificate.lumped`); a merge
   that is not exact is refused as before, and so is the unmerged graph (`merge=False`: no quotient to carry from, the check stays independent).

The bound may exceed `tolerance` when the values are large next to the cheapest action (rounding amplification, as in
`_certify.py`); the loop stops when the residuals reach the tolerance or the rounding floor. A solve the certificate then refuses (a bound above
`accept_bound`, 1e-6) is corrected (`corrected`: one step of iterative refinement, its residual taken with every sum rounded once, at most
`CORRECTIONS` times) and measured again (#867). What is still above `accept_bound` raises `ConvergenceError`, unless the caller takes every
value with its certified error and passed `refuse_above` (a search that stops at a gap): then only a bound above that is refused. A solve
refused so is solved again in rational numbers when its exact quotient is small (`_packed_exact`, #1380): a plan of 10^14 attempts (R17's
Alchemy round, 2.26e16 c) merges into 3 classes, and its optimum is then exact, where float64 certified it only to 0.18.
"""

import heapq
import math
import sys
import time
from array import array
from time import perf_counter as _tick  # for the seconds in `info`: the clock the progress lines read is `time.perf_counter`, which a test replaces
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import numpy as np

from ._certify import ACCEPT_BOUND, AHEAD_FIRST, AHEAD_LIMIT, AHEAD_WEIGHT, ConvergenceError, Late, lowered, widen  # noqa: F401  (ACCEPT_BOUND, AHEAD_*: read here, by tests, and shared with the object solver, #842)
from ._packed import PackedGraph, expand_ranges, kernel_any, kernel_min, kernel_sums, kernel_sums_rounded_once, rounded_once_allowance
from . import _packed_linear
from ._packed_chain import ChainSolver
from ._packed_linear import DENSE_LIMIT, backward_error  # noqa: F401  (DENSE_LIMIT: the default of `solve_graph`, read by callers; backward_error: by tests)
from ._packed_merge import exact_classes, identity_classes, lumps_exactly, quotient
from ._packed_exact import exact_quotient

EPS = sys.float_info.epsilon
INF = math.inf
CHUNK_EDGES = 4_000_000
HEAVY_SELF = 0.5  # an action whose kernel puts more than this chance on its own state is summed edge by edge: taking the own term off a shared sum would lose digits
SWEEPS_BEFORE_PASS = 64  # `proper_states` runs its one shortest-path pass once its sweeps have changed the distances this many times (see there)
PASS_ASK = 1 << 16  # ... and that pass asks the caller's clock after each this many states it settles
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
    rounded_once: bool = False  # the bound given is measured with every Bellman sum rounded once (`_packed.kernel_sums_rounded_once`, #867), not once a term
    term_bound: float | None = None  # with `rounded_once`: the bound of the measure with a rounding a term, which the caller did not accept
    exact: bool = False  # the values are the exact optimum rounded once to float64 (`_packed_exact`, #1380): `bound` is that rounding
    lumped: float | None = None  # the bound is the quotient's, carried to the whole graph by its merge checked exact (`lumps_exactly`, #1412); this is what the whole graph's own measure gave


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
    if certificate.exact:
        return " (solved exactly in rational numbers)"
    if certificate.lumped is not None:
        return f" (the quotient's, carried by its merge checked exact in integers: measured on the whole graph itself, {certificate.lumped:.3g})"
    if certificate.rounded_once:
        return f" (measured with every sum rounded once; with a rounding a term: {certificate.term_bound:.3g})"
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
    """The certificate of `_certify`, measured a second time with every Bellman sum rounded once when the first does not reach `wanted` (#867).

    The rounding the certificate allows for a computed sum of `m` terms is `(m + 2) eps` of it, and the bound is that allowance times the value over
    the margin (the cost of a step): a reroll with 35,000 outcomes at a state worth 10^5 steps gives 8e-7 before any residual. It is an allowance for
    the worst order of the roundings, not an error of the values (measured on the family's graphs: 2 eps). `_packed.kernel_sums_rounded_once` takes
    the same sums with one rounding whatever their length, so the allowance is `4 eps`, and the same theorems hold of the same exact operator. The
    second measure costs a few sweeps of the graph and is made only for a plan the first refuses, so a plan that certified keeps its numbers to the
    bit. `at_floor` stays the first measure's: more evaluation cannot help a residual that is within the rounding of the sums the solve itself takes.
    """
    work = work or Work(graph)
    found = _certify(graph, value, solved, work, wanted, False)
    if found.bound <= wanted:
        return found
    finer = _certify(graph, value, solved, work, wanted, True)
    if finer is None or not finer.bound < found.bound:
        return found
    return replace(finer, at_floor=found.at_floor, residual=found.residual, own_bound=found.own_bound, own_cost=found.own_cost, rounded_once=True, term_bound=found.bound)


def _certify(graph: PackedGraph, value: np.ndarray, solved: np.ndarray, work: Work, wanted: float, once: bool) -> Certificate | None:
    """The certificate of the module docstring for candidate `value` on the states `solved` (the others are dead). With `once` the sums are those of
    `kernel_sums_rounded_once` and the allowance is theirs; None when they cannot be taken (a product out of the range in which they are exact).

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
    n, goal = work.n, graph.goal
    targets = ~goal & solved
    if not targets.any():
        return Certificate(0.0, 1.0, 1.0, 0.0, True)
    v = np.where(solved, value, 0.0)
    bad = kernel_any(graph, ~solved)
    ok = ~bad[graph.act_kernel]

    def backup(f: np.ndarray, fine: bool = once) -> tuple[np.ndarray, np.ndarray] | None:
        """`(q, Tf)`: every action's cost plus its expected `f` (infinite for an action that may leave the solved states), and their least per state.
        `fine`: the sums rounded once (None when they cannot be)."""
        sums = kernel_sums_rounded_once(graph, f) if fine else kernel_sums(graph, f)
        if sums is None:
            return None
        q = np.where(ok, graph.act_cost + sums[graph.act_kernel], INF)
        return q, work.state_min(q)

    first = backup(v)
    if first is None:
        return None
    q, tv = first
    if not np.all(np.isfinite(tv[targets])):
        return Certificate(INF, 0.0, INF, INF, False)
    greedy = np.maximum(work.state_argmin(q, tv), 0)
    g_all = work.state_min(np.where(ok, graph.act_cost, INF))
    terms = work.state_reduce(np.maximum, np.where(ok, work.asize + 1, 0).astype(np.float64), 0.0)
    rho = rounded_once_allowance(terms) if once else (terms + 2.0) * EPS
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
            step = np.where(targets, backup(step, False)[1], 0.0)  # (`h` may be any vector that is at least 0: its own sums need no care)
            total += step
            steps += 1
        return total * (AHEAD_WEIGHT / window)

    def measure(h: np.ndarray) -> tuple[float, float, int, np.ndarray]:
        backed = backup(h)
        if backed is None:
            return 0.0, INF, int(targets.sum()), g
        qh, th = backed
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
    if not bound <= wanted and not once:
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


def proper_states(
    work: Work, alive: np.ndarray, effective: np.ndarray, deadline: Callable[[str], None] | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """`(Y, ok, distance, policy)`: the states with a proper policy, the actions that stay in Y, the luckiest-path costs, a proper policy.

    The luckiest-path cost is the least fixed point below infinity of `d(s) = min(d(s), min_a (cost_a + min_{t in K(a)} d(t)))`, `d = 0` at the
    goals, with `cost >= 0`. A sweep of that update over the whole graph (`kernel_min`, `Work.state_min`) carries it one step further from the
    goals, so from infinity a chain of `n` states that reaches a goal only at its far end takes `n` sweeps: 9.3 s on a chain of 20,000 states,
    more than 10 minutes on 200,000, about 1,000 s a round on R17's 210,847 (#1516, #1527). So once the sweeps have changed the distances
    `SWEEPS_BEFORE_PASS` times, one label-setting pass from the goals (`_cheapest_paths`, Dijkstra) gives the fixed point, and the sweeps go on
    from there: the next one changes nothing, and gives the policy as before. A graph that settles in fewer sweeps (most do: R17's rounds took
    0.02 to 0.08 s here) never runs the pass, whose cost per edge is Python's, not numpy's; the switch after 64 bounds what a wrong guess
    costs either way (a pass costs about as much as that many sweeps: see `SWEEPS_BEFORE_PASS` and #1527's measurement).

    The output is the one the sweeps from infinity give, to the bit, whatever the pass returns as long as it is at least that fixed point and 0 at
    the goals: from infinity the sweeps reach the least float value over all paths to a goal, each path's value taken as the sweeps add it (the
    cost of the first step plus the value of the rest, rounded once per step; rounding is monotone, so `fl(c + min x) = min fl(c + x)`), and
    from any start at or above that, they reach the same least value. The distances after a sweep are such a start (each is one path's value),
    and so is the pass (one path's value for every state it reaches, its sum added in that same order, infinity elsewhere), and so is the lesser of
    the two. A pass that missed an edge would cost sweeps, never the answer.

    `deadline`, when given, is asked before every sweep after the first, before the pass and inside it (`_cheapest_paths`), and raises `Late`
    once the caller's time is up."""
    g = work.g
    inside = np.ones(work.n, dtype=bool)
    while True:
        stray = kernel_any(g, ~inside)
        ok = alive & ~stray[g.act_kernel]
        cost = np.where(ok, effective, INF)
        distance = np.where(g.goal, 0.0, INF)
        changed = 0
        while True:
            lowest = kernel_min(g, distance)
            candidate = cost + lowest[g.act_kernel]
            best = work.state_min(candidate)
            nearer = np.minimum(distance, best)
            if np.array_equal(nearer, distance):
                break
            distance = nearer
            changed += 1
            if changed == SWEEPS_BEFORE_PASS:
                distance = np.minimum(distance, _cheapest_paths(work, cost, deadline))
            if deadline is not None:
                deadline("a sweep of the cheapest paths to a goal")
        found = np.isfinite(distance) & inside
        if np.array_equal(found, inside):
            break
        inside = found
    policy = work.state_argmin(candidate, best)
    policy[g.goal | ~inside | ~np.isfinite(best)] = -1
    return inside, ok, distance, policy


def _cheapest_paths(work: Work, cost: np.ndarray, deadline: Callable[[str], None] | None = None) -> np.ndarray:
    """For every state, the cost of its cheapest path to a goal (0 at a goal, infinity where none) under the action costs `cost` (infinity: not
    usable): one label-setting pass (Dijkstra) from the goals backwards over the kernels, a start for the sweeps of `proper_states` (see there).

    A state settled at `d` settles each kernel it is a successor of that is not settled yet, at `d` exactly (the least successor of a kernel is
    the first one settled), and each usable action of a kernel just settled offers its state `cost[a] + d`, one rounding per step, the sum the
    sweeps make. So a kernel that many actions share is entered once, and the work is the edges of the kernels the usable actions use, plus a heap
    push per action that lowers a state: `E + A log A`, in Python. `deadline` is asked before the pass and after every `PASS_ASK` settled states.
    Its arrays (the reverse edges of the used kernels) are built at once, not in chunks: about 40 bytes an edge at their peak."""
    g, n = work.g, work.n
    if deadline is not None:
        deadline("the shortest-path pass to a goal")
    distance = np.where(g.goal, 0.0, INF)
    usable = np.flatnonzero(np.isfinite(cost))
    goals = np.flatnonzero(g.goal)
    if not len(goals) or not len(usable):
        return distance
    by_kernel = usable[np.argsort(g.act_kernel[usable], kind="stable")]
    kernel_of_user = g.act_kernel[by_kernel]
    user_ptr = np.searchsorted(kernel_of_user, np.arange(g.num_kernels + 1))  # the usable actions of kernel k: user_ptr[k]:user_ptr[k + 1]
    kernels = np.unique(kernel_of_user)
    sizes = work.ksize[kernels]
    succ = g.k_succ[expand_ranges(g.k_ptr[kernels], sizes)]
    by_succ = np.argsort(succ, kind="stable")
    into = np.repeat(kernels, sizes)[by_succ]  # the used kernels holding state t: into[into_ptr[t]:into_ptr[t + 1]]
    into_ptr = np.searchsorted(succ[by_succ], np.arange(n + 1))
    into, into_ptr, user_ptr = (memoryview(np.ascontiguousarray(x, dtype=np.int64)) for x in (into, into_ptr, user_ptr))
    user_state = memoryview(np.ascontiguousarray(work.act_state[by_kernel], dtype=np.int64))
    user_cost = memoryview(np.ascontiguousarray(cost[by_kernel], dtype=np.float64))
    best = array("d", distance.tobytes())
    settled = bytearray(n)
    entered = bytearray(g.num_kernels)
    heap = [(0.0, int(t)) for t in goals]
    pop, push = heapq.heappop, heapq.heappush
    count = 0
    while heap:
        d, t = pop(heap)
        if settled[t]:
            continue
        settled[t] = 1
        count += 1
        if deadline is not None and count % PASS_ASK == 0:
            deadline("the rest of the shortest-path pass to a goal")
        for i in range(into_ptr[t], into_ptr[t + 1]):
            k = into[i]
            if entered[k]:
                continue
            entered[k] = 1
            for j in range(user_ptr[k], user_ptr[k + 1]):
                s = user_state[j]
                offer = user_cost[j] + d
                if offer < best[s]:
                    best[s] = offer
                    push(heap, (offer, s))
    return np.frombuffer(best, dtype=np.float64).copy()


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
    work: Work, alive: np.ndarray, effective: np.ndarray, start: np.ndarray, info: dict, value: np.ndarray | None = None, leave: np.ndarray | None = None,
    deadline: Callable[[str], None] | None = None,
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
    inside, ok, _, cheapest = proper_states(work, alive, effective, deadline)
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


def policy_system(work: Work, leave: np.ndarray, chosen: np.ndarray, states: np.ndarray, position: np.ndarray) -> _packed_linear.Sparse:
    """The policy's system in its sparse form with one extra unknown per kernel it uses (`_packed_linear.Sparse`, for the preconditioned solve, #1484).

    A state that `policy_terms` sums on its kernel's shared sum has the row `(leave[s] + own[s]) x[s] - y[k] = cost[s]` (the row of `I - T` times
    `leave[s]`), and each such kernel `k` the row `y[k] - sum over its successors t in the policy of p[k, t] x[t] = 0`, the own term included: no
    kernel is expanded state by state (R17's first plan: 1,024,996 states and 301,629 kernels in 5.2M entries, 3.6M edges had they been expanded).
    A state `Work.edgewise` names keeps its edges, the row `leave[s] x[s] - sum over t != s of p[s, t] x[t] = cost[s]`, with no own term to take off.
    A successor outside the policy (a goal, a state solved) is 0.
    """
    g, m = work.g, len(states)
    wise = work.edgewise[chosen]
    by_edges = np.flatnonzero(wise)
    shared = np.flatnonzero(~wise)
    kernels, slot = np.unique(g.act_kernel[chosen[shared]], return_inverse=True)
    k = len(kernels)
    sizes = work.ksize[kernels]
    idx = expand_ranges(g.k_ptr[kernels], sizes)
    kernel_column = position[g.k_succ[idx]]
    kernel_row = m + np.repeat(np.arange(k, dtype=np.int64), sizes)
    inside = kernel_column < m
    kernels_e = g.act_kernel[chosen[by_edges]]
    sizes_e = work.ksize[kernels_e]
    idx_e = expand_ranges(g.k_ptr[kernels_e], sizes_e)
    edge_target = g.k_succ[idx_e]
    edge_column = position[edge_target]
    keep = (edge_column < m) & (edge_target != np.repeat(states[by_edges], sizes_e))
    tail = m + np.arange(k, dtype=np.int64)
    row = np.concatenate((shared, shared, kernel_row[inside], tail, by_edges, np.repeat(by_edges, sizes_e)[keep]))
    col = np.concatenate((shared, m + slot, kernel_column[inside], tail, by_edges, edge_column[keep]))
    value = np.concatenate((
        leave[chosen[shared]] + work.self_mass[chosen[shared]], -np.ones(len(shared)), -g.k_prob[idx][inside], np.ones(k),
        leave[chosen[by_edges]], -g.k_prob[idx_e][keep],
    ))  # fmt: skip
    return _packed_linear.Sparse(m + k, row, col, value, leave[chosen])


class _PolicyTerms(_packed_linear.Terms):
    """The policy's system `x[s] = cost[s] / leave[s] + sum over t != s of (p[s, t] / leave[s]) x[t]` for the one linear solve (`_packed_linear`).

    Up to `dense_limit` states it is held as a dense matrix; above, as `policy_terms` (each kernel summed once, memory O(edges)). Its exact solve is the
    one by the cycles of the policy's chain (`policy_solver`), its sparse form the one with an unknown per kernel (`policy_system`).
    """

    def __init__(self, work: Work, leave: np.ndarray, chosen: np.ndarray, states: np.ndarray, position: np.ndarray, dense: bool, info: dict) -> None:
        self.work, self.leave, self.chosen, self.states, self.position = work, leave, chosen, states, position
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

    def sparse(self) -> _packed_linear.Sparse:
        return policy_system(self.work, self.leave, self.chosen, self.states, self.position)


def _preconditioned_words(tried: dict) -> str:
    """What the preconditioned solve did, for the words of a refusal (#1484); empty when it was not tried."""
    if not tried:
        return ""
    if "why" in tried:
        return f"; {tried['why']}"
    return f"; the preconditioned solve reached a backward error of {tried['backward']:.3g} (forward estimate {tried['forward']:.3g}) after {tried['seconds']:.0f} s of factorisation"


def evaluate_policy(
    work: Work, leave: np.ndarray, policy: np.ndarray, start: np.ndarray, dense_limit: int, tol: float, info: dict
) -> np.ndarray:
    """The values of the proper `policy` (action index per state, -1 for the states outside): a full-length vector.

    The system is `x[s] - sum over t != s of (p[s, t] / leave[s]) x[t] = cost[s] / leave[s]`, solved by the one linear solve (`_packed_linear.solve`,
    ticket #841): dense up to `dense_limit` states, else BiCGSTAB (aiming at the relative residual `tol`, from `start`) until it converges or first
    stagnates. What is taken is judged by what bounds its error, never by a residual alone (#699): the forward estimate (the residual against the
    right-hand side, or the componentwise backward error times the amplification measured by one more solve). Above `ACCEPT_ERROR` the exact solve by
    the cycles of the policy's chain is made, whatever the number of states (`policy_solver`: components inverted without a subtraction, the rows many
    states share cut and put back by the Woodbury identity, then refined while the backward error falls); when that cannot be made
    and the iteration stalled, the same BiCGSTAB preconditioned by an incomplete LU of the system with one unknown per kernel (`policy_system`, #1484). The exact solve costs the cells of the cut rows, not a
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
    if found.preconditioned:  # the plain iteration stalled: the preconditioned solve was tried (#1484), with its time
        info["linear_preconditioned"] = info.get("linear_preconditioned", 0) + 1
        info["seconds_preconditioned"] = info.get("seconds_preconditioned", 0.0) + found.preconditioned.get("seconds", 0.0)
        info["preconditioned"] = dict(found.preconditioned)  # (the last of this solve; over the solves of a search, a record of the worst, `_envelope.add_solve_info`)
    if found.how == "preconditioned":
        info["linear_preconditioned_taken"] = info.get("linear_preconditioned_taken", 0) + 1
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
                f"and the exact solve by its cycles could not be made: {found.why}" + _preconditioned_words(found.preconditioned),
                INF,
            )
        if found.residual >= info.get("linear_limit", {}).get("residual", 0.0):  # (the worst of the evaluations of a solve is the one that is said)
            # taken as it is; the certificate that follows bounds the error of the values. `amplification`: the forward estimate over the backward error
            amplification = max(1.0, found.forward / found.backward) if found.backward > 0.0 and math.isfinite(found.forward) else max(1.0, float(np.max(np.abs(found.x))) / max(float(np.max(np.abs(rhs))), 1e-300))
            info["linear_limit"] = {"states": m, "residual": found.residual, "amplification": amplification, "why": found.why, **found.cost}
    values[states] = found.x
    return values


CORRECTION_ERROR = 0.25  # the forward error a correction of `corrected` is taken at: it is added to values the certificate then judges, so a rough one serves
CORRECTIONS = 2  # the corrections of a solve the certificate refuses: the second gains what the first one's own rounding left; a third gains nothing


def corrected(work: Work, leave: np.ndarray, policy: np.ndarray, value: np.ndarray, dense_limit: int, info: dict) -> np.ndarray | None:
    """`value` with one step of iterative refinement of the `policy`'s equation, its residual taken with every sum rounded once (ticket #867), or None
    when those sums cannot be taken or the correction has no finite answer.

    An evaluation leaves an error of some hundred roundings of the value (1e-13 of it, by its own measures: a backward error, a forward estimate). The
    certificate divides the residual by the cost of a step, so on a plan worth 10^7 steps that error alone is 1e-6. The residual `r = c + P V - V` of
    the policy, taken with sums that carry one rounding, is known to `4 eps V`; the correction `dx` of `(I - P) dx = r` is the error itself to a few
    digits, and `V + dx` has a residual at the rounding of the values. The equation is the evaluation's (the chance to stay divided out) with `r` in
    place of the cost, solved to `CORRECTION_ERROR` only: nothing rests on the correction, the certificate measures what it gave.
    """
    states = np.flatnonzero(policy >= 0)
    m = len(states)
    if m == 0:
        return None
    graph = work.g
    sums = kernel_sums_rounded_once(graph, value)
    if sums is None:
        return None
    chosen = policy[states]
    residual = (graph.act_cost[chosen] + sums[graph.act_kernel[chosen]]) - value[states]
    position = np.full(work.n, m, dtype=np.int64)
    position[states] = np.arange(m)
    terms = _PolicyTerms(work, leave, chosen, states, position, m <= dense_limit, {})
    found = _packed_linear.solve(terms, residual / leave[chosen], dense_limit=dense_limit, tol=CORRECTION_ERROR, iterate_tol=1e-8, info=info)
    if found.x is None or not np.all(np.isfinite(found.x)):
        return None
    out = value.copy()
    out[states] += found.x
    if np.any(out[states] < 0.0):
        return None
    return out


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
    refuse_above: float | None = None,
    late: Callable[[], bool] | None = None,
) -> Core:
    """Policy iteration on `graph` itself (no merge): see the module docstring, steps 2 to 5.

    `start_policy` (an action index of the graph for each state, -1 where none) and `start_value` (a vector of values to start the first evaluation
    from) warm-start the iteration with those of a nearby graph, as the envelope search does round after round. The policy need not be proper on this
    graph: `warm_policy` keeps it where it is and replaces it where it is not, and proves the result proper. The answer does not depend on the start
    (the same fixed point, to the certified error), only the work. `self_mass[a]` is the chance that action `a`'s kernel gives the state of `a` (see
    `Work.self_mass`), for a caller that knows it from building the kernels.

    `refuse_above` (default: `accept_bound`) is the certified bound above which the solve is refused, for a caller that takes every figure with
    its certified error (`value * (1 - bound) <= V* <= value * (1 + bound)`) and so needs the bound only small next to what it compares (#867).
    The work is the same whatever it is: the certificate, its finer measures and the corrections all aim at `accept_bound`.

    `late` (None for none) says whether the caller's time limit has passed (OR-40, #1516), on the caller's own clock: the solve asks it between two
    of its steps (each sweep of `proper_states` after the first and each `PASS_ASK` states of its shortest-path pass, each round of policy
    iteration after the first, each refinement and correction, and before the exact solve) and raises `Late`, a `ConvergenceError` with no figure,
    once it says so. A step that has begun runs to its end (one sweep, one evaluation of the policy and its improvement, one certificate, one
    correction, never the exact solve once late), so the solve goes
    past the limit by at most one such step: on R17's 210,847 states a sweep takes about 3 ms, an evaluation about 0.1 s.
    """
    refuse_above = accept_bound if refuse_above is None else max(refuse_above, accept_bound)
    say = progress or (lambda _text: None)
    info = {} if info is None else info
    began = time.perf_counter()
    on_time = None if late is None else _deadline(late, began)
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
        inside, ok, distance, policy = proper_states(work, alive, effective, on_time)
        value = np.where(inside, np.where(np.isfinite(distance), distance, 0.0), 0.0)
    else:
        inside, ok, policy = warm_policy(work, alive, effective, np.asarray(start_policy), info, start_value, leave, on_time)
        value = np.zeros(n) if start_value is None else np.where(inside & np.isfinite(start_value), start_value, 0.0)
    info["seconds_proper"] = _tick() - mark
    say(f"proper states: {int(inside.sum()):,} of {n:,} ({time.perf_counter() - began:.1f} s)")
    terms = work.state_reduce(np.maximum, work.asize.astype(np.float64) + 1.0, 0.0)
    noise = (terms + 2.0) * EPS
    rounds = 0
    while rounds < max_rounds:
        if rounds and on_time is not None:
            on_time("a round of policy iteration")
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
        if on_time is not None:
            on_time("a refinement of the values")
        refinements += 1
        value = evaluate_policy(work, leave, policy, value, dense_limit, 1e-15, info)
        certificate = certify(graph, value, inside, work, accept_bound)
    info["refinements"] = refinements
    corrections = 0
    while not certificate.bound <= accept_bound and corrections < CORRECTIONS:  # only a plan that would be refused: one that certified keeps its numbers to the bit
        if on_time is not None:
            on_time("a correction of the values")
        finer = corrected(work, leave, policy, value, dense_limit, info)
        if finer is None:
            break
        again = certify(graph, finer, inside, work, accept_bound)
        if not again.bound < certificate.bound:
            break
        value, certificate, corrections = finer, again, corrections + 1
    info["corrections"] = corrections
    if not certificate.bound <= refuse_above:  # also false for an infinite or undefined bound
        if on_time is not None:
            on_time("the exact solve in rational numbers")
        exact = _exact(graph, inside, info)  # values float64 cannot certify: the optimum in rational numbers on the quotient, when it is small (#1380)
        if exact is not None and exact.certificate.bound <= refuse_above:  # (its one rounding: a caller that accepts no error at all is refused still)
            say(f"solved exactly in rational numbers on {info['exact_classes']:,} classes: the float64 certificate gave only {certificate.bound:.3g}")
            return exact
        raise ConvergenceError(
            f"the policy iteration on {n:,} states certifies only a relative bound of {certificate.bound:.3g} "
            f"(asked: tolerance {tolerance}, accepted: {refuse_above}; residual {certificate.residual:.3g} of its margin){_own_text(certificate)}; "
            "the exact solve in rational numbers did not apply (its states merge into too many classes, or its kernels' weights are too large, or it has a free action)",
            certificate.bound,
        )
    info["quotient_own_bound"], info["quotient_own_cost"] = certificate.own_bound, certificate.own_cost
    say(f"certificate on the quotient: bound {certificate.bound:.3g}{_own_text(certificate)} ({time.perf_counter() - began:.1f} s)")
    value = np.where(inside, value, INF)
    return Core(value, inside, np.where(inside & ~graph.goal, policy, -1), certificate)


def _deadline(late: Callable[[], bool], began: float) -> Callable[[str], None]:
    """What `solve_graph` asks between two steps: it raises `Late`, naming the step it stopped before, once `late()` says the time is up."""

    def ask(step: str) -> None:
        if late():
            now = time.perf_counter()
            raise Late(
                f"the solve stopped at its caller's time limit after {now - began:.1f} s, before {step} (it asks the clock between two steps)",
                now - began, step,
            )

    return ask


def _exact(graph: PackedGraph, inside: np.ndarray, info: dict) -> Core | None:
    """The `Core` of `_packed_exact.exact_quotient` (the exact optimum over the proper states, its values rounded once), or None when it
    does not apply (a quotient of more than `EXACT_CLASSES` classes)."""
    found = exact_quotient(graph, inside)
    if found is None:
        return None
    value, solved, reduced, kernel_map, cls, class_action = found
    info["exact_classes"] = reduced.n
    action = lift_policy(graph, reduced, kernel_map, cls, class_action)
    action = np.where(solved & ~graph.goal, action, -1)
    return Core(np.where(solved, value, INF), solved, action, Certificate(EPS, 1.0 - EPS, 1.0 + EPS, 0.0, True, exact=True))


def solve_packed(
    graph: PackedGraph,
    *,
    tolerance: float = 1e-10,
    dense_limit: int = DENSE_LIMIT,
    max_rounds: int = 500,
    accept_bound: float = ACCEPT_BOUND,
    merge: bool = True,
    progress: Callable[[str], None] | None = None,
    refuse_above: float | None = None,
    late: Callable[[], bool] | None = None,
) -> PackedSolution:
    """Minimise the mean cost to a goal from every state of `graph`: merged exactly, solved, certified on the unmerged graph.

    `tolerance` is the stopping threshold on the residual of the Bellman operator relative to the cheapest action of a state
    (as `solve`'s): the evaluation of the policy is refined while it is above it and not at the rounding floor. The certified
    bound of the result (`error_bound`) may exceed `tolerance` by the rounding of the sums, but a bound above `accept_bound`
    (or none) raises `ConvergenceError`; `refuse_above` moves that refusal for a caller that takes the values with `error_bound` (`solve_graph`).
    `late` is `solve_graph`'s: the solve of the quotient raises `Late` once it says the time is up (#1553).
    """
    refuse_above = accept_bound if refuse_above is None else max(refuse_above, accept_bound)
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
        reduced, tolerance=tolerance, dense_limit=dense_limit, max_rounds=max_rounds, accept_bound=accept_bound, progress=say, info=info,
        refuse_above=refuse_above, late=late,
    )  # fmt: skip
    info["solve_seconds"] = round(time.perf_counter() - mark, 2)
    cls = classes.cls
    value = core.value[cls]
    solved = core.solved[cls]
    mark = time.perf_counter()
    # an exact solve of the quotient is the exact optimum of the graph (the merge is exact); float64 cannot measure it again (#1380)
    certificate = core.certificate if core.certificate.exact else certify(graph, value, solved, wanted=accept_bound)
    info["certify_seconds"] = round(time.perf_counter() - mark, 2)
    info["quotient_bound"] = core.certificate.bound
    if not certificate.bound <= refuse_above and core.certificate.bound <= refuse_above and reduced is not graph and _lumps(graph, cls, reduced, kernel_map, info):
        # float64 cannot measure on the whole graph what it measured on the quotient (#1412): a class whose members pass a run among themselves
        # is one state with a self-loop on the quotient, divided out there (`_divided`), and a cycle of many states here, whose margin is one
        # step. The merge, checked exact in integers on the graph itself, carries the quotient's certificate to the members
        info["graph_bound"] = certificate.bound
        certificate = replace(core.certificate, lumped=certificate.bound)
    if not certificate.bound <= refuse_above:
        raise ConvergenceError(
            f"the values of the merged graph do not satisfy the Bellman equation of the whole graph to {refuse_above} "
            f"(bound {certificate.bound:.3g}, residual {certificate.residual:.3g} of its margin): the merge or the solve is wrong",
            certificate.bound,
        )
    info["own_bound"], info["own_cost"] = certificate.own_bound, certificate.own_cost
    say(f"certificate on the whole graph: bound {certificate.bound:.3g}{_own_text(certificate)} ({info['certify_seconds']} s)")
    action = lift_policy(graph, reduced, kernel_map, cls, core.action)
    info["seconds"] = round(time.perf_counter() - began, 2)
    return PackedSolution(value, action, certificate.bound, classes.count, reduced, cls, core.action, info)


def packed_of_core(graph: PackedGraph, core: Core, core_info: dict | None = None, *, merge: bool = True, progress: Callable[[str], None] | None = None) -> PackedSolution:
    """`solve_packed`'s answer for a graph its caller has solved already: `core` is `solve_graph`'s on `graph` itself, so its values, its
    policy and its certificate are of the whole graph. The graph is merged into its exact classes (what the lumped chain of the answer and its
    risk read), and each class takes the distribution its first member's action has in `core`; nothing is solved again (#1566). `core_info` is
    the `info` that solve filled: the answer keeps what it says of the solve (`linear_limit`, the limit that names costs found by approximation).

    The envelope search prices the plan in hand by `solve_graph` (`_envelope.Search._upper`); after a stop at its net, solving the same graph
    again for the answer cost R17 283 s past its net (the merge 6 s, the policy iteration on 152,294 classes 269 s, the certificates 3 s)."""
    say = progress or (lambda _text: None)
    info: dict = {"states": graph.n, "actions": graph.num_actions, "kernels": graph.num_kernels, "edges_stored": graph.num_edges, "priced_before": True}
    info = {**(core_info or {}), **info}
    began = time.perf_counter()
    classes = exact_classes(graph, say) if merge else identity_classes(graph)
    reduced, kernel_map = quotient(graph, classes)
    info.update(
        classes=classes.count, merge_rounds=classes.rounds, merge_seconds=round(time.perf_counter() - began, 2),
        quotient_actions=reduced.num_actions, quotient_edges_stored=reduced.num_edges,
    )
    cls = classes.cls
    first = np.unique(cls, return_index=True)[1].astype(np.int64)
    taken = np.asarray(core.action, dtype=np.int64)[first]
    wanted = np.where(taken >= 0, kernel_map[graph.act_kernel[np.maximum(taken, 0)]], -1) if graph.num_actions else np.full(len(first), -1, dtype=np.int64)
    class_action = np.full(reduced.n, -1, dtype=np.int64)
    has = np.diff(reduced.act_ptr) > 0
    if reduced.num_actions:
        owner = np.repeat(np.arange(reduced.n, dtype=np.int64), np.diff(reduced.act_ptr))
        hit = np.where(reduced.act_kernel == wanted[owner], np.arange(reduced.num_actions), reduced.num_actions)
        found = np.full(reduced.n, reduced.num_actions, dtype=np.int64)
        found[has] = np.minimum.reduceat(hit, reduced.act_ptr[:-1][has])
        class_action = np.where((wanted >= 0) & (found < reduced.num_actions), found, -1)
    certificate = core.certificate
    info["own_bound"], info["own_cost"], info["quotient_bound"] = certificate.own_bound, certificate.own_cost, certificate.bound
    action = lift_policy(graph, reduced, kernel_map, cls, class_action)
    info["seconds"] = round(time.perf_counter() - began, 2)
    say(
        f"merged {graph.n:,} states into {classes.count:,} classes, {reduced.num_actions:,} actions; the plan is the one the search priced, "
        f"bound {certificate.bound:.3g}, not solved again ({info['seconds']} s)"
    )
    return PackedSolution(np.asarray(core.value, dtype=np.float64), action, certificate.bound, classes.count, reduced, cls, class_action, info)


def _lumps(graph: PackedGraph, cls: np.ndarray, reduced: PackedGraph, kernel_map: np.ndarray, info: dict) -> bool:
    """`lumps_exactly`, its seconds in `info["lump_check_seconds"]` (it runs only when the whole graph's measure refused)."""
    mark = time.perf_counter()
    found = lumps_exactly(graph, cls, reduced, kernel_map)
    info["lump_check_seconds"] = round(time.perf_counter() - mark, 2)
    return found


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
