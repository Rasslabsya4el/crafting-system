"""Rebuild the small repoe-fork excerpts next to this file from a full dump (ADR-0003).

Usage: python -I make_excerpts.py <folder with the five pinned dumps> [<output folder>]

The output folder defaults to the folder of this script. Records are copied verbatim (keys and
their order untouched); only the choice of records is made here. A record the excerpt names
pulls in every mod it references, so the excerpt is closed: all mod ids resolve inside it.
The bench options are picked by their position in the pinned 3.29.3.3 file.

This file is a script, not a test: pytest does not collect it (its name has no `test_` prefix).
"""

import json
import sys
from pathlib import Path

MODS = (
    "LocalAddedFireDamageTwoHand1",
    "LocalIncreasedEnergyShield1",
    "JunMaster2ArmourAndEnergyShield1",
    "FireDamagePrefixOnWeapon1",
    "SpellDamageOnWeapon1",
    "LocalIncreasedPhysicalDamageReductionRating1",
    "IncreasedEnergyShield1",
    # the item model (#18): a rare of 3 prefixes and 3 suffixes, a two-tier family, the five metamods
    "IncreasedLife1",
    "LifeRegeneration1",
    "LightningResist1",
    "LightningResist2",  # same family as LightningResist1
    "GlobalLightningGemLevel1",
    "DexMasterItemGenerationCannotChangeSuffixes",
    "IntMasterItemGenerationCannotRollAttackAffixes",
    "StrDexMasterItemGenerationCannotRollCasterAffixes",
    "StrIntMasterItemGenerationCanHaveMultipleCraftedMods",
    # the R12 actions (#23): every amulet mod with the tag lightning (23 mods, 14,950 weight from
    # item level 84), the gem-level siblings that share the family of GlobalLightningGemLevel1,
    # and a few more complete families (prefixes and suffixes, one with generation weights)
    "AddedLightningDamage1",
    "AddedLightningDamage2",
    "AddedLightningDamage3",
    "AddedLightningDamage4",
    "AddedLightningDamage5",
    "AddedLightningDamage6",
    "AddedLightningDamage7",
    "AddedLightningDamage8",
    "AddedLightningDamage9",
    "LightningResist3",
    "LightningResist4",
    "LightningResist5",
    "LightningResist6",
    "LightningResist7",
    "LightningResist8",
    "LightningDamagePercent1",
    "LightningDamagePercent2",
    "LightningDamagePercent3",
    "LightningDamagePercent4",
    "LightningDamagePercent5",
    "GlobalFireGemLevel1_",
    "GlobalColdGemLevel1__",
    "GlobalPhysicalGemLevel1_",
    "GlobalChaosGemLevel1",
    "GlobalSkillGemLevel1",
    "ItemFoundRarityIncreasePrefix1",
    "ItemFoundRarityIncreasePrefix2",
    "ItemFoundRarityIncreasePrefix3",
    "ItemFoundRarityIncreasePrefix4_",
    "ChaosResist1",
    "ChaosResist2",
    "ChaosResist3",
    "ChaosResist4",
    "ChaosResist5",
    "ChaosResist6",
    "LifeLeechPermyriadSuffix1",
    "LifeLeechPermyriadSuffix2",
    "LifeLeechPermyriadSuffix3",
    "ManaLeechPermyriadSuffix1",
    "ManaLeechPermyriadSuffix2",
)
BASE_ITEMS = (
    "Metadata/Items/Armours/BodyArmours/BodyInt1",
    "Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1",  # has an implicit
    "Metadata/Items/Weapons/OneHandWeapons/OneHandMaces/Sceptre1",  # repeats the tag `sceptre`
    "Metadata/Items/Amulets/Amulet1",  # an amulet: a base with mods of its own on the item model
)
FOSSILS = (
    "Metadata/Items/Currency/CurrencyDelveCraftingFire",  # Scorched
    "Metadata/Items/Currency/CurrencyDelveCraftingGemLevel",  # Faceted, has added mods
)
ESSENCES = (
    "Metadata/Items/Currency/CurrencyEssenceHatred1",
    "Metadata/Items/Currency/CurrencyEssenceHysteria1",  # corruption only
    "Metadata/Items/Currency/CurrencyCorruptMonolith",  # no mod for any item class
)
# positions in crafting_bench_options.json: a socket count, a link, a colour, remove crafted
# mods, an enchant with two costs, the Niko belt option for JunMaster2ArmourAndEnergyShield1,
# a rarity reroll, a rare reroll, an Einhar explicit mod
BENCH_OPTIONS = (0, 5, 10, 20, 294, 527, 753, 754, 760)


def read(folder: Path, name: str):
    return json.loads((folder / name).read_bytes().decode("utf-8"))


def write(folder: Path, name: str, data) -> None:
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    (folder / name).write_bytes(text.encode("utf-8"))


def referenced_mods(bases, fossils, essences, options) -> list[str]:
    ids = list(MODS)
    for record in bases:
        ids += record["implicits"]
    for record in fossils:
        ids += record["added_mods"] + record["forced_mods"]
    for record in essences:
        ids += [mod for mod in record["mods"].values() if mod is not None]
    for record in options:
        actions = record["actions"]
        ids += [actions[key] for key in ("add_explicit_mod", "add_enchant_mod") if actions[key]]
    return ids


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__, file=sys.stderr)
        return 2
    source = Path(argv[0])
    target = Path(argv[1]) if len(argv) == 2 else Path(__file__).parent

    raw_mods = read(source, "mods.json")
    raw_bases = read(source, "base_items.json")
    raw_fossils = read(source, "fossils.json")
    raw_essences = read(source, "essences.json")
    raw_options = read(source, "crafting_bench_options.json")

    bases = {key: raw_bases[key] for key in BASE_ITEMS}
    fossils = {key: raw_fossils[key] for key in FOSSILS}
    essences = {key: raw_essences[key] for key in ESSENCES}
    options = [raw_options[index] for index in BENCH_OPTIONS]

    wanted = set(
        referenced_mods(bases.values(), fossils.values(), essences.values(), options)
    )
    mods = {key: record for key, record in raw_mods.items() if key in wanted}  # file order
    missing = wanted - set(mods)
    if missing:
        print(f"mods missing from the dump: {sorted(missing)}", file=sys.stderr)
        return 1

    target.mkdir(parents=True, exist_ok=True)
    write(target, "mods.json", mods)
    write(target, "base_items.json", bases)
    write(target, "fossils.json", fossils)
    write(target, "essences.json", essences)
    write(target, "crafting_bench_options.json", options)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
