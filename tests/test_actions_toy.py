"""A new method is one file: a toy action defined only here is offered, gets exact kernels, simulates and passes the contract suite.

The toy is an Orb of Annulment in all but name: it removes one mod that is not fractured, uniformly. It
touches nothing but this file: it subclasses `Action`, lists its results with `Finite`, and registers
its kind in the catalog for the length of a test (`registered`). Ticket #108's "Done when".
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_pool import LIFE_1, RESIST_2
from cli_support import R12, price_file
from contract_support import CONTRACT_DATA, GOAL, check_action, fixture_items
from targets_support import DATA

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    Action,
    Adds,
    Finite,
    Kind,
    NotApplicableError,
    Reads,
    catalog,
    registered,
)
from crafting_system.cli import make_plan
from crafting_system.cli._offers import offer_of, offers_for, price_offers
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.prices import PriceEntry
from crafting_system.simulator import Step, simulate
from crafting_system.targets import load_target

TOY_ORB = "Toy Annulment Orb"


@dataclasses.dataclass(frozen=True)
class ToyAnnulment(Action):
    """Removes one mod that is not fractured, each with the same chance; the rarity stays."""

    def label(self, data: GameData | None = None) -> str:
        return "Toy Annulment"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {TOY_ORB: 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset())  # how many mods there are, not which families

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.removal()

    def outcomes(self, data: GameData, item: Item) -> Finite:
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError("the toy works on a rare item only")
        removable = [entry for entry in item.mods if not entry.fractured]
        if not removable:
            raise NotApplicableError("the item holds no mod to remove")
        chance = Fraction(1, len(removable))
        results = tuple(
            (chance, item.changed(data, mods=tuple(entry for entry in item.mods if entry is not gone)))
            for gone in removable
        )
        return Finite(data, item, results)


def toy_members(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        yield ToyAnnulment()


@pytest.fixture
def toy_registered():
    with registered(Kind("toy-annulment", toy_members, order=900)):
        yield


@pytest.fixture(scope="module")
def items():
    return fixture_items()


def test_the_toy_is_in_the_catalog_only_while_it_is_registered(items, toy_registered):
    assert ToyAnnulment() in catalog(CONTRACT_DATA, items["rare_junk"])
    assert ToyAnnulment() in catalog(CONTRACT_DATA, items["rare_junk"], planner_only=True)
    assert ToyAnnulment() not in catalog(CONTRACT_DATA, items["magic"])


def test_the_catalog_does_not_keep_the_toy_afterwards(items):
    assert ToyAnnulment() not in catalog(CONTRACT_DATA, items["rare_junk"])


def test_the_cli_offers_the_toy_with_its_resources(items, toy_registered):
    start = items["rare_junk"]
    offers = offers_for(CONTRACT_DATA, GOAL, start.base_id, start).offers
    toy = next(offer for offer in offers if offer.label == "Toy Annulment")
    assert toy.action == ToyAnnulment() and dict(toy.resources) == {TOY_ORB: 1}
    assert [offer.label for offer in offers[:2]] == ["Chaos Orb", "Harvest Reforge Lightning"]
    priced, dropped = price_offers([toy], dataclasses.replace(price_file(), prices={TOY_ORB: PriceEntry(2.5, "test")}))
    assert not dropped and priced[0].cost == 2.5


def test_the_plan_of_a_target_offers_the_toy(toy_registered):
    prices = dataclasses.replace(price_file(), prices={**price_file().prices, TOY_ORB: PriceEntry(0.5, "test")})
    plan = make_plan(CONTRACT_DATA, load_target(R12, CONTRACT_DATA), prices)
    assert "Toy Annulment" in [priced.label for priced in plan.offers]
    assert plan.dropped  # the crafts it keeps in play have no price in the file, and are reported as dropped


def test_crafts_that_count_for_nothing_are_left_out_and_the_reason_says_when_that_is_not_a_proof(items):
    start = items["rare_junk"]
    goal = Goal((Wanted(frozenset({RESIST_2})),))

    def crafts(offers):
        return [offer.label for offer in offers if offer.label.startswith("Bench craft")]

    exact = offers_for(CONTRACT_DATA, goal, start.base_id, start)
    assert crafts(exact.offers) == [] and "exact while every other action erases crafted mods" in exact.left_out[0].reason
    with registered(Kind("toy-annulment", toy_members, order=900)):  # it declares that a crafted mod can survive
        offered = offers_for(CONTRACT_DATA, goal, start.base_id, start)
    assert crafts(offered.offers) == []  # still left out: all of them would make the graph too big (R13, #66) ...
    (left,) = offered.left_out
    assert "keeps crafted mods" in left.reason and "cheapest among the offered crafts" in left.reason  # ... and the report says so


def test_the_kernel_of_the_toy_is_exact(items):
    start = items["rare_junk"]  # a resistance and a life mod
    goal = Goal((Wanted(frozenset({RESIST_2})), Wanted(frozenset({LIFE_1}))))
    toy = ToyAnnulment()
    ab = Abstraction(CONTRACT_DATA, goal, start.base_id, start.item_level, [toy])
    without = {
        mod_id: start.changed(CONTRACT_DATA, mods=tuple(e for e in start.mods if e.mod_id != mod_id))
        for mod_id in (RESIST_2, LIFE_1)
    }
    expected = {ab.compress(item): Fraction(1, 2) for item in without.values()}
    assert dict(ab.kernel(ab.compress(start), toy)) == expected


def test_the_toy_runs_in_the_simulator(items):
    start = items["rare_junk"]

    def no_life(item: Item) -> bool:
        return all(entry.mod_id != LIFE_1 for entry in item.mods)

    # remove a mod until the life mod is gone: 1/2 done at once, else one more removal: 1.5 uses, 2 Chaos each
    report = simulate(CONTRACT_DATA, lambda item: Step(ToyAnnulment(), 2.0), start, no_life, runs=3_000, seed=108)
    assert report.successes == 3_000
    assert abs(report.cost.value - 3.0) <= 5 * report.cost.standard_error


@pytest.mark.parametrize("name", ["rare_junk", "rare_fractured", "rare_crafted"])
def test_the_toy_passes_the_contract_suite(items, name):
    assert check_action(ToyAnnulment(), items[name])
