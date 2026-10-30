"""A second fixture version of the repoe-fork data with seeded changes, for the patch diff tests.

Version A is the committed excerpts as they are; `seeded_raw()` returns a deep copy of the
parsed raw files with changes of every kind the diff reports. `SEEDED_CHANGES` lists them in
words, so a test can check that the diff reports exactly these and nothing else.
"""

import copy

from repoe_support import raw_fixtures

BODY = "Metadata/Items/Armours/BodyArmours/"
HATRED = "Metadata/Items/Currency/CurrencyEssenceHatred1"
HYSTERIA = "Metadata/Items/Currency/CurrencyEssenceHysteria1"
MONOLITH = "Metadata/Items/Currency/CurrencyCorruptMonolith"
FOSSIL_FIRE = "Metadata/Items/Currency/CurrencyDelveCraftingFire"
FOSSIL_GEM = "Metadata/Items/Currency/CurrencyDelveCraftingGemLevel"

SEEDED_CHANGES = (
    "mod added: LightningResistTest1; mod removed: FireDamagePrefixOnWeapon1",
    "mod scalars: ColdResist1 (required_level, text, stats), IncreasedEnergyShield1 (name), "
    "AreaOfEffectEssence1 (type, generation_type, is_essence_only)",
    "spawn weights: LocalIncreasedEnergyShield1 (changed, added, removed), "
    "LocalIncreasedPhysicalDamageReductionRating1 (order only), DelveStrengthGemLevel1 (duplicate tag)",
    "generation weights: LocalAddedFireDamageTwoHand1 (changed), LocalAddedColdDamage1 (order only)",
    "families: LocalAddedColdDamage1 (+), JunMaster2ArmourAndEnergyShield1 (-)",
    "tags: LocalAddedFireDamageTwoHand1 adds_tags, ColdResist1 implicit_tags, Sceptre1 base tags; "
    "base item added BodyInt2, removed OneHandSword1",
    "bench: Jun socket-count cost, Niko explicit-mod tier, one option added, one removed",
    "essences: Hatred1 changed, Hysteria1 changed, Hysteria2 added, CorruptMonolith removed",
    "fossils: Fire changed, GemLevel changed, one fossil added",
)


def _weights(*pairs):
    return [{"tag": tag, "weight": weight} for tag, weight in pairs]


def seeded_raw() -> dict[str, object]:
    raw = copy.deepcopy(raw_fixtures())
    mods = raw["mods.json"]
    bases = raw["base_items.json"]
    essences = raw["essences.json"]
    fossils = raw["fossils.json"]
    bench = raw["crafting_bench_options.json"]

    # mods added and removed
    added = copy.deepcopy(mods["ColdResist1"])
    added.update(
        name="of the Storm",
        text="+(6-11)% to Lightning Resistance",
        groups=["LightningResistance"],
        type="LightningResistance",
    )
    mods["LightningResistTest1"] = added
    del mods["FireDamagePrefixOnWeapon1"]

    # mod scalar fields
    cold = mods["ColdResist1"]
    cold["required_level"] = 5
    cold["text"] = "+(7-12)% to Cold Resistance"
    cold["stats"] = [{"id": "base_cold_damage_resistance_%", "min": 7, "max": 12}]
    mods["IncreasedEnergyShield1"]["name"] = "Gleaming"
    essence_mod = mods["AreaOfEffectEssence1"]
    essence_mod.update(type="AreaOfEffectTest", generation_type="prefix", is_essence_only=False)

    # spawn weights: one changed, one added, one removed; an order-only change; a duplicate tag
    mods["LocalIncreasedEnergyShield1"]["spawn_weights"] = _weights(
        ("int_armour", 1200), ("dex_int_armour", 500), ("default", 0)
    )
    order_only = mods["LocalIncreasedPhysicalDamageReductionRating1"]["spawn_weights"]
    order_only[0], order_only[1] = order_only[1], order_only[0]
    mods["DelveStrengthGemLevel1"]["spawn_weights"].append({"tag": "staff", "weight": 5})

    # generation weights: one changed, one order-only change
    for entry in mods["LocalAddedFireDamageTwoHand1"]["generation_weights"]:
        if entry["tag"] == "dagger":
            entry["weight"] = 75
    order_only = mods["LocalAddedColdDamage1"]["generation_weights"]
    order_only[0], order_only[1] = order_only[1], order_only[0]

    # families
    mods["LocalAddedColdDamage1"]["groups"] = ["ColdDamage", "AddedColdTest"]
    mods["JunMaster2ArmourAndEnergyShield1"]["groups"] = ["IncreasedPhysicalDamageReductionRating"]

    # tags
    mods["LocalAddedFireDamageTwoHand1"]["adds_tags"] = ["has_fire_mod"]
    cold["implicit_tags"] = ["elemental", "cold", "defences"]
    sceptre = bases["Metadata/Items/Weapons/OneHandWeapons/OneHandMaces/Sceptre1"]
    sceptre["tags"] = [tag for tag in sceptre["tags"] if tag != "onehand"] + ["caster_test"]
    robe = copy.deepcopy(bases[BODY + "BodyInt1"])
    robe["name"] = "Test Robe"
    bases[BODY + "BodyInt2"] = robe
    del bases["Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"]

    # bench options: cost changed, tier changed, one added, one removed
    sockets, _, _, _, _, explicit, _, rare, einhar = bench
    sockets["cost"]["Metadata/Items/Currency/CurrencyRerollSocketNumbers"] = 2
    explicit["bench_tier"] = 2
    new_option = copy.deepcopy(rare)
    new_option["actions"] = {**rare["actions"], "reroll_rare_mods": None, "add_explicit_mod": "ColdResist1"}
    new_option["cost"] = {"Metadata/Items/Currency/CurrencyModValues": 1}
    new_option["item_classes"] = ["Ring", "Amulet"]
    bench.remove(einhar)
    bench.append(new_option)

    # essences
    hatred = essences[HATRED]
    hatred["level"] = 2
    hatred["name"] = "Whispering Essence of Hatred II"
    hatred["mods"]["Amulet"] = "ColdResist1"
    del hatred["mods"]["Belt"]
    hatred["mods"]["Hybrid"] = "ColdResist1"
    hysteria = essences[HYSTERIA]
    hysteria.update(item_level_restriction=60, spawn_level_min=1)
    hysteria["type"] = {"is_corruption_only": False, "tier": 7}
    twin = copy.deepcopy(hysteria)
    twin["name"] = "Essence of Hysteria Two"
    essences["Metadata/Items/Currency/CurrencyEssenceHysteria2"] = twin
    del essences[MONOLITH]

    # fossils
    fire = fossils[FOSSIL_FIRE]
    fire["positive_mod_weights"] = _weights(("fire", 1500))
    fire["negative_mod_weights"] = _weights(("cold", 0), ("lightning", 0))
    fire["forbidden_tags"] = ["lightning"]
    fire["changes_quality"] = True
    gem = fossils[FOSSIL_GEM]
    gem["added_mods"] = ["DelveStrengthGemLevel1", "DelveIntelligenceGemLevel1"]
    gem["forced_mods"] = ["ColdResist1"]
    gem["corrupted_essence_chance"] = 10
    extra = copy.deepcopy(fire)
    extra["name"] = "Test Fossil"
    fossils["Metadata/Items/Currency/CurrencyDelveCraftingTest"] = extra
    return raw


# The complete text of the diff of the two versions, with the labels used in the tests below; every
# line was checked by hand against the seeds above.
SEEDED_DIFF_TEXT = r"""Patch diff: 3.29.3.3 (ee2084de) -> commit 0123456789ab
Summary: Mods 5; Spawn weights 3; Generation weights 2; Families 2; Tags 5; Bench options 4; Essences 4; Fossils 3

Mods: 1 added, 1 removed, 3 changed
+ LightningResistTest1 "of the Storm": text "+(6-11)% to Lightning Resistance", level 1, domain item, generation_type suffix, families LightningResistance
- FireDamagePrefixOnWeapon1 "Searing": text "(10-19)% increased Fire Damage", level 2, domain item, generation_type prefix, families WeaponCasterDamagePrefix
~ AreaOfEffectEssence1
    type: "AreaOfEffect" -> "AreaOfEffectTest"
    generation_type: "suffix" -> "prefix"
    is_essence_only: true -> false
~ ColdResist1
    text: "+(6-11)% to Cold Resistance" -> "+(7-12)% to Cold Resistance"
    required_level: 1 -> 5
    stats: base_cold_damage_resistance_% (6 to 11) -> base_cold_damage_resistance_% (7 to 12)
~ IncreasedEnergyShield1
    name: "Shining" -> "Gleaming"

Spawn weights: 3 changed
~ DelveStrengthGemLevel1 "of the Underground"
    + staff #2: 5
~ LocalIncreasedEnergyShield1 "Shining"
    int_armour: 1000 -> 1200
    + dex_int_armour: 500
    - str_dex_int_armour: 166
~ LocalIncreasedPhysicalDamageReductionRating1 "Lacquered"
    order changed: str_armour, str_dex_int_armour, default -> str_dex_int_armour, str_armour, default

Generation weights: 2 changed
~ LocalAddedColdDamage1 "Frosted"
    order changed: attack_dagger, dagger, warstaff, staff, sceptre, wand_can_roll_caster_modifiers, default -> dagger, attack_dagger, warstaff, staff, sceptre, wand_can_roll_caster_modifiers, default
~ LocalAddedFireDamageTwoHand1 "Heated"
    dagger: 50 -> 75

Families: 2 changed
~ JunMaster2ArmourAndEnergyShield1 "Upgraded"
    - IncreasedEnergyShield
~ LocalAddedColdDamage1 "Frosted"
    + AddedColdTest

Tags: 1 added, 1 removed, 3 changed
+ base item Metadata/Items/Armours/BodyArmours/BodyInt2 "Test Robe": item_class Body Armour
- base item Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1 "Rusted Sword": item_class One Hand Sword
~ mod ColdResist1 "of the Inuit"
    implicit_tags: + defences
    implicit_tags: - resistance
~ mod LocalAddedFireDamageTwoHand1 "Heated"
    adds_tags: + has_fire_mod
    adds_tags: - has_attack_mod
~ base item Metadata/Items/Weapons/OneHandWeapons/OneHandMaces/Sceptre1 "Driftwood Sceptre"
    tags: + caster_test
    tags: - onehand

Bench options: 1 added, 1 removed, 2 changed
+ Niko, Master of the Depths: add_explicit_mod ColdResist1 ("+(7-12)% to Cold Resistance"); item classes Amulet, Ring; bench_tier 0; cost CurrencyModValues x1
- Einhar, Beastmaster: add_explicit_mod StrMasterItemGenerationCannotChangePrefixes ("Prefixes Cannot Be Changed"); item classes Amulet, Belt, Body Armour, Boots, Bow, Claw, Dagger, Gloves, Helmet, One Hand Axe, One Hand Mace, One Hand Sword, Quiver, Ring, Rune Dagger, Sceptre, Shield, Staff, Thrusting One Hand Sword, Two Hand Axe, Two Hand Mace, Two Hand Sword, Wand, Warstaff; bench_tier 0; cost CurrencyModValues x2
~ Jun, Veiled Master: change_socket_count 2; item classes Body Armour, Boots, Bow, Claw, Dagger, Gloves, Helmet, One Hand Axe, One Hand Mace, One Hand Sword, Rune Dagger, Sceptre, Shield, Staff, Thrusting One Hand Sword, Two Hand Axe, Two Hand Mace, Two Hand Sword, Wand, Warstaff
    cost CurrencyRerollSocketNumbers: 1 -> 2
~ Niko, Master of the Depths: add_explicit_mod JunMaster2ArmourAndEnergyShield1 ("+(105-150) to Armour\n+(11-15) to maximum Energy Shield"); item classes Belt
    bench_tier: 1 -> 2

Essences: 1 added, 1 removed, 2 changed
+ Metadata/Items/Currency/CurrencyEssenceHysteria2 "Essence of Hysteria Two": tier 7, level 8
- Metadata/Items/Currency/CurrencyCorruptMonolith "Remnant of Corruption": tier 0, level 0
~ Metadata/Items/Currency/CurrencyEssenceHatred1 "Whispering Essence of Hatred II"
    name: "Whispering Essence of Hatred" -> "Whispering Essence of Hatred II"
    level: 1 -> 2
    mod for Amulet: ColdDamagePercentEssence1 -> ColdResist1
    + mod for Hybrid: ColdResist1
    - mod for Belt: ColdResist1
~ Metadata/Items/Currency/CurrencyEssenceHysteria1 "Essence of Hysteria"
    tier: 6 -> 7
    is_corruption_only: true -> false
    item_level_restriction: none -> 60
    spawn_level_min: 0 -> 1

Fossils: 1 added, 2 changed
+ Metadata/Items/Currency/CurrencyDelveCraftingTest "Test Fossil"
~ Metadata/Items/Currency/CurrencyDelveCraftingFire "Scorched Fossil"
    changes_quality: false -> true
    forbidden_tags: + lightning
    positive_mod_weights fire: 1000 -> 1500
    negative_mod_weights + lightning: 0
~ Metadata/Items/Currency/CurrencyDelveCraftingGemLevel "Faceted Fossil"
    corrupted_essence_chance: 0 -> 10
    added_mods: - DelveDexterityGemLevel1
    forced_mods: + ColdResist1"""
