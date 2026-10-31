"""Target files on disk: R12, R13, the B1 routes R10, R11, R05 with buy specs, and the price file path."""

from pathlib import Path

import pytest
import yaml
from abstraction_support import real_game_data
from targets_support import AMULET, BELT, DATA, EXAMPLES, belt, roll

from crafting_system.items import ExplicitMod, Rarity
from crafting_system.prices.trade_query import load_buy_spec
from crafting_system.targets import KOfN, Requirement, TargetError, load_target

R12 = EXAMPLES / "r12-lightning-amulet.yaml"
R13 = EXAMPLES / "r13-life-resist-belt.yaml"
BUY = EXAMPLES.parent / "buy"
# route: target file, buy spec file, the trade-site text of the fractured mod of the start item, and its minimum
ROUTES = {
    "r10": ("r10-fractured-boots.yaml", "r10-start-boots.yaml", "#% increased Movement Speed", 30),
    "r11": ("r11-reservation-helmet.yaml", "r11-start-helmet.yaml", "+#% to Chaos Resistance", None),
    "r05": ("r05-strength-ring.yaml", "r05-start-ring.yaml", "+# to all Attributes", 13),
}


def test_the_r12_example_parses_into_the_route():
    target = load_target(R12, DATA)

    assert (target.base_id, target.item_level, target.influences) == (AMULET, 84, frozenset())
    stat, family = target.requirements
    assert isinstance(stat, Requirement) and stat.stat == "+1 to Level of all Lightning Skill Gems"
    assert "GlobalLightningGemLevel1" in stat.mod_ids
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
    assert "JunMaster2AllDamage2_" in damage.of[0].mod_ids
    assert "EinharMasterWeaponElementalDamage1_" in damage.of[1].mod_ids


def test_the_r13_damage_families_are_damage_prefixes_the_bench_offers_on_a_belt_in_two_tiers():
    target = load_target(R13, DATA)
    damage = target.requirements[2]
    assert isinstance(damage, KOfN)

    for member in damage.of:
        offered = {
            option.actions.add_explicit_mod
            for option in DATA.bench_options
            if "Belt" in option.item_classes
            and option.actions.add_explicit_mod in member.mod_ids
            and DATA.mods[option.actions.add_explicit_mod].generation_type == "prefix"
        }
        assert offered == member.mod_ids and len(offered) == 2, member.family


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


def alias_bomb(levels: int) -> str:
    """A requirements list where each level's group lists the previous level's anchor ten times."""
    lines = ["base: Paua Amulet", "item_level: 84", "requirements:", "  - &l0 {family: IncreasedLife}"]
    for level in range(1, levels + 1):
        aliases = ", ".join([f"*l{level - 1}"] * 10)
        lines.append(f"  - &l{level} {{at_least: 1, of: [{aliases}]}}")
    return "\n".join(lines) + "\n"


def test_an_alias_bomb_is_refused_at_its_first_anchor_without_being_expanded(tmp_path):
    path = tmp_path / "bomb.yaml"
    path.write_text(alias_bomb(12), encoding="utf-8")

    with pytest.raises(TargetError) as caught:
        load_target(path, DATA)

    assert str(caught.value).startswith(f"{path}:4: ")
    assert "anchors `&l0` are not supported" in str(caught.value)


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


# -- the B1 routes R10, R11 and R05 and their buy specs (ticket #60) -----------------------------


@pytest.mark.parametrize("route", ROUTES)
def test_a_route_buy_spec_loads_and_is_the_start_price_of_its_target(route):
    target_file, buy_file, stat, minimum = ROUTES[route]
    spec = load_buy_spec(BUY / buy_file)
    start_price = yaml.safe_load((EXAMPLES / target_file).read_text(encoding="utf-8"))["start_price"]

    assert spec.name == start_price
    assert spec.rarity == "rare" and spec.corrupted is False
    assert [(mod.stat, mod.minimum, mod.fractured) for mod in spec.mods] == [(stat, minimum, True)]


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.mark.parametrize("route", ROUTES)
def test_a_route_target_loads_on_the_real_data_with_a_fractured_start_item(real, route):
    target_file, buy_file, _, _ = ROUTES[route]
    target = load_target(EXAMPLES / target_file, real)

    assert target.start_item.rarity is Rarity.RARE
    assert [mod.fractured for mod in target.start_item.mods] == [True]
    assert target.start_price == load_buy_spec(BUY / buy_file).name
    assert not target.is_met_by(target.start_item)


def test_the_r10_target_asks_for_fractured_speed_the_essence_intelligence_life_and_the_craft(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)

    assert target.base_id == "Metadata/Items/Armours/Boots/BootsInt9" and target.item_level == 84
    assert target.start_item.mods == (ExplicitMod("MovementVelocity5", 2, (30,), fractured=True),)
    speed, intelligence, life, ailments = target.requirements
    assert (speed.family, speed.min_tier, speed.not_crafted) == ("MovementVelocity", 2, True)
    assert (intelligence.family, intelligence.min_tier, intelligence.not_crafted) == ("Intelligence", 2, True)
    assert (life.family, life.min_tier, life.min_roll, life.not_crafted) == ("IncreasedLife", None, None, True)
    assert (ailments.family, ailments.not_crafted) == ("AvoidElementalStatusAilments", False)
    assert "Intelligence8" in intelligence.mod_ids
    assert "EinharMasterAvoidElementalAilments2_" in ailments.mod_ids


def test_the_r10_boots_are_met_by_the_essence_intelligence_life_and_the_crafted_ailment_avoidance(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)
    finished = target.start_item
    for mod in (
        ExplicitMod("Intelligence8", 2, (48,)),
        ExplicitMod("IncreasedLife5", 4, (75,)),
        ExplicitMod("EinharMasterAvoidElementalAilments2_", 1, (23,), crafted=True),
    ):
        finished = finished.add_mod(real, mod)
    weaker_intelligence = target.start_item.add_mod(real, ExplicitMod("Intelligence7", 3, (40,)))

    assert target.is_met_by(finished)
    assert [node.family for node in target.unmet(weaker_intelligence)] == [
        "Intelligence",
        "IncreasedLife",
        "AvoidElementalStatusAilments",
    ]


def test_the_r11_target_asks_for_chaos_resistance_reservation_high_evasion_and_life(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)

    assert target.base_id == "Metadata/Items/Armours/Helmets/HelmetDex10" and target.item_level == 84
    assert target.start_item.mods == (ExplicitMod("ChaosResist3", 4, (18,), fractured=True),)
    chaos, reservation, evasion, life = target.requirements
    assert (chaos.family, chaos.min_tier) == ("ChaosResistance", None)
    assert (reservation.family, reservation.min_tier) == ("ReducedManaReservationsCost", None)
    assert reservation.min_roll is None
    assert (evasion.family, evasion.min_tier, evasion.not_crafted) == ("DefencesPercent", 3, True)
    assert (life.family, life.not_crafted) == ("IncreasedLife", True)
    assert "ManaReservationEfficiencyEssence6_" in reservation.mod_ids


def test_the_r11_helmet_needs_evasion_of_tier_three_or_better(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)
    base = target.start_item.add_mod(real, ExplicitMod("ManaReservationEfficiencyEssence6_", 1, (7,)))
    base = base.add_mod(real, ExplicitMod("IncreasedLife5", 5, (75,)))

    assert target.is_met_by(base.add_mod(real, ExplicitMod("LocalIncreasedEvasionRatingPercent5", 3, (70,))))
    assert not target.is_met_by(base.add_mod(real, ExplicitMod("LocalIncreasedEvasionRatingPercent4", 4, (60,))))


def test_the_r05_target_asks_for_all_attributes_strength_and_one_of_life_or_a_resistance(real):
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", real)

    assert target.base_id == "Metadata/Items/Rings/Ring10" and target.item_level == 75
    assert target.start_item.mods == (ExplicitMod("AllAttributes4", 1, (14,), fractured=True),)
    attributes, strength, extra = target.requirements
    assert (attributes.family, attributes.min_tier, attributes.not_crafted) == ("AllAttributes", 1, True)
    assert (strength.family, strength.min_tier, strength.not_crafted) == ("Strength", 1, True)
    assert isinstance(extra, KOfN) and extra.at_least == 1
    assert [member.family for member in extra.of] == [
        "IncreasedLife",
        "FireResistance",
        "ColdResistance",
        "LightningResistance",
    ]
    assert "StrengthEssence7_" in strength.mod_ids


def test_the_r05_ring_is_met_by_the_essence_strength_and_a_rolled_or_crafted_life_or_resistance(real):
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", real)
    with_strength = target.start_item.add_mod(real, ExplicitMod("StrengthEssence7_", 1, (51,)))
    crafted_life = ExplicitMod("EinharMasterIncreasedLife3", 1, (45,), crafted=True)

    assert not target.is_met_by(with_strength)
    assert target.is_met_by(with_strength.add_mod(real, ExplicitMod("IncreasedLife3", 5, (45,))))
    assert target.is_met_by(with_strength.add_mod(real, ExplicitMod("FireResist4", 5, (25,))))
    assert target.is_met_by(with_strength.add_mod(real, crafted_life))  # the guide ends with a bench craft
