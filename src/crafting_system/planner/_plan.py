"""From a target to a solved policy with its risk: targets -> prices -> abstraction -> solver -> risk.

`make_plan` is the whole pipeline of the R12 slice and does no printing and no file work: the
caller loads the game data, the target and the prices and decides what to do with the `Plan`.
Nothing here reads the clock except `time.perf_counter` around the solve and the risk run, which
are reported (the budget DP of `risk.evaluate` is pure Python and can be slow on large policies).

Under a `budget` with a gap (1% by default) the default search (`solver="auto"`) is the envelope search wherever its bound can be built and no
given route is judged: it keeps proving while the plan is under its aim, and past the aim stops by itself once its plan is proved within the
budget's gap of the cheapest (OR-32, OR-39, #826, #925; `search_gap`),
and the run's net, when the budget has one, guards it (OR-33, OR-40); the `Plan` has no `approximation` (its mean is the mean of the plan
shown, certified to `EnvelopeInfo.mean_error`: 1e-6 or less except for a plan of very many steps, #867) and `Plan.search` says how the search ended. Where that search cannot take the target, `auto` walks every item exactly, as with no budget,
to the run's net (#926). Without a `budget`, or with a gap of 0, the plan is always exact. The forecast of ADR-0023 (`_decide.decide`) and its ladder of coarse levels (`_approx`), which answer with an `approximation`
(a pessimistic `solution` on blocks and no `risk`), are retired: only a walk asked for by name (`solver="packed"`, `"object"`) under a budget
still reaches them, until #928 deletes them.
"""

import itertools
import math
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any

from crafting_system import parallel
from crafting_system.abstraction import _pattern
from crafting_system.budget import NO_PLAN, PIECES, STATES, Binding, Budget, BudgetExceeded, Clock, checkpoint, running, stage
from crafting_system.budget import active as budget_active
from crafting_system.abstraction import Abstraction, CompressedState, Gap, Goal, adds_metamod, integer_weights, pattern_refusal, refusal_causes
from crafting_system.actions import BLOCKING, Axis, NotApplicableError, OutOfScopeError, Reading, kinds, open_listing, sharing, start_over_wipe, unopened_listing
from crafting_system.data import GameData
from crafting_system.items import Item, eldritch_side
from crafting_system.prices import PriceFile, lock_price, planned_price
from crafting_system.prices.price_source import DEFAULT_PRICE_SOURCE
from crafting_system.risk import IntervalReport, RiskReport, Searched, _regen, evaluate, has_inputs, is_free_cost, solve_readings
from crafting_system.risk._moments import interval as _moments_interval
from crafting_system.solver import MAIN, Acquisition, Action, ConvergenceError, Outcome, PeekNode, Solution, solve
from crafting_system.prices.query_compare import other_item
from crafting_system.targets import KOfN, PlainQualityRequirement, Requirement, StartBuyError, StartKind, Target, buy_spec_of, shared_name_refusal

from ._approx import Approximation, climb
from ._awakener import Donor, awakener_offers, donor_base_cost, donor_limits, fold, solve_donors, whole_info
from ._axes import axis_what
from ._offer_kinds import merge_twins
from ._decide import Rates, decide
from ._finish import FinishRefused, PlanFinish, finish_limits, plan_finish, split_names, without_finish_kinds
from . import _implicit_finish, _quality_finish
from ._implicit_finish import ImplicitFinish, ImplicitFinishRefused, implicit_finish_limits, plan_implicit_finish
from ._quality_finish import QualityFinish, QualityFinishRefused, plan_quality_finish, quality_finish_limits
from ._foresight import CoarseLockError, Foresight, PlanSites, Status as LockStatus, cheapest_cost, coarse_check, foresee, lock_wanted, plan_burn
from . import _limits
from ._made_start import made_start
from ._start_types import MadeStart
from ._limits import Limit, approximate_limits, rough_mean_limits, budget_limit, claim, kind_title, model_gap_limits, pruning_limits, risk_limits, twins_limit, unpriced_limits, with_limits
from ._offers import RESTART, BuyStartItem, Offer, PricedOffer, WipeStartItem, wipe_offer, cheapest_per_class, eldritch_unreachable, free_action_cost, listing_draw, offers_for, price_offers, same_craft_limit, split_usable, takes_inputs, unusable_limits
from . import _packed
from ._envelope import ACCEPT_BOUND, Net, NoPolicy, Standing
from ._envelope_plan import SEARCH_PER_BUILD, BoundError, EnvelopeInfo, build_stop, certified_upper, envelope_limits, envelope_result
from ._packed import SOLVERS, PackedResult, packed_result
from ._pattern_bound import MIN_OFFERS, offers_floor
from ._presenter import presenter_limits
from ._price_cut import price_cut_limit, restart_dominated
from . import _growth, _rounds
from ._rounds import RoundCall
from ._prune import chosen_offers, solver_actions, wipe_lands
from ._start_types import StartChoice

VIEW_FROM_STATES = 1_000  # a packed plan whose policy visits more item states than this is shown by its lumped chain (ticket #70)
MERGE_EQUAL = True  # offers with an equal kernel at a state: only the cheapest (exact; a test turns it off for the reference)
PRUNE_CORRUPTING = True  # corrupting offers of a target that asks are left out of the states that cannot reach its goal (exact, ADR-0036; a test turns it off)
PRUNE_BOUND = True  # with `MIN_OFFERS` offers or more the dearer twins are left out of the solve (exact; a test turns it off for the reference)
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
    searched: Mapping[str, Any] | None = field(default=None, compare=False)  # the stored search body when `taken_for` is set: the page names and links it (#937)
    made: MadeStart | None = field(default=None, compare=False)  # the item is made by its recipe, not bought as one (#1523): the goods priced

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
    starts: StartChoice | None = None  # the start options compared and refused (ADR-0059, `_starts.plan_with_starts`); None when none was compared
    packed: PackedResult | None = None  # set when the packed solver solved it (ticket #374): what its risk is evaluated on
    readings: IntervalReport[CompressedState, Reading] | None = None  # set when an offer reads a rule axis that is not planned: the solve of every reading (#589)
    foresight: Foresight | None = None  # what the plan found about Hinekora's Lock (ticket #296, ADR-0057); None for a plan that was not solved
    finish: PlanFinish | None = None  # the socket finish added to every goal state (ticket #231, ADR-0045); None for a target that names no sockets
    donors: "DonorPlan | None" = None  # set when an offer takes donors (ticket #225): the product of the main item and its donors' processes
    quality_finish: QualityFinish | None = None  # the catalyst quality applied after the mods (#159, `_quality_finish`); None when none is asked or it is searched
    implicit_finish: ImplicitFinish | None = None  # the base implicit rolled by Blessed Orbs after the mods (#1231, `_implicit_finish`); None when none is asked or it is searched

    def __post_init__(self) -> None:
        # one place decides what a guarantee of cheapness says: an approximate answer reaches the cheapest only to within its stated gap (OR-13),
        # and so does a search that ended at a proved gap or at a net (OR-32, OR-33; #826)
        search = self.search
        if self.approximation is not None or (search is not None and not search.exact):
            object.__setattr__(self, "limits", approximate_limits(self.limits))
        if search is not None and not search.exact and search.mean_error > ACCEPT_BOUND:  # its mean is certified only to `mean_error` (#867)
            object.__setattr__(self, "limits", rough_mean_limits(self.limits, search.mean_error))

    @property
    def search(self) -> EnvelopeInfo | None:
        """How the envelope search ended, when it made this plan: exact, at a proved gap (`within`) or at a net (`stopped`), with the plan's
        mean `upper` (certified to `mean_error` of itself) and the figure no plan can cost less than, `lower` (both after the start item). None for a plan of another path."""
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
        """What the finishes add to every goal state: the socket finish's mean from the start item's sockets (ADR-0045), the quality finish's
        from its quality (#159) and the implicit finish's from its implicit (#1231), 0 for a target that asks for none.

        One value for every goal state (no mod action changes sockets; Orb of Binding, which gives a goal a second one, is ticket #232; no mod
        action changes the quality or the implicit where it is a finish), so the plan of the mods is the cheapest with the finishes too and only
        its mean grows (`_finish.py`, `_quality_finish.py`, `_implicit_finish.py`)."""
        return (0.0 if self.finish is None else self.finish.value) + self.quality_finish_value + self.implicit_finish_value

    @property
    def quality_finish_value(self) -> float:
        """What the quality finish adds to every goal state (#159): the mean cost of the catalysts from the start item's quality, 0 for none."""
        return 0.0 if self.quality_finish is None else self.quality_finish.value

    @property
    def implicit_finish_value(self) -> float:
        """What the implicit finish adds to every goal state (#1231): the mean cost of the Blessed Orbs from the start item's implicit, 0 for none."""
        return 0.0 if self.implicit_finish is None else self.implicit_finish.value

    def value_of(self, state: CompressedState) -> float:
        """The expected cost from `state` to the finished item: the solver's value of the mods plus the finish, which every goal state adds."""
        return self.solution.values[state] + self.finish_value

    @property
    def total_mean(self) -> float:
        """The expected cost of the whole craft from the start, the mods and the finishes, without the price of the start item."""
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
        if isinstance(priced.offer.action, WipeStartItem) and not wipe_lands(abstraction, priced.offer.action, state):
            raise NotApplicableError("the Orb of Scouring does not give the start item back here")
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
    made = made_start(data, target, prices, price_source)  # a dual-influenced item the market has no line for is made by an Awakener's Orb (#1523)
    if made is not None and (planned is None or made.chaos < planned.chaos):
        words = " + ".join(f"{count} {good}" for good, count, _, _ in made.goods)
        return StartPrice(name, made.chaos, f"made with an {made.orb}: {words}", made=made)
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
    taken_for = other_item(spec, stored) if isinstance(stored, dict) else None
    return StartPrice(name, entry.chaos, entry.source, taken_for, mark=planned.mark, searched=stored if taken_for else None)


def searched_rarity(price: StartPrice) -> str | None:
    """The rarity the stored trade search of the start's price asked for ("normal", "magic", "rare", "nonunique"), or None when no search is kept."""
    stored = price.searched
    if not isinstance(stored, Mapping):
        return None
    query = stored.get("query") if isinstance(stored.get("query"), Mapping) else stored
    return ((((query.get("filters") or {}).get("type_filters") or {}).get("filters") or {}).get("rarity") or {}).get("option")


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
    route_actions: tuple[str, ...] | None = None,
    methods: tuple[str, ...] | None = None,
) -> Plan:
    """Solve the target and measure the risk of the policy, under one budget of time and memory (`crafting_system.budget`, #825).

    Under a budget the envelope search keeps proving while the plan is under its aim, and past the aim stops by itself once its plan is proved to
    cost at most the budget's `gap` more than the cheapest (OR-32, OR-39, #826, #925, `search_gap`; a number of seconds is a budget with the
    default gap); with no budget, `Budget.unlimited()` or a gap of 0 the proof is exact. `watch` is told
    where that search stands, from its first executable plan on and after each round (`_envelope.Standing`: the best plan's cost so far and the
    figure no plan can cost less than), so a caller can show a plan while the proof goes on.

    `budget` is the run's `Budget` (OR-33: the aim and the stop-and-say-so net of time and memory, `Budget.default()`), or a number of seconds
    (the aim alone, with the default gap and no net: the stop at the proved gap applies past the aim, and the retired forecast of ADR-0023 reads the aim for
    a walk asked for by name), or None (no aim and no net: every stage runs to its end, as a test of the
    exact answer or a measurement needs). `net` is the older way to give the net (its time, memory and states), and is folded into the budget.
    Every stage runs on the one clock of the run (a plan inside a run that already has a clock, a start option or a reading, shares it), and a
    stage that a limit stopped is listed in one limit of the answer (`_limits.budget_limit`, #378). A stop before any plan closed is a `PlanError`
    that says where it stopped ("no plan found yet", OR-33); a stop after one did keeps it and says so. A judged route is evaluated on its own
    reach (`cli._route.evaluate_route`, #986); `route_actions` are the labels it names (`cli._route.route_actions`), which lead the first round
    of the offers (#1110), and `judges_route` alone, with no labels, searches every offer at once (`_make_plan`). `methods` are the run's
    methods setting (`PlanSettings.methods`, #405): the plan is made with those alone (`with_methods`); None leaves the target's as they are,
    which for a target read from a file is every beta method. A target that asks for a catalyst quality is planned without it, and the quality is
    added as a finish (`_quality_finish`, #159: no other method changes the quality, so the catalysts come last and cost `Q(q0)` from the start
    item's quality, `Plan.quality_finish`); where an offered action changes or reads the quality, or corrupts the item, the quality is searched
    with the mods instead. A target whose implicit wishes are all on base implicits the start item holds is planned without them likewise, and
    the roll is added as a finish of Blessed Orbs (`_implicit_finish`, #1231: no other method changes a base implicit, so the orbs come last and
    cost `b / p`, `Plan.implicit_finish`); where an offered action changes or reads the implicits, or corrupts the item, the implicit is
    searched with the mods instead. The rest is `_make_plan`'s text.
    """
    target = with_methods(target, methods)
    plan_budget: Budget | None = as_budget(budget, net)
    owns = budget_active() is None and plan_budget is not None
    judged = judges_route or incumbent is not None or route_actions is not None
    finished_last = _quality_finish.applies(target, offers, judged=judged)  # the catalyst quality is a finish (#159): the mods are planned without it, then it is added
    implicit_last = _implicit_finish.applies(data, target, offers, judged=judged)  # so is a base implicit's roll (#1231)

    def mods_target() -> Target:
        return replace(target, quality=None if finished_last else target.quality, implicits=() if implicit_last else target.implicits)

    # one store of exact draws for the whole plan: no round, start option or second item makes a walk another made (`actions.draw.DrawStore`, #1194)
    with running(plan_budget.start() if plan_budget is not None else None) as clock, sharing():
        try:
            plan = _make_plan(
                data, mods_target(), prices, start_price=start_price, offers=offers,
                aim=None if plan_budget is None else plan_budget.aim_seconds, rates=rates,
                strands=strands, solve_it=solve_it, start_price_of=start_price_of, price_source=price_source, solver=solver, with_risk=with_risk,
                incumbent=incumbent, clock=clock, watch=watch, judges_route=judges_route, route_actions=route_actions, priced_as=target,
            )  # fmt: skip
            offered = [p.offer.action for p in plan.offers if not isinstance(p.offer.action, BuyStartItem)]
            quality_holds = not finished_last or _quality_finish.holds(data, offered)
            implicit_holds = not implicit_last or _implicit_finish.holds(data, offered)
            if not (quality_holds and implicit_holds):
                # an offered action other than a catalyst changes or reads the quality, or one changes or reads the implicits, or corrupts the
                # item (a recombinator, a Vaal Orb a run names, an Ember on boots): that finish is not exact, so what it would finish is searched
                # with the mods, in the one search. The second plan shares the run's clock, so it pays what is left of the net; checking the
                # offers before the first plan would need the offers `_make_plan` chooses (#159, #1231)
                finished_last, implicit_last = finished_last and quality_holds, implicit_last and implicit_holds
                plan = _make_plan(
                    data, mods_target(), prices, start_price=start_price, offers=offers, aim=None if plan_budget is None else plan_budget.aim_seconds,
                    rates=rates, strands=strands, solve_it=solve_it, start_price_of=start_price_of, price_source=price_source, solver=solver,
                    with_risk=with_risk, incumbent=incumbent, clock=clock, watch=watch, judges_route=judges_route, route_actions=route_actions,
                    priced_as=target,
                )  # fmt: skip
        except BudgetExceeded as stop:  # a stage met the net before any plan closed (a stage that has one keeps it and does not raise): OR-33
            if clock is not None:
                clock.bind(stop.binding)  # a stop a forked worker met was bound on its own copy of the clock
            raise PlanError(stopped_refusal(clock, stop.binding)) from None
    # after the mods, so that a refusal of the target itself is said first
    try:
        quality = plan_quality_finish(data, target, prices, price_source, names=target.actions) if finished_last else None
        implicit = plan_implicit_finish(data, target, prices, price_source, names=target.actions) if implicit_last else None
    except (QualityFinishRefused, ImplicitFinishRefused, OutOfScopeError) as error:
        raise PlanError(str(error)) from error
    plan = with_finishes(plan, quality, implicit)
    return with_bindings(plan, clock) if owns else plan


def with_finishes(plan: Plan, quality: QualityFinish | None, implicit: ImplicitFinish | None) -> Plan:
    """`plan` of the mods with the quality finish (#159) and the implicit finish (#1231) added: their values on every goal state, and the lines
    that say them (`_quality_finish`, `_implicit_finish`). Each line gives the total of the whole craft, the mods and both finishes."""
    if quality is None and implicit is None:
        return plan
    mods = plan.solution.values.get(plan.start, float("inf"))
    upper_end = plan.approximation is not None or (plan.search is not None and not plan.search.exact)  # the mods' mean is then an upper end (OR-13)
    quality_value = 0.0 if quality is None else quality.value
    implicit_value = 0.0 if implicit is None else implicit.value
    said: tuple[Limit, ...] = ()
    if quality is not None:
        said += quality_finish_limits(quality, mods + implicit_value, mods_at_most=upper_end)
    if implicit is not None:
        said += implicit_finish_limits(implicit, mods + quality_value + implicit_value, at_most=upper_end)
    return replace(plan, quality_finish=quality, implicit_finish=implicit, limits=(*plan.limits, *said))


def with_methods(target: Target, methods: tuple[str, ...] | None) -> Target:
    """`target` planned with the run's methods setting (#405): the planner reads the methods a run may use from `Target.actions`, which a
    target file never sets; None leaves `target` as it is (every beta method for a target read from a file)."""
    if methods is None:
        return target
    if isinstance(methods, str) or not methods or not all(isinstance(name, str) and name.strip() for name in methods):
        raise PlanError(f"the methods setting must name at least one method (a kind such as chaos-orb, or the label of one action), got {methods!r}")
    return replace(target, actions=tuple(dict.fromkeys(name.strip() for name in methods)))


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
WALK_STAGE = "the walk of every item the actions can reach"
READINGS_STAGE = "the plan made once for each reading of a rule the sources leave open"
LOCK_STAGE = "the check of Hinekora's Lock"
BUILD_STAGE = "the count of the cheapest possible cost"  # the bound's build, as `build_note` says it
BUILD_KEPT = "the cheapest possible cost was worked out only in part, so the search had a weaker bound to cut with"
LOCK_KEPT = "the plan is the best one without the Lock; whether the Lock saves anything was not checked"
SEARCH_KEPT = "the best plan found so far is kept, with the figure below which no plan can cost"
RISK_STAGE = "the work on the cost figures (the median cost and the cost 9 runs in 10 stay under)"
RISK_KEPT = "the figures of the coarser step already worked out are kept, or none when no step was"


def search_net(
    clock: Clock | None, searches: int = 1, give_way=None, states: int | None = None, held: bool = False, walked: bool = False, blind: int | None = None
) -> Net | None:
    """The envelope search's net from the run's clock: the time left (an equal share of it when `searches` searches are still to run: an
    Awakener's Orb's donors and then the target, #832), and the memory and state nets as they are; None when the run has no net. `states`, when
    given, is the search's own states net in place of the budget's (a round's share of a run counted in states, `_rounds.StatesMeter`).

    A run counted in states (`Budget.in_states`, #1101) shares its states as the time net shares its seconds: a search's net is the states left
    on the run's account (`Clock.spend`), an equal share of them when `searches` are still to run, and at least one (a search given one state
    makes its first plan and stops, as one given no time left does); its bound's build may do `Budget.build_per_state` pieces of work per state
    of that net (`Net.pieces`).

    `held` (#1099): the search begins with a plan in hand (a round of `_rounds` after the first plan), so the answer already holds a plan
    (OR-33) and its bound's build keeps no room for the search to make one: on the clock it may take the search's whole net
    (`_envelope_plan.build_stop`), and counted in states it is given the pieces of that whole net, `1 + SEARCH_PER_BUILD` times the quarter
    `build_per_state` stands for. Without it a round's short share cut its build at a quarter: R11's Exalted round had about 20 s, its build
    needs about 6 s, and the round stopped on a weak lower figure with no plan, where the complete bound's first plan costs 188.03 c (#1086).
    Such a build that its share ends nearly done may go past it by `Net.late` times it (#1135, `abstraction._pattern.Growth`): at most
    `LATE`, and at most half of the time the `searches - 1` rounds after it have, so the last round (all the time left) goes past nothing
    and the run keeps its net (OR-40). `walked` (#1224): the plan in hand is one a stopped search walked to (#1142); its build has the same
    net and room, and keeps a quarter of it for the search unless the pace its model grows at ends within that room
    (`abstraction._pattern.Pace.verdict`). `blind` (#1268): the search begins with no plan in hand and `blind` rounds are left, this one
    included: should its bound's build end before it is complete, its search keeps to its share of the net and gives way with no plan
    (`Net.blind`, `_envelope_plan.YIELDED`)."""
    if clock is None:
        return None
    given: Budget = clock.budget
    if given.seconds is None and given.memory_mb is None and given.states is None:
        return None
    left = clock.left()
    pieces = None
    if given.counted:
        if states is None:
            states = max(int(clock.states_left() or 0) // max(searches, 1), 1)
        pieces = max(int(given.build_per_state * (1.0 + SEARCH_PER_BUILD if held or walked else 1.0) * states), 1)
    return Net(
        seconds=left if left is None else left / max(searches, 1), states=given.states if states is None else states, memory_mb=given.memory_mb,
        give_way=give_way, pieces=pieces, held=held, walked=walked and not held, late=min(_pattern.LATE, (max(searches, 1) - 1) / 2.0) if held or walked else 0.0,
        blind=None if held or walked or blind is None or blind <= 1 else blind,
    )  # fmt: skip


def search_gap(clock: Clock | None) -> tuple[float, float | None]:
    """The envelope search's stop at a proved gap from the run's budget (OR-32 as narrowed by OR-39, the dispatcher's decision on #925): the
    budget's gap, applying once the plan's elapsed time has passed its aim (`Budget.aim_seconds`, a setting of the machine): the seconds of the
    aim the run has not yet spent, never below 0. Under the aim the search keeps proving, so a craft whose proof closes inside it is proved the
    cheapest; past it, the search stops at the first round whose plan is proved within the gap. With no aim, from the first round. `(0, None)`,
    the exact search, for a run with no budget or a gap of 0 (`Budget.unlimited()`)."""
    if clock is None or not clock.budget.gap > 0.0:
        return 0.0, None
    aim = clock.budget.aim_seconds
    return clock.budget.gap, 0.0 if aim is None else max(aim - clock.elapsed(), 0.0)


def end_gap(clock: Clock | None) -> float:
    """The gap the search's own rule (`_envelope.Search._beaten`) allows now (`search_gap`): the run's gap once its aim has passed, else 0 (only
    to the certified 1e-6). A stopped round set aside is read against the final plan with it (`_rounds.beaten_later`, #1559, OR-39)."""
    gap, after = search_gap(clock)
    return gap if after is not None and after <= 0.0 else 0.0


def bind_search(clock: Clock | None, info: EnvelopeInfo, given_states: int | None = None) -> None:
    """Record on the clock the limit that stopped the envelope search or its bound's build, when one did (OR-13: the plan says which bound).

    A search that ended at a proved gap met no limit: its own limit says how it ended (`envelope_limits`). In a run counted in states the build
    that its pieces of work stopped and the search that its states net (`given_states`) stopped are each bound in their own unit."""
    ended = info.exact or info.within is not None  # the search ended by itself, not at a net
    if clock is None or (ended and info.bound_stopped is None):
        return
    if not ended:
        what = SEARCH_KEPT
    elif info.exact:
        what = "the cheapest possible cost was worked out only in part; the plan is still the cheapest"
    else:
        what = "the cheapest possible cost was worked out only in part; the plan is still proved within the stated gap of the cheapest"
    if clock.budget.counted:  # each stage names its own count, never seconds (#1101)
        if info.bound_stopped is not None and info.bound_share is not None and info.bound_pieces >= info.bound_share:
            clock.bind(Binding(BUILD_STAGE, PIECES, info.bound_share, info.bound_pieces, BUILD_KEPT if not ended else what))
        if not ended:
            clock.bind(Binding(SEARCH_STAGE, STATES, given_states if given_states is not None else clock.budget.states or 0, info.touched, what))
        return
    found = clock.over(SEARCH_STAGE, what)
    if found is None:  # the net the search met is no longer met now (the memory fell when its graph was let go): say the one it names
        given = clock.budget
        if given.states is not None and info.touched >= given.states:
            found = Binding(SEARCH_STAGE, STATES, given.states, info.touched, what)
        elif given.memory_mb is not None and info.peak_mb is not None and info.peak_mb >= given.memory_mb:
            found = Binding(SEARCH_STAGE, "memory", given.memory_mb, info.peak_mb, what)
        elif given.seconds is None and given.states is not None:  # a run counted in states names no seconds (`Budget.in_states`)
            found = Binding(SEARCH_STAGE, STATES, given.states, info.touched, what)
        else:
            found = Binding(SEARCH_STAGE, "time", given.seconds if given.seconds is not None else 0.0, clock.elapsed(), what)
    clock.bind(found)


def stopped_refusal(clock: Clock | None, binding: Binding) -> str:
    """The `PlanError` of a run its net stopped before any plan closed (OR-33): how long it ran and where it stopped (a run counted in states
    names no seconds: its binding names its count, #1101)."""
    spent = f" after {clock.elapsed():,.0f} s" if clock is not None and not clock.budget.counted else ""
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
    watch: Callable[[Standing], None] | None = None,
    judges_route: bool = False,
    foresee: bool = True,
    round_call: RoundCall | None = None,
    route_actions: tuple[str, ...] | None = None,
    priced_as: Target | None = None,
) -> Plan:
    """Solve the target and measure the risk of the policy.

    `start_price` is the cost of the start item for this run (it wins over the price file);
    `offers` default to `offers_for` the target. Raises `PlanError` when the target asks for the plain quality of a weapon or armour (the
    catalyst quality is planned since #159: as a finish after the mods, `make_plan`, or where that is not exact with the quality in the bound's key
    and a catalyst offered last) or for a corrupted implicit (the Eldritch implicits are planned since #835: the bound's key holds the pair, and the
    Eldritch currencies are offered to a target that asks for one; a base implicit's roll since #1231: as a finish after the mods, `make_plan`, or
    where that is not exact with the roll status in the bound's key and the Blessed Orb an offer), when no offer has a price or no policy reaches the
    goal, and what the layers below raise for a bad input.

    A target that names sockets (ADR-0045, ticket #231) is planned in two parts: the mods as for the same target without sockets, and the socket
    finish solved on its own from the start item's sockets (`_finish.plan_finish`), whose value every goal state adds (`Plan.finish`,
    `Plan.total_mean`). Its refusals (`sockets: any`, a corrupted goal, a mod action that changes sockets, a finish no offered action completes)
    are `PlanError`s too.

    Remove Crafted Mods is kept only when a priced bench craft is, or the start item holds a crafted
    mod: otherwise no crafted mod can ever exist and tracking the junk slots for it would only grow
    the state space. A bought start item is offered again as `restart` from every state; a given one never is (OR-6).

    `aim` (seconds, the budget's aim) is read by nothing on `auto`'s way (#926; the envelope search reads the aim of the clock's budget instead,
    `search_gap`, #925). For a walk asked for by name (`solver="packed"`,
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
    `priced_as` is the target whose start item is priced when the caller gives no price: the target as written, where `target` is it with its
    finishes taken off (`make_plan`). The start item is the same item, but its key is computed from the target, and a catalyst quality narrows
    the window of item levels the key names (R06: `item level 75` with its Intrinsic quality, `75-76` without, #1267), so the price is the
    one of the item the target describes (OR-3).

    `solver` picks the exact solve (ticket #374, #377, #535, ADR-0063): "auto" (the default) is the envelope search wherever its bound can be
    built (`abstraction.pattern_refusal` says before any solve; none refuses it since #833: imprints are held by the key since #833, a roll
    limit and a Divine Orb since #830, an unveil offer since #828), whatever the size of the graph and whatever the `budget`, because that search is exact, ends in seconds on the small
    graphs and expands far less than the walk on the big ones. Where the bound cannot be built, "auto" is the path it was before the envelope search,
    with or without a `budget` (#926: no forecast and no approximate answer; the run's net ends a walk that is too long, and the stop says what the
    search has no bound for, `walk_cause`): the graph is walked on packed arrays (the dearer twins left out with `MIN_OFFERS` offers or more) and
    solved there when it holds more than `_packed.OBJECT_SOLVER_EDGES` transitions (R04, R14, S02) and by the object solver below that.
    There is no fallback once the envelope search has started: a search that cannot answer is a `PlanError` that says why and names
    `solver="packed"`. The number of offers decides nothing: the fossil sets (B1) take the envelope search too, with or without a budget, each offer
    carrying its own floor into it (#829; the bound pruning `solve_pruned` and its switch at 40 offers are retired). A given route judged against the plan (`judges_route`: `--route`, `benchmark`)
    takes the search too, whatever the size of the graph: the route is a fixed policy, evaluated exactly on its own reach (`cli._route.evaluate_route`:
    as objects, or on packed arrays when that reach is too big for objects, #986), so it needs neither the walk nor the planner's choice at the states
    the search proved irrelevant (#829, #986). "object" never packs; "packed" always walks, and with `MIN_OFFERS` offers or more it solves the offers left after the twins are
    merged (the cross-check of the solvers). The means are the same to the certificate; only the cost differs.
    "envelope" is the same search asked for by name: it refuses with `PlanError` an abstraction the bound cannot be built for (#507). It is the
    exact branch-and-bound of OR-12: the walk-free lower bound of #497 (`_pattern_bound`) and a search that expands only the states, and builds
    only the actions, the bound cannot rule out (`_envelope`); it gives the same plan and mean as "packed" and says so in `Plan.limits` (which
    cut ran, what it guarantees). It takes the offers after the twins are merged, as "packed" does, and makes no forecast: with no budget it is exact
    whatever the size, and under one, past the budget's aim, it stops once its plan is proved within the budget's gap of the cheapest
    (`search_gap`, OR-32, OR-39, #826, #925), so a test or a measurement that needs the ladder's approximate answer or the budget refusal names `solver="packed"` or `"object"`. `incumbent` (a state to
    the labels of the offers it takes) is the policy the search completes with a restart for its
    first upper bound (`_envelope_plan.route_incumbent` reads a given route as one); `clock` is the run's clock (`make_plan`), whose net the search
    is given (what is left of its time, its memory and state nets): when it ends the search the plan is the best executable one, `Plan.limits` says
    it is not shown to be the best and gives the lower and upper bounds of its cost.

    With `with_risk` False the policy is solved but its risk (the p50, p90 and CVaR grid, which can take minutes where the solve takes
    seconds) is left out, `Plan.risk` is None, and `add_risk` fills it in later: the choice among start options compares the
    means and measures the risk of the one it keeps (ticket #331).

    When the offers fall in more than one group of the features they add to the model (`_rounds`, #1069), the envelope search widens them in
    rounds and keeps the cheapest plan of every round (`widened_plan`); `round_call` is set on the plan of one round (its share of the time, the
    plan in hand to cut against), which widens nothing itself. A plan a given route is judged against takes the rounds too once the route's
    actions are known (`route_actions`, the labels its rules name, #1110): they lead the first round, as the target's named actions do, so
    every round holds them (the first round is the base of every later one), no round's price cut leaves them out, and the plan's offers and
    model hold every action the route takes. The route is then read on that plan as before, and the answer says whether the first round,
    which held the route's methods, finished (`_rounds.judged_route_limit`): only then is the plan proved no dearer than the route. A judged
    route whose actions are not given (`judges_route` alone) may name any offer, and the offers are searched at once, as before #1110.
    """
    if solver not in SOLVERS:
        raise ValueError(f"solver must be one of {', '.join(SOLVERS)}, got {solver!r}")
    setting = strand_setting(target.start_item, asked=strands)
    if setting.on:
        raise PlanError(
            f"Memory Strands are on ({setting.why}), which the planner cannot plan yet"
            ": the cut and the spend of strands are not built, so an answer would silently ignore them"
        )
    if isinstance(target.quality, PlainQualityRequirement):
        raise PlanError(
            "the target asks for the plain quality of a weapon or armour, which the planner cannot plan yet (the quality currency is not a"
            " method of the planner); it plans the catalyst quality of a ring, an amulet or a belt"
        )
    if any(wish.corrupted for wish in target.implicits):
        raise PlanError(
            "the target asks for a corrupted implicit, which the planner cannot plan yet; it plans the implicits of the base (rolled by a"
            " Blessed Orb) and the Searing Exarch and Eater of Worlds implicits"
        )
    if target.enchantment is not None:
        raise PlanError(
            "the target asks for an enchantment, which the planner cannot plan yet"
        )
    priced_start = target if priced_as is None else priced_as
    price_of_start = start_price_of if start_price_of is not None else resolve_start_price(data, priced_start, prices, start_price, price_source)
    goal = Goal.from_target(target)
    limits: tuple[Limit, ...] = (strands_limit(),)
    if target.quality is not None and lock_wanted(target.actions):  # the run names the Lock, and a burn keeps no quality yet (#159)
        limits += (_limits.lock_with_quality_limit(),)
    mod_names, finish_names = split_names(data, target.start_item, target.actions) if target.sockets is not None else (target.actions, None)
    chosen_here = offers is None  # the planner's own offers (a caller's are searched as given, in one search)
    if offers is None:
        try:
            chosen = offers_for(data, goal, target.base_id, target.start_item, mod_names)
        except ValueError as error:
            raise PlanError(str(error)) from error
        offers, limits = chosen.offers, (*chosen.limits, *limits)
    offers = tuple(offers)  # read twice when a plan without the metamods is made first (`known_upper`)
    priced, dropped = price_offers(offers, prices, price_source)
    priced, same = cheapest_per_class(priced)  # one craft of each class `blocking_crafts` offered (#886): the others are never cheaper
    if same:
        limits += (same_craft_limit(same),)
    if not priced and not target.is_met_by(target.start_item):  # a start that meets the target needs no action (the mods of a quality finish, #159)
        names = sorted({name for drop in dropped for name in drop.missing})
        raise PlanError(f"no action has a price; missing: {', '.join(names)}")
    listing = unopened_listing(data, target.start_item) if price_of_start.bought else None
    if listing is not None:  # ADR-0064: the bought item is the one the market sells, so the plan opens with the draw of its mods
        normal_base = searched_rarity(price_of_start) == "normal"  # the price is a Normal base's: the orb that makes it rare is used and paid (#1522)
        draw = listing_draw(data, listing, target.start_item.rarity, priced, prices, price_source, normal_base=normal_base)
        priced = (*priced, draw)
        if normal_base and not draw.offer.resources:  # the orb that makes the Normal base the rarity has no price: the free draw stands in, said (OR-16, OR-13)
            orb = open_listing(target.start_item.rarity, paid=True)
            limits += unpriced_limits(((orb.label(data), tuple(orb.resources(data)), ""),))
    limits += unpriced_limits((drop.label, drop.missing, drop.kind) for drop in dropped)
    usable, removed = split_usable(data, target.start_item, [p.offer.action for p in priced])
    kept = set(usable)
    if removed:
        limits += unusable_limits(data, ((p.label, p.offer.action) for p in priced if p.offer.action not in kept))
    priced = tuple(p for p in priced if p.offer.action in kept)
    unreachable = eldritch_unreachable(data, goal, target.start_item, ((p.offer.action, p.offer.kind) for p in priced))
    if unreachable:
        raise PlanError(unreachable)  # an exact refusal: the search would only run to its net (#835)
    limits += start_limits(price_of_start)
    if target.sockets is not None and solve_it:  # the finish uses the socket kinds: they are not "methods the planner cannot use yet", in a
        limits = without_finish_kinds(limits)  # plan searched in rounds too (#886: the rounds keep the limits given here)
    if price_of_start.bought:
        bought = price_of_start.name or "start item"
        restart = Offer(RESTART, BuyStartItem(listing or target.start_item), {bought: 1}, shares=False)
        parts = price_of_start.made.goods if price_of_start.made is not None else ((bought, 1, price_of_start.chaos, price_of_start.source),)
        marks = ((bought, price_of_start.mark),) if price_of_start.mark else ()
        priced = (*priced, PricedOffer(restart, price_of_start.chaos, parts, marks))
        # OR-42: starting over may wipe the item in hand instead, where that is cheaper; it is offered beside the restart, which stays at every
        # state (a wipe is an action only where its Scouring gives the start back: `_prune.wipe_lands`)
        wipe = start_over_wipe(data, target.start_item, listing, paid=listing is not None and normal_base)
        if wipe is not None:
            wiped, _ = price_offers((wipe_offer(data, wipe, listing or target.start_item),), prices, price_source)
            if wiped and wiped[0].cost < price_of_start.chaos:
                priced = (*priced, *wiped)
    # a route judged against the plan: no price cut, since the route may name the offer it would leave out; a round of the rounds is cut, and its
    # cut keeps the route's offers (`route_actions`)
    judged = incumbent is not None or judges_route or (route_actions is not None and round_call is None)
    # a route whose actions are not known may name any offer, and an incumbent is a policy over every offer: those are searched at once
    unknown_route = incumbent is not None or (judges_route and route_actions is None)
    if round_call is None and chosen_here and rounds_apply(data, target, priced, solve_it=solve_it, judged=unknown_route, solver=solver):
        own = {id(offer) for offer in offers}
        grouped = tuple(p.offer for p in priced if id(p.offer) in own)
        groups = offer_groups(data, goal, target, grouped, route_actions or ())
        if len(groups) > 1:  # the offers refine the model in more than one way: they are searched in rounds (#1069)
            # the rounds grow from the plan in hand first (`_growth`, #1414): its table reads the offers with their costs, in the rounds' order
            grower = rounds_grower(data, goal, target, tuple(p for p in priced if id(p.offer) in own), listing, route_actions or ())
            return widened_plan(
                data, target, prices, groups, grouped, limits, aim=aim, rates=rates, strands=strands, price_of_start=price_of_start,
                price_source=price_source, solver=solver, with_risk=with_risk, clock=clock, watch=watch, foresee=foresee, route_actions=route_actions,
                grower=grower,
            )  # fmt: skip
    if round_call is not None and round_call.upper is not None and price_cut_applies(data, target, priced, price_of_start, solve_it=solve_it, judged=judged):
        # cut against the plan in hand (`_rounds`); a judged route's offers are kept, since the route is read on the plan's offers (#1110)
        priced, cut = restart_dominated(priced, price_of_start.chaos, round_call.upper, keep=frozenset(route_actions or ()))
        if cut:
            limits += (price_cut_limit(cut, price_of_start.chaos, round_call.upper),)
    # a metamod craft the target did not ask for, offered by the rule of blocking crafts (#886), makes the model track every mod's protected tags on
    # every state (#1069), and an offer that reads a rule the sources leave open makes the plan one search per reading of it (#1111): a plan
    # without those offers is made first, and each offer that a restart and that plan beat is left out (`_price_cut`); a plan without the offers
    # that read an axis costs the same at every reading, so its figure holds at each
    speculative = lambda offer: (offer.blocks is not None and adds_metamod(data, offer.action)) or reads_open_rule(data, offer)  # noqa: E731
    if round_call is None and price_cut_applies(data, target, priced, price_of_start, solve_it=solve_it, judged=judged) and any(
        speculative(p.offer) for p in priced
    ):
        known = plan_without(
            data, target, prices, offers=tuple(o for o in offers if not speculative(o)), aim=aim, rates=rates, strands=strands,
            start_price_of=price_of_start, price_source=price_source, solver=solver, clock=clock,
        )  # fmt: skip
        if known is not None and known.search is not None and known.search.stopped is not None:
            # the run's net stopped the plan without them: no time is left to try them, and that plan is the answer (OR-33, OR-13)
            untried = tuple(sorted({p.label for p in priced if speculative(p.offer)}))
            own = (*limits, *(limit for limit in known.limits if limit not in limits))  # what the offers' choice said is said of this plan too
            plan = replace(known, limits=(*own, untried_limit(untried)))
            return add_risk(plan) if with_risk else plan
        upper = None if known is None else known_upper(known)
        if upper is not None:
            priced, cut = restart_dominated(priced, price_of_start.chaos, upper)
            if cut:
                limits += (price_cut_limit(cut, price_of_start.chaos, upper),)

    enabled = [p.offer.action for p in priced if (reads := p.offer.action.reads(data)).junk or reads.item_state]
    awakened = awakener_offers(priced)  # the Awakener's Orbs: each donor is searched on its own and priced into its orb (#832, `_awakener`)
    donated = tuple(
        p for p in priced if not isinstance(p.offer.action, BuyStartItem) and takes_inputs(p.offer.action) and p not in awakened
    )  # offers that take donors (#225)
    holds_metamod = bool(target.start_item.metamods(data) & BLOCKING)
    # a planned axis is answered at its plan reading (the abstraction's default), its claim an approximate input (OR-11, OR-23); any other
    # axis is solved at every reading of its grid by the interval driver (#589, ADR-0012, ADR-0022): the plan is the route at the plan reading
    axes = interval_axes(data, priced)
    if not axes:  # donors are planned by the interval driver only (#225); an action with inputs and no axis stays a gap of its own (G6)
        donated = ()
    if axes and solver not in ("auto", "object", "envelope"):
        raise PlanError(
            f"an offered action reads a rule the sources leave open ({', '.join(axis_what(axis.name) for axis in axes)}), so the plan is "
            f"made once for each reading of that rule by the envelope search (or by the walk of every item, `--solver object`); `--solver {solver}` does not do that"
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
            allow_inputs=bool(donated) or bool(awakened),
            reading=reading,
        )

    abstraction = model()
    start = abstraction.compress(listing or target.start_item)
    if round_call is not None and round_call.floors:  # only the figure the rounds order the groups by (`_rounds.by_floor`, #1135)
        # asked before the finish is solved (the floors need no finish): its net is what is left of the order pass's share (#1241)
        net = search_net(clock, round_call.searches, states=round_call.states, held=True)
        if net is not None and net.seconds is not None and round_call.seconds is not None:
            net = replace(net, seconds=min(net.seconds, round_call.seconds))
        raise _rounds.Floor(offers_floor(abstraction, start, priced, target.start_item, build_stop(net, time.perf_counter()), None if net is None else net.pieces))
    finish = None
    if target.sockets is not None and solve_it:  # the finish is solved on its own and added to every goal state (ticket #231, ADR-0045)
        try:
            finish = plan_finish(
                data, target, prices, price_source, names=finish_names, goal_takes_corrupted=goal.takes_corrupted,
                mod_actions=[p.offer.action for p in priced if not isinstance(p.offer.action, BuyStartItem)],
            )  # fmt: skip
        except (FinishRefused, OutOfScopeError, ArithmeticError) as error:  # ArithmeticError: the finish did not converge
            raise PlanError(str(error)) from error

    if not solve_it:
        unsolved = Solution({start: float("inf")}, {}, float("inf"))
        return Plan(target, abstraction, leaf_labels(target), prices, start, price_of_start, priced, limits, unsolved, None, 0.0, 0.0, finish=finish)
    if donated and solver not in ("auto", "object"):
        raise PlanError(f"an offered action takes donors, so the plan is made by the search that holds every item it reaches; `--solver {solver}` does not do that")
    donors: tuple[Donor, ...] = ()
    unfolded = priced
    if awakened:  # each donor first, by the same search (#832): the orb is then an ordinary offer whatever solver takes the target
        # a donor stops as the target does (past the aim, at a proved gap) on its share of the net; its [lower, upper] goes into `whole_lower`
        # in a round of a run counted in states the donors share the round's own share of the states with its search (#1101)
        share = None if round_call is None or round_call.states is None else round_call.states
        spent_before = 0 if clock is None else clock.spent
        donors, left_out = solve_donors(
            abstraction, awakened, priced, net=lambda searches: search_net(clock, searches, states=None if share is None else max(share // searches, 1)),
            stop=lambda: search_gap(clock), spend=None if clock is None else clock.spend,
        )  # fmt: skip
        if share is not None and clock is not None:
            round_call = replace(round_call, states=max(share - (clock.spent - spent_before), 1))  # the round's search has what its donors left
        kept_orbs = {d.action for d in donors}
        priced = fold(tuple(p for p in priced if p not in awakened or p.offer.action in kept_orbs), donors)
        limits += left_out + donor_limits(donors, donor_base_cost(unfolded))
    refusal = pattern_refusal(abstraction) if not axes else "the plan reads a rule axis"  # searched per reading below (#589, #1111)
    # "auto" is the envelope search wherever its bound can be built (#535), a plan a given route is judged against included: the route is evaluated on
    # its own reach, as objects or packed (#829, #986). The number of offers decides nothing (#829): the fossil sets take the envelope search with or
    # without a budget.
    envelope = solver == "envelope" or (solver == "auto" and refusal is None)
    # why `auto` walks every item instead of searching, said when a net stops that walk before a plan closed (OR-13, #926)
    unbounded = () if refusal is None else refusal_causes(abstraction, player=True) or (refusal,)  # the causes in a player's words, else the refusal's own text
    walks_because = None if solver != "auto" or envelope or axes else walk_cause(unbounded)
    # The forecast of ADR-0023 and its ladder of approximate answers are retired (direction of 2026-11-13) and `auto` never reaches them (#926):
    # under a budget it is the envelope search, or, where that search cannot take the target, the same walk as with no budget, to the run's net.
    # They stand only behind a walk asked for by name, for the tests and measurements of the ladder itself, until #928 deletes them.
    if aim is not None and solver in FORECAST_SOLVERS and not axes:
        forecast = merged = priced
        merged_twins: list[tuple[str, str]] = []
        if PRUNE_BOUND and len(priced) >= MIN_OFFERS:  # the walk and an approximate answer are made of the offers after the twins
            merged, merged_twins = (tuple(each) for each in merge_twins(data, target.start_item, priced))
            forecast = merged
        decision = decide(abstraction, start, forecast, aim, rates)
        if decision.message:
            limits += (whole_search_limit(decision.message, decision.detail),)
        if decision.rate_why:
            limits += (guessed_rate_limit(decision.rate_why, decision.rate_detail),)
        if decision.action == "refused":
            if solver == "object":
                raise PlanError(decision.message)
            # no coarse level exists and the graph is beyond the object solver: the packed solver holds it (ticket #70, ADR-0063), so the
            # answer is exact and takes the walk's minutes instead of being refused
            limits = with_limits(limits, (whole_search_limit(_packed_note(decision), decision.detail),), _limits.SOLVE)
        if decision.action == "approximate":
            try:
                with stage(APPROXIMATE_STAGE):
                    solved = climb(decision, start, merged)
                wanted = lock_wanted(target.actions) and not abstraction.tracks_quality  # a burn keeps no quality yet (#159)
                burn = plan_burn(data, target.start_item, abstraction, prices, price_source, sockets=target.sockets is not None) if wanted else None
                foresight = coarse_check(solved.solution.values, lock_price(prices, price_source), cheapest_cost(merged, burn), wanted)
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
    packed = None
    readings = None
    donor_plan = None
    many = PRUNE_BOUND and len(priced) >= MIN_OFFERS
    # every stage below stops at the run's net (#825): `make_plan` says a stop before a plan closed, "no plan found yet", with where (OR-33)
    if axes:
        # each reading is searched by the envelope search (#1111): a reading costs its search, never the whole graph; the offers that take donors
        # (the recombinator, a deferred method, OR-37) and the object solver asked by name still solve every reading whole
        searches: list[PackedResult] = []
        search = None if donated or solver == "object" else reading_search(
            abstraction, start, priced, clock, watch, searches, solver, readings_count(axes), item=target.start_item if many else None
        )  # fmt: skip
        # each search stops at its own share of the net and keeps its plan, and the routes are then compared on what they reach, which a stop
        # there would throw away (OR-33); the whole walk stops at the net as it always did
        with stage(READINGS_STAGE, SEARCH_KEPT, stops=search is None):
            try:
                readings, others, product = solve_each_reading(abstraction, model, start, priced, axes, donors=donated, search=search)
            except Uncovered:  # a reading's outcomes reach what another reading's search never held: every reading is solved whole (#1111)
                search = None
                with stage(READINGS_STAGE):
                    readings, others, product = solve_each_reading(abstraction, model, start, priced, axes, donors=donated)
        solution = readings.solution
        if search is not None:  # the plan is the plan reading's search from the start (the first search made), its risk the packed one
            packed = searches[0]
            solution = packed.solution
            limits += envelope_limits(packed.info["envelope"]) + _packed.evaluation_limits(packed.info)
        if product is not None:  # the solve was over the product of the target and its donors: the plan's own process is read off it
            donor_plan = DonorPlan(product, product.start(start), readings.solution)
            solution = main_view(readings.solution)
            limits += (_limits.feeder_donors_limit(), _limits.free_donor_base_limit(), _limits.second_items_shown_limit())
        limits += reading_limits(abstraction, others, aim is not None and search is None)
        offered = None  # the second solve of a Lock takes the offers after the twins, without the bound pruning (`_foresight`)
    else:
        offered, twins = (tuple(each) for each in merge_twins(data, target.start_item, priced)) if many else (priced, ())
        if twins:
            limits += (twins_limit(twins),)  # G17: the dearer twins are left out of the search and the walk
        if envelope:
            net = search_net(clock, round_call.searches, round_call.give_way, round_call.states, round_call.held, round_call.walked, round_call.blind) if round_call is not None else search_net(clock)
            try:
                with stage(SEARCH_STAGE, SEARCH_KEPT, stops=False):  # the search stops at its own net (`search_net`) and keeps its plan
                    gap, gap_after = search_gap(clock)
                    packed = envelope_result(
                        abstraction, start, offered, prune_corrupting=PRUNE_CORRUPTING, incumbent=incumbent,
                        net=net, item=target.start_item if many else None, gap=gap,
                        gap_after=gap_after, watch=watch if round_call is None or round_call.watched else None,
                        beaten_at=round_call.upper if round_call is not None else None,
                    )  # fmt: skip
            except (OutOfScopeError, NoPolicy, BoundError, ConvergenceError) as error:
                if round_call is None and clock is not None:  # a round's states are counted by the rounds (`_rounds.StatesMeter`)
                    clock.spend(getattr(error, "states", 0))
                raise PlanError(envelope_refusal(solver, error)) from error
            packed.info["envelope"] = whole_info(packed.info["envelope"], unfolded, donors)  # the target and its donors together (`_awakener`)
            limits += envelope_limits(packed.info["envelope"])
            if round_call is None:  # a round's stop is said by the rounds (`widened_plan`), and its states counted there
                bind_search(clock, packed.info["envelope"], None if net is None else net.states)
                if clock is not None:
                    clock.spend(packed.info["envelope"].touched)
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
    elif not foresee or round_call is not None:  # a plan made only for its mean without the Lock (`plan_without`, a round: #1069)
        status = LockStatus.STOPPED if lock_wanted(target.actions) else LockStatus.SWITCHED_OFF
        foresight, with_lock = Foresight(status, lock_price(prices, price_source)), None
    else:
        foresight, with_lock = lock_foresight(data, target, prices, abstraction, start, solution, priced, offered, price_source, clock)
    if with_lock is not None and readings is not None:
        raise PlanError(
            "the cheapest plan takes Hinekora's Lock, and a plan made once for each reading of a rule the sources leave open "
            "cannot take the Lock yet. To see the best plan without the Lock, name the methods to use in the run's setting (`--methods`) without `hinekora-lock`"
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
        solution, risk, solve_seconds, risk_seconds, None, packed=packed, readings=readings, foresight=foresight, finish=finish, donors=donor_plan,
    ))


def lock_foresight(data, target, prices, abstraction, start, solution, priced, offered, price_source, clock, fallback=None):
    """What the plan finds about Hinekora's Lock (`plan_foresight`), and the plan with the Lock when it takes it; a stop of the run's net keeps
    the plan without the Lock and the clock lists the stop (OR-33). In a run counted in states the check walks at most the run's states net
    (`Budget.states`) of states of its own, one per checkpoint, and a stop there names that count (#1101): the search before it may have used
    the whole net, and under the time net the check takes what the search left."""
    try:
        with stage(LOCK_STAGE, LOCK_KEPT, states=clock.budget.states if clock is not None and clock.budget.counted else None):
            return plan_foresight(data, target, prices, abstraction, start, solution, priced, offered, price_source, fallback=fallback)
    except BudgetExceeded as stop:  # a plan has closed: it is kept, without the Lock, and the clock lists the stop (OR-33)
        if clock is not None:
            clock.bind(stop.binding)  # a stop a forked worker met was bound on its own copy of the clock
        return Foresight(LockStatus.STOPPED, lock_price(prices, price_source)), None


def plan_fallback(solution: Solution, offered: Sequence[PricedOffer]) -> tuple[PricedOffer, ...]:
    """The offers of `offered` the plan's policy takes somewhere: the fallback of the Lock's gains for N of a plan searched in rounds (#1080).

    The plan is chosen before its Lock is foreseen. The gains of N read the Lock-free values at the states the plan visits, and their fallback
    is what the player does after a peek he does not take; built over every offer of the plan's round, it made the kernel of each offer at each
    of up to `GAIN_STATES` states (R05: 85 offers, about 100 s and 8 GB after the net, #1091). Over the plan's own crafts each gain is still what
    one Lock saves there (a peek, then the option or one of the plan's own crafts or the burn), so each is a true "would pay below"; only the
    largest over every craft is not proved, and the Lock line's `n_exact` says so. The options of a peek, the exact pruning and the second solve
    still read every offer: the Lock's status and a plan with the Lock are as before. A packed policy names its offers without building an
    action at each of its states (`PackedPolicy.offers`): building them would cost what this saves."""
    policy = solution.policy
    taken = getattr(policy, "offers", None)
    used = {priced.label for _, priced in taken()} if taken is not None else {action.label for action in policy.values()}
    return tuple(priced for priced in offered if priced.label in used)


def rounds_apply(data: GameData, target: Target, priced: Sequence[PricedOffer], *, solve_it: bool, judged: bool, solver: str) -> bool:
    """Whether the offers may be searched in rounds (`_rounds`, #1069): a plan the envelope search solves, of one reading (no rule axis), with no
    offer that takes donors other than an Awakener's Orb, and no route judged against it whose actions are not known (`judged`: such a route,
    or an incumbent, is a fixed policy that may name any offer; a route whose actions are known leads the first round instead, #1110). An
    Awakener's Orb is searched in the rounds that hold it, its donor searched inside that round's share (`_make_plan`, #1101); refusing the
    rounds for it made a target offered one a single search of every offer, which the growth never reached (#1426, R14)."""
    if not solve_it or judged or solver not in ("auto", "envelope"):
        return False
    if interval_axes(data, priced):
        return False
    orbs = {id(p) for p in awakener_offers(priced)}
    return not any(takes_inputs(p.offer.action) for p in priced if not isinstance(p.offer.action, BuyStartItem) and id(p) not in orbs)


def offer_groups(data: GameData, goal: Goal, target: Target, offers: Sequence[Offer], route: Sequence[str] = ()) -> tuple[_rounds.Group, ...]:
    """The groups of `offers` by the features each adds to the target's own model (`Abstraction.features`, `_rounds.round_groups`). An offer
    that reads neither the junk nor the item's state is never in the model (`_make_plan`'s `enabled`) and adds nothing. `route` are the
    labels a judged route names (#1110): they lead the first group with the target's named actions."""
    holds = bool(target.start_item.metamods(data) & BLOCKING)

    def model(actions) -> Abstraction:
        return Abstraction(
            data, goal, target.base_id, target.item_level, actions, metamods=holds, enchantment=target.start_item.enchantment, allow_inputs=True
        )  # fmt: skip

    own = model(()).features()
    known: dict = {}

    def added(offer: Offer) -> frozenset[str]:
        reads = offer.action.reads(data)
        if not (reads.junk or reads.item_state):
            return frozenset()
        try:
            key = (reads, offer.action.adds(data))
            hash(key)
        except TypeError:
            key = None
        if key is not None and key in known:
            return known[key]
        try:
            found = model((offer.action,)).features() - own
        except (ValueError, OutOfScopeError) as error:  # a model of this offer alone is refused (an unveil offer needs a junk reader): a group of its own
            found = frozenset({f"refused alone: {error}"[:120]})
        if key is not None:
            known[key] = found
        return found

    return _rounds.round_groups(offers, (*(target.actions or ()), *route), added)


def rounds_grower(
    data: GameData, goal: Goal, target: Target, priced: Sequence[PricedOffer], listing: Item | None, route: Sequence[str] = ()
) -> _growth.Grower | None:
    """The plan-led growth of the rounds (`_growth`, #1414) over `priced` (the rounds' offers with their costs, in their order): the table of
    what each offer declares, and the positions of the run's named offers (the target's actions and a judged route's labels, as
    `_rounds.round_groups` names them), which every round holds. None when no wanted mod is open at the start (nothing to grow)."""
    if not _growth.GROWS:
        return None
    names = {*(target.actions or ()), *route}
    try:
        table = _growth.growth_table(data, goal, target, priced, listing, ask=checkpoint)
    except (ValueError, OutOfScopeError, NotApplicableError, BudgetExceeded):
        # the growth only orders what is searched first: a table it cannot read (a model refused, a net spent while reading it) leaves the
        # rounds to main's widening, which says itself what the model makes of the offers, and what a spent net stopped (#1414)
        return None
    if not table.open:
        return None
    asked = [i for i, p in enumerate(priced) if p.offer.label in names or (p.offer.kind in names and p.offer.blocks is None)]
    return _growth.Grower(table, asked)


def round_end(plan: Plan) -> tuple[str, str]:
    """How a round's plan ended (`_rounds.widen`): closed (exact, or a walk), within the gap, or stopped, with the reason."""
    info = plan.search
    if info is None or info.exact:
        return _rounds.CLOSED, ""
    if info.within is not None:
        return _rounds.WITHIN, f"proved within {info.within:.2%} of the cheapest of its methods"
    reason = info.stopped or "the search was stopped"
    if info.bound_share is not None and info.bound_stopped is not None:  # a run counted in states names its build's count too (#1101, OR-13)
        reason += f"; {BUILD_STAGE} it cut with was stopped too: {info.bound_stopped}"
    return _rounds.STOPPED, reason


def release_round(plan: Plan) -> None:
    """What a finished round's plan lets go of before the next round (`_rounds.widen`'s `release`, #1076): its abstraction's memos
    (`Abstraction.release_memos`). The plan keeps its policy, its figures and its abstraction, whose kernels the answer's later steps (the Lock,
    the risk, the route page) make again as they ask them."""
    abstraction = getattr(plan, "abstraction", None)
    if abstraction is not None:
        abstraction.release_memos()


def widened_plan(
    data: GameData, target: Target, prices: PriceFile, groups: Sequence[_rounds.Group], grouped: tuple[Offer, ...], limits: tuple[Limit, ...], *,
    price_of_start: StartPrice, clock: Clock | None, with_risk: bool, watch, foresee: bool, route_actions: tuple[str, ...] | None = None,
    grower: _growth.Grower | None = None, **kwargs,
) -> Plan:
    """The plan of `groups` of `grouped` searched in rounds (`_rounds`, #1069): the cheapest plan of every round, with the Lock foreseen and its
    risk, and the answer says over which methods it is proved and which rounds were set aside or not tried (OR-13). `limits` are what the choice
    of the offers said; `kwargs` go to each round's `_make_plan`. `route_actions` are the labels of a route judged against the plan (#1110):
    the first group holds them, each round's price cut keeps them, and the answer says what the first round proved against the route."""

    def run(chosen: tuple[Offer, ...], call: RoundCall) -> Plan:
        try:
            return _make_plan(
                data, target, prices, start_price=None, offers=chosen, solve_it=True, start_price_of=price_of_start, with_risk=False,
                incumbent=None, clock=clock, watch=watch, judges_route=False, foresee=False, round_call=call, route_actions=route_actions, **kwargs,
            )  # fmt: skip
        except PlanError as error:  # the search's `NoPolicy`: a net stopped it before a plan closed (a stop), or no plan of the offers exists
            cause = error.__cause__
            while cause is not None and not isinstance(cause, NoPolicy):
                cause = cause.__cause__
            stopped = cause
            while stopped is not None and getattr(stopped, "stopped", None) is None:
                stopped = stopped.__cause__ if isinstance(stopped.__cause__, NoPolicy) else None
            if stopped is not None:
                raise _rounds.Stopped(stopped.stopped, stopped.lower) from error
            if cause is not None and cause.__cause__ is None:  # the search's own proof, its bound whole: no plan of these offers reaches the target
                raise _rounds.NoPlan(str(error)) from error
            raise

    def floor(chosen: tuple[Offer, ...], call: RoundCall) -> float | None:
        try:
            run(chosen, call)
        except _rounds.Floor as figure:
            return figure.figure
        return None  # (a refusal or a net before the floors is `_rounds.figure_of`'s: the group then has no figure)

    meter = states_meter(clock)
    widened = _rounds.widen(
        groups, grouped, run, upper_of=known_upper, mean_of=lambda plan: float(plan.mean_remaining), ended=round_end,
        left=(lambda: None) if clock is None else clock.left, clock_now=time.perf_counter if clock is None else clock.elapsed, meter=meter,
        gap=0.0 if clock is None else clock.budget.gap, floor=floor, release=release_round, grow=grower, end_gap=lambda: end_gap(clock),
    )  # fmt: skip
    if widened.plan is None:
        said = _rounds.no_plan_words(widened.records)
        if said is not None:  # a net stopped a round, or left one untried: no plan found yet, never "no plan reaches the goal" (#1168, OR-33)
            if isinstance(widened.error, BudgetExceeded) and clock is not None:
                clock.bind(widened.error.binding)  # as `make_plan` binds a stop that reaches it (a forked worker's was bound on its own clock)
            spent = f" after {clock.elapsed():,.0f} s" if clock is not None and not clock.budget.counted else ""
            raise PlanError(f"stopped{spent}, {NO_PLAN}: {said}") from widened.error  # as `stopped_refusal` says a stop (OR-33's example)
        raise widened.error if widened.error is not None else PlanError("no round of the offers made a plan")
    plan, records = widened.plan, widened.records
    closed = _rounds.all_closed(records)
    if not closed and clock is not None and (spent := clock.over(SEARCH_STAGE, SEARCH_KEPT)) is not None:
        # the run's net ended the rounds with a plan in hand: the answer is that plan, and it says the net stopped the run (OR-13, OR-33, #1566).
        # Each round's line says how it ended; this is the run's own stop, listed with the stages a limit stopped. Rounds that all closed were
        # not stopped, even when the clock is past the net by the time they are read
        clock.bind(spent)
    withins = [record.within for record in records if record.within is not None]
    within = max(withins) if withins else None  # a finished round proved within the gap: what the rounds prove is proved only to that gap
    exact = closed and not withins
    # the plan is proved within that gap of the cheapest of every method only when every round closed (the last then held every offer); when one
    # did not, a round's gap proves the plan only against the methods of the rounds that finished (the rounds' limit says so), never against
    # the cheapest, so the search reads as stopped, not "within" (#1182, #1186: R17 82,832.74 c and R20 35,058,370.98 c were recorded "proved
    # within 1%" over a lower figure of 0 after the start item, from a first round of chaos and essences that closed within 1% while the
    # rounds of the methods the guides use were stopped)
    proved_within = within if closed else None
    # the winner's own word on how its search ended holds over the whole only when every round closed exactly; otherwise the rounds say it (OR-13)
    own = (*limits, *(limit for limit in plan.limits if limit not in limits and (exact or limit.kind != _limits.SOLVE)))
    info = plan.search
    if info is not None:
        last = records[-1]
        upper = certified_upper(info)
        lower = min(last.lower if last.lower is not None else 0.0, upper) if closed else 0.0  # the last round held every offer when all closed
        plan.packed.info["envelope"] = replace(
            info, exact=exact, within=proved_within, stopped=None if closed else "not every round of the methods finished", lower=lower, widening=records,
            offered=len(grouped),
        )  # fmt: skip
    judged = () if route_actions is None else (_rounds.judged_route_limit(sorted({o.label for o in grouped} & set(route_actions)), records[0]),)
    plan = replace(plan, limits=(*own, *_rounds.rounds_limits(records, exact, within), *judged))
    if foresee:
        offered = merge_twins(data, target.start_item, plan.offers)[0] if PRUNE_BOUND and len(plan.offers) >= MIN_OFFERS else plan.offers
        fallback = plan_fallback(plan.solution, offered)
        foresight, with_lock = lock_foresight(
            data, target, prices, plan.abstraction, plan.start, plan.solution, plan.offers, tuple(offered), kwargs["price_source"], clock, fallback
        )  # fmt: skip
        if foresight.n is not None and len(fallback) < len(offered):
            foresight = replace(foresight, n_exact=False)  # N's gains read only the plan's own crafts after a peek: each is true, the largest unproved
        plan = replace(plan, foresight=foresight) if with_lock is None else replace(plan, foresight=foresight, solution=with_lock, packed=None)
    return add_risk(plan) if with_risk else plan


def states_meter(clock: Clock | None) -> _rounds.StatesMeter | None:
    """The rounds' meter in states when the run counts its work in states (`Budget.in_states`: a states net and no time net), so that no round
    reads the clock and the plan is the same on every machine (#886); None for a run on the clock (a user's run: the site and the command). The
    rounds share the states left on the run's account (`Clock.spend`), what an earlier search of the run (a start option's) did not use (#1101)."""
    if clock is None or not clock.budget.counted:
        return None
    return _rounds.StatesMeter(int(clock.states_left() or 0), clock)


def price_cut_applies(data: GameData, target: Target, priced: Sequence[PricedOffer], start: StartPrice, *, solve_it: bool, judged: bool) -> bool:
    """Whether the premise of the price cut holds for this plan (`_price_cut`, #1069): a bought start item (a restart at every state but the
    start), no offer that searches a second item with a restart of its own (an
    Awakener's Orb's donor, an offer that takes donors: there the restart is not the start item's), no route judged against the plan (a route is a
    fixed policy and may name the offer), and a start item that holds no metamod (its model tracks the protected tags anyway). Offers that read a
    rule axis do not stop it (#1111): the figure cut against is then of a plan without them (`reads_open_rule`), which costs the same at every
    reading, so the cut holds at each."""
    if not (solve_it and start.bought and not judged) or target.start_item.metamods(data) & BLOCKING:
        return False
    if awakener_offers(priced):
        return False
    return not any(takes_inputs(p.offer.action) for p in priced if not isinstance(p.offer.action, BuyStartItem))


def plan_without(data: GameData, target: Target, prices: PriceFile, *, offers: tuple[Offer, ...], **kwargs) -> Plan | None:
    """The plan of `offers` alone, without Hinekora's Lock and without its risk (#1069, `_price_cut`); None when it cannot be made (a refusal):
    then nothing is cut. It shares the run's clock (OR-33): the time it takes is the run's, and a net that stops it leaves the run no time."""
    try:
        return _make_plan(
            data, target, prices, start_price=None, offers=offers, solve_it=True, with_risk=False, incumbent=None, watch=None, foresee=False, **kwargs
        )  # fmt: skip
    except PlanError:
        return None


def known_upper(plan: Plan) -> float | None:
    """A certified upper figure of the cheapest cost from the start (after the start item) of every set of offers that holds the plan's own: the
    mean of `plan` (a plan without the Lock) with its certified error added. None for a plan whose mean is not a certified figure (an approximate
    answer of the retired ladder) or is not finite."""
    mean = float(plan.mean_remaining)
    if plan.approximation is not None or not math.isfinite(mean):
        return None
    search = plan.search
    return certified_upper(search) if search is not None and not search.exact else mean * (1.0 + ACCEPT_BOUND)


def untried_limit(labels: tuple[str, ...]) -> Limit:
    """The limit of the metamod crafts a plan never tried because the run's net stopped the plan made without them first (#1069, OR-13)."""
    return Limit(
        _limits.UNTRIED,
        "Not tried",
        "the run's time, states or memory limit was reached by the plan made without them first, to price them against",
        "The plan is the one without these crafts; one of them might make it cheaper.",
        labels,
    )


def interval_axes(data: GameData, priced: Iterable[PricedOffer]) -> tuple[Axis, ...]:
    """The rule axes the offered actions read that are not `planned` (ADR-0033), by name: the ones the plan is solved at every reading of (#589)."""
    found: dict[str, Axis] = {}
    for each in priced:
        for axis in each.offer.action.rule_axes(data):
            if not axis.planned:
                found.setdefault(axis.name, axis)
    return tuple(found[name] for name in sorted(found))


def reads_open_rule(data: GameData, offer: Offer) -> bool:
    """Whether `offer`'s action reads a rule axis the plan is made at every reading of (one not `planned`, `interval_axes`)."""
    return any(not axis.planned for axis in offer.action.rule_axes(data))


def solve_each_reading(
    abstraction: Abstraction,
    model: Callable[[Reading], Abstraction],
    start: CompressedState,
    priced: Sequence[PricedOffer],
    axes: Sequence[Axis],
    *,
    donors: Sequence[PricedOffer] = (),
    search: Callable[[Reading, Abstraction, CompressedState], PackedResult] | None = None,
) -> tuple[IntervalReport, tuple[Abstraction, ...], Acquisition | None]:
    """Solve the plan once for each reading of `axes` and cross-evaluate the routes (`risk.solve_readings`, ADR-0012, ADR-0022; #589).

    A reading is one value of each axis (their product, the plan reading first); an axis that is `planned` stays at its plan value in every
    one (OR-11). `abstraction` is the model of the plan reading (its `reading` None); each other reading gets its own, `model(reading)`, of the
    same target and enabled actions, so every kernel is taken at that reading. Without `search` each model is solved whole by the object solver
    (the offers that take donors, and `--solver object`); the solve is exact; no comparison route is asked, since the planner offers no action with inputs.
    Offers with an equal kernel are not merged (`merge_equal`): the routes are compared across readings by their offers' labels, and an offer
    merged away at one reading could leave a route with no action there.

    With `donors` (the offers among `priced` that take donors, ticket #225) each reading's model is the product of the target and its donors'
    processes (`DonorModel` under `solver.Acquisition`, every donor the offers name offered at once: they are the target's few isolated feeders,
    and a recombination is offered only on an item in hand that is one too, `feeders_only`: the guides' own feeders, and a product that stays small),
    an acquisition ends at the first state with the donor's key (`Abstraction.reaches_donor`), the driver starts from the target's own process,
    and the best route without the actions that take donors is solved beside the plan (ADR-0012's comparison route). The report is then over
    product states. Returns the driver's report, the abstractions of the other readings and the plan reading's product (None without donors).

    With `search` (no donors) each reading is solved by the envelope search instead of whole (#1111): `search(reading, abstraction, state)` is
    the search of that reading's model from `state`, made once per reading from the start. A reading costs its search, not its whole graph, and
    the routes are compared on the states the candidates reach (`risk.solve_readings`, `solve_one`); each reading's lower figure is the one its
    search proved (`reading_solution`). When a candidate reaches under another reading a state its own search never held (the outcomes of an
    action that reads the axis have another support there), `Uncovered` is raised: a search from that state would restart at it and not at
    the start item, so the caller solves the readings whole instead.
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
    solve_one = None
    if search is not None and not donors:
        searched: dict[Reading, PackedResult] = {}

        def solve_one(reading: Reading, starts: list[CompressedState]) -> Solution:
            if len(starts) > 1:  # a candidate reaches under another reading a state its own search never held (`Uncovered`)
                raise Uncovered(starts[1:])
            if reading not in searched:
                searched[reading] = search(reading, abstractions[reading], start)
            return reading_solution(searched[reading], start)

    try:
        report = solve_readings(models, root, plan=plan, without=without, solve_one=solve_one)
    except (OutOfScopeError, ConvergenceError) as error:
        raise PlanError(f"the plan could not be made at every reading of the rule axis {', '.join(names)}: {error}") from error
    others = tuple(each for reading, each in abstractions.items() if reading != plan)
    return report, others, (models[plan] if donors else None)


def readings_count(axes: Sequence[Axis]) -> int:
    """How many readings the rule axes have (the product of their grids)."""
    return math.prod(len(axis.readings) for axis in axes)


def reading_search(
    abstraction: Abstraction, start: CompressedState, priced: Sequence[PricedOffer], clock: Clock | None, watch, searches: list[PackedResult],
    solver: str, count: int, *, item=None,
) -> Callable[[Reading, Abstraction, CompressedState], PackedResult]:
    """The envelope search of one reading's model from one state, for `solve_each_reading` (#1111). Each search has an equal share of what the
    run has left over the readings not yet searched and the comparison of their routes (`search_net`), stops at the run's gap as the plan's own search does (`search_gap`), and
    counts its states on the run's clock; each is appended to `searches`, the plan reading's search from the start first (the driver searches
    the plan reading first). The run's watcher sees that one only. A search that cannot answer is the plan's refusal (`envelope_refusal`)."""

    def search(reading: Reading, model: Abstraction, state: CompressedState) -> PackedResult:
        net = search_net(clock, count - len(searches) + 1)  # a share for each reading left and one for comparing the routes after them
        gap, gap_after = search_gap(clock)
        first = model is abstraction and state == start
        try:
            with stage(SEARCH_STAGE, SEARCH_KEPT, stops=False):
                found = envelope_result(
                    model, state, priced, prune_corrupting=PRUNE_CORRUPTING, net=net, item=item if state == start else None, gap=gap,
                    gap_after=gap_after, watch=watch if first else None,
                )  # fmt: skip
        except (OutOfScopeError, NoPolicy, BoundError, ConvergenceError) as error:
            if clock is not None:
                clock.spend(getattr(error, "states", 0))
            raise PlanError(envelope_refusal(solver, error)) from error
        info = found.info["envelope"]
        bind_search(clock, info, None if net is None else net.states)
        if clock is not None:
            clock.spend(info.touched)
        searches.append(found)
        return found

    return search


class Uncovered(Exception):
    """A candidate of one reading reaches, under another reading, states its own envelope search never held (`solve_each_reading`)."""

    def __init__(self, states: Sequence[CompressedState]) -> None:
        super().__init__(f"{len(states)} states a candidate reaches under another reading were not searched")
        self.states = tuple(states)


def reading_solution(found: PackedResult, start: CompressedState) -> Searched:
    """One reading's solution for the interval driver from its envelope search from the start (#1111), with the lower figure the search proved:
    its plan's own mean when it closed exactly, else its lower figure (a search stopped at the gap or at a net, OR-13)."""
    solution = found.solution
    info = found.info.get("envelope")
    value = float(solution.values[start])
    lower = value if info is None or info.exact else min(float(info.lower), value)
    return Searched(solution.values, solution.policy, solution.error_bound, lower)


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
    price_source: str = DEFAULT_PRICE_SOURCE,
    *,
    fallback: Sequence[PricedOffer] | None = None,
) -> tuple[Foresight, Solution | None]:
    """Hinekora's Lock of an exact plan (`_foresight.foresee`): its status, N and, when the plan takes it, the solution with the Lock.

    The options come from the full list `priced`; the fallback of the gains for N reads `fallback` when given, else the offers the Lock-free solve
    used (`offered`, or `priced`); the second solve and the fallback of its Peeks read the offers after the twins (`offered`, or the twins merged
    from `priced`). Nothing is built for a Lock the target switched off.
    """
    lock = lock_price(prices, price_source)
    if not lock_wanted(target.actions):  # switched off: nothing is built
        return Foresight(LockStatus.SWITCHED_OFF, lock), None
    if abstraction.tracks_quality:  # a burn keeps no quality yet (#159): nothing is built, and the answer says the Lock was not offered
        return Foresight(LockStatus.WITH_QUALITY, lock), None
    burn = plan_burn(data, target.start_item, abstraction, prices, price_source, sockets=target.sockets is not None)
    cache: dict = {}
    plain = fallback if fallback is not None else offered if offered is not None else priced
    sites = PlanSites(abstraction, priced, plain, start, burn, prune_corrupting=PRUNE_CORRUPTING, cache=cache)

    def second_solve():
        second = offered if offered is not None else tuple(merge_twins(data, target.start_item, priced)[0])
        peeks = sites if second is plain else PlanSites(abstraction, priced, second, start, burn, prune_corrupting=PRUNE_CORRUPTING, cache=cache)
        return _Model(abstraction, start, second, cache), peeks

    return foresee(
        abstraction, start, solution, sites, second_solve, lock=lock, c_min=cheapest_cost(priced, burn), is_goal=abstraction.is_goal,
    )  # fmt: skip


def walk_cause(unbounded: Sequence[str]) -> str:
    """Why `solver="auto"` walks every item the actions can reach instead of running the envelope search (#926): what the search has no lower
    bound for yet (`refusal_causes`), decided before solving. A route to judge is never a cause since #986: it is evaluated on its own reach."""
    if not unbounded:
        raise ValueError("a walk has a cause: an abstraction the search has no bound for")
    return "the faster search, which proves its plan against the cheapest possible cost, was not used: " + f"it has no such cost yet where {'; '.join(unbounded)}"


def walk_stop(cause: str | None) -> str:
    """What a net's stop of a walk leaves (OR-33: "no plan found yet"), with why `auto` walked instead of searching when it chose to (OR-13, #926)."""
    return NO_PLAN if cause is None else f"{NO_PLAN}; {cause}"


def envelope_refusal(solver: str, error: Exception) -> str:
    """The `PlanError` text of an envelope search that cannot answer (OR-13): the cause in words. It no longer points to the walk (`--solver packed`),
    a retired path (#1380); the walk is never taken silently (#535).

    Under `auto` a refusal of the bound's build carries a player's cause (`.player`, set by `abstraction._pattern`) in place of the developer's text,
    and a search that found no route says so as the walk does, with no advice to walk: the walk would find none either. A search a net
    stopped before any plan closed (a `NoPolicy` of its chain carries the net's words, `.stopped`) found no plan yet: it says so, never that
    no plan reaches the goal, with what the user can do (#1168, OR-13, OR-33).
    """
    if isinstance(error, NoPolicy):
        chain, cause = [error], error.__cause__
        while isinstance(cause, NoPolicy):  # (the note of a bound cut short is raised from the search's refusal)
            chain.append(cause)
            cause = cause.__cause__
        if isinstance(cause, ConvergenceError):  # a plan exists, but its cost could not be certified (#867): not "no route", nor "none found"
            if solver == "envelope":
                return f"the envelope search cannot answer this target: {error}"
            return f"a plan was found, but its average cost could not be worked out to a certified figure, so it is not shown ({error})"
        if any(each.stopped is not None for each in chain):  # a net stopped the search before a plan closed: it found none yet (#1168, OR-33)
            return (
                f"stopped, {NO_PLAN}: the search found no plan before it stopped, so this does not show that no plan exists ({error}). To get a plan, "
                "run again with a larger time, states or memory limit, or with fewer methods: a search over fewer methods is smaller and may finish where "
                "this one stopped"
            )
    if solver == "envelope":
        return f"the envelope search cannot answer this target: {error}"
    if isinstance(error, NoPolicy):
        return f"no policy of the offered actions reaches the goal from the start item ({error})"
    cause = getattr(error, "player", None) or str(error)
    return f"the search for the cheapest route could not give an answer: {cause}"  # (no advice to walk: the full walk is retired, #1380)


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
        _limits.GROUPS_EXACT,
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
            coarse_first=resolve, regenerative=resolve, mean_error=getattr(getattr(packed, "solution", None), "error_bound", None),
        )  # fmt: skip
    finally:
        _regen.TRACE = None
    if _packed.PROGRESS is not None:
        _packed.PROGRESS(f"risk: p50 {risk.p50!r}, p90 {risk.p90!r}")
    error = _limits.relative_error(risk.mean)
    if error > ACCEPT_BOUND:  # the risk's mean is certified only to `error` (#1467: its moment solves take a long chain with its error): no text calls it exact
        return risk, rough_mean_limits(_packed_risk_limits(risk, resolve, moves), error)
    return risk, _packed_risk_limits(risk, resolve, moves)


def _packed_risk_limits(risk: RiskReport, resolve: bool, moves: int) -> tuple[Limit, ...]:
    if not resolve:
        return (
            Limit(
                _limits.RISK,
                _limits.not_computed(*_limits.QUANTILES),
                f"the plan can lead from one state to another in {moves:,} ways, more than the {RISK_QUANTILE_TRANSITIONS:,} the calculation "
                "of the cost figures can hold in memory",
                _limits.RISK_EXACT,
            ),
        )
    return risk_limits(risk)


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
    mean_error: float | None = None,
) -> RiskReport:
    """The risk metrics of a fixed policy whose mean cost from `start` is about `mean`.

    `mean_error`, when given, is the certified relative error of `mean` as the plan's solve worked it out: a report whose moments the run's time
    net stopped gives that mean (`risk.evaluate`'s `known_mean`, #1553).

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
    if mean_error is not None and math.isfinite(mean):
        extra["known_mean"] = (mean, *_moments_interval(mean, mean_error))
    if free_cost is None or not any(is_free_cost(action.cost, free_cost) for action in policy.values()):
        return evaluate(policy, start, is_goal, max_bins=bins, max_coarse_bins=COARSE_BINS, **extra)
    paid = min((action.cost for action in policy.values() if not is_free_cost(action.cost, free_cost)), default=0.0)
    apart = UNRESOLVED_BINS if 2 * RISK_BINS * paid < mean else RISK_BINS  # the grid is set by the actions that cost something
    return evaluate(policy, start, is_goal, max_bins=apart, max_coarse_bins=COARSE_BINS, free_cost=free_cost, free_fallback_bins=bins, **extra)


def _finite(value: float) -> bool:
    return value == value and value != float("inf")


def chance(weight: int, total: int) -> float:
    """`weight / total` as a float, exact in the ratio even for huge integers."""
    return float(Fraction(weight, total))
