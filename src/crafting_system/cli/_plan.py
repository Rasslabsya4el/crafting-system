"""From a target to a solved policy with its risk: targets -> prices -> abstraction -> solver -> risk.

`make_plan` is the whole pipeline of the R12 slice and does no printing and no file work: the
caller loads the game data, the target and the prices and decides what to do with the `Plan`.
Nothing here reads the clock except `time.perf_counter` around the solve and the risk run, which
are reported (the budget DP of `risk.evaluate` is pure Python and can be slow on large policies).

With a `budget` the plan first forecasts its size (`_decide.decide`): a query that fits runs exactly, a
larger one is answered by the ladder of coarse levels (`_approx`) and the `Plan` then has an `approximation`,
its `solution` is the pessimistic one on blocks and it has no `risk` (ADR-0023). Without a `budget` the plan
is always exact, as before.
"""

import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction

from crafting_system import parallel
from crafting_system.abstraction import Abstraction, CompressedState, Goal, integer_weights
from crafting_system.actions import BLOCKING, OutOfScopeError, kinds, unopened_listing
from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.prices import PriceFile, planned_entry
from crafting_system.risk import RiskReport, _regen, evaluate, is_free_cost
from crafting_system.solver import Action, ConvergenceError, Outcome, Solution, solve
from crafting_system.prices.query_compare import other_item
from crafting_system.targets import KOfN, Requirement, StartBuyError, StartKind, Target, buy_spec_of, shared_name_refusal

from ._approx import Approximation, climb
from ._bound_prune import Pruned, merge_twins, solve_pruned, starting_offers
from ._decide import Rates, decide
from . import _limits
from ._limits import Limit, approximate_limits, claim, kind_title, model_gap_limits, pruning_limits, risk_limits, twins_limit, unpriced_limits, with_limits
from ._offers import RESTART, BuyStartItem, Offer, PricedOffer, crafted_mods_limit, free_action_cost, listing_draw, offers_for, price_offers, split_usable
from . import _packed
from ._envelope import Net, NoPolicy
from ._envelope_plan import BoundError, EnvelopeInfo, envelope_limits, envelope_result
from ._packed import SOLVERS, PackedResult, packed_result
from ._route_chain import chain_of_plan
from ._route_flow import flow_limits
from ._prune import chosen_offers, solver_actions
from ._reach import reach_limit
from ._start_types import StartChoice

VIEW_FROM_STATES = 1_000  # a packed plan whose policy visits more item states than this is shown by its lumped chain (ticket #70)
MERGE_EQUAL = True  # offers with an equal kernel at a state: only the cheapest (exact; a test turns it off for the reference)
PRUNE_CORRUPTING = True  # corrupting offers of a target that asks are left out of the states that cannot reach its goal (exact, ADR-0036; a test turns it off)
PRUNE_BOUND = True  # twins and offers proved not needed are left out of the solve (exact; a test turns it off for the reference)
MIN_OFFERS_TO_PRUNE = 40  # fewer priced offers than this are solved whole


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

    def __post_init__(self) -> None:
        # one place decides what a guarantee of cheapness says: an approximate answer reaches the cheapest only to within its stated gap (OR-13)
        if self.approximation is not None:
            object.__setattr__(self, "limits", approximate_limits(self.limits))

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
        return self.abstraction.is_goal(state)

    def offer_of(self, action: Action[CompressedState]) -> PricedOffer:
        """The priced offer a policy action stands for (the action label is the offer label); `restart` is one."""
        return next(priced for priced in self.offers if priced.label == action.label)

    @property
    def mean_remaining(self) -> float:
        """The solver's expected cost from the start, without the price of the start item."""
        return self.solution.values[self.start]


class _Model:
    """The solver's view of the compressed states under the offered actions.

    `restart` (buying the start item again, ADR-0011) is one of the offers when the start item has a
    price; it is an action of every state but the start itself, where it would change nothing.
    """

    def __init__(
        self, abstraction: Abstraction, start: CompressedState, offers: Iterable[PricedOffer], cache: dict | None = None
    ) -> None:
        self.abstraction = abstraction
        self.start = start
        self.offers = tuple(offers)
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
                self.abstraction, self.offers, state, self.start, merge_equal=MERGE_EQUAL, prune_corrupting=PRUNE_CORRUPTING
            )
            for priced in chosen:
                if self.cache is None or (state, priced.label, priced.cost) not in self.cache:
                    if not isinstance(priced.offer.action, BuyStartItem):
                        requests.append((state, priced.offer.action))
        self.abstraction.prime(requests)

    def actions(self, state: CompressedState) -> list[Action[CompressedState]]:
        chosen = self.chosen.pop(state, None)
        return solver_actions(
            self.abstraction, self.offers, state, self.start,
            merge_equal=MERGE_EQUAL, prune_corrupting=PRUNE_CORRUPTING, cache=self.cache, chosen=chosen,
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
    data: GameData, target: Target, prices: PriceFile, override: float | None
) -> StartPrice:
    """The cost of the start item (OR-6): a given one costs nothing and is never bought again; a bought one has a price.

    A target that says `start: given` has no price to set: `--start-price` on it is refused. A bought one is a run's own number
    (`--start-price`, above 0), else the price file (hand overrides already in it) under the key computed from the target
    (`start_price_key`); a key that is not in the file is an error that names it: the cost of the whole craft would be wrong without it.
    A poe.ninja price of a name that several bases share is refused with the words that say why (`shared_name_refusal`).
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
    entry = planned_entry(prices, name)  # OR-8: a thin market is priced, with its mark in the source
    if entry is None:
        raise PlanError(
            f"no price for the start item {name!r}. A bought start item must have a price. Price it on the trade site with the "
            "`trade` command, write a hand price for it in your price overrides, or give it with --start-price"
        )
    refusal = shared_name_refusal(data, target.base_id, entry.source, f"the start item {name!r}")
    if refusal is not None:  # a poe.ninja line has no base id: for a name that several bases share it prices none of them (#471)
        raise PlanError(refusal)
    stored = (entry.detail or {}).get("query")
    return StartPrice(name, entry.chaos, entry.source, other_item(spec, stored) if isinstance(stored, dict) else None)


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
    budget: float | None = None,
    rates: Rates | None = None,
    strands: bool = False,
    solve_it: bool = True,
    start_price_of: StartPrice | None = None,
    solver: str = "auto",
    with_risk: bool = True,
    incumbent: Callable[[CompressedState], Sequence[str]] | None = None,
    net: Net | None = None,
) -> Plan:
    """Solve the target and measure the risk of the policy.

    `start_price` is the cost of the start item for this run (it wins over the price file);
    `offers` default to `offers_for` the target. Raises `PlanError` when the target has `implicits` or
    `quality` (the planner ignores them until B2), when no offer has a price or no policy reaches the
    goal, and what the layers below raise for a bad input.

    Remove Crafted Mods is kept only when a priced bench craft is, or the start item holds a crafted
    mod: otherwise no crafted mod can ever exist and tracking the junk slots for it would only grow
    the state space. A bought start item is offered again as `restart` from every state; a given one never is (OR-6).

    `budget` (seconds) turns on the decision of ADR-0023: when the forecast of the exact run is longer, the
    answer is approximate within the tolerance if some coarse level reaches it, and `PlanError` says so
    when none exists and the exact run is not offered. `rates` injects the seconds per kernel outcome and per
    solved edge instead of measuring them. None (the default) always solves exactly. With `solve_it` False nothing is
    solved: the plan holds the offers, the abstraction and the start, an empty policy and an infinite value, so that a
    given route can be read and played on concrete items (`_route_sim`) when the graph is too large to solve (R04, R14).
    `strands` is the setting `memory_strands` of the query (ADR-0040): with it off and no strands on the start item the
    plan does not consider strands, as before; with either on, `PlanError` says the planner cannot plan with them yet
    (tickets of batch B5). `start_price_of` is the price of the start item as the caller worked it out, for a start option that is
    not the target's own item (a vendor recipe, ADR-0059): it wins over `start_price` and over the price the target's computed key has in the file.

    `solver` picks the exact solve (ticket #374, ADR-0063): "auto" (the default) walks the graph on packed arrays first and
    solves it there when it holds more than `_packed.OBJECT_SOLVER_EDGES` transitions (R04, R14, S02), otherwise the
    object solver solves it as it always did; "object" never packs; "packed" always does, and with 40 offers or more it
    solves the offers left after the twins are merged, without the bound pruning (the cross-check of the two solvers).
    The values are the same to the certificate; only the cost differs. "envelope" (ticket #377, ADR-0063 point 4) is the exact branch-and-bound
    of OR-12: the walk-free lower bound of #497 (`_pattern_bound`) and a search that expands only the states, and builds only the actions, the
    bound cannot rule out (`_envelope`); it gives the same plan and mean as "packed" and says so in `Plan.limits` (which cut ran, what it
    guarantees). It takes the offers after the twins are merged, as "packed" does, ignores `budget` (it is always exact), and refuses with
    `PlanError` an abstraction the bound cannot be built for (#507). `incumbent` (a state to the labels of the offers it takes) is the policy the search completes with a restart for its
    first upper bound (`_envelope_plan.route_incumbent` reads a given route as one); `net` is a stop-and-say-so safety net (time, states or
    memory; none by default): when it ends the search the plan is the best executable one, `Plan.limits` says it is not shown to be the best and
    gives the lower and upper bounds of its cost.

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
    if target.sockets is not None:
        raise PlanError(
            "the target asks for sockets, which the planner cannot plan yet"
            ": the finish of sockets is not built, so an answer would silently ignore them"
        )
    if target.enchantment is not None:
        raise PlanError(
            "the target asks for an enchantment, which the planner cannot plan yet"
        )
    price_of_start = start_price_of if start_price_of is not None else resolve_start_price(data, target, prices, start_price)
    goal = Goal.from_target(target)
    limits: tuple[Limit, ...] = (strands_limit(),)
    if offers is None:
        try:
            chosen = offers_for(data, goal, target.base_id, target.start_item, target.actions)
        except ValueError as error:
            raise PlanError(str(error)) from error
        offers, limits = chosen.offers, (*chosen.limits, *limits)
    priced, dropped = price_offers(offers, prices)
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
        limits += (crafted_mods_limit(tuple(p.label for p in priced if p.offer.action not in kept)),)
    priced = tuple(p for p in priced if p.offer.action in kept)
    limits += start_limits(price_of_start)
    if price_of_start.bought:
        bought = price_of_start.name or "start item"
        restart = Offer(RESTART, BuyStartItem(listing or target.start_item), {bought: 1}, shares=False)
        part = (bought, 1, price_of_start.chaos, price_of_start.source)
        priced = (*priced, PricedOffer(restart, price_of_start.chaos, (part,)))

    enabled = [p.offer.action for p in priced if (reads := p.offer.action.reads(data)).junk or reads.item_state]
    holds_metamod = bool(target.start_item.metamods(data) & BLOCKING)
    axes = sorted({axis.name for p in priced for axis in p.offer.action.rule_axes(data)})
    if axes:
        raise PlanError(
            f"an offered action reads the rule axis {', '.join(axes)}, and the planner does not solve a reading "
            "of it with the interval yet"
        )
    abstraction = Abstraction(
        data,
        goal,
        target.base_id,
        target.item_level,
        enabled,
        metamods=holds_metamod,
        enchantment=target.start_item.enchantment,
        allow_inputs=False,
    )
    start = abstraction.compress(listing or target.start_item)
    shape = abstraction.compress(target.start_item) if listing is not None else None  # the item the start opens into: what the pruning bounds the offers on (ADR-0064)

    if not solve_it:
        unsolved = Solution({start: float("inf")}, {}, float("inf"))
        return Plan(target, abstraction, leaf_labels(target), prices, start, price_of_start, priced, limits, unsolved, None, 0.0, 0.0)
    if budget is not None and solver != "envelope":
        forecast = merged = priced
        merged_twins: list[tuple[str, str]] = []
        if PRUNE_BOUND and len(priced) >= MIN_OFFERS_TO_PRUNE:
            # The exact run solves a small set first and proves the rest not needed: it is forecast on that set, not on
            # a pilot over thousands of fossil sets. An approximate answer is made of all the offers, twins merged.
            merged, merged_twins = (tuple(each) for each in merge_twins(data, target.start_item, priced))
            forecast = tuple(starting_offers(abstraction, start, merged, target.start_item, min_offers=MIN_OFFERS_TO_PRUNE, shape=shape))
        decision = decide(abstraction, start, forecast, budget, rates)
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
                solved = climb(decision, start, merged)
            except ValueError as error:
                raise PlanError(str(error)) from error
            limits += skipped_level_limits(solved.skipped)
            if merged_twins:
                limits += (twins_limit(merged_twins),)  # G17: the approximate answer is made of the offers left after the twins
            return finished(Plan(
                target, abstraction, leaf_labels(target), prices, solved.start, price_of_start, priced, limits,
                solved.solution, None, solved.seconds, 0.0, solved.approximation,
            ))  # fmt: skip

    began = time.perf_counter()
    pruned = None
    packed = None
    many = PRUNE_BOUND and len(priced) >= MIN_OFFERS_TO_PRUNE
    if many and solver not in ("packed", "envelope"):
        pruned = solve_pruned(abstraction, start, priced, target.start_item, min_offers=MIN_OFFERS_TO_PRUNE, shape=shape)
        solution = pruned.solution
        limits += _pruned_limits(pruned)
    else:
        offered, twins = (tuple(each) for each in merge_twins(data, target.start_item, priced)) if many else (priced, ())
        if twins:
            limits += (twins_limit(twins),)  # G17: the packed path leaves out the dearer twins, as the bound pruning does
        if solver == "envelope":
            try:
                packed = envelope_result(
                    abstraction, start, offered, prune_corrupting=PRUNE_CORRUPTING, incumbent=incumbent, net=net, item=target.start_item if many else None
                )
            except (OutOfScopeError, NoPolicy, BoundError, ConvergenceError) as error:
                raise PlanError(f"the envelope search cannot answer this target: {error}") from error
            limits += envelope_limits(packed.info["envelope"])
        else:
            packed = packed_result(abstraction, start, offered, solver=solver, prune_corrupting=PRUNE_CORRUPTING)
        solution = packed.solution if packed is not None else solve(_Model(abstraction, start, priced), [start])
        if packed is not None:
            limits += _packed.evaluation_limits(packed.info)  # (OR-13, #621) the policy evaluation that stopped short of the exact system says so
    solve_seconds = time.perf_counter() - began
    if not abstraction.is_goal(start) and not _finite(solution.values[start]):
        raise PlanError("no policy of the offered actions reaches the goal from the start item")

    risk, risk_seconds = None, 0.0
    if with_risk:
        began = time.perf_counter()
        if packed is not None:
            risk, risk_found = packed_risk(packed, solution.values[start], free_action_cost(priced))
        else:
            risk = evaluate_risk(solution.policy, start, abstraction.is_goal, solution.values[start], free_cost=free_action_cost(priced))
            risk_found = risk_limits(risk)
        limits += risk_found
        risk_seconds = time.perf_counter() - began
    if packed is not None and packed.view is not None and len(solution.policy) > VIEW_FROM_STATES:
        limits += (lumped_limit(len(solution.policy), len(packed.view) + 1),)

    return finished(Plan(
        target, abstraction, leaf_labels(target), prices, start, price_of_start, priced, limits,
        solution, risk, solve_seconds, risk_seconds, None, pruned, packed=packed,
    ))


def finished(plan: Plan) -> Plan:
    """`plan` with the limits only the finished walk and policy can tell: the actions the model had no rule for, the offers left out of states
    that cannot use them, and what the state descriptions and the reach chances leave out."""
    added = (*model_gap_limits(plan.abstraction.gaps.entries()), *pruning_limits(plan.abstraction.prunings), *display_limits(plan))
    return replace(plan, limits=(*plan.limits, *added))


def display_limits(plan: Plan) -> tuple[Limit, ...]:
    """What the text report, the JSON and the page leave out of a state's description (V4) and of its reach chance (C15, V8)."""
    found = [states_limit(plan.abstraction.keeps_junk)]
    reach = reach_limit(plan.start, plan.view_policy, plan.is_goal)
    if reach is not None:
        found.append(reach)
    return (*found, *flow_limits(chain_of_plan(plan)))  # what the route page cannot say of the steps of the policy (#466)


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
    if plan.packed is not None:
        risk, found = packed_risk(plan.packed, plan.solution.values[plan.start], free)
    else:
        risk = evaluate_risk(plan.solution.policy, plan.start, plan.abstraction.is_goal, plan.solution.values[plan.start], free_cost=free)
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
