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
reach a goal. They are the solution of the system (I - Q)^T v = e_start with each self-loop divided out so that no
`1 - p` is formed: dense for at most `DENSE_LIMIT` such states, else BiCGSTAB on the edge arrays (memory O(edges),
never O(states^2)). The dense solve and the iteration are two ways to the same numbers, a speed choice and no cut (a
test lowers the limit and compares). What is shown is a solution whose TRUE residual `|b - A x| / |b|` was measured,
never the residual BiCGSTAB claims of its own recurrence (tickets #584 and #600); a solve that does not reach it
falls back to the dense solve for up to `DENSE_FALLBACK` states, else the flow is not `measured`. The chances are
`Fraction`s of integer weights turned to float64 once (correctly rounded). From the same visits come the uses of a
step (the sum of the visits of its states, so `sum(uses x cost)` is the mean cost of the policy) and, for a step with
an action, the chance a run ever enters it: the chance of reaching a state of the step when the step's states
absorb, one solve of the same kind for each step, whatever the size of the policy (ticket #490). A step with no
action is entered with the chance of stepping into it from the visited states. A state from which no run can ever
reach a goal (it loops forever, or every way out ends in a state with no action) has no visits: a step whose states
are all of that kind has `uses = inf` and the plain mean of its states as its chances; in a step that also has
states that can finish, only those are counted.

`reach_of` gives the chance a run ever visits a state, N[start, s] / N[s, s], for any state of a chain of
any size (ticket #572), as a number and never as a bound: the diagonal of N comes from the cycles of the chain (`solver/_packed_chain.py`) and is
checked against the visits, which another method found.

Three things are stated, not hidden (OR-12, OR-13), and the chances and uses are as solved where they are shown:

* `Flow.measured` is False when the visits cannot be solved (a chance per use so small that it is lost in the
  float, or a solve whose true residual stayed above `ACCEPT_RESIDUAL`): the uses and visits are then not known, and
  the chances of a step with several states are the plain mean of them. The page says so on each step it applies to.
* `Flow.entered` is False when the chance of entering some step could not be solved to that residual (`Step.reached`
  is None for it). Uses, costs and chances do not depend on it, and it does not depend on the size of the policy.
* The digits. What is checked is a residual (`ACCEPT_RESIDUAL`), and a stiff chain loses digits between a residual and an answer: a plan whose
  runs take millions of steps is good to fewer digits than `percent` prints. `precision_of` estimates the error the residual guarantees (that
  residual times the expected steps of a run) and `flow_limits` says how many digits it supports once it passes `STIFF_ERROR`.

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
from crafting_system.solver._packed_chain import CyclesTooTangled, inverse_diagonal
from crafting_system.solver._packed_solve import DENSE_FALLBACK, DENSE_FALLBACK_RESIDUAL, DENSE_LIMIT, bicgstab_checked

from ._limits import STEPS, Limit, claim
from ._reach import policy_states

VISITS_TOLERANCE = 1e-12  # the relative residual BiCGSTAB aims at
ACCEPT_RESIDUAL = 1e-9  # the largest true relative residual of a solve that is shown; above it the flow is not `measured`
AGREE = 1e-6  # the most the visits (iteration) and the same row from the cycles of the chain (direct) may differ for the visit chances to be shown
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

    @property
    def never_finishes(self) -> bool:
        """Whether no run that enters the step can finish from it (its uses are infinite)."""
        return self.uses is not None and math.isinf(self.uses)

    @property
    def step_cost(self) -> float | None:
        """What the step costs in a run on average, uses times cost per use; None when it has no action, its uses are not solved, or it never finishes.

        The one place this is computed: the route page and the text report both read it, so the buy plus the step costs add up to the mean the same way in both.
        """
        return None if self.uses is None or self.never_finishes else self.uses * self.cost


@dataclass(frozen=True)
class Flow[S]:
    """The steps (numbered from 1, the start's step first) and the step of every reachable non-goal state.

    `measured`: whether the expected visits were computed (False when the chain cannot be solved).
    `entered`: whether `Step.reached` was computed for every step it can be (False when a solve of the chance of entering a step did not reach its residual, see the module text).
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

    step, used, first_of_key = _numbering(chain)  # step number from 0 of every state
    nsteps = len(used)
    step_key = [chain.keys[k] for k in used.tolist()]
    step_first = first_of_key[used]
    step_acts = np.array([k[0] == "action" for k in step_key], dtype=bool)
    step_action = [chain.action_of(int(i)) if acts else None for i, acts in zip(step_first.tolist(), step_acts.tolist())]
    restarting = np.array(
        [action is not None and is_restart is not None and bool(is_restart(action)) for action in step_action], dtype=bool
    )
    has_action = step_acts[step]

    done = _solved(chain)  # made once for a chain: the plan's limits and the page both read them
    finishing, visits, solved = done.finishing, done.visits, done.solved
    reached, unsettled = _entries(chain)
    weights = np.where(finishing, visits, 0.0) if solved else np.zeros(m)
    raw = np.bincount(step, weights=weights, minlength=nsteps)
    mix = np.where(raw[step] > 0.0, weights, 1.0)  # nobody can finish here, or unmeasured: the plain mean
    total = np.bincount(step, weights=mix, minlength=nsteps)

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
    return Flow(tuple(steps), {chain.states[i]: int(step[i]) + 1 for i in range(m)}, solved, solved and unsettled == 0)


def flow_limits(chain: Chain) -> tuple[Limit, ...]:
    """The limits of the steps made from `chain` (OR-12, OR-13): what the page then cannot promise. Empty when the visits were solved, the entry chances computed and the digits printed are supported by the residual.

    Found by the solve itself, so they are written wherever a plan is finished (`Plan.limits`) and for a given route's own chain.
    """
    if chain.m == 0:
        return ()
    done = _solved(chain)
    if not done.solved:
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
    reached, unsettled = _entries(chain)
    limits: list[Limit] = []
    if unsettled:
        limits.append(
            Limit(
                STEPS,
                "How often a run enters a step is not shown",
                f"the calculation of the share of runs that enter a step did not settle for {unsettled} of the {len(reached)} steps",
                **claim(
                    "the methods offered",
                    "The uses and cost of each step and the chances of each step are as shown; only the share of runs that ever enter a step is missing where it did not settle.",
                ),
            )
        )
    error = precision_of(done)
    if error > STIFF_ERROR:  # the residual is what is checked; on a stiff chain the digits are fewer than the residual (OR-13)
        limits.append(
            Limit(
                STEPS,
                "The numbers of the steps are good to fewer digits than printed",
                f"a run of this plan takes about {float(done.visits.sum()):,.0f} steps, and a solve checked to a residual of {ACCEPT_RESIDUAL:g} is then good to about "
                f"{digits_text(error)} significant digits",
                **claim(
                    "the methods offered",
                    f"How often each step is used, what it costs, its chances and the share of runs that enter it are solutions of the plan's equations to a residual of {ACCEPT_RESIDUAL:g}; "
                    f"on a plan that takes this many steps that supports about {digits_text(error)} digits, not the digits printed.",
                ),
            )
        )
    return tuple(limits)


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


def _numbering(chain: Chain) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`(step, used, first_of_key)`: the steps are the keys in use, numbered by the first state that has the key; `step[i]` is the number from 0 of state `i`."""
    m = chain.m
    nkeys = len(chain.keys)
    first_of_key = np.full(nkeys, m, dtype=np.int64)
    np.minimum.at(first_of_key, chain.key, np.arange(m))
    used = np.flatnonzero(first_of_key < m)
    used = used[np.argsort(first_of_key[used], kind="stable")]
    rank = np.full(nkeys, -1, dtype=np.int64)
    rank[used] = np.arange(len(used))
    return rank[chain.key], used, first_of_key


@dataclass(frozen=True)
class _Solved:
    """What the visits solve of a chain gives, made once (`_solved`): the states that can finish and their expected visits.

    `solved`: the visits were solved to `ACCEPT_RESIDUAL`. `inverse`: N over the states that can finish, when there are at most `DENSE_LIMIT` of them.
    """

    finishing: np.ndarray
    visits: np.ndarray
    solved: bool
    inverse: np.ndarray | None


def _solved(chain: Chain) -> _Solved:
    """The visits of `chain`, kept on it: the plan's limits, the page and the benchmark all read them, and a solve of a big policy takes a minute."""
    key = (DENSE_LIMIT, DENSE_FALLBACK, ACCEPT_RESIDUAL, VISITS_TOLERANCE)  # a test that changes a limit gets its own
    cached = chain.__dict__.get("_solved")
    if cached is None or cached[0] != key:
        m = chain.m
        src = np.repeat(np.arange(m), np.diff(chain.ptr))
        into_goal = chain.dst >= m
        finishing = _can_finish(m, src, chain.dst, into_goal, ~into_goal)
        visits, solved, inverse = _visits(chain, _system(chain, src, finishing), finishing)
        cached = (key, _Solved(finishing, visits, solved, inverse))
        object.__setattr__(chain, "_solved", cached)
    return cached[1]


def _entries(chain: Chain) -> tuple[list[float | None], int]:
    """`(reached, unsettled)` of `chain`, kept on it: the chance of entering each step (None where it is not defined or not solved) and how many steps had a solve that did not settle."""
    key = (DENSE_LIMIT, DENSE_FALLBACK, ACCEPT_RESIDUAL, VISITS_TOLERANCE)
    cached = chain.__dict__.get("_entries")
    if cached is None or cached[0] != key:
        done = _solved(chain)
        m = chain.m
        src = np.repeat(np.arange(m), np.diff(chain.ptr))
        step, used, _ = _numbering(chain)
        system = _system(chain, src, done.finishing)
        reached: list[float | None] = [None] * len(used)
        reached[0] = 1.0
        unsettled = 0
        if done.solved and system is not None:
            reached, unsettled = _entered(chain, step, len(used), src, done.finishing, done.visits, system, done.inverse)
        cached = (key, (reached, unsettled))
        object.__setattr__(chain, "_entries", cached)
    return cached[1]


@dataclass(frozen=True)
class _System:
    """The chain on the states that can finish: `position[i]` numbers them; the edges among them (`row -> column`, chance `p`); `leave[s]`: the chance to leave `s` for any other state, a goal or not; `leak[s]`: the chance to go to a goal or to a state that cannot finish."""

    position: np.ndarray
    nt: int
    row: np.ndarray
    column: np.ndarray
    p: np.ndarray
    leave: np.ndarray
    leak: np.ndarray


def _system(chain: Chain, src: np.ndarray, finishing: np.ndarray) -> _System | None:
    """The system of the states that can finish, None when the start cannot (then nothing else is a run's business)."""
    if not finishing[0]:
        return None
    m, dst = chain.m, chain.dst
    position = np.cumsum(finishing) - 1
    inside = finishing[src] & (dst < m)
    inside[inside] = finishing[dst[inside]]
    nonself = dst != src
    leave = np.bincount(src[nonself], weights=chain.prob[nonself], minlength=m)[finishing]  # a sum of positive terms: no `1 - p`
    outside = finishing[src] & ~inside
    leak = np.bincount(position[src[outside]], weights=chain.prob[outside], minlength=int(finishing.sum()))  # a sum of positive terms
    return _System(position, int(finishing.sum()), position[src[inside]], position[dst[inside]], chain.prob[inside], leave, leak)


def _visits(chain: Chain, system: _System | None, finishing: np.ndarray) -> tuple[np.ndarray, bool, np.ndarray | None]:
    """`(visits, solved, inverse)`: the expected visits from the start of each state (zero where a run cannot finish).

    Row `start` of N = (I - Q)^-1. With at most `DENSE_LIMIT` states that can finish, N is inverted whole (`inverse`, over the positions) and the row
    is read off it; its row is accepted only when it solves (I - Q)^T v = e_start to `ACCEPT_RESIDUAL`, else the system is solved as it is for more
    states: (I - Q)^T v = e_start with each self-loop divided out, v[c] = e[c] / leave[c] + sum over the edges r -> c of p / leave[c] v[r] (`_linear`).
    When the start cannot finish nothing else is a run's business: all zero and solved. `solved` is False when no solve reaches the residual.
    """
    visits = np.zeros(chain.m)
    if system is None:
        return visits, True, None
    nt, start = system.nt, int(system.position[0])
    found = inverse = None
    if nt <= DENSE_LIMIT:
        inverse = _inverse(system)
        if inverse is not None:
            e = np.zeros(nt)
            e[start] = 1.0
            found = inverse[start]
            if not (np.all(np.isfinite(found)) and _backward_error(nt, system.column, system.row, system.p, e, found) <= ACCEPT_RESIDUAL):
                found = inverse = None
    if found is None:
        keep = system.row != system.column
        r, c, w = system.row[keep], system.column[keep], system.p[keep]
        b = np.zeros(nt)
        b[start] = 1.0 / system.leave[start]
        found = _linear(nt, c, r, w / system.leave[c], b)
    if found is None or not np.all(np.isfinite(found)) or np.any(found < -1e-9):
        return visits, False, None
    visits[finishing] = np.maximum(found, 0.0)
    return visits, True, inverse


def _inverse(system: _System) -> np.ndarray | None:
    """N = (I - Q)^-1 over the states that can finish, dense, or None when it does not pass its check.

    Not formed as I - Q: a state that stays with chance 1 - 1e-13 has 1 - p = 1e-13 +- 1e-16 there, and an inverse of that is good to three digits (an entry
    chance off by 3e-4 in a test). Each row is divided by the chance to leave its state, which takes the self-loops out, and the inverse of
    I - P (P = Q / leave without the diagonal) is scaled back by columns: N = (I - P)^-1 diag(1 / leave). The whole inverse is checked, not
    only the row of the start that the visits are read from: every entry of (I - P) (I - P)^-1 - I must be within `ACCEPT_RESIDUAL` of the size of the terms it is made of.
    """
    nt = system.nt
    off = system.row != system.column
    row, column = system.row[off], system.column[off]
    with np.errstate(all="ignore"):
        matrix = np.eye(nt) - np.bincount(row * nt + column, weights=system.p[off] / system.leave[row], minlength=nt * nt).reshape(nt, nt)
        try:
            inverse = np.linalg.inv(matrix)
        except np.linalg.LinAlgError:
            return None
        scale = np.abs(matrix) @ np.abs(inverse) + np.eye(nt)
        if not (np.all(np.isfinite(inverse)) and np.max(np.abs(matrix @ inverse - np.eye(nt)) / scale) <= ACCEPT_RESIDUAL):
            return None
        return inverse / system.leave[None, :]


def _backward_error(n: int, own: np.ndarray, dep: np.ndarray, weight: np.ndarray, b: np.ndarray, x: np.ndarray) -> float:
    """The TRUE residual of `x` in `x[s] = b[s] + sum of weight[e] x[dep[e]]` (`own[e] = s`), measured against the size of the terms it is made of.

    `max over s of |b[s] - (x[s] - sum weight x[dep])| / (|x[s]| + sum |weight| |x[dep]| + |b[s]|)`: the componentwise backward error. Plain
    `|b - A x| / |b|` cannot get below the rounding of the terms when the answer is far larger than the right-hand side (a policy that restarts
    a million times), and then refuses a solve that is as good as floats allow; this number is the size of the change of the system
    that would make `x` exact, so it is small exactly for such a solve and about 1 for a wrong iterate.
    """
    with np.errstate(all="ignore"):
        terms = np.bincount(own, weights=weight * x[dep], minlength=n)
        scale = np.abs(x) + np.bincount(own, weights=np.abs(weight) * np.abs(x[dep]), minlength=n) + np.abs(b)
        error = np.abs(b - (x - terms)) / np.where(scale > 0, scale, 1.0)
    return float(np.max(error)) if len(error) else 0.0


def _linear(n: int, own: np.ndarray, dep: np.ndarray, weight: np.ndarray, b: np.ndarray) -> np.ndarray | None:
    """The `x` with `x[s] = b[s] + sum of weight[e] x[dep[e]]` over the edges `e` with `own[e] = s`, that is `(I - P) x = b`; None when no solve reaches `ACCEPT_RESIDUAL`.

    Dense up to `DENSE_LIMIT` states, else BiCGSTAB; a stiff system falls back to the dense solve for up to `DENSE_FALLBACK` states. Every
    answer is accepted on its TRUE residual (`_backward_error`, one more product), never on a number a method claims of itself.
    """
    with np.errstate(all="ignore"):
        if n > DENSE_LIMIT:

            def matvec(x: np.ndarray) -> np.ndarray:
                return x - np.bincount(own, weights=weight * x[dep], minlength=n)

            x, _, _ = bicgstab_checked(matvec, b, np.zeros(n), VISITS_TOLERANCE)
            error = _backward_error(n, own, dep, weight, b, x)
            if error <= DENSE_FALLBACK_RESIDUAL:
                return x
            if n > DENSE_FALLBACK:  # too big for the dense solve: the iterate is shown only if its true residual is good enough
                return x if error <= ACCEPT_RESIDUAL else None
        matrix = np.eye(n) - np.bincount(own * n + dep, weights=weight, minlength=n * n).reshape(n, n)
        bnorm = max(float(np.linalg.norm(b)), 1e-300)
        try:
            x = np.linalg.solve(matrix, b)
            for _ in range(2):  # iterative refinement: a stiff system loses digits in one solve
                correction = b - matrix @ x
                if not float(np.linalg.norm(correction)) > 4 * np.finfo(float).eps * bnorm:
                    break
                x = x + np.linalg.solve(matrix, correction)
        except np.linalg.LinAlgError:  # a chance per use so small that 1 - q is 1 in floats: nothing to say
            return None
        return x if _backward_error(n, own, dep, weight, b, x) <= ACCEPT_RESIDUAL else None


@dataclass(frozen=True)
class Reach:
    """The chance a run ever visits one state of a chain (ticket #554).

    `chance` is None when it is not measured, and `why` says in a line why: the visits could not be solved, the start cannot finish, the state
    is one from which no run can finish (a route that stops there), or the cycles of the chain could not be put back or did not agree with the
    visits. A chance that is given is a solution of its equations to a backward error of at most `ACCEPT_RESIDUAL`, checked against the visits
    by another method (ticket #572); no upper bound is shown for it. `error` is the relative error that guarantee supports, and no more: the
    residual is what is checked, and a stiff chain (a state a run is in for millions of steps) loses digits between a residual and an answer.
    """

    chance: float | None
    why: str | None = None
    error: float = 0.0


STIFF_ERROR = 1e-4  # a chance is printed to 4 significant digits (`percent`): an error the guarantee supports above this is said, not hidden


def precision_of(done: "_Solved") -> float:
    """The relative error of a chance or a visit count that the residual `ACCEPT_RESIDUAL` guarantees, estimated as that residual times the expected number of steps of a run.

    The condition number of I - Q is at least the expected steps of a run from the start (the sum of the visits), so a solve with a backward error of
    `ACCEPT_RESIDUAL` is guaranteed to that times it, no better. R04 and R14 are about 1e-6; a chain with chances per use of 1e-10 is 1.
    """
    return float(done.visits.sum()) * ACCEPT_RESIDUAL


def digits_text(error: float) -> str:
    """How many significant digits an `error` supports, for a reader."""
    return f"{max(0, int(-math.log10(error)) if error > 0 else 0)}"


def reach_of(chain: Chain, wanted: Sequence[int]) -> list[Reach]:
    """The chance a run ever visits each of the states `wanted` (indexes into `chain.states`), from the start: N[start, s] / N[s, s].

    The expected visits N[start, s] are the same solve the steps of the page use (`_solved`). The diagonal N[s, s] of every state comes from the cycles
    of the chain, whatever its size (`solver/_packed_chain.py`: components of the chain inverted whole, the rows that many states share cut and put
    back by the Woodbury identity), and is checked: the same pieces give the row of the start, which must agree with the visits to `AGREE`, else
    no chance is shown (`Reach.why`). The start is visited with chance 1.
    """
    m = chain.m
    if m == 0:
        return [Reach(None, "the chain has no state") for _ in wanted]
    from . import _packed  # a measuring script sets `_packed.PROGRESS`; the library never does

    began = time.perf_counter()
    say = _packed.PROGRESS or (lambda _text: None)
    done = _solved(chain)
    say(f"visit chances: the visits of {int(done.finishing.sum()):,} states that can finish solved ({time.perf_counter() - began:.1f} s)")
    src = np.repeat(np.arange(m), np.diff(chain.ptr))
    found: dict[int, Reach] = {}
    asked = [i for i in dict.fromkeys(wanted) if i != 0 and done.solved and done.finishing[0] and done.finishing[i]]
    diagonal, why = _diagonal(chain, src, done, say) if asked else (None, None)
    position = np.cumsum(done.finishing) - 1
    error = precision_of(done) if asked else 0.0
    for i in dict.fromkeys(wanted):
        if i == 0:
            found[i] = Reach(1.0)
        elif not done.solved:
            found[i] = Reach(None, f"the visits of the chain were not solved to a residual of {ACCEPT_RESIDUAL:g}")
        elif not done.finishing[0]:
            found[i] = Reach(None, "no run can finish from the start of the chain")
        elif not done.finishing[i]:
            found[i] = Reach(None, "no run can finish from this state (the route stops there)")
        elif diagonal is None:
            found[i] = Reach(None, why)
        else:
            found[i] = Reach(min(1.0, max(0.0, float(done.visits[i] / diagonal[position[i]]))), None, error)
    say(f"visit chances: {len(found):,} states done ({time.perf_counter() - began:.1f} s)")
    return [found[i] for i in wanted]


def _diagonal(chain: Chain, src: np.ndarray, done: _Solved, say) -> tuple[np.ndarray | None, str | None]:
    """`(N[s, s] of every state that can finish (by position), None)`, or `(None, the reason)` when the cycles cannot be put back or the pieces do not agree with the visits.

    The chain is Q on the states that can finish, self-loops included, with `leave` the chance to leave each state (`_system`); the cycles of the
    chain give the diagonal of N = (I - Q)^-1 (`solver/_packed_chain.py`) and, from the same pieces, the row of the start, which must be the visits.
    """
    system = _system(chain, src, done.finishing)
    assert system is not None
    ptr = np.searchsorted(system.row, np.arange(system.nt + 1))  # the edges are in the order of their states, which the positions keep
    start = int(system.position[0])
    visits = done.visits[done.finishing]
    with np.errstate(all="ignore"):
        try:
            diagonal, deviation = inverse_diagonal(
                system.nt, ptr, system.column, system.p, system.leave, start=start, start_row=visits, progress=say, leak=system.leak
            )
        except CyclesTooTangled as error:  # not measured, never a guess: the benchmark line shows `?` and says why
            why = f"the cycles of the chain are too tangled to put back within the memory of a run ({error})"
        except MemoryError:
            why = "the memory of the run ran out putting back the cycles of the chain"
        except np.linalg.LinAlgError:
            why = "a block of cycles of the chain is singular in floats"
        else:
            if deviation <= AGREE and np.all(np.isfinite(diagonal)) and np.all(diagonal >= 1.0 - 1e-9):
                return diagonal, None
            why = f"the cycles of the chain and the visits disagree by {deviation:.3g} (more than {AGREE:g})"
    say(f"visit chances: not measured ({why})")
    return None, why


def _entry_chance(system: _System, absorbing: np.ndarray) -> float | None:
    """The chance a run from the start ever reaches a state of `absorbing` (a mask over the positions; the start is not in it); None when the solve did not settle.

    h(s) is that chance from s, the states of `absorbing` made to stop the run: h(s) = sum over u in `absorbing` of p(s, u) / leave(s) + sum over the
    other states t of p(s, t) / leave(s) h(t), each self-loop divided out as in `_visits`.
    """
    free = ~absorbing
    index = np.cumsum(free) - 1
    row, column = system.row, system.column
    edge = (row != column) & free[row]
    inner = edge & free[column]
    entering = edge & absorbing[column]
    b = np.bincount(index[row[entering]], weights=system.p[entering] / system.leave[row[entering]], minlength=int(free.sum()))
    h = _linear(int(free.sum()), index[row[inner]], index[column[inner]], system.p[inner] / system.leave[row[inner]], b)
    if h is None:
        return None
    return min(1.0, max(0.0, float(h[index[system.position[0]]])))


def _entered(chain, step, nsteps, src, finishing, visits, system, inverse) -> tuple[list[float | None], int]:
    """`(chance, unsettled)`: the chance a run ever enters each step (1 for the first), and how many steps had a solve that did not settle.

    For a step A of states that can finish, the first state of A a run meets is a with chance H(a), and the visits of N split by it:
    N[start, b] = sum over a in A of H(a) N[a, b], so H = N[start, A] N[A, A]^-1 and the chance is its sum, when N is at hand (`inverse`, up to
    `DENSE_LIMIT` states). Otherwise `_entry_chance` solves for the chance of reaching A with its states made absorbing, one solve for each
    step. A step of states that cannot finish (a dead end, a gap) is entered from the states that can: its chance is the expected number of
    such steps into it, since a run never comes back from it. A step that has both kinds of state is left unmeasured (None).
    """
    result: list[float | None] = [None] * nsteps
    result[0] = 1.0
    unsettled = 0
    m = chain.m
    for s in range(1, nsteps):
        members = np.flatnonzero(step == s)
        live = finishing[members]
        if 0 in members:
            result[s] = 1.0
        elif live.all():
            inside = system.position[members]
            if inverse is not None:
                with np.errstate(all="ignore"):
                    try:
                        first = np.linalg.solve(inverse[np.ix_(inside, inside)].T, inverse[system.position[0], inside])
                    except np.linalg.LinAlgError:
                        first = np.array([math.nan])
                value = float(first.sum())
                value = min(1.0, max(0.0, value)) if math.isfinite(value) else None
            else:
                absorbing = np.zeros(system.nt, dtype=bool)
                absorbing[inside] = True
                value = _entry_chance(system, absorbing)
            if value is None:
                unsettled += 1
            else:
                result[s] = value
        elif not live.any():
            into = np.zeros(m, dtype=bool)
            into[members] = True
            edge = (chain.dst < m) & into[np.minimum(chain.dst, m - 1)] & finishing[src]
            result[s] = min(1.0, max(0.0, float(np.sum(visits[src[edge]] * chain.prob[edge]))))
    return result, unsettled
