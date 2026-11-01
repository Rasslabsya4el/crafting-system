"""An opt-in kind is a planner kind that a target has to name (ticket #63).

The fossil sets (12,696 of them on boots) are `opt_in`: the planner can use them, but
the catalog and the offers leave them out unless the target lists them in `actions:` (`names` / `kinds_named`).
The toy is registered for the length of a test (`registered`), over the fixture belt of `test_cli_offers`, so
no real data is needed.
"""

import dataclasses
from fractions import Fraction

import pytest
from test_cli_offers import BELT, LIFE, PRICED_DATA

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import Action, Adds, Finite, Kind, Reads, catalog, kinds, registered
from crafting_system.cli import offers_for
from items_support import item

TOY = "toy-opt-in"
TOY_LABEL = "Toy Opt-In Orb"


@dataclasses.dataclass(frozen=True)
class ToyOptIn(Action):
    """A removal that any item takes; it is only ever listed through its kind."""

    def label(self, data=None) -> str:
        return TOY_LABEL

    def resources(self, data=None) -> dict[str, int]:
        return {TOY_LABEL: 1}

    def reads(self, data) -> Reads:
        return Reads(junk=True, families=frozenset())

    def adds(self, data=None, item=None) -> Adds:
        return Adds.removal()

    def outcomes(self, data, item) -> Finite:
        return Finite(data, item, ((Fraction(1), item),))  # never run here: the test only asks the catalog and the offers


def toy_members(data, item):
    yield ToyOptIn()


@pytest.fixture
def toy_opt_in():
    with registered(Kind(TOY, toy_members, order=900, planner=True, opt_in=True)):
        yield


def test_an_opt_in_kind_is_left_out_of_the_planner_catalog(toy_opt_in):
    assert ToyOptIn() not in catalog(PRICED_DATA, item(base_id=BELT), planner_only=True)


def test_an_opt_in_kind_is_listed_when_a_target_names_it(toy_opt_in):
    assert ToyOptIn() in catalog(PRICED_DATA, item(base_id=BELT), planner_only=True, names=[TOY])


def test_a_catalog_that_is_not_the_planners_still_lists_an_opt_in_kind(toy_opt_in):
    assert ToyOptIn() in catalog(PRICED_DATA, item(base_id=BELT))


def test_the_planner_kinds_list_an_opt_in_kind_so_a_target_may_name_it(toy_opt_in):
    assert TOY in {entry.name for entry in kinds(planner_only=True)}


def test_offers_leave_an_opt_in_kind_out_unless_the_target_names_it(toy_opt_in):
    start = item(base_id=BELT)
    goal = Goal((Wanted(frozenset({LIFE})),))

    unnamed = offers_for(PRICED_DATA, goal, BELT, start, kinds_named=None)
    assert TOY_LABEL not in {offer.label for offer in unnamed.offers}

    named = offers_for(PRICED_DATA, goal, BELT, start, kinds_named=[TOY])
    assert [offer.label for offer in named.offers] == [TOY_LABEL]
    assert named.offers[0].action == ToyOptIn()
