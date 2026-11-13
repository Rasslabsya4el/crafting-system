"""Hinekora's Lock in the plan: its options at a state, the exact pruning, the second solve, the Lock line's N and the coarse refusal (ticket #296, B8-4).

The design is ADR-0054 to ADR-0057; the solver's side (`solver.Peek`, `solver.solve_peek`) is ADR-0054's and ticket #293's. This module builds
what the planner gives the solver and decides when it is worth building at all.

**The Lock is a planner kind on by default** (`LOCK_KIND`): a target whose `actions:` does not name it has none (`lock_wanted`). Its price is the
price file's (`prices.lock_price`); with none the Lock is dropped (ADR-0056) and `N` is still found, since it does not need the price.

**At a state `s` the Peek is a `Site`** (`PlanSites`):

* the **options** are the previewable offers (`Action.previewable` is not `no`, ADR-0055) of the FULL list of priced offers, before twins, the
  equal-kernel merge and the bound pruning (ADR-0031's amendment: two currencies with one kernel are two independent previews, and an offer the Lock-free
  optimum never needs can still win as one more), **one per currency item** (`Action.currency_item`): the cheapest that the game allows at `s`. The
  legality filters that are no pruning stay: an offer the game refuses, a corrupting offer that ADR-0036 offers only at the states that meet every other
  requirement, a quality offer that ADR-0029 offers only at the last step;
* the **fallback** is every plain action of `s` that is not previewable (the bench, Harvest, the restart, ...) and the cheapest legal burn of the
  start item (`actions.burns_at`, `prices.cheapest_burn`, ADR-0056). The planner refuses a target that names quality, sockets, implicits or an
  enchantment (`make_plan`), so a burn changes nothing the state keeps: it leads back to `s`, a cycle through the Lock that `solve_peek` handles.
  A corrupted state takes no Lock (`hinekora_lock.refused_on`), and a jewel has no burn.

**Exact pruning** (ADR-0054): the Lock is offered at `s` only if `L + c_min < V_noLock(s)`. A Peek costs at least `L` plus the cheapest of its options
and fallback actions (values are at least 0), and adding the Lock can only lower a value, so a state that fails the test never profits. `c_min` here is
the cheapest action of the whole plan (every priced offer and the burn): it is at most the cheapest action of any state (and of any member of a block, the
optimistic offer of the coarse level), so the test stays exact; at the Lock's price (hundreds of Divine) the difference is nothing. `V_noLock` may be
any upper bound of the Lock-free value (the pessimistic values of a coarse level, the values of a pruned solve): the test only gets weaker. A state with
no Lock-free value is offered the Lock (sound, only slower).

**The second solve** runs only when some state keeps the Lock: `solve_peek` on the model of the plain offers (twins merged, no bound pruning, which is
proved for the Lock-free model only) with a Peek at every state that keeps it. `solve_peek` solves that model without the Lock first and starts its policy
iteration from that proper policy. When the Lock is pruned everywhere nothing is solved again and the plan is the Lock-free plan, bit for bit.

**N** (ADR-0057) is the largest gain `g(s) = V(s) - E[min(min_a(c_a + V(o_a)), F(s))]` over the states the Lock-free plan visits: the Peek at price 0
with the Lock-free values, one sorted-tail sweep (`solver.peek_backup`) per state. Below `N` one Lock at that state already lowers the plan's cost. The
states are taken in falling `V(s)`, and `g(s) <= V(s) - c_min` closes the search once no state left can beat the best gain (branch and bound); a plan
that visits more than `GAIN_STATES` states stops there and `n_exact` is False (each gain found is still a true "would pay below", so the line stays true).

**The coarse level** (ADR-0023, ADR-0054) has no Peek: a query whose Lock survives the pruning tested against the pessimistic values of the coarse level
has no approximate answer (`CoarseLockError` says why, and that `actions:` can drop the Lock); one whose Lock is pruned everywhere keeps its level and
its bounds, unchanged.
"""

import math
import time
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.actions import BurnKeeps, HinekoraLock, NotApplicableError, OutOfScopeError, Previewable, burns_at
from crafting_system.items import Item
from crafting_system.prices import PriceFile, cheapest_burn
from crafting_system.solver import Action, Outcome, Peek, PeekNode, Solution, peek_backup, solve_peek

from ._offers import LOCK_KIND, BuyStartItem, PricedOffer
from ._prune import corrupting_offer_pruned, solver_actions

__all__ = [
    "LOCK_KIND",
    "LOCK_LABEL",
    "CoarseLockError",
    "Foresight",
    "LockModel",
    "PlanSites",
    "Site",
    "Status",
    "coarse_check",
    "lock_gain",
    "lock_wanted",
    "survives",
]

LOCK_LABEL = HinekoraLock().label()
GAIN_STATES = 200  # the most visited states whose gain is computed for N (each needs the kernels of its options)


class Status(StrEnum):
    """What the plan says about the Lock (ADR-0057): one of these, never silence."""

    USED = "used"  # the plan takes the Lock at some step
    NOT_WORTH = "not worth it"  # the Lock is offered and priced, and no plan step takes it
    NO_OPTION = "no previewable action"  # no state the plan visits has a previewable option
    REFUSED = "refused"  # the start item takes no Lock (corrupted)
    SWITCHED_OFF = "switched off by the target"  # the target's `actions:` does not name it
    NO_PRICE = "no price"  # the price file has none: the Lock is dropped, N is still found
    COARSE = "coarse"  # an approximate answer whose pruning removed the Lock everywhere: no N (the exact values it needs do not exist)
    STOPPED = "not checked: the time or memory limit was reached"  # the run's net stopped the check (#825, OR-33): the plan is the one without the Lock


@dataclass(frozen=True)
class Foresight:
    """What a plan found about Hinekora's Lock; the report's Lock line and the `foresight` JSON object read it (ticket #298).

    `price` is one Lock in Chaos (None: no price). `n` is the Lock line's N in Chaos (None where it is not found: switched off, refused, coarse, or no
    option on any visited state); `n_exact` is False when the plan visits more states than `GAIN_STATES` and the search stopped before it closed.
    `best_state` is the state of the largest gain and `by_item_text` the options there that preview by the Lock's item text only. `kept` and `pruned`
    count the states with a Lock-free value where the Lock survives the exact pruning and where it is removed. `lock_free_mean` and `saving` are the mean
    still to pay from the start without the Lock and what the Lock saves of it (None when the Lock is not used). `seconds` is the time this stage took
    (the gains, the pruning and the second solve).
    """

    status: Status
    price: float | None = None
    n: float | None = None
    n_exact: bool = True
    best_state: Hashable | None = None
    by_item_text: tuple[str, ...] = ()
    kept: int = 0
    pruned: int = 0
    lock_free_mean: float | None = None
    saving: float | None = None
    seconds: float = 0.0


class CoarseLockError(ValueError):
    """An approximate answer refused because Hinekora's Lock survives the exact pruning on the coarse bounds (ADR-0054)."""


def lock_wanted(actions: Sequence[str] | None) -> bool:
    """Whether a target's `actions:` lets the plan use the Lock: it is on by default and dropped by an `actions:` that does not name it."""
    return actions is None or LOCK_KIND in actions


def survives(lock: float, c_min: float, value: float) -> bool:
    """The exact pruning test of ADR-0054: the Lock is offered at a state only if `L + c_min < V_noLock` there."""
    return lock + c_min < value


@dataclass(frozen=True)
class Site:
    """The Peek of one state: the options (one per currency item), the fallback actions and the options previewed by item text only."""

    options: tuple[Action, ...]
    fallback: tuple[Action, ...]
    by_item_text: tuple[str, ...] = ()


def _value(action: Action, values: Mapping[Hashable, float]) -> float:
    """`cost + E[V(next)]` of a plain action under `values` (a state without a value is infinite)."""
    total = sum(weight for _, weight in action.outcomes)
    terms = [action.cost]
    for state, weight in action.outcomes:
        if weight:
            terms.append(values.get(state, math.inf) * (weight / total))
    for state in action.extra_inputs:
        terms.append(values.get(state, math.inf))
    return math.fsum(terms)


def gain(site: Site, value: float, values: Mapping[Hashable, float]) -> float:
    """`g(s) = V(s) - E[min(min_a(c_a + V(o_a)), F(s))]`: what one Lock at price 0 saves at a state, with the Lock-free values (ADR-0057)."""
    if not site.options or not math.isfinite(value):
        return -math.inf
    limit = min((_value(action, values) for action in site.fallback), default=math.inf)
    pairs = [[(option.cost + values.get(state, math.inf), weight) for state, weight in option.outcomes if weight] for option in site.options]
    return value - min(limit, peek_backup(pairs, limit))


@dataclass(frozen=True)
class Gain:
    """The Lock line's N over the visited states: the largest gain, where, and whether the search closed."""

    n: float | None
    state: Hashable | None
    by_item_text: tuple[str, ...]
    exact: bool
    any_option: bool


def lock_gain(
    states: Iterable[Hashable],
    values: Mapping[Hashable, float],
    sites: Callable[[Hashable], Site | None],
    c_min: float,
    *,
    limit: int = GAIN_STATES,
) -> Gain:
    """N: the largest `gain` over `states` (the states the Lock-free plan visits), by branch and bound on `g(s) <= V(s) - c_min`.

    The states are taken in falling value (ties by their order in `states`); the search stops when the next cannot beat the best gain found, or after
    `limit` states (then `exact` is False). `n` is None when no state examined has an option.
    """
    ranked = sorted(
        ((values[state], position, state) for position, state in enumerate(states) if math.isfinite(values.get(state, math.inf))),
        key=lambda entry: (-entry[0], entry[1]),
    )
    best, where, text, any_option, exact = -math.inf, None, (), False, True
    for count, (value, _, state) in enumerate(ranked):
        if value - c_min <= best:
            break
        if count >= limit:
            exact = False
            break
        site = sites(state)
        if site is None or not site.options:
            continue
        any_option = True
        found = gain(site, value, values)
        if found > best:
            best, where, text = found, state, site.by_item_text
    return Gain(best if any_option else None, where, text if any_option else (), exact, any_option)


class LockModel:
    """A plan's model with a Peek at every state that keeps the Lock: the base model's actions, and the Lock's Peek where `keep(state)` and the state
    has an option. The Peek of a state is built once and given again on every round of `solve_peek`."""

    def __init__(self, base, sites: Callable[[Hashable], Site | None], lock: float, keep: Callable[[Hashable], bool]) -> None:
        self._base = base
        self._sites = sites
        self._lock = lock
        self._keep = keep
        self._peeks: dict[Hashable, Peek | None] = {}
        prefetch = getattr(base, "prefetch", None)
        if prefetch is not None:
            self.prefetch = prefetch

    def is_goal(self, state: Hashable) -> bool:
        return self._base.is_goal(state)

    def actions(self, state: Hashable) -> list:
        plain = list(self._base.actions(state))
        if state not in self._peeks:
            site = self._sites(state) if self._keep(state) else None
            self._peeks[state] = Peek(LOCK_LABEL, self._lock, site.options, site.fallback) if site is not None and site.options else None
        peek = self._peeks[state]
        return plain if peek is None else [*plain, peek]

    @property
    def offered(self) -> int:
        """The states at which the Peek was offered."""
        return sum(peek is not None for peek in self._peeks.values())


def visited_states(policy: Mapping, start: Hashable, is_goal: Callable[[Hashable], bool]) -> list[Hashable]:
    """The non-goal states a policy reaches from `start`, first met first. A packed policy's keys are already those (`PackedPolicy`)."""
    if hasattr(policy, "walked"):
        return list(policy)
    found: dict[Hashable, None] = {}
    queue = [start]
    while queue:
        state = queue.pop()
        if state in found or is_goal(state) or state not in policy:
            continue
        found[state] = None
        queue.extend(next_state for next_state, weight in policy[state].outcomes if weight)
    return list(found)


def takes_the_lock(policy: Mapping, start: Hashable, is_goal: Callable[[Hashable], bool]) -> bool:
    """Whether the policy takes the Lock at a state it reaches from the start."""
    found: set = set()
    queue = [start]
    while queue:
        state = queue.pop()
        if state in found or (not isinstance(state, PeekNode) and is_goal(state)) or state not in policy:
            continue
        found.add(state)
        action = policy[state]
        if action.label == LOCK_LABEL:
            return True
        queue.extend(next_state for next_state, weight in action.outcomes if weight)
    return False


class PlanSites:
    """The Peek of a compressed state of a plan (see the module text): options from the full list of priced offers, one per currency item, and the
    non-previewable plain actions of the state with the burn as the fallback. Each state's site is built once."""

    def __init__(
        self,
        abstraction: Abstraction,
        offers: Iterable[PricedOffer],
        plain_offers: Iterable[PricedOffer],
        start: CompressedState,
        burn: BurnPrice | None,
        *,
        prune_corrupting: bool = True,
        cache: dict | None = None,
    ) -> None:
        data = abstraction.data
        self._abstraction = abstraction
        self._start = start
        self._plain = tuple(plain_offers)
        self._burn = burn
        self._prune_corrupting = prune_corrupting
        self._cache = cache
        previewable = [
            (priced.cost, position, priced)
            for position, priced in enumerate(offers)
            if not isinstance(priced.offer.action, BuyStartItem) and _previewable(priced, data) is not Previewable.NO
        ]
        self._options = tuple(priced for _, _, priced in sorted(previewable, key=lambda entry: entry[:2]))  # cheapest first: the option of its item
        self._previewable_labels = frozenset(priced.label for priced in self._options)
        self._sites: dict[CompressedState, Site | None] = {}

    @property
    def previewable_labels(self) -> frozenset[str]:
        return self._previewable_labels

    def __call__(self, state: CompressedState) -> Site | None:
        if state not in self._sites:
            self._sites[state] = self._build(state)
        return self._sites[state]

    def _build(self, state: CompressedState) -> Site | None:
        from ._plan import offer_action  # _plan imports this module

        abstraction, data = self._abstraction, self._abstraction.data
        if abstraction.is_goal(state) or state.flags.corrupted:  # a corrupted item takes no Lock (hinekora_lock.refused_on)
            return None
        options: dict[str, Action] = {}
        by_text: list[str] = []
        for priced in self._options:
            action = priced.offer.action
            item = action.currency_item(data) or priced.label
            if item in options:
                continue  # one option per currency item: the cheapest the game allows here
            if self._prune_corrupting and corrupting_offer_pruned(abstraction, priced, state):
                continue
            if abstraction.quality_offer_pruned(state, action):
                continue
            built = None if self._cache is None else self._cache.get((state, priced.label, priced.cost))
            if built is None:
                try:
                    built = offer_action(abstraction, priced, state, self._start)
                except (NotApplicableError, OutOfScopeError):
                    continue
                if self._cache is not None:
                    self._cache[(state, priced.label, priced.cost)] = built
            options[item] = built
            if action.previewable(data) is Previewable.BY_ITEM_TEXT:
                by_text.append(priced.label)
        if not options:
            return None
        plain = solver_actions(abstraction, self._plain, state, self._start, prune_corrupting=self._prune_corrupting, cache=self._cache)
        fallback = [action for action in plain if action.label not in self._previewable_labels]
        if self._burn is not None:
            fallback.append(Action(self._burn.label, self._burn.cost, (Outcome(state, 1),)))  # a burn changes nothing the state keeps (module text)
        return Site(tuple(options.values()), tuple(fallback), tuple(by_text))


def _previewable(priced: PricedOffer, data) -> Previewable:
    previewable = getattr(priced.offer.action, "previewable", None)
    return Previewable.NO if previewable is None else previewable(data)


@dataclass(frozen=True)
class BurnPrice:
    """The burn of a plan's Peeks: its label and the price of one use; at each state it is the action that leads back to the state."""

    label: str
    cost: float


def plan_burn(data, item: Item, abstraction: Abstraction, prices: PriceFile, price_source: str = "both") -> BurnPrice | None:
    """The burn of the plan's Peeks: the cheapest legal burn of the start item, or None.

    Its legality is read on the start item: a burn depends on the class, the corruption (a corrupted state takes no Lock), the implicits (refused
    where the state keeps them, `BurnKeeps.implicits`) and the quality (which the planner never keeps: it refuses a target that names it).
    """
    if abstraction.tracks_quality:
        raise ValueError("the Lock's burn is built for states that keep no quality; the planner refuses a target that names it")
    keeps = BurnKeeps(quality=False, implicits=abstraction.tracks_implicits, enchantment=False)
    found = cheapest_burn(burns_at(data, item, keeps), data, prices, price_source)
    return None if found is None else BurnPrice(found.burn.label(data), found.cost)


def cheapest_cost(offers: Iterable[PricedOffer], burn: BurnPrice | None) -> float:
    """`c_min`: the cheapest action of the plan, a lower bound of the cheapest option or fallback action of every state (module text)."""
    return min((*(priced.cost for priced in offers), *((burn.cost,) if burn is not None else ())), default=0.0)


def coarse_check(values: Mapping[Hashable, float], lock: float | None, c_min: float, wanted: bool) -> Foresight:
    """The Lock at the coarse level (ADR-0054): `Status.COARSE` when the pruning on the pessimistic `values` removes it from every block, else
    `CoarseLockError`. A Lock switched off or without a price is said as such and refuses nothing."""
    if not wanted:
        return Foresight(Status.SWITCHED_OFF, lock)
    if lock is None:
        return Foresight(Status.NO_PRICE)
    kept = sum(survives(lock, c_min, value) for value in values.values())
    if kept:
        raise CoarseLockError(
            f"no approximate answer: Hinekora's Lock could pay at {kept:,} of the coarse states (one Lock costs {lock:,.0f} Chaos, less than the "
            "pessimistic cost still to pay there), and an approximate answer cannot weigh a Lock. Drop the Lock with the target's `actions:` "
            "(name the kinds to use, without `hinekora-lock`) to get an approximate answer without it, or let the exact search run"
        )
    return Foresight(Status.COARSE, lock, pruned=len(values))


def foresee(
    abstraction: Abstraction,
    start: CompressedState,
    first: Solution,
    sites: PlanSites,
    second_solve: Callable[[], tuple[object, PlanSites]],
    *,
    lock: float | None,
    c_min: float,
    is_goal: Callable[[Hashable], bool],
) -> tuple[Foresight, Solution | None]:
    """The Lock of an exact plan that wants it: its status, N, the pruning count and, when the Lock survives somewhere and the plan takes it, the
    second solution.

    `first` is the Lock-free solution, `sites` the Peeks the gains for N read, `lock` the Lock's price (None: no price). `second_solve` gives the
    solver's model of the plain offers that the second solve runs on and the Peeks of that solve (whose fallback reads those offers); it is asked only
    when some state keeps the Lock. The second solution is returned only when its policy takes the Lock from the start; otherwise None, and the plan
    stays the Lock-free one, bit for bit.
    """
    began = time.perf_counter()
    if start.flags.corrupted:  # every state of a corrupted start is corrupted: the item takes no Lock (hinekora_lock.refused_on)
        return Foresight(Status.REFUSED, lock), None
    values = first.values
    visited = visited_states(first.policy, start, is_goal)
    found = lock_gain(visited, values, sites, c_min)

    def done(status: Status, **more) -> tuple[Foresight, Solution | None]:
        solution = more.pop("solution", None)
        return Foresight(
            status, lock, found.n, found.exact, found.state, found.by_item_text, seconds=time.perf_counter() - began, **more
        ), solution

    if lock is None:
        return done(Status.NO_PRICE)
    states = [state for state in values if not is_goal(state)]
    kept = sum(survives(lock, c_min, values[state]) and not state.flags.corrupted for state in states)
    pruned = len(states) - kept
    if not kept:
        return done(Status.NO_OPTION if not found.any_option else Status.NOT_WORTH, pruned=pruned)

    def keep(state: Hashable) -> bool:
        return survives(lock, c_min, values.get(state, math.inf))

    plain_model, second_sites = second_solve()
    second = solve_peek(LockModel(plain_model, second_sites, lock, keep), [start])
    mean = values[start]
    if takes_the_lock(second.policy, start, is_goal) and second.values[start] < mean:
        return done(Status.USED, kept=kept, pruned=pruned, lock_free_mean=mean, saving=mean - second.values[start], solution=second)
    return done(Status.NOT_WORTH if found.any_option else Status.NO_OPTION, kept=kept, pruned=pruned)
