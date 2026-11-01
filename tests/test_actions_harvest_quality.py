"""The Harvest quality enchants as exact actions (ticket #240, ADR-0052).

"Done when": the contract suite passes unedited (it is run by `tests/test_actions_contract.py` through
`tests/contract_fixtures_harvest_quality.py`, not here); the cost of a body armour Life enchant is 3,250 Wild Lifeforce and of a
weapon enchant 5,000; a Tailoring Orb after a quality enchant replaces it.

Every expected number is written by hand in `harvest_quality_support.COSTS` (the wiki table), not read from the registry. The real
Tailoring Orb is ticket #239 and not landed, so `ToyTailoring` below stands for it.
"""

import dataclasses
import datetime
from fractions import Fraction

import pytest
from enchant_support import ARMOUR_EXTRA_SLOT, BODY, BOW, DATA as ENCHANT_DATA, LIFE as POOL_LIFE, SWORD
from harvest_quality_support import (
    ARMOUR,
    COSTS,
    CRITICAL,
    DEXTERITY,
    LIFE,
    MANA,
    PRIMAL,
    RANGE,
    VIVID,
    WEAPON,
    WILD,
    body_armour,
    quality_data,
    sword,
)
from items_support import AMULET, roll as fixture_roll

from crafting_system.actions import (
    Action,
    Adds,
    Finite,
    HarvestQualityEnchant,
    NotApplicableError,
    Reads,
    kinds,
)
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.rules import get_rule

DATA = quality_data(ENCHANT_DATA)
KIND = "harvest-quality-enchant"
ALL_MODS = {**ARMOUR, **WEAPON}


def amulet(data: GameData = DATA) -> Item:
    return Item.build(data, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=())


def single(outcomes: Finite) -> Item:
    ((chance, result),) = outcomes.results
    assert chance == Fraction(1)
    return result


@dataclasses.dataclass(frozen=True)
class ToyTailoring(Action):
    """A toy Tailoring Orb: it puts `enchant` on the item, replacing the one there, and touches nothing else."""

    enchant: str = POOL_LIFE

    @property
    def variant(self) -> str:
        return self.enchant

    def label(self, data: GameData | None = None) -> str:
        return "Toy Tailoring"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Tailoring Orb": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset())

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, enchantment=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        return Finite(data, item, ((Fraction(1), item.changed(data, enchantment=self.enchant)),))


# --- the cost ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("mod_id", sorted(ALL_MODS))
def test_the_cost_of_each_enchant_is_the_hand_typed_wiki_table(mod_id):
    assert HarvestQualityEnchant(mod_id).resources(DATA) == COSTS[mod_id]


def test_the_costs_the_ticket_names():
    assert HarvestQualityEnchant(LIFE).resources() == {"Wild Crystallised Lifeforce": 3250}
    assert HarvestQualityEnchant(RANGE).resources() == {"Wild Crystallised Lifeforce": 5000}
    assert HarvestQualityEnchant(CRITICAL).resources() == {PRIMAL: 5000}
    assert HarvestQualityEnchant(DEXTERITY).resources() == {VIVID: 3250}


def test_the_life_enchant_is_priced_from_the_price_file():
    price = 0.0156
    prices = PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, {WILD: PriceEntry(price, "test")})
    action = HarvestQualityEnchant(LIFE)
    priced, dropped = price_offers([offer_of(action, action.label(DATA), DATA, body_armour(DATA))], prices)
    assert not dropped and len(priced) == 1
    assert priced[0].cost == pytest.approx(3250 * price)


def test_an_enchant_is_dropped_when_its_lifeforce_has_no_price():
    action = HarvestQualityEnchant(CRITICAL)  # Primal; the file prices only the Wild one
    prices = PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, {WILD: PriceEntry(0.0156, "test")})
    priced, dropped = price_offers([offer_of(action, action.label(DATA))], prices)
    assert not priced and len(dropped) == 1 and dropped[0].missing == (PRIMAL,)


# --- the result ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.RARE])
def test_the_result_is_one_item_of_chance_one_holding_the_enchant(rarity):
    item = body_armour(DATA, rarity=rarity)
    outcomes = HarvestQualityEnchant(LIFE).outcomes(DATA, item)
    assert isinstance(outcomes, Finite)
    assert len(outcomes.results) == 1
    ((chance, result),) = outcomes.results
    assert chance == Fraction(1)
    assert result == item.changed(DATA, enchantment=LIFE)
    assert result.enchantment == LIFE and item.enchantment is None
    assert (result.mods, result.rarity, result.corrupted, result.base_id) == (item.mods, item.rarity, item.corrupted, item.base_id)


def test_a_magic_item_takes_the_enchant_too():
    item = Item.build(DATA, base_id=BODY, item_level=84, rarity=Rarity.MAGIC, mods=(fixture_roll("IncreasedLife1"),))
    result = single(HarvestQualityEnchant(LIFE).outcomes(DATA, item))
    assert result == item.changed(DATA, enchantment=LIFE)
    assert result.mods == item.mods


# --- replacing -----------------------------------------------------------------------------------------


def test_the_enchant_replaces_a_tailoring_pool_enchant():
    held = body_armour(DATA, enchantment=POOL_LIFE)
    result = single(HarvestQualityEnchant(LIFE).outcomes(DATA, held))
    assert result.enchantment == LIFE
    assert POOL_LIFE not in repr(result) and held.enchantment == POOL_LIFE


def test_the_enchant_replaces_the_extra_crafted_mod_slot_enchant():
    held = body_armour(DATA, enchantment=ARMOUR_EXTRA_SLOT)
    assert single(HarvestQualityEnchant(LIFE).outcomes(DATA, held)).enchantment == LIFE


def test_the_enchant_replaces_another_quality_enchant():
    held = body_armour(DATA, enchantment=MANA)
    result = single(HarvestQualityEnchant(LIFE).outcomes(DATA, held))
    assert result.enchantment == LIFE
    assert single(HarvestQualityEnchant(MANA).outcomes(DATA, result)).enchantment == MANA


def test_the_enchant_the_item_already_holds_changes_nothing():
    held = body_armour(DATA, enchantment=LIFE)
    assert single(HarvestQualityEnchant(LIFE).outcomes(DATA, held)) == held


# --- replaced by a Tailoring Orb -------------------------------------------------------------------------


def test_a_tailoring_orb_after_a_quality_enchant_replaces_it():
    item = body_armour(DATA)
    enchanted = single(HarvestQualityEnchant(LIFE).outcomes(DATA, item))
    assert enchanted.enchantment == LIFE
    tailored = single(ToyTailoring().outcomes(DATA, enchanted))
    assert tailored.enchantment == POOL_LIFE
    assert tailored == item.changed(DATA, enchantment=POOL_LIFE)


def test_the_quality_enchant_after_a_tailoring_orb_replaces_it_the_other_way():
    item = body_armour(DATA)
    tailored = single(ToyTailoring().outcomes(DATA, item))
    assert tailored.enchantment == POOL_LIFE
    enchanted = single(HarvestQualityEnchant(LIFE).outcomes(DATA, tailored))
    assert enchanted.enchantment == LIFE
    assert enchanted == item.changed(DATA, enchantment=LIFE)


# --- refusals --------------------------------------------------------------------------------------------


def test_a_corrupted_item_is_refused():
    with pytest.raises(NotApplicableError, match="corrupted"):
        HarvestQualityEnchant(LIFE).outcomes(DATA, body_armour(DATA, corrupted=True))
    with pytest.raises(NotApplicableError, match="corrupted"):
        HarvestQualityEnchant(RANGE).outcomes(DATA, sword(DATA, corrupted=True))


def test_a_body_armour_enchant_is_refused_on_a_weapon():
    with pytest.raises(NotApplicableError, match="body armour"):
        HarvestQualityEnchant(LIFE).outcomes(DATA, sword(DATA))


def test_a_weapon_enchant_is_refused_on_a_body_armour():
    with pytest.raises(NotApplicableError):
        HarvestQualityEnchant(CRITICAL).outcomes(DATA, body_armour(DATA))


@pytest.mark.parametrize("mod_id", sorted(ALL_MODS))
def test_neither_class_of_enchant_works_on_an_amulet(mod_id):
    with pytest.raises(NotApplicableError):
        HarvestQualityEnchant(mod_id).outcomes(DATA, amulet())


def test_a_weapon_enchant_works_on_a_sword():
    item = sword(DATA)
    assert single(HarvestQualityEnchant(RANGE).outcomes(DATA, item)) == item.changed(DATA, enchantment=RANGE)


def test_a_weapon_enchant_works_on_a_bow():
    if BOW not in DATA.base_items:
        pytest.skip("the fixture data holds no bow")
    bow = Item.build(DATA, base_id=BOW, item_level=84, rarity=Rarity.RARE, mods=())
    assert single(HarvestQualityEnchant(RANGE).outcomes(DATA, bow)).enchantment == RANGE


# --- the catalog -----------------------------------------------------------------------------------------


def members(item: Item):
    (entry,) = (entry for entry in kinds() if entry.name == KIND)
    return list(entry.members(DATA, item))


def test_the_kind_is_not_a_planner_kind_and_says_why():
    (entry,) = (entry for entry in kinds() if entry.name == KIND)
    assert entry.planner is False and entry.why_not
    assert entry in kinds() and entry not in kinds(planner_only=True)
    assert KIND not in [other.name for other in kinds(planner_only=True)]


def test_a_body_armour_is_offered_the_eight_armour_enchants():
    found = members(body_armour(DATA))
    assert all(isinstance(action, HarvestQualityEnchant) for action in found)
    assert {action.mod_id for action in found} == set(ARMOUR) and len(found) == 8


def test_a_weapon_is_offered_the_six_weapon_enchants():
    found = members(sword(DATA))
    assert {action.mod_id for action in found} == set(WEAPON) and len(found) == 6


def test_an_amulet_is_offered_none():
    assert members(amulet()) == []


# --- the declarations ------------------------------------------------------------------------------------


def test_the_enchant_declares_that_it_adds_an_enchantment_and_nothing_else():
    item = body_armour(DATA)
    action = HarvestQualityEnchant(LIFE)
    adds = action.adds(DATA, item)
    assert adds.enchantment is True and adds.draws is False and adds.named == frozenset()
    assert not adds.item_state and not action.adds().item_state
    assert action.adds().draws is False and action.adds().named == frozenset()
    assert action.reads(DATA).enchantment is False


def test_a_mod_id_that_is_no_enchant_is_refused_at_construction():
    with pytest.raises(ValueError):
        HarvestQualityEnchant("Nope")


def test_the_fourteen_have_distinct_labels_a_variant_that_is_the_mod_id_and_a_positive_cost():
    actions = [HarvestQualityEnchant(mod_id) for mod_id in ALL_MODS]
    assert len(actions) == 14
    assert len({action.label(DATA) for action in actions}) == 14
    for action in actions:
        assert action.variant == action.mod_id
        resources = action.resources(DATA)
        assert resources and all(isinstance(count, int) and count > 0 for count in resources.values())


# --- the claims ------------------------------------------------------------------------------------------


def test_the_action_names_the_claims_its_answer_depends_on():
    claims = set(HarvestQualityEnchant(LIFE).claims(DATA))
    assert {
        "enchantment.harvest_quality_enchant_costs",
        "enchantment.quality_enchant_replaces_heist_enchant",
        "enchantment.one_slot_new_replaces_old",
        "enchantment.harvest_quality_enchants_14",
        "enchantment.quality_enchant_changes_only_its_stat",
    } <= claims


def test_the_replacement_of_a_heist_enchant_is_flagged_approximate():
    assert get_rule("enchantment.quality_enchant_replaces_heist_enchant").approximate is True


def test_the_registry_costs_equal_the_hand_typed_table():
    value = get_rule("enchantment.harvest_quality_enchant_costs").value
    assert {mod_id: dict(cost) for mod_id, cost in value.items()} == COSTS
