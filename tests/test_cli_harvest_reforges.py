"""Every Harvest reforge is offered by the CLI's model and priced from its lifeforce (ticket #72).

The prices are made-up numbers, one per lifeforce, so each expected cost is the sum written here from the wiki
table (count times price), not read from the registry.
"""

import datetime

import pytest
from cli_support import R12
from harvest_reforge_support import BOW, HUNTER, INFLUENCE_COST, LIKELIHOOD_COST, TABLE, bow
from items_support import AMULET, DATA

from crafting_system.actions import HarvestReforge, HarvestReforgeInfluence, HarvestReforgeLikelihood, kinds
from crafting_system.cli import make_plan, offers_for
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.abstraction import Goal, Wanted
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import load_target

PRICES = {
    "Wild Crystallised Lifeforce": 0.01,
    "Vivid Crystallised Lifeforce": 0.02,
    "Primal Crystallised Lifeforce": 0.03,
    "Sacred Crystallised Lifeforce": 40.0,
    "Crystallised Rancour": 0.5,
}
GOAL = Goal((Wanted(frozenset({"GlobalLightningGemLevel1"})),))


def price_file(**missing) -> PriceFile:
    prices = {name: PriceEntry(chaos, "test") for name, chaos in PRICES.items() if name not in missing.get("without", ())}
    return PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, prices)


def cost_of(resources: dict[str, int]) -> float:
    return sum(count * PRICES[name] for name, count in resources.items())


@pytest.fixture(scope="module")
def amulet_offers():
    target = load_target(R12, DATA)
    return offers_for(DATA, target.goal if hasattr(target, "goal") else GOAL, AMULET, target.start_item).offers


def test_the_sixteen_tagged_reforges_and_both_likelihood_reforges_are_offered_for_a_rare_amulet(amulet_offers):
    labels = {offer.label for offer in amulet_offers}
    assert {f"Harvest Reforge {craft.title()}" for craft in TABLE} <= labels
    assert "Harvest Reforge Influence" not in labels  # the start amulet has no influence
    assert not labels & {"Harvest Reforge More Likely", "Harvest Reforge Less Likely"}  # not a planner kind, see below


def test_the_likelihood_reforges_are_a_catalog_kind_the_planner_leaves_out_with_its_reason():
    (entry,) = (entry for entry in kinds() if entry.name == "harvest-reforge-likelihood")
    assert not entry.planner and "pruning (#118)" in entry.why_not
    assert entry in kinds() and entry not in kinds(planner_only=True)


def test_every_reforge_is_priced_by_its_lifeforce(amulet_offers):
    likelihood = [offer_of(HarvestReforgeLikelihood(more), HarvestReforgeLikelihood(more).label()) for more in (True, False)]
    priced, dropped = price_offers([o for o in amulet_offers if o.label.startswith("Harvest Reforge")] + likelihood, price_file())

    assert not dropped
    costs = {offer.offer.label: offer.cost for offer in priced}
    for craft, (_, cost) in TABLE.items():
        assert costs[f"Harvest Reforge {craft.title()}"] == pytest.approx(cost_of(cost)), craft
    assert costs["Harvest Reforge More Likely"] == pytest.approx(cost_of(LIKELIHOOD_COST))
    assert costs["Harvest Reforge Less Likely"] == pytest.approx(cost_of(LIKELIHOOD_COST))


def test_without_rancour_only_the_five_rancour_crafts_are_dropped(amulet_offers):
    _, dropped = price_offers([o for o in amulet_offers if o.label.startswith("Harvest Reforge")], price_file(without=("Crystallised Rancour",)))

    assert {drop.label: drop.missing for drop in dropped} == {
        f"Harvest Reforge {craft.title()}": ("Crystallised Rancour",)
        for craft in ("minion", "elemental", "attribute", "mana", "drop")
    }


def test_the_influence_reforge_is_offered_for_an_influenced_item_and_priced_by_primal_and_sacred_lifeforce():
    start = bow()
    offers = offers_for(DATA, GOAL, BOW, start).offers
    influence = [offer for offer in offers if offer.label == "Harvest Reforge Influence"]
    assert len(influence) == 1 and isinstance(influence[0].action, HarvestReforgeInfluence)

    priced, dropped = price_offers(influence, price_file())
    assert not dropped
    assert priced[0].cost == pytest.approx(5000 * 0.03 + 1 * 40.0)
    assert dict(influence[0].resources) == INFLUENCE_COST
    assert start.influences == HUNTER


def test_a_plan_with_all_the_reforges_priced_still_solves_the_r12_target():
    target = load_target(R12, DATA)
    prices = price_file()
    prices.prices["R12 start amulet"] = PriceEntry(4.0, "trade-api")

    plan = make_plan(DATA, target, prices)

    assert {offer.offer.label for offer in plan.offers} >= {"Chaos Orb", "Harvest Reforge Lightning"}
    assert {f"Harvest Reforge {craft.title()}" for craft in TABLE} <= {offer.offer.label for offer in plan.offers}
    assert plan.mean_remaining > 0
