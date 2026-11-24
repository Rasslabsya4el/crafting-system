"""A bought listing priced as a Normal base: the orb that makes it the rarity is a step, named and paid (#1522, OR-16, OR-43).

R08 and R09 start from a Rare pair of boots with no mod named (ADR-0064), and their price is the trade search of a Normal base. Before #1522 the
plan drew the Rare listing for free at the Normal base's price, so the Orb of Alchemy that makes the base rare was neither shown nor paid. Now
the draw is that orb when the start's stored search asks for a Normal base: an Orb of Alchemy for a Rare start, an Orb of Transmutation for a
Magic one (the same 1 or 2 mods as an Alteration), each at its price. Toy boots worked by hand (`listing_support`).
"""

import pytest
from listing_support import LISTING, magic_toy, prices, rare_toy, target

from crafting_system.actions import DRAW_LABEL
from crafting_system.cli import build_report, evaluate_route, make_plan, parse_route
from crafting_system.cli._report import listing_lines
from crafting_system.planner._offers import RESTART
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import start_price_key

TRANSMUTATION = 0.2  # `listing_support.prices`
ALCHEMY = 0.3
PAID_RARE = "Orb of Alchemy on the bought Normal base"
PAID_MAGIC = "Orb of Transmutation on the bought Normal base"


def searched_at(file: PriceFile, key: str, rarity: str, alchemy: bool = True) -> PriceFile:
    """`file` with the start's price read from a trade search of `rarity` (the body a trade price keeps, `detail.query`)."""
    filters = {"type_filters": {"filters": {"rarity": {"option": rarity}}}, "misc_filters": {"filters": {"ilvl": {"min": 86}, "corrupted": {"option": "false"}}}}
    entries = dict(file.prices) | {key: PriceEntry(LISTING, "trade-api", detail={"query": {"query": {"type": "Toy Listing Boots", "filters": filters}}})}
    if alchemy:
        entries["Orb of Alchemy"] = PriceEntry(ALCHEMY, "fixture")
    return PriceFile(file.league, file.fetched_at, file.chaos_per_divine, entries)


def opening(plan):
    return next(p for p in plan.offers if p.offer.action.opens_listing)


def plans(data, aim, key):
    """The plan at a Rare listing's price (the free draw) and at a Normal base's (the orb paid)."""
    return make_plan(data, aim, searched_at(prices(key), key, "rare")), make_plan(data, aim, searched_at(prices(key), key, "normal"))


def test_a_rare_start_priced_as_a_normal_base_uses_and_pays_an_orb_of_alchemy():
    """Hand: the Alchemy leaves what the free draw left, so the mean is the drawn plan's with its draw cost taken out and one Alchemy put in."""
    data = rare_toy()
    aim = target(data, rarity="rare", actions="alchemy-orb, chaos-orb", wanted=("ToyP1", "ToyS1"))
    drawn, bought = plans(data, aim, start_price_key(data, aim))
    free, paid = opening(drawn), opening(bought)

    assert drawn.policy[drawn.start].label == DRAW_LABEL and free.offer.resources == {}
    assert bought.policy[bought.start].label == PAID_RARE  # the step is named by the orb a player uses
    assert paid.offer.resources == {"Orb of Alchemy": 1} and paid.cost == pytest.approx(ALCHEMY)
    assert bought.solution.values[bought.start] == pytest.approx(drawn.solution.values[drawn.start] - free.cost + ALCHEMY, rel=1e-9)
    assert bought.start_price.chaos == drawn.start_price.chaos == LISTING  # the base's price is the start price, as before
    restart = next(p for p in bought.offers if p.label == RESTART)
    assert restart.cost == LISTING and restart.offer.action.sample(None).unopened  # a restart buys the Normal base again and pays the orb again
    assert "Orb of Alchemy" in listing_lines(bought, data)[0] and "Normal base" in listing_lines(bought, data)[0]


def test_a_magic_start_priced_as_a_normal_base_pays_an_orb_of_transmutation():
    data = magic_toy()
    aim = target(data, actions="alteration-orb, augmentation-orb")
    drawn, bought = plans(data, aim, start_price_key(data, aim))

    assert bought.policy[bought.start].label == PAID_MAGIC and opening(bought).cost == pytest.approx(TRANSMUTATION)
    assert bought.solution.values[bought.start] == pytest.approx(drawn.solution.values[drawn.start] - opening(drawn).cost + TRANSMUTATION, rel=1e-9)


@pytest.mark.parametrize("rarity", ["magic", "nonunique"])
def test_a_start_priced_at_its_own_rarity_or_any_rarity_keeps_the_free_draw(rarity):
    data = magic_toy()
    aim = target(data, actions="alteration-orb, augmentation-orb")
    key = start_price_key(data, aim)
    plan = make_plan(data, aim, searched_at(prices(key), key, rarity))

    assert plan.policy[plan.start].label == DRAW_LABEL and opening(plan).offer.resources == {}


def test_an_unpriced_orb_leaves_the_free_draw():
    data = rare_toy()
    aim = target(data, rarity="rare", actions="chaos-orb", wanted=("ToyP1", "ToyS1"))
    key = start_price_key(data, aim)
    plan = make_plan(data, aim, searched_at(prices(key), key, "normal", alchemy=False))

    assert plan.policy[plan.start].label == DRAW_LABEL
    said = [limit for limit in plan.limits if limit.kind == "unpriced"]
    assert said and "Orb of Alchemy" in " ".join(" ".join(limit.names) for limit in said)  # the free draw stands in for an unpriced orb, and the answer says so


def test_a_guide_route_takes_the_paid_alchemy_first_and_needs_no_rule_for_it():
    data = rare_toy()
    aim = target(data, rarity="rare", actions="alchemy-orb, chaos-orb", wanted=("ToyP1", "ToyS1"))
    key = start_price_key(data, aim)
    plan = make_plan(data, aim, searched_at(prices(key), key, "normal"), judges_route=True)
    route = parse_route("rules:\n  - when: {rarity: rare}\n    do: Chaos Orb\n", plan, data)
    result = evaluate_route(plan, route, data)

    assert route.rules[0].do == PAID_RARE and result.gaps == ()
    assert plan.solution.values[plan.start] <= result.risk.mean.value + 1e-9
    report = build_report(plan, data)
    assert any(state.action == PAID_RARE for state in report.states)
