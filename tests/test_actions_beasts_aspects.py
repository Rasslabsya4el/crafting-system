"""The aspect beasts against their exact hand oracle, and what they refuse (ticket #147).

An aspect craft adds one suffix that grants the skill, at level 20 or 30: a deterministic add of a named mod,
like a bench craft, but the mod is of the `item` domain, so the item holds it as an ordinary explicit mod and
the craft ignores the limit of crafted mods (`beastcraft.aspect_needs_open_suffix`, approximate). The fixture
lacks the eight mods, so `beasts_support` adds synthetic copies of a fixture suffix with their real ids.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from abstraction_pool import COLD_RESIST, LIFE_1, MANA_1, RESIST_2
from beasts_support import (
    AMULET,
    ASPECT_IDS,
    BEAST_DATA,
    COLD,
    DAMAGE,
    DATA,
    FIRE,
    LIFE,
    MANA,
    SHIELD,
    TALISMAN,
    beast_data,
    contract_beast_data,
    contract_item,
    rare,
    roll,
)
from contract_support import check_action
from repoe_support import no_network  # noqa: F401

from crafting_system.actions import NotApplicableError, OutOfScopeError, catalog, kinds
from crafting_system.actions.beasts import AspectBeast
from crafting_system.items import Influence, Item, Rarity

ASPECTS = ("avian", "cat", "crab", "spider")
BEASTS = {  # the named beast of each aspect recipe
    "avian": "Saqawal, First of the Sky",
    "cat": "Farrul, First of the Plains",
    "crab": "Craiceann, First of the Deep",
    "spider": "Fenumus, First of the Night",
}
ALL = [(aspect, level) for aspect in ASPECTS for level in (20, 30)]
IDS = {  # the real ids, written out (claim beastcraft.aspect_mods)
    ("avian", 20): "GrantsBirdAspectCrafted",
    ("avian", 30): "GrantsBirdAspectCrafted30",
    ("cat", 20): "GrantsCatAspectCrafted",
    ("cat", 30): "GrantsCatAspectCrafted30",
    ("crab", 20): "GrantsCrabAspectCrafted",
    ("crab", 30): "GrantsCrabAspectCrafted30",
    ("spider", 20): "GrantsSpiderAspectCrafted",
    ("spider", 30): "GrantsSpiderAspectCrafted30",
}


def amulet(*mod_ids, **fields) -> Item:
    return rare(AMULET, mod_ids, **fields)


def listed(item: Item, data=BEAST_DATA) -> list:
    return [action for action in catalog(data, item) if isinstance(action, AspectBeast)]


def test_the_test_data_holds_the_real_ids():
    assert ASPECT_IDS == IDS
    assert {action.mod_id for action in map(lambda pair: AspectBeast(*pair), ALL)} == set(IDS.values())
    assert all(AspectBeast(*pair).mod_id == IDS[pair] for pair in ALL)


# --- one mod added -----------------------------------------------------------------------------------


@pytest.mark.parametrize(("aspect", "level"), ALL)
def test_the_craft_adds_its_suffix_at_its_lowest_values_as_an_ordinary_mod_with_certainty(aspect, level):
    start = amulet(LIFE, FIRE)

    outcomes = AspectBeast(aspect, level).outcomes(BEAST_DATA, start)

    [(chance, result)] = outcomes.results
    assert chance == 1
    assert result.mods == tuple(sorted((*start.mods, roll(IDS[aspect, level])), key=lambda mod: mod.mod_id))
    added = next(entry for entry in result.mods if entry.mod_id == IDS[aspect, level])
    assert (added.tier, added.values, added.crafted, added.fractured) == (1, (level,), False, False)
    assert result.crafted_mods == ()
    assert outcomes.fractures is False


def test_chance_all_is_one_for_the_new_and_the_old_mods_and_zero_for_the_rest():
    outcomes = AspectBeast("cat", 30).outcomes(BEAST_DATA, amulet(LIFE, FIRE))

    assert outcomes.chance_all([IDS["cat", 30]]) == 1
    assert outcomes.chance_all([IDS["cat", 30], LIFE, FIRE]) == 1
    assert outcomes.chance_all([IDS["cat", 20]]) == 0
    assert outcomes.chance_all([IDS["cat", 30], IDS["avian", 30]]) == 0  # two aspects share a family
    assert outcomes.chance_all([IDS["cat", 30], "LightningResist1"]) == 0
    assert outcomes.chance_all([]) == 1
    with pytest.raises(ValueError, match="NoSuchMod is not in the game data"):
        outcomes.chance_all(["NoSuchMod"])


def test_the_distribution_has_the_one_new_mod_seen_through_the_label_with_probability_one():
    outcomes = AspectBeast("spider", 20).outcomes(BEAST_DATA, amulet(LIFE))

    assert dict(outcomes.distribution(lambda mod: mod.id)) == {frozenset({(IDS["spider", 20], 1)}): Fraction(1)}
    assert dict(outcomes.distribution(lambda mod: mod.generation_type)) == {frozenset({("suffix", 1)}): Fraction(1)}


def test_the_seeded_sample_is_the_item_with_the_aspect_and_valid():
    start = amulet(LIFE, SHIELD, FIRE)
    outcomes = AspectBeast("crab", 30).outcomes(BEAST_DATA, start)

    for seed in range(10):
        finished = outcomes.sample(random.Random(seed))
        finished.validate(BEAST_DATA)
        assert {entry.mod_id for entry in finished.mods} == {entry.mod_id for entry in start.mods} | {IDS["crab", 30]}
        assert finished == outcomes.results[0][1]


def test_the_components_are_the_one_fixed_result():
    outcomes = AspectBeast("avian", 20).outcomes(BEAST_DATA, amulet(LIFE))

    [(share, part)] = outcomes.components
    assert share == 1 and part.result == outcomes.results[0][1]


def test_no_item_level_gate_applies():
    low = amulet(LIFE, item_level=1)

    assert AspectBeast("cat", 20).outcomes(BEAST_DATA, low).chance_all([IDS["cat", 20]]) == 1


def test_full_prefixes_and_an_open_suffix_take_the_craft():
    full_prefixes = amulet(LIFE, SHIELD, DAMAGE, FIRE)

    assert AspectBeast("cat", 20).outcomes(BEAST_DATA, full_prefixes).chance_all([IDS["cat", 20]]) == 1


def test_the_craft_takes_an_influenced_item_and_a_fractured_one():
    fractured = Item.build(
        BEAST_DATA, base_id=AMULET, item_level=86, rarity=Rarity.RARE, mods=(roll(LIFE, fractured=True), roll(FIRE))
    )
    influenced = amulet(LIFE, influences=frozenset({Influence.SHAPER}))

    for item in (fractured, influenced):
        assert AspectBeast("cat", 20).outcomes(BEAST_DATA, item).chance_all([IDS["cat", 20]]) == 1


def test_the_craft_works_on_a_talisman_too():
    assert AspectBeast("cat", 20).outcomes(BEAST_DATA, rare(TALISMAN, (LIFE,))).chance_all([IDS["cat", 20]]) == 1


# --- refusals ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.MAGIC])
def test_a_normal_or_magic_item_is_out_of_scope(rarity):
    item = amulet(LIFE, rarity=rarity) if rarity is Rarity.MAGIC else amulet(rarity=rarity)

    with pytest.raises(OutOfScopeError, match="no admitted rule"):
        AspectBeast("cat", 20).outcomes(BEAST_DATA, item)


def test_a_corrupted_item_is_refused():
    with pytest.raises(NotApplicableError, match="corrupted"):
        AspectBeast("cat", 20).outcomes(BEAST_DATA, amulet(LIFE, corrupted=True))


def test_an_item_with_three_suffixes_has_no_free_suffix():
    with pytest.raises(NotApplicableError, match="no free suffix slot"):
        AspectBeast("cat", 20).outcomes(BEAST_DATA, amulet(LIFE, FIRE, COLD, MANA))


@pytest.mark.parametrize(("aspect", "level"), [("cat", 20), ("cat", 30), ("avian", 20), ("spider", 30)])
def test_an_item_that_holds_an_aspect_refuses_every_other_aspect(aspect, level):
    held = amulet(LIFE, IDS[aspect, level])

    for other in ALL:
        with pytest.raises(NotApplicableError, match="shares a family"):
            AspectBeast(*other).outcomes(BEAST_DATA, held)


def test_the_refusals_come_in_order_rarity_corruption_slot_family():
    with pytest.raises(OutOfScopeError):
        AspectBeast("cat", 20).outcomes(BEAST_DATA, amulet(rarity=Rarity.NORMAL, corrupted=True))
    with pytest.raises(NotApplicableError, match="corrupted"):
        AspectBeast("cat", 20).outcomes(BEAST_DATA, amulet(FIRE, COLD, IDS["cat", 20], corrupted=True))
    with pytest.raises(NotApplicableError, match="no free suffix slot"):
        AspectBeast("cat", 20).outcomes(BEAST_DATA, amulet(FIRE, COLD, IDS["avian", 20]))


def test_the_data_without_the_aspect_mods_is_a_value_error_not_a_refusal():
    with pytest.raises(ValueError, match="GrantsCatAspectCrafted is not a mod"):
        AspectBeast("cat", 20).outcomes(DATA, rare(AMULET, (LIFE,), data=DATA))
    with pytest.raises(ValueError, match="not a mod in the game data"):
        AspectBeast("cat", 20).reads(DATA)


@pytest.mark.parametrize(("aspect", "level"), [("dragon", 20), ("Cat", 20), ("", 30), ("cat", 25), ("cat", 0), ("cat", 40)])
def test_an_aspect_or_a_level_outside_the_recipes_is_a_value_error(aspect, level):
    with pytest.raises(ValueError, match="must be one of"):
        AspectBeast(aspect, level)


# --- the contract every action meets -------------------------------------------------------------------


@pytest.mark.parametrize(("aspect", "level"), [("cat", 30), ("avian", 20), ("spider", 20), ("crab", 30)])
def test_the_aspect_meets_the_contract_suite_where_it_applies_and_where_it_refuses(aspect, level):
    data = contract_beast_data()
    action = AspectBeast(aspect, level)
    applies = contract_item(AMULET, (RESIST_2, LIFE_1), data=data)
    full_suffixes = contract_item(AMULET, (RESIST_2, MANA_1, COLD_RESIST), data=data)
    holds_an_aspect = contract_item(AMULET, (RESIST_2, LIFE_1, IDS["cat", 20]), data=data)
    magic = contract_item(AMULET, (LIFE_1,), data=data, rarity=Rarity.MAGIC)

    assert check_action(action, applies, data) is True
    assert [check_action(action, item, data) for item in (full_suffixes, holds_an_aspect, magic)] == [False] * 3


# --- the action around the outcomes -------------------------------------------------------------------


def test_the_labels():
    assert AspectBeast("cat", 30).label() == "Beastcraft Aspect of the Cat (level 30)"
    assert AspectBeast("avian", 20).label(BEAST_DATA) == "Beastcraft Aspect of the Avian (level 20)"
    assert len({AspectBeast(*pair).label() for pair in ALL}) == 8


@pytest.mark.parametrize("aspect", ASPECTS)
def test_a_level_20_aspect_costs_its_beast_and_three_rare_beasts_as_chaos_orbs(aspect):
    assert AspectBeast(aspect, 20).resources() == {BEASTS[aspect]: 1, "Chaos Orb": 3}
    assert AspectBeast(aspect, 20, rare_creature_price=2).resources() == {BEASTS[aspect]: 1, "Chaos Orb": 6}


@pytest.mark.parametrize("aspect", ASPECTS)
def test_a_level_30_aspect_adds_the_black_morrigan_and_one_rare_beast_fewer(aspect):
    assert AspectBeast(aspect, 30).resources(BEAST_DATA) == {BEASTS[aspect]: 1, "The Black Mórrígan": 1, "Chaos Orb": 2}
    assert AspectBeast(aspect, 30, rare_creature_price=2).resources() == {BEASTS[aspect]: 1, "The Black Mórrígan": 1, "Chaos Orb": 4}


def test_the_rare_creature_price_is_part_of_the_action():
    assert AspectBeast("cat", 20) == AspectBeast("cat", 20, rare_creature_price=1)
    assert AspectBeast("cat", 20) != AspectBeast("cat", 20, rare_creature_price=2)
    assert len({AspectBeast(*pair) for pair in ALL}) == 8


def test_the_declarations_are_those_of_a_named_ordinary_add():
    action = AspectBeast("crab", 30)
    reads, adds = action.reads(BEAST_DATA), action.adds(BEAST_DATA, amulet(LIFE))

    assert reads.junk and reads.families == frozenset({"GrantedSkill"}) and reads.block_invariant is True
    assert reads.pool_weight is False and reads.needs_crafted is False
    assert adds.named == frozenset({IDS["crab", 30]}) and adds.crafted is False and adds.draws is False
    assert action.adds().named == adds.named


def test_the_kind_lists_the_eight_aspects_for_a_rare_item_and_is_not_a_planner_kind():
    assert listed(amulet(LIFE)) == [AspectBeast(*pair) for pair in ALL]  # the order: aspect, then level
    assert listed(amulet()) == listed(amulet(LIFE))
    assert listed(amulet(LIFE, rarity=Rarity.MAGIC)) == [] and listed(amulet(rarity=Rarity.NORMAL)) == []
    assert AspectBeast("cat", 20) not in catalog(BEAST_DATA, amulet(LIFE), planner_only=True)
    registered = {entry.name: entry for entry in kinds()}["aspect-beast"]
    assert registered.planner is False and registered.order == 84 and "#149" in registered.why_not


def test_the_kind_lists_only_the_aspects_whose_mod_is_in_the_data():
    partial = beast_data(talisman=False, aspects=True)
    mods = {mod_id: mod for mod_id, mod in partial.mods.items() if mod_id not in (IDS["cat", 20], IDS["spider", 30])}
    partial = dataclasses.replace(partial, mods=mods)

    found = listed(rare(AMULET, (LIFE,), data=partial), partial)

    assert {(action.aspect, action.level) for action in found} == set(ALL) - {("cat", 20), ("spider", 30)}
    assert listed(rare(AMULET, (LIFE,), data=DATA), DATA) == []


def test_an_aspect_is_refused_and_not_offered_on_a_base_of_another_domain():
    jewel_base = dataclasses.replace(BEAST_DATA.base_items[AMULET], domain="item_jewel")
    data = dataclasses.replace(BEAST_DATA, base_items={**BEAST_DATA.base_items, AMULET: jewel_base})
    item = rare(AMULET, [LIFE], data=BEAST_DATA)
    assert not [action for action in catalog(data, item) if isinstance(action, AspectBeast)]
    with pytest.raises(NotApplicableError, match="does not fit the base"):
        AspectBeast("cat", 20).outcomes(data, item)
