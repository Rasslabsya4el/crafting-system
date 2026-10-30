"""Parsing a target file: the keys, the defaults, the start item and the price file path."""

from pathlib import Path

from targets_support import AMULET, BELT, DATA, parse

from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.targets import KOfN, Requirement, Target


def test_a_minimal_target_resolves_the_base_and_fills_the_defaults():
    target = parse(
        """
        requirements:
          - stat: "+1 to Level of all Lightning Skill Gems"
        """
    )

    assert isinstance(target, Target)
    assert target.base_id == AMULET
    assert target.item_level == 84
    assert target.influences == frozenset()
    assert target.price_file is None
    assert target.start_item == Item.build(
        DATA, base_id=AMULET, item_level=84, rarity=Rarity.NORMAL
    )
    (requirement,) = target.requirements
    assert isinstance(requirement, Requirement)
    assert requirement.stat == "+1 to Level of all Lightning Skill Gems"
    assert requirement.family is None
    assert "GlobalLightningGemLevel1" in requirement.mod_ids
    assert (requirement.min_tier, requirement.min_roll, requirement.not_crafted) == (None, None, False)


def test_the_base_may_be_named_by_id():
    text = f"base: {AMULET}\nitem_level: 70\nrequirements:\n  - family: LightningResistance\n"

    target = parse(text, header=False)

    assert target.base_id == AMULET and target.item_level == 70


def test_influences_are_case_insensitive_and_go_onto_the_start_item():
    target = parse(
        """
        influence: [Shaper, ELDER]
        requirements:
          - family: LightningResistance
        """
    )

    assert target.influences == frozenset({Influence.SHAPER, Influence.ELDER})
    assert target.start_item.influences == target.influences
    assert target.start_item.rarity is Rarity.NORMAL
    assert target.start_item.mods == ()


def test_a_family_requirement_collects_every_mod_of_the_family():
    target = parse(
        """
        requirements:
          - family: LightningResistance
        """
    )

    (requirement,) = target.requirements
    assert requirement.family == "LightningResistance"
    assert requirement.stat is None
    assert {"LightningResist1", "LightningResist2", "LightningResist3"} <= requirement.mod_ids


def test_a_group_holds_its_members_in_order_and_nested_groups_parse():
    target = parse(
        """
        requirements:
          - at_least: 1
            of:
              - family: FireResistance
              - at_least: 2
                of:
                  - family: ColdResistance
                  - family: LightningResistance
                  - family: IncreasedLife
        """
    )

    (group,) = target.requirements
    assert isinstance(group, KOfN) and group.at_least == 1
    first, nested = group.of
    assert first.family == "FireResistance"
    assert isinstance(nested, KOfN) and nested.at_least == 2
    assert [member.family for member in nested.of] == ["ColdResistance", "LightningResistance", "IncreasedLife"]


def test_the_options_of_a_requirement_are_read():
    target = parse(
        """
        requirements:
          - family: LightningResistance
            min_tier: 2
            min_roll: 12
            not_crafted: true
          - stat: "Adds (1-2) to (3-4) Cold Damage"
            min_roll: [null, 4]
        """
    )

    resist, cold = target.requirements
    assert (resist.min_tier, resist.min_roll, resist.not_crafted) == (2, (12,), True)
    assert (cold.min_tier, cold.min_roll, cold.not_crafted) == (None, (None, 4), False)


def test_the_start_item_is_built_from_its_mods():
    target = parse(
        """
        requirements:
          - family: LightningResistance
        start_item:
          mods:
            - mod: LightningResist2
              tier: 3
              values: 14
              fractured: true
            - mod: IncreasedLife1
              tier: 1
              values: [10]
        """
    )

    start = target.start_item
    assert start.rarity is Rarity.RARE
    assert start.base_id == AMULET and start.item_level == 84
    assert start.mods == (
        ExplicitMod("IncreasedLife1", 1, (10,)),
        ExplicitMod("LightningResist2", 3, (14,), fractured=True),
    )


def test_the_start_item_rarity_and_corruption_are_read():
    target = parse(
        """
        influence: [hunter]
        requirements:
          - family: LightningResistance
        start_item:
          rarity: Magic
          corrupted: true
          mods:
            - mod: LightningResist1
              tier: 1
              values: [6]
        """
    )

    start = target.start_item
    assert start.rarity is Rarity.MAGIC and start.corrupted
    assert start.influences == {Influence.HUNTER}


def test_a_relative_price_file_counts_from_the_base_directory():
    text = """
        requirements:
          - family: LightningResistance
        price_file: prices/day1.json
        """

    target = parse(text, base_dir=Path("somewhere"))

    assert target.price_file == Path("somewhere") / "prices" / "day1.json"
    assert parse(text).price_file == Path("prices") / "day1.json"


def test_a_base_name_that_only_one_base_carries_finds_it():
    text = "base: Leather Belt\nitem_level: 86\nrequirements:\n  - family: IncreasedLife\n"

    assert parse(text, header=False).base_id == BELT
