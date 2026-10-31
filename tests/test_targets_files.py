"""Target files on disk: R12, R13, the B1 routes R10, R11, R05 with buy specs, and the price file path."""

from pathlib import Path

import pytest
import yaml
from abstraction_support import real_game_data
from targets_support import AMULET, BELT, DATA, EXAMPLES, belt, roll

from crafting_system.items import ExplicitMod, Rarity, mod_tier
from crafting_system.prices.trade_query import load_buy_spec
from crafting_system.targets import KOfN, Requirement, TargetError, load_target

R12 = EXAMPLES / "r12-lightning-amulet.yaml"
R13 = EXAMPLES / "r13-life-resist-belt.yaml"
BUY = EXAMPLES.parent / "buy"
# route: target file, buy spec file, the trade-site text of the fractured mod of the start item, and its minimum
ROUTES = {
    "r10": ("r10-fractured-boots.yaml", "r10-start-boots.yaml", "#% increased Movement Speed", 30),
    "r11": ("r11-reservation-helmet.yaml", "r11-start-helmet.yaml", "+#% to Chaos Resistance", 31),
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


def with_mods(real, item, *mods):
    """The item with each of the mods added in turn."""
    for mod in mods:
        item = item.add_mod(real, mod)
    return item


def tiered(real, base_id, mod_id, *values, crafted=False):
    """A mod as the game data tiers it on the base, with the given rolls."""
    return ExplicitMod(mod_id, mod_tier(real, base_id, mod_id), values, crafted=crafted)


def unmet_families(target, real, *mods):
    """What the target still lacks once the mods are on its start item: a family, a stat text or "a group"."""
    unmet = target.unmet(with_mods(real, target.start_item, *mods))
    return [getattr(node, "family", None) or getattr(node, "stat", None) or "a group" for node in unmet]


def test_the_r10_target_asks_for_the_fractured_speed_the_essence_intelligence_top_life_and_the_one_craft(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)

    assert target.base_id == "Metadata/Items/Armours/Boots/BootsInt9" and target.item_level == 84
    assert target.start_item.mods == (ExplicitMod("MovementVelocity5", 2, (30,), fractured=True),)
    speed, intelligence, life, ailments = target.requirements
    assert (speed.family, speed.mod_ids, speed.min_tier) == ("MovementVelocity", {"MovementVelocity5"}, None)
    assert (intelligence.family, intelligence.mod_ids) == ("Intelligence", {"Intelligence8"})
    assert (intelligence.min_tier, intelligence.min_roll) == (None, None)
    assert (life.family, life.min_tier, life.min_roll, life.not_crafted) == ("IncreasedLife", 1, None, True)
    assert ailments.family == "AvoidElementalStatusAilments"
    assert ailments.mod_ids == {"EinharMasterAvoidElementalAilments1"}


def test_the_r10_start_boots_carry_the_thirty_percent_speed_the_buy_spec_prices(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)
    spec = load_buy_spec(BUY / "r10-start-boots.yaml")
    start_mod = target.start_item.mods[0]

    assert [(mod.stat, mod.minimum) for mod in spec.mods] == [("#% increased Movement Speed", 30)]
    assert (start_mod.mod_id, start_mod.values) == ("MovementVelocity5", (30,))
    assert start_mod.tier == mod_tier(real, target.base_id, "MovementVelocity5") == 2
    assert target.requirements[0].is_met_by(target.start_item)


def test_the_r10_boots_are_met_by_the_essence_intelligence_top_life_and_the_crafted_sixteen_to_twenty_avoidance(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)
    base_id = target.base_id
    finished = with_mods(
        real,
        target.start_item,
        tiered(real, base_id, "Intelligence8", 48),
        tiered(real, base_id, "IncreasedLife8", 120),
        ExplicitMod("EinharMasterAvoidElementalAilments1", 1, (18,), crafted=True),
    )

    assert target.is_met_by(finished)
    assert target.unmet(finished) == ()


def test_the_r10_boots_are_not_met_by_another_tier_of_intelligence_life_or_ailment_avoidance(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)
    base_id = target.base_id
    intelligence, life = tiered(real, base_id, "Intelligence8", 48), tiered(real, base_id, "IncreasedLife8", 120)
    craft = ExplicitMod("EinharMasterAvoidElementalAilments1", 1, (18,), crafted=True)
    weaker_intelligence = tiered(real, base_id, "Intelligence7", 40)
    top_intelligence = tiered(real, base_id, "Intelligence9", 53)  # exactly the essence mod, not a better one
    second_life = tiered(real, base_id, "IncreasedLife7", 105)
    stronger_craft = ExplicitMod("EinharMasterAvoidElementalAilments2_", 1, (23,), crafted=True)

    assert unmet_families(target, real, weaker_intelligence, life, craft) == ["Intelligence"]
    assert unmet_families(target, real, top_intelligence, life, craft) == ["Intelligence"]
    assert unmet_families(target, real, intelligence, second_life, craft) == ["IncreasedLife"]
    assert unmet_families(target, real, intelligence, life, stronger_craft) == ["AvoidElementalStatusAilments"]
    assert unmet_families(target, real, intelligence, life) == ["AvoidElementalStatusAilments"]
    assert unmet_families(target, real, weaker_intelligence, second_life, stronger_craft) == [
        "Intelligence",
        "IncreasedLife",
        "AvoidElementalStatusAilments",
    ]


def test_the_r11_target_asks_for_top_chaos_resistance_the_shrieking_reservation_top_evasion_and_top_life(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)

    assert target.base_id == "Metadata/Items/Armours/Helmets/HelmetDex10" and target.item_level == 84
    assert target.start_item.mods == (ExplicitMod("ChaosResist6", 1, (33,), fractured=True),)
    chaos, reservation, evasion, life = target.requirements
    assert (chaos.family, chaos.min_tier, chaos.not_crafted) == ("ChaosResistance", 1, False)
    assert reservation.family == "ReducedManaReservationsCost"
    assert (reservation.min_tier, reservation.min_roll) == (None, None)
    assert reservation.mod_ids == {"ManaReservationEfficiencyEssence6_"}
    assert (evasion.family, evasion.min_tier, evasion.not_crafted) == ("DefencesPercent", 1, True)
    assert (life.family, life.min_tier, life.not_crafted) == ("IncreasedLife", 1, True)


def test_the_r11_start_helmet_is_the_top_chaos_resistance_and_the_buy_minimum_is_the_lowest_roll_of_it(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)
    spec = load_buy_spec(BUY / "r11-start-helmet.yaml")
    top, next_down = real.mods["ChaosResist6"], real.mods["ChaosResist5"]
    minimum = spec.mods[0].minimum

    assert mod_tier(real, target.base_id, "ChaosResist6") == 1 and mod_tier(real, target.base_id, "ChaosResist5") == 2
    assert [(mod.stat, mod.minimum) for mod in spec.mods] == [("+#% to Chaos Resistance", 31)]
    assert top.stats[0].min == minimum and next_down.stats[0].max < minimum  # tier 2 cannot pass the buy spec
    assert target.requirements[0].is_met_by(target.start_item)


def test_the_r11_helmet_needs_the_top_evasion_and_life_and_exactly_the_shrieking_reservation(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)
    base_id = target.base_id
    reservation = ExplicitMod("ManaReservationEfficiencyEssence6_", 1, (7,))
    life = tiered(real, base_id, "IncreasedLife9", 135)
    evasion = tiered(real, base_id, "LocalIncreasedEvasionRatingPercent7", 95)
    screaming = ExplicitMod("ManaReservationEfficiencyEssence5__", 1, (5,))
    second_life = tiered(real, base_id, "IncreasedLife8", 120)
    second_evasion = tiered(real, base_id, "LocalIncreasedEvasionRatingPercent6", 85)

    assert target.is_met_by(with_mods(real, target.start_item, reservation, life, evasion))
    assert unmet_families(target, real, screaming, life, evasion) == ["ReducedManaReservationsCost"]
    assert unmet_families(target, real, reservation, second_life, evasion) == ["IncreasedLife"]
    assert unmet_families(target, real, reservation, life, second_evasion) == ["DefencesPercent"]
    assert unmet_families(target, real, reservation, life) == ["DefencesPercent"]


def test_the_r05_target_asks_for_all_attributes_the_essence_strength_and_one_top_tier_life_or_resistance(real):
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", real)

    assert target.base_id == "Metadata/Items/Rings/Ring10" and target.item_level == 75
    assert target.start_item.mods == (ExplicitMod("AllAttributes4", 1, (14,), fractured=True),)
    attributes, strength, extra = target.requirements
    assert (attributes.family, attributes.min_tier, attributes.not_crafted) == ("AllAttributes", 1, True)
    assert (strength.family, strength.mod_ids, strength.min_tier) == ("Strength", {"StrengthEssence7_"}, None)
    assert isinstance(extra, KOfN) and extra.at_least == 1
    assert [(member.family, member.min_tier, member.not_crafted) for member in extra.of] == [
        ("IncreasedLife", 1, False),
        ("FireResistance", 2, False),
        ("ColdResistance", 2, False),
        ("LightningResistance", 2, False),
    ]


def test_the_r05_ring_is_met_by_the_essence_strength_and_a_top_tier_life_or_resistance_rolled_or_crafted(real):
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", real)
    base_id = target.base_id
    with_strength = target.start_item.add_mod(real, ExplicitMod("StrengthEssence7_", 1, (55,)))
    crafted_life = ExplicitMod("EinharMasterIncreasedLife3", 1, (45,), crafted=True)

    assert not target.is_met_by(with_strength)
    assert target.is_met_by(with_strength.add_mod(real, tiered(real, base_id, "IncreasedLife7", 105)))
    assert target.is_met_by(with_strength.add_mod(real, tiered(real, base_id, "FireResist7", 43)))
    assert target.is_met_by(with_strength.add_mod(real, crafted_life))  # the guide ends with a bench craft


def test_the_r05_ring_is_not_met_by_a_lower_tier_life_or_resistance_or_by_another_strength(real):
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", real)
    base_id = target.base_id
    essence_strength = ExplicitMod("StrengthEssence7_", 1, (55,))
    top_life = tiered(real, base_id, "IncreasedLife7", 105)
    second_life = tiered(real, base_id, "IncreasedLife6", 90)
    third_fire = tiered(real, base_id, "FireResist6", 38)
    rolled_strength = tiered(real, base_id, "Strength9", 53)  # tier 1 too, but not the essence mod

    group = ["a group"]
    assert unmet_families(target, real, essence_strength, second_life) == group
    assert unmet_families(target, real, essence_strength, third_fire) == group
    assert unmet_families(target, real, top_life) == ["Strength"]
    assert unmet_families(target, real, rolled_strength, top_life) == ["Strength"]
