"""A given route evaluated on packed arrays: on the walked graph of a packed plan (ticket #70), or on a packed walk of its own reach (#986).

`_route.evaluate_route` walks the route's policy over compressed states and keeps every outcome of every action it takes: R04's
essence rerolls have about 1,500 successors in each of 177,000 states, which an object chain cannot hold. Two packed readings stand in:

* A packed plan of the walk already holds the walked graph (one stored kernel per distinct distribution), so the route is read there
  (`evaluate_route_packed`): at each state the first rule that matches names an offer, the graph's action with that offer's tag is the
  route's action, and the route's policy is the graph restricted to those actions.
* A plan of the envelope search holds only the states the search could not prove irrelevant, so the route walks its own reach into a
  packed graph of its own (`walk_route`, `evaluate_route_reach`): the states its rules reach from the start, one action each, a kernel
  computed once per `Abstraction.kernel_key` and shared, as the plan's walk does. Nothing walks the planner's whole graph (#986).

Either chain is merged exactly, its chain lumped and the risk evaluated on the lumped chain, as for the plan's own policy (`_packed.solve_walked`).

On the walked graph the walk offers a state only the cheapest of the offers with the same kernel there (`_prune.keyed_offers`), so the route's
offer may be missing from the state's actions; then the kept action with the same `kernel_key` is its twin: the route uses that kernel at its own
price. The route has no action at a state when the game refuses its offer there, when the offer was pruned, or when no rule matches:
that is a gap, a dead end of the chain (the odds are then below 1 and the mean infinite, as in the object evaluation). Its own reach has no
pruning and no twins: there a gap is a state where no rule matches or the game refuses the rule's action, as in the object evaluation.
"""

import dataclasses
import time
from typing import NamedTuple

import numpy as np

from crafting_system.abstraction import CompressedState, integer_weights
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.budget import checkpoint
from crafting_system.data import GameData
from crafting_system.solver import PackedBuilder, PackedGraph, lump_policy
from crafting_system.solver._packed import expand_ranges
from crafting_system.solver._packed_merge import exact_classes, quotient
from crafting_system.planner import (
    BuyStartItem,
    PackedPolicy,
    PackedResult,
    Plan,
    Walked,
    free_action_cost,
    lumped_policy,
    lumped_view,
    packed_risk,
    progress,
)
from crafting_system.planner._packed import VERIFY_EVERY, VERIFY_FIRST

from ._route_chain import chain_of_route


class _Reading:
    """The route read in the walked graph of a packed plan: the rule and the action it gives at any state."""

    def __init__(self, plan: Plan, route, data: GameData) -> None:
        self.plan = plan
        self.route = route
        self.data = data
        self.walked = plan.policy.walked
        self.graph = self.walked.graph
        self.tags = {priced.label: position for position, priced in enumerate(self.walked.offers)}
        self.priced = {priced.label: priced for priced in plan.offers}

    def choose(self, i: int) -> tuple[str, int] | str:
        """What the route does at state `i`: `(offer label, graph action)` of the first matching rule whose action the walk has there, else the reason it does nothing.

        A rule whose action is missing (the game refuses it, or the walk left it out) ends the search, a gap, unless the route
        says `skip_refused`: then the next matching rule is tried.
        """
        reason = "no rule matches this state"
        state = self.walked.states[i]
        for rule in self.route.rules:
            if not rule.when.matches(state, self.data):
                continue
            action = self.action(i, rule.do)
            if action is not None:
                return rule.do, action
            reason = f"{rule.do} cannot be used here (rule at line {rule.line}): the game refuses it, or the planner's walk left it out"
            if not self.route.skip_refused:
                break
        return reason

    def action(self, i: int, label: str) -> int | None:
        """The index of the graph's action that stands for offer `label` at state `i`: its own, else its twin's; None when there is none."""
        graph = self.graph
        low, high = int(graph.act_ptr[i]), int(graph.act_ptr[i + 1])
        found = np.flatnonzero(graph.act_tag[low:high] == self.tags.get(label, -1))
        if len(found):
            return low + int(found[0])
        offer = self.priced[label].offer.action
        if isinstance(offer, BuyStartItem):
            return None
        abstraction, state = self.plan.abstraction, self.walked.states[i]
        try:
            key = abstraction.kernel_key(state, offer)
        except (NotApplicableError, OutOfScopeError):  # either: the route has no action here (a gap of the route, and the line says the game refuses it or the walk left it out)
            return None
        for a in range(low, high):
            other = self.walked.offers[int(graph.act_tag[a])].offer.action
            if isinstance(other, BuyStartItem):
                continue
            try:
                if abstraction.kernel_key(state, other) == key:
                    return a
            except (NotApplicableError, OutOfScopeError):  # either: that offer is not a twin here
                continue
        return None


def route_actions(plan: Plan, route, data: GameData):
    """What the route does on the walked graph: `(chosen, labels, cost, gaps)`.

    `chosen[i]` is the index of the graph action whose kernel the route uses at state `i` (-1: no action), `labels[i]` the offer it
    names, `cost[i]` that offer's price, and `gaps` the `(state number, reason)` of each reachable state where it does nothing.
    """
    reading = _Reading(plan, route, data)
    graph = reading.graph
    chosen = np.full(graph.n, -1, dtype=np.int64)
    cost = np.zeros(graph.n)
    labels: dict[int, str] = {}
    gaps: list[tuple[int, str]] = []
    seen = np.zeros(graph.n, dtype=bool)
    seen[0] = True
    frontier = [0]
    ksize = graph.kernel_sizes()
    while frontier:
        kernels = set()
        for i in frontier:
            if graph.goal[i]:
                continue
            found = reading.choose(i)
            if isinstance(found, str):
                gaps.append((i, found))
                continue
            label, action = found
            chosen[i] = action
            labels[i] = label
            cost[i] = reading.priced[label].cost
            kernels.add(int(graph.act_kernel[action]))
        if not kernels:
            break
        picked = np.fromiter(kernels, dtype=np.int64)
        successors = np.unique(graph.k_succ[expand_ranges(graph.k_ptr[picked], ksize[picked])])
        fresh = successors[~seen[successors]]
        seen[fresh] = True
        frontier = fresh.tolist()
    return chosen, labels, cost, gaps


def restricted(graph: PackedGraph, chosen: np.ndarray, cost: np.ndarray) -> PackedGraph:
    """`graph` with only the actions in `chosen` (-1: the state has none), each at the price in `cost[state]`."""
    has = chosen >= 0
    ptr = np.concatenate(([0], np.cumsum(has))).astype(np.int64)
    keep = chosen[has]
    return dataclasses.replace(graph, act_ptr=ptr, act_tag=graph.act_tag[keep], act_cost=cost[has], act_kernel=graph.act_kernel[keep])


def evaluate_route_packed(plan: Plan, route, data: GameData):
    """The `RouteResult` of `route` on the packed plan `plan` of the walk; see the module docstring.

    The route's chain (the graph restricted to the route's actions) is merged exactly, lumped (`solver._packed_lump`) and evaluated by
    `risk.evaluate` on the lumped chain, so the odds (below 1 when a gap is reachable), mean, variance, quantiles and CVaR are those
    of the object evaluation; `policy` is the lumped chain on one shown state per block (what the report and the route view read).
    """
    from ._route import Divergence  # _route imports this module's caller

    began = time.perf_counter()
    walked = plan.policy.walked
    say = progress() or (lambda _text: None)
    chosen, labels, cost, gaps = route_actions(plan, route, data)
    say(f"route read on the walked graph: {int((chosen >= 0).sum()):,} states act, {len(gaps):,} gaps ({time.perf_counter() - began:.1f} s)")
    chain = restricted(walked.graph, chosen, cost)
    divergences = _divergences(plan, route, data, labels, Divergence)
    return _result(plan, walked, chain, chosen, labels, cost, gaps, divergences, began)


def _result(plan: Plan, walked: Walked, chain: PackedGraph, chosen: np.ndarray, labels: dict[int, str], cost: np.ndarray, gaps, divergences, began: float):
    """The `RouteResult` of the route's chain `chain` (one action at each state that acts) on the states of `walked`."""
    from ._route import Gap, RouteResult  # _route imports this module's caller

    say = progress() or (lambda _text: None)
    found_gaps = tuple(Gap(walked.states[i], reason) for i, reason in gaps)
    classes = exact_classes(chain)
    reduced, _ = quotient(chain, classes)
    say(f"route chain merged into {classes.count:,} classes ({time.perf_counter() - began:.1f} s)")
    class_action = np.where(np.diff(reduced.act_ptr) > 0, reduced.act_ptr[:-1], -1)
    lumped = lump_policy(reduced, class_action, int(classes.cls[0]))
    say(f"route chain lumped into {lumped.count:,} blocks, {lumped.transitions:,} transitions ({time.perf_counter() - began:.1f} s)")
    goal = lumped.goal
    result = PackedResult(plan.solution, lumped_policy(lumped, reduced, walked.offers), lumped.start, lambda b: bool(goal[b]), {})
    risk, _ = packed_risk(result, plan.mean_remaining, free_action_cost(plan.offers))  # the route costs at least the solver's mean
    say(f"route risk evaluated ({time.perf_counter() - began:.1f} s)")
    view = lumped_view(lumped, reduced, classes.cls, walked)
    item_chain = chain_of_route(walked, chosen, labels, cost, gaps)  # what the route page reads: item states, not the shown member of a block
    return RouteResult(
        view,
        risk,
        found_gaps,
        divergences[0] if divergences else None,
        time.perf_counter() - began,
        item_chain,
        tuple(divergences),
    )


def _divergences(plan: Plan, route, data: GameData, labels: dict[int, str], make) -> list:
    """Every state of the solver's main line (breadth first, the lower state number first) where the route takes another action, in that order."""
    parted = []
    reading = _Reading(plan, route, data)
    graph = reading.graph
    mine = plan.policy.action_array
    ksize = graph.kernel_sizes()
    seen = np.zeros(graph.n, dtype=bool)
    seen[0] = True
    frontier = np.array([0], dtype=np.int64)
    while len(frontier):
        frontier = np.sort(frontier[mine[frontier] >= 0])
        for i in frontier.tolist():
            ours = reading.walked.offers[int(graph.act_tag[mine[i]])].label
            theirs = labels.get(i)
            if theirs is None:
                found = reading.choose(i)
                if not isinstance(found, str):
                    theirs = found[0]  # the route does not reach this state; it would act here (a gap is not a divergence)
            if theirs is not None and theirs != ours:
                parted.append(make(reading.walked.states[i], ours, theirs))
        if not len(frontier):
            break
        kernels = np.unique(graph.act_kernel[mine[frontier]])
        successors = np.unique(graph.k_succ[expand_ranges(graph.k_ptr[kernels], ksize[kernels])])
        frontier = successors[~seen[successors]].astype(np.int64)
        seen[frontier] = True
    return parted


class _Named(NamedTuple):
    """`restart` among the offers of a route's own reach when the plan does not offer it (only its label is read there)."""

    label: str


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class RouteReach:
    """The route's own reach walked into a packed graph (`walk_route`): one action at each state where it acts, its index in `chosen`.

    `walked.offers[t]` is the offer of tag `t`; `labels[i]` is the offer the route names at state `i`, `cost[i]` what it pays there, and `gaps`
    the `(state number, reason)` of each reached state where it does nothing, in the order the object evaluation finds them.
    """

    walked: Walked
    chosen: np.ndarray
    labels: dict[int, str]
    cost: np.ndarray
    gaps: list[tuple[int, str]]


def walk_route(plan: Plan, route, data: GameData) -> RouteReach:
    """Walk the states `route` reaches from `plan.start`, breadth first, into a packed graph with the route's one action at each (#986).

    At each state the first matching rule gives the action, as `_route._decide` does (`skip_refused` tries the next): `restart` goes to the start
    for the start item's price, any other offer is its kernel, computed once per `kernel_key` and shared by every state with that key (the
    planner's walk does the same, `_packed.walk`). The states are numbered in the order the object evaluation meets them.
    """
    from ._route import RESTART  # _route imports this module's caller

    abstraction = plan.abstraction
    by_label = {priced.label: priced for priced in plan.offers}
    offers: list = list(plan.offers)
    tags = {priced.label: position for position, priced in enumerate(offers)}
    if RESTART not in tags:
        tags[RESTART] = len(offers)
        offers.append(_Named(RESTART))
    states: list[CompressedState] = [plan.start]
    index: dict[CompressedState, int] = {plan.start: 0}
    goals: list[bool] = [plan.is_goal(plan.start)]
    builder = PackedBuilder()
    shared: dict[object, int] = {}
    chosen: list[int] = []
    labels: dict[int, str] = {}
    cost: list[float] = []
    gaps: list[tuple[int, str]] = []
    restart: list[int] = []  # the one kernel of `restart`, the start for certain, once it is used
    hits = [0]  # kernels found shared by their key
    acted = 0
    began = time.perf_counter()

    def intern(state: CompressedState) -> int:
        found = index.get(state)
        if found is None:
            found = index[state] = len(states)
            states.append(state)
            goals.append(plan.is_goal(state))
        return found

    def act(rule, state: CompressedState) -> tuple[int, float] | str:
        """The kernel and the price of `rule`'s action in `state`, or why the game or the model refuses it there."""
        priced = by_label.get(rule.do)
        if rule.do == RESTART or isinstance(priced.offer.action, BuyStartItem):
            if not restart:
                restart.append(builder.kernel([0], [1]))
            return restart[0], plan.start_price.chaos if rule.do == RESTART else priced.cost
        action = priced.offer.action
        try:
            key = abstraction.kernel_key(state, action)
            kernel = shared.get(key)
            if kernel is None:
                weights = integer_weights(abstraction.kernel(state, action))
                kernel = shared[key] = builder.kernel([intern(s) for s in weights], list(weights.values()))
            else:
                hits[0] += 1
                if hits[0] <= VERIFY_FIRST or hits[0] % VERIFY_EVERY == 0:  # as `_packed.walk` checks the kernels it shares
                    fresh = dict(integer_weights(abstraction.kernel(state, action)))
                    succ, kept = builder.kernel_edges(kernel)
                    if {states[s]: w for s, w in zip(succ, kept)} != fresh:
                        raise ValueError(
                            f"two states share the kernel key of {rule.do!r} but not its kernel (checked at {state!r}): "
                            "the key the model gives to tell its states apart does not say enough for the route's packed walk"
                        )
        except (NotApplicableError, OutOfScopeError) as problem:  # either: the route's rule cannot be used here, and the line says why
            return f"{rule.do} cannot be used here (rule at line {rule.line}): {problem}"
        return kernel, priced.cost

    i = 0
    while i < len(states):
        checkpoint()  # the run's net (#825): the walk stops between two states once its time or memory is spent
        state = states[i]
        taken, price = -1, 0.0
        if not goals[i]:
            reason = "no rule matches this state"
            for rule in route.rules:
                if not rule.when.matches(state, data):
                    continue
                found = act(rule, state)
                if isinstance(found, str):
                    reason = found
                    if route.skip_refused:
                        continue
                    break
                kernel, price = found
                taken, labels[i] = acted, rule.do
                acted += 1
                builder.action(tags[rule.do], price, kernel)
                break
            if taken < 0:
                gaps.append((i, reason))
        chosen.append(taken)
        cost.append(price)
        builder.close_state(goals[i])
        abstraction._prepared_by.clear()  # each state is asked once (as in `_packed.walk`)
        i += 1
    graph = builder.build()
    say = progress() or (lambda _text: None)
    say(f"route's own reach walked: {graph.n:,} states, {graph.num_kernels:,} kernels, {graph.edges_counted():,} transitions ({time.perf_counter() - began:.1f} s)")
    walked = Walked(graph, states, index, tuple(offers), time.perf_counter() - began)
    return RouteReach(walked, np.asarray(chosen, dtype=np.int64), labels, np.asarray(cost, dtype=np.float64), gaps)


def evaluate_route_reach(plan: Plan, route, data: GameData):
    """The `RouteResult` of `route` walked on its own reach (`walk_route`), for a plan whose graph does not hold that reach (#986).

    The risk is evaluated as on the walked graph (merged, lumped, `packed_risk`); the divergences are read on the states of the plan's own
    policy, breadth first from the start, as the object evaluation reads them.
    """
    began = time.perf_counter()
    reach = walk_route(plan, route, data)
    divergences = _policy_divergences(plan, route, data, reach)
    return _result(plan, reach.walked, reach.walked.graph, reach.chosen, reach.labels, reach.cost, reach.gaps, divergences, began)


def _policy_divergences(plan: Plan, route, data: GameData, reach: RouteReach) -> list:
    """Every state of the plan's policy (breadth first from the start, as `_reach.policy_states`) where the route takes another action.

    The route's action at a state it reaches is read from `reach`; at another it is the first matching rule the game allows (`route_label`).
    A packed policy is read on its arrays: no `Action` of the plan is built.
    """
    from ._reach import policy_states
    from ._route import Divergence

    def theirs(state: CompressedState) -> str | None:
        j = reach.walked.index.get(state)
        if j is not None:
            return reach.labels.get(j)
        return route_label(plan, route, data, state)

    parted = []
    policy = plan.policy
    if isinstance(policy, PackedPolicy):
        walked, mine = policy.walked, policy.action_array
        graph = walked.graph
        order, seen, k = [0], {0}, 0
        while k < len(order):
            i = order[k]
            k += 1
            if graph.goal[i] or mine[i] < 0:
                continue
            ours = walked.offers[int(graph.act_tag[mine[i]])].label
            label = theirs(walked.states[i])
            if label is not None and label != ours:
                parted.append(Divergence(walked.states[i], ours, label))
            kernel = int(graph.act_kernel[mine[i]])
            for s in graph.k_succ[graph.k_ptr[kernel] : graph.k_ptr[kernel + 1]].tolist():
                if s not in seen:
                    seen.add(s)
                    order.append(s)
        return parted
    for state in policy_states(plan.start, policy, plan.is_goal):
        if plan.is_goal(state) or state not in policy:
            continue
        label = theirs(state)
        if label is not None and label != policy[state].label:
            parted.append(Divergence(state, str(policy[state].label), label))
    return parted


def route_label(plan: Plan, route, data: GameData, state: CompressedState) -> str | None:
    """The offer the route names in `state`: the first matching rule the game allows there (`skip_refused` tries the next); None when it does nothing.

    Whether the game allows it is read off `kernel_key`, as the walked graph's reading does (`_Reading.action`): no kernel is built.
    """
    from ._route import RESTART

    for rule in route.rules:
        if not rule.when.matches(state, data):
            continue
        if rule.do == RESTART:
            return RESTART
        action = next(priced for priced in plan.offers if priced.label == rule.do).offer.action
        if isinstance(action, BuyStartItem):
            return rule.do
        try:
            plan.abstraction.kernel_key(state, action)
        except (NotApplicableError, OutOfScopeError):  # either: the route has no action here (a gap, not a divergence)
            if not route.skip_refused:
                return None
            continue
        return rule.do
    return None
