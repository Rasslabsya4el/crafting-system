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

The search ends in one of three ways, and `EnvelopeInfo` says which (ticket #826, OR-32, OR-39, OR-33): *exact* (the plan is proved the cheapest); *at a
proved gap* (`within`: the plan is proved to cost at most that share more than the cheapest); *stopped by a net* (`stopped`: the
best plan found, with the gap that was proved). In all three the mean shown is the mean of the plan returned: the graph the search ended with is
solved again here, and that solve, not the search's upper figure, is the mean shown. Of an exact search it is certified to the solver's 1e-6 (the
"exact mean" of OR-32) or the plan is refused. Of the other two it is certified to `EnvelopeInfo.mean_error`, which a plan of very many steps can
leave above 1e-6 (#867), and nothing printed of such a plan calls its mean exact: the gap and the interval are taken from `certified_upper`, the
mean with its certified error added, against `lower`, the bound with its error taken off, so the gap stated holds every error its figures carry
(the reading of OR-32 of 2026-11-14 in `docs/owner-rules.md`).
"""

import dataclasses
import math
import time
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass

import numpy as np

from crafting_system import parallel
from crafting_system.abstraction import PRUNED_CORRUPTING, PRUNED_QUALITY, Abstraction, CompressedState, integer_weights
from crafting_system.abstraction._pattern import SINK, Pattern
from crafting_system.actions import NotApplicableError, OutOfScopeError

from . import _limits
from ._envelope import ACCEPT_BOUND, BoundError, Net, NoPolicy, Refused, Search, Standing, figure_error, resident_mb
from ._limits import Limit, claim
from ._offer_floor import OTHER, OUTSIDE
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
        self.floors = bound.floors
        self.in_model = frozenset(bound.positions)  # the offers the model holds; the others have a floor and no abstract action (`_pattern_bound`)
        self.tip = [not built for built in model.expanded] if model.expanded else [False] * len(model.keys)  # keys the build did not reach
        values = np.asarray(bound.value, dtype=np.float64) * (1.0 - bound.error_bound)  # lowered by what the solver cannot certify
        self.values = values
        expected: list[float] = []  # the lowered value of each pushed kernel of the model, in expectation
        sink = len(values) - 1  # the successor `SINK` (-1) of a float kernel is the model's last state, the goal that costs nothing (`_pattern_bound`, `close_state`)
        for successors, weights in model.kernels:
            total = sum(weights)
            chance = np.array([w / total for w in weights])  # int / int is exact to one rounding, whatever the size
            expected.append(float(chance @ values[[sink if key == SINK else key for key in successors]]))
        self.lowest: list[dict[int, float]] = []  # key -> offer position -> the least lowered backup of its abstract actions there
        for row in model.actions:
            found: dict[int, float] = {}
            for index, kernel in row:
                position = bound.positions[index]
                q = self.offers[position].cost + expected[kernel]
                if position not in found or q < found[position]:
                    found[position] = q
            self.lowest.append(found)
        self.restart = next((p for p, priced in enumerate(self.offers) if isinstance(priced.offer.action, BuyStartItem)), None)
        self.start_lower = float(values[0])  # key 0 is the start's
        self.keys_missing = 0
        self.bound_error = float(bound.error_bound)  # what the values below are lowered by: the search's consistency guard allows for it above 1e-6 (#867)

    def is_goal(self, state: CompressedState) -> bool:
        return self.ab.is_goal(state)

    def _key(self, state: CompressedState) -> int | None:
        return self.index.get(self.pattern.key(state))

    def _klass(self, state: CompressedState) -> int:
        return OTHER if self.floors is None else self.floors.klass(state.flags, state.fractured, state.status)

    def lower(self, state: CompressedState) -> float:
        k = self._key(state)
        if k is None:
            self.keys_missing += 1  # the model never reached this key: the floor of the offers' class (0 outside it) is a bound that needs no model
            return self.floors.rho if self._klass(state) == OUTSIDE else 0.0
        found = float(self.values[k])
        return max(found, self.floors.rho) if self._klass(state) == OUTSIDE else found

    def candidates(self, state: CompressedState) -> list[tuple[float, int]]:
        k = self._key(state)
        found = None if k is None or self.tip[k] else self.lowest[k]
        klass = self._klass(state)
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
                low = priced.cost + self.start_lower
            elif found is None or position not in self.in_model:
                low = priced.cost  # no abstract action to read: the offer's own cost, or its floor below
            elif position in found:
                low = found[position]
            else:
                continue  # the model holds the offer and no member of the key can take it
            if self.floors is not None:
                low = max(low, self.floors.lower(position, klass))  # a floor of the same class as the state's: the bound of the state (`lower`) never exceeds the least of these
                if low == math.inf:
                    continue  # refused at this state (an unopened listing takes the draw alone)
            out.append((low, position))
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

    def prime(self, state: CompressedState, positions: Sequence[int]) -> int:
        """Make the exact distributions of these offers at `state` in the process pool (ticket #250, #626); returns how many it made (0 with one worker, no `fork`, or all made)."""
        return self.ab.prime(
            [(state, self.offers[position].offer.action) for position in positions if not isinstance(self.offers[position].offer.action, BuyStartItem)]
        )

    def release(self) -> None:
        self.ab._prepared_by.clear()


SEARCH_PER_BUILD = 3.0  # the search after a build takes at least this many times the build's time: measured 3.7 (R04: build 99 s, search 364-510 s) and 6.2 (R14: 37 s, 231-238 s), research note 2026-11-13-planning-speed, section 1; rounded down


def build_stop(net: Net | None, began: float) -> Callable[[], str | None] | None:
    """The net of the bound's build (OR-12): a quarter of the time net, and the memory net as it is (the state net counts the search's states).

    `began` is the clock reading when `envelope_result` started. The build asks it between two pieces of its work (two offers, or before a solve of
    its model); it returns the reason once one is reached. The plan comes from the search after the build, so the build keeps room for it: it stops
    when the time left is at most `SEARCH_PER_BUILD` times the time it has taken, which is the same as a fixed share of a quarter of the time it was
    given: a hand-set stop-and-say-so net under OR-12, set from the search/build ratio on R04 (3.7) and R14 (6.2) and checked on R08, not a measure
    of this build. A build that ends earlier leaves the search all the rest. This replaced `BUILD_SHARE = 0.5` (#825): on
    R08 at the prices of 2026-11-10 a build that left the search 103 s gave a plan of 33,755 Chaos where a search given 266 s gave 2,236, on the same
    lower figure (heavy runs 43358114571, 43358085172).
    """
    if net is None or (net.seconds is None and net.states is None and net.memory_mb is None):
        return None

    def stop() -> str | None:
        now = time.perf_counter()
        if net.seconds is not None:
            spent = now - began
            left = net.seconds - spent
            if left <= 0.0:
                return f"the time limit of {net.seconds:g} seconds was reached"
            if left <= SEARCH_PER_BUILD * spent:
                return (
                    f"stopped after {spent:.0f} of the {net.seconds:g} seconds of the time limit, to leave the rest for the search for the plan, "
                    f"which takes several times as long as this count"
                )
        if net.memory_mb is not None:
            used = resident_mb()
            if used is not None and used >= net.memory_mb:
                return f"the process held {used:,.0f} MB, the limit is {net.memory_mb:,.0f} MB"
        return None

    return stop


def route_incumbent(route, data) -> Callable[[CompressedState], list[str]]:
    """A given route as the incumbent of the search: at a state, the labels of the offers its matching rules name, in order.

    The search realizes the first that the game allows, so a route that says `skip_refused` falls through to its next rule as `evaluate_route` does;
    where none matches or none applies the incumbent restarts (the "completed route", `cli/_route.py`). A label the search does not offer (a twin
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
    upper: float  # U: the plan returned costs this much on average (the mean shown; certified to `mean_error` of itself)
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
    bound_stopped: str | None = None  # why the bound's build ended before it was complete (a net); None for a complete model
    bound_expanded: int = 0  # keys the build expanded (the others were tips with a floor)
    bound_offers: int = 0  # offers the model was built on (the rest are carried by their floors, `_pattern_bound`)
    bound_rounds: int = 1
    within: float | None = None  # the gap setting, when the search ended because the plan was proved within it of the cheapest (OR-32); then `stopped` is None
    restarts: bool = True  # whether the plan of a search that is not exact buys the start item again wherever the search had not looked (False: a given start, whose plan closed)
    first_plan: int = 0  # actions built along the first plan's chain, before the first round
    upper_refused: int = 0  # rounds in which the plan in hand could not be solved to a certified cost, so the stop at the gap waited (#769)
    upper_seconds: float = 0.0
    held: bool = False  # a net's stop kept an earlier plan, because the plan in hand could not be solved to a certified cost
    mean_error: float = 0.0  # the certified relative error of `upper`, the mean shown (the final solve's bound): above 1e-6 only for a plan of very many steps (#867)
    proved_upper: float | None = None  # the search's own certified upper figure of the plan returned (its solve's value with its error added), when it is not exact: what its stop compared


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
    guard: bool = True,
    item=None,
    gap: float = 0.0,
    gap_after: float | None = None,
    watch: Callable[[Standing], None] | None = None,
) -> PackedResult:
    """Search the graph of `offers` from `start` by the envelope search and solve what it expanded; `info["envelope"]` is an `EnvelopeInfo`.

    `gap` and `gap_after` are the stop at a proved gap (OR-32, OR-39, `_envelope`): once `gap_after` seconds of this call have passed (the bound's build
    counts; the planner passes 0, the stop applies whatever the time), the search ends when its plan is proved to cost at most `gap` more than the
    cheapest; `gap` 0 or `gap_after` None is the exact search.
    `watch` is told where the search stands after the first plan and after each round (`_envelope.Standing`: the best plan's cost so far and the
    figure no plan can cost less than).

    Raises `OutOfScopeError` when the bound cannot be built for this abstraction (a goal with a roll limit, an action that rerolls values, an unveil
    offer, imprints: #507), `NoPolicy` when no policy reaches the goal, or the net stopped the search before one closed and the start is given, and
    `BoundError` when the bound is shown not to be a consistent lower bound as the search looks further (a state's bound above its offers', or the bound
    of the root falling from one round to the next: `_envelope`, "A guard for the bound"; `guard=False` turns that refusal off, for the tests that plant a
    wrong bound and check that the comparison with the full walk catches what the guard would have refused).
    """
    from . import _packed

    say = progress or _packed.PROGRESS or (lambda _text: None)
    try:
        with parallel.memory_net(net.memory_mb if net is not None else None):  # the pool's workers are watched by the memory net too (#626, OR-12)
            return _envelope_run(abstraction, start, offers, prune_corrupting, incumbent, net, bound, tolerance, say, guard, item, gap, gap_after, watch)
    finally:  # said on a refusal too
        if (reason := getattr(abstraction, "prime_stopped", None)) is not None:
            say(f"the side-by-side work was stopped by the memory net ({reason}); the rest was made one at a time")


def _envelope_run(abstraction, start, offers, prune_corrupting, incumbent, net, bound, tolerance, say, guard, item, gap, gap_after, watch) -> PackedResult:
    """The body of `envelope_result`, under the run's memory net."""
    began = time.perf_counter()
    if bound is None:
        bound = pattern_lower_bound(
            abstraction, start, offers, progress=say, item=item, stop=build_stop(net, began), refuse_above=figure_error(gap, gap_after)
        )  # fmt: skip
    built = time.perf_counter()
    expanded = sum(bound.model.expanded) if bound.model.expanded else len(bound.model.keys)
    say(
        f"bound built: {bound.model.stats.keys:,} keys ({expanded:,} expanded), {len(bound.positions):,} of {len(offers):,} offers in the model, start value "
        f"{bound.start_value!r} ({built - began:.0f} s)" + ("" if bound.complete else f"; STOPPED in the {bound.phase} phase: {bound.stopped}")
    )
    if net is not None and net.seconds is not None:
        net = dataclasses.replace(net, seconds=max(net.seconds - (built - began), 0.0))  # the search has what the build left of the time
    if gap_after is not None:
        gap_after = max(gap_after - (built - began), 0.0)  # the aim is of the whole plan: the build's time counts toward it
    problem = CraftingProblem(abstraction, start, offers, bound, prune_corrupting=prune_corrupting)
    where = {priced.label: position for position, priced in enumerate(offers)}
    positions = None if incumbent is None else (lambda state: [where[label] for label in incumbent(state) if label in where])
    search = Search(problem, net=net, incumbent=positions, progress=say, tolerance=tolerance, guard=guard, gap=gap, gap_after=gap_after, watch=watch)
    try:
        result = search.run()
    except NoPolicy as refusal:
        if bound.complete:
            raise
        raise NoPolicy(f"{refusal}. {build_note(bound, expanded, len(offers))}") from refusal
    walked = Walked(result.graph, result.states, result.index, tuple(offers), time.perf_counter() - built)
    # the mean shown: of an exact answer to the solver's 1e-6; of a plan proved within a gap, or one a net stopped, to the error the search took its
    # figures at, and the limit says so when it is above 1e-6 (`mean_error_text`, #867): OR-33 asks for a plan with its gap, not a refusal
    packed = solve_walked(
        abstraction, start, walked, tolerance=tolerance, progress=say, refuse_above=None if result.exact else figure_error(gap, gap_after)
    )  # fmt: skip
    mean = float(packed.solution.values[start])
    stats = result.stats
    packed.info["envelope"] = EnvelopeInfo(
        result.exact, result.stopped, result.lower, mean, stats.rounds, stats.touched, stats.expanded, stats.realized, stats.candidates,
        problem.keys_missing, incumbent is not None, stats.first_upper, bound.model.stats.keys, bound.build_seconds + bound.solve_seconds,
        time.perf_counter() - began, stats.peak_mb, bound.stopped, expanded, len(bound.positions), bound.rounds,
        result.within, result.restarts, stats.seeded, stats.upper_refused, stats.upper_seconds, result.held, float(packed.solution.error_bound),
        None if result.exact else result.upper,
    )  # fmt: skip
    return packed


BUILD_PHASES = {  # the phase of a stopped build, as a player reads it
    "floors": "working out the cheapest possible cost of each action",
    "model": "counting the kinds of item the crafting can reach",
    "growth": "adding the actions that matter to that count",
    "solve": "solving that count",
}


def build_note(bound: PatternBound, expanded: int, offers: int) -> str:
    """What a refusal says about the count of the cheapest possible cost when the net stopped it before it was finished (OR-13): the phase and the sizes it reached."""
    phase = BUILD_PHASES.get(bound.phase, bound.phase)
    return (
        f"The count of the cheapest possible cost was stopped ({bound.stopped}) while {phase}: it had worked through {expanded:,} of the "
        f"{bound.model.stats.keys:,} kinds of item it had found and counted {len(bound.positions):,} of the {offers:,} actions offered"
    )


def envelope_limits(info: EnvelopeInfo) -> tuple[Limit, ...]:
    """The limit that says which cut ran and what it still guarantees (OR-13)."""
    if info.exact:
        return (
            Limit(
                _limits.SOLVE,
                "The search expanded only what could matter",
                f"it looked at the actions of {info.expanded:,} of the {info.touched:,} states it found and built {info.realized:,} of the "
                f"{info.candidates:,} actions offered at them: an action it did not build costs more, even at its best case, than the one it kept",
                **claim(
                    "the methods offered",
                    "The cut is exact: nothing was left out for being unlikely or by a tolerance, and the mean cost is that of the best plan.",
                    # the answer is approximate although this search is exact when another start option's plan is only proved within a gap (#826)
                    "This search left nothing out for being unlikely or by a tolerance, and the mean cost is that of the best plan from this start item; "
                    "another start item that was compared has a plan proved only to within its gap.",
                ),
            ),
        )
    if info.within is not None:
        waited = (
            f"; in {info.upper_refused:,} of its rounds the plan in hand could not be worked out to a certified cost, and the search went on until one could"
            if info.upper_refused
            else ""
        )
        return (
            Limit(
                _limits.SOLVE,
                "The search stopped once the plan was proved close to the cheapest",
                f"the search stopped by itself, after {info.rounds:,} rounds and {info.expanded:,} states looked at, "
                f"as soon as its plan was proved to cost at most {certificate_gap_text(info.within)} more than the cheapest possible (the gap this run allows)"
                + (", buying the start item again wherever it had not looked" if info.restarts else "")
                + waited,
                f"The plan is {_limits.WITHIN_GAP}: it costs {info.upper:,.2f} Chaos on average after the start item, and that figure is the average of "
                "the plan shown itself, not an estimate of the cheapest. " + mean_error_text(info) + certificate_text(info),
            ),
        )
    return (
        Limit(
            _limits.SOLVE,
            "The search was stopped",
            f"{info.stopped}, after {info.rounds:,} rounds and {info.expanded:,} states looked at"
            + ("; the plan restarts from the start item wherever the search had not looked" if info.restarts else "")
            + ("; the cost of the last plan it had could not be worked out to a certified figure, so the plan shown is the one before it" if info.held else ""),
            f"The plan is not shown to be the best: it costs {info.upper:,.2f} Chaos on average after the start item, the average of the plan shown itself. "
            + mean_error_text(info)
            + certificate_text(info),
        ),
    )


def mean_error_text(info: EnvelopeInfo) -> str:
    """What is said of the mean when the solver certifies it only to more than the 1e-6 of an exact answer (#867, OR-13): empty otherwise."""
    if not info.mean_error > ACCEPT_BOUND:
        return ""
    return (
        f"The plan takes so many steps that its average cost is worked out only to within {info.mean_error:.2g} of itself "
        f"({info.upper * info.mean_error:,.2f} Chaos either way); the gap stated allows for that. "
    )


def certified_upper(info: EnvelopeInfo) -> float:
    """The upper figure of the gap and of the interval: the most the plan returned costs on average, every error of the figure included (#867).

    Of an exact search it is the mean (certified to the solver's 1e-6: OR-32's exact mean). Otherwise it is the mean with its certified error added,
    `upper (1 + mean_error)`, or the search's own certified figure of the same plan (`proved_upper`) when that is lower: each is at least the
    plan's true average cost, so the lower of the two is. With `lower`, which the search already took with its solve's error off, the gap
    `certified_upper / lower - 1` is proved whatever the errors are, and at a stop at a gap it is at most `within` (the search stopped on
    `proved_upper <= (1 + within) lower`).
    """
    if info.exact:
        return info.upper
    own = info.upper * (1.0 + info.mean_error)
    return own if info.proved_upper is None else min(own, info.proved_upper)


def certificate_gap(info: EnvelopeInfo) -> float | None:
    """The most the stop can have cost, `U / LB - 1` with `U` the `certified_upper`: how far the plan can be above the best possible cost. None when
    `LB` is not above zero."""
    upper = certified_upper(info)
    if not info.lower > 0.0 or not math.isfinite(upper):
        return None
    return max(upper / info.lower - 1.0, 0.0)


def certificate_figures(lower: float, upper: float) -> tuple[str, str]:
    """`LB` and `U` as printed: two decimals, and more only when two decimals would print them the same although `LB < U` (a nearly closed search)."""
    for places in range(2, 13):
        low, high = f"{lower:,.{places}f}", f"{upper:,.{places}f}"
        if low != high or not lower < upper:
            return low, high
    return low, high


def certificate_gap_text(gap: float) -> str:
    """The gap as printed, always a percent: two decimals from 0.1% up, below that two significant digits ("0.000014%"), never a rounded 0."""
    if gap == 0.0:
        return "0%"
    percent = gap * 100.0
    if percent >= 0.1:
        return f"{percent:.2f}%"
    return f"{percent:.{1 - math.floor(math.log10(percent))}f}%"


def certificate_text(info: EnvelopeInfo) -> str:
    """What a search that did not end exact still guarantees, next to the point answer (OR-13, OR-32): `[LB, U]`, the gap, the bound used and what it bounds.

    The plan and its mean stay the answer; the interval only says how far the stop could be from the best possible cost, and its upper end is
    `certified_upper` (the mean with its certified error: the same figure to the cent unless the plan takes very many steps, #867). `LB` is a
    lower bound of the whole graph: the optimistic model of the crafted pattern (the walk-free bound), raised by the actions the search looked at,
    and never above the best cost of any plan over every state the item can reach, expanded or not. It holds because the bound is sound by
    construction (#497: the optimistic model costs no more than the real game at every key); the guard of the search (`BoundError`) checks the
    bound only at the states it expanded, and at the tips only when a lower solve fails, so the text never says the guard verified `LB`.
    """
    gap = certificate_gap(info)
    upper = certified_upper(info)
    lower = min(max(info.lower, 0.0), upper)  # a rounding of LB just above U never prints [x, y] with x above y
    low, high = certificate_figures(lower, upper)
    head = (
        f"The best possible cost lies in [{low}, {high}] Chaos after the start item: no way of crafting this item, including the ones the search "
        f"did not look at, costs less than {low} on average. "
    )
    gap_text = (
        f"The plan costs at most {certificate_gap_text(gap)} more than the best possible cost. "
        if gap is not None
        else "No gap can be stated: the lower figure is not above zero. "
    )
    bound = (
        f"{low} comes from a simplified count of the item that tracks only its rarity, how many mods it has on each side, and its fractured and "
        "crafted mods, which never prices a step above its true cost; the search raised it with the steps it did look at. It holds because of how "
        "that count is built, not because it was checked on every item the crafting can reach: the search checks it only on the ones it looked at."
    )
    cut = (
        f" The count itself was stopped before it was finished ({info.bound_stopped}): it was built for {info.bound_expanded:,} of the {info.bound_keys:,} "
        "kinds of item it had found, and it counts the rest at the least their steps can cost, so the lower figure is lower than a finished count would give."
        if info.bound_stopped
        else ""
    )
    return head + gap_text + bound + cut


__all__ = [
    "BoundError", "CraftingProblem", "EnvelopeInfo", "NoPolicy", "Net", "Standing", "certificate_figures", "certificate_gap", "certificate_gap_text",
    "certificate_text", "certified_upper", "envelope_limits", "envelope_result", "route_incumbent",
]  # fmt: skip
