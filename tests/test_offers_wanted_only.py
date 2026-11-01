"""An action that declares `Adds.wanted_only` is offered only for a target that wants a mod it names (ticket #147).

The aspect beasts are the case: one fixed suffix and nothing else, so a target that wants none of the aspects gains
nothing from their price and their slot. Their kind is not a planner kind yet (#149), so the test registers a planner
kind of the same actions for the length of each test.
"""

import pytest
from contract_support import CONTRACT_DATA, GOAL, fixture_items

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import AspectBeast, Kind, registered
from crafting_system.actions.beasts import ASPECT_LEVELS, ASPECT_WORDS
from crafting_system.cli._offers import offers_for
from crafting_system.items import Rarity


def aspect_members(data, item):
    if item.rarity is Rarity.RARE:
        for aspect in ASPECT_WORDS:
            for level in ASPECT_LEVELS:
                yield AspectBeast(aspect, level)


@pytest.fixture
def aspects_registered():
    with registered(Kind("toy-aspect-beast", aspect_members, order=901)):
        yield


def aspect_offers(goal):
    start = fixture_items()["rare_junk"]
    offered = offers_for(CONTRACT_DATA, goal, start.base_id, start)
    return [offer for offer in offered.offers if isinstance(offer.action, AspectBeast)], offered


def test_the_aspect_beasts_are_declared_wanted_only():
    assert AspectBeast("cat", 20).adds(CONTRACT_DATA).wanted_only


def test_no_aspect_is_offered_for_a_target_that_names_none(aspects_registered):
    offers, offered = aspect_offers(GOAL)
    assert offers == []
    reported = [label for left in offered.left_out if "fixed mod" in left.reason for label in left.labels]
    assert len(reported) == len(ASPECT_WORDS) * len(ASPECT_LEVELS)
    assert all(label.startswith("Beastcraft Aspect") for label in reported)


def test_only_the_aspect_a_target_names_is_offered(aspects_registered):
    wanted = AspectBeast("crab", 30)
    goal = Goal((Wanted(wanted.adds(CONTRACT_DATA).named),))
    offers, _ = aspect_offers(goal)
    assert [offer.action for offer in offers] == [wanted]
