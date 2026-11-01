"""The item cards show implicits, quality, the veiled placeholder and the unveil offer (ticket #143, piece B; ADR-0027).

The cards come from the hand-made belt of `implicits_support` with the real stat texts of
`targets_implicits_support`; nothing here needs the real game data.
"""

import dataclasses

from abstraction_pool import AMULET, SMALL, small_item
from abstraction_support import GOALS
from implicits_support import BELT, BOOTS, placeholder
from items_support import DATA
from targets_implicits_support import TEXTED

from crafting_system.abstraction import Abstraction
from crafting_system.cli._route_card import ItemCard, Slot, card_of_item, card_of_states, card_of_target, mod_text
from crafting_system.cli._route_html import _item
from crafting_system.items import CatalystType, ImplicitMod, Influence, Item, Quality, Rarity
from crafting_system.targets import ImplicitRequirement, QualityRequirement, Target

STRENGTH = "StrengthImplicitBelt1"
STRENGTH_RANGE = "+(25-35) to Strength"
SHOCK = "(36-38)% chance to Avoid being Shocked"
EMPTY = Slot("empty", "empty")
ANY_OR_EMPTY = Slot("any mod or empty", "any")
OFFER = ("UnveiledPrefixLife1", "UnveiledPrefixMana1")
PRISMATIC_12 = Quality(CatalystType.PRISMATIC, 12)
IMPLICIT_ID = "ManaRegenerationImplicitAmulet1"
POOL = dataclasses.replace(SMALL, mods={**SMALL.mods, IMPLICIT_ID: DATA.mods[IMPLICIT_ID]})  # SMALL plus the base's implicit


def build(*mods, base_id: str = BELT, **fields) -> Item:
    return Item.build(TEXTED, base_id=base_id, item_level=84, rarity=Rarity.RARE, mods=mods, **fields)


def plain_card(item: Item, **options) -> ItemCard:
    return card_of_item(TEXTED, item, **options)


def target_of(**fields) -> Target:
    return Target(BELT, 84, frozenset(), (), build(), **fields)


# --- an item with nothing new reads as it did -------------------------------------------------------------


def test_an_item_without_implicits_quality_or_offer_has_the_card_it_had_before():
    card = plain_card(build())

    assert card == ItemCard(
        name="Heavy Belt",
        properties=("Rare", "item level 84"),
        implicits=(Slot(STRENGTH_RANGE, "implicit"),),
        enchantments=(),
        prefixes=(EMPTY, EMPTY, EMPTY),
        suffixes=(EMPTY, EMPTY, EMPTY),
    )
    assert card.offer == ()


def test_the_html_of_such_a_card_has_the_plain_implicit_line_and_no_offer_block():
    html = _item(plain_card(build()))

    assert f'<div class="sd">Implicit</div><div class="s i">{STRENGTH_RANGE}</div><div class="sd">Prefixes</div>' in html
    assert "Unveil offer" not in html and "catalyst" not in html


# --- implicits --------------------------------------------------------------------------------------------


def test_an_eldritch_implicit_has_its_value_filled_in_its_grade_and_its_side():
    item = build(implicits=(ImplicitMod("AvoidShockEldritchImplicit2", 2, (37,)),))

    card = plain_card(item)

    assert card.implicits == (
        Slot(STRENGTH_RANGE, "implicit"),
        Slot("37% chance to Avoid being Shocked", "implicit", ("searing exarch",), "grade 2 (Greater)"),
    )


def test_an_eater_of_worlds_implicit_names_its_side():
    item = build(implicits=(ImplicitMod("ChanceToShockEldritchImplicit2", 2, (10,)),))

    (_, eldritch) = plain_card(item).implicits

    assert eldritch == Slot("10% chance to Shock", "implicit", ("eater of worlds",), "grade 2 (Greater)")


def test_a_stored_base_implicit_shows_its_rolled_value_once_and_has_no_note_or_mark():
    item = build(implicits=(ImplicitMod(STRENGTH, 0, (30,)),))

    assert plain_card(item).implicits == (Slot("+30 to Strength", "implicit"),)


def test_a_stored_base_implicit_beside_an_eldritch_one_does_not_repeat_the_base_implicit():
    item = build(implicits=(ImplicitMod(STRENGTH, 0, (30,)), ImplicitMod("AvoidShockEldritchImplicit1", 1, (34,))))

    implicits = plain_card(item).implicits

    assert [slot.text for slot in implicits] == ["+30 to Strength", "34% chance to Avoid being Shocked"]
    assert implicits[1].note == "grade 1 (Lesser)"


def test_a_card_that_is_not_rolled_shows_the_range_of_a_stored_implicit_with_its_grade():
    item = build(implicits=(ImplicitMod("AvoidShockEldritchImplicit2", 2, (37,)),))

    (_, eldritch) = plain_card(item, rolled=False).implicits

    assert eldritch.text == SHOCK and eldritch.note == "grade 2 (Greater)"


def test_the_html_of_an_eldritch_implicit_has_the_note_and_the_side_badge_in_the_implicit_block():
    item = build(implicits=(ImplicitMod("AvoidShockEldritchImplicit2", 2, (37,)),))

    html = _item(plain_card(item))

    assert (
        '<div class="s i">37% chance to Avoid being Shocked<span class="n"> · grade 2 (Greater)</span>'
        '<span class="b">searing exarch</span></div>'
    ) in html
    assert html.index("Implicit") < html.index("37%") < html.index("Prefixes")


# --- quality ----------------------------------------------------------------------------------------------


def test_quality_is_a_property_pill_after_the_influences_and_before_corrupted():
    item = build(quality=PRISMATIC_12, influences=frozenset({Influence.SHAPER}), corrupted=True)

    assert plain_card(item).properties == ("Rare", "item level 84", "Shaper", "Prismatic catalyst quality 12%", "corrupted")


def test_an_item_without_quality_has_no_quality_pill():
    assert not any("quality" in line for line in plain_card(build()).properties)
    assert not any("quality" in line for line in plain_card(build(base_id=BOOTS)).properties)


def test_the_html_of_quality_is_one_more_pill():
    html = _item(plain_card(build(quality=Quality(CatalystType.NOXIOUS, 3))))

    assert '<span class="pl">item level 84</span><span class="pl">Noxious catalyst quality 3%</span>' in html


# --- the veiled placeholder and its offer -----------------------------------------------------------------


def test_a_veiled_placeholder_reads_veiled_prefix_with_the_veiled_mark_not_its_id():
    card = plain_card(build(placeholder()), tiers=True)

    assert card.prefixes[0] == Slot("veiled prefix", "mod", ("veiled",))
    assert "VeiledPrefix" not in str(card)


def test_a_suffix_placeholder_reads_veiled_suffix():
    card = plain_card(build(placeholder("VeiledSuffix")), tiers=True)

    assert card.suffixes[0] == Slot("veiled suffix", "mod", ("veiled",))


def test_the_offer_is_one_slot_per_offered_mod_with_its_tier():
    card = plain_card(build(placeholder(), veil_offer=OFFER), tiers=True)

    assert card.offer == (Slot("x", "mod", (), "T1"), Slot("x", "mod", (), "T1"))  # the hand-made records have the text x


def test_the_offer_has_no_tier_note_when_the_card_does_not_ask_for_tiers():
    card = plain_card(build(placeholder(), veil_offer=OFFER))

    assert [slot.note for slot in card.offer] == ["", ""]


def test_an_offered_mod_keeps_the_range_of_its_stat_in_the_game_text():
    life = TEXTED.mods["UnveiledPrefixLife1"]
    texted = dataclasses.replace(
        TEXTED, mods={**TEXTED.mods, life.id: dataclasses.replace(life, text="+(30-40) to maximum Life")}
    )

    card = card_of_item(texted, build(placeholder(), veil_offer=(life.id,)), tiers=True)

    assert card.offer == (Slot(mod_text(texted.mods[life.id]), "mod", (), "T1"),)
    assert card.offer[0].text == "+(30-40) to maximum Life"


def test_an_item_with_a_placeholder_but_no_offer_has_no_offer_block():
    item = build(placeholder())

    assert plain_card(item, tiers=True).offer == ()
    assert "Unveil offer" not in _item(plain_card(item, tiers=True))


def test_the_html_of_an_offer_is_a_heading_and_its_slots_after_the_suffixes():
    html = _item(plain_card(build(placeholder(), veil_offer=OFFER), tiers=True))

    assert html.index("Suffixes") < html.index('<div class="sd">Unveil offer</div>')
    assert html.count('<div class="s m">') == 1 + 2  # the placeholder and the two offered mods
    assert html.index("Unveil offer") > html.rindex("empty")


# --- the target -------------------------------------------------------------------------------------------


def test_an_implicit_requirement_is_a_wanted_implicit_with_hashes_the_grade_and_the_rolls():
    wish = ImplicitRequirement(
        None,
        SHOCK,
        frozenset({"AvoidShockEldritchImplicit1", "AvoidShockEldritchImplicit2", "AvoidShockEldritchImplicit3"}),
        min_grade=2,
        min_roll=(38,),
    )

    card = card_of_target(TEXTED, target_of(implicits=(wish,)))

    assert card.implicits == (
        Slot(STRENGTH_RANGE, "implicit"),
        Slot("#% chance to Avoid being Shocked", "wanted", (), "grade 2 or better, roll 38 or more"),
    )


def test_an_implicit_requirement_with_neither_grade_nor_roll_has_no_note():
    wish = ImplicitRequirement("Strength", None, frozenset({STRENGTH}))

    (_, wanted) = card_of_target(TEXTED, target_of(implicits=(wish,))).implicits

    assert wanted == Slot("+# to Strength", "wanted")


def test_a_roll_requirement_skips_the_stats_that_have_none():
    wish = ImplicitRequirement(None, "x", frozenset({"AvoidShockEldritchImplicitUniquePresence4"}), min_roll=(None, 1))

    (_, wanted) = card_of_target(TEXTED, target_of(implicits=(wish,))).implicits

    assert wanted.note == "roll 1 or more"


def test_a_quality_requirement_is_a_property_pill_that_says_or_more():
    card = card_of_target(TEXTED, target_of(quality=QualityRequirement(CatalystType.PRISMATIC, 12)))

    assert card.properties == ("Rare", "item level 84", "Prismatic catalyst quality 12% or more")


def test_a_target_with_neither_has_the_card_it_had_before():
    card = card_of_target(TEXTED, target_of())

    assert card.properties == ("Rare", "item level 84")
    assert card.implicits == (Slot(STRENGTH_RANGE, "implicit"),) and card.offer == ()
    assert card.prefixes == (ANY_OR_EMPTY,) * 3 and card.suffixes == (ANY_OR_EMPTY,) * 3


def test_the_html_of_a_wanted_implicit_is_a_wanted_line_in_the_implicit_block():
    wish = ImplicitRequirement(None, SHOCK, frozenset({"AvoidShockEldritchImplicit1"}), min_grade=1)

    html = _item(card_of_target(TEXTED, target_of(implicits=(wish,))), target=True)

    assert '<div class="s w">#% chance to Avoid being Shocked<span class="n"> · grade 1 or better</span></div>' in html


# --- escaping ---------------------------------------------------------------------------------------------


def test_every_text_of_an_implicit_and_an_offer_slot_is_escaped():
    card = ItemCard(
        "Belt",
        ("Rare",),
        (Slot("<b>&", "implicit", ("x<",), "n&"),),
        (),
        (),
        (),
        (Slot("<i>", "mod", (), "T<1"),),
    )

    html = _item(card)

    assert "<b>" not in html and "<i>" not in html
    assert "&lt;b&gt;&amp;" in html and "n&amp;" in html and "x&lt;" in html and "&lt;i&gt;" in html and "T&lt;1" in html


# --- the card after a step --------------------------------------------------------------------------------


def test_the_card_of_a_state_still_shows_the_base_implicits_as_ranges_and_no_offer():
    ab = Abstraction(POOL, GOALS["r12"], AMULET, 84)

    card = card_of_states(ab, [ab.compress(small_item())])

    assert card.implicits == (Slot("(20-30)% increased Mana Regeneration Rate", "implicit"),)
    assert card.offer == () and card.properties == ("Rare", "item level 84")
