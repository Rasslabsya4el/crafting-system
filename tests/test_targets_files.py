"""Target files on disk: the R12 and R13 examples, `load_target`, and the price file path."""

from pathlib import Path

import pytest
from targets_support import AMULET, BELT, DATA, EXAMPLES, belt, roll

from crafting_system.items import ExplicitMod, Rarity
from crafting_system.targets import KOfN, Requirement, TargetError, load_target

R12 = EXAMPLES / "r12-lightning-amulet.yaml"
R13 = EXAMPLES / "r13-life-resist-belt.yaml"


def test_the_r12_example_parses_into_the_route():
    target = load_target(R12, DATA)

    assert (target.base_id, target.item_level, target.influences) == (AMULET, 84, frozenset())
    stat, family = target.requirements
    assert isinstance(stat, Requirement) and stat.stat == "+1 to Level of all Lightning Skill Gems"
    assert stat.mod_ids == {"GlobalLightningGemLevel1"}
    assert isinstance(family, Requirement) and family.family == "LightningResistance"
    assert (family.min_tier, family.min_roll, family.not_crafted) == (None, None, False)
    assert target.start_item.rarity is Rarity.RARE
    assert target.start_item.mods == (ExplicitMod("LightningResist2", 3, (14,), fractured=True),)
    assert target.price_file is None


def test_the_r12_start_item_has_the_resistance_but_not_the_gem_level_and_adding_it_meets_the_target():
    target = load_target(R12, DATA)
    finished = target.start_item.add_mod(DATA, roll("GlobalLightningGemLevel1"))

    assert not target.is_met_by(target.start_item)
    assert [node.stat or node.family for node in target.unmet(target.start_item)] == [
        "+1 to Level of all Lightning Skill Gems"
    ]
    assert target.is_met_by(finished)


def test_the_r13_example_parses_into_the_route():
    target = load_target(R13, DATA)

    assert (target.base_id, target.item_level) == (BELT, 86)
    assert target.start_item.mods == () and target.start_item.rarity is Rarity.NORMAL
    life, resists, damage = target.requirements
    assert isinstance(life, Requirement)
    assert (life.family, life.min_tier, life.not_crafted) == ("IncreasedLife", 1, True)
    assert isinstance(resists, KOfN) and resists.at_least == 2
    assert [member.family for member in resists.of] == ["FireResistance", "ColdResistance", "LightningResistance"]
    assert all(member.min_tier == 1 and member.not_crafted for member in resists.of)
    assert isinstance(damage, KOfN) and damage.at_least == 1
    assert [member.family for member in damage.of] == ["AllDamage", "IncreasedWeaponElementalDamagePercent"]
    assert damage.of[0].mod_ids == {"JunMaster2AllDamage2_"}
    assert damage.of[1].mod_ids == {"EinharMasterWeaponElementalDamage1_"}


def test_the_r13_belt_is_met_by_life_two_resists_and_a_crafted_damage_mod():
    target = load_target(R13, DATA)
    life = roll("IncreasedLife1")
    fire, cold = roll("FireResist1"), roll("ColdResist1")
    damage = roll("JunMaster2AllDamage2_", crafted=True)
    elemental = roll("EinharMasterWeaponElementalDamage1_", crafted=True)

    assert target.is_met_by(belt(life, damage, fire, cold))
    assert target.is_met_by(belt(life, elemental, cold, roll("LightningResist1")))
    assert not target.is_met_by(belt(life, fire, cold))
    assert not target.is_met_by(belt(life, damage, fire))
    assert not target.is_met_by(belt(damage, fire, cold))
    assert target.unmet(belt(life, damage, fire)) == (target.requirements[1],)


def test_the_r13_resists_must_be_tier_one():
    target = load_target(R13, DATA)
    life, damage = roll("IncreasedLife1"), roll("JunMaster2AllDamage2_", crafted=True)

    second_tier = ExplicitMod("ColdResist1", 2, (6,))

    assert not target.is_met_by(belt(life, damage, roll("FireResist1"), second_tier))


def test_a_relative_price_file_counts_from_the_folder_of_the_target_file(tmp_path):
    path = tmp_path / "targets" / "t.yaml"
    path.parent.mkdir()
    path.write_text(
        "base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nprice_file: ../prices/day.json\n",
        encoding="utf-8",
    )

    assert load_target(path, DATA).price_file == tmp_path / "targets" / ".." / "prices" / "day.json"


def test_a_price_file_is_neither_read_nor_checked(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text(
        "base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nprice_file: not-there.json\n",
        encoding="utf-8",
    )

    target = load_target(path, DATA)

    assert target.price_file == tmp_path / "not-there.json" and not target.price_file.exists()


def test_a_target_without_a_price_file_has_none(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text("base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n", encoding="utf-8")

    assert load_target(path, DATA).price_file is None


def test_a_file_is_read_as_utf8(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text(
        "# Verstärkung — 魔法\nbase: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n",
        encoding="utf-8",
    )

    assert load_target(path, DATA).base_id == AMULET


def test_a_file_with_a_byte_order_mark_is_read(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_bytes(b"\xef\xbb\xbfbase: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n")

    assert load_target(path, DATA).base_id == AMULET


def test_a_missing_file_is_a_target_error_that_names_the_path(tmp_path):
    path = tmp_path / "nowhere.yaml"

    with pytest.raises(TargetError) as caught:
        load_target(path, DATA)

    assert str(path) in str(caught.value) and "does not exist" in str(caught.value)


def test_a_file_that_is_not_utf8_is_a_target_error(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_bytes(b"base: Paua Amulet\n# \xff\xfe\n")

    with pytest.raises(TargetError, match="not UTF-8"):
        load_target(path, DATA)


def test_a_folder_instead_of_a_file_is_a_target_error(tmp_path):
    with pytest.raises(TargetError, match="cannot be read"):
        load_target(tmp_path, DATA)


def test_errors_from_a_file_name_the_path_as_given(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("base: Paua Amulet\nitem_level: 101\nrequirements:\n  - family: IncreasedLife\n", encoding="utf-8")

    with pytest.raises(TargetError) as caught:
        load_target(path, DATA)

    assert str(caught.value).startswith(f"{path}:2: item_level: ")


def test_loading_works_from_a_relative_path(tmp_path, monkeypatch):
    (tmp_path / "t.yaml").write_text(
        "base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nprice_file: p.json\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert load_target(Path("t.yaml"), DATA).price_file == Path("p.json")
