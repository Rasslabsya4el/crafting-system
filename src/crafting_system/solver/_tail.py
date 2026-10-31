"""The tail cut: expand exactly only where a coarse policy goes, and bound the rest by the blocks (ADR-0023, ticket #129).

A coarse solve (`solve_bounds` on the optimistic and pessimistic models of a coarse state) gives, for every
block `B`, a certified lower bound `L(B) <= V*(s)` and a certified upper bound `U(B) >= J(pi)(s)` for every
member `s`, where `pi` is the coarse policy, an ordinary policy of the exact problem. The tail cut follows `pi`
from the start in the exact model and **expands** every state it enters with an expected count above `theta`
(all the actions of the exact model are kept there). A successor that is not expanded is a **leaf**: its value
is `L(block)` in the optimistic tail model and `U(block)` in the pessimistic one (a leaf is one action to the
goal that costs that bound). Both are then solved by `solve_bounds`:

* optimistic: `L(block)` is below the optimum of the leaf, so the least fixed point of the tail model is below
  the optimum;
* pessimistic: let `G(s) = U(block(s))`. `G` is above the one-step backup of `pi` in every state (that is what
  the coarse upper bound says), so it is above the pessimistic tail operator on the expanded states and equals the
  leaf value on the leaves; hence the tail value `W` is at most `G` on the expanded states. The policy `mu` that
  plays the tail action in an expanded state and `pi` in every other state has the cost `J(mu)` at most `Z`, with
  `Z = W` on the expanded states and `Z = G` elsewhere: for an expanded state `Z` is its tail backup, and for any
  other state `G` is above the backup of `pi` taken over `G`, which is above the backup taken over `Z <= G`. A
  supersolution of the policy's own backup bounds its cost, so `V* <= J(mu) <= W`.

Both bounds are at least as tight as the coarse ones, and they tighten as the expanded set grows, because a block
bound is a sub- or supersolution of the exact backup. With no state expanded (`theta` of 1 or more, or `math.inf`)
the bounds are the coarse ones.

A state is expanded when the expected number of times `pi` **enters** it from another state is above `theta`
(the start counts as one entry; the repeats of a self-loop are folded into the state's own successors and are not
counted as entries, because an unexpanded state's loop is unknown). The entries are found by pushing probability
mass along `pi` through the expanded states only, so they are a lower bound of the true entries, and any
expanded set gives valid bounds: `theta` only decides how tight they are and how much is solved. With `theta = 0`
every state `pi` can reach is expanded.

The three models must agree: an action of the coarse policy is offered in the exact model under the same label (one
action to a label in a state) in every member of its block, and a coarse kernel is the exact kernel pushed through
`block_of`. This module checks the label in each expanded state and leaves the kernels to the builder of the models
(the tests compare them with a brute force); the pessimistic coarse model may charge a member more than the exact
model does. Nothing here knows the game: states are any hashable objects.
"""

import math
from collections import defaultdict, deque
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass

from ._bounds import Bounds, _gap, solve_bounds
from ._model import Action, Model, Outcome

LEAF = "tail-cut leaf"  # the label of the one action of a leaf state
PUSH_FLOOR = 1e-3  # mass below this fraction of `theta` waiting in an expanded state is not pushed on


@dataclass(frozen=True, slots=True)
class _Leaf:
    """A state that is cut: valued by the bound of its block."""

    state: Hashable


class _Sink:
    """The goal that every leaf action ends in."""

    __slots__ = ()


SINK = _Sink()


@dataclass(frozen=True, slots=True)
class TailCut[S, B]:
    """What `solve_tail_cut` returns.

    `bounds` is a `Bounds` over the expanded states and the goals the expanded states reach: `lower[s]` and
    `upper[s]` are certified bounds on the optimum of `s`, and `upper` also on the cost of the policy, which
    is `bounds.policy` on the expanded states and `coarse.policy` on every other state (a leaf, or a state
    outside the expanded set). The start is in it; with nothing expanded it holds the coarse bounds of the
    start's block and an empty policy. `expanded` is the set of states expanded, `leaves` the number of
    distinct cut states the expanded ones reach, `coarse` the coarse bounds the leaves are valued by.
    """

    bounds: Bounds[S]
    expanded: frozenset[S]
    leaves: int
    theta: float
    coarse: Bounds[B]


def solve_tail_cut[S, B](
    exact: Model[S],
    optimistic: Model[B],
    pessimistic: Model[B],
    block_of: Callable[[S], B],
    start: S,
    theta: float,
    *,
    tolerance: float = 1e-10,
    direct_solve_limit: int = 64,
    max_sweeps: int = 100_000,
) -> TailCut[S, B]:
    """Bound the optimum of `start` by expanding the states the coarse policy enters with count above `theta`.

    `optimistic` and `pessimistic` are the two coarse models (their states are the blocks `block_of` maps the
    exact states to). They are solved from the block of the start; a cut state whose block that solve did not
    reach (the pessimistic model offers fewer actions than the exact one, so an action it does not offer can lead
    there) is added as a start and both are solved again, which leaves the earlier numbers as they were or
    tighter. `theta = math.inf` expands nothing. Raises `ValueError` for a `theta` below 0 or NaN, a start whose
    block has no finite upper bound (no policy to follow), and a coarse policy action that the exact model does
    not offer in an expanded state.
    """
    if isinstance(theta, bool) or not (theta >= 0.0):  # also catches NaN
        raise ValueError(f"theta must be at least 0, got {theta!r}")
    options = {"tolerance": tolerance, "direct_solve_limit": direct_solve_limit, "max_sweeps": max_sweeps}
    start_block = block_of(start)
    coarse = solve_bounds(optimistic, pessimistic, [start_block], **options)
    if coarse.upper[start_block] == math.inf:
        raise ValueError(f"the coarse models have no proper policy from the start (block {start_block!r}): nothing to follow")

    offered: dict[S, tuple[Action[S], ...]] = {}  # the exact actions of every expanded state
    _expand(exact, coarse, block_of, start, theta, offered)
    if not offered:
        low, high = coarse.lower[start_block], coarse.upper[start_block]
        bounds = Bounds({start: low}, {start: high}, {}, _gap(low, high), coarse.optimistic_error, coarse.pessimistic_error)
        return TailCut(bounds, frozenset(), 0, theta, coarse)

    reached = dict.fromkeys(  # the blocks of the cut states, in the order they are met
        block_of(outcome.state)
        for actions in offered.values()
        for action in actions
        for outcome in action.outcomes
        if outcome.weight > 0 and outcome.state not in offered and not exact.is_goal(outcome.state)
    )
    missing = [block for block in reached if block not in coarse.lower or block not in coarse.upper]
    if missing:
        coarse = solve_bounds(optimistic, pessimistic, [start_block, *missing], **options)

    leaves: set[S] = set()

    def cut(action: Action[S]) -> Action[Hashable]:
        outcomes = []
        for outcome in action.outcomes:
            if outcome.weight == 0:
                continue
            target = outcome.state
            if target not in offered and not exact.is_goal(target):
                leaves.add(target)
                target = _Leaf(target)
            outcomes.append(Outcome(target, outcome.weight))
        return Action(action.label, action.cost, tuple(outcomes), action.extra_inputs)

    tail = {state: tuple(cut(action) for action in actions) for state, actions in offered.items()}
    below = _TailModel(exact, tail, lambda state: _leaf_cost(coarse.lower, block_of, state, tiny=True))
    above = _TailModel(exact, tail, lambda state: _leaf_cost(coarse.upper, block_of, state, tiny=False))
    found = solve_bounds(below, above, [start], **options)
    policy = {
        state: Action(
            action.label,
            action.cost,
            tuple(Outcome(o.state.state if isinstance(o.state, _Leaf) else o.state, o.weight) for o in action.outcomes),
            action.extra_inputs,
        )
        for state, action in found.policy.items()
        if _is_exact(state)
    }
    bounds = Bounds(
        {state: value for state, value in found.lower.items() if _is_exact(state)},
        {state: value for state, value in found.upper.items() if _is_exact(state)},
        policy,
        found.gap,
        found.optimistic_error,
        found.pessimistic_error,
    )
    return TailCut(bounds, frozenset(offered), len(leaves), theta, coarse)


def _is_exact(state: Hashable) -> bool:
    return not isinstance(state, (_Leaf, _Sink))


def _leaf_cost[S, B](values: Mapping[B, float], block_of: Callable[[S], B], state: S, *, tiny: bool) -> float | None:
    """The cost of a leaf's one action: the bound of its block; None when the block has no finite value."""
    block = block_of(state)
    if block not in values:
        raise ValueError(f"the coarse bounds do not cover the block {block!r} of a cut state {state!r}")
    value = values[block]
    if value == math.inf:
        return None
    if value <= 0.0:  # an action costs more than zero: a lower bound of zero stays a lower bound at the smallest cost
        if not tiny:
            raise ValueError(f"a non-goal block {block!r} has the upper bound {value!r}")
        return math.nextafter(0.0, 1.0)
    return value


class _TailModel:
    """The expanded states with all their exact actions, and every other state a leaf worth its block bound."""

    def __init__(self, exact: Model, tail: Mapping, leaf_cost: Callable) -> None:
        self._exact, self._tail, self._leaf_cost = exact, tail, leaf_cost

    def is_goal(self, state) -> bool:
        if isinstance(state, _Sink):
            return True
        return not isinstance(state, _Leaf) and self._exact.is_goal(state)

    def actions(self, state) -> tuple[Action, ...]:
        if isinstance(state, _Leaf):
            cost = self._leaf_cost(state.state)
            return () if cost is None else (Action(LEAF, cost, ((SINK, 1),)),)
        return self._tail[state]


def _expand[S, B](
    exact: Model[S], coarse: Bounds[B], block_of: Callable[[S], B], start: S, theta: float, offered: dict[S, tuple[Action[S], ...]]
) -> None:
    """Fill `offered` with the exact actions of every state the coarse policy enters often enough.

    `theta = 0` expands the states the policy can reach (a breadth-first closure). Otherwise mass is pushed along
    the policy: the mass that has entered a state, with the loops folded in, goes on to its successors, and a
    state is expanded as soon as the mass that entered it is above `theta`.
    """
    followed: dict[S, tuple[tuple[S, float], ...]] = {}  # successor and chance of the policy action, self-loop folded out
    entered: defaultdict[S, float] = defaultdict(float)
    waiting: defaultdict[S, float] = defaultdict(float)
    queue: deque[S] = deque()
    queued: set[S] = set()
    floor = max(theta * PUSH_FLOOR, 1e-300)  # a subnormal theta must not make the floor 0

    def arrive(state: S, mass: float) -> None:
        if exact.is_goal(state):
            return
        entered[state] += mass
        if state not in offered:
            if not entered[state] > theta and theta > 0.0:
                return
            followed[state] = _policy_step(exact, coarse, block_of, state, offered)
            waiting[state] = entered[state]
        else:
            waiting[state] += mass
        if (waiting[state] > floor or theta == 0.0) and state not in queued:
            queued.add(state)
            queue.append(state)

    if theta == math.inf:
        return
    arrive(start, 1.0)
    while queue:
        state = queue.popleft()
        queued.discard(state)
        mass, waiting[state] = waiting[state], 0.0
        if theta == 0.0:
            mass = 1.0
        for successor, chance in followed[state]:
            if theta == 0.0 and (successor in offered or exact.is_goal(successor)):
                continue
            arrive(successor, mass * chance)


def _policy_step[S, B](
    exact: Model[S], coarse: Bounds[B], block_of: Callable[[S], B], state: S, offered: dict[S, tuple[Action[S], ...]]
) -> tuple[tuple[S, float], ...]:
    """Record the exact actions of `state` and return the successors of the coarse policy's action, the self-loop folded in.

    The chance of a successor is its chance divided by one minus the chance of staying, so that the mass
    entering the state is carried on in one step; the state itself is not listed.
    """
    block = block_of(state)
    if block not in coarse.policy:
        raise ValueError(f"the coarse policy has no action in the block {block!r} of the expanded state {state!r}")
    wanted = coarse.policy[block]
    actions = tuple(exact.actions(state))
    offered[state] = actions
    matching = [action for action in actions if action.label == wanted.label]
    if not matching:
        raise ValueError(f"the coarse policy takes {wanted.label!r} in the block {block!r} but the exact model does not offer it in {state!r}")
    if len(matching) > 1:
        raise ValueError(f"the exact model offers {len(matching)} actions labelled {wanted.label!r} in {state!r}: a label must name one action")
    chosen = matching[0]
    chances: defaultdict[S, int] = defaultdict(int)
    for outcome in chosen.outcomes:
        chances[outcome.state] += outcome.weight
    total = sum(chances.values())
    stay = chances.pop(state, 0)
    if stay >= total:
        raise ValueError(f"the coarse policy never leaves the expanded state {state!r}")
    return tuple((successor, weight / (total - stay)) for successor, weight in chances.items() if weight > 0)
