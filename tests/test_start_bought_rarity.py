"""A bought start priced as a lower rarity is that item: the plan starts from it and pays the steps that make it the rarity (#1522, OR-43, OR-16).

R08 and R09 start from a Rare pair of boots with no mod named (ADR-0064), and their price is the trade search of a Normal base. Before #1522 the
plan drew a Rare listing for free at the Normal base's price, so the step that makes the base rare was neither shown nor paid. The rule: the
start is the item the price's search asked for (`StartPrice.rarity`), and the planner's own offers make it the needed rarity, each a step with
its price. Toy boots worked by hand (`listing_support`): an Orb of Transmutation leaves what an Orb of Alteration does (1 or 2 mods, 1/2 each),
and an Orb of Alchemy leaves what the free draw of a Rare listing did.
"""

from fractions import Fraction

import pytest
from listing_support import ALTERATION, AUGMENTATION, LISTING, magic_sets, magic_toy, prices, rare_toy, target

from crafting_system.actions import DRAW_LABEL
from crafting_system.cli import make_plan
from crafting_system.items import Rarity
from crafting_system.planner._offers import DRAW_COST_SHARE, RESTART
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import start_price_key

TRANSMUTATION = 0.2  # `listing_support.prices`
ALCHEMY = 0.3


def searched_at(file: PriceFile, key: str, rarity: str) -> PriceFile:
    """`file` with the start's price read from a trade search of `rarity` (the body a trade price keeps, `detail.query`)."""
    filters = {"type_filters": {"filters": {"rarity": {"option": rarity}}}, "misc_filters": {"filters": {"ilvl": {"min": 86}, "corrupted": {"option": "false"}}}}
    query = {"query": {"type": "Toy Listing Boots", "filters": filters}}
    entries = dict(file.prices) | {key: PriceEntry(LISTING, "trade-api", detail={"query": query})}
    entries["Orb of Alchemy"] = PriceEntry(ALCHEMY, "fixture")
    return PriceFile(file.league, file.fetched_at, file.chaos_per_divine, entries)


def magic_mean_by_hand() -> Fraction:
    """The mean cost from a Magic item just rolled by an Alteration (or a Transmutation, the same law), the Augmentations taken where they pay
    (the hand solve of `test_start_listing_draw`: A and C wanted, an Augmentation where one of them is held alone)."""
    sets = magic_sets()
    a, g = Fraction(ALTERATION), Fraction(AUGMENTATION)
    goal = frozenset({"ToyA", "ToyC"})
    coefficient, constant = Fraction(0), Fraction(0)
    for held, chance in sets.items():
        if held == goal:
            continue
        if held == frozenset({"ToyA"}):
            coefficient += chance * Fraction(4, 6)
            constant += chance * (g + Fraction(4, 6) * a)
        elif held == frozenset({"ToyC"}):
            coefficient += chance * Fraction(1, 4)
            constant += chance * (g + Fraction(1, 4) * a)
        else:
            coefficient += chance
            constant += chance * a
    return constant / (1 - coefficient)


def test_a_magic_start_priced_as_a_normal_base_starts_normal_and_pays_a_transmutation():
    data = magic_toy()
    aim = target(data, actions="alteration-orb, augmentation-orb, transmutation-orb")
    key = start_price_key(data, aim)
    plan = make_plan(data, aim, searched_at(prices(key), key, "normal"))

    assert plan.start_price.rarity is Rarity.NORMAL and plan.start_price.chaos == LISTING
    assert plan.target.start_item.rarity is Rarity.NORMAL and not plan.start.flags.unopened  # the item bought, not a listing drawn for free
    assert not any(p.offer.action.opens_listing for p in plan.offers)
    assert plan.policy[plan.start].label == "Orb of Transmutation"  # the step that makes it magic is a step, with its price
    # hand: one Transmutation, then the mean of a just-rolled magic item; nothing free stands in for it
    assert plan.solution.values[plan.start] == pytest.approx(TRANSMUTATION + float(magic_mean_by_hand()), rel=1e-9)
    restart = next(p for p in plan.offers if p.label == RESTART)
    assert restart.cost == LISTING and restart.offer.action.sample(None).rarity is Rarity.NORMAL  # a restart buys the Normal base again
    assert plan.start_price.taken_for is None and plan.start_price.searched is not None  # the price is the item planned; the page links its search


def test_a_rare_start_priced_as_a_normal_base_pays_the_alchemy_the_free_draw_stood_for():
    """The Alchemy on the Normal base leaves what the free draw of the Rare listing left, so the mean is the drawn plan's, its draw
    (`DRAW_COST_SHARE` of the cheapest priced offer) taken out and one Orb of Alchemy put in."""
    data = rare_toy()
    aim = target(data, rarity="rare", actions="alchemy-orb, chaos-orb", wanted=("ToyP1", "ToyS1"))
    key = start_price_key(data, aim)
    drawn = make_plan(data, aim, searched_at(prices(key), key, "rare"))  # a Rare listing's price: the draw stays
    bought = make_plan(data, aim, searched_at(prices(key), key, "normal"))

    assert drawn.policy[drawn.start].label == DRAW_LABEL and drawn.target.start_item.rarity is Rarity.RARE
    assert bought.target.start_item.rarity is Rarity.NORMAL
    assert bought.policy[bought.start].label == "Orb of Alchemy"
    draw = next(p for p in drawn.offers if p.offer.action.opens_listing).cost
    assert draw == pytest.approx(DRAW_COST_SHARE * min(p.cost for p in drawn.offers if p.offer.resources and p.cost > 0 and p.label != RESTART))
    assert bought.solution.values[bought.start] == pytest.approx(drawn.solution.values[drawn.start] - draw + ALCHEMY, rel=1e-9)


@pytest.mark.parametrize("rarity", ["magic", "nonunique"])
def test_a_start_priced_at_its_own_rarity_or_any_rarity_is_still_the_listing_drawn(rarity):
    data = magic_toy()
    aim = target(data, actions="alteration-orb, augmentation-orb, transmutation-orb")
    key = start_price_key(data, aim)
    plan = make_plan(data, aim, searched_at(prices(key), key, rarity))

    assert plan.start_price.rarity is None
    assert plan.start.flags.unopened and plan.policy[plan.start].label == DRAW_LABEL


def test_a_start_that_names_its_mods_keeps_its_rarity_whatever_the_search():
    data = magic_toy()
    aim = target(data, mods="  mods:\n    - mod: ToyA\n      values: [3]\n", actions="alteration-orb, augmentation-orb, transmutation-orb")
    key = start_price_key(data, aim)
    plan = make_plan(data, aim, searched_at(prices(key), key, "normal"))

    assert plan.start_price.rarity is None and plan.target.start_item.rarity is Rarity.MAGIC
    assert [mod.mod_id for mod in plan.target.start_item.mods] == ["ToyA"]

