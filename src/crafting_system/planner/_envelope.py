"""The envelope search: the branch-and-bound of OR-12 on a lower bound that needs no walk, two-sided since #826 (ticket #377, ADR-0063 point 4).

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
`U >= V*` replaced by the stronger `V*` it stands for; the upper bound of an executable policy (the completed route of the guide, or the
restart at every tip) does not move the cut. It is what a stop returns (below). A state is expanded only when the greedy policy of the lower graph
reaches it, or when the first plan does (below: the least-`la` offer of a state has `la <= V*` there, so the cut's statement holds for it too).
Nothing is cut by a number: no tolerance, no lumping by chance. The stop at a proved gap (below) cuts nothing either: it ends the proof early.

**Why the mean is exact.** Each round takes the greedy policy `pi` of the lower graph. If it reaches no fake action, every state it reaches is
expanded and the action it takes there is realized: `pi` is a policy of the real graph. The lower graph restricted to its reach is then exactly the
evaluation equation of `pi`, so `L(root) = V^pi(root)`, the value of an executable policy, and `L(root) <= V*(root) <= V^pi(root)`: `pi` is optimal
and its mean is pinned by `LB = UB`, with no state of the optimal policy unexpanded. (The reach of `pi` is the whole of what the answer needs; the
rest of the expanded graph is waste of earlier rounds, not a part of the proof.) Until then `L(root)` is the lower bound `LB` of the certificate
`[LB, U]` (ticket #499; the seam is `SearchResult.lower` and `SearchResult.upper`).

**A guard for the bound.** A consistent bound solves the model's own equation: the bound of a state is at most the least bound of the actions offered there,
and `L(root)` only rises round after round. A bound that breaks either is not a lower bound of anything a cut may rest on, and a lower graph built on it can
be unsolvable (an improper policy, ticket #539), so the search checks both as it goes and refuses at the first sign (`BoundError`, with `guard=True`):

* when a state is expanded, its bound must not be above the least `la` of its offers by more than `CONSISTENCY_LIMIT` (the certified error that the bound's
  own solve may leave in its values, at most 1e-6), nor by more than that share of the root's bound in absolute terms (a value near 0 carries rounding, not a
  relative error);
* after each round, `L(root)` must not have fallen by more than `FALL_LIMIT` (the solver's own rounding is far below it); `SearchStats.largest_fall` is the
  largest relative fall that a round caused.

A bound that passes both has shown no fault on the states the search has expanded. The tips it has not expanded are checked only when the solve of a lower graph
fails (`ConvergenceError`): a bound raised at the tips (50 times at every third key, on R13) can make the graph unsolvable before any of them is expanded, so the
search then asks the problem for the offers' bounds at every tip (no kernel is built) and applies the same check. A `ConvergenceError` that no state shows to be
the bound's doing is left as it is (a free action, or a cost ratio of 1e14 between the cheapest action and the values, cannot be certified even on a perfect
bound; an improper policy of a stiff evaluation is a limit of the solver).

**What a round costs, and the warm start (ticket #568).** The rounds are about the depth of the optimal policy (R04: 48), and each solves the whole lower graph.
A round's graph differs from the last round's in the frontier only, so three things are carried over or shared instead of done again:

* the kernels live in flat arrays (`Kernels`), every edge once, and a round's graph is a view of them: no second copy of the edges, no chances worked out again;
* the solver sums each kernel once, however many states share it (`Work.shared_sums`, the products of `evaluate_policy`), with the chance of a node in its own
  kernel (`_self_mass`, found when the kernel is realized) taken off the shared sum;
* the solve starts from the last round's policy and values (`_warm`): a node keeps the action of the same tag, a new node is a tip and starts on its fake action.
  The start is a guess and costs the answer nothing: `solver._packed_solve.warm_policy` proves it proper (every state reaches the goal with positive chance, which for a
  finite chain is properness) or replaces it at the states that cannot finish by the cheapest path's action, and the policy iteration ends at the same fixed point
  from any proper start. `SearchStats.solve_info` sums the solver's counts and seconds over the rounds (`warm_kept`, `warm_repaired`, matvecs, seconds of each stage).

**Convergence.** Each round expands at least one tip or realizes at least one offer (a greedy fake action at an expanded node always realizes the
first offer it stands for, even on a tie), and both are finite: the search ends, in at most as many rounds as the graph has (state, offer) pairs.
In practice a round expands the whole frontier of the greedy policy, so the rounds are about the depth of the optimal policy. Within a round the
bounds are fixed points computed to the solver's certified relative error (`L` is taken `(1 - error)` lower; the offers' `la` are taken `SLACK`
lower), so a cut never rests on a rounding: a bound moves only up (`L`) and every comparison that decides a cut is against a value that was
lowered by what the solver cannot certify.

**The upper side (ticket #826).** `U` is the value of a policy that can be executed: the best policy of the *upper graph*, which holds the realized
actions plus, at every state but the start, the restart (buy the start item again) when the start item is bought. A tip then restarts (its cost is
the start price plus the start value, a fixed point of the same graph). A start that is given has no restart: a tip has no executable action, and
`U` is infinite until some policy of the realized actions closes (reaches no tip). Every action of the upper graph is a real action with its exact
kernel, so its best policy is a policy of the real game and `U`, solved with a certified residual and taken `(1 + error)` higher, is at least that
policy's exact mean, which is at least `V*(root)`. The upper graph only gains actions, so `U` only falls.

**The first plan.** Before the first round the search realizes one action along a chain from the start (`_seed`): at each state the offer with the
least `la` (the action the bound thinks best; an offer the game refuses passes to the next), or the offers a given route names (`incumbent`, the
"completed route" of `cli/_route.py`, #536). That chain with the restart at whatever it leaves is the first executable plan, and its `U` the first
upper figure (`SearchStats.first_upper`): on R04 it is the optimum itself, on R14 0.0004% above it (research note 2026-11-13-planning-speed,
section 3). From then on a caller can read the best plan so far and its proved gap at any time (`Search.standing`, `Search.plan_now`, `watch`).

**The stop at a proved gap (OR-32).** With `gap = eps > 0`, once `gap_after` seconds have passed, the search ends at the first round where
`U <= (1 + eps) L(root)`: the answer is the upper graph's best policy, `exact` is False and `within` is `eps`. The stop is sound because of two
facts and nothing else. (1) *The lower side is admissible*: `L(root) <= V*(root)` ("The lower graph", above), and the figure compared is
`L(root)` less its certified error. (2) *The upper side is an executable policy evaluated exactly*: the plan returned is the policy whose value
`U` is (the same graph, solved in the same round), every action in it is real, and `U` is taken with its certified error added. Then
`mean(plan) <= U <= (1 + eps) L(root) <= (1 + eps) V*(root)`: the plan costs at most `eps` more than the cheapest plan of the offers. A `U` that
is an estimate, a heuristic's value or the value of a policy that reaches a state with no executable action would break (2); a bound that is not
a lower bound would break (1), and the guard above refuses the ones it can see. A round whose upper solve cannot be certified (`ConvergenceError`:
the free-action and stiff cases of #769) does not stop: the stop waits for a certified `U` (`SearchStats.upper_refused` counts the rounds it
waited). Before `gap_after` only the exact stop ends the search ("exact when the whole plan fits in about a minute"); `gap = 0`, or `gap_after`
None, is the exact search and nothing else. The gap closes monotonically (`U` only falls, `L` only rises), so the search is anytime.

**The stop-and-say-so net.** A time, memory or state net (`Net`) ends the search between rounds, and the time and memory nets also inside a
round and inside the first plan's chain (the state net waits for the first round, so the first plan's reach can pass it); the answer is then the
best executable policy and `exact` is False, with `stopped` saying which net. When the plan in hand at the stop cannot be solved to a certified cost
(#769), the answer is the last plan that could, from the first plan or an earlier round (`SearchResult.held`): OR-33 asks for a plan, not a refusal. A given start whose plan has not closed has no answer
(`NoPolicy`).
"""

import math
import time
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from crafting_system import parallel
from crafting_system.solver import ConvergenceError, PackedGraph, policy_reach
from crafting_system.solver._packed import BIG_TOTAL
from crafting_system.solver._packed_solve import solve_graph

FLOOR = 1e-200  # a fake action of bound 0 is carried at this cost: the certificate divides by the cheapest cost of a state (a rise of 1e-200 moves no cut)
FAKE = -1  # the tag of a fake action (a tip's bound, or the least bound of the offers not realized yet)
NO_ACTION = -2  # the tag of "no action" in the policy handed to the next round
WARM_START = True  # each round's solve starts from the last round's policy and values (False: from the cheapest path, as the first round does; for measuring)
SLACK = 1e-9  # the lower bound of an offer is taken this much lower in relative terms (rounding of the model's sums; only ever costs a tie)
FALL_LIMIT = 1e-6  # a relative fall of `L(root)` above this is no rounding: the bound is not consistent (`SearchStats.largest_fall`)
CONSISTENCY_LIMIT = 1e-5  # a state's bound above the least `la` of its offers by more than this share is no rounding of the bound's solve (it is certified to 1e-6)
PRIME_AHEAD = 32  # the offers of a state that the problem is asked to prime at once (`Problem.prime`) ...
PRIME_FROM = 16  # ... when at least this many are still to be built: a pool of processes costs more than a route of a dozen offers (R14: twice its time) saves
POLL_SECONDS = 0.5  # how often a round that expands many states, or the first plan's chain, asks the net inside it
VERIFY_FIRST = 20  # the first this many shared kernels are checked against a fresh kernel ...
VERIFY_EVERY = 4_096  # ... and then one in this many (a `kernel_key` promises equal kernels at one state; the search shares them across states)


class Refused(Exception):
    """The offer has no action at this state: the game refuses it, or the model has no rule for it there (the problem has noted which)."""


class BoundError(ValueError):
    """The bound the search was given is not a consistent lower bound (see "A guard for the bound"): the search refuses to answer on it."""


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

    # optional: `prime(state, positions)` makes, side by side, what the kernels of these offers at the state will cost most (a process pool); it changes no answer


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
    first_upper: float | None = None  # the certified upper figure of the first plan (the least-`la` chain or the incumbent's, the restart at the rest); None when not finite or not certified
    seeded: int = 0  # (state, offer) pairs realized along the first plan's chain, before the first round
    upper_solves: int = 0  # solves of the upper graph
    upper_refused: int = 0  # of those, the ones the solver could not certify (the stop at a gap waited)
    upper_seconds: float = 0.0
    solve_seconds: float = 0.0
    build_seconds: float = 0.0
    expand_seconds: float = 0.0
    verified: int = 0
    peak_mb: float | None = None
    solve_info: dict = field(default_factory=dict)  # the solver's counts and seconds, summed over the rounds


@dataclass(frozen=True, eq=False)
class SearchResult[S]:
    """The graph the search ended with, as a packed graph over `states` (the start is 0): tips are dead ends, or restart where `restarts`.

    `exact`: the greedy policy reaches only expanded states and its mean is the optimum, pinned by `lower == upper` to the solver's certified
    error. Otherwise `stopped` says which net ended the search and the graph holds the best executable policy (the restart at every tip).
    `lower` is `L(root)` less its certified error (the `LB` of the certificate `[LB, U]`). `upper` is the certified upper figure of the plan in
    `graph` (its value with the solver's error added; the caller solves the graph for the exact mean), None for an exact answer, where the mean
    is pinned by the lower graph itself. `within` is the gap setting when the search ended at a proved gap (OR-32): then `stopped` is None,
    `exact` is False and `upper <= (1 + within) * lower`. `held` says that the plan is an earlier one, kept because the plan in hand at a net's stop
    could not be solved to a certified cost: `states` and `index` are then the states that plan knew.
    """

    states: list[S]
    index: dict[S, int]
    graph: PackedGraph
    lower: float
    exact: bool
    stopped: str | None
    restarts: bool
    stats: SearchStats
    upper: float | None = None
    within: float | None = None
    held: bool = False


@dataclass(frozen=True)
class Standing:
    """Where the search stands: the best plan so far and its proved gap, for a caller to read at any time (`Search.standing`, `watch`).

    `lower`: no plan costs less (certified). `upper`: a plan the search holds costs at most this (certified; `Search.plan_now` returns that plan
    or a cheaper one), None while no executable plan has closed. Both are the remaining cost from the start state.
    """

    lower: float
    upper: float | None
    rounds: int
    seconds: float

    @property
    def gap(self) -> float | None:
        """`U / L - 1`: the most the plan can cost above the cheapest; None with no plan yet or a lower figure not above zero."""
        if self.upper is None or not self.lower > 0.0 or not math.isfinite(self.upper):
            return None
        return max(self.upper / self.lower - 1.0, 0.0)


def resident_mb() -> float | None:
    """The memory this process and its live pool workers hold, in MB, or None where it cannot be read (`parallel.held_mb`, #626).

    The workers that prime the distributions are processes of their own: a net that read this process alone let them take a runner's memory.
    """
    return parallel.held_mb()


class Kernels:
    """The kernels of the search in flat arrays: every edge is held once, as the packed graph holds it, and a round's graph is a view of them.

    A kernel is the successors of an offer at a state and their chances; a round used to join them all into new arrays (and work the chances out of the weights
    again), at a cost that grew with the graph and with a second copy of every edge in memory. Now `add` writes a kernel after the others, and `graph` hands
    the solver slices (the extra kernel it is given is written past the end and not kept).
    """

    def __init__(self) -> None:
        self.count = 0
        self.edges = 0
        self.ptr = np.zeros(1025, dtype=np.int64)
        self.succ = np.zeros(4096, dtype=np.int32)
        self.wt = np.zeros(4096, dtype=np.int64)  # zero for a big kernel, whose exact weights are in `big`
        self.prob = np.zeros(4096)
        self.big: dict[int, tuple[int, ...]] = {}

    def _room(self, kernels: int, edges: int) -> None:
        if kernels + 2 > len(self.ptr):
            self.ptr = np.concatenate((self.ptr, np.zeros(len(self.ptr) // 2 + kernels, dtype=np.int64)))
        if edges + 2 > len(self.succ):
            grow = max(edges + 2 - len(self.succ), len(self.succ) // 2)
            self.succ = np.concatenate((self.succ, np.zeros(grow, dtype=np.int32)))
            self.wt = np.concatenate((self.wt, np.zeros(grow, dtype=np.int64)))
            self.prob = np.concatenate((self.prob, np.zeros(grow)))

    def add(self, successors: list[int], weights: list[int]) -> int:
        size = len(weights)
        total = 0
        for w in weights:
            total += w
        self._room(self.count + 1, self.edges + size)
        lo, hi = self.edges, self.edges + size
        self.succ[lo:hi] = successors
        if total >= BIG_TOTAL:
            self.big[self.count] = tuple(int(w) for w in weights)
            self.wt[lo:hi] = 0
            self.prob[lo:hi] = [w / total for w in weights]  # exact big-integer ratios, rounded once
        else:
            self.wt[lo:hi] = weights
            self.prob[lo:hi] = np.asarray(weights, dtype=np.float64) / float(total)
        self.edges = hi
        self.count += 1
        self.ptr[self.count] = hi
        return self.count - 1

    def span(self, kernel: int) -> slice:
        return slice(int(self.ptr[kernel]), int(self.ptr[kernel + 1]))

    def weights(self, kernel: int) -> list[int] | tuple[int, ...]:
        """The exact integer weights of a kernel."""
        big = self.big.get(kernel)
        return big if big is not None else [int(w) for w in self.wt[self.span(kernel)]]

    def graph(self, goal, act_ptr, act_tag, act_cost, act_kernel, tail: tuple[int, int] | None = None) -> PackedGraph:
        """The packed graph of these kernels. `tail` = (successor, weight) adds a last kernel of one edge (the fake action's to the goal node)."""
        count, edges = self.count, self.edges
        if tail is not None:
            self._room(count + 1, edges + 1)
            self.succ[edges], self.wt[edges], self.prob[edges] = tail[0], tail[1], 1.0
            self.ptr[count + 1] = edges + 1
            count, edges = count + 1, edges + 1
        return PackedGraph(
            goal=goal, act_ptr=act_ptr, act_tag=act_tag, act_cost=act_cost, act_kernel=act_kernel,
            k_ptr=self.ptr[: count + 1], k_succ=self.succ[:edges], k_wt=self.wt[:edges], k_prob=self.prob[:edges], k_big=self.big,
        )  # fmt: skip


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
        guard: bool = True,
        warm: bool | None = None,
        gap: float = 0.0,
        gap_after: float | None = None,
        watch: Callable[[Standing], None] | None = None,
    ) -> None:
        if not (gap >= 0.0 and math.isfinite(gap)):
            raise ValueError(f"the gap of the stop is a share, zero or more (0.01 is 1%); got {gap!r}")
        self.p = problem
        self.net = net or Net()
        self.gap = gap  # OR-32: stop when the plan is proved to cost at most this share more than the cheapest; 0 is the exact search
        self.gap_after = gap_after  # the seconds of `run` after which the stop at the gap applies (0: from the first round); None: never
        self.watch = watch
        self.upper: float | None = None  # the least certified upper figure so far (the upper graph only gains actions, so a later plan costs no more)
        self.held: tuple[PackedGraph, float] | None = None  # the last upper graph the solver certified with a finite cost, and that cost: what a net's stop falls back on
        self.standing: Standing | None = None
        self.incumbent = incumbent
        self.say = progress or (lambda _text: None)
        self.tolerance = tolerance
        self.guard = guard  # False for the tests that plant a wrong bound and watch what it does
        self.warm = WARM_START if warm is None else warm
        self.stats = SearchStats()
        self.states: list[S] = []
        self.index: dict[S, int] = {}
        self.goal = bytearray()
        self.expanded = bytearray()
        self.lb = np.zeros(1024)
        self.rows: dict[int, list[tuple[int, float, int, float]]] = {}  # expanded node -> realized (position, cost, kernel, chance of the node itself in it)
        self.cands: dict[int, list[tuple[float, int]]] = {}  # expanded node -> offers not realized yet, the least `la` last
        self.kernels = Kernels()
        self.shared: dict[Hashable, int] = {}
        self.hits = 0
        self.values: np.ndarray | None = None  # the solved lower graph (node n_solved is the goal node)
        self.tags: np.ndarray | None = None  # the tag (offer position, or FAKE) of the action the last solve chose at each node, NO_ACTION where none
        self.n_solved = 0
        self.restart_kernel: int | None = None
        self.prime_skip = 0  # states to leave before the problem is asked to prime again (see `realize`)
        self.prime_zero = 0
        self.self_mass = np.zeros(0)  # per action of the graph last built: the chance of its node in its kernel (the solver sums shared kernels once)
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
        self.stats.kernels += 1
        return self.kernels.add(successors, weights)

    def _fresh_equal(self, state: S, position: int, kid: int) -> bool:
        weights = self.p.kernel(state, position)
        kernels = self.kernels
        got = {self.states[int(t)]: w for t, w in zip(kernels.succ[kernels.span(kid)], kernels.weights(kid))}
        return got == dict(weights)

    def _self_mass(self, i: int, kid: int) -> float:
        """The chance that kernel `kid` gives node `i` itself (0 if `i` is not among its successors): the solver takes it off a shared sum."""
        kernels = self.kernels
        at = kernels.span(kid)
        hit = np.flatnonzero(kernels.succ[at] == i)
        return float(kernels.prob[at][hit[0]]) if hit.size else 0.0

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
        if self.guard and listed:
            self._consistent(i, self.cands[i][-1][0])  # the last is the least `la`

    def _consistent(self, i: int, least: float) -> None:
        """Raise `BoundError` when the bound of node `i` is above `least`, the least lower bound of its offers (a consistent bound is at most that)."""
        bound = float(self.lb[i])
        if bound > least * (1.0 + CONSISTENCY_LIMIT) + CONSISTENCY_LIMIT * float(self.lb[0]):  # the last term: values near 0 carry rounding, not a relative error
            raise BoundError(
                f"the lower bound is not consistent: it puts the cost of a state at {bound:,.6g}, yet no action there costs less than {least:,.6g} even "
                "at its best case, which a lower bound never does: it cannot be trusted for a cut"
            )

    def _probe(self) -> None:
        """Look at the tips of the graph that could not be solved: raise `BoundError` if the bound is not consistent at one of them.

        A tip has not been expanded, so the bound has not been checked there; its offers' bounds come from the problem without building any kernel. A failure
        of the solve that none of the states shows to be the bound's doing is left to the caller (it is not the bound's doing as far as the search can tell).
        """
        for i in range(len(self.states)):
            if self.goal[i] or self.expanded[i] or not math.isfinite(self.lb[i]):
                continue
            offered = [la for la, _ in self.p.candidates(self.states[i])]
            self.p.release()
            if offered:
                self._consistent(i, min(offered) * (1.0 - SLACK))

    def _value(self, ids: np.ndarray) -> np.ndarray:
        """The lower value of nodes: the last solve's where there is one, else their bound."""
        out = self.lb[ids].copy()
        if self.values is not None:
            known = ids < self.n_solved
            out[known] = self.values[ids[known]]
        return out

    def _q(self, cost: float, kid: int) -> float:
        at = self.kernels.span(kid)
        return cost + float(self.kernels.prob[at] @ self._value(self.kernels.succ[at]))

    def realize(self, i: int, force: bool) -> None:
        """Realize the offers of node `i` whose lower bound is below the best realized lower cost (the first one regardless, with `force`)."""
        rows, cands = self.rows[i], self.cands[i]
        best = min((self._q(c, kid) for _, c, kid, _ in rows), default=math.inf)
        first = force
        prime = getattr(self.p, "prime", None)
        primed = 0  # how many of the offers at the end of `cands` have been primed
        self.prime_skip = max(self.prime_skip - 1, 0)
        while cands and (first or cands[-1][0] < best):
            if prime is not None and primed == 0 and not self.prime_skip:
                # the offers still to be realized are among those whose bound is below the best now (it only falls): ask the problem to make their
                # expensive parts side by side before they are built one by one
                ahead = [position for la, position in reversed(cands[-PRIME_AHEAD:]) if first or la < best]
                if len(ahead) >= PRIME_FROM:
                    made = prime(self.states[i], ahead)
                    # a call that found everything made already (the pools of one offer are the same at most states) costs the preparation of every offer
                    # for nothing: the next calls wait 2, 4, ... 64 states while the answer stays 0
                    self.prime_zero = 0 if made else self.prime_zero + 1
                    self.prime_skip = min(2**self.prime_zero, 64) if not made else 0
                primed = len(ahead)
            first = False
            primed -= 1
            _, position = cands.pop()
            try:
                kid = self._kernel(i, position)
            except Refused:
                continue
            cost = self.p.cost(position)
            rows.append((position, cost, kid, self._self_mass(i, kid)))
            self.stats.realized += 1
            best = min(best, self._q(cost, kid))

    def _seed(self, began: float) -> str | None:
        """Realize one action along a chain from the start, the first plan (see the module text): the incumbent's where one is given, else the
        offer with the least `la`; an offer the game refuses passes to the next. Returns the reason when the time or the memory net ended the
        chain early (the states it had not come to stay tips, which restart)."""
        queue = [0]
        seen = {0}
        polled = -math.inf  # the memory is read at the first state, and then every `POLL_SECONDS`
        for i in queue:
            if self.goal[i]:
                continue
            poll = time.perf_counter() - polled >= POLL_SECONDS
            if poll:
                polled = time.perf_counter()
            stopped = self._net(began, memory=poll, states=False)  # the clock at every state; the state net waits for the first round, so the chain is whole
            if stopped is not None:
                return stopped
            if not self.expanded[i]:
                self.expand(i)
            rows, cands = self.rows[i], self.cands[i]
            wanted = self.incumbent(self.states[i]) if self.incumbent is not None else [position for _, position in reversed(cands)]  # the least `la` is last
            for position in wanted:
                held = [c for c in cands if c[1] == position]
                if not held:
                    continue
                cands.remove(held[0])  # a refused offer is not asked again: it has no action here
                try:
                    kid = self._kernel(i, position)
                except Refused:
                    continue
                rows.append((position, self.p.cost(position), kid, self._self_mass(i, kid)))
                self.stats.realized += 1
                self.stats.seeded += 1
                for j in self.kernels.succ[self.kernels.span(kid)].tolist():
                    if j not in seen:
                        seen.add(j)
                        queue.append(j)
                break
            self.p.release()
        return None

    # ---- the graphs ---------------------------------------------------------------------------------------------

    def _graph(self, mode: str) -> PackedGraph:
        """The packed graph over the nodes: `lower` (fakes, plus a goal node at the end), `upper` (restart at every node but the start) or
        `exact` (realized actions only, tips are dead ends). `self.self_mass` is left holding the chance of each action's node in its kernel."""
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
        selves: list[float] = []
        sizes = np.zeros(len(ids), dtype=np.int64)
        fake_kernel = self.kernels.count  # the kernel `Kernels.graph` appends for the fake actions
        restart = self.p.restart
        for slot, i in enumerate(ids.tolist()):
            rows = self.rows[i]
            made = 0
            if not goal[i]:
                for position, cost, kid, mass in rows:
                    tags.append(position)
                    costs.append(cost)
                    kernels.append(kid)
                    selves.append(mass)
                    made += 1
                if lower:
                    held = self.cands[i]
                    if held and math.isfinite(held[-1][0]):
                        tags.append(FAKE)
                        costs.append(max(held[-1][0], FLOOR))
                        kernels.append(fake_kernel)
                        selves.append(0.0)
                        made += 1
                elif upper and i != 0 and not any(position == restart for position, _, _, _ in rows):
                    tags.append(restart)
                    costs.append(self.p.cost(restart))
                    kernels.append(self.restart_kernel)
                    selves.append(0.0)
                    made += 1
            sizes[slot] = made
        counts[ids] = sizes
        ptr = np.concatenate(([0], np.cumsum(counts)))
        total = int(ptr[-1])
        act_tag = np.zeros(total, dtype=np.int32)
        act_cost = np.zeros(total)
        act_kernel = np.zeros(total, dtype=np.int32)
        act_self = np.zeros(total)
        if len(tags):
            offsets = np.repeat(ptr[ids], sizes) + (np.arange(len(tags)) - np.repeat(np.cumsum(sizes) - sizes, sizes))
            act_tag[offsets] = tags
            act_cost[offsets] = costs
            act_kernel[offsets] = kernels
            act_self[offsets] = selves
        tip_ids = np.flatnonzero(tip)
        if lower:
            tip_ids = tip_ids[np.isfinite(bound[tip_ids])]
            at = ptr[tip_ids]
            act_tag[at], act_cost[at], act_kernel[at] = FAKE, np.maximum(bound[tip_ids], FLOOR), fake_kernel
        elif upper:
            tip_ids = tip_ids[tip_ids != 0]
            at = ptr[tip_ids]
            act_tag[at], act_cost[at], act_kernel[at] = restart, self.p.cost(restart), self.restart_kernel
        self.self_mass = act_self
        goal_flags = np.concatenate((goal, [True])) if lower else goal
        return self.kernels.graph(goal_flags, ptr, act_tag, act_cost, act_kernel, tail=(n, 1) if lower else None)

    def _warm(self, graph: PackedGraph) -> tuple[np.ndarray, np.ndarray] | None:
        """The start of the next solve: the last round's policy and values, carried to the nodes of `graph` (None in the first round).

        A node keeps the action of the same tag it took (the offers realized stay; a fake action is the same tag whatever it costs now). A node the last
        round did not know is a tip, whose one action is the fake. The policy is a guess: the solver proves it proper or replaces it
        (`solver._packed_solve.warm_policy`), so it is no risk to the answer; it only saves the policy iteration from starting over. The values start
        the first evaluation of the linear system: the last round's, the bound at a node it did not know.
        """
        if not self.warm or self.tags is None or self.values is None:
            return None
        nodes = graph.n
        known = min(len(self.tags), nodes)
        tag = np.full(nodes, FAKE, dtype=np.int32)
        tag[:known] = self.tags[:known]
        owner = graph.action_state()
        found = np.flatnonzero(graph.act_tag == tag[owner])
        policy = np.full(nodes, -1, dtype=np.int64)
        policy[owner[found]] = found
        value = np.zeros(nodes)
        value[: len(self.states)] = self.lb[: len(self.states)]
        carried = min(self.n_solved, len(self.states))
        value[:carried] = np.where(np.isfinite(self.values[:carried]), self.values[:carried], value[:carried])
        return policy, value

    def upper_value(self) -> float:
        """The value of the best executable policy of the graph now (the restart at every tip): infinite when the start item is given and no policy
        of the realized actions closes. Raises `ConvergenceError` when the solver cannot certify it."""
        return self._upper()[1]

    def _upper(self) -> tuple[PackedGraph, float, float]:
        """The upper graph now, the value of its best policy at the start and that value with the solver's certified error added (the upper
        figure a stop may rest on). With no restart the graph is the realized actions alone (a tip is a dead end). Raises `ConvergenceError`."""
        mark = time.perf_counter()
        self.stats.upper_solves += 1
        try:
            graph = self._graph("upper")
            core = solve_graph(graph, tolerance=self.tolerance, info={}, self_mass=self.self_mass)
        except ConvergenceError:
            self.stats.upper_refused += 1
            raise
        finally:
            self.stats.upper_seconds += time.perf_counter() - mark
        value = float(core.value[0])
        certified = value * (1.0 + core.certificate.bound) if math.isfinite(value) else math.inf
        if math.isfinite(certified):
            self.held = graph, certified
            if self.upper is None or certified < self.upper:
                self.upper = certified
        return graph, value, certified

    def plan_now(self) -> SearchResult[S] | None:
        """The best executable plan the search holds now, as a stop would return it, or None while none has closed or the solver cannot certify
        it. For a caller that shows a plan before the proof ends (it costs one solve of the upper graph)."""
        try:
            graph, _, certified = self._upper()
        except ConvergenceError:
            return None
        if not math.isfinite(certified):
            return None
        lower = self.standing.lower if self.standing is not None else float(self.lb[0])
        self.stats.touched = len(self.states)
        return SearchResult(self.states, self.index, graph, lower, False, None, self.p.restart is not None, self.stats, certified, None)

    def _stand(self, lower: float, began: float) -> None:
        """Record where the search stands and tell the watcher."""
        self.standing = Standing(lower, self.upper, self.stats.rounds, time.perf_counter() - began)
        if self.watch is not None:
            self.watch(self.standing)

    # ---- the rounds ---------------------------------------------------------------------------------------------

    def _net(self, began: float, memory: bool = True, states: bool = True) -> str | None:
        """The reason a net is reached now, or None; `memory` False leaves the memory unread (reading it costs too much to do at every state),
        `states` False leaves the count of states unasked (the first plan's chain: the state net is asked between rounds)."""
        net = self.net
        if net.seconds is not None and time.perf_counter() - began >= net.seconds:
            return f"the time limit of {net.seconds:g} seconds was reached"
        if states and net.states is not None and len(self.states) >= net.states:
            return f"{len(self.states):,} states were known, the limit is {net.states:,}"
        if memory and net.memory_mb is not None:
            used = resident_mb()
            if used is not None and used >= net.memory_mb:
                return f"the process held {used:,.0f} MB, the limit is {net.memory_mb:,.0f} MB"
        return None

    def run(self) -> SearchResult[S]:
        began = time.perf_counter()
        if self.p.restart is not None:
            self.restart_kernel = self._store([0], [1])
        stopped = None
        if not self.goal[0]:
            if math.isfinite(self.lb[0]):
                self._last_root = float(self.lb[0])  # the lower graph before the first plan is the start alone, a tip, and its value the start's bound: the first round must not fall below it (the guard)
            mark = time.perf_counter()
            stopped = self._seed(began)
            self.stats.expand_seconds += time.perf_counter() - mark
            try:
                upper = self._upper()[2]
            except ConvergenceError:  # the first plan is beyond what the solver certifies (#769): the search goes on without an upper figure
                upper = math.inf
            self.stats.first_upper = upper if math.isfinite(upper) else None
            self.say(
                f"first plan ({'the given route' if self.incumbent is not None else 'the least lower cost at each state'}): {self.stats.seeded:,} actions "
                f"realized along its chain over {len(self.states):,} states, costs at most {upper!r} ({time.perf_counter() - began:.0f} s)"
                + (f"; its chain was cut short: {stopped}" if stopped is not None else "")
            )
            self._stand(float(self.lb[0]), began)  # the bound of the start is a lower figure before any round
        lower = 0.0
        while stopped is None:
            mark = time.perf_counter()
            graph = self._graph("lower")
            self.stats.build_seconds += time.perf_counter() - mark
            mark = time.perf_counter()
            info: dict = {}
            warm = self._warm(graph)
            try:
                if warm is None:
                    core = solve_graph(graph, tolerance=self.tolerance, info=info, self_mass=self.self_mass)
                else:
                    core = solve_graph(
                        graph, tolerance=self.tolerance, info=info, start_policy=warm[0], start_value=warm[1], self_mass=self.self_mass
                    )
            except ConvergenceError:
                if self.guard:
                    self._probe()  # a bound that is not consistent can leave the lower graph unsolvable: say so, with the fault found
                raise
            self.stats.solve_seconds += time.perf_counter() - mark
            for name, amount in info.items():
                if isinstance(amount, str):
                    name, amount = f"{name}_{amount}", 1
                self.stats.solve_info[name] = self.stats.solve_info.get(name, 0) + amount
            self.tags = np.full(graph.n, NO_ACTION, dtype=np.int32)
            chosen = core.action >= 0
            self.tags[chosen] = graph.act_tag[core.action[chosen]]
            self.values = core.value
            self.n_solved = len(self.states)
            self.stats.rounds += 1
            lower = float(core.value[0]) * (1.0 - core.certificate.bound)
            root = float(core.value[0])
            if self._last_root is not None and math.isfinite(root) and self._last_root > 0:
                fall = (self._last_root - root) / self._last_root
                self.stats.largest_fall = max(self.stats.largest_fall, fall)
                if self.guard and fall > FALL_LIMIT:
                    raise BoundError(
                        f"the lower bound fell by {fall:.2%} from one round of the search to the next, which a consistent bound never does: "
                        "it cannot be trusted for a cut (a declared block invariance may be wrong)"
                    )
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
            self.say(
                f"  totals: build {self.stats.build_seconds:.0f} s, solve {self.stats.solve_seconds:.0f} s, expand {self.stats.expand_seconds:.0f} s; "
                f"this solve {time.perf_counter() - mark:.1f} s on {graph.n:,} nodes, {graph.num_actions:,} actions, {graph.num_edges:,} edges stored: "
                + ", ".join(f"{name} {amount:.4g}" if isinstance(amount, float) else f"{name} {amount}" for name, amount in sorted(info.items()))
            )
            if not len(fake):
                self.stats.touched = len(self.states)
                self.upper = min(root * (1.0 + core.certificate.bound), self.upper if self.upper is not None else math.inf)  # the greedy policy is executable and its value is `root`
                self._stand(lower, began)
                return SearchResult(self.states, self.index, self._graph("exact"), lower, True, None, False, self.stats)
            if self.gap > 0.0 and self.gap_after is not None and time.perf_counter() - began >= self.gap_after:
                try:
                    plan, _, upper = self._upper()
                except ConvergenceError:  # the stop waits for an upper figure the solver can certify (#769)
                    plan, upper = None, math.inf
                    self.say("  the plan in hand could not be solved to a certified cost this round: the stop at the gap waits")
                if plan is not None and upper <= (1.0 + self.gap) * lower:
                    self.stats.touched = len(self.states)
                    self._stand(lower, began)
                    self.say(f"stop: the plan costs at most {upper!r}, no plan costs less than {lower!r}: proved within {self.gap:.3%}")
                    return SearchResult(self.states, self.index, plan, lower, False, None, self.p.restart is not None, self.stats, upper, self.gap)
            self._stand(lower, began)
            stopped = self._net(began)
            if stopped is not None:
                break
            mark = time.perf_counter()
            polled = mark
            for i in fake.tolist():
                if not self.expanded[i]:
                    self.expand(i)
                self.realize(i, force=True)
                self.p.release()
                if time.perf_counter() - polled >= POLL_SECONDS:  # a round can expand tens of thousands of states: the net is asked inside it too (#626)
                    polled = time.perf_counter()
                    stopped = self._net(began)
                    if stopped is not None:
                        break
            self.stats.expand_seconds += time.perf_counter() - mark
            if stopped is not None:
                break
        self.stats.touched = len(self.states)
        if not self.stats.rounds:
            lower = float(self.lb[0])  # the net ended the first plan's chain before any round: the start's own bound is the lower figure
        try:
            plan, _, upper = self._upper()
        except ConvergenceError as error:  # the plan of a stopped search over a big, stiff graph can be beyond what the solver certifies
            if self.held is not None:  # an earlier plan was certified: it is the answer (OR-33), over the states it knew
                plan, upper = self.held
                self.say(f"  the plan in hand at the stop could not be solved to a certified cost ({error}): the last plan that could is kept, at most {upper!r}")
                self._stand(lower, began)
                known = plan.n
                index = {state: i for state, i in self.index.items() if i < known}
                return SearchResult(self.states[:known], index, plan, lower, False, stopped, self.p.restart is not None, self.stats, upper, None, True)
            raise NoPolicy(
                f"the search stopped ({stopped}) and the plan it had found over {len(self.states):,} states cannot be solved to a certified cost ({error}); "
                f"it had looked at {self.stats.expanded:,} of them and no plan costs less than {lower:,.6g} (the lower bound of the whole graph)"
            ) from error
        if not math.isfinite(upper):
            if self.p.restart is None:
                raise NoPolicy(
                    f"the search stopped ({stopped}) before any policy closed, and the start item is given, so there is no restart to fall back on; "
                    f"it had looked at {self.stats.expanded:,} of {len(self.states):,} states and no plan costs less than {lower:,.6g}"
                )
            raise NoPolicy(
                f"the search stopped ({stopped}) before any policy that can be executed was found: it had looked at {self.stats.expanded:,} of {len(self.states):,} states "
                f"and no plan costs less than {lower:,.6g} (the lower bound of the whole graph)"
            )
        self._stand(lower, began)
        return SearchResult(self.states, self.index, plan, lower, False, stopped, self.p.restart is not None, self.stats, upper, None)


class NoPolicy(ValueError):
    """The search found no policy that reaches the goal (or none before a net stopped it, with no restart to complete it)."""


__all__ = [
    "CONSISTENCY_LIMIT", "FAKE", "FALL_LIMIT", "BoundError", "Net", "NoPolicy", "Problem", "Refused", "Search", "SearchResult", "SearchStats", "Standing",
    "resident_mb",
]  # fmt: skip
