"""The steps of a policy: one step per player action, with the exact mixture of the chances of its item states.

A step is the set of states on which the policy takes the same action, found by its label and nothing else
(OR-18): states with different actions branch, and neither a different chance nor a detail the search does not
track splits one action into several steps. States with no action (a dead end of a policy, a gap of a given
route) are steps too, one per reason. Steps are numbered in the order their first state is met breadth-first.

The states are item states, never the blocks of a lumped chain: a lumped view shows a block by one member, and
what a page says about an item (a mod lost, the tiers a draw can add) is a fact about one item. `Chain` is the
policy on item states as arrays (a state per row, its edges in CSR form); `chain_of_policy` makes one from any
policy mapping and `_route_chain` makes one from the walked graph of a packed plan, without building an `Action`
per state. `flow_of(chain)` is the one place the steps are made.

The chances of a step (OR-20). The states of one step need not have the same chance for an outcome, so the step
shows the mixture of them: for an outcome, the sum over the step's states of (expected visits of the state x its
chance) divided by the expected visits of the step. The weights are the expected visits from the start under the
policy itself: row `start` of N = (I - Q)^-1, where Q holds the chances among the states that have an action and can
reach a goal. Up to `ENTRY_STATES` such states N is inverted (dense, float64); above that the row is the solution of
the sparse system (I - Q)^T v = e_start by BiCGSTAB on the edge arrays (the method and the code of the packed
solver's policy evaluation, with each self-loop divided out so that no `1 - p` is formed), checked by its residual,
with a dense solve as the fallback for up to `DENSE_FALLBACK` states. Memory is O(edges), never O(states^2), above
`ENTRY_STATES`. The chances are `Fraction`s of integer weights turned to float64 once (correctly rounded). From the
same N come the uses of a step (the sum of the visits of its states, so `sum(uses x cost)` is the mean cost of the
policy) and, for a step with an action, the chance a run ever enters it. A step with no action is entered with the
chance of stepping into it from the visited states. A state from which no run can ever reach a goal (it loops
forever, or every way out ends in a state with no action) has no visits: a step whose states are all of that kind has
`uses = inf` and the plain mean of its states as its chances; in a step that also has states that can finish, only
those are counted.

Two things are stated, not hidden (OR-12, OR-13), and both leave the chances and uses exact where they are shown:

* `Flow.measured` is False when the visits cannot be solved (a chance per use so small that it is lost in the
  float, or a sparse solve that did not reach its residual): the uses and visits are then not known, and the chances
  of a step with several states are the plain mean of them. The page says so on each step it applies to.
* `Flow.entered` is False when the policy has more than `ENTRY_STATES` states that can finish: the chance a run
  enters a step needs a solve per step, and it is left out (`Step.reached` is None for every step but the first,
  which is reached for sure). Uses, costs and chances do not depend on it.

Both are `Limit` records (`flow_limits`, kind `STEPS`) written into `Plan.limits` when a plan is finished and shown, like every limit, by the text
report, the JSON and the goal card of the page; a given route's own chain gets its own on its section.

An edge groups the outcomes that lead to the same place: a goal, or the next step. `kind`: "goal", "failure"
(the item lost a wanted mod, the action is a restart, or the item lands in a step that restarts or that has no
action: it is thrown away or the route stops), "again" (the same step, nothing lost), "forward" (any other step).
Nothing is decided by what the item still costs to finish (PRES-6). What a use loses of the wanted mods is told by
the caller (`loss`), which keeps this module free of the compressed state. Pure, no I/O, deterministic.
"""

import math
import time
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

import numpy as np

from crafting_system.solver import Action
from crafting_system.solver._packed_solve import _bicgstab

from ._limits import STEPS, Limit, claim
from ._reach import policy_states

ENTRY_STATES = 1000  # up to this many states that can finish N is inverted and the chance of entering a step is solved per step; above it only the visits are found (sparse)
DENSE_FALLBACK = 6000  # a sparse solve that did not converge falls back to a dense one for up to this many states
VISITS_TOLERANCE = 1e-12  # the relative residual BiCGSTAB aims at
ACCEPT_RESIDUAL = 1e-9  # the largest relative residual of the visits that is shown; above it the flow is not `measured`
BICGSTAB_ITERATIONS = 4000
BICGSTAB_RESTARTS = 3
EXACT_RETURNS = 25  # above `ENTRY_STATES` states the chance that a state is visited needs a solve of its own: this many states (the most visited first) get one, the rest a bound (`reach_of`)
EXACT_RETURN_EDGES = 5_000_000  # ... and only on a chain of at most this many edges: R04's policy has 18,696 states and about 28 million edges, where one solve took over two minutes (ticket #554, issue #572)
_GOAL = -1  # the target "a goal state" while steps are numbered from 0


@dataclass(frozen=True)
class Edge[S]:
    """Where some outcomes of a step's action lead.

    `kind`: "goal" the target reached (`to` is then None), "failure" a wanted mod lost, a restart, or a landing
    in a step that restarts or has no action, "again" the same step with nothing lost, "forward" any other step.
    `chance` is the chance per use of the action, mixed over the step's states by their expected visits; `states` are
    the states the outcomes land in (goal states for "goal"); `lost` is everything the loss reader said some of
    them loses (the wanted mods, sorted), empty when no use of the edge loses any.
    """

    kind: Literal["forward", "failure", "again", "goal"]
    to: int | None
    chance: float
    states: tuple[S, ...]
    lost: tuple = ()


@dataclass(frozen=True)
class Step[S]:
    """One step of the route.

    `states`: the item states it stands for, in breadth-first order. `weights`: the expected visits of each
    of them from the start, the weights of the mixture (all 1.0 when the flow is not `measured`, or when none
    of the states can finish). `action`: the action of the step's first state, the label every state shares; None
    when there is no action here and then `reason` says why. `cost`: the cost per use, the mean over the states by
    their weights (the same number for every state of one offer). `edges`: one per distinct (target, whether a
    wanted mod is lost) pair, the goal first, then by step number; empty without an action. `uses`: the expected
    number of uses of the action in one run from the start (None without an action, or when the flow is not
    `measured`). `reached`: the chance a run ever enters the step.
    """

    number: int
    states: tuple[S, ...]
    action: Action[S] | None
    reason: str | None
    edges: tuple[Edge[S], ...]
    uses: float | None
    reached: float | None
    weights: tuple[float, ...] = ()
    cost: float = 0.0


@dataclass(frozen=True)
class Flow[S]:
    """The steps (numbered from 1, the start's step first) and the step of every reachable non-goal state.

    `measured`: whether the expected visits were computed (False when the chain cannot be solved).
    `entered`: whether `Step.reached` was computed (False above `ENTRY_STATES` states, see the module text).
    """

    steps: tuple[Step[S], ...]
    step_of: Mapping[S, int]
    measured: bool = True
    entered: bool = True


@dataclass(frozen=True, eq=False)
class Chain[S]:
    """The policy on item states as arrays.

    `states`: the reachable non-goal states, the start first (row `i` of every array); `goals`: the goal states they
    lead to. `key[i]` is the index into `keys` of the step the state belongs to: `("action", label)` or
    `("none", reason)` for a state with no action. `cost[i]` is the price of its action. The edges of state `i`
    are `ptr[i]:ptr[i + 1]` of `dst` and `prob`: `dst < len(states)` is a state, `dst >= len(states)` is
    the goal `goals[dst - len(states)]`; `prob` sums to 1 on a state with an action and the edges are in outcome order.
    `action_of(i)` is the solver action of state `i` (called for the first state of a step only).
    """

    states: Sequence[S]
    goals: Sequence[S]
    key: np.ndarray
    keys: tuple[Hashable, ...]
    cost: np.ndarray
    ptr: np.ndarray
    dst: np.ndarray
    prob: np.ndarray
    action_of: Callable[[int], Action[S]]

    @property
    def m(self) -> int:
        return len(self.states)


def empty_chain() -> Chain:
    """The chain of a start that already is a goal: no step."""
    zero = np.zeros(0, dtype=np.int64)
    return Chain([], [], zero, (), np.zeros(0), np.zeros(1, dtype=np.int64), zero, np.zeros(0), lambda i: None)  # type: ignore[arg-type,return-value]


def chain_of_policy[S: Hashable](
    start: S, policy: Mapping[S, Action[S]], is_goal: Callable[[S], bool], reasons: Mapping[S, str] | None = None
) -> Chain[S]:
    """The chain of `policy` from `start`; `reasons` says why a reachable non-goal state has no entry in `policy`."""
    if is_goal(start):
        return empty_chain()
    reasons = reasons or {}
    states = [s for s in policy_states(start, policy, is_goal) if not is_goal(s)]
    index = {s: i for i, s in enumerate(states)}
    m = len(states)
    goals: list[S] = []
    goal_index: dict[S, int] = {}
    keys: dict[Hashable, int] = {}
    key = np.zeros(m, dtype=np.int64)
    cost = np.zeros(m)
    ptr = [0]
    dst: list[int] = []
    prob: list[float] = []
    for i, state in enumerate(states):
        if state in policy:
            action = policy[state]
            key[i] = keys.setdefault(("action", action.label), len(keys))
            cost[i] = action.cost
            total = sum(weight for _, weight in action.outcomes)
            merged: dict[S, Fraction] = {}
            for successor, weight in action.outcomes:
                if weight > 0:
                    merged[successor] = merged.get(successor, Fraction(0)) + Fraction(weight, total)
            for successor, chance in merged.items():
                if is_goal(successor):
                    dst.append(m + goal_index.setdefault(successor, len(goal_index)))
                    if len(goals) < len(goal_index):
                        goals.append(successor)
                else:
                    dst.append(index[successor])
                prob.append(float(chance))
        else:
            key[i] = keys.setdefault(("none", reasons.get(state)), len(keys))
        ptr.append(len(dst))
    return Chain(
        states,
        goals,
        key,
        tuple(keys),
        cost,
        np.array(ptr, dtype=np.int64),
        np.array(dst, dtype=np.int64),
        np.array(prob),
        lambda i: policy[states[i]],
    )


def failure_by(failed: Callable[[S, S], tuple] | None) -> Callable | None:  # type: ignore[type-var]
    """A loss reader from `failed(state, landing)`, which says what a use that takes `state` to `landing` loses (a tuple of sortable items, empty for nothing)."""
    if failed is None:
        return None

    def loss(chain: Chain, src: np.ndarray, dst: np.ndarray) -> tuple[Sequence, np.ndarray]:
        everything = [*chain.states, *chain.goals]
        found = [tuple(failed(chain.states[s], everything[d])) for s, d in zip(src.tolist(), dst.tolist())]
        items = sorted({item for each in found for item in each})
        column = {item: u for u, item in enumerate(items)}
        matrix = np.zeros((len(found), len(items)), dtype=bool)
        for e, each in enumerate(found):
            for item in each:
                matrix[e, column[item]] = True
        return items, matrix

    return loss


def build_flow[S: Hashable](
    start: S,
    policy: Mapping[S, Action[S]],
    is_goal: Callable[[S], bool],
    reasons: Mapping[S, str] | None = None,
    is_restart: Callable[[Action[S]], bool] | None = None,
    failed: Callable[[S, S], tuple] | None = None,
) -> Flow[S]:
    """The steps of `policy` from `start`; `reasons` says why a reachable non-goal state has no entry in `policy`.

    A start that is a goal gives an empty flow. `is_restart` says which actions go back to the start: all their
    edges are failures. `failed(state, landing)` says what a use that takes `state` to `landing` loses of the
    wanted mods: a tuple of sortable items (the leaves of the target it stops meeting), empty for nothing. Outcomes that
    lead to the same step are one edge, except that those which lose a wanted mod are apart from those which do not.
    """
    return flow_of(chain_of_policy(start, policy, is_goal, reasons), is_restart, failure_by(failed))


def flow_of[S: Hashable](
    chain: Chain[S],
    is_restart: Callable[[Action[S]], bool] | None = None,
    loss: Callable[[Chain, np.ndarray, np.ndarray], tuple[Sequence, np.ndarray]] | None = None,
) -> Flow[S]:
    """The steps of `chain`. `loss(chain, src, dst)` gives `(items, matrix)`: for the edges `src[e] -> dst[e]` which of `items` they lose."""
    m = chain.m
    if m == 0:
        return Flow((), {})
    edges_per_state = np.diff(chain.ptr)
    src = np.repeat(np.arange(m), edges_per_state)
    dst = chain.dst
    into_goal = dst >= m
    into_state = ~into_goal

    # the steps: one per key, numbered by the first state that has it
    nkeys = len(chain.keys)
    first_of_key = np.full(nkeys, m, dtype=np.int64)
    np.minimum.at(first_of_key, chain.key, np.arange(m))
    used = np.flatnonzero(first_of_key < m)
    used = used[np.argsort(first_of_key[used], kind="stable")]
    rank = np.full(nkeys, -1, dtype=np.int64)
    rank[used] = np.arange(len(used))
    nsteps = len(used)
    step = rank[chain.key]  # step number from 0 of every state
    step_key = [chain.keys[k] for k in used.tolist()]
    step_first = first_of_key[used]
    step_acts = np.array([k[0] == "action" for k in step_key], dtype=bool)
    step_action = [chain.action_of(int(i)) if acts else None for i, acts in zip(step_first.tolist(), step_acts.tolist())]
    restarting = np.array(
        [action is not None and is_restart is not None and bool(is_restart(action)) for action in step_action], dtype=bool
    )
    has_action = step_acts[step]

    finishing = _can_finish(m, src, dst, into_goal, into_state)
    visits, solved, inverse, tpos = _visits(chain, src, finishing)
    weights = np.where(finishing, visits, 0.0) if solved else np.zeros(m)
    raw = np.bincount(step, weights=weights, minlength=nsteps)
    mix = np.where(raw[step] > 0.0, weights, 1.0)  # nobody can finish here, or unmeasured: the plain mean
    total = np.bincount(step, weights=mix, minlength=nsteps)
    reached = _entered(chain, step, nsteps, src, finishing, visits, inverse, tpos)

    # the edges, grouped by (step, target step, whether a wanted mod is lost)
    target = np.where(into_goal, _GOAL, step[np.minimum(dst, m - 1)])
    if loss is None or len(dst) == 0:
        items, lost_matrix = (), np.zeros((len(dst), 0), dtype=bool)
    else:
        items, lost_matrix = loss(chain, src, dst)
    lost_edge = lost_matrix.any(axis=1) if lost_matrix.shape[1] else np.zeros(len(dst), dtype=bool)
    lost_edge &= ~into_goal & ~restarting[step[src]]  # a restart is one failure whatever it throws away
    lost_matrix = lost_matrix & lost_edge[:, None]
    code = ((step[src] * (nsteps + 1) + (target + 1)) * 2 + lost_edge).astype(np.int64)
    group_codes, group = np.unique(code, return_inverse=True)
    ngroups = len(group_codes)
    group_lost = np.array([(c % 2) == 1 for c in group_codes.tolist()], dtype=bool)
    group_target = (group_codes // 2) % (nsteps + 1) - 1
    group_step = (group_codes // 2) // (nsteps + 1)
    chance = np.bincount(group, weights=mix[src] * chain.prob, minlength=ngroups) / total[group_step]
    gone = [np.bincount(group, weights=lost_matrix[:, u], minlength=ngroups) > 0 for u in range(len(items))]
    width = m + len(chain.goals)
    pair = np.unique(group.astype(np.int64) * width + dst)  # the distinct landing states of each group, sorted
    pair_group = pair // width
    bounds = np.searchsorted(pair_group, np.arange(ngroups + 1))
    everything = (lambda d: chain.states[d] if d < m else chain.goals[d - m])
    edges_of: list[list[Edge]] = [[] for _ in range(nsteps)]
    for g in range(ngroups):
        s, t = int(group_step[g]), int(group_target[g])
        if t == _GOAL:
            kind = "goal"
        elif restarting[s] or group_lost[g] or not step_acts[t] or restarting[t]:
            kind = "failure"
        elif t == s:
            kind = "again"
        else:
            kind = "forward"
        landing = tuple(everything(int(d)) for d in (pair[bounds[g] : bounds[g + 1]] % width).tolist())
        lost = tuple(sorted(items[u] for u in range(len(items)) if gone[u][g]))
        edges_of[s].append(Edge(kind, None if t == _GOAL else t + 1, float(chance[g]), landing, lost))  # type: ignore[arg-type]

    # the steps
    order = np.argsort(step, kind="stable")
    bounds = np.searchsorted(step[order], np.arange(nsteps + 1))
    uses_sum = np.bincount(step, weights=np.where(finishing, visits, 0.0), minlength=nsteps)
    finishers = np.bincount(step, weights=finishing, minlength=nsteps)
    mean_cost = np.bincount(step, weights=mix * chain.cost, minlength=nsteps) / total
    steps = []
    for s in range(nsteps):
        members = order[bounds[s] : bounds[s + 1]]
        if step_acts[s]:
            uses = math.inf if finishers[s] == 0 else (float(uses_sum[s]) if solved else None)
        else:
            uses = None
        key = step_key[s]
        steps.append(
            Step(
                number=s + 1,
                states=tuple(chain.states[i] for i in members.tolist()),
                action=step_action[s],
                reason=None if step_acts[s] else key[1],
                edges=tuple(edges_of[s]) if step_acts[s] else (),
                uses=uses,
                reached=reached[s],
                weights=tuple(mix[members].tolist()),
                cost=float(mean_cost[s]) if step_acts[s] else 0.0,
            )
        )
    entered = inverse is not None or not finishing[0]
    return Flow(tuple(steps), {chain.states[i]: int(step[i]) + 1 for i in range(m)}, solved, entered)


def flow_limits(chain: Chain) -> tuple[Limit, ...]:
    """The limits of the steps made from `chain` (OR-12, OR-13): what the page then cannot promise. Empty when the visits were solved and the entry chances computed.

    Found by the solve itself, so they are written wherever a plan is finished (`Plan.limits`) and for a given route's own chain.
    """
    if chain.m == 0:
        return ()
    src = np.repeat(np.arange(chain.m), np.diff(chain.ptr))
    into_goal = chain.dst >= chain.m
    finishing = _can_finish(chain.m, src, chain.dst, into_goal, ~into_goal)
    _, solved, inverse, _ = _visits(chain, src, finishing)
    if not solved:
        return (
            Limit(
                STEPS,
                "How often a step is used is not shown",
                "how often a run is in each state could not be computed reliably: some chances are too small for the arithmetic used, "
                "or the calculation did not settle",
                **claim(
                    "the methods offered",
                    "The page leaves out how often each step is used and what it costs, and the chances of a step that joins several states are the "
                    "plain mean of those states, not the mean weighted by how often a run is in each.",
                ),
            ),
        )
    if inverse is None and finishing[0]:
        return (
            Limit(
                STEPS,
                "How often a run enters a step is not shown",
                f"the plan has {int(finishing.sum()):,} states that can finish, and the chance of entering a step needs a separate calculation "
                f"for each, made only up to {ENTRY_STATES:,} states",
                **claim(
                    "the methods offered",
                    "The uses and cost of each step and the chances of each step are as shown; only the share of runs that ever enter a step is missing.",
                ),
            ),
        )
    return ()


def _can_finish(m: int, src: np.ndarray, dst: np.ndarray, into_goal: np.ndarray, into_state: np.ndarray) -> np.ndarray:
    """The states with an action from which some run reaches a goal through states that have an action."""
    finishing = np.zeros(m, dtype=bool)
    finishing[src[into_goal]] = True
    toward = np.minimum(dst, m - 1)
    while True:
        hit = into_state & finishing[toward]
        fresh = np.zeros(m, dtype=bool)
        fresh[src[hit]] = True
        fresh &= ~finishing
        if not fresh.any():
            return finishing
        finishing |= fresh


def _visits(chain: Chain, src: np.ndarray, finishing: np.ndarray):
    """`(visits, solved, inverse, position)`: the expected visits from the start of each state (zero where a run cannot finish).

    `position[i]` numbers the states that can finish; `inverse` is N over them when there are at most `ENTRY_STATES`.
    When the start cannot finish nothing else is a run's business: all zero and solved. `solved` is False when the
    system could not be solved to `ACCEPT_RESIDUAL`.
    """
    m = chain.m
    visits = np.zeros(m)
    if not finishing[0]:
        return visits, True, None, None
    position = np.cumsum(finishing) - 1
    nt = int(finishing.sum())
    dst = chain.dst
    inside = finishing[src] & (dst < m)
    inside[inside] = finishing[dst[inside]]
    row, column, p = position[src[inside]], position[dst[inside]], chain.prob[inside]
    try:
        with np.errstate(all="ignore"):
            if nt <= ENTRY_STATES:
                matrix = np.eye(nt) - np.bincount(row * nt + column, weights=p, minlength=nt * nt).reshape(nt, nt)
                inverse = np.linalg.inv(matrix)
                found = inverse[position[0]]
            else:
                inverse = None
                found = _sparse_visits(chain, src, finishing, position, nt, row, column, p)
    except np.linalg.LinAlgError:  # a chance per use so small that 1 - q is 1 in floats: nothing to say about visits
        return visits, False, None, position
    if found is None or not np.all(np.isfinite(found)) or np.any(found < -1e-9):
        return visits, False, None, position
    visits[finishing] = np.maximum(found, 0.0)
    return visits, True, inverse, position


def _sparse_visits(chain, src, finishing, position, nt, row, column, p):
    """Row `start` of N by BiCGSTAB on (I - Q)^T v = e_start, each row divided by the chance to leave its state (self-loops out)."""
    nonself = chain.dst != src
    leave = np.bincount(src[nonself], weights=chain.prob[nonself], minlength=chain.m)[finishing]  # a sum of positive terms
    keep = row != column
    r, c, w = row[keep], column[keep], p[keep]
    coefficient = w / leave[c]  # the edge row -> column enters `column`: v_column - sum v_row p / leave_column = e / leave
    b = np.zeros(nt)
    b[position[0]] = 1.0 / leave[position[0]]

    def matvec(x: np.ndarray) -> np.ndarray:
        return x - np.bincount(c, weights=coefficient * x[r], minlength=nt)

    x, residual, _ = _bicgstab(matvec, b, np.zeros(nt), VISITS_TOLERANCE, BICGSTAB_ITERATIONS)
    for _ in range(BICGSTAB_RESTARTS):
        if residual <= 10 * VISITS_TOLERANCE:
            break
        x, residual, _ = _bicgstab(matvec, b, x, VISITS_TOLERANCE, BICGSTAB_ITERATIONS)
    if residual > 1e-10 and nt <= DENSE_FALLBACK:  # a stiff system: the dense solve is slow but sure
        matrix = np.eye(nt)
        np.subtract.at(matrix, (c, r), coefficient)  # matrix[column, row] -= coefficient
        scaled = np.linalg.solve(matrix, b)
        return scaled
    return x if residual <= ACCEPT_RESIDUAL else None


@dataclass(frozen=True)
class Reach:
    """The chance a run ever visits one state of a chain (ticket #554).

    `chance` is None when it is not measured: the visits could not be solved, the start cannot finish, or the state is one from
    which no run can finish (a route that stops there). `exact` is False when `chance` is an upper bound, never a guess: the
    state's return chance needed a solve of its own that was not made (see `EXACT_RETURNS`).
    """

    chance: float | None
    exact: bool = True


def reach_of(chain: Chain, wanted: Sequence[int]) -> list[Reach]:
    """The chance a run ever visits each of the states `wanted` (indexes into `chain.states`), from the start: N[start, s] / N[s, s].

    The expected visits are the same solve the steps of the page use (`_visits`). With at most `ENTRY_STATES` states that can
    finish, N is inverted and the answer is exact for every state. Above that the visits v(s) are known for every state and the
    chance is v(s) times the chance that a run which leaves s never comes back, which is one sparse solve per state with s made
    absorbing; it is made for the `EXACT_RETURNS` most visited states of `wanted`, and the others get the upper bound
    v(s) (1 - the chance of a self-loop of s), marked not `exact`; a chain of more than `EXACT_RETURN_EDGES` edges gets bounds only. The start is visited with chance 1.
    """
    m = chain.m
    unknown = Reach(None, False)
    if m == 0:
        return [unknown for _ in wanted]
    src = np.repeat(np.arange(m), np.diff(chain.ptr))
    dst = chain.dst
    finishing = _can_finish(m, src, dst, dst >= m, dst < m)
    from . import _packed  # a measuring script sets `_packed.PROGRESS`; the library never does

    began = time.perf_counter()
    say = _packed.PROGRESS or (lambda _text: None)
    visits, solved, inverse, position = _visits(chain, src, finishing)
    say(f"visit chances: the visits of {int(finishing.sum()):,} states that can finish solved ({time.perf_counter() - began:.1f} s)")
    found: dict[int, Reach] = {}
    sparse: list[int] = []
    for i in dict.fromkeys(wanted):
        if i == 0:
            found[i] = Reach(1.0)
        elif not solved or not finishing[0] or not finishing[i]:
            found[i] = unknown
        elif inverse is not None:
            a, b = position[0], position[i]
            found[i] = Reach(min(1.0, max(0.0, float(inverse[a, b] / inverse[b, b]))))
        else:
            sparse.append(i)
    if sparse:
        found.update(_sparse_reach(chain, src, finishing, position, visits, sparse))
    return [found[i] for i in wanted]


def _sparse_reach(chain: Chain, src: np.ndarray, finishing: np.ndarray, position: np.ndarray, visits: np.ndarray, states: list[int]) -> dict[int, Reach]:
    """`reach_of` above `ENTRY_STATES` states: v(s) times the chance that a run leaving s never returns."""
    m, dst = chain.m, chain.dst
    nt = int(finishing.sum())
    inside = finishing[src] & (dst < m)
    inside[inside] = finishing[dst[inside]]
    row, column, p = position[src[inside]], position[dst[inside]], chain.prob[inside]
    nonself = dst != src
    leave = np.bincount(src[nonself], weights=chain.prob[nonself], minlength=m)[finishing]  # a sum of positive terms
    stay = np.bincount(src[~nonself], weights=chain.prob[~nonself], minlength=m)  # the chance of a self-loop
    ordered = sorted(states, key=lambda i: -visits[i])
    solving = len(dst) <= EXACT_RETURN_EDGES
    found: dict[int, Reach] = {}
    for rank, i in enumerate(ordered):
        bound = min(1.0, float(visits[i] * (1.0 - stay[i])))
        returned = _escape(row, column, p, leave, nt, int(position[i])) if solving and rank < EXACT_RETURNS else None
        found[i] = Reach(min(1.0, max(0.0, float(visits[i] * returned))), True) if returned is not None else Reach(bound, False)
    return found


def _escape(row, column, p, leave, nt: int, s: int) -> float | None:
    """The chance that a run which is in state `s` (a position among the finishing states) never comes back to it; None when the solve did not reach its residual.

    h(t) is the chance of ever reaching s from t, with s absorbing: h(t) - sum over u (not t, not s) of p(t, u) / leave(t) h(u) =
    p(t, s) / leave(t), each self-loop divided out as in `_sparse_visits`. The chance of escaping is sum over u of p(s, u) (1 - h(u))
    for the edges of s that leave it (a goal or a state that cannot finish counts as h = 0), a sum of positive terms.
    """
    keep = (row != column) & (row != s)  # the edges of s itself are not part of the system
    into = keep & (column == s)
    inner = keep & (column != s)
    r, c, w = row[inner], column[inner], p[inner] / leave[row[inner]]
    b = np.bincount(row[into], weights=p[into] / leave[row[into]], minlength=nt)

    def matvec(x: np.ndarray) -> np.ndarray:
        return x - np.bincount(r, weights=w * x[c], minlength=nt)

    h, residual, _ = _bicgstab(matvec, b, np.zeros(nt), VISITS_TOLERANCE, BICGSTAB_ITERATIONS)
    for _ in range(BICGSTAB_RESTARTS):
        if residual <= 10 * VISITS_TOLERANCE:
            break
        h, residual, _ = _bicgstab(matvec, b, h, VISITS_TOLERANCE, BICGSTAB_ITERATIONS)
    if not residual <= ACCEPT_RESIDUAL:
        return None
    out = (row == s) & (column != s)
    back = float(np.sum(p[out] * h[column[out]]))
    leaving = float(leave[s])  # the chance to leave s, to every state, goal or not
    return max(0.0, leaving - back)


def _entered(chain, step, nsteps, src, finishing, visits, inverse, position) -> list[float | None]:
    """The chance a run ever enters each step: 1 for the first, None for the others when `inverse` (N) is not there.

    For a step A of states that can finish, the first state of A a run meets is a with chance H(a), and the visits
    of N split by it: N[start, b] = sum over a in A of H(a) N[a, b], so H = N[start, A] N[A, A]^-1 and the chance is
    its sum. A step of states that cannot finish (a dead end, a gap) is entered from the states that can: its
    chance is the expected number of such steps into it, since a run never comes back from it. A step that has
    both kinds of state is left unmeasured (None).
    """
    result: list[float | None] = [None] * nsteps
    result[0] = 1.0
    if inverse is None or not finishing[0]:
        return result
    m = chain.m
    row = inverse[position[0]]
    for s in range(1, nsteps):
        members = np.flatnonzero(step == s)
        live = finishing[members]
        if 0 in members:
            result[s] = 1.0
        elif live.all():
            inside = position[members]
            try:
                with np.errstate(all="ignore"):
                    first = np.linalg.solve(inverse[np.ix_(inside, inside)].T, row[inside])
            except np.linalg.LinAlgError:
                continue
            value = float(first.sum())
            result[s] = min(1.0, max(0.0, value)) if math.isfinite(value) else None
        elif not live.any():
            into = np.zeros(m, dtype=bool)
            into[members] = True
            edge = (chain.dst < m) & into[np.minimum(chain.dst, m - 1)] & finishing[src]
            result[s] = min(1.0, max(0.0, float(np.sum(visits[src[edge]] * chain.prob[edge]))))
    return result
