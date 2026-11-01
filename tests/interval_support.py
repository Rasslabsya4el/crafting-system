"""The tiny recombinator case of the prototype, as an answer that reads a rule axis (ticket #221).

Four item states: E (empty), P, Q and PQ (the goal). A prefix is crafted at a fixed price or bought; a recombination of P (or Q) with a
donor of the other prefix, built from E, gives PQ, keeps one of the two or loses both, and how often depends on the selection exponent
alpha: the rare mod Q is kept with weight 250 to the alpha, the common P with 1000 to the alpha (whole numbers, so the chances are exact).
The recombination is priced by the real cost rule from a price file whose Dust is 100,000 per Chaos and whose Gold is 500 Chaos per
million, so one combine costs exactly 1 + 6 = 7 Chaos, the 7 the model charges. The toy plan of the report is the belt plan of
`test_cli_approximate_inputs` (its policy is not what is under test); the offers of the model's other actions are Chaos Orb stand-ins.
"""

import dataclasses
from fractions import Fraction

from items_support import DATA, roll
from route_view_support import BELT, COLD_REQ, FRACTURED_COLD, LEVEL, LIFE, PRICES, START_NAME, belt

from crafting_system.abstraction import Abstraction, Goal
from crafting_system.actions import ChaosOrb
from crafting_system.actions.recombinator import ALPHA_AXIS, DUST_NAME, GOLD_NAME, Recombinator
from crafting_system.cli import Offer, price_offers
from crafting_system.cli._interval import IntervalAnswer, build_interval_answer
from crafting_system.cli._plan import Plan, StartPrice, leaf_labels, offer_action
from crafting_system.items import Rarity
from crafting_system.prices import CHAOS_ORB
from crafting_system.prices.price_file import PriceEntry
from crafting_system.risk import IntervalReport, evaluate, has_inputs, solve_readings
from crafting_system.actions.contract import Reading
from crafting_system.solver import Acquisition, Action, Need, Solution, TabularModel
from crafting_system.targets import Target

GRID = tuple(Fraction(x) for x in ("2/5", "7/10", "1", "13/10", "8/5"))
CRAFT, BUY, SCOUR, RECOMBINE = "Craft a prefix", "Buy a prefix", "Scour", "Recombine with a donor"
CRAFT_P, CRAFT_Q, BUY_P, BUY_Q = f"{CRAFT} P", f"{CRAFT} Q", f"{BUY} P", f"{BUY} Q"
PRICE = {"craft": 3, "buy_p": 3, "buy_q": 12, "recombine": 7, "scour": 2}
LABELS = (CRAFT_P, CRAFT_Q, BUY_P, BUY_Q, SCOUR, RECOMBINE)
TINY_PRICES = PRICES.prices | {
    DUST_NAME: PriceEntry(1 / 100_000, "default"),
    "Gold": PriceEntry(0.0005, "default"),
}


def weights(alpha: Fraction) -> tuple[int, int]:
    """The kept weights of the rare Q and the common P at the exponent `alpha`, as whole numbers."""
    return int(250 ** float(alpha)), int(1000 ** float(alpha))


class Tiny:
    """The base model: states E, P, Q, PQ; `recombine` needs the other prefix as a donor built from E."""

    def __init__(self, alpha: Fraction, recombine: bool = True) -> None:
        self.alpha, self.recombine = alpha, recombine

    def is_goal(self, state: str) -> bool:
        return state == "PQ"

    def actions(self, state: str) -> tuple[Action, ...]:
        kq, kp = weights(self.alpha)
        if state == "E":
            return (
                Action(CRAFT_P, PRICE["craft"], (("P", 1), ("E", 9))),
                Action(CRAFT_Q, PRICE["craft"], (("Q", 1), ("E", 9))),
                Action(BUY_P, PRICE["buy_p"], (("P", 1),)),
                Action(BUY_Q, PRICE["buy_q"], (("Q", 1),)),
            )
        if state in ("P", "Q"):
            other = "Q" if state == "P" else "P"
            found = [Action(CRAFT + " " + other, PRICE["craft"], (("PQ", 1), (state, 19)))]
            if self.recombine:
                outcomes = (("PQ", kq + kp), ("Q", 2 * kq), ("P", 2 * kp))
                found.append(Action(RECOMBINE, PRICE["recombine"], outcomes, (Need("E", other),)))
            found.append(Action(SCOUR, PRICE["scour"], (("E", 1),)))
            return tuple(found)
        return ()


def tiny_result(prices: dict | None = None) -> tuple[IntervalReport, str, object]:
    """The interval driver's result on the tiny case (plan at alpha 1, the best route without recombinators beside it)."""
    models = {Reading.of({ALPHA_AXIS.name: alpha}): Acquisition(Tiny(alpha)) for alpha in GRID}
    plan_reading = Reading.of({ALPHA_AXIS.name: Fraction(1)})
    acquisition = next(iter(models.values()))
    start = acquisition.start("E")
    result = solve_readings(models, start, plan=plan_reading, without=has_inputs)
    return result, start, acquisition.is_goal


def toy_report_plan(labels: tuple[str, ...] = LABELS, recombine: str = RECOMBINE) -> Plan:
    """A plan with the offers of a model whose actions carry `labels`, the recombination among them under the label `recombine`.

    The belt policy of the report body is only there to make the report.
    """
    start = belt(FRACTURED_COLD, roll("LifeRegeneration1"))
    target = Target(BELT, LEVEL, frozenset(), (COLD_REQ, LIFE), start, start_price=START_NAME)
    ab = Abstraction(DATA, Goal.from_target(target), BELT, LEVEL, ())
    donor = belt(roll("LifeRegeneration1"), rarity=Rarity.MAGIC)
    recombinator = Recombinator(donor)
    prices = dataclasses.replace(PRICES, prices=TINY_PRICES)
    offers = [Offer("Chaos Orb", ChaosOrb(), {CHAOS_ORB: 1})]
    offers += [Offer(label, ChaosOrb(), {CHAOS_ORB: 1}) for label in labels if label != recombine]
    offers.append(Offer(recombine, recombinator, dict(recombinator.resources(DATA)), axes=(ALPHA_AXIS,)))
    priced, dropped = price_offers(offers, prices)
    assert not dropped
    by_label = {offer.label: offer for offer in priced}
    first = ab.compress(start)
    policy, order = {}, [first]
    for state in order:
        if ab.is_goal(state):
            continue
        policy[state] = offer_action(ab, by_label["Chaos Orb"], state)
        order += [s for s, w in policy[state].outcomes if w > 0 and s not in order]
    values = {state: 0.0 if ab.is_goal(state) else 1.0 for state in order}
    return Plan(
        target=target, abstraction=ab, leaf_labels=leaf_labels(target), prices=prices, start=first,
        start_price=StartPrice(START_NAME, 6.0, "trade-api"), offers=priced, dropped=(), left_out=(),
        solution=Solution(values, policy, 0.0), risk=evaluate(policy, first, ab.is_goal),
        solve_seconds=0.0, risk_seconds=0.0,
    )  # fmt: skip


def tiny_answer() -> tuple[IntervalAnswer | None, IntervalReport, Plan]:
    plan = toy_report_plan()
    result, start, is_goal = tiny_result()
    return build_interval_answer(result, plan, DATA, start=start, is_goal=is_goal), result, plan


GAMBLE, SAFE = "Gamble on a recombination", "Safe craft"


def gamble_answer() -> tuple[IntervalAnswer | None, IntervalReport]:
    """The worst case of the plan sits at an inner reading and the safe action has the smallest worst case (`test_risk_readings`): the plan is the gamble."""
    weights = dict(zip(GRID, (5, 1, 3, 5, 5)))  # the gamble costs 10 / w: 2, 10, 10/3, 2, 2 at the grid points in order
    models = {
        Reading.of({ALPHA_AXIS.name: alpha}): TabularModel(
            ["goal"],
            {"S": [Action(GAMBLE, 1, (("goal", w), ("S", 10 - w))), Action(SAFE, 6, (("goal", 1),))]},
        )
        for alpha, w in weights.items()
    }
    result = solve_readings(models, "S", plan=Reading.of({ALPHA_AXIS.name: Fraction(1)}), without=has_inputs)
    plan = toy_report_plan((GAMBLE, SAFE), recombine=GAMBLE)
    return build_interval_answer(result, plan, DATA, start="S", is_goal=lambda s: s == "goal"), result
