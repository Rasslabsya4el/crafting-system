"""Target files on disk: R12, R13, the B1 routes R10, R11, R05 with their computed buy specs, and the price file path."""

from dataclasses import replace
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from targets_support import AMULET, BELT, DATA, EXAMPLES, belt, roll

from crafting_system.items import ExplicitMod, Rarity, mod_tier
from crafting_system.prices import load_price_file
from crafting_system.targets import KOfN, Requirement, TargetError, buy_spec_of, load_target, start_price_key

R12 = EXAMPLES / "r12-lightning-amulet.yaml"
R13 = EXAMPLES / "r13-life-resist-belt.yaml"
PRICES = EXAMPLES.parents[1] / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
# route: target file, the text of the fractured mod of the start item as the buy spec searches it, and its minimum (the lowest roll of the mod)
ROUTES = {
    "r10": ("r10-fractured-boots.yaml", "30% increased Movement Speed", 30),
    "r11": ("r11-reservation-helmet.yaml", "+(31-35)% to Chaos Resistance", 31),
    "r05": ("r05-strength-ring.yaml", "+(13-16) to all Attributes", 13),
}


def test_the_r12_example_parses_into_the_route():
    target = load_target(R12, DATA)

    assert (target.base_id, target.item_level, target.influences) == (AMULET, 84, frozenset())
    stat, family = target.requirements
    assert isinstance(stat, Requirement) and stat.stat == "+1 to Level of all Lightning Skill Gems"
    assert "GlobalLightningGemLevel1" in stat.mod_ids
    assert isinstance(family, Requirement) and family.family == "LightningResistance"
    assert (family.min_tier, family.any_tier, family.min_roll, family.not_crafted) == (None, True, None, False)
    assert "LightningResist2" in family.tier_ok and "JunMaster2AllDamage3" not in family.tier_ok  # the start amulet's tier 7 counts; no craft does
    assert target.start_item.rarity is Rarity.RARE
    assert target.start_item.mods == (ExplicitMod("LightningResist2", (14,), fractured=True),)
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
    assert target.start_item.mods == () and target.start_item.rarity is Rarity.MAGIC  # the guide opens with Alteration (#576)
    life, resists, damage = target.requirements
    assert isinstance(life, Requirement)
    assert (life.family, life.min_tier, life.not_crafted) == ("IncreasedLife", 1, True)
    assert isinstance(resists, KOfN) and resists.at_least == 2
    assert [member.family for member in resists.of] == ["FireResistance", "ColdResistance", "LightningResistance"]
    assert all(member.min_tier == 1 and member.not_crafted for member in resists.of)
    # "a crafted damage modifier" is exactly the craft the given route buys (OR-2): (15-17)% increased Damage
    assert isinstance(damage, Requirement) and damage.family == "AllDamage"
    assert damage.mod_ids == frozenset({"JunMaster2AllDamage3"}) and damage.tier_ok is None


def test_the_r13_damage_craft_is_a_damage_prefix_the_bench_offers_on_a_belt():
    target = load_target(R13, DATA)
    damage = target.requirements[2]

    offered = {
        option.actions.add_explicit_mod
        for option in DATA.bench_options
        if "Belt" in option.item_classes
        and option.actions.add_explicit_mod is not None
        and DATA.mods[option.actions.add_explicit_mod].generation_type == "prefix"
    }
    assert damage.mod_ids <= offered


def test_the_r13_belt_is_met_by_life_two_resists_and_the_named_damage_craft_and_no_other_damage_mod():
    target = load_target(R13, DATA)
    life = roll("IncreasedLife3")  # tier 1
    fire, cold = roll("FireResist1"), roll("ColdResist1")
    damage = roll("JunMaster2AllDamage3", crafted=True)
    other_craft = roll("JunMaster2AllDamage2_", crafted=True)  # the (12-14)% craft: not the one the route buys
    elemental = roll("EinharMasterWeaponElementalDamage1_", crafted=True)

    assert target.is_met_by(belt(life, damage, fire, cold))
    assert target.is_met_by(belt(life, damage, cold, roll("LightningResist8")))
    assert not target.is_met_by(belt(life, other_craft, fire, cold))  # OR-2: exactly that mod
    assert not target.is_met_by(belt(life, elemental, fire, cold))
    assert not target.is_met_by(belt(life, fire, cold))
    assert not target.is_met_by(belt(life, damage, fire))
    assert not target.is_met_by(belt(damage, fire, cold))
    assert target.unmet(belt(life, damage, fire)) == (target.requirements[1],)


def test_the_r13_resists_must_be_tier_one():
    target = load_target(R13, DATA)
    life, damage = roll("IncreasedLife3"), roll("JunMaster2AllDamage3", crafted=True)

    second_tier = roll("LightningResist7")  # tier 2 in the data, whatever an item marks

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
        "base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nprice_file: ../prices/day.json\nstart_item:\n  rarity: normal\nstart: given\n",
        encoding="utf-8",
    )

    assert load_target(path, DATA).price_file == tmp_path / "targets" / ".." / "prices" / "day.json"


def test_a_price_file_is_neither_read_nor_checked(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text(
        "base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nprice_file: not-there.json\nstart_item:\n  rarity: normal\nstart: given\n",
        encoding="utf-8",
    )

    target = load_target(path, DATA)

    assert target.price_file == tmp_path / "not-there.json" and not target.price_file.exists()


def test_a_target_without_a_price_file_has_none(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text("base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nstart_item:\n  rarity: normal\nstart: given\n", encoding="utf-8")

    assert load_target(path, DATA).price_file is None


def test_a_file_is_read_as_utf8(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text(
        "# Verstärkung — 魔法\nbase: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nstart_item:\n  rarity: normal\nstart: given\n",
        encoding="utf-8",
    )

    assert load_target(path, DATA).base_id == AMULET


def test_a_file_with_a_byte_order_mark_is_read(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_bytes(b"\xef\xbb\xbfbase: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nstart_item:\n  rarity: normal\nstart: given\n")

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
        "base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\nprice_file: p.json\nstart_item:\n  rarity: normal\nstart: given\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert load_target(Path("t.yaml"), DATA).price_file == Path("p.json")


# -- the B1 routes R10, R11 and R05 and their buy specs (ticket #60) -----------------------------


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.mark.parametrize("route", ROUTES)
def test_the_buy_spec_computed_from_a_route_target_is_its_fractured_start_mod_and_is_priced_in_the_committed_file(real, route):
    target_file, stat, minimum = ROUTES[route]
    target = load_target(EXAMPLES / target_file, real)
    spec = buy_spec_of(real, target)

    assert spec.rarity == "rare" and spec.corrupted is False
    assert [(mod.stat, mod.minimum, mod.fractured) for mod in spec.mods] == [(stat, minimum, True)]
    assert spec.name == start_price_key(real, target) and spec.name in load_price_file(PRICES).prices


@pytest.mark.parametrize("route", ROUTES)
def test_a_route_target_loads_on_the_real_data_with_a_fractured_start_item(real, route):
    target_file, _, _ = ROUTES[route]
    target = load_target(EXAMPLES / target_file, real)

    assert target.start_item.rarity is Rarity.RARE
    assert [mod.fractured for mod in target.start_item.mods] == [True]
    assert target.bought
    assert not target.is_met_by(target.start_item)


def with_mods(real, item, *mods):
    """The item with each of the mods added in turn."""
    for mod in mods:
        item = item.add_mod(real, mod)
    return item


def tiered(real, base_id, mod_id, *values, crafted=False):
    """A mod with the given rolls (its tier is the game data's)."""
    return ExplicitMod(mod_id, values, crafted=crafted)


def unmet_families(target, real, *mods):
    """What the target still lacks once the mods are on its start item: a family, a stat text or "a group"."""
    unmet = target.unmet(with_mods(real, target.start_item, *mods))
    return [getattr(node, "family", None) or getattr(node, "stat", None) or "a group" for node in unmet]


def test_the_r10_target_asks_for_the_fractured_speed_the_essence_intelligence_life_of_tier_1_or_2_and_the_one_craft(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)

    assert target.base_id == "Metadata/Items/Armours/Boots/BootsInt9" and target.item_level == 84
    assert target.start_item.mods == (ExplicitMod("MovementVelocity5", (30,), fractured=True),)
    speed, intelligence, life, ailments = target.requirements
    assert (speed.family, speed.mod_ids, speed.min_tier) == ("MovementVelocity", {"MovementVelocity5"}, None)
    assert (intelligence.family, intelligence.mod_ids) == ("Intelligence", {"Intelligence8"})
    assert (intelligence.min_tier, intelligence.min_roll) == (None, None)
    # the owner's target of 2026-11-13 (#895): Life tier 1 or tier 2, not "any tier" and not the guide's "at least 70"
    assert (life.family, life.stat, life.min_tier, life.min_roll, life.not_crafted) == (None, "+# to maximum Life", 2, None, True)
    assert sorted((mod_tier(real, target.base_id, mod_id), mod_id) for mod_id in life.tier_ok) == [(1, "IncreasedLife8"), (2, "IncreasedLife7")]
    # the guide's own number stays in the other file, as a roll with no tier (#71)
    roll_70 = load_target(EXAMPLES / "r10-fractured-boots-70-life.yaml", real).requirements[2]
    assert (roll_70.stat, roll_70.min_tier, roll_70.min_roll, roll_70.tier_ok) == ("+# to maximum Life", None, (70,), None)
    assert ailments.family == "AvoidElementalStatusAilments"
    assert ailments.mod_ids == {"EinharMasterAvoidElementalAilments1"}


def test_the_r10_start_boots_carry_the_thirty_percent_speed_the_buy_spec_prices(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)
    spec = buy_spec_of(real, target)
    start_mod = target.start_item.mods[0]

    assert [(mod.stat, mod.minimum) for mod in spec.mods] == [("30% increased Movement Speed", 30)]
    assert (start_mod.mod_id, start_mod.values) == ("MovementVelocity5", (30,))
    assert mod_tier(real, target.base_id, "MovementVelocity5") == 2  # the tier is the data's: the file writes none
    assert target.requirements[0].is_met_by(target.start_item)


def test_the_r10_boots_are_met_by_the_essence_intelligence_life_of_tier_1_or_2_and_the_crafted_sixteen_to_twenty_avoidance(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)
    base_id = target.base_id
    finished = with_mods(
        real,
        target.start_item,
        tiered(real, base_id, "Intelligence8", 48),
        tiered(real, base_id, "IncreasedLife8", 120),
        ExplicitMod("EinharMasterAvoidElementalAilments1", (18,), crafted=True),
    )

    assert target.is_met_by(finished)
    assert target.unmet(finished) == ()
    # tier 2 of the boots, +(100-114), meets it too, at its lowest roll: the leaf asks a tier, not a roll
    second_tier = with_mods(
        real,
        target.start_item,
        tiered(real, base_id, "Intelligence8", 48),
        tiered(real, base_id, "IncreasedLife7", 100),
        ExplicitMod("EinharMasterAvoidElementalAilments1", (18,), crafted=True),
    )
    assert target.unmet(second_tier) == ()


def test_the_r10_boots_are_not_met_by_another_tier_of_intelligence_life_below_tier_2_or_ailment_avoidance(real):
    target = load_target(EXAMPLES / "r10-fractured-boots.yaml", real)
    base_id = target.base_id
    intelligence, life = tiered(real, base_id, "Intelligence8", 48), tiered(real, base_id, "IncreasedLife8", 120)
    craft = ExplicitMod("EinharMasterAvoidElementalAilments1", (18,), crafted=True)
    weaker_intelligence = tiered(real, base_id, "Intelligence7", 40)
    top_intelligence = tiered(real, base_id, "Intelligence9", 53)  # exactly the essence mod, not a better one
    low_life = tiered(real, base_id, "IncreasedLife6", 99)  # tier 3, +(85-99): above the guide's 70, below the owner's tier 2 (#895)
    crafted_life = ExplicitMod("EinharMasterIncreasedLife5_", (80,), crafted=True)  # from the bench: it has no natural tier
    stronger_craft = ExplicitMod("EinharMasterAvoidElementalAilments2_", (23,), crafted=True)
    life_stat = "+# to maximum Life"

    assert unmet_families(target, real, weaker_intelligence, life, craft) == ["Intelligence"]
    assert unmet_families(target, real, top_intelligence, life, craft) == ["Intelligence"]
    assert unmet_families(target, real, intelligence, low_life, craft) == [life_stat]
    assert unmet_families(target, real, intelligence, crafted_life, craft) == [life_stat]
    assert unmet_families(target, real, intelligence, life, stronger_craft) == ["AvoidElementalStatusAilments"]
    assert unmet_families(target, real, intelligence, life) == ["AvoidElementalStatusAilments"]
    assert unmet_families(target, real, weaker_intelligence, low_life, stronger_craft) == [
        "Intelligence",
        life_stat,
        "AvoidElementalStatusAilments",
    ]


def test_the_r11_target_asks_for_any_chaos_resistance_a_shrieking_or_deafening_reservation_evasion_of_tier_1_to_3_and_tier_1_life(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)

    assert target.base_id == "Metadata/Items/Armours/Helmets/HelmetDex10" and target.item_level == 84
    assert target.start_item.mods == (ExplicitMod("ChaosResist6", (33,), fractured=True),)
    chaos, reservation, evasion, life = target.requirements
    # the guide: "Buy a Fractured Chaos Resistance Base" (no tier), "Essences of Loathing (at least Shrieking)" (OR-4, #404);
    # the owner's target of 2026-11-13 (#895) for the two prefixes: Evasion tier 1 to tier 3, Life tier 1
    assert (chaos.family, chaos.min_tier, chaos.any_tier, chaos.not_crafted) == ("ChaosResistance", None, True, False)
    assert isinstance(reservation, KOfN) and reservation.at_least == 1
    assert [(member.family, member.min_tier, member.min_roll, sorted(member.mod_ids)) for member in reservation.of] == [
        ("ReducedManaReservationsCost", None, None, ["ManaReservationEfficiencyEssence6_"]),
        ("ReducedManaReservationsCost", None, None, ["ManaReservationEfficiencyEssence7"]),
    ]
    assert (evasion.family, evasion.min_tier, evasion.any_tier, evasion.not_crafted) == ("DefencesPercent", 3, False, True)
    assert sorted(mod_tier(real, target.base_id, mod_id) for mod_id in evasion.tier_ok) == [1, 2, 3]
    assert (life.family, life.stat, life.min_tier, life.min_roll, life.not_crafted) == (None, "+# to maximum Life", 1, None, True)
    assert life.tier_ok == {"IncreasedLife9"}


def test_the_r11_start_helmet_is_the_top_chaos_resistance_and_the_buy_minimum_is_the_lowest_roll_of_it(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)
    spec = buy_spec_of(real, target)
    top, next_down = real.mods["ChaosResist6"], real.mods["ChaosResist5"]
    minimum = spec.mods[0].minimum

    assert mod_tier(real, target.base_id, "ChaosResist6") == 1 and mod_tier(real, target.base_id, "ChaosResist5") == 2
    assert [(mod.stat, mod.minimum) for mod in spec.mods] == [("+(31-35)% to Chaos Resistance", 31)]
    assert top.stats[0].min == minimum and next_down.stats[0].max < minimum  # tier 2 cannot pass the buy spec
    assert target.requirements[0].is_met_by(target.start_item)


def test_the_r11_helmet_needs_a_shrieking_or_deafening_reservation_evasion_of_tier_1_to_3_and_tier_1_life(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)
    base_id = target.base_id
    reservation = ExplicitMod("ManaReservationEfficiencyEssence6_", (7,))
    deafening = ExplicitMod("ManaReservationEfficiencyEssence7", (9,))
    life = tiered(real, base_id, "IncreasedLife9", 135)
    evasion = tiered(real, base_id, "LocalIncreasedEvasionRatingPercent7", 95)
    screaming = ExplicitMod("ManaReservationEfficiencyEssence5__", (5,))
    second_tier_life = tiered(real, base_id, "IncreasedLife8", 129)  # tier 2, +(115-129): over the guide's 95, not the owner's tier 1
    third_tier_evasion = tiered(real, base_id, "LocalIncreasedEvasionRatingPercent5", 68)  # tier 3, (68-79)%: the worst that counts
    fourth_tier_evasion = tiered(real, base_id, "LocalIncreasedEvasionRatingPercent4", 67)  # tier 4, (56-67)%
    life_stat = "+# to maximum Life"

    assert target.is_met_by(with_mods(real, target.start_item, reservation, life, evasion))
    assert target.is_met_by(with_mods(real, target.start_item, deafening, life, evasion))
    assert target.is_met_by(with_mods(real, target.start_item, reservation, life, third_tier_evasion))
    assert unmet_families(target, real, screaming, life, evasion) == ["a group"]
    assert unmet_families(target, real, reservation, second_tier_life, evasion) == [life_stat]
    assert unmet_families(target, real, reservation, life, fourth_tier_evasion) == ["DefencesPercent"]
    assert unmet_families(target, real, reservation, life) == ["DefencesPercent"]


def test_the_r11_chaos_resistance_leaf_takes_any_tier_of_the_fractured_resistance(real):
    target = load_target(EXAMPLES / "r11-reservation-helmet.yaml", real)
    chaos = target.requirements[0]
    base_id = target.base_id
    lower_fractured = ExplicitMod("ChaosResist3", (18,), fractured=True)

    assert mod_tier(real, base_id, "ChaosResist3") == 4  # not the tier the start item and the buy spec price (1)
    assert chaos.is_met_by(replace(target.start_item, mods=(lower_fractured,)))


def test_the_r05_target_asks_for_all_attributes_the_essence_strength_and_tier_1_life(real):
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", real)

    assert target.base_id == "Metadata/Items/Rings/Ring10" and target.item_level == 75
    assert target.start_item.mods == (ExplicitMod("AllAttributes4", (14,), fractured=True),)
    attributes, strength, life = target.requirements
    assert (attributes.family, attributes.min_tier, attributes.not_crafted) == ("AllAttributes", 1, True)
    assert (strength.family, strength.mod_ids, strength.min_tier) == ("Strength", {"StrengthEssence7_"}, None)
    # the owner's target of 2026-11-13 (#895): tier 1 Life as the prefix, no "useful mod of any kind" (it was "at least 1 of Life and
    # the three resistances" before)
    assert isinstance(life, Requirement) and (life.family, life.min_tier, life.not_crafted) == ("IncreasedLife", 1, True)
    assert life.tier_ok == {"IncreasedLife7"} and real.mods["IncreasedLife7"].generation_type == "prefix"


def test_the_r05_ring_is_met_by_the_essence_strength_and_tier_1_life_rolled_not_crafted(real):
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", real)
    base_id = target.base_id
    with_strength = target.start_item.add_mod(real, ExplicitMod("StrengthEssence7_", (55,)))
    crafted_life = ExplicitMod("EinharMasterIncreasedLife3", (45,), crafted=True)

    assert not target.is_met_by(with_strength)
    assert target.is_met_by(with_strength.add_mod(real, tiered(real, base_id, "IncreasedLife7", 105)))
    assert not target.is_met_by(with_strength.add_mod(real, tiered(real, base_id, "FireResist7", 43)))  # a top resistance is no Life (#895)
    # the guide's closing bench craft is not a tier of Life: it has none, so it meets no tier line (OR-1; R05 once read it as tier 1, 12 c against 135 c)
    assert not target.is_met_by(with_strength.add_mod(real, crafted_life))


def test_the_r05_ring_is_not_met_by_a_lower_tier_life_a_resistance_or_another_strength(real):
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", real)
    base_id = target.base_id
    essence_strength = ExplicitMod("StrengthEssence7_", (55,))
    top_life = tiered(real, base_id, "IncreasedLife7", 105)
    second_life = tiered(real, base_id, "IncreasedLife6", 90)
    third_fire = tiered(real, base_id, "FireResist6", 38)
    rolled_strength = tiered(real, base_id, "Strength9", 53)  # tier 1 too, but not the essence mod

    assert unmet_families(target, real, essence_strength, second_life) == ["IncreasedLife"]
    assert unmet_families(target, real, essence_strength, third_fire) == ["IncreasedLife"]
    assert unmet_families(target, real, top_life) == ["Strength"]
    assert unmet_families(target, real, rolled_strength, top_life) == ["Strength"]
