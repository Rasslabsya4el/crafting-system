"""The packed solve of a plan: walk the graph into arrays, merge it exactly, solve it, certify it (ticket #374, ADR-0063 point 1).

The object solver holds a transition per (state, action, outcome), which is 17 GB for the 536 million transitions of R04
and out of reach for the 76.6 billion of S02. The packed route shares one kernel (successors and weights) between all the
(state, offer) pairs with the same `Abstraction.kernel_key`, so the walk pays one kernel per key and a state costs its
keys. The graph is then handed to `solver.solve_packed`, which merges it exactly (the coarsest partition with the same
futures), solves the merged graph by policy iteration and certifies the values on the unmerged graph.

What comes back is what `make_plan` needs from a solve: a `Solution` of the concrete states (the value of every walked
state; the policy as a lazy mapping that builds a state's `Action` when it is asked for, so the 100,000 states of S02,
with kernels of tens of thousands of outcomes each, are never all held as objects), and the risk of the policy, which is
evaluated on the merged chain (same mean, odds and quantiles by lumpability) because the merged chain is the one that
fits: 20 classes for S02, 12,000 for R04.

`make_plan(solver="auto")` walks packed first and keeps the object solver for graphs of at most `EXACT_TRANSITIONS`
transitions (what it has been run on, ADR-0023), unchanged; `solver="packed"` always uses this route and `"object"`
never. The answers are the same to the certificate; only the cost differs. The packed route takes no inputs, variants or
Locks (the abstraction of `make_plan` has none; `Peek` is solved elsewhere).
"""

import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from crafting_system.abstraction import Abstraction, CompressedState, integer_weights
from crafting_system.actions import ActionError
from crafting_system.solver import (
    Action,
    Outcome,
    PackedBuilder,
    PackedGraph,
    PackedSolution,
    Solution,
    policy_reach,
    solve_packed,
)

from ._decide import EXACT_TRANSITIONS
from ._offers import BuyStartItem, PricedOffer
from ._prune import keyed_offers

OBJECT_SOLVER_EDGES = EXACT_TRANSITIONS  # at most this many transitions: `solver="auto"` keeps the object solver
SOLVERS = ("auto", "object", "packed")
PROGRESS: Callable[[str], None] | None = None  # a measuring script sets it to see each phase as it ends (never set by the library)
REPORT_EVERY = 30.0  # seconds between the lines of a long walk


@dataclass(frozen=True, slots=True, eq=False)
class Walked:
    """A completely walked graph: `states[i]` is state `i` (the start is 0), `graph.act_tag` indexes `offers`."""

    graph: PackedGraph
    states: list[CompressedState]
    index: dict[CompressedState, int]
    offers: tuple[PricedOffer, ...]
    seconds: float


def walk(
    abstraction: Abstraction,
    start: CompressedState,
    offers: Sequence[PricedOffer],
    *,
    prune_corrupting: bool = True,
    progress: Callable[[str], None] | None = None,
) -> Walked:
    """Walk the exact graph of `offers` from `start` breadth first into a packed graph.

    The actions of a state are `_prune.keyed_offers`' (the allowed offers, equal kernels at one state merged to the
    cheapest), in the order of `offers`; a kernel is computed once per `kernel_key` and shared. `restart` has one
    kernel, the start. The abstraction's per-state cache is cleared after each state (each pair is asked once).
    """
    say = progress or PROGRESS or (lambda _text: None)
    offers = tuple(offers)
    began = last = time.perf_counter()
    states: list[CompressedState] = [start]
    index: dict[CompressedState, int] = {start: 0}
    goals: list[bool] = [abstraction.is_goal(start)]
    builder = PackedBuilder()
    shared: dict[object, int] = {}
    restart: int | None = None

    def intern(state: CompressedState) -> int:
        found = index.get(state)
        if found is None:
            found = index[state] = len(states)
            states.append(state)
            goals.append(abstraction.is_goal(state))
        return found

    i = 0
    while i < len(states):
        state = states[i]
        if not goals[i]:
            for position, priced, key in keyed_offers(abstraction, offers, state, start, merge_equal=True, prune_corrupting=prune_corrupting):
                action = priced.offer.action
                if isinstance(action, BuyStartItem):
                    if restart is None:
                        restart = builder.kernel([0], [1])
                    kernel = restart
                else:
                    found = shared.get(key)
                    if found is None:
                        try:
                            weights = integer_weights(abstraction.kernel(state, action))
                        except ActionError:  # the game refuses it here after all (as `solver_actions` skips it)
                            continue
                        found = shared[key] = builder.kernel([intern(s) for s in weights], list(weights.values()))
                    kernel = found
                builder.action(position, priced.cost, kernel)
        builder.close_state(goals[i])
        abstraction._prepared_by.clear()
        i += 1
        now = time.perf_counter()
        if now - last >= REPORT_EVERY:
            last = now
            say(
                f"walk: {len(states):,} states found, {i:,} done, {builder.kernels:,} kernels, "
                f"{builder.edges:,} transitions ({now - began:.0f} s)"
            )
    graph = builder.build()
    seconds = time.perf_counter() - began
    say(
        f"walk finished: {graph.n:,} states, {graph.num_actions:,} actions, {graph.num_kernels:,} kernels, "
        f"{graph.edges_counted():,} transitions ({seconds:.0f} s)"
    )
    return Walked(graph, states, index, offers, seconds)


class PackedPolicy(Mapping):
    """The policy of a packed solve as a mapping from concrete states to `Action`s, each built when asked for.

    The keys are the non-goal states the policy reaches from the start (what the report and the risk walk); an `Action`
    is the solver action of the chosen offer at that state (`offer_action`: the cost and the integer weights of its kernel).
    """

    def __init__(
        self,
        abstraction: Abstraction,
        start: CompressedState,
        walked: Walked,
        action: np.ndarray,
    ) -> None:
        self._abstraction = abstraction
        self._start = start
        self._walked = walked
        self._action = action
        reached = policy_reach(walked.graph, action, 0)
        self._keys = reached[action[reached] >= 0]
        self._member = np.zeros(walked.graph.n, dtype=bool)
        self._member[self._keys] = True
        self._built: dict[int, Action[CompressedState]] = {}

    def __len__(self) -> int:
        return len(self._keys)

    def __iter__(self) -> Iterator[CompressedState]:
        states = self._walked.states
        return (states[i] for i in self._keys.tolist())

    def __contains__(self, state: object) -> bool:
        i = self._walked.index.get(state)  # type: ignore[arg-type]
        return i is not None and bool(self._member[i])

    def __getitem__(self, state: CompressedState) -> Action[CompressedState]:
        from ._plan import offer_action  # _plan imports this module

        i = self._walked.index.get(state)
        if i is None or not self._member[i]:
            raise KeyError(state)
        built = self._built.get(i)
        if built is None:
            walked = self._walked
            priced = walked.offers[int(walked.graph.act_tag[self._action[i]])]
            built = self._built[i] = offer_action(self._abstraction, priced, state, self._start)
        return built


def class_policy(solved: PackedSolution, offers: Sequence[PricedOffer]) -> dict[int, Action[int]]:
    """The policy on the merged chain: for every class the optimal policy reaches from the start class, its action.

    States are class numbers, outcomes are weights over classes; `risk.evaluate` takes it as any policy (the mean, the
    odds and the quantiles of the policy are the same on the classes as on their members).
    """
    reduced = solved.quotient
    chosen = solved.class_action
    reached = policy_reach(reduced, chosen, int(solved.cls[0]))
    policy: dict[int, Action[int]] = {}
    for c in reached.tolist():
        a = int(chosen[c])
        if a < 0:
            continue
        kernel = int(reduced.act_kernel[a])
        low, high = int(reduced.k_ptr[kernel]), int(reduced.k_ptr[kernel + 1])
        weights = reduced.kernel_weights(kernel)
        outcomes = tuple(Outcome(int(s), int(w)) for s, w in zip(reduced.k_succ[low:high].tolist(), weights))
        policy[c] = Action(offers[int(reduced.act_tag[a])].label, float(reduced.act_cost[a]), outcomes)
    return policy


@dataclass(frozen=True, slots=True, eq=False)
class PackedResult:
    """What a packed solve of a plan gives `make_plan`: the solution, and what the risk is evaluated on."""

    solution: Solution[CompressedState]
    risk_policy: Mapping[int, Action[int]]
    risk_start: int
    risk_is_goal: Callable[[int], bool]
    info: dict


def solve_walked(
    abstraction: Abstraction,
    start: CompressedState,
    walked: Walked,
    *,
    tolerance: float = 1e-10,
    progress: Callable[[str], None] | None = None,
) -> PackedResult:
    """Merge, solve and certify a walked graph; wrap it as the `Solution` of the concrete states."""
    say = progress or PROGRESS or (lambda _text: None)
    solved = solve_packed(walked.graph, tolerance=tolerance, progress=say)
    values = solved.value.tolist()
    solution = Solution(
        values=dict(zip(walked.states, values)),
        policy=PackedPolicy(abstraction, start, walked, solved.action),
        error_bound=solved.error_bound,
    )
    reduced_goal = solved.quotient.goal
    info = {**solved.info, "walk_seconds": round(walked.seconds, 1), "transitions": walked.graph.edges_counted()}
    return PackedResult(solution, class_policy(solved, walked.offers), int(solved.cls[0]), lambda c: bool(reduced_goal[c]), info)


def packed_result(
    abstraction: Abstraction,
    start: CompressedState,
    offers: Sequence[PricedOffer],
    *,
    solver: str = "auto",
    prune_corrupting: bool = True,
    tolerance: float = 1e-10,
    progress: Callable[[str], None] | None = None,
) -> PackedResult | None:
    """Solve the exact graph of `offers` on packed arrays, or None when the object solver is to do it.

    With `solver="auto"` the graph is walked first; one of at most `OBJECT_SOLVER_EDGES` transitions is left to the object
    solver (None), a larger one is solved here. `"packed"` always solves here; `"object"` returns None without walking.
    """
    if solver not in SOLVERS:
        raise ValueError(f"solver must be one of {', '.join(SOLVERS)}, got {solver!r}")
    if solver == "object":
        return None
    walked = walk(abstraction, start, offers, prune_corrupting=prune_corrupting, progress=progress)
    if solver == "auto" and walked.graph.edges_counted() <= OBJECT_SOLVER_EDGES:
        return None
    return solve_walked(abstraction, start, walked, tolerance=tolerance, progress=progress)
