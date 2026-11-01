"""The Peek kind: look, then choose (ADR-0054, ADR-0010 amendment; ticket #293).

A `Peek` (see `_model.Peek`) throws the dice of all its options at once and lets the player take the best result or
give the Peek up. Its backup at a state `s` is

    V(s) = min( best plain action, L + E[ min( min_a ( c_a + V(o_a) ), F(s) ) ] ),

with the `o_a` drawn independently from the options' kernels and `F(s)` the value of the best fallback action.

How it is solved, and the seam. The Peek is a minimum, over every reaction (a function from the thrown previews to a
choice), of an affine backup, so it is an ordinary stochastic shortest path once a reaction is fixed, and the solver
below is not touched. `solve_peek` runs **policy iteration on the reaction around the unchanged `solve`**:

1. *Lock-free solve.* The model with every Peek dropped is solved by `solve`. Its policy is proper, which is where the
   iteration starts, and its values `V0` are an upper bound of the answer. The Peeks' option and fallback states are
   added to the starts until the solve covers them all (a state the Lock-free walk never built still needs a value).
2. *Reaction from the values.* At each Peek state the sorted-tail sweep (`peek_backup`) ranks every (option, result)
   pair by `c_a + V(o)` (ties by state id, then option order: a strict total order) and the **acceptance set** is the
   ranked list of the pairs below `F(s)`, the value of giving up.
3. *Expansion.* Under a fixed acceptance set the Peek is replaced, in the policy graph only, by ordinary actions
   (`ExpandedModel`): the Lock leads to `m` "apply a" pseudo-states with the exact chance that option `a` holds the
   best accepted pair, and to "give up" with the chance that no pair is accepted; "apply a" pays `c_a` and leads to
   each result with the chance that `a` wins with it; "give up" holds the fallback actions. `solve` runs on that.
4. Repeat from step 2 with the new values until the acceptance sets stop changing. Each round can only lower the values
   (the reaction is greedy for the last values), and a fixed point is a solution of the Bellman equation of the Peek.

The weights are exact integers (denominators multiply, a few big integers per Peek state) and the values float64,
converted once. A reaction that never accepts is a probability-1 cycle through the give-up branch: the expanded model
has no proper policy through it and `solve` reports it as such (it never loops). The certificate (`error_bound`) is
`solve`'s own on the last expanded model: under a fixed reaction the operator is affine with a positive constant term,
which is all that `_certify` uses.

`solve_peek` asks the model for its actions again in every round (the model must answer the same each time); a
model with no `Peek` is solved by one plain `solve` and the answer is the same bit for bit.
"""

import math
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from ._certify import ConvergenceError
from ._model import Action, Model, Outcome, Peek
from ._solve import Solution, solve

Reaction = tuple[tuple[int, Hashable], ...]
"""An acceptance set: the (option index, result state) pairs taken, best first (a strict ranking)."""

APPLY = "apply"
GIVE_UP = "give up"
_STALL = 1e-12  # relative drop below which a changed reaction is a tie, not progress


@dataclass(frozen=True, slots=True)
class PeekNode[S]:
    """A pseudo-state of the policy graph under a fixed acceptance set.

    `kind` is `APPLY` (`option` is the index of the option being applied) or `GIVE_UP` (`option` is -1).
    `state` is the state whose Peek it belongs to. Nodes appear in `values` and `policy` of a `PeekSolution` and
    nowhere else; `risk` and the simulator read them as ordinary states.
    """

    state: S
    kind: str
    option: int = -1


@dataclass(frozen=True, slots=True)
class PeekSolution[S](Solution[S]):
    """`Solution` of a model with Peeks.

    `values` and `policy` also hold the `PeekNode`s of the final expansion. `reactions` maps each state that offers a
    Peek to the acceptance set the policy plays there (the same set can be expanded again under another reading of
    the kernels with `ExpandedModel`). `rounds` is the number of expanded solves (0: the model has no Peek).
    """

    reactions: Mapping[S, Reaction]
    rounds: int


class _Merged(NamedTuple):
    """One option's kernel with repeated successors merged and zero weights dropped."""

    outcomes: tuple[tuple[Hashable, int], ...]
    total: int


def _merge(action: Action) -> _Merged:
    merged: dict[Hashable, int] = {}
    for state, weight in action.outcomes:
        if weight:
            merged[state] = merged.get(state, 0) + weight
    return _Merged(tuple(merged.items()), sum(merged.values()))


def peek_backup(options: Sequence[Sequence[tuple[float, int]]], limit: float = math.inf) -> float:
    """`E[min(X_1, ..., X_m, limit)]` for independent `X_a`, each given as `(value, integer weight)` pairs.

    The sorted-tail sweep: the integral from 0 to `limit` of the product of the tails `P(X_a > t)`. The weights stay
    integers (the probability that the minimum is `v` is a difference of integer products over the product of the
    totals) and each value is converted to float64 once. Values are positive. `limit` is the value of giving up
    (`inf`: the player must take a result). The answer is `inf` when a positive chance is left on values at or above
    an infinite `limit`.
    """
    remaining = [sum(weight for _, weight in option) for option in options]
    denominator = math.prod(remaining)
    events = sorted(
        ((value, a, weight) for a, option in enumerate(options) for value, weight in option if weight and value < limit),
        key=lambda event: event[0],
    )
    product, terms, i = denominator, [], 0
    while i < len(events):
        value = events[i][0]
        while i < len(events) and events[i][0] == value:
            remaining[events[i][1]] -= events[i][2]
            i += 1
        after = math.prod(remaining)
        terms.append(value * ((product - after) / denominator))
        product = after
    if product:
        if limit == math.inf:
            return math.inf
        terms.append(limit * (product / denominator))
    return math.fsum(terms)


def action_value(action: Action, values: Mapping[Hashable, float]) -> float:
    """`cost + E[V(next)] + V(inputs)` of one action under the values `values` (a missing state is infinite)."""
    total = sum(weight for _, weight in action.outcomes)
    terms = [action.cost]
    for state, weight in action.outcomes:
        if weight:
            terms.append(values.get(state, math.inf) * (weight / total))
    for state in action.extra_inputs:
        terms.append(values.get(state, math.inf))
    return math.fsum(terms)


def fallback_value(peek: Peek, values: Mapping[Hashable, float]) -> float:
    """`F`: the value of the best fallback action (`inf` when there is none)."""
    return min((action_value(action, values) for action in peek.fallback), default=math.inf)


def choose_reaction(
    peek: Peek, values: Mapping[Hashable, float], ids: dict[Hashable, int]
) -> Reaction:
    """The acceptance set that is greedy for `values`: every (option, result) pair below the fallback, ranked.

    The rank is `(c_a + V(o), id of o, option index)`, a strict total order; `ids` numbers the states in the order
    they are first ranked. When giving up is impossible (`F` infinite) the pairs of finite value are taken, and if
    there are none every pair is (nothing is lost, and the Peek is not stuck on a value that is still unknown).
    """
    limit = fallback_value(peek, values)
    pairs = []
    for a, option in enumerate(peek.options):
        for state, _ in _merge(option).outcomes:
            value = option.cost + values.get(state, math.inf)
            pairs.append((value, ids.setdefault(state, len(ids)), a, state))
    pairs.sort(key=lambda pair: pair[:3])
    if limit == math.inf:
        taken = [pair for pair in pairs if pair[0] < math.inf] or pairs
    else:
        taken = [pair for pair in pairs if pair[0] < limit]
    return tuple((pair[2], pair[3]) for pair in taken)


def lock_expansion(
    state: Hashable, peek: Peek, reaction: Reaction
) -> tuple[Action, dict[PeekNode, tuple[Action, ...]]]:
    """The ordinary actions that replace `peek` at `state` under `reaction`: the Lock action and the nodes' actions.

    With `m` options the nodes are the `m` "apply a" nodes that can be reached and "give up" (at most `m + 1`).
    The chance that pair `(a, o)` is the best accepted one is `p_a(o)` times, for every other option `b`, the chance
    that `b` throws no accepted pair ranked above it; in integers over the product of the options' totals.
    """
    merged = [_merge(option) for option in peek.options]
    totals = [kernel.total for kernel in merged]
    weight_of = [dict(kernel.outcomes) for kernel in merged]
    denominator = math.prod(totals)
    seen = [0] * len(merged)  # weight of the accepted pairs of each option that rank above the pair in hand
    wins: list[list[tuple[Hashable, int]]] = [[] for _ in merged]
    taken: set[tuple[int, Hashable]] = set()
    for a, result in reaction:
        if not 0 <= a < len(merged) or result not in weight_of[a]:
            raise ValueError(f"the acceptance set of state {state!r} holds {(a, result)!r}, which is no outcome of an option")
        if (a, result) in taken:
            raise ValueError(f"the acceptance set of state {state!r} holds {(a, result)!r} twice")
        taken.add((a, result))
        weight = weight_of[a][result]
        chance = weight
        for b, (total, got) in enumerate(zip(totals, seen)):
            if b != a:
                chance *= total - got
        wins[a].append((result, chance))
        seen[a] += weight
    nodes: dict[PeekNode, tuple[Action, ...]] = {}
    outcomes: list[Outcome] = []
    applied = 0
    for a, results in enumerate(wins):
        if results:
            node = PeekNode(state, APPLY, a)
            option = peek.options[a]
            nodes[node] = (Action(option.label, option.cost, tuple(Outcome(r, w) for r, w in results)),)
            weight = sum(w for _, w in results)
            applied += weight
            outcomes.append(Outcome(node, weight))
    if applied < denominator:
        node = PeekNode(state, GIVE_UP)
        nodes[node] = peek.fallback
        outcomes.append(Outcome(node, denominator - applied))
    return Action(peek.label, peek.cost, tuple(outcomes)), nodes


def _split(state: Hashable, actions: Iterable) -> tuple[tuple, Peek | None]:
    plain, found = [], None
    for action in actions:
        if isinstance(action, Peek):
            if found is not None:
                raise ValueError(f"state {state!r} offers more than one peek")
            found = action
        else:
            plain.append(action)
    return tuple(plain), found


class _View:
    """What the two views of a model with Peeks share: goals, the node test and the pool hook."""

    def __init__(self, base: Model) -> None:
        self._base = base
        prefetch = getattr(base, "prefetch", None)
        if prefetch is not None:  # the base model's states only; pseudo-states have nothing to prime
            self.prefetch = lambda states: prefetch([s for s in states if not isinstance(s, PeekNode)])

    def is_goal(self, state: Hashable) -> bool:
        return False if isinstance(state, PeekNode) else self._base.is_goal(state)


class LockFree(_View):
    """The model with every Peek dropped; the Peeks met are kept in `peeks`, by state, in the order they were met."""

    def __init__(self, base: Model) -> None:
        super().__init__(base)
        self.peeks: dict[Hashable, Peek] = {}

    def actions(self, state: Hashable) -> tuple:
        plain, found = _split(state, self._base.actions(state))
        if found is not None:
            self.peeks[state] = found
        return plain

    def referenced(self) -> list[Hashable]:
        """The states the Peeks met can lead to (option results, fallback results and inputs), first met first."""
        found: dict[Hashable, None] = {}
        for peek in self.peeks.values():
            for action in (*peek.options, *peek.fallback):
                for state, weight in action.outcomes:
                    if weight:
                        found[state] = None
                found.update(dict.fromkeys(action.extra_inputs))
        return list(found)


class ExpandedModel(_View):
    """The model with each Peek replaced by ordinary actions under a fixed acceptance set (ADR-0054).

    `reactions` gives the acceptance set of every state that offers a Peek (a missing one is an error). The states
    of the base model are kept; the pseudo-states are `PeekNode`s. Use it to solve a given reaction with `solve`,
    or to read the same reaction under another reading of the kernels (`risk`, the simulator).
    """

    def __init__(self, base: Model, reactions: Mapping[Hashable, Reaction]) -> None:
        super().__init__(base)
        self._reactions = reactions
        self._pending: dict[PeekNode, tuple[Action, ...]] = {}

    def actions(self, state: Hashable) -> tuple:
        if isinstance(state, PeekNode):
            found = self._pending.pop(state, None)
            if found is None:  # asked before its state was expanded
                found = self._expand(state.state)[1][state]
            return found
        plain, peek = _split(state, self._base.actions(state))
        if peek is None:
            return plain
        lock, nodes = self._expand(state, peek)
        self._pending.update(nodes)
        return (*plain, lock)

    def _expand(self, state: Hashable, peek: Peek | None = None):
        if peek is None:
            peek = _split(state, self._base.actions(state))[1]
        try:
            reaction = self._reactions[state]
        except KeyError:
            raise ValueError(f"no acceptance set for state {state!r}, which offers a peek") from None
        return lock_expansion(state, peek, reaction)


def solve_peek[S](
    model: Model[S],
    starts: Iterable[S],
    *,
    tolerance: float = 1e-10,
    direct_solve_limit: int = 64,
    max_sweeps: int = 100_000,
    value_ceiling: float = 1e12,
    max_rounds: int = 100,
) -> PeekSolution[S]:
    """`solve` for a model whose states may offer a `Peek`: the minimum mean cost to a goal, reactions included.

    The options are as in `solve`. `max_rounds` bounds the policy iteration on the reactions; `ConvergenceError`
    is raised when it does not settle. A model that offers no `Peek` is solved by one `solve` of its own, and the
    answer is the same bit for bit (`rounds == 0`).

    The model's `actions` is asked again in every round, and must give equal answers. See the module text for the method.
    """
    options = dict(
        tolerance=tolerance, direct_solve_limit=direct_solve_limit, max_sweeps=max_sweeps, value_ceiling=value_ceiling
    )
    roots = list(starts)
    free = LockFree(model)
    first = solve(free, roots, **options)
    if not free.peeks:
        return PeekSolution(first.values, first.policy, first.error_bound, {}, 0)
    while True:  # cover the states the Peeks can lead to, which the Lock-free walk may never have built
        missing = [state for state in free.referenced() if state not in first.values]
        if not missing:
            break
        roots += missing
        first = solve(free, roots, **options)
    values, ids = first.values, {}
    peeks = dict(free.peeks)
    reactions = {state: choose_reaction(peek, values, ids) for state, peek in peeks.items()}
    for rounds in range(1, max_rounds + 1):
        current = solve(ExpandedModel(model, reactions), roots, **options)
        better = {state: choose_reaction(peek, current.values, ids) for state, peek in peeks.items()}
        if better == reactions or not _progress(values, current.values):
            return PeekSolution(current.values, current.policy, current.error_bound, reactions, rounds)
        values, reactions = current.values, better
    raise ConvergenceError(f"the reactions did not settle within {max_rounds} rounds", current.error_bound)


def _progress(before: Mapping[Hashable, float], after: Mapping[Hashable, float]) -> bool:
    """Whether the new values are lower than the old ones by more than a tie (a state may turn from infinite to finite)."""
    for state, old in before.items():
        new = after.get(state, old)
        if new < old and (old == math.inf or old - new > _STALL * old):
            return True
    return False
