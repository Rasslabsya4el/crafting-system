"""The crafted-pattern lower bound of a plan, solved (ticket #497, research #376, ADR-0063 point 3).

`pattern_lower_bound` builds the optimistic model of the key from the `Abstraction` and the priced offers (`abstraction._pattern`, no walk of
the concrete graph), solves it on the packed solver, and returns the value of every key. The value of a key is at most the exact cost of
every concrete state that has it (`lower` allows for the solver's certified error), so `lower` of the start key is a lower bound of the
cost of the whole graph: the `LB` of the certificate `[LB, U]` (#499) and the bound of the envelope search (#377).
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.abstraction._pattern import PatternModel, PatternOffer, PatternStats, build_pattern_model
from crafting_system.solver import PackedBuilder, solve_packed

from ._offers import BuyStartItem, PricedOffer


@dataclass(frozen=True)
class PatternBound:
    """The solved optimistic model of the key."""

    model: PatternModel
    value: np.ndarray  # the value of every key (index = `model.index[key]`)
    start_value: float  # the value of the start key: at most the exact cost of the start
    error_bound: float  # the solver's certified relative error: the exact value of the model lies in `[value (1 - e), value (1 + e)]`
    build_seconds: float
    solve_seconds: float

    @property
    def lower(self) -> float:
        """A lower bound of the exact cost of the start, with the solver's error taken off."""
        return self.start_value * (1.0 - self.error_bound)

    @property
    def stats(self) -> PatternStats:
        return self.model.stats

    def value_of(self, pattern, state: CompressedState) -> float:
        """The value of the key of a concrete state (`pattern` is the `Pattern` the model was built with, or any with the same `tags`)."""
        return float(self.value[self.model.index[pattern.key(state)]])


def pattern_offers(priced: Sequence[PricedOffer]) -> list[PatternOffer]:
    """The offers of a plan as the model sees them: the restart (`BuyStartItem`) has no action."""
    return [PatternOffer(p.label, None if isinstance(p.offer.action, BuyStartItem) else p.offer.action, p.cost) for p in priced]


def pack_pattern_model(model: PatternModel, offers: Sequence[PatternOffer]):
    """The packed graph of the model: state `k` is key `k`, an action's tag is its offer number."""
    builder = PackedBuilder()
    built: dict[int, int] = {}
    for row, is_goal in zip(model.actions, model.goal):
        for offer_index, kernel in row:
            made = built.get(kernel)
            if made is None:
                successors, weights = model.kernels[kernel]
                made = built[kernel] = builder.kernel(successors, weights)
            builder.action(offer_index, offers[offer_index].cost, made)
        builder.close_state(is_goal)
    return builder.build()


def pattern_lower_bound(
    abstraction: Abstraction,
    start: CompressedState,
    priced: Sequence[PricedOffer],
    *,
    tags: bool | None = None,
    progress: Callable[[str], None] | None = None,
    max_keys: int | None = None,
) -> PatternBound:
    """Build and solve the optimistic model of the key for the offers `priced`, from the state `start`."""
    offers = pattern_offers(priced)
    began = time.perf_counter()
    model = build_pattern_model(abstraction, start, offers, tags=tags, progress=progress, max_keys=max_keys)
    built = time.perf_counter()
    if progress is not None:
        progress(f"model built: {model.stats}")
    graph = pack_pattern_model(model, offers)
    solved = solve_packed(graph, progress=progress)
    return PatternBound(model, solved.value, float(solved.value[0]), float(solved.error_bound), built - began, time.perf_counter() - built)


__all__ = ["PatternBound", "pack_pattern_model", "pattern_lower_bound", "pattern_offers"]
