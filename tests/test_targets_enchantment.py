"""The `enchantment:` target and the start item's `enchantment:` (ticket #236, ADR-0050, ADR-0053)."""

import textwrap

import pytest
from cli_support import price_file
from enchant_support import (
    ARMOUR_EXTRA_SLOT,
    ARMOUR_LINKED,
    ARMOUR_REQUIREMENTS,
    BODY,
    CLEAN_LIFE,
    DATA,
    EXTRA_SLOT_TEXT,
    LIFE,
    LIFE_ATTRIBUTE,
    LIFE_ATTRIBUTE_TEXT,
    LIFE_NO_RED,
    LIFE_REQUIREMENTS_PENALTY,
    LIFE_RESISTANCE_PENALTY,
    LIFE_SOCKET_PENALTY,
    LIFE_TEXT,
    QUALITY_LIFE,
    WEAPON_CRITICAL,
    WEAPON_EXTRA_SLOT,
)

from crafting_system.cli import PlanError, make_plan
from crafting_system.items import Item, Rarity
from crafting_system.targets import EnchantmentRequirement, TargetError, parse_target

ARMOUR = "Simple Robe"
WEAPON = "Rusted Sword"


def parse(text: str, *, base: str = ARMOUR):
    body = textwrap.dedent(text).lstrip("\n")
    return parse_target(f"base: {base}\nitem_level: 84\nrequirements:\n  - stat: \"+# to maximum Life\"\n{body}", DATA, source="t.yaml")


def parse_error(text: str, *, base: str = ARMOUR) -> str:
    with pytest.raises(TargetError) as caught:
        parse(text, base=base)
    return str(caught.value)


def armour(enchantment: str | None) -> Item:
    return Item.build(DATA, base_id=BODY, item_level=84, rarity=Rarity.RARE, enchantment=enchantment)


def test_a_target_without_the_key_has_no_enchantment_requirement():
    assert parse("").enchantment is None


def test_a_bare_tag_stands_for_the_clean_enchants_of_that_tag():
    target = parse(
        """
        enchantment:
          any_of: [Life]
        """
    )
    assert target.enchantment == EnchantmentRequirement(("Life",), CLEAN_LIFE)


def test_a_bare_tag_is_read_without_regard_to_case():
    assert parse("enchantment:\n  any_of: [life]\n").enchantment.mod_ids == CLEAN_LIFE


def test_a_listed_hybrid_resolves_to_itself_by_its_text_or_its_id():
    by_text = parse("enchantment:\n  any_of:\n    - \"" + LIFE_ATTRIBUTE_TEXT.replace("\n", "\\n") + "\"\n").enchantment
    by_id = parse(f"enchantment:\n  any_of: [{LIFE_ATTRIBUTE}]\n").enchantment
    assert by_text.mod_ids == by_id.mod_ids == frozenset({LIFE_ATTRIBUTE})


def test_a_stat_text_resolves_to_the_one_mod_with_that_text():
    assert parse(f'enchantment:\n  any_of: ["{LIFE_TEXT}"]\n').enchantment.mod_ids == {LIFE}


def test_an_enchant_with_a_rider_or_a_downside_is_never_in_a_tag_but_is_named_by_its_own_id_or_text():
    clean = parse("enchantment:\n  any_of: [Life]\n").enchantment.mod_ids
    for dirty in (LIFE_SOCKET_PENALTY, LIFE_NO_RED, LIFE_REQUIREMENTS_PENALTY, LIFE_RESISTANCE_PENALTY):
        assert dirty not in clean
        assert parse(f"enchantment:\n  any_of: [{dirty}]\n").enchantment.mod_ids == {dirty}
    text = DATA.mods[LIFE_SOCKET_PENALTY].text.replace("\n", "\\n")
    assert parse(f'enchantment:\n  any_of: ["{text}"]\n').enchantment.mod_ids == {LIFE_SOCKET_PENALTY}


def test_entries_of_several_kinds_are_read_as_alternatives():
    wanted = parse(f"enchantment:\n  any_of: [Life, {QUALITY_LIFE}, {ARMOUR_REQUIREMENTS}]\n").enchantment
    assert wanted.entries == ("Life", QUALITY_LIFE, ARMOUR_REQUIREMENTS)
    assert wanted.mod_ids == CLEAN_LIFE | {QUALITY_LIFE, ARMOUR_REQUIREMENTS}


def test_the_enchantments_are_resolved_among_the_base_class_only():
    weapon = parse(f"enchantment:\n  any_of: [{WEAPON_CRITICAL}, Critical]\n", base=WEAPON).enchantment
    assert weapon.mod_ids == {WEAPON_CRITICAL}
    assert "is a body armour enchantment, but the base takes weapon enchantments" in parse_error(
        f"enchantment:\n  any_of: [{LIFE}]\n", base=WEAPON
    )


def test_the_target_is_met_by_an_item_whose_enchantment_is_one_of_the_set():
    target = parse("enchantment:\n  any_of: [Life]\n")
    assert target.enchantment.is_met_by(armour(LIFE))
    assert target.enchantment.is_met_by(armour(LIFE_ATTRIBUTE))
    assert not target.enchantment.is_met_by(armour(ARMOUR_LINKED))
    assert not target.enchantment.is_met_by(armour(None))


def test_the_enchantment_counts_in_unmet_after_the_other_conditions():
    target = parse("enchantment:\n  any_of: [Life]\n")
    bare = armour(None)
    assert target.enchantment in target.unmet(bare)
    assert target.unmet(bare)[-1] is target.enchantment
    missing = armour(ARMOUR_LINKED)
    assert target.enchantment in target.unmet(missing)
    held = armour(LIFE)
    assert target.enchantment not in target.unmet(held)


def test_a_target_without_an_enchantment_has_the_same_unmet_as_before():
    target = parse("")
    assert target.unmet(armour(LIFE)) == target.unmet(armour(None))


# -- the refusals ---------------------------------------------------------------------------------


def test_all_of_is_refused_with_the_rule():
    message = parse_error(f"enchantment:\n  all_of: [{LIFE}, {ARMOUR_REQUIREMENTS}]\n")
    assert message == (
        "t.yaml:6: enchantment.all_of: `all_of` cannot be met: an item holds one enchantment, so a target cannot ask"
        " for two at once; list the enchants that would do under `any_of`"
    )


def test_two_enchantment_keys_are_refused_with_the_rule():
    message = parse_error(f"enchantment:\n  any_of: [{LIFE}]\nenchantment:\n  any_of: [{ARMOUR_REQUIREMENTS}]\n")
    assert message == (
        "t.yaml:7: enchantment: this key is written twice in one mapping, first on line 5; an item holds one"
        " enchantment, so only one `enchantment:` can be written; to accept several enchants, list them under"
        " `enchantment: {any_of: [...]}`"
    )


def test_a_list_in_place_of_the_mapping_is_refused_with_the_rule():
    message = parse_error(f"enchantment:\n  - {LIFE}\n  - {ARMOUR_REQUIREMENTS}\n")
    assert message.startswith("t.yaml:5: enchantment: must be a mapping with `any_of`, got a list; an item holds one enchantment")


def test_the_extra_crafted_slot_without_a_start_item_that_has_it_is_refused_with_the_rule_of_adr_0053():
    message = parse_error(f'enchantment:\n  any_of: ["{EXTRA_SLOT_TEXT}"]\n')
    assert message == (
        "t.yaml:6: enchantment.any_of[0]: this enchantment cannot be reached by clicking orbs;"
        " give a start item that already has it, with its price"
    )


def test_the_extra_slot_listed_among_alternatives_is_still_refused_and_the_entry_is_named():
    message = parse_error(f"enchantment:\n  any_of: [Life, {ARMOUR_EXTRA_SLOT}]\n")
    assert message.startswith("t.yaml:6: enchantment.any_of[1]: this enchantment cannot be reached by clicking orbs")


def test_a_start_item_that_holds_a_different_enchantment_does_not_satisfy_the_extra_slot_entry():
    text = f"enchantment:\n  any_of: [{ARMOUR_EXTRA_SLOT}]\nstart_item:\n  enchantment: {LIFE}\n"
    assert "cannot be reached by clicking orbs" in parse_error(text)


def test_the_extra_slot_is_accepted_when_the_start_item_has_it():
    target = parse(f"enchantment:\n  any_of: [{ARMOUR_EXTRA_SLOT}]\nstart_item:\n  enchantment: {ARMOUR_EXTRA_SLOT}\n")
    assert target.start_item.enchantment == ARMOUR_EXTRA_SLOT
    assert target.enchantment.is_met_by(target.start_item)
    assert target.unmet(target.start_item) == target.unmet(Item.build(DATA, base_id=BODY, item_level=84, rarity=Rarity.NORMAL, enchantment=ARMOUR_EXTRA_SLOT))


def test_the_weapon_extra_slot_is_checked_against_a_weapon_start_item():
    ok = parse(
        f"enchantment:\n  any_of: [{WEAPON_EXTRA_SLOT}]\nstart_item:\n  enchantment: \"{EXTRA_SLOT_TEXT}\"\n",
        base=WEAPON,
    )
    assert ok.start_item.enchantment == WEAPON_EXTRA_SLOT
    assert "cannot be reached by clicking orbs" in parse_error(f"enchantment:\n  any_of: [{WEAPON_EXTRA_SLOT}]\n", base=WEAPON)


def test_an_unknown_entry_is_refused_with_close_matches():
    message = parse_error('enchantment:\n  any_of: ["8% increased Explicit Lyfe Modifier magnitudes"]\n')
    assert message.startswith('t.yaml:6: enchantment.any_of[0]: no body armour enchantment is named "8% increased Explicit Lyfe')
    assert LIFE_TEXT in message


def test_an_entry_listed_twice_an_empty_list_and_a_missing_any_of_are_refused():
    assert "enchantment.any_of[1]: \"Life\" is listed twice (first at enchantment.any_of[0])" in parse_error(
        "enchantment:\n  any_of: [Life, Life]\n"
    )
    assert "enchantment.any_of: must be a non-empty list of enchantments (a stat text, a mod id or a tag), got an empty list" in parse_error(
        "enchantment:\n  any_of: []\n"
    )
    assert "enchantment.any_of: this key is required but missing" in parse_error("enchantment: {}\n")
    assert "unknown key `any_off`; did you mean `any_of`?" in parse_error("enchantment:\n  any_off: [Life]\n")
    assert "enchantment.any_of[0]: must be an enchantment (non-empty text), got 3" in parse_error("enchantment:\n  any_of: [3]\n")


def test_a_base_that_holds_no_enchantment_is_refused():
    message = parse_error(f"enchantment:\n  any_of: [{LIFE}]\n", base="Paua Amulet")
    assert "enchantment: Paua Amulet is a Amulet, and only weapons and body armour hold an enchantment" in message


# -- the start item ---------------------------------------------------------------------------------


def test_the_start_item_loads_its_enchantment_by_id_or_by_exact_text():
    assert parse(f"start_item:\n  enchantment: {LIFE}\n").start_item.enchantment == LIFE
    assert parse(f'start_item:\n  enchantment: "{LIFE_TEXT}"\n').start_item.enchantment == LIFE
    assert parse("").start_item.enchantment is None


def test_the_start_item_enchantment_comes_with_its_other_fields():
    start = parse(f"start_item:\n  rarity: magic\n  corrupted: true\n  enchantment: {LIFE}\n").start_item
    assert (start.rarity, start.corrupted, start.enchantment) == (Rarity.MAGIC, True, LIFE)


def test_the_start_item_names_one_enchantment_so_a_tag_is_refused():
    message = parse_error("start_item:\n  enchantment: Life\n")
    assert message.startswith('t.yaml:6: start_item.enchantment: no body armour enchantment is named "Life"')


def test_a_start_item_enchantment_of_the_wrong_class_is_refused_where_it_is_written():
    message = parse_error(f"start_item:\n  enchantment: {WEAPON_CRITICAL}\n")
    assert message.startswith(f"t.yaml:6: start_item.enchantment: `{WEAPON_CRITICAL}` is a weapon enchantment")


def test_a_start_item_enchantment_that_is_no_text_is_refused():
    assert "start_item.enchantment: must be an enchantment mod id or its exact stat text, got 4" in parse_error(
        "start_item:\n  enchantment: 4\n"
    )


def test_the_start_item_key_list_names_the_enchantment():
    assert "`enchantment`" in parse_error("start_item: 3\n")
    assert "unknown key `enchantmet`; did you mean `enchantment`?" in parse_error("start_item:\n  enchantmet: x\n")


def test_a_target_with_an_enchantment_is_refused_by_the_planner_because_it_would_ignore_it():
    target = parse(f"enchantment:\n  any_of: [{LIFE}]\n")

    with pytest.raises(PlanError, match=r"asks for an enchantment, which the planner cannot plan yet.*#242"):
        make_plan(DATA, target, price_file())
