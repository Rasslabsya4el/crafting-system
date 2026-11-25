"""A bought Normal start whose first step reforges a Rare one alike: the route page tells the player to buy either (#1673, OR-43, OR-16).

R06 plans from a Normal Hunter belt nobody lists, while the market sells Rare ones, and its first step, Deafening Essence of Rage, reforges
either alike (`test_r06_start_reforge_1673.py` pins that law on the real data). The page's buy step then names "Normal or Rare", says why
in one line naming the step, and its one trade link searches the item at any rarity but unique, so it finds what the player is told to buy.
The rule is the action's own behaviour (`cli._route_reforge.reforged_start`), checked here on the fixture belt: the Essence of Hysteria
reforges a Normal and a Rare belt alike; a start that is already Rare, or a first step that is not a reforge, keeps the page as it was.
"""

from route_view_support import HYSTERIA_REQ, LIFE, belt, hand_input

from crafting_system.cli._route_reforge import either_rarity, link_spec, reforged_start
from crafting_system.cli._route_view import build_section
from crafting_system.items import Rarity
from crafting_system.prices import BuySpec
from items_support import DATA


def essence_for_hysteria(state, ab):
    return "Essence of Hysteria"


def lines_of(row, label: str) -> list[str]:
    return next(([line.text for line in field.lines] for field in row.fields if field.label == label), [])


def test_a_normal_start_reforged_first_is_bought_normal_or_rare_and_the_page_says_why():
    plan_input = hand_input(belt(rarity=Rarity.NORMAL), (HYSTERIA_REQ, LIFE), essence_for_hysteria)
    assert reforged_start(DATA, plan_input.plan) == "Essence of Hysteria"

    buy = build_section(plan_input, DATA).rows[0]
    assert buy.title == "Buy Hand start belt (Normal or Rare)"
    assert lines_of(buy, "Accepts")[-1] == "a Normal or a Rare one, the cheaper: the first step, Essence of Hysteria, reforges either alike"


def test_a_start_that_is_already_rare_keeps_the_buy_step_as_it_was():
    rare = hand_input(belt(rarity=Rarity.RARE), (HYSTERIA_REQ, LIFE), essence_for_hysteria)

    assert reforged_start(DATA, rare.plan) is None
    buy = build_section(rare, DATA).rows[0]
    assert buy.title == "Buy Hand start belt" and not any("reforges either alike" in line for line in lines_of(buy, "Accepts"))


def test_a_first_step_whose_second_use_keeps_another_item_is_no_reforge_of_both():
    # the Essence of Hysteria on the Rare belt it made keeps that same item; an action that kept the earlier mods would not
    plan_input = hand_input(belt(rarity=Rarity.NORMAL), (HYSTERIA_REQ, LIFE), essence_for_hysteria)
    action = plan_input.plan.offer_of(plan_input.plan.policy[plan_input.plan.start]).offer.action
    made = action.outcomes(DATA, plan_input.plan.target.start_item)
    assert action.outcomes(DATA, made.retained).retained == made.retained  # what the rule reads


def test_the_words_and_the_link_of_either_rarity():
    accepts, name = either_rarity(
        ["Any rarity but unique Heavy Belt", "item level 75", "Hunter influence", "not corrupted"], "Heavy Belt, normal, item level 75, Hunter influence", "Deafening Essence of Rage"
    )
    assert name == "Heavy Belt, Normal or Rare, item level 75, Hunter influence"
    assert accepts == [
        "Normal or Rare Heavy Belt", "item level 75", "Hunter influence", "not corrupted",
        "a Normal or a Rare one, the cheaper: the first step, Deafening Essence of Rage, reforges either alike",
    ]  # fmt: skip
    spec = BuySpec("Heavy Belt, normal, item level 75, Hunter influence", "Heavy Belt", "accessory.belt", "normal", 75, 75, ("hunter",))
    linked = link_spec(spec)
    assert linked.rarity == "nonunique" and linked.item_level_min == linked.item_level_max == 75 and linked.influences == ("hunter",)
