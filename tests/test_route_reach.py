"""A given route judged without the full walk (ticket #986): the plan is the envelope search's, the route is walked on its own reach.

`planner.plan_target(..., judges_route=True)` makes the plan by the one search whatever the size of the graph; nothing walks the whole graph for
it (`_packed.walk` is made to fail here). `cli.evaluate_route` walks the route's reach as objects up to `_route.OBJECT_ROUTE_EDGES` transitions
and on packed arrays past it (`_route_packed.evaluate_route_reach`); the limit is lowered to 0 here so the small hand-made worlds take the packed
walk. Its numbers are checked to 1e-9 against a brute-force evaluation of the route (its states walked one by one with the solver's own action,
the mean and the chance of the goal solved as a linear system with numpy) and against the object walk (gaps, divergences, the whole risk).
"""

import math
import textwrap

import numpy as np
import pytest
from cli_support import R12, price_file
from targets_support import DATA

from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.cli import _route, evaluate_route, parse_route
from crafting_system.planner import PlanSettings, _packed, offer_action, plan_target
from crafting_system.prices import PriceEntry
from crafting_system.targets import load_target, parse_target, start_price_key

GEM_TEXT = "+1 to Level of all Lightning Skill Gems"
CHAOS = "Chaos Orb"
REFORGE = "Harvest Reforge Lightning"
START_PRICE = 4.0
TWO_LEAVES = f"""\
base: Paua Amulet
item_level: 84
requirements:
  - stat: "{GEM_TEXT}"
  - family: LightningResistance
    min_tier: any
start_item:
  rarity: rare
start: bought
"""

ROUTES = {
    "chaos until the mod": f"rules:\n  - do: {CHAOS}\n",
    "the reforge until the mod": f"rules:\n  - do: {REFORGE}\n",
    "the reforge, then chaos": f"rules:\n  - when:\n      rarity: rare\n    do: {CHAOS}\n  - do: {REFORGE}\n",
    "a gap at every magic item": f"rules:\n  - when:\n      rarity: rare\n    do: {CHAOS}\n",
    "restart a half-made item": f"""\
rules:
  - when:
      requirements:
        - stat: "{GEM_TEXT}"
          status: passing
        - family: LightningResistance
          status: absent
    do: restart
  - do: {CHAOS}
""",
}


@pytest.fixture(autouse=True)
def no_full_walk(monkeypatch):
    """Nothing walks the planner's whole graph for a judged route (#986): the walk fails if it is called."""

    def refused(*_args, **_kwargs):
        raise AssertionError("the full graph was walked for a judged route")

    monkeypatch.setattr(_packed, "walk", refused)


def judged(target, prices):
    plan = plan_target(DATA, target, prices, PlanSettings(recipe_starts=False, judges_route=True))
    assert plan.search is not None  # the plan is the envelope search's
    return plan


@pytest.fixture(scope="module")
def worlds():
    r12 = load_target(R12, DATA)
    two = parse_target(TWO_LEAVES, DATA, source="two.yaml")
    prices = price_file(start=None)
    prices.prices[start_price_key(DATA, two)] = PriceEntry(START_PRICE, "trade-api")
    return {"r12": (r12, price_file()), "two leaves": (two, prices)}


def read(text: str, plan):
    return parse_route(textwrap.dedent(text).lstrip("\n"), plan, DATA, "route.yaml")


def brute_force(plan, route) -> tuple[float, float, int]:
    """The route's chance of the goal and mean cost from the plan's start, by its states one by one and a linear solve; and its number of gaps.

    Each reached non-goal state takes the first matching rule's action the game allows (the solver's own action, `offer_action`); a state with none
    is a gap (it never reaches the goal). With Q the moves among the non-goal states, c the price paid in each and r the chance of a goal in one
    step: the chance is (I - Q)^-1 r, and the mean (I - Q)^-1 c where the chance is 1 (infinite elsewhere).
    """
    order, index, rows, gaps = [plan.start], {plan.start: 0}, [], 0
    k = 0
    while k < len(order):
        state = order[k]
        k += 1
        action = None
        if not plan.is_goal(state):
            for rule in route.rules:
                if not rule.when.matches(state, DATA):
                    continue
                if rule.do == "restart":
                    action = ("restart", plan.start_price.chaos, ((plan.start, 1),))
                    break
                priced = next(p for p in plan.offers if p.label == rule.do)
                try:
                    made = offer_action(plan.abstraction, priced, state, plan.start)
                except (NotApplicableError, OutOfScopeError):  # the game or the model refuses it: the next rule only under `skip_refused`
                    if route.skip_refused:
                        continue
                    break
                action = (made.label, made.cost, tuple(made.outcomes))
                break
            gaps += action is None and not plan.is_goal(state)
        rows.append(action)
        for successor, _weight in action[2] if action else ():
            if successor not in index:
                index[successor] = len(order)
                order.append(successor)
    n = len(order)
    q, c, r = np.zeros((n, n)), np.zeros(n), np.zeros(n)
    for i, (state, action) in enumerate(zip(order, rows)):
        if plan.is_goal(state):
            continue
        if action is None:
            continue
        _label, cost, outcomes = action
        total = sum(weight for _s, weight in outcomes)
        c[i] = cost
        for successor, weight in outcomes:
            if plan.is_goal(successor):
                r[i] += weight / total
            else:
                q[i, index[successor]] += weight / total
    chance = np.linalg.solve(np.eye(n) - q, r)
    goal_start = 1.0 if plan.is_goal(plan.start) else float(chance[0])
    if goal_start < 1.0 - 1e-12:
        return goal_start, math.inf, gaps
    return goal_start, float(np.linalg.solve(np.eye(n) - q, c)[0]), gaps


@pytest.mark.parametrize("world", ["r12", "two leaves"])
@pytest.mark.parametrize("name", list(ROUTES))
def test_a_route_walked_packed_on_its_own_reach_reads_as_its_brute_force_and_as_the_object_walk(monkeypatch, worlds, world, name):
    target, prices = worlds[world]
    plan = judged(target, prices)
    route = read(ROUTES[name], plan)

    as_objects = evaluate_route(plan, route, DATA)
    monkeypatch.setattr(_route, "OBJECT_ROUTE_EDGES", 0)
    packed = evaluate_route(plan, route, DATA)

    assert packed.chain is not None  # walked on packed arrays (the object walk has no item chain)
    chance, mean, gaps = brute_force(plan, route)
    assert packed.risk.success_probability.value == pytest.approx(chance, rel=1e-9, abs=1e-12)
    if math.isinf(mean):
        assert math.isinf(packed.risk.mean.value)
    else:
        assert packed.risk.mean.value == pytest.approx(mean, rel=1e-9)
    assert len(packed.gaps) == gaps

    assert packed.gaps == as_objects.gaps
    for field in ("success_probability", "mean", "variance", "cvar"):
        ours, theirs = getattr(packed.risk, field).value, getattr(as_objects.risk, field).value
        assert ours == theirs or ours == pytest.approx(theirs, rel=1e-9)
    for level in as_objects.risk.quantiles:
        assert packed.risk.quantiles[level].low == pytest.approx(as_objects.risk.quantiles[level].low, rel=1e-9)
        assert packed.risk.quantiles[level].high == pytest.approx(as_objects.risk.quantiles[level].high, rel=1e-9)
    assert [(d.state, d.solver_action, d.route_action) for d in packed.divergences] == [
        (d.state, d.solver_action, d.route_action) for d in as_objects.divergences
    ]


def test_the_restart_route_on_two_leaves_costs_its_closed_form_walked_packed(monkeypatch, worlds):
    """The closed form of `test_cli_route.test_a_restart_costs_the_closed_form_on_a_two_leaf_target`, on the packed walk of the route's reach."""
    from crafting_system.actions import ChaosOrb

    target, prices = worlds["two leaves"]
    plan = judged(target, prices)
    monkeypatch.setattr(_route, "OBJECT_ROUTE_EDGES", 0)
    result = evaluate_route(plan, read(ROUTES["restart a half-made item"], plan), DATA)

    outcomes = ChaosOrb().outcomes(DATA, target.start_item)
    resists = [mod_id for mod_id, mod in DATA.mods.items() if "LightningResistance" in mod.families]
    gem = "GlobalLightningGemLevel1"
    g = sum(float(outcomes.chance_all([gem, mod_id])) for mod_id in resists)
    b = float(outcomes.chance_all([gem])) - g
    d = next(entry.cost for entry in plan.offers if entry.offer.action.opens_listing)
    s = START_PRICE
    expected = (d + b * s + (1 - g - b) * (1 + b * s) / (g + b)) / (1 - b - (1 - g - b) * b / (g + b))
    assert result.gaps == ()
    assert result.risk.success_probability.value == 1.0
    assert result.risk.mean.value == pytest.approx(expected, rel=1e-9)


def test_a_gap_on_the_packed_reach_says_why_as_the_object_walk_does(monkeypatch, worlds):
    target, prices = worlds["r12"]
    plan = judged(target, prices)
    route = read(f"rules:\n  - when:\n      rarity: magic\n    do: {REFORGE}\n", plan)
    monkeypatch.setattr(_route, "OBJECT_ROUTE_EDGES", 0)

    result = evaluate_route(plan, route, DATA)

    assert [gap.state for gap in result.gaps] == [plan.start]
    assert "no rule" in result.gaps[0].reason
    assert result.risk.success_probability.value < 1.0 and math.isinf(result.risk.mean.value)
    assert result.divergence is None  # a gap is not a divergence
