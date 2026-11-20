"""The crafted-pattern lower bound of a plan, solved (ticket #497, research #376, ADR-0063 point 3; the build's net and its offers, ticket #626).

`pattern_lower_bound` builds the optimistic model of the key from the `Abstraction` and the priced offers (`abstraction._pattern`, no walk of
the concrete graph), solves it on the packed solver, and returns the value of every key. The value of a key is at most the exact cost of
every concrete state that has it (`lower` allows for the solver's certified error), so `lower` of the start key is a lower bound of the
cost of the whole graph: the `LB` of the certificate `[LB, U]` (#499) and the bound of the envelope search (#377).

**Which offers the model builds (#626, #829).** The kernel of an offer is an exact distribution, and a fossil set's takes seconds. With many offers
(`item` given) the model is built once on a subset `S` of them and carries, at every key, one more action: a *floor action* to the goal whose cost is
the least floor (`_offer_floor`) of the offers outside `S` at that key. Every action outside `S` costs at least that at the key, so the model is still
a lower bound of the model on all offers, whatever `S` is. `S` starts with the restart, the bench crafts and the rerolls of least cost / pbar, and
grows by the offers that could lower the value of a key where the floor action is the cheapest action (`_binding`), each offer's floor first raised as
far as it goes (`OfferFloors.needed`), until the floor action is the cheapest at no key the model's policy reaches nor of the start's shape: there the
model then equals the model on all offers. Each offer still outside `S` carries its own floor into the envelope search, which builds it at a state
only when that floor, its chance worked out once for all the states of its class (`OfferFloors.tighten`), is below the best it has there.

*Why the model grows (#988).* A floor is raised only where it has something to raise: a reroll's chance, at a state of the start's shape. Everywhere
else an offer's floor is its price (a terminal offer such as an Orb of Augmentation, an Exalted Orb or a harvest swap, and every offer at a state of
another shape, which is most states once the item has changed rarity: 1,088 of the 1,089 keys of the generated essences/large). The floor action of
a key is the least floor of the offers outside `S`, so a model built once on `S` was capped at the price of the cheapest offer left out: the start
value of growing-4-harvest/small was 0.0095 (an Orb of Augmentation) where the optimum is 5.08, and of essences/large 0.109. No `tighten` of the
search can raise those floors, and the search, its bounds that low at every tip, ran out of time where the grown model ended exact (#829 had
dropped the growth: R08 at the prices of 2026-11-10 spent its whole run on rounds).

*What a round costs (#1086).* The builder keeps every key it expanded and builds at them only the offers that join (`PatternBuilder.extend`). An
offer that joins with a mod the pool does not list (an essence's forced mod) grows the universe, and the build begins again only at the keys the new
slot may be in (`Pattern.may_hold`), keeping every key and kernel (R11 with the Exalted Orb: four essences joined; the bound took 16.7 s here, 17.9 s
on a runner, where the model takes 4.6 s built at once; now 6.4 s, the same value).

**The net (OR-12, OR-13).** The build is asked for its `stop` between two offers, so a key of thousands of offers is no longer one step. A build that
stops leaves the keys it did not expand as tips, each with a floor action of the least floor of *all* the offers at that key, and the model is
solved as it is: its value is still a lower bound, weaker where the build did not reach. `PatternBound.stopped` says why and `PatternBound.phase` says
which phase it was in.
"""

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.abstraction._pattern import CHOICE, IMPRINTS, ChoiceNode, Growth, PatternBuilder, PatternKey, PatternModel, PatternOffer, PatternStats, Room, Ruin, Tally
from crafting_system.solver import ConvergenceError, PackedBuilder, policy_reach, solve_packed

from ._offer_floor import CLASSES, INSIDE, OTHER, OUTSIDE, UNOPENED, FloorsStopped, OfferFloors, shape_of
from ._offer_kinds import SLACK
from ._offers import BuyStartItem, PricedOffer

FAKE = -1  # the tag of the floor action
FLOOR_COST = 1e-200  # a floor action of cost 0 is carried at this cost, as the envelope search carries a fake action
BINDING = 1e-12  # relative: the floor action is "the cheapest" at a key when it is below the model's best by more than this
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
    phase: str = "complete"  # where the build was when it stopped: "floors", "model" (expanding keys) or "growth" (offers joining: the round before stands)
    seconds_by_phase: dict = field(default_factory=dict, compare=False)
    rounds: int = 1  # models built and solved (more than one when offers joined, #988)
    pieces: int = 0  # a build counted in pieces of work (`pieces` of `pattern_lower_bound`, #1101): the pieces it did; 0 otherwise
    share: int | None = None  # the pieces it was given; None for a build on the clock
    late: bool = False  # nearly done when its net was reached, it went on past it (`Growth`, `room` of `pattern_lower_bound`, #1135)
    narrow: dict = field(default_factory=dict, compare=False)  # an offer of the model built at some keys only (#1325): its position in the offers given -> those keys' numbers

    def holds(self, k: int, position: int) -> bool:
        """Whether the model built the offer at `position` at key number `k` (an offer of the model held at some keys only is not built elsewhere)."""
        keys = self.narrow.get(position)
        return keys is None or k in keys

    @property
    def lower(self) -> float:
        """A lower bound of the exact cost of the start, with the solver's error taken off."""
        return self.start_value * lowering(self.error_bound)

    @property
    def stats(self) -> PatternStats:
        return self.model.stats

    @property
    def complete(self) -> bool:
        return self.stopped is None

    def value_of(self, pattern, state: CompressedState) -> float:
        """The value of the key of a concrete state (`pattern` is the `Pattern` the model was built with, or any with the same `tags`)."""
        return float(self.value[self.model.index[pattern.key(state)]])


def lowering(error: float) -> float:
    """What a value certified to a relative `error` is multiplied by to be a lower bound: `1 - error`, and 0 for an error of 1 or more."""
    return max(0.0, 1.0 - error) if math.isfinite(error) else 0.0


def pattern_offers(priced: Sequence[PricedOffer]) -> list[PatternOffer]:
    """The offers of a plan as the model sees them: the restart (`BuyStartItem`) has no action."""
    return [PatternOffer(p.label, None if isinstance(p.offer.action, BuyStartItem) else p.offer.action, p.cost) for p in priced]


def pack_pattern_model(model: PatternModel, offers: Sequence[PatternOffer], floor: Callable[[PatternKey, bool], float | None] | None = None):
    """The packed graph of the model: state `k` is key `k`, an action's tag is its offer number.

    `floor(k, key, expanded)` is the cost of the floor action of key number `k` (None for none): an action with tag `FAKE` to one more goal state, the last. A key that
    was not expanded (a tip) has no other action. The ruined state (`PatternModel.ruined`, #1367) has none once built with its restart row: that row is
    its value on every offer, worked out or not (`abstraction._pattern`, "The ruined keys"), so no offer's floor is below it and none joins it.
    """
    builder = PackedBuilder()
    built: dict[int, int] = {}
    expanded = model.expanded or [True] * len(model.keys)
    n = len(model.keys)
    sink = None
    for k, (key, row, is_goal, was_built) in enumerate(zip(model.keys, model.actions, model.goal, expanded)):
        for offer_index, kernel in row:
            made = built.get(kernel)
            if made is None:
                successors, weights = model.kernels[kernel]
                made = built[kernel] = builder.kernel([n if successor < 0 else successor for successor in successors], weights)  # -1 is the sink
            # a row of a choice node (a step of a relaxed draw, `abstraction/_relaxed.py`) costs nothing: carried at `FLOOR_COST`, as a floor of 0
            builder.action(offer_index, FLOOR_COST if offer_index == CHOICE else offers[offer_index].cost, made)
        if floor is not None and not is_goal and not isinstance(key, ChoiceNode) and not (k == model.ruined and was_built and row):
            cost = floor(k, key, was_built)
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
    pieces: int | None = None,
    room: Room | None = None,
) -> PatternBound:
    """Build and solve the optimistic model of the key for the offers `priced`, from the state `start`.

    `refuse_above` is the certified error above which the model's solve is refused (default: the solver's `ACCEPT_BOUND`). The bound is used lowered
    by that error (`PatternBound.error_bound`), so it is a lower bound whatever the error: a search that stops at a gap passes a share of its gap (#867).

    `item` (the start item) turns on the offers' floors when there are `MIN_OFFERS` offers or more: the model is then built on the offers that can
    matter (see the module text). `stop` is the net: it is asked while the model is built and returns the reason once one is reached.
    `approximate` makes the kernels in floats, shrunk so that the model stays below the exact one (`build_pattern_model`); by default it is on exactly
    when the offers' floors are, since a model of hundreds of offers is where the exact distributions cost the time (R08: 0.4 s each, 6.9 s with a
    Fractured Fossil, 3,938 fossil sets), and a model of a few offers is built exactly as before.

    `pieces` (a run counted in states, #1101) is the build's net in pieces of work (`abstraction._pattern.Tally`: a (member, offer) pair looked at,
    or an offer's floor raised, the binding step's included): it is asked at every offer and before every raise and solve, never on the clock, so
    where it stops is the same on every machine; `stop` is asked after it. The bound says how many it did (`PatternBound.pieces`).
    `room` (a round that began with a plan in hand, #1099, #1135, #1224): the pieces net is the round's whole share, and the build goes on
    past a quarter of it, or past it, as `abstraction._pattern.Pace.verdict` says. Each time a solved model lets more offers join, the build
    tells its nets how far it is (`Growth`, `Pace.grown`: the offers of its first model, of the model solved, of the model being built, of
    those given); the net on the clock (`stop`, when it is a `Pace`: `_envelope_plan.BuildStop`) decides the same of its seconds.
    `PatternBound.late` says it went past its net.
    """
    say = progress or (lambda _text: None)
    all_offers = pattern_offers(priced)
    began = time.perf_counter()
    tally = None if pieces is None else Tally(pieces, _pieces_words, stop, room=room)
    watched = [net for net in (tally, stop) if hasattr(net, "grown")]  # the nets told how far the build is (`Pace`)
    if tally is not None:
        stop = tally
    phases: dict[str, float] = {"floors": 0.0, "model": 0.0, "solve": 0.0}
    floors = None
    order: list[int] = list(range(len(priced)))  # the offers of the model, in the order they joined: offer j of the model is `priced[order[j]]`
    floors_stopped: str | None = None  # the reason the net ended the floors: the bound is then the start alone, every key a tip with the cheapest offer as its floor
    if item is not None and len(priced) >= MIN_OFFERS:
        say(f"offers' floors: working out the floors of {len(priced):,} offers")
        try:
            floors = OfferFloors(abstraction, start, priced, item, stop, tally)
        except FloorsStopped as reached:
            floors_stopped, order = reached.reason, []
            say(f"offers' floors: STOPPED ({floors_stopped}) after {time.perf_counter() - began:.1f} s; the bound is the cheapest offer at every key")
            stop = lambda: floors_stopped  # noqa: E731  (the builder below ends at once, with every key a tip)
        else:
            order = floors.initial()
            phases["floors"] = time.perf_counter() - began
            for net in watched:  # the model grows from part of the offers: past a quarter of a share it needs a pace (`Pace.verdict`)
                net.grows = len(order) < len(priced)
            say(
                f"offers' floors: rho {floors.rho!r}, {len(floors.chosen)} necessary open leaves; the model starts on {len(order):,} of {len(priced):,} offers "
                f"({phases['floors']:.1f} s)"
            )
    builder = PatternBuilder(
        abstraction, start, tags=tags, progress=say, max_keys=max_keys, stop=stop, grow=floors is not None,
        approximate=floors is not None if approximate is None else approximate, tally=tally, ruin=Ruin.of(abstraction, all_offers),
    )
    kept = None  # the last round that ran to its end: (model, value, error bound, order, the offers held at some keys only)
    adding = list(order)
    at: list[list[int]] | None = None  # where the offers joining are built: every key for the first model, the keys that need them after (#1325)
    spread: dict[int, list[int]] | None = None  # offers of the model held at some keys, built at more keys (model offer number -> keys)
    holders: dict[int, set[int]] = {}  # an offer held at some keys only: its position in `priced` -> the numbers of those keys
    first = len(order)  # the offers of the first model: what growth adds is the rest (`Growth.start`)
    rounds = 0
    while True:
        rounds += 1
        mark = time.perf_counter()
        model = builder.extend([all_offers[p] for p in adding], at, spread)
        built = time.perf_counter()
        phases["model"] += built - mark
        if model.stopped is not None and kept is not None:  # the round that was growing the model did not end: the round before stands
            reason = model.stopped
            say(f"model {rounds}: stopped while {len(adding):,} offers were joining ({reason}); the model of round {rounds - 1} stands")
            model, value, error, order, narrow = kept
            return _bound(model, value, error, phases, began, order, floors, rounds - 1, reason, "growth", tally, watched, narrow)
        inside = set(order)
        outside = [p for p in range(len(priced)) if p not in inside] if floors is not None else []
        floor = _floor_of(floors, outside, priced, holders) if floors is not None else _tip_floor(priced)
        graph = pack_pattern_model(model, [all_offers[p] for p in order], floor)
        if kept is not None and stop is not None and (reason := stop()) is not None:  # the solve cannot be interrupted: the net is asked before it
            say(f"model {rounds}: the net was reached before the solve ({reason}); the model of round {rounds - 1} stands")
            model, value, error, order, narrow = kept
            return _bound(model, value, error, phases, began, order, floors, rounds - 1, reason, "growth", tally, watched, narrow)
        say(f"model {rounds}: solving the count on {len(model.keys):,} keys and {graph.num_kernels:,} kernels")
        try:
            solved = solve_packed(graph, progress=None, refuse_above=refuse_above)  # one step the net cannot cut: it overshoots by at most this solve (R04: 0.9 s on 79,000 kernels)
        except ConvergenceError:
            if refuse_above == math.inf:
                raise  # nothing looser to ask for
            # A model of very many steps (divine-roll-limits/large, #830: 2,917 keys whose certified error is 0.577 of the value): the bound is the
            # value lowered by whatever error the solver does certify (`PatternBound.lower`, 0 when it certifies none), a weaker bound and still a
            # lower one. Refusing it refused the whole target, where OR-33 wants a plan with its gap; the search's own figures then say how far it is.
            solved = solve_packed(graph, progress=None, refuse_above=math.inf)
        solved_at = time.perf_counter()
        phases["solve"] += solved_at - built
        n = len(model.keys)
        value = np.asarray(solved.value[: n + 1])  # the keys, and the sink last (a goal: 0)
        say(
            f"model {rounds}: {len(order):,} offers, {n:,} keys ({sum(model.expanded):,} expanded"
            + (f", {model.stats.ruined_keys:,} ruined keys held by one" if model.stats.ruined_keys else "")
            + f"), {model.stats.kernels:,} kernels, start value "
            f"{float(solved.value[0])!r} (model {built - mark:.1f} s, solve {solved_at - built:.1f} s)" + (f"; STOPPED: {model.stopped}" if model.stopped else "")
        )
        if model.stopped is not None or floors is None or not (outside or holders):  # every offer built at every key: nothing can join
            phase = "floors" if floors_stopped else "model" if model.stopped else "complete"
            return _bound(model, value, float(solved.error_bound), phases, began, order, floors, rounds, model.stopped, phase, tally, watched, _frozen(holders))
        try:
            needs, limits = _binding(graph, solved, model, floors, outside, holders, say)
        except FloorsStopped as reached:  # the model of this round is solved and stands; only the offers that would join are not known
            say(f"model {rounds}: the net was reached while the offers outside the model were examined ({reached.reason}); the model of this round stands")
            return _bound(model, value, float(solved.error_bound), phases, began, order, floors, rounds, reached.reason, "growth", tally, watched, _frozen(holders))
        if not needs:
            return _bound(model, value, float(solved.error_bound), phases, began, order, floors, rounds, None, "complete", tally, watched, _frozen(holders))
        more = [p for p in needs if p not in inside]
        slot = {p: j for j, p in enumerate(order)}
        spread = {slot[p]: keys for p, keys in needs.items() if p in inside}
        at = [needs[p] for p in more]
        kept = (model, value, float(solved.error_bound), list(order), _frozen(holders))
        for p, keys in needs.items():
            holders.setdefault(p, set()).update(keys)
        built = sum(len(keys) for keys in needs.values())
        names = ", ".join(f"{priced[p].label} (cost {priced[p].cost:.3g})" for p in more[:2]) + (", ..." if len(more) > 2 else "")
        named = ((OUTSIDE, "outside E"), (INSIDE, "inside E"), (OTHER, "other shape"), (UNOPENED, "unopened"), *((k, f"shape {shape_of(k)}") for k in floors.classes[len(CLASSES):]))
        said = ", ".join(f"{name} {limits[k]:.4g}" for k, name in named if limits.get(k) is not None)
        say(
            f"model {rounds}: the floor action is the cheapest at some key (largest model value there: {said}); {len(more):,} offers more join the model"
            + (f" and {len(spread):,} of its offers are built at more keys" if spread else "")
            + f", at {len({k for keys in needs.values() for k in keys}):,} keys that need them ({built:,} offers at a key): {names}"
        )
        adding = more
        order = [*order, *more]
        for net in watched:  # the next model holds these offers: how far the build is, for a net that lets a nearly done build finish
            net.grown(Growth(len(order), len(priced), first, len(kept[3])), net.used())


def _frozen(holders: dict[int, set[int]]) -> dict[int, frozenset[int]]:
    return {p: frozenset(keys) for p, keys in holders.items()}


def _bound(model, value, error, phases, began, order, floors, rounds, stopped, phase, tally: Tally | None = None, watched=(), narrow=None) -> PatternBound:
    solve = phases["solve"]
    return PatternBound(
        model, value, float(value[0]), error, time.perf_counter() - began - solve, solve, tuple(order), floors, stopped, phase, dict(phases), rounds,
        0 if tally is None else tally.done, None if tally is None else tally.cap, any(getattr(net, "late", False) for net in watched), narrow or {},
    )  # fmt: skip


def offers_floor(
    abstraction: Abstraction, start: CompressedState, priced: Sequence[PricedOffer], item, stop: Callable[[], str | None] | None = None,
    pieces: int | None = None,
) -> float | None:
    """The figure no plan of `priced` from `start` costs less than (after the start item), from the offers' floors alone (`OfferFloors`: the Wald
    floor `rho` when the start is outside the goal's set E, else 0), with no model built: what the rounds order the groups by once a plan is in
    hand (`_rounds.widen`, #1135). Its net is `stop` (the clock), and `pieces` (a run counted in states) its cap in pieces of work; None when a
    net ended it before the floors were worked out."""
    tally = None if pieces is None else Tally(pieces, _pieces_words, stop)
    try:
        floors = OfferFloors(abstraction, start, priced, item, stop if tally is None else tally, tally)
    except FloorsStopped:
        return None
    return floors.rho if floors.klass(start.flags, start.fractured, start.status, start.imprints) == OUTSIDE else 0.0


def _pieces_words(done: int, cap: int) -> str:
    """Why a build counted in pieces of work stopped (OR-13)."""
    return (
        f"it had done {done:,} pieces of work, its allowance being {cap:,} pieces of work, set from the run's states net (a piece is an action tried at one item of a kind, "
        "or the least cost an action can have worked out)"
    )


def _tip_floor(priced: Sequence[PricedOffer]) -> Callable[[PatternKey, bool], float | None]:
    """The floor action of a build without offers' floors: only a tip has one, at the cost of the cheapest offer (any action costs that or more)."""
    cheapest = min((p.cost for p in priced), default=0.0)
    return lambda _k, _key, expanded: None if expanded else cheapest


def _floor_of(
    floors: OfferFloors, outside: list[int], priced: Sequence[PricedOffer], holders: dict[int, set[int]] | None = None
) -> Callable[[int, PatternKey, bool], float | None]:
    """The floor action of a key: the least floor of the offers the model did not build there (those outside the model, and those of the model
    held at other keys only, #1325), or of all the offers when the key is a tip."""
    names = range(len(priced))
    table = {klass: (floors.floor(outside, klass), floors.floor(names, klass)) for klass in floors.classes}
    held = holders or {}
    # the offers held at some keys only, least floor first, per class: a key's floor action is the first of them it does not hold, when that is
    # below the floor of the offers outside
    ranked = {klass: sorted((floors.lower(p, klass), p) for p in held) for klass in floors.classes} if held else {}

    def floor(k: int, key: PatternKey, expanded: bool) -> float | None:
        klass = floors.klass(key.flags, key.fractured, key.status, key.held[IMPRINTS])
        if not expanded:
            cost = table[klass][1]
        else:
            cost = table[klass][0]
            for low, p in ranked.get(klass, ()):
                if low >= cost:
                    break
                if k not in held[p]:
                    cost = low
                    break
        return None if cost == float("inf") else cost

    return floor


def _binding(
    graph, solved, model: PatternModel, floors: OfferFloors, outside: list[int], holders: dict[int, set[int]] | None = None,
    say: Callable[[str], None] = lambda _text: None,
) -> tuple[dict[int, list[int]], dict[int, float | None]]:
    """The offers the model did not build at a key where the floor action is the cheapest and that could lower its value there, each with the
    numbers of those keys, the least floors first.

    At a key whose floor action is cheaper than every action of the model, the value is the floor and not the model's own; an offer the model did
    not build there (outside the model, or held at other keys only) whose floor there is not above the model's best could lower it. Only a key that
    the policy of the model reaches from the start, or has the start's shape (the classes of `_offer_floor` where the floors are strong), counts;
    when that policy takes the floor action nowhere, it is a policy of the model on all the offers, and the value of the start is the model's own
    (at most the exact value, and at least the value of a policy of the exact model); the keys the policy does not reach keep the value the floor
    action gives them, which is a lower bound all the same. Nothing is returned when the floor action is the cheapest nowhere.

    *Where an offer joins (#1325).* An offer is built at the keys that need it, not at every key: the model is a lower bound whatever offers it
    builds at each key, since the floor action of a key carries the least floor of every offer not built there (`_floor_of`, `PatternBound.holds`).
    Built at every key, the offers a class of another shape needed joined by the thousand where one key needed them (R24: 2,831 offers needed at
    1 key, built at 18,478; R04: 1,245 offers, 49 s a key), since every offer's floor in such a class is its price (`OfferFloors.lower`).
    """
    held = holders or {}
    value = np.asarray(solved.value, dtype=np.float64)
    n = graph.n
    contribution = graph.k_prob * value[graph.k_succ]
    expect = np.add.reduceat(contribution, graph.k_ptr[:-1]) if len(contribution) else np.zeros(0)
    q = graph.act_cost + expect[graph.act_kernel]
    owner = graph.action_state()
    real = graph.act_tag != FAKE
    best = np.full(n, np.inf)
    np.minimum.at(best, owner[real], q[real])
    fake = np.full(n, np.inf)
    np.minimum.at(fake, owner[~real], q[~real])
    binding = fake < best * (1.0 - BINDING)
    reached = np.zeros(n, dtype=bool)
    reached[policy_reach(graph, np.asarray(solved.action), 0)] = True  # a key the policy of the model reaches from the start can change the value of the start
    shaped = np.array([not isinstance(key, ChoiceNode) and floors.klass(key.flags, key.fractured, key.status, key.held[IMPRINTS]) in (INSIDE, OUTSIDE) for key in model.keys] + [False] * (n - len(model.keys)), dtype=bool)
    unreached = binding & ~(reached | shaped)  # binding keys of another shape the policy does not reach: some get the offers all the same (`_spread`)
    binding &= reached | shaped  # and so do the keys of the start's shape, where the floors are strong: the search goes there; a key of another shape (OTHER: the cost of an offer as its floor; SHAPED + S: rho_S, #973) is left to the search unless the policy reaches it
    if not binding[: len(model.keys)].any():
        return {}, dict.fromkeys(floors.classes)
    limit: dict[int, float | None] = dict.fromkeys(floors.classes)
    by_class: dict[int, list[int]] = {}
    for k in np.flatnonzero(binding[: len(model.keys)]).tolist():
        key = model.keys[k]
        if not model.expanded[k]:
            continue
        klass = floors.klass(key.flags, key.fractured, key.status, key.held[IMPRINTS])
        by_class.setdefault(klass, []).append(k)
    _spread(by_class, np.flatnonzero(unreached[: len(model.keys)]).tolist(), lambda k: fake[k] / best[k], model, floors, held)
    for klass, keys in by_class.items():
        limit[klass] = float(best[keys].max())
    keys_of = {klass: np.array(keys, dtype=np.int64) for klass, keys in by_class.items()}
    best_of = {klass: best[keys] for klass, keys in keys_of.items()}
    found: list[tuple[float, int]] = []
    needs: dict[int, list[int]] = {}
    candidates = [*outside, *held]
    examined = time.perf_counter()
    say(f"binding: examining {len(outside):,} offers outside the model and {len(held):,} held at some keys only")
    for position in candidates:  # a floor raised here is an exact chance: `needed` asks the net before each (`FloorsStopped`)
        low = floors.needed(position, limit)
        if low is None:
            continue
        where: list[int] = []
        for klass, keys in keys_of.items():  # the keys where its floor is not above the model's best: there it could lower the value
            where.extend(keys[floors.lower(position, klass) * (1 - SLACK) <= best_of[klass]].tolist())
        if position in held:
            where = [k for k in where if k not in held[position]]
        if where:
            found.append((low, position))
            needs[position] = where
    more = _doubled(needs, holders or {}, keys_of, candidates, floors, found)
    say(
        f"binding: {len(needs):,} of {len(candidates):,} offers are needed, at {len({k for keys in needs.values() for k in keys}):,} of {len(model.keys):,} keys"
        + (f"; {more:,} more offers at a key, as many as those keys held (`_doubled`)" if more else "")
        + f" ({time.perf_counter() - examined:.1f} s)"
    )
    found.sort()
    return {position: sorted(needs[position]) for _, position in found}, limit


def _spread(by_class: dict[int, list[int]], unreached: list[int], ratio, model: PatternModel, floors: OfferFloors, holders: dict[int, set[int]]) -> None:
    """Add to a class of another shape where the policy reaches a binding key as many more binding keys of that class as already hold offers
    built at some keys only, the most binding first (the least ratio of the floor action to the model's best), so the keys a class's offers are
    built at double each round it is found binding (#1325).

    The policy, moved off a key given offers, reaches the next binding key of its class in the next round: R24 crept a cent a round over one key
    at a time (64 rounds, start value 222.03 to 222.82); given at every binding key at once, 2,884 offers were built at all 18,469 keys, the join
    of the whole model again. Doubling, a class is found binding at most about log2 of its keys times in a row. Which keys hold an offer changes
    nothing of the bound's soundness (`_floor_of`): only how many rounds the growth takes."""
    if not unreached or not holders:
        return
    klass_of = lambda k: floors.klass(model.keys[k].flags, model.keys[k].fractured, model.keys[k].status, model.keys[k].held[IMPRINTS])  # noqa: E731
    wanted = {klass for klass in by_class if klass not in (INSIDE, OUTSIDE)}
    if not wanted:
        return
    holding: dict[int, int] = {}
    for k in set().union(*holders.values()):
        if (klass := klass_of(k)) in wanted:
            holding[klass] = holding.get(klass, 0) + 1
    spare: dict[int, list[tuple[float, int]]] = {}
    for k in unreached:
        if model.expanded[k] and (klass := klass_of(k)) in wanted and holding.get(klass):
            spare.setdefault(klass, []).append((float(ratio(k)), k))
    for klass, keys in spare.items():
        keys.sort()
        by_class[klass].extend(k for _, k in keys[: holding[klass]])


def _doubled(needs: dict[int, list[int]], holders: dict[int, set[int]], keys_of, candidates: list[int], floors: OfferFloors, found: list) -> int:
    """Give a key of another shape that needs offers at least as many as it already holds of those built at some keys only, the least floors
    first (#1325).

    The model's value at a key of another shape rises by cents as offers join, and every offer's floor there is its price (`OfferFloors.lower`):
    R24's thousands of fossil sets, priced a cent apart, joined three a round at one key, 325 rounds of a solve each with no end in sight. Given as
    many as it held, a key that keeps needing offers holds twice as many each time it is found binding, so it is found binding at most about
    log2 of the offers times, and it is given at most twice the offers it needs in the end. Which offers a key holds changes nothing of
    the bound's soundness (any set of offers built at a key is a lower bound there, `_floor_of`): only how many rounds the growth takes.
    Adds to `needs` and `found` in place; returns how many (offer, key) pairs were added."""
    if not holders:
        return 0
    held: dict[int, int] = {}
    for keys in holders.values():
        for k in keys:
            held[k] = held.get(k, 0) + 1
    given: dict[int, int] = {}
    for keys in needs.values():
        for k in keys:
            given[k] = given.get(k, 0) + 1
    added = 0
    asked = {p: set(keys) for p, keys in needs.items()}  # (a set: `needs[p]` may name thousands of keys)
    ranked: dict[int, list[tuple[float, int]]] = {}
    for klass, keys in keys_of.items():
        if klass in (INSIDE, OUTSIDE):  # the start's shape: the floors are strong and `needed` names the few offers that could lower a key's value
            continue  # (R24, doubled there too: 21 offers needed at 18,385 keys became 367,700 pairs, the whole join again in a few rounds)
        short = [k for k in keys.tolist() if 0 < given.get(k, 0) < held.get(k, 0)]
        if not short:
            continue
        if klass not in ranked:
            ranked[klass] = sorted((low, p) for p in candidates if (low := floors.lower(p, klass)) < math.inf)
        for k in short:
            want = held[k] - given[k]
            for low, p in ranked[klass]:
                if want == 0:
                    break
                if k in holders.get(p, ()) or k in asked.get(p, ()):
                    continue
                if p not in needs:
                    needs[p] = []
                    found.append((low, p))
                needs[p].append(k)
                asked.setdefault(p, set()).add(k)
                want -= 1
                added += 1
    return added


__all__ = ["PatternBound", "pack_pattern_model", "pattern_lower_bound", "pattern_offers"]
