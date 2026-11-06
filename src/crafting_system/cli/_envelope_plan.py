"""The envelope search on a plan: the crafting problem of `_envelope.Search`, solved to a `PackedResult` (ticket #377, OR-12, OR-13).

`CraftingProblem` fills the generic search from the `Abstraction`, the priced offers and the walk-free bound of #497 (`_pattern_bound`):

* `lower(state)` is the value of the state's key in the optimistic model (less the solver's certified error): at most the exact cost of every state
  with that key;
* `candidates(state)` are the offers the walk would offer there (the corrupting and quality prunings of `_prune.keyed_offers`, the restart not at the
  start), each with the least backup of its abstract actions at the state's key under the lowered values: at most the exact `Q*` of the offer at the
  state (the per-offer statement `tests/test_abstraction_pattern.py` checks against every member of a key). An offer the model has no abstract action
  for at the key is one no member of the key can take, so the state cannot take it; the restart is the exception the model does not list at the
  start's own key, so it is always a candidate, with the start's bound as its own;
* `kernel_key` and `kernel` are the abstraction's, with a refusal (`NotApplicableError`, or a model gap `OutOfScopeError`, which is noted in
  `abstraction.gaps` as the walk notes it) raised as `Refused`.

`envelope_result` runs the search, solves the graph it ended with exactly (`_packed.solve_walked`: merge, policy iteration, certificate, the lumped chain
the report and the risk read) and returns the `PackedResult` that `make_plan` takes from the packed walk, with the search's numbers in `info["envelope"]`.
`envelope_limits` is the `Limit` the report shows: which cut ran and what it guarantees (OR-13).
"""

import math
import time
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass

import numpy as np

from crafting_system.abstraction import PRUNED_CORRUPTING, PRUNED_QUALITY, Abstraction, CompressedState, integer_weights
from crafting_system.abstraction._pattern import Pattern
from crafting_system.actions import NotApplicableError, OutOfScopeError

from . import _limits
from ._envelope import Net, NoPolicy, Refused, Search
from ._limits import Limit, claim
from ._offers import RESTART, BuyStartItem, PricedOffer
from ._packed import PackedResult, Walked, solve_walked
from ._pattern_bound import PatternBound, pattern_lower_bound
from ._prune import corrupting_offer_pruned

RESTART_KEY = ("restart",)


class CraftingProblem:
    """The crafting plan as a `_envelope.Problem` (see the module text)."""

    def __init__(
        self, abstraction: Abstraction, start: CompressedState, offers: Sequence[PricedOffer], bound: PatternBound, *, prune_corrupting: bool = True
    ) -> None:
        self.ab = abstraction
        self.start = start
        self.offers = tuple(offers)
        self.prune_corrupting = prune_corrupting
        self.pattern = Pattern(abstraction, tags=bound.model.keys[0].tags is not None)
        model = bound.model
        self.index = model.index
        values = np.asarray(bound.value, dtype=np.float64) * (1.0 - bound.error_bound)  # lowered by what the solver cannot certify
        self.values = values
        expected: list[float] = []  # the lowered value of each pushed kernel of the model, in expectation
        for successors, weights in model.kernels:
            total = sum(weights)
            chance = np.array([w / total for w in weights])  # int / int is exact to one rounding, whatever the size
            expected.append(float(chance @ values[list(successors)]))
        self.lowest: list[dict[int, float]] = []  # key -> offer position -> the least lowered backup of its abstract actions there
        for row in model.actions:
            found: dict[int, float] = {}
            for position, kernel in row:
                q = self.offers[position].cost + expected[kernel]
                if position not in found or q < found[position]:
                    found[position] = q
            self.lowest.append(found)
        self.restart = next((p for p, priced in enumerate(self.offers) if isinstance(priced.offer.action, BuyStartItem)), None)
        self.start_lower = float(values[0])  # key 0 is the start's
        self.keys_missing = 0

    def is_goal(self, state: CompressedState) -> bool:
        return self.ab.is_goal(state)

    def _key(self, state: CompressedState) -> int | None:
        return self.index.get(self.pattern.key(state))

    def lower(self, state: CompressedState) -> float:
        k = self._key(state)
        if k is None:
            self.keys_missing += 1  # the model never reached this key: 0 is a bound that needs no model
            return 0.0
        return float(self.values[k])

    def candidates(self, state: CompressedState) -> list[tuple[float, int]]:
        k = self._key(state)
        found = None if k is None else self.lowest[k]
        out: list[tuple[float, int]] = []
        for position, priced in enumerate(self.offers):
            action = priced.offer.action
            restart = isinstance(action, BuyStartItem)
            if priced.label == RESTART and state == self.start:
                continue
            if self.prune_corrupting and corrupting_offer_pruned(self.ab, priced, state):
                self.ab.prunings.note(priced.label, PRUNED_CORRUPTING)
                continue
            if not restart and self.ab.quality_offer_pruned(state, action):
                self.ab.prunings.note(priced.label, PRUNED_QUALITY)
                continue
            if restart:
                out.append((priced.cost + self.start_lower, position))
            elif found is None:
                out.append((0.0, position))
            elif position in found:
                out.append((found[position], position))
        return out

    def cost(self, position: int) -> float:
        return self.offers[position].cost

    def kernel_key(self, state: CompressedState, position: int) -> Hashable | None:
        action = self.offers[position].offer.action
        if isinstance(action, BuyStartItem):
            return RESTART_KEY
        try:
            return self.ab.kernel_key(state, action)
        except NotApplicableError:
            raise Refused from None
        except OutOfScopeError as gap:
            self.ab.gaps.note(self.offers[position].label, state, gap)
            raise Refused from None

    def kernel(self, state: CompressedState, position: int) -> dict[CompressedState, int]:
        action = self.offers[position].offer.action
        if isinstance(action, BuyStartItem):
            return {self.start: 1}
        try:
            return integer_weights(self.ab.kernel(state, action))
        except NotApplicableError:
            raise Refused from None
        except OutOfScopeError as gap:
            self.ab.gaps.note(self.offers[position].label, state, gap)
            raise Refused from None

    def release(self) -> None:
        self.ab._prepared_by.clear()


def route_incumbent(route, data) -> Callable[[CompressedState], list[str]]:
    """A given route as the incumbent of the search: at a state, the labels of the offers its matching rules name, in order.

    The search realizes the first that the game allows, so a route that says `skip_refused` falls through to its next rule as `evaluate_route` does;
    where none matches or none applies the incumbent restarts (the route "completed with a restart"). A label the search does not offer (a twin
    left out, say) is passed over.
    """

    def choose(state: CompressedState) -> list[str]:
        found: list[str] = []
        for rule in route.rules:
            if not rule.when.matches(state, data):
                continue
            found.append(rule.do)
            if not route.skip_refused:
                break
        return found

    return choose


@dataclass(frozen=True)
class EnvelopeInfo:
    """What the report says of the search (`info["envelope"]` of the `PackedResult`)."""

    exact: bool
    stopped: str | None
    lower: float  # LB: no plan costs less (the start's remaining cost, without the price of the start item)
    upper: float  # U: the plan returned costs this much on average
    rounds: int
    touched: int
    expanded: int
    realized: int
    candidates: int
    keys_missing: int
    incumbent: bool
    first_upper: float | None
    bound_keys: int
    bound_seconds: float
    seconds: float
    peak_mb: float | None


def envelope_result(
    abstraction: Abstraction,
    start: CompressedState,
    offers: Sequence[PricedOffer],
    *,
    prune_corrupting: bool = True,
    incumbent: Callable[[CompressedState], Sequence[str]] | None = None,
    net: Net | None = None,
    bound: PatternBound | None = None,
    tolerance: float = 1e-10,
    progress: Callable[[str], None] | None = None,
) -> PackedResult:
    """Search the graph of `offers` from `start` by the envelope search and solve what it expanded; `info["envelope"]` is an `EnvelopeInfo`.

    Raises `OutOfScopeError` when the bound cannot be built for this abstraction (a goal with a roll limit, an action that rerolls values, an unveil
    offer, imprints: #507) and `NoPolicy` when no policy reaches the goal, or the net stopped the search before one closed and the start is given.
    """
    from . import _packed

    say = progress or _packed.PROGRESS or (lambda _text: None)
    began = time.perf_counter()
    if bound is None:
        bound = pattern_lower_bound(abstraction, start, offers, progress=say)
    built = time.perf_counter()
    say(f"bound built: {bound.model.stats.keys:,} keys, start value {bound.start_value!r} ({built - began:.0f} s)")
    problem = CraftingProblem(abstraction, start, offers, bound, prune_corrupting=prune_corrupting)
    where = {priced.label: position for position, priced in enumerate(offers)}
    positions = None if incumbent is None else (lambda state: [where[label] for label in incumbent(state) if label in where])
    search = Search(problem, net=net, incumbent=positions, progress=say, tolerance=tolerance)
    result = search.run()
    walked = Walked(result.graph, result.states, result.index, tuple(offers), time.perf_counter() - built)
    packed = solve_walked(abstraction, start, walked, tolerance=tolerance, progress=say)
    mean = float(packed.solution.values[start])
    stats = result.stats
    packed.info["envelope"] = EnvelopeInfo(
        result.exact, result.stopped, result.lower, mean, stats.rounds, stats.touched, stats.expanded, stats.realized, stats.candidates,
        problem.keys_missing, incumbent is not None, stats.first_upper, bound.model.stats.keys, bound.build_seconds + bound.solve_seconds,
        time.perf_counter() - began, stats.peak_mb,
    )  # fmt: skip
    return packed


def envelope_limits(info: EnvelopeInfo) -> tuple[Limit, ...]:
    """The limit that says which cut ran and what it still guarantees (OR-13)."""
    if info.exact:
        return (
            Limit(
                _limits.SOLVE,
                "The search expanded only what could matter",
                f"it looked at the actions of {info.expanded:,} of the {info.touched:,} item states it found and built {info.realized:,} of the "
                f"{info.candidates:,} actions offered at them: an action it did not build costs more, even at its best case, than the one it kept",
                **claim(
                    "the methods offered",
                    "The cut is exact: nothing was left out for being unlikely or by a tolerance, and the mean cost is that of the best plan.",
                ),
            ),
        )
    return (
        Limit(
            _limits.SOLVE,
            "The search was stopped",
            f"{info.stopped}, after {info.rounds:,} rounds and {info.expanded:,} item states looked at; the plan restarts from the start item "
            "wherever the search had not looked",
            f"The plan is not shown to be the best: it costs {info.upper:,.2f} Chaos on average after the start item, and no plan costs less "
            f"than {info.lower:,.2f}.",
        ),
    )


__all__ = ["CraftingProblem", "EnvelopeInfo", "NoPolicy", "Net", "envelope_limits", "envelope_result", "route_incumbent"]
