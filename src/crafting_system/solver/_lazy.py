"""Lazy donor generation: the lazy offer loop of ADR-0062, on top of `Acquisition` and `solve`.

The caller gives the full model `M`: for every base state its actions, among them the **candidates**, the actions that
consume other items (`Action.extra_inputs`, each a `Need`). `solve_lazily` does not offer them all. It solves the product
(`Acquisition`) with the candidates offered so far, then tests every candidate it left out against a lower bound and
offers the ones that fail, until none does; the last solve is the value of `M`, with the candidates left out proved
unneeded. Plain actions (no extra input) are always offered, and `solve` itself is not touched.

Why it is exact (ADR-0062, "Why the loop is exact"). Let `V_k` be the value of the product with the offers so far and
`T` the Bellman operator of `M`. Put `L = V_k` on the product states that were solved with a finite value and `L = D`, the
**determinized distance**, elsewhere: the cheapest path of action costs to a state that reaches the want, over every
possible successor of every action of `M`, the inputs free. `D` is below every value, because an action costs at least its
own cost and a successor is worth at least its `D`, whatever it needs. If `L <= T L` at every state then `L <= V*`, since
`T` is monotone and `T^n L <= T_mu^n L` for the optimal policy, whose iterates tend to `V*`; and `V* <= V_k`, because a policy
of the product with fewer offers is a policy of `M`. The inequality holds at the offered actions (`V_k` is their fixed point)
and at an action left out exactly when `cost + sum V(input) + sum p(j) L(j) >= V_k(state)`, which is the test below. Where
a state has no finite value in hand nothing can be pruned, so every candidate there is offered, except where `D` itself is
infinite (no sequence of actions reaches the want from there, so nothing helps and `M` is infinite too).

What is returned is exact to two things: the certified `error_bound` of `solve` on the last round, and the **slack** of the
test, a relative `slack` (default 1e-9): a candidate that would lower a value by less than that is not offered. The sum is
`LazySolution.error_bound`.

The seam (ticket #312, exact merging and an envelope search): the loop touches the model in two places only, `_Space`
(the base states, their candidates and the lower bounds `D`) and `_check` (which candidates fail the test given the values
of one solve). Both read the values of a finished solve and nothing else, so a flat solver or a search that expands states
on demand replaces `_check` and the solve and keeps the rest. The loop never merges states.
"""

import heapq
import math
import operator
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from numbers import Real

from ._acquire import MAIN, Acquisition, Need
from ._model import Action, Model
from ._solve import Solution, solve


@dataclass(frozen=True, slots=True)
class Round:
    """What one round of the loop saw: the size of its solve, what it offered so far and what the test added."""

    product_states: int
    wants: int  # acquisition processes in the solve, the main target included
    offered: int  # (state, candidate) pairs offered in this round's solve
    added: int  # pairs the test added after it (0 in the last round)


@dataclass(frozen=True, slots=True)
class LazySolution[S]:
    """What `solve_lazily` returns.

    `solution` is the last solve, over the product states of `acquisition` (`start` is the main target's); `offered` maps a
    base state to the keys `(label, extra_inputs)` of the candidates offered there (a state with none is missing);
    `pairs` is the number of (state, candidate) pairs of `M`, so `pairs - offered pairs` were proved unneeded; `rounds` has
    one entry per solve. `error_bound` is the certified relative bound of `solve` plus `slack`; see the module docstring.
    """

    solution: Solution[tuple]
    acquisition: Acquisition[S]
    start: tuple
    offered: Mapping[S, frozenset[Hashable]]
    pairs: int
    rounds: tuple[Round, ...]
    slack: float

    @property
    def values(self) -> Mapping[tuple, float]:
        return self.solution.values

    @property
    def value(self) -> float:
        """The expected cost of the main target from the start state."""
        return self.solution.values[self.start]

    @property
    def error_bound(self) -> float:
        return self.solution.error_bound + self.slack

    @property
    def offered_pairs(self) -> int:
        return sum(len(keys) for keys in self.offered.values())


def solve_lazily[S](
    model: Model[S],
    start: S,
    *,
    reaches: Callable[[S, S], bool] | None = None,
    seed: Callable[[S, Action[S]], bool] | None = None,
    slack: float = 1e-9,
    **options,
) -> LazySolution[S]:
    """Minimise the mean cost of the main target from `start` in `model`, offering its candidates only as the solve needs them.

    `model` is the full model `M`; an action with `extra_inputs` is a candidate, and each of its extra inputs must be a
    `Need` (as for `Acquisition`, whose `reaches` is passed on and used for the bounds too). Two candidates of one state
    must differ in `(label, extra_inputs)`, which is the key under which one is offered. `seed(state, action)` says which
    candidates are offered at the start (default none); a good seed only saves rounds, never changes the answer. `slack`
    is the relative slack of the test (0 or more, below 1). `options` go to `solve` (`tolerance`, `direct_solve_limit`, ...).

    The model is explored whole once: every state reachable from `start` and from the start of any `Need`, under every
    action of `M`, with each state's actions asked of `model` once. That is what the lower bound needs; the solve itself
    builds only what the offers reach.
    """
    if isinstance(slack, bool) or not isinstance(slack, Real) or not (0 <= slack < 1):
        raise ValueError(f"slack must be a real in [0, 1), got {slack!r}")
    reaches = reaches if reaches is not None else operator.eq
    space = _Space(model, reaches)
    space.explore(start)
    offered: dict[S, set[Hashable]] = defaultdict(set)
    if seed is not None:
        for state, candidates in space.candidates.items():
            for key, action in candidates:
                if seed(state, action):
                    offered[state].add(key)
    pairs = sum(len(candidates) for candidates in space.candidates.values())

    rounds: list[Round] = []
    while True:
        acquisition = Acquisition(_Offered(space, offered), reaches=reaches)
        begin = acquisition.start(start)
        solution = solve(acquisition, [begin], **options)
        failing = _check(space, acquisition, solution, offered, slack)
        now = sum(len(keys) for keys in offered.values())
        wants = {product[1] for product in solution.values}
        added = sum(len(keys) for keys in failing.values())
        rounds.append(Round(len(solution.values), len(wants), now, added))
        if not failing:
            return LazySolution(
                solution,
                acquisition,
                begin,
                {state: frozenset(keys) for state, keys in offered.items() if keys},
                pairs,
                tuple(rounds),
                float(slack),
            )
        for state, keys in failing.items():
            offered[state] |= keys


class _Offered[S]:
    """The model of one round: every plain action of a state, and the candidates offered there."""

    def __init__(self, space: "_Space[S]", offered: Mapping[S, set[Hashable]]) -> None:
        self._space = space
        self._offered = offered

    def is_goal(self, state: S) -> bool:
        return self._space.model.is_goal(state)

    def actions(self, state: S) -> tuple[Action[S], ...]:
        space = self._space
        if state not in space.plain:  # the bounds were made from the states `explore` found; a state outside them has none
            raise RuntimeError(f"state {state!r} was not found when the model was explored: its actions must not change between calls")
        keys = self._offered.get(state, ())
        return (*space.plain[state], *(action for key, action in space.candidates[state] if key in keys))


class _Space[S]:
    """The base states of `M`, built once: their actions, split into plain and candidates, and the lower bounds `D`."""

    def __init__(self, model: Model[S], reaches: Callable[[S, S], bool]) -> None:
        self.model = model
        self.reaches = reaches
        self.plain: dict[S, tuple[Action[S], ...]] = {}
        self.candidates: dict[S, tuple[tuple[Hashable, Action[S]], ...]] = {}
        self._forward: dict[S, list[tuple[float, S]]] = {}
        self._reverse: dict[S, list[tuple[float, S]]] = defaultdict(list)
        self._prepared: dict[tuple[S, Hashable], tuple[float, tuple[tuple[S, float], ...], tuple[Need[S], ...]]] = {}
        self._sources: dict[object, tuple[S, ...]] = {}
        self._to: dict[object, dict[S, float]] = {}
        self._from: dict[S, dict[S, float]] = {}
        self._acquisition: dict[tuple[S, S], float] = {}

    # --- the states and their actions -----------------------------------------------------------------

    def expand(self, state: S) -> None:
        """Ask the model for the actions of `state` (once) and record their edges."""
        if state in self.plain:
            return
        plain, candidates, seen = [], [], set()
        edges = self._forward[state] = []
        for action in self.model.actions(state):
            if not isinstance(action, Action):
                raise TypeError(f"the actions of state {state!r} must be Action objects, got {action!r}")
            for entry in action.extra_inputs:
                if not isinstance(entry, Need):
                    raise TypeError(
                        f"extra input {entry!r} of an action in state {state!r} is not a Need: "
                        "a lazy model must write every extra input as Need(start, want)"
                    )
            for outcome in action.outcomes:
                if outcome.weight > 0 and outcome.state != state:
                    edges.append((action.cost, outcome.state))
                    self._reverse[outcome.state].append((action.cost, state))
            if not action.extra_inputs:
                plain.append(action)
                continue
            key = (action.label, action.extra_inputs)
            if key in seen:
                raise ValueError(
                    f"two candidate actions of state {state!r} have the label {action.label!r} and the same inputs; "
                    "a lazy model must tell its candidates apart by (label, extra_inputs)"
                )
            seen.add(key)
            candidates.append((key, action))
        self.plain[state] = tuple(plain)
        self.candidates[state] = tuple(candidates)

    def explore(self, start: S) -> None:
        """Expand every state reachable from `start` and from the start of any `Need`, under every action."""
        stack, found = [start], {start}
        while stack:
            state = stack.pop()
            self.expand(state)
            targets = [target for _, target in self._forward[state]]
            for action in (*self.plain[state], *(action for _, action in self.candidates[state])):
                targets.extend(entry.start for entry in action.extra_inputs)
            for target in targets:
                if target not in found:
                    found.add(target)
                    stack.append(target)
        self.nodes = tuple(found)

    def prepared(self, state: S, key: Hashable, action: Action[S]) -> tuple[float, tuple[tuple[S, float], ...], tuple[Need[S], ...]]:
        """The cost, the outcomes as (successor, chance) and the needs of a candidate, as floats, built once."""
        found = self._prepared.get((state, key))
        if found is None:
            total = sum(outcome.weight for outcome in action.outcomes)
            chances = tuple((outcome.state, outcome.weight / total) for outcome in action.outcomes if outcome.weight > 0)
            found = self._prepared[(state, key)] = (action.cost, chances, action.extra_inputs)
        return found

    # --- the determinized distance D ---------------------------------------------------------------------

    def sources(self, want: object) -> tuple[S, ...]:
        """The base states that end an acquisition of `want`: the goals of the model for `MAIN`, else those that reach `want`."""
        found = self._sources.get(want)
        if found is None:
            if want is MAIN:
                found = tuple(state for state in self.nodes if self.model.is_goal(state))
            else:
                found = tuple(state for state in self.nodes if self.reaches(state, want))
            self._sources[want] = found
        return found

    def to(self, want: object) -> dict[S, float]:
        """`D_want(s)` for every state: the cheapest path of action costs to a state that ends the acquisition (inf if none)."""
        found = self._to.get(want)
        if found is None:
            found = self._to[want] = _dijkstra(self.sources(want), self._reverse)
        return found

    def acquisition(self, start: S, want: S) -> float:
        """`D_want(start)`: a lower bound on what it costs to obtain `want` from `start` (one forward search per start)."""
        key = (start, want)
        found = self._acquisition.get(key)
        if found is None:
            distance = self._from.get(start)
            if distance is None:
                distance = self._from[start] = _dijkstra((start,), self._forward)
            found = self._acquisition[key] = min((distance.get(state, math.inf) for state in self.sources(want)), default=math.inf)
        return found


def _dijkstra[S](roots: Iterable[S], edges: Mapping[S, list[tuple[float, S]]]) -> dict[S, float]:
    """Shortest distances from `roots` over `edges[state] = [(cost, next state)]`."""
    best = {root: 0.0 for root in roots}
    heap = [(0.0, index, root) for index, root in enumerate(best)]
    heapq.heapify(heap)
    counter = len(heap)
    while heap:
        distance, _, state = heapq.heappop(heap)
        if distance > best.get(state, math.inf):
            continue
        for cost, target in edges.get(state, ()):
            reached = distance + cost
            if reached < best.get(target, math.inf):
                best[target] = reached
                counter += 1
                heapq.heappush(heap, (reached, counter, target))
    return best


def _check[S](
    space: _Space[S],
    acquisition: Acquisition[S],
    solution: Solution[tuple],
    offered: Mapping[S, set[Hashable]],
    slack: float,
) -> dict[S, set[Hashable]]:
    """The candidates left out that the values of this solve do not prove unneeded, by base state.

    For every solved product state `x = (want, s)` with value `v` and every candidate at `s` not offered, the candidate is
    unneeded when `cost + sum V(input) + sum p(j) L(j) >= v (1 - slack)`; `L(j)` is the value of `(want, j)` when it was
    solved with a finite value and `D_want(j)` otherwise, and `V(input)` likewise for the process of the input (module
    docstring). Terms are not negative, so a sum is dropped as soon as it passes the limit. A state with no finite value
    fails every candidate it has, unless `D` says the want cannot be reached from it at all.
    """
    values = solution.values
    failing: dict[S, set[Hashable]] = defaultdict(set)
    infinity = math.inf
    for product, value in values.items():
        _, want, state = product
        if value == 0.0:  # an end of the acquisition: no action is taken there
            continue
        candidates = space.candidates.get(state)
        if not candidates:
            continue
        held = offered.get(state, ())
        if value == infinity:  # no incumbent: nothing can be pruned, unless nothing can reach the want from here
            if space.to(want).get(state, infinity) == infinity:
                continue
            failing[state].update(key for key, _ in candidates if key not in held)
            continue
        limit = value * (1.0 - slack)
        distance = space.to(want)
        for key, action in candidates:
            if key in held or key in failing[state]:
                continue
            cost, chances, needs = space.prepared(state, key, action)
            bound = cost
            for need in needs:
                inner = values.get(acquisition.product(need.want, need.start), infinity)
                bound += inner if inner != infinity else space.acquisition(need.start, need.want)
            if bound >= limit:
                continue
            for successor, chance in chances:
                level = values.get(acquisition.product(want, successor), infinity)
                bound += chance * (level if level != infinity else distance.get(successor, infinity))
                if bound >= limit:
                    break
            else:
                failing[state].add(key)
    return {state: keys for state, keys in failing.items() if keys}
