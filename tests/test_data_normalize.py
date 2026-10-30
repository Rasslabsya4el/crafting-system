"""Normalizing the repoe-fork excerpts into the typed model (ADR-0003)."""

import dataclasses

import pytest
from repoe_support import fixture_game_data, no_network, raw_fixtures  # noqa: F401

from crafting_system.data.model import (
    BaseItem,
    BenchActions,
    BenchOption,
    CostEntry,
    Essence,
    EssenceMod,
    Fossil,
    GameData,
    Mod,
    StatRange,
    Weight,
)

DATA = fixture_game_data()


def W(*pairs):
    return tuple(Weight(tag, weight) for tag, weight in pairs)


def test_game_data_carries_the_version_and_keeps_file_order_of_the_mods():
    assert DATA.version == "0.0-test"
    assert list(DATA.mods) == list(raw_fixtures()["mods.json"])


def test_heated_fire_damage_mod_for_two_hand_weapons():
    mod = DATA.mods["LocalAddedFireDamageTwoHand1"]

    assert mod == Mod(
        id="LocalAddedFireDamageTwoHand1",
        name="Heated",
        text="Adds (3-5) to (6-7) Fire Damage",
        type="LocalFireDamageTwoHand",
        families=("FireDamage",),
        domain="item",
        generation_type="prefix",
        required_level=1,
        spawn_weights=W(
            ("one_hand_weapon", 0),
            ("bow", 1400),
            ("sword", 1200),
            ("axe", 1200),
            ("mace", 500),
            ("staff", 600),
            ("default", 0),
        ),
        generation_weights=W(
            ("attack_dagger", 100),
            ("dagger", 50),
            ("warstaff", 100),
            ("staff", 50),
            ("sceptre", 50),
            ("wand_can_roll_caster_modifiers", 50),
            ("default", 100),
        ),
        adds_tags=("has_attack_mod",),
        implicit_tags=("elemental_damage", "damage", "elemental", "fire", "attack"),
        stats=(
            StatRange("local_minimum_added_fire_damage", 3, 5),
            StatRange("local_maximum_added_fire_damage", 6, 7),
        ),
        is_essence_only=False,
    )


def test_local_energy_shield_mod_is_in_the_base_local_defences_family():
    mod = DATA.mods["LocalIncreasedEnergyShield1"]

    assert mod.families == ("BaseLocalDefences",)
    assert mod.type == "LocalEnergyShield"
    assert mod.name == "Shining"
    assert mod.domain == "item"
    assert mod.generation_type == "prefix"
    assert mod.required_level == 3
    assert mod.spawn_weights == W(("int_armour", 1000), ("str_dex_int_armour", 166), ("default", 0))
    assert mod.generation_weights == ()
    assert mod.adds_tags == ()
    assert mod.implicit_tags == ("defences", "energy_shield")
    assert mod.stats == (StatRange("local_energy_shield", 3, 5),)


def test_bench_mod_has_two_families_in_file_order_and_the_crafted_domain():
    mod = DATA.mods["JunMaster2ArmourAndEnergyShield1"]

    assert mod.families == ("IncreasedPhysicalDamageReductionRating", "IncreasedEnergyShield")
    assert mod.domain == "crafted"
    assert mod.type == "ArmourAndEnergyShield"
    assert mod.generation_type == "prefix"
    assert mod.required_level == 60
    assert mod.spawn_weights == W(("belt", 0), ("default", 0))
    assert mod.implicit_tags == ("unveiled_mod", "defences", "armour", "energy_shield")
    assert mod.stats == (
        StatRange("base_physical_damage_reduction_rating", 105, 150),
        StatRange("base_maximum_energy_shield", 11, 15),
    )
    assert mod.text == "+(105-150) to Armour\n+(11-15) to maximum Energy Shield"


def test_weapon_caster_prefixes_share_a_family_but_differ_in_type_and_added_tags():
    fire = DATA.mods["FireDamagePrefixOnWeapon1"]
    spell = DATA.mods["SpellDamageOnWeapon1"]

    assert fire.families == spell.families == ("WeaponCasterDamagePrefix",)
    assert (fire.type, spell.type) == ("FireDamageWeaponPrefix", "WeaponSpellDamage")
    assert fire.adds_tags == ()
    assert spell.adds_tags == ("has_caster_mod",)
    assert spell.spawn_weights[0] == Weight("attack_dagger", 0)  # file order, not sorted


def test_armour_and_energy_shield_mods_of_the_other_conflicting_pairs():
    armour = DATA.mods["LocalIncreasedPhysicalDamageReductionRating1"]
    plain = DATA.mods["IncreasedEnergyShield1"]

    assert armour.families == ("BaseLocalDefences",)
    assert armour.type == "LocalPhysicalDamageReductionRating"
    assert armour.required_level == 1
    assert plain.families == ("IncreasedEnergyShield",)
    assert plain.type == "EnergyShield"


def test_a_null_text_is_kept_as_none():
    raw = raw_fixtures()
    raw["mods.json"]["IncreasedEnergyShield1"]["text"] = None

    from crafting_system.data.normalize import normalize_mods

    assert normalize_mods(raw["mods.json"])["IncreasedEnergyShield1"].text is None


def test_unknown_raw_keys_are_ignored():
    raw = raw_fixtures()
    assert "grants_effects" in raw["mods.json"]["LocalAddedFireDamageTwoHand1"]

    assert not hasattr(DATA.mods["LocalAddedFireDamageTwoHand1"], "grants_effects")


def test_model_is_frozen_and_uses_tuples():
    mod = DATA.mods["LocalAddedFireDamageTwoHand1"]

    with pytest.raises(dataclasses.FrozenInstanceError):
        mod.name = "x"  # type: ignore[misc]
    for field in ("families", "spawn_weights", "generation_weights", "adds_tags", "implicit_tags", "stats"):
        assert isinstance(getattr(mod, field), tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        DATA.version = "x"  # type: ignore[misc]
    with pytest.raises(TypeError):
        DATA.mods["new"] = mod  # type: ignore[index]


def test_body_armour_base_keeps_its_ordered_tags():
    base = DATA.base_items["Metadata/Items/Armours/BodyArmours/BodyInt1"]

    assert base == BaseItem(
        id="Metadata/Items/Armours/BodyArmours/BodyInt1",
        name="Simple Robe",
        item_class="Body Armour",
        domain="item",
        drop_level=3,
        tags=("int_armour", "body_armour", "armour", "default"),
        implicits=(),
        release_state="released",
    )


def test_weapon_base_lists_its_implicit_mod_and_that_mod_exists():
    base = DATA.base_items["Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"]

    assert base.implicits == ("AccuracyPercentImplicitSword1",)
    assert base.tags == ("sword", "one_hand_weapon", "onehand", "weapon", "default")
    assert base.item_class == "One Hand Sword"
    assert base.name == "Rusted Sword"
    assert base.drop_level == 1
    assert base.implicits[0] in DATA.mods


def test_a_repeated_tag_of_a_base_is_kept():
    base = DATA.base_items["Metadata/Items/Weapons/OneHandWeapons/OneHandMaces/Sceptre1"]

    assert base.tags == ("sceptre", "sceptre", "one_hand_weapon", "onehand", "weapon", "default")


def test_fossil_with_weights_and_no_added_mods():
    fossil = DATA.fossils["Metadata/Items/Currency/CurrencyDelveCraftingFire"]

    assert fossil == Fossil(
        id="Metadata/Items/Currency/CurrencyDelveCraftingFire",
        name="Scorched Fossil",
        added_mods=(),
        forced_mods=(),
        allowed_tags=(),
        forbidden_tags=(),
        positive_mod_weights=W(("fire", 1000)),
        negative_mod_weights=W(("cold", 0)),
        changes_quality=False,
        rolls_lucky=False,
        rolls_white_sockets=False,
        mirrors=False,
        corrupted_essence_chance=0,
    )


def test_fossil_with_added_mods():
    fossil = DATA.fossils["Metadata/Items/Currency/CurrencyDelveCraftingGemLevel"]

    assert fossil.name == "Faceted Fossil"
    assert fossil.added_mods == (
        "DelveStrengthGemLevel1",
        "DelveDexterityGemLevel1",
        "DelveIntelligenceGemLevel1",
    )
    assert fossil.positive_mod_weights == W(("gem", 1000))
    assert fossil.negative_mod_weights == ()


def test_essence_maps_item_classes_to_mods_in_file_order():
    essence = DATA.essences["Metadata/Items/Currency/CurrencyEssenceHatred1"]

    assert essence.name == "Whispering Essence of Hatred"
    assert essence.tier == 1
    assert essence.is_corruption_only is False
    assert essence.level == 1
    assert essence.item_level_restriction == 35
    assert essence.spawn_level_min == 1
    assert essence.mods[:3] == (
        EssenceMod("Amulet", "ColdDamagePercentEssence1"),
        EssenceMod("Belt", "ColdResist1"),
        EssenceMod("Body Armour", "ColdResist1"),
    )
    assert len(essence.mods) == 22
    assert isinstance(essence, Essence)


def test_essence_mod_for_an_item_class():
    essence = DATA.essences["Metadata/Items/Currency/CurrencyEssenceHatred1"]

    assert essence.mod_for("Bow") == "LocalAddedColdDamageTwoHand1"
    assert essence.mod_for("Wand") == "LocalAddedColdDamage1"
    assert essence.mod_for("Flask") is None


def test_corruption_only_essence_and_a_missing_level_restriction():
    essence = DATA.essences["Metadata/Items/Currency/CurrencyEssenceHysteria1"]

    assert essence.is_corruption_only is True
    assert essence.tier == 6
    assert essence.item_level_restriction is None


def test_an_essence_class_with_a_null_mod_has_no_mod_for_it():
    essence = DATA.essences["Metadata/Items/Currency/CurrencyCorruptMonolith"]

    assert essence.mod_for("Amulet") is None
    assert EssenceMod("Amulet", None) in essence.mods


def test_bench_options_keep_file_order_and_have_no_ids():
    options = DATA.bench_options

    assert isinstance(options, tuple)
    assert all(isinstance(option, BenchOption) for option in options)
    assert [option.master for option in options] == [
        raw["master"] for raw in raw_fixtures()["crafting_bench_options.json"]
    ]
    assert options[0].actions.change_socket_count == 2


def test_socket_count_bench_option():
    option = DATA.bench_options[0]

    assert option.master == "Jun, Veiled Master"
    assert option.bench_tier == 0
    assert option.cost == (CostEntry("Metadata/Items/Currency/CurrencyRerollSocketNumbers", 1),)
    assert option.item_classes[:3] == ("Dagger", "Rune Dagger", "One Hand Axe")
    assert option.item_classes[-1] == "Shield"
    assert option.actions == BenchActions(
        add_explicit_mod=None,
        add_enchant_mod=None,
        change_socket_count=2,
        link_sockets=None,
        color_sockets=None,
        remove_crafted_mods=None,
        remove_enchantments=None,
        reroll_rarity=None,
        reroll_rare_mods=None,
    )


def test_link_and_colour_bench_options():
    by_action = {}
    for option in DATA.bench_options:
        if option.actions.link_sockets is not None:
            by_action["link"] = option.actions.link_sockets
        if option.actions.color_sockets is not None:
            by_action["color"] = option.actions.color_sockets

    assert by_action == {"link": 2, "color": "NN"}


def test_remove_crafted_mods_and_rarity_and_rare_reroll_options():
    actions = [option.actions for option in DATA.bench_options]

    assert [a.remove_crafted_mods for a in actions if a.remove_crafted_mods is not None] == [True]
    assert [a.reroll_rarity for a in actions if a.reroll_rarity is not None] == [True]
    assert [a.reroll_rare_mods for a in actions if a.reroll_rare_mods is not None] == [3]


def test_bench_option_with_two_cost_entries_and_an_enchant():
    (option,) = [o for o in DATA.bench_options if len(o.cost) == 2]

    assert option.master == "Niko, Master of the Depths"
    assert option.cost == (
        CostEntry("Metadata/Items/Currency/CurrencyInstillingOrb", 5),
        CostEntry("Metadata/Items/Currency/CurrencyFlaskQuality", 5),
    )
    assert option.actions.add_enchant_mod == "FlaskEnchantmentInjectorAdjacentFlasks___"
    assert option.actions.add_enchant_mod in DATA.mods


def test_the_niko_belt_option_adds_the_two_family_mod():
    (option,) = [
        o for o in DATA.bench_options if o.actions.add_explicit_mod == "JunMaster2ArmourAndEnergyShield1"
    ]
    mod = DATA.mods[option.actions.add_explicit_mod]

    assert option.master == "Niko, Master of the Depths"
    assert option.item_classes == ("Belt",)
    assert option.bench_tier == 1
    assert option.cost == (CostEntry("Metadata/Items/Currency/CurrencyRerollMagic", 8),)
    assert len(mod.families) == 2


def test_an_einhar_option_adds_a_metamod():
    (option,) = [o for o in DATA.bench_options if o.master.startswith("Einhar")]

    assert option.actions.add_explicit_mod == "StrMasterItemGenerationCannotChangePrefixes"
    assert option.cost == (CostEntry("Metadata/Items/Currency/CurrencyModValues", 2),)


def test_the_excerpt_is_closed_every_referenced_mod_exists():
    referenced = set()
    for base in DATA.base_items.values():
        referenced.update(base.implicits)
    for fossil in DATA.fossils.values():
        referenced.update(fossil.added_mods)
        referenced.update(fossil.forced_mods)
    for essence in DATA.essences.values():
        referenced.update(entry.mod_id for entry in essence.mods if entry.mod_id is not None)
    for option in DATA.bench_options:
        for mod_id in (option.actions.add_explicit_mod, option.actions.add_enchant_mod):
            if mod_id is not None:
                referenced.add(mod_id)

    assert referenced - set(DATA.mods) == set()


def test_game_data_is_a_game_data():
    assert isinstance(DATA, GameData)
