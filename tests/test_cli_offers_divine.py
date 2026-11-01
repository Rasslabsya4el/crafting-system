"""A planner offers a Divine Orb only for a target with a roll limit on a mod that can occur on the item (ticket #71).

The action declares `Adds.needs_roll_limit`; `cli._offers.offers_for` reads the declaration and names no concrete
action (`test_actions_no_concrete_imports.py`). A roll limit is a requirement leaf with a `min_roll` that asks for
some value; a mod can occur on the item when the start item holds it, a draw of the item's pool can give it, or
an offered action adds it by name.
"""

import datetime

from actions_support import DATA, amulet
from items_support import roll

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import DivineOrb
from crafting_system.cli._offers import offer_of, offers_for, price_offers
from crafting_system.items import Rarity
from crafting_system.prices import PriceEntry, PriceFile

LIFE, LIFE_2 = "IncreasedLife1", "IncreasedLife2"
RESIST = "LightningResist1"


def divine_offers(goal, start):
    offered = offers_for(DATA, goal, start.base_id, start)
    return [offer for offer in offered.offers if isinstance(offer.action, DivineOrb)], offered


def test_a_divine_orb_is_offered_for_a_roll_limit_on_a_mod_that_can_be_drawn():
    goal = Goal((Wanted(frozenset({LIFE, LIFE_2}), min_roll=(20,)),))
    offers, _ = divine_offers(goal, amulet(roll(RESIST)))

    assert [offer.action for offer in offers] == [DivineOrb()]
    assert offers[0].resources == {"Divine Orb": 1}


def test_a_divine_orb_is_offered_for_a_roll_limit_on_a_mod_the_start_item_holds():
    goal = Goal((Wanted(frozenset({RESIST}), min_roll=(9,)),))
    offers, _ = divine_offers(goal, amulet(roll(RESIST)))

    assert len(offers) == 1


def test_a_divine_orb_is_left_out_for_a_target_without_a_roll_limit_and_nothing_is_said_about_it():
    goal = Goal((Wanted(frozenset({LIFE, LIFE_2})),))
    offers, offered = divine_offers(goal, amulet(roll(RESIST)))

    assert offers == []
    assert not any("Divine Orb" in left.labels for left in offered.left_out)


def test_a_roll_limit_that_asks_for_no_value_is_no_roll_limit():
    goal = Goal((Wanted(frozenset({LIFE}), min_roll=(None,)),))

    assert divine_offers(goal, amulet(roll(RESIST)))[0] == []


def test_a_roll_limit_on_a_mod_that_cannot_occur_on_the_item_does_not_offer_it():
    nowhere = next(mod.id for mod in DATA.mods.values() if mod.generation_type in ("prefix", "suffix") and mod.stats
                   and not any(weight.weight > 0 for weight in mod.spawn_weights) and mod.domain == "item")
    goal = Goal((Wanted(frozenset({nowhere}), min_roll=(1,)),))
    offers, offered = divine_offers(goal, amulet(roll(RESIST)))

    assert offers == []
    assert [left.labels for left in offered.left_out if "roll limit" in left.reason] == [("Divine Orb",)]  # a limit was asked for, so the report says why


def test_a_normal_start_item_is_offered_no_divine_orb_even_when_a_draw_may_give_the_mod():
    # the catalog lists the orb only for magic and rare items, so a normal start has none to offer
    goal = Goal((Wanted(frozenset({LIFE}), min_roll=(20,)),))

    assert divine_offers(goal, amulet(rarity=Rarity.NORMAL))[0] == []


def test_a_divine_orb_is_priced_by_its_entry_of_the_price_file_or_by_the_divine_rate():
    offer = offer_of(DivineOrb(), "Divine Orb", DATA, amulet(roll(LIFE)))
    when = datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC)
    listed = PriceFile("Test", when, 300.0, {"Divine Orb": PriceEntry(372.2, "poe.ninja")})
    unlisted = PriceFile("Test", when, 300.0, {})

    (priced,) = price_offers([offer], listed)[0]
    assert priced.cost == 372.2 and priced.parts[0][3] == "poe.ninja"
    (rated,) = price_offers([offer], unlisted)[0]
    assert rated.cost == 300.0 and rated.parts[0][3] == "rate"
