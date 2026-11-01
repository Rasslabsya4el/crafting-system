"""Our Harvest reforge on the owner's locked shield against what the Craft of Exile emulator gave (ticket #198).

The counts below were measured on 2026-11-01 with `tools/coe_emulator/compare.py` (the check
`tools/coe_emulator/checks/197-shield.json`): 1000 Harvest reforges per tag in the emulator, run
headless from its local copy (package.js SHA256 faa6a774...f639). They are our measurement, not
Craft of Exile's code, so they live here; the emulator itself is not needed to run this test.

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there; CI fetches it (ticket #165), so they run there.
"""

import math

import pytest

from crafting_system.actions import HarvestReforge
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table

SHIELD = "Metadata/Items/Armours/Shields/ShieldInt16"  # Titanium Spirit Shield
OLD_MODS = (
    "LocalIncreasedEnergyShieldPercent8",  # T1 % increased Energy Shield, prefix
    "FasterStartEnergyShieldRecharge5_",  # T1 faster start of Energy Shield Recharge, suffix
    "StrIntMasterItemGenerationCanHaveMultipleCraftedMods",  # crafted, suffix
    "StrMasterItemGenerationCannotChangePrefixes",  # crafted, suffix
    "DexMasterItemGenerationCannotChangeSuffixes",  # crafted, prefix
)

# the one new mod of each result, counted over 1000 emulator reforges per tag
EMULATOR = {
    "fire": {
        "FireDamagePrefixOnWeapon1": 157, "FireDamagePrefixOnWeapon2": 159, "FireDamagePrefixOnWeapon3": 183,
        "FireDamagePrefixOnWeapon4": 170, "FireDamagePrefixOnWeapon5_": 178, "FireDamagePrefixOnWeapon6": 50,
        "FireDamagePrefixOnWeapon7_": 14, "FireDamagePrefixOnWeapon8_": 2, "GlobalFireSpellGemsLevel1_": 87,
    },
    "cold": {
        "ColdDamagePrefixOnWeapon1": 171, "ColdDamagePrefixOnWeapon2": 187, "ColdDamagePrefixOnWeapon3_": 165,
        "ColdDamagePrefixOnWeapon4": 157, "ColdDamagePrefixOnWeapon5_": 175, "ColdDamagePrefixOnWeapon6": 47,
        "ColdDamagePrefixOnWeapon7": 16, "ColdDamagePrefixOnWeapon8": 3, "GlobalColdSpellGemsLevel1_": 79,
    },
    "lightning": {
        "LightningDamagePrefixOnWeapon1_": 182, "LightningDamagePrefixOnWeapon2": 164, "LightningDamagePrefixOnWeapon3": 132,
        "LightningDamagePrefixOnWeapon4": 186, "LightningDamagePrefixOnWeapon5": 161, "LightningDamagePrefixOnWeapon6": 50,
        "LightningDamagePrefixOnWeapon7": 15, "LightningDamagePrefixOnWeapon8": 9, "GlobalLightningSpellGemsLevel1": 101,
    },
}  # fmt: skip


@pytest.fixture(scope="module")
def data():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


@pytest.fixture(scope="module")
def shield(data):
    table = tier_table(data, SHIELD)
    mods = []
    for mod_id in OLD_MODS:
        mod = data.mods[mod_id]
        low = tuple(min(stat.min, stat.max) for stat in mod.stats)
        mods.append(ExplicitMod(mod_id, table.get(mod_id, 1), low, crafted=mod.domain == "crafted"))
    return Item.build(data, base_id=SHIELD, item_level=100, rarity=Rarity.RARE, mods=tuple(mods))


@pytest.mark.parametrize("tag", sorted(EMULATOR))
def test_every_old_mod_stays_and_one_new_mod_comes_in_both_systems(data, shield, tag):
    outcomes = HarvestReforge(tag).outcomes(data, shield)
    shown = outcomes.distribution(lambda mod: mod.id)
    assert {mod.mod_id for mod in outcomes.retained.mods} == set(OLD_MODS)
    assert all(sum(count for _, count in outcome) == 1 for outcome in shown)
    ours = {label: chance for outcome, chance in shown.items() for label, _ in outcome}
    assert set(EMULATOR[tag]) <= set(ours), "the emulator gave a mod our system never gives"


@pytest.mark.parametrize("tag", sorted(EMULATOR))
def test_the_new_mod_follows_the_emulator_s_frequencies(data, shield, tag):
    shown = HarvestReforge(tag).outcomes(data, shield).distribution(lambda mod: mod.id)
    ours = {label: float(chance) for outcome, chance in shown.items() for label, _ in outcome}
    counts = EMULATOR[tag]
    total = sum(counts.values())
    assert total == 1000
    for mod_id, chance in ours.items():
        seen = counts.get(mod_id, 0)
        z = (seen / total - chance) / math.sqrt(chance * (1 - chance) / total)
        assert abs(z) < 4, f"{mod_id}: ours {chance:.4f}, emulator {seen}/{total}"
