"""A given route evaluated on the packed graph of a packed plan (ticket #70).

`_route.evaluate_route` walks the route's policy over compressed states and keeps every outcome of every action it takes: R04's
essence rerolls have about 1,500 successors in each of 177,000 states, which an object chain cannot hold. A packed plan already
holds the walked graph (one stored kernel per distinct distribution), so the route is read there instead: at each state the first
rule that matches names an offer, the graph's action with that offer's tag is the route's action, and the route's policy is the graph
restricted to those actions. The restricted graph is solved by the packed solver (a policy with one action per state is a policy
evaluation, merged exactly and certified) and the risk is evaluated on its merged chain, as for the plan's own policy.

The walk offers a state only the cheapest of the offers with the same kernel there (`_prune.keyed_offers`), so the route's offer may
be missing from the state's actions; then the kept action with the same `kernel_key` is its twin: the route uses that kernel at its own
price. The route has no action at a state when the game refuses its offer there, when the offer was pruned, or when no rule matches:
that is a gap. A route with a gap never finishes with certainty: its mean is infinite and its success chance is found by iterating
the chain (a lower bound; the upper bound is 1 until the iteration settles).
"""

import dataclasses
import math
import time

import numpy as np

from crafting_system.abstraction import CompressedState
from crafting_system.actions import ActionError
from crafting_system.data import GameData
from crafting_system.risk import Estimate, GridInfo, RiskReport
from crafting_system.solver import PackedGraph
from crafting_system.solver._packed import expand_ranges, kernel_sums

from ._offers import BuyStartItem, free_action_cost
from ._packed import PackedPolicy, Walked, solve_walked
from ._plan import Plan, packed_risk

SUCCESS_ITERATIONS = 5_000  # sweeps of the success chance of a route with a gap
SUCCESS_SETTLED = 1e-13  # the largest change in a sweep that counts as settled


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


def success_chance(graph: PackedGraph, chosen: np.ndarray) -> Estimate:
    """The chance the route's chain from state 0 ends in a goal: iterated from below, so `low` is certain and `high` is 1 until it settles."""
    n = graph.n
    taken = chosen >= 0
    kernel_of = np.where(taken, graph.act_kernel[np.maximum(chosen, 0)], 0)
    x = graph.goal.astype(np.float64)
    for _ in range(SUCCESS_ITERATIONS):
        sums = kernel_sums(graph, x)
        new = np.where(graph.goal, 1.0, np.where(taken, sums[kernel_of], 0.0))
        change = float(np.max(np.abs(new - x))) if n else 0.0
        x = new
        if change < SUCCESS_SETTLED:
            return Estimate(float(x[0]), float(x[0]), float(x[0]))
    return Estimate(float(x[0]), float(x[0]), 1.0)


def evaluate_route_packed(plan: Plan, route, data: GameData):
    """The `RouteResult` of `route` on the packed plan `plan`; see the module docstring."""
    from ._route import Divergence, Gap, RouteResult  # _route imports this module's caller

    began = time.perf_counter()
    walked = plan.policy.walked
    graph = walked.graph
    chosen, labels, cost, gaps = route_actions(plan, route, data)
    found_gaps = tuple(Gap(walked.states[i], reason) for i, reason in gaps)
    if gaps:
        never = Estimate(math.inf, math.inf, math.inf)
        risk = RiskReport(
            success_chance(graph, chosen), never, never, {0.5: never, 0.9: never}, never, 0.9, GridInfo(0.0, True, 0, 0.0, 0.0)
        )
        policy = PackedPolicy(plan.abstraction, plan.start, walked, chosen)
    else:
        solved = solve_walked(
            plan.abstraction, plan.start, Walked(restricted(graph, chosen, cost), walked.states, walked.index, walked.offers, 0.0)
        )
        policy = solved.solution.policy
        risk, _ = packed_risk(solved, solved.solution.values[plan.start], free_action_cost(plan.offers), "")
    return RouteResult(policy, risk, found_gaps, _divergence(plan, route, data, labels, Divergence), time.perf_counter() - began)


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
