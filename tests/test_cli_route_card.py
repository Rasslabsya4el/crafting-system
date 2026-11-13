"""The item cards of the route view: a concrete item, the target, and the state after a step (ticket #78, piece B).

The cards come from the small amulet pool and the fixture belt; the R12 start and goal cards also run on
the real 3.29.3.3 dump, and skip cleanly when the cache is not there (CI fetches it, ticket #165).
"""

import dataclasses
from types import SimpleNamespace

import pytest
from abstraction_pool import AMULET, CRAFTED, GEM, RESIST_1, RESISTS, SMALL, small_item
from abstraction_pool import roll as small_roll
from abstraction_support import CHAOS, GOALS, REFORGE, real_game_data
from items_support import DATA, item, roll
from targets_support import EXAMPLES

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import ApplyEssence, BenchCraft, ChaosOrb, RemoveCraftedMods
from crafting_system.cli._route_card import (
    _leaf_slot,
    Group,
    ItemCard,
    Slot,
    _StateReader,
    card_of_item,
    card_of_states,
    card_of_target,
    essence_notes,
    essence_tier,
    mod_text,
    tracks_junk,
)
from crafting_system.cli._route_html import _item
from crafting_system.cli._route_tiers import tier_lines
from crafting_system.items import ExplicitMod, Influence, Rarity, Side, accepted_by_tier, tier_table
from crafting_system.targets import KOfN, Requirement, StartKind, Target, load_target

IMPLICIT = "(20-30)% increased Mana Regeneration Rate"
IMPLICIT_HELD = "20% increased Mana Regeneration Rate"  # the start amulet carries it at the low end of its range (#484)
IMPLICIT_ID = "ManaRegenerationImplicitAmulet1"
POOL = dataclasses.replace(SMALL, mods={**SMALL.mods, IMPLICIT_ID: DATA.mods[IMPLICIT_ID]})  # SMALL plus the base's implicit
EMPTY = Slot("empty", "empty")
ANY_OR_EMPTY = Slot("any mod or empty", "any")
ANY_MOD = Slot("any mod", "any")
RESIST_TEXT = "+#% to Lightning Resistance"
GEM_TEXT = "+1 to Level of all Lightning Skill Gems"

BELT = "Metadata/Items/Belts/Belt3"
BELT_LEVEL = 86
LIFE, LIFE_3, SHIELD = "IncreasedLife1", "IncreasedLife3", "IncreasedEnergyShield1"
FIRE, CHAOS_RES, REGEN = "FireResist1", "ChaosResist2", "LifeRegeneration1"
PREFIXES_LOCK = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix metamod
CRAFTS = (BenchCraft("JunMaster2AllDamage2_"), BenchCraft("JunMaster2ArmourAndEnergyShield1"), RemoveCraftedMods())
LIFE_LEAF = Wanted(frozenset({LIFE, "IncreasedLife2", LIFE_3}))


def small_abstraction(goal, level: int = 84, *, metamods: bool = False) -> Abstraction:
    """The small amulet pool with its implicit, rerolls only: a state keeps no junk (unless it models metamods)."""
    return Abstraction(POOL, GOALS[goal], AMULET, level, metamods=metamods)


def belt_abstraction(*, metamods: bool = False) -> Abstraction:
    """The fixture belt with the bench crafts enabled: the junk of a state is tracked."""
    return Abstraction(DATA, Goal((LIFE_LEAF,)), BELT, BELT_LEVEL, CRAFTS, metamods=metamods)


def belt(*mods, **fields):
    return item(*mods, base_id=BELT, item_level=BELT_LEVEL, **fields)


def target_of(*requirements, influences=frozenset()) -> Target:
    return Target(AMULET, 84, influences, tuple(requirements), small_item(), start=StartKind.GIVEN)


def gem_leaf() -> Requirement:
    return Requirement(None, GEM_TEXT, frozenset({GEM}))


def resist_leaf(**limits) -> Requirement:
    return Requirement("LightningResistance", None, RESISTS, **limits)


# --- the text of a mod ----------------------------------------------------------------------------------


def test_a_mod_text_is_the_game_text_with_its_roll_ranges():
    assert mod_text(DATA.mods["IncreasedLife3"]) == "+(40-54) to maximum Life"


def test_a_hybrid_mod_keeps_its_line_break_as_a_slash():
    text = mod_text(DATA.mods["JunMaster2ArmourAndEnergyShield1"])

    assert text == "+(105-150) to Armour / +(11-15) to maximum Energy Shield"


def test_the_markup_of_the_data_is_stripped_to_the_shown_words():
    marked = dataclasses.replace(
        DATA.mods["FireResist1"], text="+(6-11)% to [Resistances|Fire Resistance] and [Armour]"
    )

    assert mod_text(marked) == "+(6-11)% to Fire Resistance and Armour"


def test_rolled_values_replace_the_ranges_of_the_stats_that_roll():
    assert mod_text(DATA.mods["LightningResist1"], (8,)) == "+8% to Lightning Resistance"
    # the first stat of this mod is fixed (1-1), so the text writes it as a plain number
    assert mod_text(DATA.mods["AddedLightningDamage2"], (1, 15)) == "Adds 1 to 15 Lightning Damage to Attacks"
    assert mod_text(DATA.mods["AddedLightningDamage3"], (2, 23)) == "Adds 2 to 23 Lightning Damage to Attacks"


def test_a_value_the_text_shows_scaled_is_scaled_back_as_the_game_shows_it():
    assert mod_text(DATA.mods["ManaLeechPermyriadSuffix1"], (30,)) == "0.3% of Physical Attack Damage Leeched as Mana"
    assert mod_text(DATA.mods["LifeRegeneration1"], (90,)) == "Regenerate 1.5 Life per second"
    assert mod_text(DATA.mods["LifeRegeneration1"], (120,)) == "Regenerate 2 Life per second"


def test_values_that_do_not_fit_the_stats_of_the_mod_are_refused():
    with pytest.raises(ValueError, match="values"):
        mod_text(DATA.mods["LightningResist1"], (8, 9))


def test_a_mod_without_text_is_shown_by_its_name():
    veiled = dataclasses.replace(DATA.mods["FireResist1"], text=None, name="Veiled Prefix")

    assert mod_text(veiled) == "Veiled Prefix"


# --- the card of a concrete item ------------------------------------------------------------------------


def r12_start():
    return item(ExplicitMod("LightningResist2", (14,), fractured=True), base_id=AMULET)


def test_the_r12_start_amulet_is_a_rare_with_a_fractured_resistance_in_the_suffixes():
    card = card_of_item(DATA, r12_start())

    assert card == ItemCard(
        name="Paua Amulet",
        properties=("Rare", "item level 84"),
        implicits=(Slot(IMPLICIT_HELD, "implicit"),),
        enchantments=(),
        prefixes=(EMPTY, EMPTY, EMPTY),
        suffixes=(Slot("+14% to Lightning Resistance", "mod", ("fractured",)), EMPTY, EMPTY),
    )


def test_a_plain_item_shows_no_influence_and_no_corrupted_line():
    card = card_of_item(DATA, r12_start())

    assert not any("nfluence" in line or "orrupted" in line for line in card.properties)


def test_influence_and_corruption_are_shown_when_the_item_has_them():
    shaped = item(base_id=AMULET, influences=frozenset({Influence.SHAPER, Influence.ELDER}), corrupted=True)

    assert card_of_item(DATA, shaped).properties == ("Rare", "item level 84", "Elder", "Shaper", "corrupted")


def test_a_normal_item_shows_the_rare_capacity_as_empty():
    card = card_of_item(DATA, item(base_id=AMULET, rarity=Rarity.NORMAL))

    assert card.properties == ("Normal", "item level 84")
    assert card.prefixes == (EMPTY,) * 3 and card.suffixes == (EMPTY,) * 3


def test_rows_run_fractured_first_then_the_mods_then_the_crafted_ones_and_each_side_fills_to_capacity():
    mods = (
        roll("StrMasterItemGenerationCannotChangePrefixes", crafted=True),
        roll("FireResist1"),
        roll("IncreasedLife3"),
        ExplicitMod("ColdResist1", (7,), fractured=True),
    )

    card = card_of_item(DATA, item(*mods, base_id=AMULET))

    assert card.prefixes == (Slot("+40 to maximum Life", "mod"), EMPTY, EMPTY)
    assert card.suffixes == (
        Slot("+7% to Cold Resistance", "mod", ("fractured",)),
        Slot("+6% to Fire Resistance", "mod"),
        Slot("Prefixes Cannot Be Changed", "crafted", ("crafted",)),
    )


def test_a_mod_that_is_neither_fractured_nor_crafted_carries_no_mark():
    card = card_of_item(DATA, item(roll("FireResist1"), base_id=AMULET))

    assert card.suffixes[0] == Slot("+6% to Fire Resistance", "mod", ())


# --- the card of the target -----------------------------------------------------------------------------


def test_the_r12_goal_has_a_wanted_slot_per_requirement_on_its_side_and_the_rest_open():
    card = card_of_target(POOL, target_of(gem_leaf(), resist_leaf()))

    assert card == ItemCard(
        name="Paua Amulet",
        properties=("Rare", "item level 84"),
        implicits=(Slot(IMPLICIT, "implicit"),),
        enchantments=(),
        prefixes=(Slot(GEM_TEXT, "wanted", note="T1"), ANY_OR_EMPTY, ANY_OR_EMPTY),
        suffixes=(Slot(RESIST_TEXT, "wanted", note="any tier"), ANY_OR_EMPTY, ANY_OR_EMPTY),
    )


def test_a_minimum_tier_is_the_note_as_that_tier_or_better():
    card = card_of_target(POOL, target_of(resist_leaf(min_tier=2)))

    assert card.suffixes[0] == Slot(RESIST_TEXT, "wanted", note="T2 or better")


def test_a_leaf_with_one_possible_mod_keeps_the_exact_text_with_its_ranges_and_the_tier_of_the_mod():
    life = Requirement(None, "+(25-39) to maximum Life", frozenset({"IncreasedLife2"}))

    card = card_of_target(POOL, target_of(life))

    assert card.prefixes[0] == Slot("+(25-39) to maximum Life", "wanted", note="T1")


def test_a_k_of_n_group_is_said_once_with_its_members_under_it_and_no_note_of_the_group_on_a_member():
    group = KOfN(1, (gem_leaf(), resist_leaf()))

    card = card_of_target(POOL, target_of(group))

    assert card.groups == (Group("at least 1 of 2 of these:", (Slot(GEM_TEXT, "wanted", ("prefix",), "T1"), Slot(RESIST_TEXT, "wanted", ("suffix",), "any tier"))),)
    assert card.prefixes == (ANY_OR_EMPTY,) * 3 and card.suffixes == (ANY_OR_EMPTY,) * 3  # the members are not slots of a side
    assert not any("at least" in slot.note for slot in (*card.prefixes, *card.suffixes))


def test_a_requirement_beside_a_group_stays_a_slot_of_its_side():
    card = card_of_target(POOL, target_of(gem_leaf(), KOfN(1, (gem_leaf(), resist_leaf()))))

    assert card.prefixes[0] == Slot(GEM_TEXT, "wanted", note="T1")
    assert [group.heading for group in card.groups] == ["at least 1 of 2 of these:"]


def test_a_group_inside_a_group_is_refused_with_a_clear_error_not_drawn_with_a_lost_link():
    nested = KOfN(1, (gem_leaf(), KOfN(1, (resist_leaf(), resist_leaf(min_tier=2)))))

    with pytest.raises(ValueError, match="inside another k-of-n group"):
        card_of_target(POOL, target_of(nested))


def test_the_page_prints_a_group_once_as_a_heading_with_its_members_under_it():
    html = _item(card_of_target(POOL, target_of(KOfN(1, (gem_leaf(), resist_leaf())))), target=True)

    assert html.count("at least 1 of 2") == 1
    heading = '<div class="gh">at least 1 of 2 of these:</div>'
    assert html.index(heading) < html.index(GEM_TEXT) < html.index(RESIST_TEXT)  # the members follow their heading, each in the one mod format
    assert f'<div class="s w">{GEM_TEXT}<span class="n"> · T1</span><span class="b">prefix</span></div>' in html
    assert f'<span class="b">suffix</span>' in html  # each member says its side in words
    assert 'class="sd">at least' not in html  # the heading has a style of its own, it is not a third list beside Prefixes and Suffixes


def test_the_influences_of_the_target_are_properties():
    card = card_of_target(POOL, target_of(gem_leaf(), influences=frozenset({Influence.SHAPER})))

    assert card.properties == ("Rare", "item level 84", "Shaper")


def test_a_leaf_that_only_a_crafted_mod_can_give_is_still_shown_by_its_text():
    meta = Requirement(None, "Prefixes Cannot Be Changed", frozenset({"StrMasterItemGenerationCannotChangePrefixes"}))

    card = card_of_target(DATA, target_of(meta))

    assert card.suffixes[0] == Slot("Prefixes Cannot Be Changed", "wanted", note="crafted")


# --- the card of the state after a step: a reroll-only abstraction (the junk is not kept) ----------------


def reroll_card(goal, *mods, metamods: bool = False, **fields) -> ItemCard:
    ab = small_abstraction(goal, metamods=metamods)
    return card_of_states(ab, [ab.compress(small_item(*mods, **fields))])


def test_a_state_after_a_reroll_shows_the_fractured_row_the_wanted_row_and_any_mod_or_empty_for_the_rest():
    fractured = small_roll("LightningResist2", fractured=True)

    card = reroll_card("r12", fractured, small_roll(GEM))

    assert card.name == "Paua Amulet" and card.properties == ("Rare", "item level 84")
    assert card.prefixes == (Slot(GEM_TEXT, "wanted", note="T1"), ANY_OR_EMPTY, ANY_OR_EMPTY)
    assert card.suffixes == (
        Slot(RESIST_TEXT, "wanted", ("fractured",), "any tier"),
        ANY_OR_EMPTY,
        ANY_OR_EMPTY,
    )


def test_a_leaf_the_state_does_not_meet_has_no_wanted_row():
    card = reroll_card("r12", small_roll("LightningResist2", fractured=True))

    assert card.prefixes == (ANY_OR_EMPTY,) * 3


def test_a_fractured_mod_that_no_leaf_wants_is_a_plain_row_with_its_exact_text():
    card = reroll_card("r12", small_roll("FireResist1", fractured=True))

    assert card.suffixes == (Slot("+(6-11)% to Fire Resistance", "mod", ("fractured",), "T1"), ANY_OR_EMPTY, ANY_OR_EMPTY)


def test_a_fractured_mod_that_stands_for_several_tiers_says_so_even_when_no_leaf_wants_it():
    card = reroll_card("roll_not_asked", small_roll("LightningResist1", fractured=True))

    assert card.suffixes[0] == Slot(RESIST_TEXT, "wanted", ("fractured",), "any tier")


def test_a_leaf_met_below_its_tier_is_the_wanted_text_with_a_note():
    card = reroll_card("tier", small_roll("ColdResist1", fractured=True), small_roll(RESIST_1), small_roll(GEM))

    assert card.suffixes == (
        Slot("+(6-11)% to Cold Resistance", "mod", ("fractured",), "T1"),
        Slot(RESIST_TEXT, "wanted", note="tier too low"),
        ANY_OR_EMPTY,
    )


def stub_reader(*mods) -> _StateReader:
    """A reader over made-up mods (fixed values, no ranges): `(id, text, tier or None, essence_only)` each, one family."""
    made = {
        mod_id: SimpleNamespace(
            id=mod_id, text=text, name=mod_id, families=("Speed",), generation_type="prefix", domain="item",
            is_essence_only=essence, spawn_weights=(),
        )
        for mod_id, text, _, essence in mods
    }  # fmt: skip
    reader = object.__new__(_StateReader)
    reader.data = SimpleNamespace(mods=made)
    reader.tiers = {mod_id: tier for mod_id, _, tier, _ in mods if tier is not None}
    reader.ab = SimpleNamespace(_drawn_contribution=lambda other: ())
    reader._fractured, reader._families = {}, {}
    reader._held = ()  # no start item: a fractured entry is drawn as the tiers it stands for
    reader._forced = {}  # no essence of a route
    return reader


FAST = ("Fast1", "35% increased Speed", 1, False), ("Fast2", "30% increased Speed", 2, False)
ESSENCE_FAST = ("FastEssence", "5% increased Speed for each nearby Enemy", None, True)


def test_a_fractured_mod_that_stands_for_tiers_with_other_fixed_values_reads_all_of_them():
    side, slot = stub_reader(*FAST).fractured("Fast2", ())

    assert side is Side.PREFIX
    assert slot == Slot("35% increased Speed or 30% increased Speed", "mod", ("fractured",), "any tier")


def test_a_fractured_mod_the_state_names_by_an_essence_only_tier_reads_as_the_tiers_of_its_class():
    reader = stub_reader(*FAST, ESSENCE_FAST)

    _, slot = reader.fractured("FastEssence", ())

    assert slot == Slot("35% increased Speed or 30% increased Speed", "mod", ("fractured",), "any tier")  # no "essence only"


def test_a_slot_of_a_family_told_apart_reads_the_texts_of_its_tiers():
    row = stub_reader(*FAST).family(SimpleNamespace(side=Side.PREFIX, kind="Speed"))

    assert row == Slot("35% increased Speed or 30% increased Speed", "mod", (), "any tier")


def test_a_fractured_mod_of_a_class_of_one_tier_keeps_its_text_and_the_state_named_mod_when_it_is_not_in_the_class():
    reader = stub_reader(FAST[0], ESSENCE_FAST)

    _, slot = reader.fractured("FastEssence", ())

    assert slot == Slot("35% increased Speed", "mod", ("fractured",), "T1")


def test_a_leaf_meets_only_mods_that_can_appear_at_the_item_level():
    tiers = tier_table(DATA, BELT)
    life = {"IncreasedLife1", "IncreasedLife2", "IncreasedLife3"}  # tiers 3, 2, 1 (item levels 5, 11, 18)

    tier_2 = accepted_by_tier(DATA, BELT, 12, frozenset(life), 2)
    assert _leaf_slot(DATA, BELT, tiers, life, 2, 12, tier_2) == (Side.PREFIX, "+(25-39) to maximum Life", "T2")  # tier 1 needs 18
    assert _leaf_slot(DATA, BELT, tiers, life, 2, 18, tier_2)[2] == "T2 or better"
    assert _leaf_slot(DATA, BELT, tiers, life, None, 12)[2] == "any tier"  # no tier asked


def test_a_leaf_only_a_crafted_mod_meets_says_crafted():
    tiers = tier_table(DATA, BELT)

    side, text, note = _leaf_slot(DATA, BELT, tiers, {PREFIXES_LOCK}, None, BELT_LEVEL)

    assert (side, note) == (Side.SUFFIX, "crafted") and text == mod_text(DATA.mods[PREFIXES_LOCK])


def test_a_leaf_only_an_essence_mod_meets_says_the_essence_that_forces_it():
    tiers = tier_table(DATA, BELT)
    mod_id = "ElementalPenetrationDuringFlaskEffectEssence1"

    _, text, note = _leaf_slot(DATA, BELT, tiers, {mod_id}, None, BELT_LEVEL)

    # a corruption-only essence has no tier word, so it is said by its name (#895)
    assert note == "Essence of Hysteria" and text == mod_text(DATA.mods[mod_id])
    assert essence_tier(DATA, BELT, mod_id) == "Essence of Hysteria" and essence_tier(DATA, BELT, LIFE) == ""


def test_an_essence_only_mod_no_essence_of_the_class_gives_says_essence_only():
    tiers = tier_table(DATA, AMULET)
    mod_id = "ElementalPenetrationDuringFlaskEffectEssence1"  # the belt's mod of the Essence of Hysteria; an amulet gets another

    assert essence_tier(DATA, AMULET, mod_id) == ""
    assert _leaf_slot(DATA, AMULET, tiers, {mod_id}, None, 84)[2] == "essence only"


def test_a_fractured_entry_of_the_class_of_the_start_items_fractured_mod_is_drawn_as_that_mod():
    reader = stub_reader(*FAST)
    reader._held = (reader.data.mods["Fast2"],)  # the route starts from an item with "30% increased Speed" fractured

    side, slot = reader.fractured("Fast1", ())  # the state names the class by its canonical id

    assert side is Side.PREFIX and slot == Slot("30% increased Speed", "mod", ("fractured",), "T2")


def test_the_card_of_a_bought_item_can_show_the_range_of_the_tier_and_any_mod_for_what_it_does_not_know():
    bought = belt(roll(FIRE, fractured=True), roll(LIFE_3))

    card = card_of_item(DATA, bought, tiers=True, rolled=False, filler=ANY_OR_EMPTY)

    assert card.suffixes == (Slot("+(6-11)% to Fire Resistance", "mod", ("fractured",), "T1"), ANY_OR_EMPTY, ANY_OR_EMPTY)
    assert card.prefixes[0] == Slot("+(40-54) to maximum Life", "mod", (), "T1")
    assert card.prefixes[1:] == (ANY_OR_EMPTY, ANY_OR_EMPTY)


def test_a_crafted_slot_is_a_crafted_row_after_the_fractured_and_wanted_ones():
    card = reroll_card("r12", small_roll("FireResist1", fractured=True), small_roll(CRAFTED, crafted=True), metamods=True)

    assert card.prefixes == (Slot("Suffixes Cannot Be Changed", "crafted", ("crafted",)), EMPTY, EMPTY)  # metamods keep the junk: nothing else is held


def test_a_normal_item_of_a_reroll_abstraction_is_all_empty():
    card = reroll_card("r12", rarity=Rarity.NORMAL)

    assert card.properties == ("Normal", "item level 84")
    assert card.prefixes == (EMPTY,) * 3 and card.suffixes == (EMPTY,) * 3


def test_the_item_level_of_a_state_is_the_one_of_the_abstraction():
    ab = small_abstraction("r12", level=90)

    card = card_of_states(ab, [ab.compress(small_item(level=90))])

    assert card.properties == ("Rare", "item level 90")


# --- the card of the state after a step: junk tracked ---------------------------------------------------


def belt_card(*mods, metamods: bool = False, **fields) -> ItemCard:
    ab = belt_abstraction(metamods=metamods)
    return card_of_states(ab, [ab.compress(belt(*mods, **fields))])


def test_an_abstraction_that_reads_the_junk_tracks_it_and_a_reroll_only_one_does_not():
    assert tracks_junk(belt_abstraction()) and not tracks_junk(small_abstraction("r12"))


@pytest.mark.parametrize(
    ("junk", "expected"),
    [
        pytest.param((), (EMPTY, EMPTY, EMPTY), id="none"),
        pytest.param((REGEN,), (ANY_MOD, EMPTY, EMPTY), id="one"),
        pytest.param((REGEN, FIRE), (ANY_MOD, ANY_MOD, EMPTY), id="two"),
        pytest.param((REGEN, FIRE, CHAOS_RES), (ANY_MOD, ANY_MOD, ANY_MOD), id="three"),
    ],
)
def test_the_junk_of_a_tracked_state_is_any_mod_per_slot_and_empty_for_the_rest(junk, expected):
    card = belt_card(*(roll(mod_id) for mod_id in junk))

    assert card.suffixes == expected
    assert card.prefixes == (EMPTY, EMPTY, EMPTY)


def test_a_wanted_slot_of_a_tracked_state_is_drawn_by_its_leaf_and_is_not_junk():
    card = belt_card(roll(FIRE, fractured=True), roll(LIFE_3))

    assert card.prefixes == (Slot("+# to maximum Life", "wanted", note="any tier"), EMPTY, EMPTY)
    assert card.suffixes == (Slot("+(6-11)% to Fire Resistance", "mod", ("fractured",), "T1"), EMPTY, EMPTY)


def test_a_metamod_of_a_tracked_state_is_a_crafted_row():
    card = belt_card(roll(FIRE, fractured=True), roll(PREFIXES_LOCK, crafted=True), metamods=True)

    assert card.suffixes == (
        Slot("+(6-11)% to Fire Resistance", "mod", ("fractured",), "T1"),
        Slot("Prefixes Cannot Be Changed", "crafted", ("crafted",)),
        EMPTY,
    )


def test_a_family_told_apart_is_a_mod_of_that_family_not_junk():
    card = belt_card(roll(FIRE, fractured=True), roll(SHIELD))

    assert card.prefixes == (Slot("+(1-3) to maximum Energy Shield", "mod", note="T1"), EMPTY, EMPTY)


def test_a_slot_below_its_tier_in_a_tracked_state_is_the_wanted_text_with_a_note():
    ab = Abstraction(DATA, Goal((Wanted(frozenset({LIFE, "IncreasedLife2", LIFE_3}), min_tier=1),)), BELT, BELT_LEVEL, CRAFTS)

    card = card_of_states(ab, [ab.compress(belt(ExplicitMod(LIFE, (10,))))])

    assert card.prefixes == (Slot("+# to maximum Life", "wanted", note="tier too low"), EMPTY, EMPTY)


# --- the join of several states -------------------------------------------------------------------------


def belt_join(*items) -> ItemCard:
    ab = belt_abstraction()
    return card_of_states(ab, [ab.compress(entry) for entry in items])


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        pytest.param((1, 2), (ANY_MOD, ANY_OR_EMPTY, EMPTY), id="one_and_two"),
        pytest.param((0, 2), (ANY_OR_EMPTY, ANY_OR_EMPTY, EMPTY), id="none_and_two"),
        pytest.param((1, 3), (ANY_MOD, ANY_OR_EMPTY, ANY_OR_EMPTY), id="one_and_three"),
        pytest.param((2, 2), (ANY_MOD, ANY_MOD, EMPTY), id="same"),
    ],
)
def test_a_join_of_states_with_different_junk_counts_is_any_mod_then_any_mod_or_empty_then_empty(counts, expected):
    junk = (REGEN, FIRE, CHAOS_RES)

    card = belt_join(*(belt(*(roll(mod_id) for mod_id in junk[:count])) for count in counts))

    assert card.suffixes == expected


def test_a_row_only_some_states_have_carries_the_note_in_some_and_a_shared_row_stays_plain():
    fractured = roll(FIRE, fractured=True)

    card = belt_join(belt(fractured), belt(fractured, roll(LIFE_3)))

    assert card.suffixes == (Slot("+(6-11)% to Fire Resistance", "mod", ("fractured",), "T1"), EMPTY, EMPTY)
    assert card.prefixes == (Slot("+# to maximum Life", "wanted", note="any tier, in some"), EMPTY, EMPTY)


def test_properties_that_differ_between_the_joined_states_say_so():
    ab = small_abstraction("r12")
    states = [
        ab.compress(small_item(rarity=Rarity.NORMAL)),
        ab.compress(small_item(small_roll("FireResist1"), rarity=Rarity.MAGIC)),
        ab.compress(small_item(influences=frozenset({Influence.SHAPER, Influence.ELDER}), corrupted=True)),
        ab.compress(small_item(influences=frozenset({Influence.SHAPER}))),
    ]

    card = card_of_states(ab, states)

    assert card.properties == ("Normal or Magic or Rare", "item level 84", "Elder (some)", "Shaper (some)", "corrupted (some)")


def test_properties_every_joined_state_has_are_plain():
    ab = small_abstraction("r12")
    states = [ab.compress(small_item(influences=frozenset({Influence.SHAPER}), corrupted=True)) for _ in range(2)]
    states.append(ab.compress(small_item(small_roll("FireResist1", fractured=True), influences=frozenset({Influence.SHAPER}), corrupted=True)))

    card = card_of_states(ab, states)

    assert card.properties == ("Rare", "item level 84", "Shaper", "corrupted")


def test_a_join_needs_at_least_one_state():
    with pytest.raises(ValueError, match="state"):
        card_of_states(small_abstraction("r12"), [])


# --- the real 3.29.3.3 dump: the R12 cards --------------------------------------------------------------


@pytest.fixture(scope="module")
def r12():
    data = real_game_data()
    target = load_target(EXAMPLES / "r12-lightning-amulet.yaml", data)
    return data, target, Abstraction(data, Goal.from_target(target), target.base_id, target.item_level)


def test_the_real_r12_start_card_is_the_fractured_resistance_with_its_rolled_value(r12):
    data, target, _ = r12

    card = card_of_item(data, target.start_item)

    assert card.name == "Paua Amulet" and card.properties == ("Rare", "item level 84")
    assert card.implicits == (Slot(IMPLICIT_HELD, "implicit"),) and card.enchantments == ()
    assert card.prefixes == (EMPTY, EMPTY, EMPTY)
    assert card.suffixes == (Slot("+14% to Lightning Resistance", "mod", ("fractured",)), EMPTY, EMPTY)


def test_the_real_r12_goal_card_wants_the_gem_level_and_the_fractured_lightning_resistance_of_the_start_item(r12):
    data, target, _ = r12

    card = card_of_target(data, target)

    assert card.prefixes == (Slot(GEM_TEXT, "wanted", note="T1"), ANY_OR_EMPTY, ANY_OR_EMPTY)
    # the leaf takes any tier, and the start amulet's fractured mod meets it: the finished item holds exactly that mod (#895)
    assert card.suffixes == (Slot("+(12-17)% to Lightning Resistance", "wanted", ("fractured",), "T7"), ANY_OR_EMPTY, ANY_OR_EMPTY)
    # a route that starts from another item (no fractured mod) shows the leaf as the target file says it
    plain = dataclasses.replace(target.start_item, mods=())
    assert card_of_target(data, target, plain).suffixes[0] == Slot(RESIST_TEXT, "wanted", note="any tier")


def test_the_real_r12_cards_after_a_step_show_the_start_items_fractured_mod_with_its_tier(r12):
    data, target, ab = r12
    start = ab.compress(target.start_item)

    with_start = card_of_states(ab, [start], _StateReader(ab, target.start_item))
    without = card_of_states(ab, [start])

    assert with_start.suffixes[0] == Slot("+(12-17)% to Lightning Resistance", "wanted", ("fractured",), "T7")
    assert without.suffixes[0] == Slot(RESIST_TEXT, "wanted", ("fractured",), "any tier")  # the state alone stands for every tier


# --- the real 3.29.3.3 dump: the fractures and the essence tiers of R05, R10, R11 (#895) ---------------


def real_card(name: str, essences: tuple[str, ...] = ()):
    """The goal card of a real target as the page of a route that uses `essences` draws it."""
    data = real_game_data()
    target = load_target(EXAMPLES / name, data)
    return data, target, card_of_target(data, target, forced=essence_notes(data, target.base_id, essences))


SPITE, ZEAL = "Shrieking Essence of Spite", "Shrieking Essence of Zeal"


def test_the_real_r10_goal_card_marks_the_fractured_movement_speed_and_says_the_essence_of_the_intelligence():
    data, target, card = real_card("r10-fractured-boots.yaml", (SPITE,))

    assert card.prefixes[0] == Slot("30% increased Movement Speed", "wanted", ("fractured",), "T2")
    assert card.prefixes[1] == Slot("+# to maximum Life", "wanted", note="T2 or better")  # tier 1 or tier 2, the owner's target
    # the route's essence forces this mod: the line says the essence's tier, not the tier 2 the mod also is on the natural ladder
    assert card.suffixes[0] == Slot("+(43-50) to Intelligence", "wanted", note="Shrieking essence")
    assert card.suffixes[1] == Slot("(16-20)% chance to Avoid Elemental Ailments", "wanted", note="crafted")


def test_where_a_mod_comes_from_is_read_from_the_route_not_from_the_target_line():
    data, target, _ = real_card("r10-fractured-boots.yaml")
    base = target.base_id
    assert essence_notes(data, base, (SPITE, "Chaos Orb", "no such essence")) == {"Intelligence8": "Shrieking essence"}
    assert essence_notes(data, base, (ZEAL,)) == {"MovementVelocity5": "Shrieking essence"}  # an essence does force the 30% Movement Speed on boots

    # no route, or a route with no essence: the Intelligence is the natural mod it also is
    assert card_of_target(data, target).suffixes[0] == Slot("+(43-50) to Intelligence", "wanted", note="T2")
    # a route that starts from boots holding the Movement Speed unfractured (the vendor recipe's, #895 review) and uses the Essence of Spite:
    # no essence of the route gives the Movement Speed, so its line is not an essence's, and nothing marks it fractured
    recipe_start = dataclasses.replace(target.start_item, mods=(ExplicitMod("MovementVelocity5", (30,)),))
    card = card_of_target(data, target, recipe_start, essence_notes(data, base, (SPITE,)))
    assert card.prefixes[0] == Slot("30% increased Movement Speed", "wanted", note="T2")
    assert card.suffixes[0] == Slot("+(43-50) to Intelligence", "wanted", note="Shrieking essence")
    # a start item whose fractured mod only an essence gives has no tier of the ladder: the line says its essence
    reservation = ExplicitMod("ManaReservationEfficiencyEssence6_", (7,), fractured=True)
    helmet = load_target(EXAMPLES / "r11-reservation-helmet.yaml", data)
    held = card_of_target(data, helmet, dataclasses.replace(helmet.start_item, mods=(*helmet.start_item.mods, reservation)))
    (member,) = [slot for group in held.groups for slot in group.members if "fractured" in slot.marks]
    assert (member.note, member.marks) == ("Shrieking essence", ("suffix", "fractured"))


def test_the_tier_line_of_a_family_is_left_out_only_for_the_action_that_forces_its_mod():
    """OR-31 and #895: the essence adds its Intelligence every time, so that step shows no chances for it; a Chaos Orb draws it by tier and shows them."""
    data, target, _ = real_card("r10-fractured-boots.yaml")
    ab = Abstraction(data, Goal.from_target(target), target.base_id, target.item_level)
    start = ab.compress(target.start_item)

    essence = {line.text for line in tier_lines(ab, ApplyEssence(SPITE), [start], [1.0])}
    chaos = {line.text: line for line in tier_lines(ab, ChaosOrb(), [start], [1.0])}

    assert essence == {"+# to maximum Life"}
    assert set(chaos) == {"+# to maximum Life", "+# to Intelligence"}
    assert [share.tier for share in chaos["+# to Intelligence"].tiers if share.wanted] == [2]  # the mod the target names


def test_the_real_r05_goal_card_is_tier_1_life_the_fractured_attributes_and_the_deafening_strength():
    _, _, card = real_card("r05-strength-ring.yaml")

    assert card.groups == ()  # no "at least 1 of 4": the Life is asked itself
    assert card.prefixes == (Slot("+(100-114) to maximum Life", "wanted", note="T1"), ANY_OR_EMPTY, ANY_OR_EMPTY)
    assert card.suffixes == (
        Slot("+(13-16) to all Attributes", "wanted", ("fractured",), "T1"),
        Slot("+(51-58) to Strength", "wanted", note="Deafening essence"),
        ANY_OR_EMPTY,
    )


def test_the_real_r11_goal_card_marks_the_fractured_chaos_resistance_and_names_each_essence_of_the_group():
    _, _, card = real_card("r11-reservation-helmet.yaml")

    assert card.prefixes == (
        Slot("#% increased Evasion Rating", "wanted", note="T3 or better"),
        Slot("+(130-144) to maximum Life", "wanted", note="T1"),
        ANY_OR_EMPTY,
    )
    # the leaf takes any tier; the bought helmet's fractured mod is tier 1 and stays on the item
    assert card.suffixes == (Slot("+(31-35)% to Chaos Resistance", "wanted", ("fractured",), "T1"), ANY_OR_EMPTY, ANY_OR_EMPTY)
    reservation = "% increased Mana Reservation Efficiency of Skills"
    assert card.groups == (
        Group(
            "at least 1 of 2 of these:",
            (
                Slot(f"(7-8){reservation}", "wanted", ("suffix",), "Shrieking essence"),
                Slot(f"(9-10){reservation}", "wanted", ("suffix",), "Deafening essence"),
            ),
        ),
    )


def test_the_real_r12_states_are_the_start_and_the_goal_and_neither_shows_markup(r12):
    data, target, ab = r12
    start = ab.compress(target.start_item)
    goal = next(state for state in ab.reachable([start], [CHAOS, REFORGE]) if ab.is_goal(state))

    cards = [card_of_states(ab, [state]) for state in (start, goal)]

    assert cards[0].prefixes == (ANY_OR_EMPTY,) * 3
    assert cards[1].prefixes == (Slot(GEM_TEXT, "wanted", note="T1"), ANY_OR_EMPTY, ANY_OR_EMPTY)
    for card in cards:
        assert card.suffixes[0].marks == ("fractured",) and card.suffixes[0].text.endswith("to Lightning Resistance")
        assert not any("[" in slot.text or "|" in slot.text for slot in (*card.prefixes, *card.suffixes))
