"""What the CLI's model offers for a target, and the restart (ticket #60), on the fixture belt and amulet.

The rule under test: a bench craft is offered ONLY WHEN ITS MOD COUNTS TOWARD A REQUIREMENT. Every other
action of this slice erases crafted mods, so a craft that gives the goal nothing only takes a slot and
costs currency; leaving it out is exact (see `offers_for`).
"""

import dataclasses
import random

import pytest
from cli_support import R12, START, price_file
from items_support import AMULET, DATA, item, roll

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import ApplyEssence, BenchCraft, ChaosOrb, RemoveCraftedMods, bench_crafts
from crafting_system.cli import RESTART, BuyStartItem, make_plan, offers_for
from crafting_system.items import Rarity
from crafting_system.targets import load_target

BELT = "Metadata/Items/Belts/Belt3"
DAMAGE_1, DAMAGE_2 = "JunMaster2AllDamage2_", "JunMaster2AllDamage3"  # prefixes, Ring and Belt only
HYBRID = "JunMaster2ArmourAndEnergyShield1"  # a prefix of Belts, not wanted below
LIFE = "IncreasedLife1"


def with_currency_names(data):
    """The fixture data with the currency base items that the bench prices name (the fixture has none)."""
    template = next(iter(data.base_items.values()))
    names = {
        "CurrencyRerollRare": "Chaos Orb",
        "CurrencyAddModToRare": "Exalted Orb",
        "CurrencyRerollMagic": "Orb of Alteration",
        "CurrencyModValues": "Divine Orb",
        "CurrencyConvertToNormal": "Orb of Scouring",
    }
    extra = {
        f"Metadata/Items/Currency/{key}": dataclasses.replace(
            template, id=f"Metadata/Items/Currency/{key}", name=name, item_class="StackableCurrency"
        )
        for key, name in names.items()
    }
    return dataclasses.replace(data, base_items={**data.base_items, **extra})


PRICED_DATA = with_currency_names(DATA)


def offered(goal: Goal, *, base_id: str = BELT, start=None):
    start = start if start is not None else item(base_id=base_id)
    return offers_for(PRICED_DATA, goal, base_id, start)


def crafts_for(item_class: str) -> int:
    """How many crafts of the fixture bench are offered for `item_class`."""
    return sum(item_class in craft.option(DATA).item_classes for craft in bench_crafts(DATA))


def crafts(offer_set) -> set[str]:
    return {offer.action.mod_id for offer in offer_set.offers if isinstance(offer.action, BenchCraft)}


def test_a_craft_whose_mod_counts_toward_a_requirement_is_offered_and_the_others_are_left_out():
    chosen = offered(Goal((Wanted(frozenset({DAMAGE_1})),)))

    assert crafts(chosen) == {DAMAGE_1}
    (left,) = chosen.left_out
    assert len(left.labels) == crafts_for("Belt") - 1  # every other craft of the belt
    assert any(isinstance(offer.action, RemoveCraftedMods) for offer in chosen.offers)


def test_a_craft_giving_the_goal_nothing_is_not_offered_and_neither_is_remove_crafted_mods():
    chosen = offered(Goal((Wanted(frozenset({LIFE})),)))

    assert crafts(chosen) == set()
    assert not any(isinstance(offer.action, RemoveCraftedMods) for offer in chosen.offers)
    (left,) = chosen.left_out
    assert len(left.labels) == crafts_for("Belt") and all(label.startswith("Bench craft ") for label in left.labels)


def test_a_requirement_that_refuses_a_crafted_mod_does_not_count_the_craft():
    chosen = offered(Goal((Wanted(frozenset({DAMAGE_1}), not_crafted=True),)))

    assert crafts(chosen) == set()


def test_a_craft_of_another_item_class_is_not_listed():
    chosen = offered(Goal((Wanted(frozenset({DAMAGE_1})),)), base_id=AMULET)

    assert crafts(chosen) == set()
    assert sum(len(left.labels) for left in chosen.left_out) == crafts_for("Amulet")  # only the crafts of its class
    assert all(("increased Damage" not in label) for left in chosen.left_out for label in left.labels)  # Ring and Belt


def test_a_start_item_with_a_crafted_mod_gets_remove_crafted_mods_without_any_craft():
    start = item(roll(DAMAGE_1, crafted=True), base_id=BELT)

    chosen = offered(Goal((Wanted(frozenset({LIFE})),)), start=start)

    assert any(isinstance(offer.action, RemoveCraftedMods) for offer in chosen.offers)


def test_the_rerolls_and_the_essences_of_the_item_class_are_offered_by_their_names():
    chosen = offered(Goal((Wanted(frozenset({LIFE})),)))

    assert any(isinstance(offer.action, ChaosOrb) for offer in chosen.offers)
    assert any(offer.label == "Harvest Reforge Lightning" for offer in chosen.offers)
    assert not any(isinstance(offer.action, ApplyEssence) for offer in chosen.offers)  # level 1 works on a normal item only


def test_a_low_essence_is_offered_for_a_normal_start_item_only():
    goal = Goal((Wanted(frozenset({LIFE})),))
    normal = offered(goal, start=item(base_id=BELT, rarity=Rarity.NORMAL))

    assert [o.label for o in normal.offers if isinstance(o.action, ApplyEssence)] == ["Whispering Essence of Hatred"]


def test_the_restart_is_an_action_of_every_state_but_the_start_and_ends_in_the_start():
    target = load_target(R12, DATA)
    plan = make_plan(DATA, target, price_file(start=4.0))
    restart = next(priced for priced in plan.offers if priced.label == RESTART)

    assert restart.cost == 4.0 and restart.parts == ((START, 1, 4.0, "trade-api"),)
    assert isinstance(restart.offer.action, BuyStartItem)
    action = plan.offer_of(plan.policy[plan.start])  # the start state itself never restarts
    assert action.label != RESTART


def test_a_free_start_item_has_no_restart():
    target = load_target(R12, DATA)
    plan = make_plan(DATA, target, price_file(start=None), start_price=0.0)

    assert all(priced.label != RESTART for priced in plan.offers)


def test_buying_again_gives_back_the_start_item_whatever_it_was():
    target = load_target(R12, DATA)
    buy = BuyStartItem(target.start_item)

    assert buy.outcomes(DATA, item(base_id=AMULET)).sample(random.Random(1)) == target.start_item


@pytest.mark.parametrize("label", ["Chaos Orb", "Harvest Reforge Lightning"])
def test_r12_keeps_its_two_rerolls(label):
    plan = make_plan(DATA, load_target(R12, DATA), price_file())

    assert label in [priced.label for priced in plan.offers]


def test_a_target_naming_action_kinds_is_offered_those_kinds_only_and_the_rest_is_listed():
    goal = Goal((Wanted(frozenset({DAMAGE_1})),))
    start = item(base_id=BELT)

    chosen = offers_for(PRICED_DATA, goal, BELT, start, ["chaos-orb", "bench-craft", "remove-crafted-mods"])

    labels = {offer.label for offer in chosen.offers}
    assert "Chaos Orb" in labels and not any(label.startswith("Harvest") or "Essence" in label for label in labels)
    assert crafts(chosen) == {DAMAGE_1}
    named = chosen.left_out[0]
    assert "essence" in named.labels and "harvest-reforge" in named.labels and "chaos-orb" not in named.labels


def test_an_unknown_action_kind_is_refused_with_the_kinds_there_are():
    with pytest.raises(ValueError, match="unknown action kind.*chaos-orb"):
        offers_for(PRICED_DATA, Goal((Wanted(frozenset({LIFE})),)), BELT, item(base_id=BELT), ["chaos-orbs"])


MAGIC_ORBS = {"Orb of Transmutation", "Orb of Alteration", "Orb of Augmentation", "Regal Orb"}


def test_a_rare_start_item_is_offered_none_of_the_orbs_of_magic_items_and_a_normal_one_is():
    goal = Goal((Wanted(frozenset({LIFE})),))
    rare = item(roll(LIFE), base_id=BELT)  # rare: the start items of R10, R11, R05 and R12
    normal = item(base_id=BELT, rarity=Rarity.NORMAL)

    assert not MAGIC_ORBS & {offer.label for offer in offers_for(PRICED_DATA, goal, BELT, rare).offers}
    assert MAGIC_ORBS <= {offer.label for offer in offers_for(PRICED_DATA, goal, BELT, normal).offers}
