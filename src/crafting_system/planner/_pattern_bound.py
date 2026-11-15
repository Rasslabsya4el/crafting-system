"""The crafted-pattern lower bound of a plan, solved (ticket #497, research #376, ADR-0063 point 3; the build's net and its offers, ticket #626).

`pattern_lower_bound` builds the optimistic model of the key from the `Abstraction` and the priced offers (`abstraction._pattern`, no walk of
the concrete graph), solves it on the packed solver, and returns the value of every key. The value of a key is at most the exact cost of
every concrete state that has it (`lower` allows for the solver's certified error), so `lower` of the start key is a lower bound of the
cost of the whole graph: the `LB` of the certificate `[LB, U]` (#499) and the bound of the envelope search (#377).

**Which offers the model builds (#626, #829).** The kernel of an offer is an exact distribution, and a fossil set's takes seconds. With many offers
(`item` given) the model is built once on a subset `S` of them and carries, at every key, one more action: a *floor action* to the goal whose cost is
the least floor (`_offer_floor`) of the offers outside `S` at that key. Every action outside `S` costs at least that at the key, so the model is still
a lower bound of the model on all offers, whatever `S` is. `S` is the restart, the bench crafts and the rerolls of least cost / pbar; the model is not
built again as offers matter: each offer outside `S` carries its own floor into the envelope search, which builds it at a state only when that floor,
its chance worked out once for all the states of its class (`OfferFloors.tighten`), is below the best it has there. (Until #829 the model grew by
rounds, solved again each time, and R08 at the prices of 2026-11-10 spent its whole run on them.)

**The net (OR-12, OR-13).** The build is asked for its `stop` between two offers, so a key of thousands of offers is no longer one step. A build that
stops leaves the keys it did not expand as tips, each with a floor action of the least floor of *all* the offers at that key, and the model is
solved as it is: its value is still a lower bound, weaker where the build did not reach. `PatternBound.stopped` says why and `PatternBound.phase` says
which phase it was in.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.abstraction._pattern import PatternBuilder, PatternKey, PatternModel, PatternOffer, PatternStats
from crafting_system.solver import PackedBuilder, solve_packed

from ._offer_floor import CLASSES, FloorsStopped, OfferFloors
from ._offers import BuyStartItem, PricedOffer

FAKE = -1  # the tag of the floor action
FLOOR_COST = 1e-200  # a floor action of cost 0 is carried at this cost, as the envelope search carries a fake action
MIN_OFFERS = 40  # fewer priced offers than this are all built and none is a twin left out (nothing to gain); `_plan` merges twins from this many too


@dataclass(frozen=True)
class PatternBound:
    """The solved optimistic model of the key."""

    model: PatternModel
    value: np.ndarray  # the value of every key (index = `model.index[key]`)
    start_value: float  # the value of the start key: at most the exact cost of the start
    error_bound: float  # the solver's certified relative error: the exact value of the model lies in `[value (1 - e), value (1 + e)]`
    build_seconds: float
    solve_seconds: float
    positions: tuple[int, ...] = ()  # the position in the offers given of each offer of the model
    floors: OfferFloors | None = None  # the floors of the offers (None unless the model was built on a subset of many offers)
    stopped: str | None = None  # the net that ended the build, None for a complete model
    phase: str = "complete"  # where the build was when it stopped: "floors" or "model" (expanding keys)
    seconds_by_phase: dict = field(default_factory=dict, compare=False)

    @property
    def lower(self) -> float:
        """A lower bound of the exact cost of the start, with the solver's error taken off."""
        return self.start_value * (1.0 - self.error_bound)

    @property
    def stats(self) -> PatternStats:
        return self.model.stats

    @property
    def complete(self) -> bool:
        return self.stopped is None

    def value_of(self, pattern, state: CompressedState) -> float:
        """The value of the key of a concrete state (`pattern` is the `Pattern` the model was built with, or any with the same `tags`)."""
        return float(self.value[self.model.index[pattern.key(state)]])


def pattern_offers(priced: Sequence[PricedOffer]) -> list[PatternOffer]:
    """The offers of a plan as the model sees them: the restart (`BuyStartItem`) has no action."""
    return [PatternOffer(p.label, None if isinstance(p.offer.action, BuyStartItem) else p.offer.action, p.cost) for p in priced]


def pack_pattern_model(model: PatternModel, offers: Sequence[PatternOffer], floor: Callable[[PatternKey, bool], float | None] | None = None):
    """The packed graph of the model: state `k` is key `k`, an action's tag is its offer number.

    `floor(key, expanded)` is the cost of the floor action of a key (None for none): an action with tag `FAKE` to one more goal state, the last. A key that
    was not expanded (a tip) has no other action.
    """
    builder = PackedBuilder()
    built: dict[int, int] = {}
    expanded = model.expanded or [True] * len(model.keys)
    n = len(model.keys)
    sink = None
    for key, row, is_goal, was_built in zip(model.keys, model.actions, model.goal, expanded):
        for offer_index, kernel in row:
            made = built.get(kernel)
            if made is None:
                successors, weights = model.kernels[kernel]
                made = built[kernel] = builder.kernel([n if successor < 0 else successor for successor in successors], weights)  # -1 is the sink
            builder.action(offer_index, offers[offer_index].cost, made)
        if floor is not None and not is_goal:
            cost = floor(key, was_built)
            if cost is not None:
                if sink is None:
                    sink = builder.kernel([n], [1])
                builder.action(FAKE, max(cost, FLOOR_COST), sink)
        builder.close_state(is_goal)
    builder.close_state(True)  # the sink: the last state, a goal; the floor action and the mass that an approximate kernel does not account for go to it
    return builder.build()


def pattern_lower_bound(
    abstraction: Abstraction,
    start: CompressedState,
    priced: Sequence[PricedOffer],
    *,
    tags: bool | None = None,
    progress: Callable[[str], None] | None = None,
    max_keys: int | None = None,
    item=None,
    stop: Callable[[], str | None] | None = None,
    approximate: bool | None = None,
    refuse_above: float | None = None,
) -> PatternBound:
    """Build and solve the optimistic model of the key for the offers `priced`, from the state `start`.

    `refuse_above` is the certified error above which the model's solve is refused (default: the solver's `ACCEPT_BOUND`). The bound is used lowered
    by that error (`PatternBound.error_bound`), so it is a lower bound whatever the error: a search that stops at a gap passes a share of its gap (#867).

    `item` (the start item) turns on the offers' floors when there are `MIN_OFFERS` offers or more: the model is then built on the offers that can
    matter (see the module text). `stop` is the net: it is asked while the model is built and returns the reason once one is reached.
    `approximate` makes the kernels in floats, shrunk so that the model stays below the exact one (`build_pattern_model`); by default it is on exactly
    when the offers' floors are, since a model of hundreds of offers is where the exact distributions cost the time (R08: 0.4 s each, 6.9 s with a
    Fractured Fossil, 3,938 fossil sets), and a model of a few offers is built exactly as before.
    """
    say = progress or (lambda _text: None)
    all_offers = pattern_offers(priced)
    began = time.perf_counter()
    phases: dict[str, float] = {"floors": 0.0, "model": 0.0, "solve": 0.0}
    floors = None
    order: list[int] = list(range(len(priced)))  # the offers of the model, in the order they joined: offer j of the model is `priced[order[j]]`
    floors_stopped: str | None = None  # the reason the net ended the floors: the bound is then the start alone, every key a tip with the cheapest offer as its floor
    if item is not None and len(priced) >= MIN_OFFERS:
        say(f"offers' floors: working out the floors of {len(priced):,} offers")
        try:
            floors = OfferFloors(abstraction, start, priced, item, stop)
        except FloorsStopped as reached:
            floors_stopped, order = reached.reason, []
            say(f"offers' floors: STOPPED ({floors_stopped}) after {time.perf_counter() - began:.1f} s; the bound is the cheapest offer at every key")
            stop = lambda: floors_stopped  # noqa: E731  (the builder below ends at once, with every key a tip)
        else:
            order = floors.initial()
            phases["floors"] = time.perf_counter() - began
            say(
                f"offers' floors: rho {floors.rho!r}, {len(floors.chosen)} necessary open leaves; the model starts on {len(order):,} of {len(priced):,} offers "
                f"({phases['floors']:.1f} s)"
            )
    builder = PatternBuilder(abstraction, start, tags=tags, progress=say, max_keys=max_keys, stop=stop, grow=floors is not None, approximate=floors is not None if approximate is None else approximate)
    mark = time.perf_counter()
    model = builder.extend([all_offers[p] for p in order])
    built = time.perf_counter()
    phases["model"] += built - mark
    inside = set(order)
    outside = [p for p in range(len(priced)) if p not in inside] if floors is not None else []
    floor = _floor_of(floors, outside, priced) if floors is not None else _tip_floor(priced)
    graph = pack_pattern_model(model, [all_offers[p] for p in order], floor)
    say(f"model: solving the count on {len(model.keys):,} keys and {graph.num_kernels:,} kernels")
    solved = solve_packed(graph, progress=None, refuse_above=refuse_above)  # one step the net cannot cut: it overshoots by at most this solve (R04: 0.9 s on 79,000 kernels)
    solved_at = time.perf_counter()
    phases["solve"] += solved_at - built
    n = len(model.keys)
    value = np.asarray(solved.value[: n + 1])  # the keys, and the sink last (a goal: 0)
    say(
        f"model: {len(order):,} offers, {n:,} keys ({sum(model.expanded):,} expanded), {model.stats.kernels:,} kernels, start value "
        f"{float(solved.value[0])!r} (model {built - mark:.1f} s, solve {solved_at - built:.1f} s)" + (f"; STOPPED: {model.stopped}" if model.stopped else "")
    )
    phase = "floors" if floors_stopped else "model" if model.stopped else "complete"
    return _bound(model, value, float(solved.error_bound), phases, began, order, floors, model.stopped, phase)


def _bound(model, value, error, phases, began, order, floors, stopped, phase) -> PatternBound:
    solve = phases["solve"]
    return PatternBound(
        model, value, float(value[0]), error, time.perf_counter() - began - solve, solve, tuple(order), floors, stopped, phase, dict(phases)
    )  # fmt: skip


def _tip_floor(priced: Sequence[PricedOffer]) -> Callable[[PatternKey, bool], float | None]:
    """The floor action of a build without offers' floors: only a tip has one, at the cost of the cheapest offer (any action costs that or more)."""
    cheapest = min((p.cost for p in priced), default=0.0)
    return lambda _key, expanded: None if expanded else cheapest


def _floor_of(floors: OfferFloors, outside: list[int], priced: Sequence[PricedOffer]) -> Callable[[PatternKey, bool], float | None]:
    """The floor action of a key: the least floor of the offers outside the model there, or of all the offers when the key is a tip."""
    names = range(len(priced))
    table = {klass: (floors.floor(outside, klass), floors.floor(names, klass)) for klass in CLASSES}

    def floor(key: PatternKey, expanded: bool) -> float | None:
        cost = table[floors.klass(key.flags, key.fractured, key.status)][0 if expanded else 1]
        return None if cost == float("inf") else cost

    return floor


__all__ = ["PatternBound", "pack_pattern_model", "pattern_lower_bound", "pattern_offers"]
