"""Hand-written veiled data for the tests of the veiled orbs, the unveil and the pick (ticket #144, ADR-0026).

The committed fixture data has no veiled or unveiled mods, so this adds a few in the shape of the real records
(`VeiledPrefix` and `VeiledSuffix` with the real stats; unveiled-domain mods that spawn on the fixture amulet with the
weights typed below). Nothing here draws from the code under test: the pool of the amulet is

* prefixes: `VeilTestLife1` (weight 1000) and `VeilTestLife2` (500) of one family, `VeilTestArmour1` (1500),
  `VeilTestMana1` (1000), and `VeilTestZero1` (weight 0: never offered);
* suffixes: `VeilTestSpeed1` (2000), `VeilTestCrit1` (1000) and the hybrid `VeilTestHybrid1` (600, two families:
  the speed family and its own), so that a pick of the hybrid takes the speed mod out too.

`JunMasterVeilTestArmour1` is the crafted version of `VeilTestArmour1` (same side, same stat ids) and `EinharVeilTestArmour1` a
crafted mod of another master with the same stats, which is not a craftable version of a veiled mod.
"""

import dataclasses

from crafting_system.data import Mod, StatRange, Weight

PLACEHOLDER_PREFIX, PLACEHOLDER_SUFFIX = "VeiledPrefix", "VeiledSuffix"
SIGNATURE_PLACEHOLDER = "HakuVeiledPrefix"
LIFE_1, LIFE_2 = "VeilTestLife1", "VeilTestLife2"
ARMOUR, MANA, ZERO = "VeilTestArmour1", "VeilTestMana1", "VeilTestZero1"
SPEED, CRIT, HYBRID = "VeilTestSpeed1", "VeilTestCrit1", "VeilTestHybrid1"
CRAFTED_ARMOUR = "JunMasterVeilTestArmour1"
OTHER_MASTER_ARMOUR = "EinharVeilTestArmour1"
LIFE_WEIGHTS = {LIFE_1: 1000, LIFE_2: 500}
PREFIX_WEIGHTS = {LIFE_1: 1000, LIFE_2: 500, ARMOUR: 1500, MANA: 1000}  # the offerable prefixes of the amulet
SUFFIX_WEIGHTS = {SPEED: 2000, CRIT: 1000, HYBRID: 600}


def _mod(mod_id, generation_type, domain, families, stats, weight=None, text="x") -> Mod:
    weights = () if weight is None else (Weight("amulet", weight), Weight("default", 0))
    return Mod(
        id=mod_id,
        name="",
        text=text if domain != "veiled" else None,
        type=families[0],
        families=tuple(families),
        domain=domain,
        generation_type=generation_type,
        required_level=60 if domain == "unveiled" else 1,
        spawn_weights=weights,
        generation_weights=(),
        adds_tags=(),
        implicit_tags=(),
        stats=tuple(StatRange(*stat) for stat in stats),
        is_essence_only=False,
    )


def veiled_mods() -> dict[str, Mod]:
    """The placeholders (real stats), the unveiled pool of the amulet, and the two crafted look-alikes."""
    seed = ("veiled_mod_seed", 1, 30000)
    mods = [
        _mod(PLACEHOLDER_PREFIX, "prefix", "veiled", ["VeiledPrefix"], [("veiled_mod_type", 1, 1), seed]),
        _mod(PLACEHOLDER_SUFFIX, "suffix", "veiled", ["VeiledSuffix"], [("veiled_mod_type", 2, 2), seed]),
        _mod(SIGNATURE_PLACEHOLDER, "prefix", "veiled", ["VeiledPrefix"], [("veiled_mod_type", 7, 7), seed]),
        _mod(LIFE_1, "prefix", "unveiled", ["VeilTestLife"], [("veil_test_life", 30, 40)], 1000),
        _mod(LIFE_2, "prefix", "unveiled", ["VeilTestLife"], [("veil_test_life", 41, 50)], 500),
        _mod(ARMOUR, "prefix", "unveiled", ["VeilTestArmour"], [("veil_test_armour", 20, 30)], 1500),
        _mod(MANA, "prefix", "unveiled", ["VeilTestMana"], [("veil_test_mana", 20, 30)], 1000),
        _mod(ZERO, "prefix", "unveiled", ["VeilTestZero"], [("veil_test_zero", 1, 2)], 0),
        _mod(SPEED, "suffix", "unveiled", ["VeilTestSpeed"], [("veil_test_speed", 10, 12)], 2000),
        _mod(CRIT, "suffix", "unveiled", ["VeilTestCrit"], [("veil_test_crit", 20, 30)], 1000),
        _mod(HYBRID, "suffix", "unveiled", ["VeilTestSpeed", "VeilTestStr"], [("veil_test_speed2", 5, 6), ("veil_test_str", 5, 6)], 600),
        _mod(CRAFTED_ARMOUR, "prefix", "crafted", ["VeilTestArmour"], [("veil_test_armour", 15, 15)]),
        _mod(OTHER_MASTER_ARMOUR, "prefix", "crafted", ["VeilTestArmourOther"], [("veil_test_armour", 16, 16)]),
    ]
    return {mod.id: dataclasses.replace(mod) for mod in mods}
