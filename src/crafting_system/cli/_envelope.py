"""The envelope search: the exact branch-and-bound of OR-12 on a lower bound that needs no walk (ticket #377, ADR-0063 point 4).

The full walk expands every state a route can reach (R14: 816,153) and every action of each. The envelope search expands only the states, and
of those only the actions, that the bound cannot rule out, and stops when the root's best action is proved. It is generic: a `Problem` gives
the start, the goal test, a lower bound of a state's value, the offers of a state with a lower bound of each, and the kernel of an offer; the
crafting problem (`_envelope_plan`) fills these from the `Abstraction` and the walk-free bound of #497, and the tests fill them from random graphs.

**The two bounds.** `lb(s) <= V*(s)` for every state and `la(s, a) <= Q*(s, a)` for every offer `a` of `s`, where `V*` is the optimal expected
cost to a goal with restarts (a fixed point of the Bellman operator: restarts make cycles) and `Q*(s, a) = c(a) + sum p(s'|s, a) V*(s')`.
Both come from the optimistic model of #497: a concrete action is no cheaper than the best abstract action of its offer at its key.

**The lower graph.** Every state known is a node. A node whose actions have not been looked at (a *tip*) has one fake action, cost `lb`, to the
goal. An *expanded* node has the actions *realized* so far (their exact kernels) and, if some are not realized yet, one fake action to the goal
whose cost is the least `la` among them. This is a stochastic shortest path problem (SSP) whose value `L` satisfies `L(s) <= V*(s)`: it is
`V*` of a game in which the fake actions are shortcuts that cost no more than the truth. It is solved by policy iteration with a certified
residual (`solver._packed_solve.solve_graph`), cycles and restarts included. Each round replaces fake actions by real ones, so `L` rises (the
bound is consistent: it solves the model's own Bellman equation, and a concrete action is no cheaper than the model's) and never passes `V*`.

**The cut.** An offer is realized at a state only when it is the greedy action of the lower graph (least `Q_L`, that is, the least lower cost)
and no realized action beats it, or while its lower bound `la` is below the best realized `Q_L`. An offer whose `la` exceeds `V*(s)` is therefore
never realized: the optimal action has `Q_L <= Q* = V*(s)`, so it is cheaper than that offer at every round. This is the cut of ADR-0063 point 4
("an action is not expanded when its cost with lower bounds exceeds the best action's cost with upper bounds"), made with the upper bound
`U >= V*` replaced by the stronger `V*` it stands for; the upper bound of an executable policy (the given route completed with a restart, or the
restart at every tip) does not move the cut. It is what a stop returns (below). A state is expanded only when the greedy policy of the lower graph
reaches it. Nothing is cut by a number: no tolerance, no lumping by chance.

**Why the mean is exact.** Each round takes the greedy policy `pi` of the lower graph. If it reaches no fake action, every state it reaches is
expanded and the action it takes there is realized: `pi` is a policy of the real graph. The lower graph restricted to its reach is then exactly the
evaluation equation of `pi`, so `L(root) = V^pi(root)`, the value of an executable policy, and `L(root) <= V*(root) <= V^pi(root)`: `pi` is optimal
and its mean is pinned by `LB = UB`, with no state of the optimal policy unexpanded. (The reach of `pi` is the whole of what the answer needs; the
rest of the expanded graph is waste of earlier rounds, not a part of the proof.) Until then `L(root)` is the lower bound `LB` of the certificate
`[LB, U]` (ticket #499; the seam is `SearchResult.lower` and `SearchResult.upper`).

**A guard for the bound.** A consistent bound only rises round after round. `SearchStats.largest_fall` is the largest relative fall of `L(root)` that a
round caused; `envelope_result` refuses (`BoundError`) when it is above `FALL_LIMIT` (the solver's own rounding is far below it), because a bound that
falls is not a lower bound of anything a cut may rest on. The guard sees only a fall; a bound too high but still consistent is not seen (the tests plant
one and the comparison with the dense optimum is what catches it).

**Convergence.** Each round expands at least one tip or realizes at least one offer (a greedy fake action at an expanded node always realizes the
first offer it stands for, even on a tie), and both are finite: the search ends, in at most as many rounds as the graph has (state, offer) pairs.
In practice a round expands the whole frontier of the greedy policy, so the rounds are about the depth of the optimal policy. Within a round the
bounds are fixed points computed to the solver's certified relative error (`L` is taken `(1 - error)` lower; the offers' `la` are taken `SLACK`
lower), so a cut never rests on a rounding: a bound moves only up (`L`) and every comparison that decides a cut is against a value that was
lowered by what the solver cannot certify.

**The upper bound, and the stop-and-say-so net.** `U` is the value of a policy that can be executed: the realized actions plus, at every state
but the start, the restart (buy the start item again) when the start item is bought. A tip then restarts (its upper bound is the start price plus
the start value, a fixed point of the same graph), and a given route, completed with a restart, is the same policy with its actions realized first
(`incumbent`). A start that is given has no restart: a tip has no executable action, and `U` is infinite until the greedy policy closes, which says
so. A time, memory or state net (`Net`) ends the search between rounds; the answer is then the best executable policy and `exact` is False.
"""

import math
import sys
import time
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from crafting_system.solver import PackedGraph, policy_reach
from crafting_system.solver._packed import BIG_TOTAL, assemble
from crafting_system.solver._packed_solve import solve_graph

FLOOR = 1e-200  # a fake action of bound 0 is carried at this cost: the certificate divides by the cheapest cost of a state (a rise of 1e-200 moves no cut)
FAKE = -1  # the tag of a fake action (a tip's bound, or the least bound of the offers not realized yet)
SLACK = 1e-9  # the lower bound of an offer is taken this much lower in relative terms (rounding of the model's sums; only ever costs a tie)
FALL_LIMIT = 1e-6  # a relative fall of `L(root)` above this is no rounding: the bound is not consistent (`SearchStats.largest_fall`)
VERIFY_FIRST = 20  # the first this many shared kernels are checked against a fresh kernel ...
VERIFY_EVERY = 4_096  # ... and then one in this many (a `kernel_key` promises equal kernels at one state; the search shares them across states)


class Refused(Exception):
    """The offer has no action at this state: the game refuses it, or the model has no rule for it there (the problem has noted which)."""


class Problem[S](Protocol):
    """What the search asks of a problem. States are hashable; positions are the offers' indexes."""

    start: S
    restart: int | None  # the position of the offer that returns to `start` for its price, None when the start item is given

    def is_goal(self, state: S) -> bool: ...

    def lower(self, state: S) -> float:
        """A lower bound of the state's optimal value (0 is always one)."""
        ...

    def candidates(self, state: S) -> Sequence[tuple[float, int]]:
        """`(la, position)` for each offer that may be an action of `state`; `la` is a lower bound of its `Q*` (at most `Q*` of the state)."""
        ...

    def cost(self, position: int) -> float: ...

    def kernel_key(self, state: S, position: int) -> Hashable | None:
        """Equal keys at two states promise equal kernels (`None`: no sharing). Raises `Refused`."""
        ...

    def kernel(self, state: S, position: int) -> dict[S, int]:
        """The outcomes with positive integer weights. Raises `Refused`."""
        ...

    def release(self) -> None:
        """Called after the work at one state, to let the problem drop what it cached for it."""
        ...


@dataclass(frozen=True)
class Net:
    """A stop-and-say-so safety net (OR-12): the search stops between two rounds once one is reached. None of them has a default."""

    seconds: float | None = None
    states: int | None = None  # states known (touched)
    memory_mb: float | None = None


@dataclass
class SearchStats:
    rounds: int = 0
    touched: int = 0  # states known, tips included
    expanded: int = 0  # states whose offers were listed
    realized: int = 0  # (state, offer) pairs whose kernel was built
    candidates: int = 0  # (state, offer) pairs that could have been (what a full expansion of the expanded states would build)
    kernels: int = 0
    lower_history: list[float] = field(default_factory=list)  # `L(root)` after each round
    largest_fall: float = 0.0  # the largest relative fall of `L(root)` from one round to the next: 0 for a consistent bound (it only rises)
    first_upper: float | None = None  # the value of the incumbent's policy (or the restart policy), when one was asked for
    solve_seconds: float = 0.0
    build_seconds: float = 0.0
    expand_seconds: float = 0.0
    verified: int = 0
    peak_mb: float | None = None


@dataclass(frozen=True, eq=False)
class SearchResult[S]:
    """The graph the search ended with, as a packed graph over `states` (the start is 0): tips are dead ends, or restart where `restarts`.

    `exact`: the greedy policy reaches only expanded states and its mean is the optimum, pinned by `lower == upper` to the solver's certified
    error. Otherwise `stopped` says which net ended the search and the graph holds the best executable policy (the restart at every tip).
    `lower` is `L(root)` less its certified error (the `LB` of the certificate `[LB, U]`); `upper` is None until a policy was executed (the caller
    solves the graph and reads the value).
    """

    states: list[S]
    index: dict[S, int]
    graph: PackedGraph
    lower: float
    exact: bool
    stopped: str | None
    restarts: bool
    stats: SearchStats


def resident_mb() -> float | None:
    """The resident memory of this process in MB, or None where it cannot be read."""
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024
    except ImportError:
        return None


class Search[S]:
    """The envelope search of a `Problem`: see the module text."""

    def __init__(
        self,
        problem: Problem[S],
        *,
        net: Net | None = None,
        incumbent: Callable[[S], Sequence[int]] | None = None,
        progress: Callable[[str], None] | None = None,
        tolerance: float = 1e-10,
    ) -> None:
        self.p = problem
        self.net = net or Net()
        self.incumbent = incumbent
        self.say = progress or (lambda _text: None)
        self.tolerance = tolerance
        self.stats = SearchStats()
        self.states: list[S] = []
        self.index: dict[S, int] = {}
        self.goal = bytearray()
        self.expanded = bytearray()
        self.lb = np.zeros(1024)
        self.rows: dict[int, list[tuple[int, float, int]]] = {}  # expanded node -> realized (position, cost, kernel)
        self.cands: dict[int, list[tuple[float, int]]] = {}  # expanded node -> offers not realized yet, the least `la` last
        self.k_succ: list[np.ndarray] = []
        self.k_wt: list = []  # int64 arrays, or a tuple of Python ints for a kernel whose weights add up to BIG_TOTAL or more
        self.k_prob: list[np.ndarray] = []
        self.shared: dict[Hashable, int] = {}
        self.hits = 0
        self.values: np.ndarray | None = None  # the solved lower graph (node n_solved is the goal node)
        self.n_solved = 0
        self.restart_kernel: int | None = None
        self._last_root: float | None = None
        self.intern(problem.start)

    # ---- nodes and kernels --------------------------------------------------------------------------------------

    def intern(self, state: S) -> int:
        found = self.index.get(state)
        if found is None:
            found = self.index[state] = len(self.states)
            self.states.append(state)
            goal = self.p.is_goal(state)
            self.goal.append(1 if goal else 0)
            self.expanded.append(0)
            if found >= len(self.lb):
                self.lb = np.concatenate((self.lb, np.zeros(len(self.lb))))
            self.lb[found] = 0.0 if goal else self.p.lower(state)
        return found

    def _store(self, successors: list[int], weights: list[int]) -> int:
        total = 0
        for w in weights:
            total += w
        if total >= BIG_TOTAL:
            self.k_wt.append(tuple(int(w) for w in weights))
            chance = np.array([w / total for w in weights])  # exact big-integer ratios, rounded once
        else:
            self.k_wt.append(np.asarray(weights, dtype=np.int64))
            chance = np.asarray(weights, dtype=np.float64) / float(total)
        self.k_succ.append(np.asarray(successors, dtype=np.int64))
        self.k_prob.append(chance)
        self.stats.kernels += 1
        return len(self.k_succ) - 1

    def _fresh_equal(self, state: S, position: int, kid: int) -> bool:
        weights = self.p.kernel(state, position)
        got = {self.states[int(s)]: w for s, w in zip(self.k_succ[kid], self._exact_weights(kid))}
        return got == dict(weights)

    def _exact_weights(self, kid: int):
        wt = self.k_wt[kid]
        return wt if isinstance(wt, tuple) else [int(w) for w in wt]

    def _kernel(self, i: int, position: int) -> int:
        """The kernel id of offer `position` at node `i`, built once for each distinct `kernel_key`. Raises `Refused`."""
        state = self.states[i]
        key = self.p.kernel_key(state, position)
        kid = self.shared.get(key) if key is not None else None
        if kid is not None:
            self.hits += 1
            if self.hits <= VERIFY_FIRST or self.hits % VERIFY_EVERY == 0:
                self.stats.verified += 1
                if not self._fresh_equal(state, position, kid):
                    raise ValueError(f"two states share the kernel key {key!r} but not its kernel (checked at {state!r})")
            return kid
        weights = self.p.kernel(state, position)
        kid = self._store([self.intern(s) for s in weights], list(weights.values()))
        if key is not None:
            self.shared[key] = kid
        return kid

    # ---- expanding and realizing --------------------------------------------------------------------------------

    def expand(self, i: int) -> None:
        """List the offers of node `i` with their lower bounds; nothing is realized yet."""
        self.expanded[i] = 1
        listed = sorted(self.p.candidates(self.states[i]), key=lambda c: (c[0], c[1]), reverse=True)
        self.cands[i] = [(la * (1.0 - SLACK), position) for la, position in listed]
        self.rows[i] = []
        self.stats.expanded += 1
        self.stats.candidates += len(listed)

    def _value(self, ids: np.ndarray) -> np.ndarray:
        """The lower value of nodes: the last solve's where there is one, else their bound."""
        out = self.lb[ids].copy()
        if self.values is not None:
            known = ids < self.n_solved
            out[known] = self.values[ids[known]]
        return out

    def _q(self, cost: float, kid: int) -> float:
        return cost + float(self.k_prob[kid] @ self._value(self.k_succ[kid]))

    def realize(self, i: int, force: bool) -> None:
        """Realize the offers of node `i` whose lower bound is below the best realized lower cost (the first one regardless, with `force`)."""
        rows, cands = self.rows[i], self.cands[i]
        best = min((self._q(c, kid) for _, c, kid in rows), default=math.inf)
        first = force
        while cands and (first or cands[-1][0] < best):
            first = False
            _, position = cands.pop()
            try:
                kid = self._kernel(i, position)
            except Refused:
                continue
            cost = self.p.cost(position)
            rows.append((position, cost, kid))
            self.stats.realized += 1
            best = min(best, self._q(cost, kid))

    def _seed(self) -> None:
        """Realize the incumbent's action along its chain from the start: the policy that gives a finite upper bound from the first round."""
        assert self.incumbent is not None
        queue = [0]
        seen = {0}
        for i in queue:
            if self.goal[i]:
                continue
            if not self.expanded[i]:
                self.expand(i)
            rows, cands = self.rows[i], self.cands[i]
            for position in self.incumbent(self.states[i]):
                held = [c for c in cands if c[1] == position]
                if not held:
                    continue
                try:
                    kid = self._kernel(i, position)
                except Refused:
                    continue
                cands.remove(held[0])
                rows.append((position, self.p.cost(position), kid))
                self.stats.realized += 1
                for j in self.k_succ[kid].tolist():
                    if j not in seen:
                        seen.add(j)
                        queue.append(j)
                break
            self.p.release()

    # ---- the graphs ---------------------------------------------------------------------------------------------

    def _graph(self, mode: str) -> PackedGraph:
        """The packed graph over the nodes: `lower` (fakes, plus a goal node at the end), `upper` (restart at every node but the start) or
        `exact` (realized actions only, tips are dead ends)."""
        n = len(self.states)
        lower = mode == "lower"
        upper = mode == "upper" and self.p.restart is not None
        goal = np.frombuffer(bytes(self.goal), dtype=np.uint8).astype(bool)
        expanded = np.frombuffer(bytes(self.expanded), dtype=np.uint8).astype(bool)
        nodes = n + 1 if lower else n
        counts = np.zeros(nodes, dtype=np.int64)
        tip = ~goal & ~expanded
        bound = self.lb[:n]
        if lower:
            counts[:n][tip & np.isfinite(bound)] = 1
        if upper:
            counts[:n][tip] = 1
            counts[0] = 0
        ids = np.fromiter(self.rows.keys(), dtype=np.int64, count=len(self.rows))
        ids.sort()
        tags: list[int] = []
        costs: list[float] = []
        kernels: list[int] = []
        sizes = np.zeros(len(ids), dtype=np.int64)
        fake_kernel = len(self.k_succ)
        restart = self.p.restart
        for slot, i in enumerate(ids.tolist()):
            rows = self.rows[i]
            made = 0
            if not goal[i]:
                for position, cost, kid in rows:
                    tags.append(position)
                    costs.append(cost)
                    kernels.append(kid)
                    made += 1
                if lower:
                    held = self.cands[i]
                    if held and math.isfinite(held[-1][0]):
                        tags.append(FAKE)
                        costs.append(max(held[-1][0], FLOOR))
                        kernels.append(fake_kernel)
                        made += 1
                elif upper and i != 0 and not any(position == restart for position, _, _ in rows):
                    tags.append(restart)
                    costs.append(self.p.cost(restart))
                    kernels.append(self.restart_kernel)
                    made += 1
            sizes[slot] = made
        counts[ids] = sizes
        ptr = np.concatenate(([0], np.cumsum(counts)))
        total = int(ptr[-1])
        act_tag = np.zeros(total, dtype=np.int32)
        act_cost = np.zeros(total)
        act_kernel = np.zeros(total, dtype=np.int32)
        if len(tags):
            offsets = np.repeat(ptr[ids], sizes) + (np.arange(len(tags)) - np.repeat(np.cumsum(sizes) - sizes, sizes))
            act_tag[offsets] = tags
            act_cost[offsets] = costs
            act_kernel[offsets] = kernels
        tip_ids = np.flatnonzero(tip)
        if lower:
            tip_ids = tip_ids[np.isfinite(bound[tip_ids])]
            at = ptr[tip_ids]
            act_tag[at], act_cost[at], act_kernel[at] = FAKE, np.maximum(bound[tip_ids], FLOOR), fake_kernel
        elif upper:
            tip_ids = tip_ids[tip_ids != 0]
            at = ptr[tip_ids]
            act_tag[at], act_cost[at], act_kernel[at] = restart, self.p.cost(restart), self.restart_kernel
        succ = list(self.k_succ)
        wt = list(self.k_wt)
        if lower:
            succ.append(np.array([n], dtype=np.int64))
            wt.append(np.array([1], dtype=np.int64))
        goal_flags = np.concatenate((goal, [True])) if lower else goal
        return assemble(goal_flags, ptr, act_tag, act_cost, act_kernel, succ, wt)

    def upper_value(self) -> float:
        """The value of the best executable policy of the graph now (restart at every tip): infinite when the start item is given and none closes."""
        if self.p.restart is None:
            return math.inf
        core = solve_graph(self._graph("upper"), tolerance=self.tolerance)
        return float(core.value[0])

    # ---- the rounds ---------------------------------------------------------------------------------------------

    def _net(self, began: float) -> str | None:
        net = self.net
        if net.seconds is not None and time.perf_counter() - began >= net.seconds:
            return f"the time limit of {net.seconds:g} seconds was reached"
        if net.states is not None and len(self.states) >= net.states:
            return f"{len(self.states):,} states were known, the limit is {net.states:,}"
        if net.memory_mb is not None:
            used = resident_mb()
            if used is not None and used >= net.memory_mb:
                return f"the process held {used:,.0f} MB, the limit is {net.memory_mb:,.0f} MB"
        return None

    def run(self) -> SearchResult[S]:
        began = time.perf_counter()
        if self.p.restart is not None:
            self.restart_kernel = self._store([0], [1])
        if self.incumbent is not None and not self.goal[0]:
            self._seed()
            upper = self.upper_value()
            self.stats.first_upper = upper if math.isfinite(upper) else None
            self.say(f"incumbent: {self.stats.realized:,} actions realized along its chain, value {upper!r}")
        stopped = None
        lower = 0.0
        while True:
            mark = time.perf_counter()
            graph = self._graph("lower")
            self.stats.build_seconds += time.perf_counter() - mark
            mark = time.perf_counter()
            core = solve_graph(graph, tolerance=self.tolerance)
            self.stats.solve_seconds += time.perf_counter() - mark
            self.values = core.value
            self.n_solved = len(self.states)
            self.stats.rounds += 1
            lower = float(core.value[0]) * (1.0 - core.certificate.bound)
            root = float(core.value[0])
            if self._last_root is not None and math.isfinite(root) and self._last_root > 0:
                self.stats.largest_fall = max(self.stats.largest_fall, (self._last_root - root) / self._last_root)
            self._last_root = root
            self.stats.lower_history.append(lower)
            if not math.isfinite(root):
                raise NoPolicy("no policy of the offers reaches the goal from the start")
            reach = policy_reach(graph, core.action, 0)
            acting = reach[core.action[reach] >= 0]
            fake = acting[graph.act_tag[core.action[acting]] == FAKE]
            used = resident_mb()
            if used is not None:
                self.stats.peak_mb = max(self.stats.peak_mb or 0.0, used)
            self.say(
                f"round {self.stats.rounds}: L(root) {root!r}, {len(fake):,} tips of {len(acting):,} acting states, {len(self.states):,} known, "
                f"{self.stats.expanded:,} expanded, {self.stats.realized:,} realized ({time.perf_counter() - began:.0f} s)"
            )
            if not len(fake):
                self.stats.touched = len(self.states)
                return SearchResult(self.states, self.index, self._graph("exact"), lower, True, None, False, self.stats)
            stopped = self._net(began)
            if stopped is not None:
                break
            mark = time.perf_counter()
            for i in fake.tolist():
                if not self.expanded[i]:
                    self.expand(i)
                self.realize(i, force=True)
                self.p.release()
            self.stats.expand_seconds += time.perf_counter() - mark
        self.stats.touched = len(self.states)
        if self.p.restart is None:
            raise NoPolicy(f"the search stopped ({stopped}) before any policy closed, and the start item is given, so there is no restart to fall back on")
        if not math.isfinite(self.upper_value()):
            raise NoPolicy(f"the search stopped ({stopped}) before any policy that can be executed was found: it had looked at {self.stats.expanded:,} states")
        return SearchResult(self.states, self.index, self._graph("upper"), lower, False, stopped, True, self.stats)


class NoPolicy(ValueError):
    """The search found no policy that reaches the goal (or none before a net stopped it, with no restart to complete it)."""


__all__ = ["FAKE", "FALL_LIMIT", "Net", "NoPolicy", "Problem", "Refused", "Search", "SearchResult", "SearchStats", "resident_mb"]
