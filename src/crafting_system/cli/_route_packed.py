"""A given route evaluated on the packed graph of a packed plan (ticket #70).

`_route.evaluate_route` walks the route's policy over compressed states and keeps every outcome of every action it takes: R04's
essence rerolls have about 1,500 successors in each of 177,000 states, which an object chain cannot hold. A packed plan already
holds the walked graph (one stored kernel per distinct distribution), so the route is read there instead: at each state the first
rule that matches names an offer, the graph's action with that offer's tag is the route's action, and the route's policy is the graph
restricted to those actions. The restricted graph is merged exactly, its chain lumped and the risk evaluated on the lumped chain, as for
the plan's own policy (`_packed.solve_walked`).

The walk offers a state only the cheapest of the offers with the same kernel there (`_prune.keyed_offers`), so the route's offer may
be missing from the state's actions; then the kept action with the same `kernel_key` is its twin: the route uses that kernel at its own
price. The route has no action at a state when the game refuses its offer there, when the offer was pruned, or when no rule matches:
that is a gap, a dead end of the chain (the odds are then below 1 and the mean infinite, as in the object evaluation).
"""

import dataclasses
import time

import numpy as np

from crafting_system.abstraction import CompressedState
from crafting_system.actions import ActionError
from crafting_system.data import GameData
from crafting_system.solver import PackedGraph, lump_policy
from crafting_system.solver._packed import expand_ranges
from crafting_system.solver._packed_merge import exact_classes, quotient

from ._offers import BuyStartItem, free_action_cost
from ._packed import PackedResult, Walked, lumped_policy, lumped_view
from ._plan import Plan, packed_risk


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

    def rule(self, state: CompressedState):
        """The first rule of the route that matches `state`, or None."""
        return next((rule for rule in self.route.rules if rule.when.matches(state, self.data)), None)

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
        except ActionError:
            return None
        for a in range(low, high):
            other = self.walked.offers[int(graph.act_tag[a])].offer.action
            if isinstance(other, BuyStartItem):
                continue
            try:
                if abstraction.kernel_key(state, other) == key:
                    return a
            except ActionError:
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
            rule = reading.rule(reading.walked.states[i])
            if rule is None:
                gaps.append((i, "no rule matches this state"))
                continue
            action = reading.action(i, rule.do)
            if action is None:
                gaps.append((i, f"{rule.do} cannot be used here (rule at line {rule.line}): the game refuses it, or the planner's walk left it out"))
                continue
            chosen[i] = action
            labels[i] = rule.do
            cost[i] = reading.priced[rule.do].cost
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
    """The `RouteResult` of `route` on the packed plan `plan`; see the module docstring.

    The route's chain (the graph restricted to the route's actions) is merged exactly, lumped (`solver._packed_lump`) and evaluated by
    `risk.evaluate` on the lumped chain, so the odds (below 1 when a gap is reachable), mean, variance, quantiles and CVaR are those
    of the object evaluation; `policy` is the lumped chain on one shown state per block (what the report and the route view read).
    """
    from ._route import Divergence, Gap, RouteResult  # _route imports this module's caller

    began = time.perf_counter()
    walked = plan.policy.walked
    chosen, labels, cost, gaps = route_actions(plan, route, data)
    found_gaps = tuple(Gap(walked.states[i], reason) for i, reason in gaps)
    chain = restricted(walked.graph, chosen, cost)
    classes = exact_classes(chain)
    reduced, _ = quotient(chain, classes)
    class_action = np.where(np.diff(reduced.act_ptr) > 0, reduced.act_ptr[:-1], -1)
    lumped = lump_policy(reduced, class_action, int(classes.cls[0]))
    if lumped is None:
        raise ValueError("the route's chain holds a kernel with weights beyond 62 bits, which the packed route evaluation does not take")
    goal = lumped.goal
    result = PackedResult(plan.solution, lumped_policy(lumped, reduced, walked.offers), lumped.start, lambda b: bool(goal[b]), {})
    risk, _ = packed_risk(result, plan.mean_remaining, free_action_cost(plan.offers), "")  # the route costs at least the solver's mean
    view = lumped_view(lumped, reduced, classes.cls, walked)
    return RouteResult(view, risk, found_gaps, _divergence(plan, route, data, labels, Divergence), time.perf_counter() - began)


def _divergence(plan: Plan, route, data: GameData, labels: dict[int, str], make):
    """The first state of the solver's main line (breadth first, the lower state number first) where the route takes another action."""
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
                rule = reading.rule(reading.walked.states[i])
                if rule is not None and reading.action(i, rule.do) is not None:
                    theirs = rule.do  # the route does not reach this state; it would act here (a gap is not a divergence)
            if theirs is not None and theirs != ours:
                return make(reading.walked.states[i], ours, theirs)
        if not len(frontier):
            break
        kernels = np.unique(graph.act_kernel[mine[frontier]])
        successors = np.unique(graph.k_succ[expand_ranges(graph.k_ptr[kernels], ksize[kernels])])
        frontier = successors[~seen[successors]].astype(np.int64)
        seen[frontier] = True
    return None
