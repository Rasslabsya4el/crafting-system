"""From a target to a solved policy with its risk: targets -> prices -> abstraction -> solver -> risk.

`make_plan` is the whole pipeline of the R12 slice and does no printing and no file work: the
caller loads the game data, the target and the prices and decides what to do with the `Plan`.
Nothing here reads the clock except `time.perf_counter` around the solve and the risk run, which
are reported (the budget DP of `risk.evaluate` is pure Python and can be slow on large policies).

Under a `budget` with a gap (1% by default) the default search (`solver="auto"`) is the envelope search wherever its bound can be built and no
given route is judged: it stops by itself once its plan is proved within the budget's gap of the cheapest, whatever the time (OR-32, OR-39, #826),
and the run's net, when the budget has one, guards it (OR-33, OR-40); the `Plan` has no `approximation` (its mean is the exact mean of the plan
shown) and `Plan.search` says how the search ended. Where that search cannot take the target, `auto` walks every item exactly, as with no budget,
to the run's net (#926). Without a `budget`, or with a gap of 0, the plan is always exact. The forecast of ADR-0023 (`_decide.decide`) and its ladder of coarse levels (`_approx`), which answer with an `approximation`
(a pessimistic `solution` on blocks and no `risk`), are retired: only a walk asked for by name (`solver="packed"`, `"object"`) under a budget
still reaches them, until #928 deletes them.
"""

import itertools
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction

from crafting_system import parallel
from crafting_system.budget import NO_PLAN, STATES, Binding, Budget, BudgetExceeded, Clock, checkpoint, running, stage
from crafting_system.budget import active as budget_active
from crafting_system.abstraction import Abstraction, CompressedState, Gap, Goal, integer_weights, pattern_refusal, refusal_causes
from crafting_system.actions import BLOCKING, Axis, OutOfScopeError, Reading, kinds, unopened_listing
from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.prices import PriceFile, lock_price, planned_price
from crafting_system.prices.price_source import DEFAULT_PRICE_SOURCE
from crafting_system.risk import IntervalReport, RiskReport, _regen, evaluate, has_inputs, is_free_cost, solve_readings
from crafting_system.solver import MAIN, Acquisition, Action, ConvergenceError, Outcome, PeekNode, Solution, solve
from crafting_system.prices.query_compare import other_item
from crafting_system.targets import KOfN, Requirement, StartBuyError, StartKind, Target, buy_spec_of, shared_name_refusal

from ._approx import Approximation, climb
from ._axes import axis_what
from ._bound_prune import Pruned, merge_twins, solve_pruned, starting_offers
from ._decide import Rates, decide
from ._finish import FinishRefused, PlanFinish, finish_limits, plan_finish, split_names, without_finish_kinds
from ._foresight import CoarseLockError, Foresight, PlanSites, Status as LockStatus, cheapest_cost, coarse_check, foresee, lock_wanted, plan_burn
from . import _limits
from ._limits import Limit, approximate_limits, budget_limit, claim, kind_title, model_gap_limits, pruning_limits, risk_limits, twins_limit, unpriced_limits, with_limits
from ._offers import RESTART, BuyStartItem, Offer, PricedOffer, free_action_cost, listing_draw, offers_for, price_offers, split_usable, takes_inputs, unusable_limits
from . import _packed
from ._envelope import Net, NoPolicy, Standing
from ._envelope_plan import BoundError, EnvelopeInfo, envelope_limits, envelope_result
from ._packed import SOLVERS, PackedResult, packed_result
from ._presenter import presenter_limits
from ._prune import chosen_offers, solver_actions
from ._start_types import StartChoice

VIEW_FROM_STATES = 1_000  # a packed plan whose policy visits more item states than this is shown by its lumped chain (ticket #70)
MERGE_EQUAL = True  # offers with an equal kernel at a state: only the cheapest (exact; a test turns it off for the reference)
PRUNE_CORRUPTING = True  # corrupting offers of a target that asks are left out of the states that cannot reach its goal (exact, ADR-0036; a test turns it off)
PRUNE_BOUND = True  # twins and offers proved not needed are left out of the solve (exact; a test turns it off for the reference)
MIN_OFFERS_TO_PRUNE = 40  # fewer priced offers than this are solved whole
FORECAST_SOLVERS = ("packed", "object")  # a walk asked for by name: the only way left to the retired forecast and its ladder under a budget (#926)


class PlanError(ValueError):
    """The target cannot be planned: a price is missing or no policy reaches the goal."""


@dataclass(frozen=True)
class StrandSetting:
    """Whether a run considers Memory Strands, and why (ADR-0040).

    Strands are off unless the start item has some or the query turns them on (the setting `memory_strands` of
    `crafting.toml`, or `--strands`); `why` is the reason in plain words and goes into the text report.
    """

    on: bool
    why: str


STRANDS_OFF = StrandSetting(False, "the start item has none and the query does not ask for them")


def strand_setting(start_item: Item, *, asked: bool = False) -> StrandSetting:
    """The strand setting of a run: on when the start item has strands (it turns the setting on by itself) or the query `asked`."""
    if start_item.memory_strands >= 1:
        return StrandSetting(True, f"the start item has {start_item.memory_strands} Memory Strands")
    if asked:
        return StrandSetting(True, "asked for by `--strands` or in the planner settings")
    return STRANDS_OFF


GIVEN_SOURCE = "given: its cost is not counted, and the plan never buys another"  # what a given start item reads as (OR-6, #505)


@dataclass(frozen=True)
class StartPrice:
    """What the start item costs to get, in Chaos, and where the number came from.

    A bought start item (OR-6) has a price above 0 and a restart. A given one has `given` set, costs 0 by definition, and has no restart:
    whether the item can be bought again is this flag, never the number (#505).
    """

    name: str | None
    chaos: float
    source: str
    taken_for: str | None = None  # "price taken for a wider item (...)": the stored search is not the item the key names (#474, OR-7)
    given: bool = False
    mark: str | None = None  # a thin market's price is marked (OR-8): "old price, read on <date>, ..." or "few offers: ..."; None for an unmarked price

    def __post_init__(self) -> None:
        if self.given and self.chaos != 0:
            raise ValueError(f"a given start item costs nothing, got {self.chaos!r} Chaos")
        if not self.given and not (self.chaos > 0 and self.chaos != float("inf")):
            raise ValueError(f"a bought start item has a price above 0 Chaos, got {self.chaos!r}")

    @property
    def bought(self) -> bool:
        return not self.given


def given_price() -> StartPrice:
    """The cost of a given start item: not counted (OR-6)."""
    return StartPrice(None, 0.0, GIVEN_SOURCE, given=True)


@dataclass(frozen=True)
class DonorPlan:
    """The plan of a target whose offers take donors (a recombinator, ticket #225, ADR-0022, ADR-0062): the product it was solved on.

    A product state is `("in", want, state)`: the item wanted (`MAIN` for the target, else the compressed donor it must become) and the
    compressed state it is in now (`solver.Acquisition`). `solution` is the plan reading's solve over the product, `start` the target's own
    process at the start state, `acquisition` the product model of the plan reading (its actions carry their donors as product states).
    `Plan.solution` is the target's own process read off it (`main_view`); the risk is measured on the whole product, donors included.
    """

    acquisition: Acquisition
    start: tuple
    solution: Solution[tuple]

    @property
    def processes(self) -> tuple[CompressedState, ...]:
        """The donors the plan makes, each a compressed want, in the order the solve met them (the target's own process left out)."""
        found: dict[CompressedState, None] = {}
        for _tag, want, _state in self.solution.policy:
            if want is not MAIN:
                found.setdefault(want, None)
        return tuple(found)


def main_view(solution: Solution[tuple]) -> Solution[CompressedState]:
    """The target's own process of a product solution, on compressed states (ticket #225).

    Its values are those of the product, so a state's value counts the donors still to make; an action keeps its label and its own cost and
    leaves its donors out (`extra_inputs` empty): what a donor costs is in the value, and how it is made is `DonorPlan`'s.
    """
    values = {state: value for (_tag, want, state), value in solution.values.items() if want is MAIN}
    policy = {}
    for (_tag, want, state), action in solution.policy.items():
        if want is MAIN:
            policy[state] = replace(action, outcomes=tuple(Outcome(t[2], w) for t, w in action.outcomes), extra_inputs=())
    return Solution(values, policy, solution.error_bound)


@dataclass(frozen=True)
class Plan:
    """Everything the report prints: the solved policy, its risk and the inputs it was built from."""

    target: Target
    abstraction: Abstraction
    leaf_labels: tuple[str, ...]
    prices: PriceFile
    start: CompressedState
    start_price: StartPrice
    offers: tuple[PricedOffer, ...]
    limits: tuple[Limit, ...]  # everything the answer leaves out, each with what it still guarantees (OR-13, `_limits`)
    solution: Solution[CompressedState]
    risk: RiskReport | None
    solve_seconds: float
    risk_seconds: float
    approximation: Approximation | None = None  # set when the answer is approximate: `start`, `solution` and `policy` are then of blocks
    pruned: Pruned | None = None  # what the bound pruning did, None when the plan was solved whole
    starts: StartChoice | None = None  # the start options compared and refused (ADR-0059, `_starts.plan_with_starts`); None when none was compared
    packed: PackedResult | None = None  # set when the packed solver solved it (ticket #374): what its risk is evaluated on
    readings: IntervalReport[CompressedState, Reading] | None = None  # set when an offer reads a rule axis that is not planned: the solve of every reading (#589)
    foresight: Foresight | None = None  # what the plan found about Hinekora's Lock (ticket #296, ADR-0057); None for a plan that was not solved
    finish: PlanFinish | None = None  # the socket finish added to every goal state (ticket #231, ADR-0045); None for a target that names no sockets
    donors: "DonorPlan | None" = None  # set when an offer takes donors (ticket #225): the product of the main item and its donors' processes

    def __post_init__(self) -> None:
        # one place decides what a guarantee of cheapness says: an approximate answer reaches the cheapest only to within its stated gap (OR-13),
        # and so does a search that ended at a proved gap or at a net (OR-32, OR-33; #826)
        search = self.search
        if self.approximation is not None or (search is not None and not search.exact):
            object.__setattr__(self, "limits", approximate_limits(self.limits))

    @property
    def search(self) -> EnvelopeInfo | None:
        """How the envelope search ended, when it made this plan: exact, at a proved gap (`within`) or at a net (`stopped`), with the plan's exact
        mean `upper` and the figure no plan can cost less than, `lower` (both after the start item). None for a plan of another path."""
        return self.packed.info.get("envelope") if self.packed is not None else None

    @property
    def simulated_start(self) -> Item:
        """The item a simulated craft starts from: the unopened listing when the start is a bought item whose mods are drawn (ADR-0064), else the target's own start item."""
        listing = unopened_listing(self.abstraction.data, self.target.start_item) if self.start.flags.unopened else None
        return listing or self.target.start_item

    @property
    def policy(self) -> Mapping[CompressedState, Action[CompressedState]]:
        return self.solution.policy

    @property
    def view_policy(self) -> Mapping[CompressedState, Action[CompressedState]]:
        """The policy the report shows: `policy` itself, or for a packed plan whose policy visits more than `VIEW_FROM_STATES` item
        states, its lumped chain on one shown state per block (item states that pay alike and lead on alike are one; the numbers
        are exact). The simulator (`--verify`) always runs the whole `policy`."""
        if self.packed is not None and self.packed.view is not None and len(self.policy) > VIEW_FROM_STATES:
            return self.packed.view
        return self.policy

    @property
    def lumped(self) -> bool:
        """Whether `view_policy` is the lumped chain, not the policy itself."""
        return self.view_policy is not self.policy

    def is_goal(self, state: CompressedState) -> bool:
        return not isinstance(state, PeekNode) and self.abstraction.is_goal(state)  # a Lock's pseudo-state (ADR-0054) is no goal

    def offer_of(self, action: Action[CompressedState]) -> PricedOffer:
        """The priced offer a policy action stands for (the action label is the offer label); `restart` is one."""
        return next(priced for priced in self.offers if priced.label == action.label)

    @property
    def mean_remaining(self) -> float:
        """The solver's expected cost of the mods from the start, without the price of the start item (the socket finish is `finish_value`)."""
        return self.solution.values[self.start]

    @property
    def finish_value(self) -> float:
        """What the socket finish adds to every goal state (ADR-0045): its mean from the start item's sockets, 0 for a target with no sockets.

        One value for every goal state (no mod action changes sockets; Orb of Binding, which gives a goal a second one, is ticket #232), so the plan
        of the mods is the cheapest with the finish too and only its mean grows (`_finish.py`)."""
        return 0.0 if self.finish is None else self.finish.value

    def value_of(self, state: CompressedState) -> float:
        """The expected cost from `state` to the finished item: the solver's value of the mods plus the finish, which every goal state adds."""
        return self.solution.values[state] + self.finish_value

    @property
    def total_mean(self) -> float:
        """The expected cost of the whole craft from the start, the mods and the socket finish, without the price of the start item."""
        return self.value_of(self.start)


class _Model:
    """The solver's view of the compressed states under the offered actions.

    `restart` (buying the start item again, ADR-0011) is one of the offers when the start item has a
    price; it is an action of every state but the start itself, where it would change nothing.
    """

    def __init__(
        self,
        abstraction: Abstraction,
        start: CompressedState,
        offers: Iterable[PricedOffer],
        cache: dict | None = None,
        merge_equal: bool | None = None,
    ) -> None:
        self.abstraction = abstraction
        self.start = start
        self.offers = tuple(offers)
        self.merge_equal = MERGE_EQUAL if merge_equal is None else merge_equal
        self.cache = cache  # (state, label, cost) -> solver action, shared by the solves of one plan
        self.chosen: dict[CompressedState, list[PricedOffer]] = {}  # the offers chosen at the queued states (`prefetch` made the choice)

    def is_goal(self, state: CompressedState) -> bool:
        return self.abstraction.is_goal(state)

    def prefetch(self, states: Sequence[CompressedState]) -> None:
        """Compute, side by side in a process pool, the label distributions that the queued `states` will need (ticket #250).

        `actions` then finds them in the abstraction's cache. Nothing is built here and nothing changes in the answer; with
        `CRAFTING_WORKERS=1` this does nothing.
        """
        if parallel.worker_count() < 2:
            return
        self.chosen.clear()  # the states of the last window have all been taken
        requests = []
        for state in states:
            if self.abstraction.is_goal(state):
                continue
            chosen = self.chosen[state] = chosen_offers(
                self.abstraction, self.offers, state, self.start, merge_equal=self.merge_equal, prune_corrupting=PRUNE_CORRUPTING
            )
            for priced in chosen:
                if self.cache is None or (state, priced.label, priced.cost) not in self.cache:
                    if not isinstance(priced.offer.action, BuyStartItem):
                        requests.append((state, priced.offer.action))
        self.abstraction.prime(requests)

    def actions(self, state: CompressedState) -> list[Action[CompressedState]]:
        checkpoint()  # the run's net (#825): every walk of the object solver, the bound pruning's and the Lock's among them, stops here between two states
        chosen = self.chosen.pop(state, None)
        return solver_actions(
            self.abstraction, self.offers, state, self.start,
            merge_equal=self.merge_equal, prune_corrupting=PRUNE_CORRUPTING, cache=self.cache, chosen=chosen,
        )  # fmt: skip


def offer_action(
    abstraction: Abstraction, priced: PricedOffer, state: CompressedState, start: CompressedState | None = None
) -> Action[CompressedState]:
    """The solver's action for one priced offer used in `state`: its cost and the integer weights of the kernel.

    `restart` ends in `start` for certain. Raises `NotApplicableError` when the game refuses the action there
    or `OutOfScopeError` when no admitted rule covers it.
    """
    if isinstance(priced.offer.action, BuyStartItem):
        if start is None:
            raise ValueError("`restart` needs the start state")
        return Action(priced.label, priced.cost, (Outcome(start, 1),))
    weights = integer_weights(abstraction.kernel(state, priced.offer.action))
    return Action(priced.label, priced.cost, tuple(Outcome(s, w) for s, w in weights.items()))


def leaf_labels(target: Target) -> tuple[str, ...]:
    """A short English name for each requirement leaf, in the order of `Goal.leaves`."""
    labels: list[str] = []

    def walk(node: Requirement | KOfN) -> None:
        if isinstance(node, KOfN):
            for member in node.of:
                walk(member)
            return
        name = node.stat if node.stat is not None else f"family {node.family}"
        if len(node.mod_ids) == 1:
            name += f", mod {next(iter(node.mod_ids))}"
        limits = []
        if node.min_tier is not None:
            limits.append(f"tier {node.min_tier} or better")
        elif node.any_tier:
            limits.append("any tier")
        elif node.tier_ok is not None:
            limits.append("top tier")  # OR-1: no tier written, so the top tier of the ladder at the item level
        if node.min_roll is not None and any(roll is not None for roll in node.min_roll):
            limits.append("roll at least " + "/".join("any" if r is None else str(r) for r in node.min_roll))
        if node.not_crafted:
            limits.append("not crafted")
        labels.append(f"{name} ({', '.join(limits)})" if limits else name)

    for requirement in target.requirements:
        walk(requirement)
    return tuple(labels)


def resolve_start_price(
    data: GameData, target: Target, prices: PriceFile, override: float | None, price_source: str = DEFAULT_PRICE_SOURCE
) -> StartPrice:
    """The cost of the start item (OR-6): a given one costs nothing and is never bought again; a bought one has a price.

    A target that says `start: given` has no price to set: `--start-price` on it is refused. A bought one is a run's own number
    (`--start-price`, above 0), else the price file (hand overrides already in it) under the key computed from the target
    (`start_price_key`); a key that is not in the file is an error that names it: the cost of the whole craft would be wrong without it.
    A poe.ninja price of a name that several bases share is refused with the words that say why (`shared_name_refusal`).
    The price is read by `planned_price` under the profile's `price_source`: a thin market is priced by OR-8 and the price carries its mark.
    """
    if target.start is not StartKind.BOUGHT:
        if override is not None:
            raise PlanError(
                "the target says its start item is given, so it has no price and `--start-price` has nothing to set; "
                "write `start: bought` in the target if the item is bought"
            )
        return given_price()
    try:
        spec = buy_spec_of(data, target)
        name = spec.name
    except StartBuyError as error:
        if override is not None:  # the run gives its own number, so the key is only a label
            return StartPrice(None, _override(override), "given on the command line")
        raise PlanError(f"the start item of the target cannot be searched: {error}") from error
    if override is not None:
        return StartPrice(name, _override(override), "given on the command line")
    planned = planned_price(prices, name, price_source)  # OR-8: a thin market is priced, with its mark
    if planned is None:
        raise PlanError(
            f"no price for the start item {name!r}. A bought start item must have a price. Price it on the trade site with the "
            "`trade` command, write a hand price for it in your price overrides, or give it with --start-price"
        )
    entry = planned.entry
    refusal = shared_name_refusal(data, target.base_id, entry.source, f"the start item {name!r}")
    if refusal is not None:  # a poe.ninja line has no base id: for a name that several bases share it prices none of them (#471)
        raise PlanError(refusal)
    stored = (entry.detail or {}).get("query")
    return StartPrice(name, entry.chaos, entry.source, other_item(spec, stored) if isinstance(stored, dict) else None, mark=planned.mark)


def _override(override: float) -> float:
    if not override > 0 or override == float("inf"):
        raise PlanError(f"the start price must be a number of Chaos above 0, got {override!r}")
    return float(override)


def make_plan(
    data: GameData,
    target: Target,
    prices: PriceFile,
    *,
    start_price: float | None = None,
    offers: Iterable[Offer] | None = None,
    budget: float | Budget | None = None,
    rates: Rates | None = None,
    strands: bool = False,
    solve_it: bool = True,
    start_price_of: StartPrice | None = None,
    price_source: str = DEFAULT_PRICE_SOURCE,
    solver: str = "auto",
    with_risk: bool = True,
    incumbent: Callable[[CompressedState], Sequence[str]] | None = None,
    net: Net | None = None,
    judges_route: bool = False,
    watch: Callable[[Standing], None] | None = None,
) -> Plan:
    """Solve the target and measure the risk of the policy, under one budget of time and memory (`crafting_system.budget`, #825).

    Under a budget the envelope search stops by itself once its plan is proved to cost at most the budget's `gap` more than the cheapest, whatever
    the time (OR-32, OR-39, #826; a number of seconds is a budget with the default gap); with no budget, `Budget.unlimited()` or a gap of 0 the
    proof is exact. `watch` is told
    where that search stands, from its first executable plan on and after each round (`_envelope.Standing`: the best plan's cost so far and the
    figure no plan can cost less than), so a caller can show a plan while the proof goes on.

    `budget` is the run's `Budget` (OR-33: the aim and the stop-and-say-so net of time and memory, `Budget.default()`), or a number of seconds
    (the aim alone, with the default gap and no net: the stop at the proved gap applies, and the retired forecast of ADR-0023 reads the aim for
    a walk asked for by name), or None (no aim and no net: every stage runs to its end, as a test of the
    exact answer or a measurement needs). `net` is the older way to give the net (its time, memory and states), and is folded into the budget.
    Every stage runs on the one clock of the run (a plan inside a run that already has a clock, a start option or a reading, shares it), and a
    stage that a limit stopped is listed in one limit of the answer (`_limits.budget_limit`, #378). A stop before any plan closed is a `PlanError`
    that says where it stopped ("no plan found yet", OR-33); a stop after one did keeps it and says so. The rest is `_make_plan`'s text.
    """
    plan_budget: Budget | None = as_budget(budget, net)
    owns = budget_active() is None and plan_budget is not None
    with running(plan_budget.start() if plan_budget is not None else None) as clock:
        try:
            plan = _make_plan(
                data, target, prices, start_price=start_price, offers=offers, aim=None if plan_budget is None else plan_budget.aim_seconds, rates=rates,
                strands=strands, solve_it=solve_it, start_price_of=start_price_of, price_source=price_source, solver=solver, with_risk=with_risk,
                incumbent=incumbent, clock=clock, judges_route=judges_route, watch=watch,
            )  # fmt: skip
        except BudgetExceeded as stop:  # a stage met the net before any plan closed (a stage that has one keeps it and does not raise): OR-33
            if clock is not None:
                clock.bind(stop.binding)  # a stop a forked worker met was bound on its own copy of the clock
            raise PlanError(stopped_refusal(clock, stop.binding)) from None
    return with_bindings(plan, clock) if owns else plan


def as_budget(budget: float | Budget | None, net: Net | None = None) -> Budget | None:
    """The run's `Budget` from `make_plan`'s arguments: a `Budget` as it is, a number as the aim alone (no net), and `net`'s figures as the net."""
    if isinstance(budget, Budget):
        found: Budget | None = budget
    elif budget is not None:
        found = Budget(aim_seconds=float(budget), seconds=None, memory_mb=None)
    else:
        found = None
    if net is None:
        return found
    base = found if found is not None else Budget.unlimited()
    return replace(
        base,
        seconds=net.seconds if net.seconds is not None else base.seconds,
        memory_mb=net.memory_mb if net.memory_mb is not None else base.memory_mb,
        states=net.states if net.states is not None else base.states,
    )  # a figure the net leaves out is the budget's


def with_bindings(plan: Plan, clock: Clock | None) -> Plan:
    """`plan` with the one limit that lists what bound in the run (#378), when something did."""
    found = budget_limit(clock.bindings) if clock is not None else None
    return plan if found is None else replace(plan, limits=(*plan.limits, found))


SEARCH_STAGE = "the search for the cheapest plan"
APPROXIMATE_STAGE = "the search for a plan within the stated gap of the cheapest"
PRUNED_STAGE = "the search for the cheapest plan, first on a smaller set of actions"
WALK_STAGE = "the walk of every item the actions can reach"
READINGS_STAGE = "the plan made once for each reading of a rule the sources leave open"
LOCK_STAGE = "the check of Hinekora's Lock"
LOCK_KEPT = "the plan is the best one without the Lock; whether the Lock saves anything was not checked"
SEARCH_KEPT = "the best plan found so far is kept, with the figure below which no plan can cost"
RISK_STAGE = "the work on the cost figures (the median cost and the cost 9 runs in 10 stay under)"
RISK_KEPT = "the figures of the coarser step already worked out are kept, or none when no step was"


def search_net(clock: Clock | None) -> Net | None:
    """The envelope search's net from the run's clock: the time left, and the memory and state nets as they are; None when the run has no net."""
    if clock is None:
        return None
    given: Budget = clock.budget
    if given.seconds is None and given.memory_mb is None and given.states is None:
        return None
    return Net(seconds=clock.left(), states=given.states, memory_mb=given.memory_mb)


def search_gap(clock: Clock | None) -> tuple[float, float | None]:
    """The envelope search's stop at a proved gap from the run's budget (OR-32 as narrowed by OR-39): the budget's gap, applying from the first
    round, whatever the time (the aim is what a plan aims at, not the switch between two kinds of answer). `(0, None)`, the exact search, for a
    run with no budget or a gap of 0 (`Budget.unlimited()`)."""
    if clock is None or not clock.budget.gap > 0.0:
        return 0.0, None
    return clock.budget.gap, 0.0


def bind_search(clock: Clock | None, info: EnvelopeInfo) -> None:
    """Record on the clock the limit that stopped the envelope search or its bound's build, when one did (OR-13: the plan says which bound).

    A search that ended at a proved gap met no limit: its own limit says how it ended (`envelope_limits`)."""
    ended = info.exact or info.within is not None  # the search ended by itself, not at a net
    if clock is None or (ended and info.bound_stopped is None):
        return
    if not ended:
        what = SEARCH_KEPT
    elif info.exact:
        what = "the cheapest possible cost was worked out only in part; the plan is still the cheapest"
    else:
        what = "the cheapest possible cost was worked out only in part; the plan is still proved within the stated gap of the cheapest"
    found = clock.over(SEARCH_STAGE, what)
    if found is None:  # the net the search met is no longer met now (the memory fell when its graph was let go): say the one it names
        given = clock.budget
        if given.states is not None and info.touched >= given.states:
            found = Binding(SEARCH_STAGE, STATES, given.states, info.touched, what)
        elif given.memory_mb is not None and info.peak_mb is not None and info.peak_mb >= given.memory_mb:
            found = Binding(SEARCH_STAGE, "memory", given.memory_mb, info.peak_mb, what)
        else:
            found = Binding(SEARCH_STAGE, "time", given.seconds if given.seconds is not None else 0.0, clock.elapsed(), what)
    clock.bind(found)


def stopped_refusal(clock: Clock | None, binding: Binding) -> str:
    """The `PlanError` of a run its net stopped before any plan closed (OR-33): how long it ran and where it stopped."""
    spent = f" after {clock.elapsed():,.0f} s" if clock is not None else ""
    return f"stopped{spent}: {binding.words()}"


def _make_plan(
    data: GameData,
    target: Target,
    prices: PriceFile,
    *,
    start_price: float | None,
    offers: Iterable[Offer] | None,
    aim: float | None,
    rates: Rates | None,
    strands: bool,
    solve_it: bool,
    start_price_of: StartPrice | None,
    price_source: str,
    solver: str,
    with_risk: bool,
    incumbent: Callable[[CompressedState], Sequence[str]] | None,
    clock: Clock | None,
    judges_route: bool,
    watch: Callable[[Standing], None] | None = None,
) -> Plan:
    """Solve the target and measure the risk of the policy.

    `start_price` is the cost of the start item for this run (it wins over the price file);
    `offers` default to `offers_for` the target. Raises `PlanError` when the target has `implicits` or
    `quality` (the planner ignores them until B2), when no offer has a price or no policy reaches the
    goal, and what the layers below raise for a bad input.

    A target that names sockets (ADR-0045, ticket #231) is planned in two parts: the mods as for the same target without sockets, and the socket
    finish solved on its own from the start item's sockets (`_finish.plan_finish`), whose value every goal state adds (`Plan.finish`,
    `Plan.total_mean`). Its refusals (`sockets: any`, a corrupted goal, a mod action that changes sockets, a finish no offered action completes)
    are `PlanError`s too.

    Remove Crafted Mods is kept only when a priced bench craft is, or the start item holds a crafted
    mod: otherwise no crafted mod can ever exist and tracking the junk slots for it would only grow
    the state space. A bought start item is offered again as `restart` from every state; a given one never is (OR-6).

    `aim` (seconds, the budget's aim) is read by nothing on `auto`'s way (#926). For a walk asked for by name (`solver="packed"`,
    `"object"`) it still turns on the retired decision of ADR-0023 (until #928): when
    the forecast of the exact run is longer, the answer is approximate within the tolerance if some coarse level reaches it, and `PlanError`
    says so when none exists and the exact run is not offered; `rates` injects the seconds per kernel outcome and per
    solved edge instead of measuring them. None (the default) always solves exactly. With `solve_it` False nothing is
    solved: the plan holds the offers, the abstraction and the start, an empty policy and an infinite value, so that a
    given route can be read and played on concrete items (`_route_sim`) when the graph is too large to solve (R04, R14).
    `strands` is the setting `memory_strands` of the query (ADR-0040): with it off and no strands on the start item the
    plan does not consider strands, as before; with either on, `PlanError` says the planner cannot plan with them yet
    (tickets of batch B5). `price_source` is the profile setting (`ninja`, `trade`, `both`) that `planned_price` respects. `start_price_of` is the price of the start item as the caller worked it out, for a start option that is
    not the target's own item (a vendor recipe, ADR-0059): it wins over `start_price` and over the price the target's computed key has in the file.

    `solver` picks the exact solve (ticket #374, #377, #535, ADR-0063): "auto" (the default) is the envelope search wherever its bound can be
    built (`abstraction.pattern_refusal` says before any solve: a goal with a roll limit, an action that rerolls values, an unveil offer or
    imprints refuse it, #507), whatever the size of the graph and whatever the `budget`, because that search is exact, ends in seconds on the small
    graphs and expands far less than the walk on the big ones. Where the bound cannot be built, "auto" is the path it was before the envelope search,
    with or without a `budget` (#926: no forecast and no approximate answer; the run's net ends a walk that is too long, and the stop says what the
    search has no bound for, `walk_cause`): `solve_pruned` for 40 offers or more, otherwise the graph is walked on packed arrays and
    solved there when it holds more than `_packed.OBJECT_SOLVER_EDGES` transitions (R04, R14, S02) and by the object solver below that.
    There is no fallback once the envelope search has started: a search that cannot answer is a `PlanError` that says why and names
    `solver="packed"`. With 40 offers or more (`MIN_OFFERS_TO_PRUNE`, the fossil sets) "auto" keeps the bound pruning for now when the run asks
    for the whole proof (no budget, or a gap of 0): on those worlds the envelope search is 1.2 to 40 times slower (#696, #742), and a search
    that owes the whole proof has no stop of its own; #742 carries removing the exception. Under a budget with a gap it is the envelope search
    there too (#926). With `judges_route` (the caller will judge a given route against the plan: `--route`, `benchmark`), "auto" is that
    older path too, decided before solving: judging a route needs the planner's action at every state the route reaches, and the envelope
    search by design never decides a state it can prove irrelevant (#535; a route judged without the full walk is #732). "object" never packs; "packed" always walks, and with 40 offers or more it solves the offers left after the twins are
    merged, without the bound pruning (the cross-check of the solvers). The means are the same to the certificate; only the cost differs.
    "envelope" is the same search asked for by name: it refuses with `PlanError` an abstraction the bound cannot be built for (#507). It is the
    exact branch-and-bound of OR-12: the walk-free lower bound of #497 (`_pattern_bound`) and a search that expands only the states, and builds
    only the actions, the bound cannot rule out (`_envelope`); it gives the same plan and mean as "packed" and says so in `Plan.limits` (which
    cut ran, what it guarantees). It takes the offers after the twins are merged, as "packed" does, and makes no forecast: with no budget it is exact
    whatever the size, and under one it stops once its plan is proved within the budget's gap of the cheapest (`search_gap`, OR-32, OR-39,
    #826), so a test or a measurement that needs the ladder's approximate answer or the budget refusal names `solver="packed"` or `"object"`. `incumbent` (a state to
    the labels of the offers it takes) is the policy the search completes with a restart for its
    first upper bound (`_envelope_plan.route_incumbent` reads a given route as one); `clock` is the run's clock (`make_plan`), whose net the search
    is given (what is left of its time, its memory and state nets): when it ends the search the plan is the best executable one, `Plan.limits` says
    it is not shown to be the best and gives the lower and upper bounds of its cost.

    With `with_risk` False the policy is solved but its risk (the p50, p90 and CVaR grid, which can take minutes where the solve takes
    seconds) is left out, `Plan.risk` is None, and `add_risk` fills it in later: the choice among start options compares the
    means and measures the risk of the one it keeps (ticket #331).
    """
    if solver not in SOLVERS:
        raise ValueError(f"solver must be one of {', '.join(SOLVERS)}, got {solver!r}")
    setting = strand_setting(target.start_item, asked=strands)
    if setting.on:
        raise PlanError(
            f"Memory Strands are on ({setting.why}), which the planner cannot plan yet"
            ": the cut and the spend of strands are not built, so an answer would silently ignore them"
        )
    if target.implicits or target.quality is not None:
        raise PlanError(
            "the target asks for implicits or quality, which the planner cannot plan yet"
        )
    if target.enchantment is not None:
        raise PlanError(
            "the target asks for an enchantment, which the planner cannot plan yet"
        )
    price_of_start = start_price_of if start_price_of is not None else resolve_start_price(data, target, prices, start_price, price_source)
    goal = Goal.from_target(target)
    limits: tuple[Limit, ...] = (strands_limit(),)
    mod_names, finish_names = split_names(data, target.start_item, target.actions) if target.sockets is not None else (target.actions, None)
    if offers is None:
        try:
            chosen = offers_for(data, goal, target.base_id, target.start_item, mod_names)
        except ValueError as error:
            raise PlanError(str(error)) from error
        offers, limits = chosen.offers, (*chosen.limits, *limits)
    priced, dropped = price_offers(offers, prices, price_source)
    if not priced:
        names = sorted({name for drop in dropped for name in drop.missing})
        raise PlanError(f"no action has a price; missing: {', '.join(names)}")
    listing = unopened_listing(data, target.start_item) if price_of_start.bought else None
    if listing is not None:  # ADR-0064: the bought item is the one the market sells, so the plan opens with the draw of its mods
        priced = (*priced, listing_draw(data, listing, target.start_item.rarity, priced))
    limits += unpriced_limits((drop.label, drop.missing, drop.kind) for drop in dropped)
    usable, removed = split_usable(data, target.start_item, [p.offer.action for p in priced])
    kept = set(usable)
    if removed:
        limits += unusable_limits(data, ((p.label, p.offer.action) for p in priced if p.offer.action not in kept))
    priced = tuple(p for p in priced if p.offer.action in kept)
    limits += start_limits(price_of_start)
    if price_of_start.bought:
        bought = price_of_start.name or "start item"
        restart = Offer(RESTART, BuyStartItem(listing or target.start_item), {bought: 1}, shares=False)
        part = (bought, 1, price_of_start.chaos, price_of_start.source)
        marks = ((bought, price_of_start.mark),) if price_of_start.mark else ()
        priced = (*priced, PricedOffer(restart, price_of_start.chaos, (part,), marks))

    enabled = [p.offer.action for p in priced if (reads := p.offer.action.reads(data)).junk or reads.item_state]
    donated = tuple(p for p in priced if not isinstance(p.offer.action, BuyStartItem) and takes_inputs(p.offer.action))  # offers that take donors (#225)
    finish = None
    if target.sockets is not None and solve_it:  # the finish is solved on its own and added to every goal state (ticket #231, ADR-0045)
        try:
            finish = plan_finish(
                data, target, prices, price_source, names=finish_names, goal_takes_corrupted=goal.takes_corrupted,
                mod_actions=[p.offer.action for p in priced if not isinstance(p.offer.action, BuyStartItem)],
            )  # fmt: skip
        except (FinishRefused, OutOfScopeError, ArithmeticError) as error:  # ArithmeticError: the finish did not converge
            raise PlanError(str(error)) from error
        limits = without_finish_kinds(limits)
    holds_metamod = bool(target.start_item.metamods(data) & BLOCKING)
    # a planned axis is answered at its plan reading (the abstraction's default), its claim an approximate input (OR-11, OR-23); any other
    # axis is solved at every reading of its grid by the interval driver (#589, ADR-0012, ADR-0022): the plan is the route at the plan reading
    axes = interval_axes(data, priced)
    if not axes:  # donors are planned by the interval driver only (#225); an action with inputs and no axis stays a gap of its own (G6)
        donated = ()
    if axes and solver not in ("auto", "object"):
        raise PlanError(
            f"an offered action reads a rule the sources leave open ({', '.join(axis_what(axis.name) for axis in axes)}), so the plan is "
            f"made once for each reading of that rule by the search that holds every item it reaches; `--solver {solver}` does not do that"
        )
    def model(reading: Reading | None = None) -> Abstraction:
        """The abstraction of the target at `reading` of the rule axes (None: the plan reading, ADR-0033)."""
        return Abstraction(
            data,
            goal,
            target.base_id,
            target.item_level,
            enabled,
            metamods=holds_metamod,
            enchantment=target.start_item.enchantment,
            allow_inputs=bool(donated),
            reading=reading,
        )

    abstraction = model()
    start = abstraction.compress(listing or target.start_item)
    shape = abstraction.compress(target.start_item) if listing is not None else None  # the item the start opens into: what the pruning bounds the offers on (ADR-0064)

    if not solve_it:
        unsolved = Solution({start: float("inf")}, {}, float("inf"))
        return Plan(target, abstraction, leaf_labels(target), prices, start, price_of_start, priced, limits, unsolved, None, 0.0, 0.0, finish=finish)
    if donated and solver not in ("auto", "object"):
        raise PlanError(f"an offered action takes donors, so the plan is made by the search that holds every item it reaches; `--solver {solver}` does not do that")
    refusal = pattern_refusal(abstraction) if not axes else "the plan reads a rule axis"  # solved per reading by the object solver (#589)
    # #535: "auto" is the envelope search wherever its bound can be built, but not for a plan a given route is to be judged against: the
    # judgement needs the planner's action at every state the route reaches, and the envelope search never decides the states it proves irrelevant.
    # Nor, for a run that asks for the whole proof (no budget, or a gap of 0), with 40 offers or more (`MIN_OFFERS_TO_PRUNE`, the switch to the
    # bound pruning that already existed, not a new cut-off): on fossil-set worlds the envelope search is 1.2 to 40 times slower than the bound
    # pruning (#696, #742), both paths are exact (OR-11, OR-12), and a search that owes the whole proof has no stop of its own to end early;
    # #742 carries removing this exception. A run whose budget has a gap takes the envelope search there too (#926): it stops by itself once its
    # plan is proved within that gap (`search_gap`, OR-39) and the run's net, where it has one, guards it (OR-33, OR-40); the bound pruning had
    # only the forecast below to keep a walk in bounds.
    many_offers = PRUNE_BOUND and len(priced) >= MIN_OFFERS_TO_PRUNE
    stops_at_gap = search_gap(clock)[0] > 0.0
    envelope = solver == "envelope" or (solver == "auto" and refusal is None and not judges_route and not (many_offers and not stops_at_gap))
    # why `auto` walks every item instead of searching, said when a net stops that walk before a plan closed (OR-13, #926)
    unbounded = () if refusal is None else refusal_causes(abstraction, player=True) or (refusal,)  # the causes in a player's words, else the refusal's own text
    walks_because = None if solver != "auto" or envelope or axes else walk_cause(unbounded, judges_route)
    # The forecast of ADR-0023 and its ladder of approximate answers are retired (direction of 2026-11-13) and `auto` never reaches them (#926):
    # under a budget it is the envelope search, or, where that search cannot take the target, the same walk as with no budget, to the run's net.
    # They stand only behind a walk asked for by name, for the tests and measurements of the ladder itself, until #928 deletes them.
    if aim is not None and solver in FORECAST_SOLVERS and not axes:
        forecast = merged = priced
        merged_twins: list[tuple[str, str]] = []
        if PRUNE_BOUND and len(priced) >= MIN_OFFERS_TO_PRUNE:
            # The exact run solves a small set first and proves the rest not needed: it is forecast on that set, not on
            # a pilot over thousands of fossil sets. An approximate answer is made of all the offers, twins merged.
            merged, merged_twins = (tuple(each) for each in merge_twins(data, target.start_item, priced))
            forecast = tuple(starting_offers(abstraction, start, merged, target.start_item, min_offers=MIN_OFFERS_TO_PRUNE, shape=shape))
        decision = decide(abstraction, start, forecast, aim, rates)
        if decision.message:
            limits += (whole_search_limit(decision.message, decision.detail),)
        if decision.rate_why:
            limits += (guessed_rate_limit(decision.rate_why, decision.rate_detail),)
        if decision.action == "refused":
            if solver == "object" or (PRUNE_BOUND and len(priced) >= MIN_OFFERS_TO_PRUNE):
                raise PlanError(decision.message)
            # no coarse level exists and the graph is beyond the object solver: the packed solver holds it (ticket #70, ADR-0063), so the
            # answer is exact and takes the walk's minutes instead of being refused
            limits = with_limits(limits, (whole_search_limit(_packed_note(decision), decision.detail),), _limits.SOLVE)
        if decision.action == "approximate":
            try:
                with stage(APPROXIMATE_STAGE):
                    solved = climb(decision, start, merged)
                burn = plan_burn(data, target.start_item, abstraction, prices, price_source, sockets=target.sockets is not None)
                foresight = coarse_check(solved.solution.values, lock_price(prices, price_source), cheapest_cost(merged, burn), lock_wanted(target.actions))
            except ValueError as error:  # CoarseLockError among them: the Lock survives the pruning on the coarse bounds (ADR-0054)
                raise PlanError(str(error)) from error
            limits += skipped_level_limits(solved.skipped)
            if merged_twins:
                limits += (twins_limit(merged_twins),)  # G17: the approximate answer is made of the offers left after the twins
            if finish is not None:
                limits += finish_limits(finish, solved.solution.values[solved.start], mods_at_most=True)  # the upper end of the approximate answer
            return finished(Plan(
                target, abstraction, leaf_labels(target), prices, solved.start, price_of_start, priced, limits,
                solved.solution, None, solved.seconds, 0.0, solved.approximation, foresight=foresight, finish=finish,
            ))  # fmt: skip

    began = time.perf_counter()
    pruned = None
    packed = None
    readings = None
    donor_plan = None
    many = PRUNE_BOUND and len(priced) >= MIN_OFFERS_TO_PRUNE
    # every stage below stops at the run's net (#825): `make_plan` says a stop before a plan closed, "no plan found yet", with where (OR-33)
    if axes:
        with stage(READINGS_STAGE):
            readings, others, product = solve_each_reading(abstraction, model, start, priced, axes, donors=donated)
        solution = readings.solution
        if product is not None:  # the solve was over the product of the target and its donors: the plan's own process is read off it
            donor_plan = DonorPlan(product, product.start(start), readings.solution)
            solution = main_view(readings.solution)
            limits += (_limits.feeder_donors_limit(), _limits.free_donor_base_limit(), _limits.second_items_shown_limit())
        limits += reading_limits(abstraction, others, aim is not None)
        offered = None  # the second solve of a Lock takes the offers after the twins, without the bound pruning (`_foresight`)
    elif many and not envelope and solver != "packed":
        with stage(PRUNED_STAGE, walk_stop(walks_because)):  # #702: the walks of the bound pruning stop at the net between two states
            pruned = solve_pruned(abstraction, start, priced, target.start_item, min_offers=MIN_OFFERS_TO_PRUNE, shape=shape)
        solution = pruned.solution
        limits += _pruned_limits(pruned)
        offered = None  # the second solve of a Lock takes the offers after the twins, without the bound pruning (`_foresight`)
    else:
        offered, twins = (tuple(each) for each in merge_twins(data, target.start_item, priced)) if many else (priced, ())
        if twins:
            limits += (twins_limit(twins),)  # G17: the packed path leaves out the dearer twins, as the bound pruning does
        if envelope:
            try:
                with stage(SEARCH_STAGE, SEARCH_KEPT, stops=False):  # the search stops at its own net (`search_net`) and keeps its plan
                    gap, gap_after = search_gap(clock)
                    packed = envelope_result(
                        abstraction, start, offered, prune_corrupting=PRUNE_CORRUPTING, incumbent=incumbent, net=search_net(clock),
                        item=target.start_item if many else None, gap=gap, gap_after=gap_after, watch=watch,
                    )  # fmt: skip
            except (OutOfScopeError, NoPolicy, BoundError, ConvergenceError) as error:
                raise PlanError(envelope_refusal(solver, error)) from error
            limits += envelope_limits(packed.info["envelope"])
            bind_search(clock, packed.info["envelope"])
        else:
            with stage(WALK_STAGE, walk_stop(walks_because)):
                packed = packed_result(abstraction, start, offered, solver=solver, prune_corrupting=PRUNE_CORRUPTING)
        with stage(WALK_STAGE, walk_stop(walks_because)):
            solution = packed.solution if packed is not None else solve(_Model(abstraction, start, priced), [start])
        if packed is not None:
            limits += _packed.evaluation_limits(packed.info)  # (OR-13, #621) the policy evaluation that stopped short of the exact system says so
    if not abstraction.is_goal(start) and not _finite(solution.values[start]):
        raise PlanError("no policy of the offered actions reaches the goal from the start item")
    if donor_plan is not None:  # the Lock's second solve has no product of donors yet (#225): it is not offered, and the answer says so
        wanted = lock_wanted(target.actions)
        if wanted:
            limits += (_limits.lock_with_donors_limit(),)
        status = LockStatus.WITH_SECOND_ITEMS if wanted else LockStatus.SWITCHED_OFF
        foresight, with_lock = Foresight(status, lock_price(prices, price_source)), None
    else:
        try:
            with stage(LOCK_STAGE, LOCK_KEPT):
                foresight, with_lock = plan_foresight(data, target, prices, abstraction, start, solution, priced, offered, pruned, price_source)
        except BudgetExceeded as stop:  # a plan has closed: it is kept, without the Lock, and the clock lists the stop (OR-33)
            if clock is not None:
                clock.bind(stop.binding)  # a stop a forked worker met was bound on its own copy of the clock
            foresight, with_lock = Foresight(LockStatus.STOPPED, lock_price(prices, price_source)), None
    if with_lock is not None and readings is not None:
        raise PlanError(
            "the cheapest plan takes Hinekora's Lock, and a plan made once for each reading of a rule the sources leave open "
            "cannot take the Lock yet. To see the best plan without the Lock, name the kinds to use in the target's `actions:` without `hinekora-lock`"
        )
    if with_lock is not None:  # the plan takes the Lock: its policy is the second solve's, on the object solver (ADR-0054)
        solution, packed = with_lock, None
    solve_seconds = time.perf_counter() - began

    risk, risk_seconds = None, 0.0
    if with_risk:
        began = time.perf_counter()
        with stage(RISK_STAGE, RISK_KEPT, stops=False):  # the risk's ladder stops itself at the run's net and keeps its coarser step (#745, `risk._evaluate`)
            if packed is not None:
                risk, risk_found = packed_risk(packed, solution.values[start], free_action_cost(priced))
            elif donor_plan is not None:  # the whole product: a recombination pays for its donor's run on every use (ADR-0022, `risk._inputs`)
                risk = evaluate_risk(
                    donor_plan.solution.policy, donor_plan.start, donor_plan.acquisition.is_goal, solution.values[start], free_cost=free_action_cost(priced)
                )
                risk_found = risk_limits(risk)
            else:
                risk = evaluate_risk(solution.policy, start, lambda state: not isinstance(state, PeekNode) and abstraction.is_goal(state), solution.values[start], free_cost=free_action_cost(priced))
                risk_found = risk_limits(risk)
        limits += risk_found
        risk_seconds = time.perf_counter() - began
    if packed is not None and packed.view is not None and len(solution.policy) > VIEW_FROM_STATES:
        limits += (lumped_limit(len(solution.policy), len(packed.view) + 1),)
    if finish is not None:
        limits += finish_limits(finish, solution.values[start])

    return finished(Plan(
        target, abstraction, leaf_labels(target), prices, start, price_of_start, priced, limits,
        solution, risk, solve_seconds, risk_seconds, None, pruned, packed=packed, readings=readings, foresight=foresight, finish=finish, donors=donor_plan,
    ))


def interval_axes(data: GameData, priced: Iterable[PricedOffer]) -> tuple[Axis, ...]:
    """The rule axes the offered actions read that are not `planned` (ADR-0033), by name: the ones the plan is solved at every reading of (#589)."""
    found: dict[str, Axis] = {}
    for each in priced:
        for axis in each.offer.action.rule_axes(data):
            if not axis.planned:
                found.setdefault(axis.name, axis)
    return tuple(found[name] for name in sorted(found))


def solve_each_reading(
    abstraction: Abstraction,
    model: Callable[[Reading], Abstraction],
    start: CompressedState,
    priced: Sequence[PricedOffer],
    axes: Sequence[Axis],
    *,
    donors: Sequence[PricedOffer] = (),
) -> tuple[IntervalReport, tuple[Abstraction, ...], Acquisition | None]:
    """Solve the plan once for each reading of `axes` and cross-evaluate the routes (`risk.solve_readings`, ADR-0012, ADR-0022; #589).

    A reading is one value of each axis (their product, the plan reading first); an axis that is `planned` stays at its plan value in every
    one (OR-11). `abstraction` is the model of the plan reading (its `reading` None); each other reading gets its own, `model(reading)`, of the
    same target and enabled actions, so every kernel is taken at that reading. Each model is solved whole by the object solver: the envelope search
    and the packed walk take no reading. The solve is exact; no comparison route is asked, since the planner offers no action with inputs.
    Offers with an equal kernel are not merged (`merge_equal`): the routes are compared across readings by their offers' labels, and an offer
    merged away at one reading could leave a route with no action there.

    With `donors` (the offers among `priced` that take donors, ticket #225) each reading's model is the product of the target and its donors'
    processes (`DonorModel` under `solver.Acquisition`, every donor the offers name offered at once: they are the target's few isolated feeders,
    and a recombination is offered only on an item in hand that is one too, `feeders_only`: the guides' own feeders, and a product that stays small),
    an acquisition ends at the first state with the donor's key (`Abstraction.reaches_donor`), the driver starts from the target's own process,
    and the best route without the actions that take donors is solved beside the plan (ADR-0012's comparison route). The report is then over
    product states. Returns the driver's report, the abstractions of the other readings and the plan reading's product (None without donors).
    """
    names = [axis.name for axis in axes]
    plan = Reading.of({axis.name: axis.plan for axis in axes})
    every = [Reading.of(dict(zip(names, values))) for values in itertools.product(*(axis.readings for axis in axes))]

    order = (plan, *(r for r in every if r != plan))
    abstractions = {reading: abstraction if reading == plan else model(reading) for reading in order}
    if donors:
        from ._donors import DonorModel  # `_donors` builds on this module's `offer_action`

        if len({type(p.offer.action) for p in donors}) != 1:
            raise PlanError("the offers take donors of more than one kind of action, which the planner cannot plan together yet")
        first = donors[0].offer.action
        models = {
            reading: Acquisition(DonorModel(each, start, priced, merge_equal=False, feeders_only=True), reaches=each.reaches_donor(first))
            for reading, each in abstractions.items()
        }
        root, without = models[plan].start(start), has_inputs
    else:
        models = {reading: _Model(each, start, priced, merge_equal=False) for reading, each in abstractions.items()}
        root, without = start, None
    try:
        report = solve_readings(models, root, plan=plan, without=without)
    except (OutOfScopeError, ConvergenceError) as error:
        raise PlanError(f"the plan could not be made at every reading of the rule axis {', '.join(names)}: {error}") from error
    others = tuple(each for reading, each in abstractions.items() if reading != plan)
    return report, others, (models[plan] if donors else None)


def reading_limits(abstraction: Abstraction, others: Iterable[Abstraction], budgeted: bool) -> tuple[Limit, ...]:
    """What the solves of the other readings left out, beyond what the plan reading's own model says (`finished` adds that), and the budget.

    A gap of an action the plan reading's model has no gap for, and a pruning limit it does not give, are said once (OR-13). With a time
    budget the run says that it did not apply: each reading is solved whole and exactly, however long that takes.
    """
    others = tuple(others)
    own = {gap.label for gap in abstraction.gaps.entries()}
    gaps: dict[str, Gap] = {}
    for other in others:
        for gap in other.gaps.entries():
            if gap.label not in own:
                gaps.setdefault(gap.label, gap)
    found = list(model_gap_limits(gaps.values()))
    seen = set(pruning_limits(abstraction.prunings))
    for other in others:
        for limit in pruning_limits(other.prunings):
            if limit not in seen:
                seen.add(limit)
                found.append(limit)
    if budgeted:
        found.append(Limit(
            _limits.SOLVE,
            "The time budget was not applied",
            "an offered action reads a rule the sources leave open, so the plan is solved whole at each reading of that rule",
            "The answer is exact at every reading; only the time it takes is not bounded.",
        ))  # fmt: skip
    return tuple(found)



def plan_foresight(
    data: GameData,
    target: Target,
    prices: PriceFile,
    abstraction: Abstraction,
    start: CompressedState,
    solution: Solution[CompressedState],
    priced: Sequence[PricedOffer],
    offered: Sequence[PricedOffer] | None,
    pruned: Pruned | None,
    price_source: str = DEFAULT_PRICE_SOURCE,
) -> tuple[Foresight, Solution | None]:
    """Hinekora's Lock of an exact plan (`_foresight.foresee`): its status, N and, when the plan takes it, the solution with the Lock.

    The options come from the full list `priced`; the fallback of the gains for N reads the offers the Lock-free solve used (`offered`, or the offers
    the bound pruning kept, a subset whose fallback is never cheaper, so N is never overstated); the second solve and the fallback of its Peeks read the
    offers after the twins, with no bound pruning (`offered`, or the twins merged from `priced`). Nothing is built for a Lock the target switched off.
    """
    lock = lock_price(prices, price_source)
    if not lock_wanted(target.actions):  # switched off: nothing is built
        return Foresight(LockStatus.SWITCHED_OFF, lock), None
    burn = plan_burn(data, target.start_item, abstraction, prices, price_source, sockets=target.sockets is not None)
    cache: dict = {}
    plain = offered if offered is not None else (pruned.used if pruned is not None else priced)
    sites = PlanSites(abstraction, priced, plain, start, burn, prune_corrupting=PRUNE_CORRUPTING, cache=cache)

    def second_solve():
        second = offered if offered is not None else tuple(merge_twins(data, target.start_item, priced)[0])
        peeks = sites if second is plain else PlanSites(abstraction, priced, second, start, burn, prune_corrupting=PRUNE_CORRUPTING, cache=cache)
        return _Model(abstraction, start, second, cache), peeks

    return foresee(
        abstraction, start, solution, sites, second_solve, lock=lock, c_min=cheapest_cost(priced, burn), is_goal=abstraction.is_goal,
    )  # fmt: skip


def walk_cause(unbounded: Sequence[str], judges_route: bool) -> str:
    """Why `solver="auto"` walks every item the actions can reach instead of running the envelope search (#926): the cause that `make_plan`
    decided on before solving, in the order it decides: what the search has no lower bound for yet (`refusal_causes`), a route to judge, or, for
    a run that asks for the whole proof (no gap), the number of offers (#742)."""
    said = "the faster search, which proves its plan against the cheapest possible cost, was not used: "
    if unbounded:
        return said + f"it has no such cost yet where {'; '.join(unbounded)}"
    if judges_route:
        return said + "a given route is judged against the plan, which needs the planner's choice at every item the route can reach"
    return said + f"{MIN_OFFERS_TO_PRUNE} actions or more are offered and the run asks for the whole proof that no plan is cheaper"


def walk_stop(cause: str | None) -> str:
    """What a net's stop of a walk leaves (OR-33: "no plan found yet"), with why `auto` walked instead of searching when it chose to (OR-13, #926)."""
    return NO_PLAN if cause is None else f"{NO_PLAN}; {cause}"


def envelope_refusal(solver: str, error: Exception) -> str:
    """The `PlanError` text of an envelope search that cannot answer (OR-13): the cause in words, and for `auto` the way to the walk, which is never taken silently (#535).

    Under `auto` a refusal of the bound's build carries a player's cause (`.player`, set by `abstraction._pattern`) in place of the developer's text,
    and a search that found no route says so as the walk does, with no advice to walk: the walk would find none either.
    """
    if solver == "envelope":
        return f"the envelope search cannot answer this target: {error}"
    if isinstance(error, NoPolicy):
        return f"no policy of the offered actions reaches the goal from the start item ({error})"
    cause = getattr(error, "player", None) or str(error)
    return (
        f"the exact search for the cheapest route could not give an answer: {cause}. "
        "The search that walks every possible item gives the exact answer instead, more slowly and with more memory: `--solver packed`"
    )


def finished(plan: Plan) -> Plan:
    """`plan` with the limits only the finished walk and policy can tell: the actions the model had no rule for, the offers left out of states
    that cannot use them, and what the state descriptions and the reach chances leave out."""
    added = (*model_gap_limits(plan.abstraction.gaps.entries()), *pruning_limits(plan.abstraction.prunings), *display_limits(plan))
    return replace(plan, limits=(*plan.limits, *added))


def display_limits(plan: Plan) -> tuple[Limit, ...]:
    """What the text report, the JSON and the page leave out of a state's description (V4) and of its reach chance (C15, V8)."""
    # the reach chance and the steps of the policy are the presenter's to tell (#466; the page's maths, asked through `_presenter`, #880)
    return (states_limit(plan.abstraction.keeps_junk), *presenter_limits(plan))


def states_limit(tracked: bool) -> Limit:
    """The limit of a state description, which names the mods the model tracks and nothing of the others (V4)."""
    if tracked:
        return Limit(
            _limits.STATE_LINE,
            "A state lists the other mods only as a count per side",
            "the model keeps the mods the target does not ask for by kind, not by name",
            "The odds and costs count every one of them.",
        )
    return Limit(
        _limits.STATE_LINE,
        "A state does not list the other mods",
        "no offered action reads the mods the target does not ask for, so the model does not track them",
        "The odds and costs do not depend on them: no offered action reads them.",
    )


def guessed_rate_limit(why: str, detail: str = "") -> Limit:
    """The limit of a forecast that used a fixed search speed because the speed could not be measured (M2); `detail` is the developer's text behind `why` (JSON only)."""
    return Limit(
        _limits.SOLVE,
        "The time of the search was guessed",
        why + ", so the size estimate used a fixed speed",
        "The answer's own guarantee does not depend on it: the size estimate only chose between the exact run and an approximate one.",
        detail=(detail,) if detail else (),
    )


def skipped_level_limits(skipped: Sequence[tuple[str, ...]]) -> tuple[Limit, ...]:
    """The limit of the tail-cut levels the ladder skipped because they had no policy to follow or did not converge (M3).

    Each entry is (level name, why) or (level name, why, the developer's text behind it); `detail` follows `names` one for one (JSON only).
    """
    if not skipped:
        return ()
    detail_of: dict[str, str] = {}
    for _, why, *rest in skipped:
        detail_of.setdefault(why, rest[0] if rest and rest[0] else why)
    return (
        Limit(
            _limits.SOLVE,
            "Approximate answers skipped",
            "they gave no plan to follow or did not settle: {names}",
            labels=tuple(name for name, *_ in skipped),
            names=tuple(detail_of),
            detail=tuple(detail_of.values()) if any(len(entry) > 2 and entry[2] for entry in skipped) else (),
            guarantee="The stated gap is that of the approximate answer shown; a skipped one could only have narrowed it.",
        ),
    )


def strands_limit() -> Limit:
    """The limit of a plan that does not consider Memory Strands (ADR-0040), naming the kinds that need them (K3, K6, G1)."""
    needing = tuple(kind_title(entry.name) for entry in kinds() if entry.needs_strands)
    return Limit(
        _limits.STRANDS,
        "Memory Strands are not considered",
        "the start item has none, and the planner cannot plan with them yet",
        "The plan makes no use of Memory Strands.",
        needing,
    )


def start_limits(price: StartPrice) -> tuple[Limit, ...]:
    """The limit of a given start item (OR-6, OR-13): its cost is not counted and it is never bought again; a bought one has none."""
    if price.bought:
        return ()
    return (
        Limit(
            _limits.START,
            "The start item is given",
            "the target says the player already holds it",
            **claim("the plans that never start over", "The cost of the start item is not counted, and the plan never buys another."),
        ),
    )


def whole_search_limit(why: str, detail: str = "") -> Limit:
    """The limit of an exact answer found by the whole search, which took longer than the time budget or could not be forecast (G12, G13).

    `detail` is the developer's text behind `why` (an exception's `detail`); the JSON carries it and no text does.
    """
    return Limit(_limits.SOLVE, "The whole search was run", why, "The answer is exact among the methods offered.", detail=(detail,) if detail else ())


def lumped_limit(item_states: int, shown: int) -> Limit:
    """The limit of a tree that shows groups of states, not every state (G14)."""
    return Limit(
        _limits.DISPLAY,
        "The tree shows groups of states",
        f"the plan passes through {item_states:,} states and the tree shows {shown:,} groups of them: states that cost the same and lead on to "
        "the same groups with the same chances are one group, shown by one of its members",
        "The odds and every cost figure are exact for the groups.",
    )


def _packed_note(decision: Decision) -> str:
    """The plan's note for a query the decision refused and the large-graph solver answers exactly: why there is no approximation and what ran."""
    size = "" if decision.transitions is None else f" (estimated at least {decision.transitions:,} possible moves between states)"
    return (
        f"No approximate answer was possible ({decision.why}), so the whole search ran: it is large{size} "
        "and takes minutes and several GB of memory."
    )


RISK_QUANTILE_TRANSITIONS = 2_000_000  # a merged chain with more transitions gets no quantile DP (ticket #374): the DP's entries outgrew 16 GB on R04's 4.7 M


def packed_risk(packed: PackedResult, mean: float, free_cost: float | None) -> tuple[RiskReport, tuple[Limit, ...]]:
    """The risk of a packed plan's policy, evaluated on its merged chain (same mean, odds and quantiles), and the limits of that risk.

    A merged chain of more than `RISK_QUANTILE_TRANSITIONS` transitions gets its exact odds, mean and variance and no quantile grid,
    and the limit says so.
    """
    if _packed.PROGRESS is not None:
        _packed.PROGRESS(f"solved: mean {mean!r}; evaluating the risk on the merged chain ({len(packed.risk_policy):,} classes)")
    moves = sum(len(action.outcomes) for action in packed.risk_policy.values())
    resolve = moves <= RISK_QUANTILE_TRANSITIONS
    # A chain whose levels the ordinary grid is not certain to reach is run on the coarse grid (R04) or, when that is too big, one attempt at a
    # time (R14), instead of running the ordinary grid to its end first and finding them unresolved (ticket #70); `evaluate` falls back
    # to the ordinary grid when neither works.
    _regen.TRACE = _packed.PROGRESS
    try:
        risk = evaluate_risk(
            packed.risk_policy, packed.risk_start, packed.risk_is_goal, mean, free_cost=free_cost, resolve_quantiles=resolve, packed_moments=True,
            coarse_first=resolve, regenerative=resolve,
        )  # fmt: skip
    finally:
        _regen.TRACE = None
    if _packed.PROGRESS is not None:
        _packed.PROGRESS(f"risk: p50 {risk.p50!r}, p90 {risk.p90!r}")
    if not resolve:
        return risk, (
            Limit(
                _limits.RISK,
                _limits.not_computed(*_limits.QUANTILES),
                f"the plan can lead from one state to another in {moves:,} ways, more than the {RISK_QUANTILE_TRANSITIONS:,} the calculation "
                "of the cost figures can hold in memory",
                "The odds, the mean and the variance are exact.",
            ),
        )
    return risk, risk_limits(risk)


def add_risk(plan: Plan) -> Plan:
    """`plan` with its risk measured, when `make_plan(with_risk=False)` left it out; a plan that has its risk, or an approximate one, is returned as is."""
    if plan.risk is not None or plan.approximation is not None:
        return plan
    began = time.perf_counter()
    free = free_action_cost(plan.offers)
    with stage(RISK_STAGE, RISK_KEPT, stops=False):  # the risk's ladder stops itself at the run's net and keeps its coarser step (#745)
        if plan.packed is not None:
            risk, found = packed_risk(plan.packed, plan.solution.values[plan.start], free)
        elif plan.donors is not None:  # the whole product: `solution` is the target's own process, whose actions leave their donors out (#225)
            donors = plan.donors
            risk = evaluate_risk(donors.solution.policy, donors.start, donors.acquisition.is_goal, plan.solution.values[plan.start], free_cost=free)
            found = risk_limits(risk)
        else:
            risk = evaluate_risk(plan.solution.policy, plan.start, plan.is_goal, plan.solution.values[plan.start], free_cost=free)
            found = risk_limits(risk)
    return replace(plan, risk=risk, limits=with_limits(plan.limits, found, _limits.RISK), risk_seconds=time.perf_counter() - began)


RISK_BINS = 200_000  # the default `max_bins` of `risk.evaluate`
UNRESOLVED_BINS = 1_000
COARSE_BINS = 1_000_000  # the most bins of the coarse grid of `risk.evaluate` (ticket #190)


def evaluate_risk(
    policy: Mapping[CompressedState, Action[CompressedState]],
    start: CompressedState,
    is_goal: Callable[[CompressedState], bool],
    mean: float,
    free_cost: float | None = None,
    *,
    resolve_quantiles: bool = True,
    packed_moments: bool = False,
    coarse_first: bool = False,
    regenerative: bool = False,
) -> RiskReport:
    """The risk metrics of a fixed policy whose mean cost from `start` is about `mean`.

    `free_cost` is what `price_offers` charged the actions that consume nothing (`free_action_cost`). Those actions are counted apart from
    the grid (ticket #349, `risk._free`): the step is set by the cheapest action that costs something, so a veil plan's quantiles and
    CVaR resolve instead of stepping by the epsilon. If the policy holds none, or the grid cannot be built that way, nothing differs.

    The ordinary quantile grid cannot step over the cheapest action, so `RISK_BINS` of it cover `RISK_BINS` times
    the cheapest cost. When that is less than half the mean the p90 (and for a repeat-until-success policy the median)
    is out of reach of it (an Alteration spam costing 6,300 Chaos next to a Transmutation of 0.0058, R13). `evaluate`
    then looks for a coarse grid (ticket #190) of up to `COARSE_BINS` bins, at which the actions that are visited
    often are whole multiples of the step; when there is none the ordinary run is cut to `UNRESOLVED_BINS`, the mean
    and the odds stay exact and the quantiles and CVaR come back unresolved (infinite) at once instead of after
    minutes. No route of R10, R11, R05 or R12 is near the cut.
    """
    cheapest = min((action.cost for action in policy.values()), default=0.0)
    bins = UNRESOLVED_BINS if 2 * RISK_BINS * cheapest < mean else RISK_BINS
    extra: dict = {} if resolve_quantiles else {"resolve_quantiles": False}
    if packed_moments:
        extra["packed_moments"] = True
    if coarse_first:
        extra["coarse_first"] = True
    if regenerative:
        extra["regenerative"] = True
    if free_cost is None or not any(is_free_cost(action.cost, free_cost) for action in policy.values()):
        return evaluate(policy, start, is_goal, max_bins=bins, max_coarse_bins=COARSE_BINS, **extra)
    paid = min((action.cost for action in policy.values() if not is_free_cost(action.cost, free_cost)), default=0.0)
    apart = UNRESOLVED_BINS if 2 * RISK_BINS * paid < mean else RISK_BINS  # the grid is set by the actions that cost something
    return evaluate(policy, start, is_goal, max_bins=apart, max_coarse_bins=COARSE_BINS, free_cost=free_cost, free_fallback_bins=bins, **extra)


def _pruned_limits(pruned: Pruned) -> tuple[Limit, ...]:
    """The offers the pruning left out of the solve, by reason (the plan still prices and evaluates all of them); the answer stays exact (K15)."""
    found = []
    if pruned.fell_back:
        found.append(
            Limit(
                _limits.SOLVE,
                "All the actions were solved",
                f"the search first solved a smaller set of actions and could not prove it enough ({pruned.why})",
                "The answer is exact among the methods offered.",
                detail=(pruned.detail,) if pruned.detail else (),
            )
        )
    if pruned.twins:
        found.append(twins_limit(pruned.twins))
    if pruned.inapplicable:
        found.append(
            Limit(
                _limits.PROVED,
                "Not searched",
                "the game refuses it on this item wherever it can be",
                "The answer is exact among the methods offered: the game never lets these be used here.",
                tuple(pruned.inapplicable),
            )
        )
    if pruned.bounded:
        found.append(
            Limit(
                _limits.PROVED,
                "Not searched",
                "proved never better: even its best case costs more than the plan",
                "The answer is exact among the methods offered: none of these can beat the plan.",
                tuple(pruned.bounded),
            )
        )
    return tuple(found)


def _finite(value: float) -> bool:
    return value == value and value != float("inf")


def chance(weight: int, total: int) -> float:
    """`weight / total` as a float, exact in the ratio even for huge integers."""
    return float(Fraction(weight, total))
