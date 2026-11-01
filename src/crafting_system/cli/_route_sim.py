"""A given route played on concrete items (ticket #70): its cost when its graph is too large to evaluate exactly.

`evaluate_route` walks the route's whole policy over compressed states and keeps every outcome of every action, which is
out of reach for R04 and R14 (an essence reroll alone has about 1,500 successor states in each of 177,000 states). The
route can still be PLAYED: at each concrete item the compressed state is found, the first rule that matches gives the
action, and the simulator uses it. The result is a Monte Carlo mean, p90 and CVaR with intervals, never an exact figure;
a state no rule covers, or where the game refuses the rule's action (a gap of the guide), stops that run, which the report counts as stopped.
"""

from crafting_system.actions import ActionError
from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.simulator import SimulationReport, Step, simulate

from ._plan import Plan
from ._route import Route
from ._verify import Memoized

DEFAULT_MAX_STEPS = 200_000


class _Ready:
    """An action whose outcomes are already computed for the item it is about to be used on."""

    def __init__(self, outcomes: object) -> None:
        self._outcomes = outcomes

    def outcomes(self, data: GameData, item: Item) -> object:
        return self._outcomes


def route_policy(plan: Plan, route: Route, data: GameData):
    """The route as a simulator policy: a concrete item to the `Step` of the first matching rule, None at a gap."""
    offers = {priced.label: priced for priced in plan.offers}
    memo: dict[str, Memoized] = {}

    def policy(item: Item) -> Step | None:
        state = plan.abstraction.compress(item)
        for rule in route.rules:
            if rule.when.matches(state, data):
                priced = offers[rule.do]
                try:
                    outcomes = memo.setdefault(priced.label, Memoized(priced.offer.action)).outcomes(data, item)
                except ActionError:
                    return None  # the game refuses the rule's action here: a gap, as in `evaluate_route`
                return Step(_Ready(outcomes), priced.cost)
        return None  # a gap of the guide: no rule covers this state

    return policy


def simulate_route(
    data: GameData, plan: Plan, route: Route, *, runs: int, seed: int = 1, max_steps: int = DEFAULT_MAX_STEPS
) -> SimulationReport:
    """`runs` crafts of the route from the target's start item, with what the start item cost added to each."""
    target = plan.target
    return simulate(
        data, route_policy(plan, route, data), target.start_item, target.is_met_by,
        runs=runs, seed=seed, start_cost=plan.start_price.chaos, max_steps=max_steps,
    )  # fmt: skip
