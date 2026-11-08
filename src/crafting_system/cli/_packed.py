"""The packed solve of a plan: walk the graph into arrays, merge it exactly, solve it, certify it (ticket #374, ADR-0063 point 1).

The object solver holds a transition per (state, action, outcome), which is 17 GB for the 536 million transitions of R04
and out of reach for the 76.6 billion of S02. The packed route shares one kernel (successors and weights) between all the
(state, offer) pairs with the same `Abstraction.kernel_key`, so the walk pays one kernel per key and a state costs its
keys. The graph is then handed to `solver.solve_packed`, which merges it exactly (the coarsest partition with the same
futures), solves the merged graph by policy iteration and certifies the values on the unmerged graph.

What comes back is what `make_plan` needs from a solve: a `Solution` of the concrete states (the value of every walked
state; the policy as a lazy mapping that builds a state's `Action` when it is asked for, so the 100,000 states of S02,
with kernels of tens of thousands of outcomes each, are never all held as objects), and the risk of the policy, which is
evaluated on the policy's chain lumped exactly (`solver._packed_lump`: same mean, odds and whole cost distribution) because that
is the chain that fits: 11,767 classes with 17 million transitions for R04 lump to 552 blocks with 2,746 transitions, R14's 65,148
to 14,743 blocks. The same lumped chain, on one shown item state per block, is what the report prints for a big policy
(`Plan.view_policy`), while `--verify` and the route evaluation run the whole policy.

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
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.solver import (
    Action,
    LumpedChain,
    Outcome,
    PackedBuilder,
    PackedGraph,
    Solution,
    lump_policy,
    policy_reach,
    solve_packed,
)

from . import _limits
from ._decide import EXACT_TRANSITIONS
from ._limits import Limit
from ._offers import BuyStartItem, PricedOffer
from ._prune import keyed_offers

OBJECT_SOLVER_EDGES = EXACT_TRANSITIONS  # at most this many transitions: `solver="auto"` keeps the object solver
SOLVERS = ("auto", "object", "packed", "envelope")
PROGRESS: Callable[[str], None] | None = None  # a measuring script sets it to see each phase as it ends (never set by the library)
REPORT_EVERY = 30.0  # seconds between the lines of a long walk
VERIFY_FIRST = 20  # the first this many shared kernels are checked against a fresh `kernel(state, action)` ...
VERIFY_EVERY = 4_096  # ... and then one in this many (`kernel_key` promises equal kernels at one state; the walk shares them across states)


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
    hits = checked = 0

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
                    if found is not None:
                        hits += 1
                        if hits <= VERIFY_FIRST or hits % VERIFY_EVERY == 0:
                            checked += 1
                            fresh = integer_weights(abstraction.kernel(state, action))
                            if _edges(builder, found, states) != {s: w for s, w in fresh.items()}:
                                raise ValueError(
                                    f"two states share the kernel key of {priced.label!r} but not its kernel (checked at {state!r}): "
                                    "the key the model gives to tell its states apart does not say enough for the packed walk"
                                )
                    if found is None:
                        try:
                            weights = integer_weights(abstraction.kernel(state, action))
                        except NotApplicableError:  # the game refuses it here after all (as `solver_actions` skips it)
                            continue
                        except OutOfScopeError as gap:  # the model has no rule for it here: left out, and the answer says so (ticket #506)
                            abstraction.gaps.note(priced.label, state, gap)
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
    say(f"{checked} of {hits:,} shared kernels checked against a fresh kernel: all equal")
    say(
        f"walk finished: {graph.n:,} states, {graph.num_actions:,} actions, {graph.num_kernels:,} kernels, "
        f"{graph.edges_counted():,} transitions ({seconds:.0f} s)"
    )
    return Walked(graph, states, index, offers, seconds)


def _edges(builder: PackedBuilder, kernel: int, states: list[CompressedState]) -> dict[CompressedState, int]:
    """A stored kernel as the dict `integer_weights` gives (successor state -> weight)."""
    succ, weights = builder.kernel_edges(kernel)
    return {states[i]: w for i, w in zip(succ, weights)}


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

    @property
    def walked(self) -> Walked:
        return self._walked

    @property
    def action_array(self) -> np.ndarray:
        """The index (in the walked graph) of the action taken at every state, -1 where the policy takes none."""
        return self._action

    def offer(self, state: CompressedState) -> PricedOffer:
        """The priced offer the policy takes in `state`, without building its `Action` (and its thousand outcomes)."""
        i = self._walked.index.get(state)
        if i is None or not self._member[i]:
            raise KeyError(state)
        return self._walked.offers[int(self._walked.graph.act_tag[self._action[i]])]

    def offers(self) -> Iterator[tuple[CompressedState, PricedOffer]]:
        """Every state of the policy with its priced offer, in the order of iteration."""
        walked = self._walked
        tags = walked.graph.act_tag[self._action[self._keys]]
        for i, tag in zip(self._keys.tolist(), tags.tolist()):
            yield walked.states[i], walked.offers[tag]

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


@dataclass(frozen=True, slots=True, eq=False)
class PackedResult:
    """What a packed solve of a plan gives `make_plan`: the solution, and what the risk is evaluated on."""

    solution: Solution[CompressedState]
    risk_policy: Mapping[int, Action[int]]
    risk_start: int
    risk_is_goal: Callable[[int], bool]
    info: dict
    view: Mapping[CompressedState, Action[CompressedState]] | None = None  # the lumped chain on one concrete state per block (what a big policy is shown by)


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
    info = {**solved.info, "walk_seconds": round(walked.seconds, 1), "transitions": walked.graph.edges_counted()}
    mark = time.perf_counter()
    lumped = lump_policy(solved.quotient, solved.class_action, int(solved.cls[0]))
    info.update(lumped_blocks=lumped.count, lumped_transitions=lumped.transitions, lump_rounds=lumped.rounds, lump_seconds=round(time.perf_counter() - mark, 1))
    say(f"policy chain lumped: {lumped.count:,} blocks, {lumped.transitions:,} transitions ({info['lump_seconds']} s)")
    goal = lumped.goal
    view = lumped_view(lumped, solved.quotient, solved.cls, walked)
    return PackedResult(solution, lumped_policy(lumped, solved.quotient, walked.offers), lumped.start, lambda b: bool(goal[b]), info, view)


def lumped_view(lumped: LumpedChain, reduced: PackedGraph, cls: np.ndarray, walked: Walked) -> dict[CompressedState, Action[CompressedState]]:
    """The lumped chain on concrete states: each block is shown by one of its members (the first state of its representative class).

    The result is a policy over those states (`Action` with the offer's label and cost, outcomes into the other blocks' shown states
    with the summed integer weights), so the report, the JSON and the route view read it as any policy. The shown state of a block stands for
    all the item states that pay alike and lead to the same blocks with the same chances; its expected remaining cost is theirs.
    """
    first = np.unique(cls, return_index=True)[1]
    shown = [walked.states[int(first[int(lumped.rep[b])])] for b in range(lumped.count)]
    view: dict[CompressedState, Action[CompressedState]] = {}
    for b in range(lumped.count):
        a = int(lumped.action[b])
        if a < 0 or lumped.goal[b]:
            continue
        outcomes = tuple(Outcome(shown[int(t)], int(w)) for t, w in zip(lumped.succ[b].tolist(), lumped.weight[b]))
        view[shown[b]] = Action(walked.offers[int(reduced.act_tag[a])].label, float(lumped.cost[b]), outcomes)
    return view


def lumped_policy(lumped: LumpedChain, reduced: PackedGraph, offers: Sequence[PricedOffer]) -> dict[int, Action[int]]:
    """The policy on the lumped chain: for every block that is not a goal, the action of its representative (states are block numbers).

    The block pays what its members pay and moves to the other blocks with the summed integer weights; the mean, the odds and the
    whole cost distribution from the start block are those of the policy on the concrete states (`solver._packed_lump`).
    """
    policy: dict[int, Action[int]] = {}
    for b in range(lumped.count):
        a = int(lumped.action[b])
        if a < 0 or lumped.goal[b]:
            continue
        outcomes = tuple(Outcome(int(s), int(w)) for s, w in zip(lumped.succ[b].tolist(), lumped.weight[b]))
        policy[b] = Action(offers[int(reduced.act_tag[a])].label, float(lumped.cost[b]), outcomes)
    return policy


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


def evaluation_limits(info: Mapping) -> tuple[Limit, ...]:
    """What the solve of the plan's values leaves out when it could not be exact (OR-12, OR-13): derived from the cost of the exact method, not from a count of states.

    `info["linear_limit"]` (`solver/_packed_solve.evaluate_policy`) is set when the repeated approximation of how much each state costs stopped short of the
    exact system and the exact method needed more memory than a run may use. The values are then taken from the approximation, which the independent check
    at the end of the solve (the error bound printed with the plan) still bounds; the limit says it, with the memory the exact method needed. Empty when the
    exact method was made, or not needed.
    """
    found = info.get("linear_limit")
    if not found:
        return ()
    need = ""
    if found.get("cells"):
        need = f"; the exact calculation would need about {found['cells'] * 8 / 1e9:.1f} GB of memory and a run may use {found['allowed'] * 8 / 1e9:.1f} GB"
    return (
        Limit(
            _limits.SOLVE,
            "How much each state costs was found by approximation",
            f"the plan has {found['states']:,} states whose costs depend on each other through long loops, and the approximation stopped at a true residual of {found['residual']:.1e}, and on a system this stiff the costs can be off by more than a residual: by that times a factor of at least {found['amplification']:,.0f}{need}",
            "The error bound printed with the plan is certified by a separate check against the exact rules of the model; the costs are not shown to be closer than that bound.",
        ),
    )
