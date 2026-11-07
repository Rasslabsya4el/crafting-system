"""One use of an action: the chance it ends in the target and what it costs (ticket #617).

The review row of `benchmark` (`_benchmark_divergence`) tells, for the planner's action and the guide's at the first place they part, the two numbers
that explain a ratio of 17 between their means: how often one use ends in the target and what one use costs, price part by price part. They come
from the same model the planner solved (`offer_action`: the integer weights of the action's kernel), not from a new search.

"Ends in the target" has two readings, and a route that ends with a sure step needs both:

* `chance`: the item after the use IS the target (`Plan.is_goal`);
* `short`: it is one sure step short of it: a bench craft (the offers of the kind `bench-craft`) turns it into the target with certainty. A Movement Speed
  craft after a fossil that left a top Energy Shield and an open prefix is such a step; the guide and the planner both do it, so a use that ends
  there is a use that reaches the target (R08, R09: the whole of their odds, #591 and #592). The step's own price is not part of the use.
"""

from collections.abc import Callable

from crafting_system.abstraction import CompressedState
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.solver import Action

from ._offers import PricedOffer
from ._plan import Plan, offer_action


GOAL, SHORT, OTHER = "goal", "short", "other"
SURE_KIND = "bench-craft"  # the catalog kind (`Offer.kind`) whose actions change an item with certainty: the bench crafts


def sure_steps(plan: Plan) -> tuple[PricedOffer, ...]:
    """The bench crafts the plan offers: the steps that change an item with certainty and cost little next to a fossil, an essence or a reroll."""
    return tuple(priced for priced in plan.offers if priced.offer.kind == SURE_KIND)


def one_step_short(plan: Plan, state: CompressedState, steps: tuple[PricedOffer, ...]) -> bool:
    """Whether `state` is not the target but one of the `steps` makes it the target with certainty (a single outcome that is the goal)."""
    for priced in steps:
        try:
            action = offer_action(plan.abstraction, priced, state, plan.start)
        except (NotApplicableError, OutOfScopeError):
            continue
        if len(action.outcomes) == 1 and plan.is_goal(action.outcomes[0].state):
            return True
    return False


def reading_of(plan: Plan, state: CompressedState, steps: tuple[PricedOffer, ...]) -> str:
    """What `state` is next to the target: `goal`, `short` (one sure step short of it) or `other`.

    The one place that says it, for the outcomes of a use here and for the finished items of the emulator in `tools/coe_emulator/record.py`.
    """
    if plan.is_goal(state):
        return GOAL
    return SHORT if one_step_short(plan, state, steps) else OTHER


def use_numbers(action: Action, priced: PricedOffer, is_goal: Callable, short: Callable | None = None) -> dict:
    """The chances one use of `action` ends in the target (`chance`) and one sure step short of it (`short`, None without a `short` judge), and the cost.

    A chance is the weight of the outcomes that are the goal (or short of it) over the whole weight; the cost is `priced`'s, the sum of its parts.
    The other items an action consumes (`extra_inputs`) are counted, not priced here: the solver pays their value on every use.
    """
    total = sum(weight for _, weight in action.outcomes)
    into = sum(weight for state, weight in action.outcomes if is_goal(state))
    near = None if short is None else sum(weight for state, weight in action.outcomes if not is_goal(state) and short(state))
    return {
        "action": str(action.label),
        "chance": into / total if total else None,
        "short": None if near is None or not total else near / total,
        "reach": (into + (near or 0)) / total if total else None,  # the one number: the item ends in the target, or is one certain bench craft away from it
        "cost": priced.cost,
        "parts": [{"resource": name, "count": count, "chaos": chaos, "source": source} for name, count, chaos, source in priced.parts],
        "other_items": len(action.extra_inputs),
        "error": None,
    }


def per_use_of(plan: Plan, state: CompressedState, label: str) -> dict:
    """`use_numbers` of the offer called `label` used in `state`; `error` says why when it is not an offer of the plan or the game refuses it there.

    Both actions of a divergence are legal in its state when the planner's policy and the route's rule took them there, but a lumped view of a
    packed plan can show a state where one is not: the row then says so in the words of the refusal, and the benchmark goes on.
    """
    priced = next((offer for offer in plan.offers if offer.label == label), None)
    if priced is None:
        return no_numbers(label, "the plan does not offer it")
    steps = sure_steps(plan)
    short = (lambda successor: one_step_short(plan, successor, steps)) if steps else None
    try:
        return use_numbers(offer_action(plan.abstraction, priced, state, plan.start), priced, plan.is_goal, short)
    except (NotApplicableError, OutOfScopeError) as problem:
        return no_numbers(label, str(problem))


def no_numbers(label: str, why: str) -> dict:
    return {"action": label, "chance": None, "short": None, "reach": None, "cost": None, "parts": [], "other_items": 0, "error": why}
