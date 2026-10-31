"""The contract suite runs on every kind of the catalog without being edited (ticket #108).

The checks are in `contract_support.py`. A new kind registered in `actions` is found here by the
catalog: its members on the fixture items are checked, and `test_every_kind_applies_on_some_fixture_item`
fails when a kind is registered that no fixture item can use (add the item it needs to `fixture_items`).
"""

import dataclasses
import json

import pytest
from cli_support import R12, price_file
from contract_support import CONTRACT_DATA, check_action, contract_pairs, fixture_items
from targets_support import DATA

from crafting_system.actions import ActionError, kinds
from crafting_system.cli import PricedOffer, make_plan, parse_route
from crafting_system.cli._offers import offer_of
from crafting_system.targets import load_target

PAIRS = contract_pairs()
ITEMS = fixture_items()


def _id(pair) -> str:
    kind, action, item = pair
    return f"{kind}:{action.label(CONTRACT_DATA)}@{item}"


@pytest.mark.parametrize("pair", PAIRS, ids=_id)
def test_the_action_meets_the_contract(pair):
    _, action, item = pair
    check_action(action, ITEMS[item])


def test_every_kind_applies_on_some_fixture_item():
    applied = set()
    for kind, action, item in PAIRS:
        try:
            action.outcomes(CONTRACT_DATA, ITEMS[item])
        except ActionError:
            continue
        applied.add(kind)
    assert {entry.name for entry in kinds()} <= applied


def test_a_kind_lists_each_action_once_per_item():
    for item in ITEMS.values():
        for entry in kinds():
            members = list(entry.members(CONTRACT_DATA, item))
            assert len(members) == len(set(members)), entry.name


@pytest.fixture(scope="module")
def plan():
    return make_plan(DATA, load_target(R12, DATA), price_file())


@pytest.mark.parametrize("pair", PAIRS, ids=_id)
def test_the_label_round_trips_through_a_given_route(pair, plan):
    _, action, item = pair
    label = action.label(CONTRACT_DATA)
    priced = PricedOffer(offer_of(action, label, CONTRACT_DATA, ITEMS[item]), 1.0, ())
    only = dataclasses.replace(plan, offers=(priced,), dropped=())
    route = parse_route(f"rules:\n  - do: {json.dumps(label)}\n", only, DATA, "route.yaml")
    assert route.rules[0].do == label
