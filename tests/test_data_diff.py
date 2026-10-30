"""The patch diff of two `GameData` versions: what it lists, the order, the escaping, determinism."""

import copy
import random

import pytest
from repoe_support import fixture_game_data, game_data_from_raw, no_network, raw_fixtures  # noqa: F401
from seeded_versions import FOSSIL_FIRE, HATRED, SEEDED_CHANGES, SEEDED_DIFF_TEXT, seeded_raw

from crafting_system.data import PatchDiff, compare_game_data, diff_game_data, render_diff

SECTION_TITLES = (
    "Mods",
    "Spawn weights",
    "Generation weights",
    "Families",
    "Tags",
    "Bench options",
    "Essences",
    "Fossils",
)


def changed(mutate):
    """The diff of the committed excerpts against a copy changed by `mutate(raw)`."""
    raw = copy.deepcopy(raw_fixtures())
    mutate(raw)
    return compare_game_data(fixture_game_data(), game_data_from_raw(raw))


def section_lines(diff: PatchDiff, title: str) -> list[str]:
    """The rendered lines of one section, count line first; empty if the section is absent."""
    lines = render_diff(diff).split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{title}: ")), None)
    if start is None:
        return []
    end = next((i for i in range(start, len(lines)) if lines[i] == ""), len(lines))
    return lines[start:end]


def titles(diff: PatchDiff) -> list[str]:
    return [section.title for section in diff.sections]


# --- nothing changed ---------------------------------------------------------------------------


def test_identical_versions_say_there_are_no_changes_after_the_header():
    data = fixture_game_data()

    text = diff_game_data(data, data, old_label="one", new_label="two")

    assert text == "Patch diff: one -> two\nNo changes."
    assert compare_game_data(data, data).sections == ()


def test_labels_default_to_the_version_of_each_data():
    data = fixture_game_data()

    assert diff_game_data(data, data).splitlines()[0] == "Patch diff: 0.0-test -> 0.0-test"


def test_a_change_of_family_order_alone_is_not_a_change():
    def reorder(raw):
        raw["mods.json"]["JunMaster2ArmourAndEnergyShield1"]["groups"].reverse()

    assert changed(reorder).sections == ()


# --- mods --------------------------------------------------------------------------------------


def test_an_added_and_a_removed_mod_are_listed_once_and_not_in_the_other_mod_sections():
    def edit(raw):
        mods = raw["mods.json"]
        mods["ColdResist2"] = copy.deepcopy(mods["ColdResist1"])
        mods["ColdResist2"].update(name="of the Polar Bear", required_level=12, text="+(12-17)% to Cold\nResistance")
        del mods["FireDamagePrefixOnWeapon1"]

    diff = changed(edit)

    assert titles(diff) == ["Mods"]
    assert section_lines(diff, "Mods") == [
        "Mods: 1 added, 1 removed",
        '+ ColdResist2 "of the Polar Bear": text "+(12-17)% to Cold\\nResistance", level 12, domain item, '
        "generation_type suffix, families ColdResistance",
        '- FireDamagePrefixOnWeapon1 "Searing": text "(10-19)% increased Fire Damage", level 2, domain item, '
        "generation_type prefix, families WeaponCasterDamagePrefix",
    ]


def test_changed_scalar_fields_of_a_mod_are_listed_as_old_to_new():
    def edit(raw):
        mod = raw["mods.json"]["ColdResist1"]
        mod.update(name="of the Yeti", text=None, type="Other", domain="crafted", generation_type="prefix")
        mod.update(required_level=9, is_essence_only=True)
        mod["stats"] = [{"id": "base_cold_damage_resistance_%", "min": 7, "max": 12}]

    diff = changed(edit)

    assert section_lines(diff, "Mods") == [
        "Mods: 1 changed",
        "~ ColdResist1",
        '    name: "of the Inuit" -> "of the Yeti"',
        '    text: "+(6-11)% to Cold Resistance" -> none',
        '    type: "ColdResistance" -> "Other"',
        '    domain: "item" -> "crafted"',
        '    generation_type: "suffix" -> "prefix"',
        "    required_level: 1 -> 9",
        "    stats: base_cold_damage_resistance_% (6 to 11) -> base_cold_damage_resistance_% (7 to 12)",
        "    is_essence_only: false -> true",
    ]
    assert titles(diff) == ["Mods"]


# --- spawn and generation weights --------------------------------------------------------------


def test_a_changed_added_and_removed_spawn_weight_are_listed_per_tag():
    def edit(raw):
        raw["mods.json"]["ColdResist1"]["spawn_weights"] = [
            {"tag": "armour", "weight": 1500},
            {"tag": "ring", "weight": 1000},
            {"tag": "amulet", "weight": 1000},
            {"tag": "belt", "weight": 1000},
            {"tag": "helmet", "weight": 0},
            {"tag": "default", "weight": 0},
        ]

    diff = changed(edit)

    assert titles(diff) == ["Spawn weights"]
    assert section_lines(diff, "Spawn weights") == [
        "Spawn weights: 1 changed",
        '~ ColdResist1 "of the Inuit"',
        "    armour: 1000 -> 1500",
        "    + helmet: 0",
        "    - quiver: 1000",
    ]


def test_generation_weights_have_their_own_section():
    def edit(raw):
        for entry in raw["mods.json"]["LocalAddedColdDamage1"]["generation_weights"]:
            if entry["tag"] == "dagger":
                entry["weight"] = 75

    diff = changed(edit)

    assert titles(diff) == ["Generation weights"]
    assert section_lines(diff, "Generation weights") == [
        "Generation weights: 1 changed",
        '~ LocalAddedColdDamage1 "Frosted"',
        "    dagger: 50 -> 75",
    ]


def test_an_order_only_change_of_the_weights_is_reported_as_such():
    def edit(raw):
        weights = raw["mods.json"]["ColdResist1"]["spawn_weights"]
        weights[0], weights[1] = weights[1], weights[0]

    diff = changed(edit)

    assert section_lines(diff, "Spawn weights") == [
        "Spawn weights: 1 changed",
        '~ ColdResist1 "of the Inuit"',
        "    order changed: armour, ring, amulet, belt, quiver, default -> ring, armour, amulet, belt, quiver, default",
    ]


def test_a_duplicate_tag_in_a_weight_list_does_not_crash_and_is_reported():
    def edit(raw):
        raw["mods.json"]["ColdResist1"]["spawn_weights"].insert(1, {"tag": "armour", "weight": 7})

    diff = changed(edit)

    assert section_lines(diff, "Spawn weights") == [
        "Spawn weights: 1 changed",
        '~ ColdResist1 "of the Inuit"',
        "    + armour #2: 7",
    ]


def test_weights_of_an_added_mod_are_not_listed_in_the_weight_sections():
    def edit(raw):
        raw["mods.json"]["ColdResist2"] = copy.deepcopy(raw["mods.json"]["ColdResist1"])

    assert titles(changed(edit)) == ["Mods"]


# --- families and tags -------------------------------------------------------------------------


def test_families_are_compared_as_sets_per_mod():
    def edit(raw):
        raw["mods.json"]["JunMaster2ArmourAndEnergyShield1"]["groups"] = ["IncreasedEnergyShield", "ZedFamily"]

    diff = changed(edit)

    assert titles(diff) == ["Families"]
    assert section_lines(diff, "Families") == [
        "Families: 1 changed",
        '~ JunMaster2ArmourAndEnergyShield1 "Upgraded"',
        "    + ZedFamily",
        "    - IncreasedPhysicalDamageReductionRating",
    ]


def test_tags_of_mods_and_base_items_and_added_and_removed_base_items():
    def edit(raw):
        raw["mods.json"]["LocalAddedColdDamage1"]["adds_tags"] = ["has_cold_mod"]
        raw["mods.json"]["ColdResist1"]["implicit_tags"].append("extra")
        bases = raw["base_items.json"]
        sceptre = bases["Metadata/Items/Weapons/OneHandWeapons/OneHandMaces/Sceptre1"]
        sceptre["tags"] = [tag for tag in sceptre["tags"] if tag != "onehand"] + ["zed"]
        bases["Metadata/Items/Armours/BodyArmours/BodyInt2"] = copy.deepcopy(
            bases["Metadata/Items/Armours/BodyArmours/BodyInt1"]
        )
        del bases["Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"]

    diff = changed(edit)

    assert titles(diff) == ["Tags"]
    assert section_lines(diff, "Tags") == [
        "Tags: 1 added, 1 removed, 3 changed",
        '+ base item Metadata/Items/Armours/BodyArmours/BodyInt2 "Simple Robe": item_class Body Armour',
        '- base item Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1 "Rusted Sword": '
        "item_class One Hand Sword",
        '~ mod ColdResist1 "of the Inuit"',
        "    implicit_tags: + extra",
        '~ mod LocalAddedColdDamage1 "Frosted"',
        "    adds_tags: + has_cold_mod",
        "    adds_tags: - has_attack_mod",
        '~ base item Metadata/Items/Weapons/OneHandWeapons/OneHandMaces/Sceptre1 "Driftwood Sceptre"',
        "    tags: + zed",
        "    tags: - onehand",
    ]


# --- bench options -----------------------------------------------------------------------------


def test_a_bench_option_is_paired_by_master_actions_and_item_classes_and_its_cost_and_tier_compared():
    def edit(raw):
        options = raw["crafting_bench_options.json"]
        options[0]["cost"] = {"Metadata/Items/Currency/CurrencyRerollSocketNumbers": 3, "Metadata/X/Extra": 1}
        options[5]["bench_tier"] = 2
        options[5]["item_classes"] = ["Belt"]  # unchanged set

    diff = changed(edit)

    assert titles(diff) == ["Bench options"]
    lines = section_lines(diff, "Bench options")
    assert lines[0] == "Bench options: 2 changed"
    assert "    bench_tier: 1 -> 2" in lines
    assert "    cost CurrencyRerollSocketNumbers: 1 -> 3" in lines
    assert "    + cost Extra: 1" in lines


def test_the_text_of_the_mod_an_option_adds_is_shown_with_it():
    def edit(raw):
        raw["crafting_bench_options.json"].pop(5)

    lines = section_lines(changed(edit), "Bench options")

    assert lines[0] == "Bench options: 1 removed"
    assert lines[1].startswith("- Niko, Master of the Depths: add_explicit_mod JunMaster2ArmourAndEnergyShield1 (")
    assert "+(105-150) to Armour\\n+(11-15) to maximum Energy" in lines[1]
    assert "item classes Belt" in lines[1]
    assert "bench_tier 1" in lines[1]
    assert "cost CurrencyRerollMagic x8" in lines[1]


def test_options_with_the_same_key_are_paired_in_file_order_and_leftovers_are_added():
    def edit(raw):
        options = raw["crafting_bench_options.json"]
        options.insert(0, copy.deepcopy(options[0]))  # the same key twice; the first of them is new
        options[0]["cost"] = {"Metadata/Items/Currency/CurrencyRerollSocketNumbers": 4}

    lines = section_lines(changed(edit), "Bench options")

    assert lines[0] == "Bench options: 1 added, 1 changed"
    assert lines[1].startswith("+ Jun, Veiled Master: change_socket_count 2; ")
    assert lines[1].endswith("cost CurrencyRerollSocketNumbers x1")
    assert lines[3] == "    cost CurrencyRerollSocketNumbers: 1 -> 4"


def test_the_order_of_item_classes_does_not_make_a_bench_option_different():
    def edit(raw):
        raw["crafting_bench_options.json"][0]["item_classes"].reverse()

    assert changed(edit).sections == ()


# --- essences and fossils ----------------------------------------------------------------------


def test_essences_added_removed_and_changed():
    def edit(raw):
        essences = raw["essences.json"]
        hatred = essences[HATRED]
        hatred.update(name="Renamed", level=3, item_level_restriction=None, spawn_level_min=9)
        hatred["type"] = {"is_corruption_only": True, "tier": 2}
        hatred["mods"]["Amulet"] = None
        hatred["mods"]["Wand"] = "ColdResist1"
        del hatred["mods"]["Belt"]
        essences["Metadata/Items/Currency/CurrencyEssenceNew"] = copy.deepcopy(essences[HATRED])
        del essences["Metadata/Items/Currency/CurrencyCorruptMonolith"]

    diff = changed(edit)

    assert titles(diff) == ["Essences"]
    lines = section_lines(diff, "Essences")
    assert lines[:3] == [
        "Essences: 1 added, 1 removed, 1 changed",
        '+ Metadata/Items/Currency/CurrencyEssenceNew "Renamed": tier 2, level 3',
        '- Metadata/Items/Currency/CurrencyCorruptMonolith "Remnant of Corruption": tier 0, level 0',
    ]
    assert lines[3:] == [
        '~ Metadata/Items/Currency/CurrencyEssenceHatred1 "Renamed"',
        '    name: "Whispering Essence of Hatred" -> "Renamed"',
        "    tier: 1 -> 2",
        "    is_corruption_only: false -> true",
        "    level: 1 -> 3",
        "    item_level_restriction: 35 -> none",
        "    spawn_level_min: 1 -> 9",
        "    mod for Amulet: ColdDamagePercentEssence1 -> none",
        "    mod for Wand: LocalAddedColdDamage1 -> ColdResist1",
        "    - mod for Belt: ColdResist1",
    ]


def test_an_item_class_added_to_an_essence_is_listed():
    def edit(raw):
        raw["essences.json"][HATRED]["mods"]["Hybrid"] = "ColdResist1"

    lines = section_lines(changed(edit), "Essences")

    assert lines[2:] == ["    + mod for Hybrid: ColdResist1"]


def test_fossils_added_removed_and_changed():
    def edit(raw):
        fossils = raw["fossils.json"]
        fire = fossils[FOSSIL_FIRE]
        fire.update(name="Blazing Fossil", changes_quality=True, rolls_lucky=True, rolls_white_sockets=True)
        fire.update(mirrors=True, corrupted_essence_chance=25)
        fire["added_mods"] = ["ColdResist1"]
        fire["forced_mods"] = ["ColdResist1", "SpellDamageOnWeapon1"]
        fire["allowed_tags"] = ["fire"]
        fire["forbidden_tags"] = ["cold", "lightning"]
        fire["positive_mod_weights"] = [{"tag": "fire", "weight": 1500}, {"tag": "chaos", "weight": 1}]
        fire["negative_mod_weights"] = []
        fossils["Metadata/Items/Currency/CurrencyDelveCraftingNew"] = copy.deepcopy(fossils[FOSSIL_FIRE])
        del fossils["Metadata/Items/Currency/CurrencyDelveCraftingGemLevel"]

    diff = changed(edit)

    assert titles(diff) == ["Fossils"]
    assert section_lines(diff, "Fossils") == [
        "Fossils: 1 added, 1 removed, 1 changed",
        '+ Metadata/Items/Currency/CurrencyDelveCraftingNew "Blazing Fossil"',
        '- Metadata/Items/Currency/CurrencyDelveCraftingGemLevel "Faceted Fossil"',
        '~ Metadata/Items/Currency/CurrencyDelveCraftingFire "Blazing Fossil"',
        '    name: "Scorched Fossil" -> "Blazing Fossil"',
        "    changes_quality: false -> true",
        "    rolls_lucky: false -> true",
        "    rolls_white_sockets: false -> true",
        "    mirrors: false -> true",
        "    corrupted_essence_chance: 0 -> 25",
        "    added_mods: + ColdResist1",
        "    forced_mods: + ColdResist1",
        "    forced_mods: + SpellDamageOnWeapon1",
        "    allowed_tags: + fire",
        "    forbidden_tags: + cold",
        "    forbidden_tags: + lightning",
        "    positive_mod_weights fire: 1000 -> 1500",
        "    positive_mod_weights + chaos: 1",
        "    negative_mod_weights - cold: 0",
    ]


# --- the seeded pair ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def versions():
    return fixture_game_data(), game_data_from_raw(seeded_raw(), version="seeded")


def test_the_seeded_changes_are_all_listed_and_nothing_else(versions):
    old, new = versions

    diff = compare_game_data(old, new)

    assert SEEDED_CHANGES  # the seeds are described in seeded_versions.py
    assert titles(diff) == list(SECTION_TITLES)
    counts = {section.title: {kind: section.count(kind) for kind in "+-~"} for section in diff.sections}
    assert counts == {
        "Mods": {"+": 1, "-": 1, "~": 3},
        "Spawn weights": {"+": 0, "-": 0, "~": 3},
        "Generation weights": {"+": 0, "-": 0, "~": 2},
        "Families": {"+": 0, "-": 0, "~": 2},
        "Tags": {"+": 1, "-": 1, "~": 3},
        "Bench options": {"+": 1, "-": 1, "~": 2},
        "Essences": {"+": 1, "-": 1, "~": 2},
        "Fossils": {"+": 1, "-": 0, "~": 2},
    }


def test_the_complete_text_of_the_seeded_diff(versions):
    old, new = versions

    text = diff_game_data(old, new, old_label="3.29.3.3 (ee2084de)", new_label="commit 0123456789ab")

    assert text == SEEDED_DIFF_TEXT


def test_diff_text_is_deterministic_and_does_not_depend_on_dict_order():
    first = diff_game_data(fixture_game_data(), game_data_from_raw(seeded_raw()))
    shuffled_raw = shuffle_dicts(seeded_raw(), random.Random(7))
    old_raw = shuffle_dicts(copy.deepcopy(raw_fixtures()), random.Random(11))

    second = diff_game_data(game_data_from_raw(old_raw), game_data_from_raw(shuffled_raw))

    assert first == second


def shuffle_dicts(value, rng):
    """The same JSON value with every object's keys in another order (lists keep their order)."""
    if isinstance(value, dict):
        keys = list(value)
        rng.shuffle(keys)
        return {key: shuffle_dicts(value[key], rng) for key in keys}
    if isinstance(value, list):
        return [shuffle_dicts(item, rng) for item in value]
    return value


def test_the_reverse_diff_swaps_added_and_removed(versions):
    old, new = versions

    forward = compare_game_data(old, new)
    backward = compare_game_data(new, old)

    assert titles(forward) == titles(backward)
    for a, b in zip(forward.sections, backward.sections, strict=True):
        assert (a.count("+"), a.count("-"), a.count("~")) == (b.count("-"), b.count("+"), b.count("~"))
        assert {e.head for e in a.entries if e.kind == "+"} == {e.head for e in b.entries if e.kind == "-"}


def test_the_reverse_diff_swaps_old_and_new_values(versions):
    old, new = versions

    forward = section_lines(compare_game_data(old, new), "Mods")
    backward = section_lines(compare_game_data(new, old), "Mods")

    assert "    required_level: 1 -> 5" in forward
    assert "    required_level: 5 -> 1" in backward


def test_the_output_has_the_header_and_a_summary_then_the_sections_in_order(versions):
    old, new = versions

    text = diff_game_data(old, new, old_label="3.29.3.3 (ee2084de)", new_label="commit 0123456789ab")

    lines = text.split("\n")
    assert lines[0] == "Patch diff: 3.29.3.3 (ee2084de) -> commit 0123456789ab"
    assert lines[1] == (
        "Summary: Mods 5; Spawn weights 3; Generation weights 2; Families 2; Tags 5; "
        "Bench options 4; Essences 4; Fossils 3"
    )
    assert lines[2] == ""
    starts = [line.split(":")[0] for line in lines if line and not line.startswith((" ", "+", "-", "~"))]
    assert starts[2:] == list(SECTION_TITLES)
    assert "\r" not in text


# --- printing safety ---------------------------------------------------------------------------


def test_newlines_and_non_ascii_text_stay_on_one_escaped_line():
    def edit(raw):
        raw["mods.json"]["ColdResist1"]["text"] = "line one\nline two Ж “quoted” \\ end"

    lines = section_lines(changed(edit), "Mods")

    assert len(lines) == 3
    assert lines[2] == (
        '    text: "+(6-11)% to Cold Resistance" -> "line one\\nline two Ж “quoted” \\\\ end"'
    )
