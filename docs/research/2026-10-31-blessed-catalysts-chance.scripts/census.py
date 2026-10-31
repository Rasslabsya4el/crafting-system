"""Counts behind note 2026-10-31-blessed-catalysts-chance.md (ticket #89).

Usage: python -I census.py <folder with the repoe-fork 3.29.3.3 export>
Reads mods.json and base_items.json only; prints every number the note quotes.
"""
import collections
import json
import math
import sys
from pathlib import Path

folder = Path(sys.argv[1])
mods = json.loads((folder / "mods.json").read_text(encoding="utf8"))
bases = json.loads((folder / "base_items.json").read_text(encoding="utf8"))
JEWELLERY = {"ring", "amulet", "belt"}

CATALYST_TAGS = {  # PoEDB "Catalyst / Tags" table, 2026-10-31
    "Abrasive": {"attack"}, "Accelerating": {"speed"}, "Fertile": {"resource"},
    "Imbued": {"caster"}, "Intrinsic": {"attribute"},
    "Noxious": {"physical_damage", "chaos_damage"}, "Prismatic": {"resistance"},
    "Tempering": {"defences"}, "Turbulent": {"elemental_damage"}, "Unstable": {"critical"},
}
POB_TAGS = {  # Path of Building catalystTags (Item.lua, commit 356bc5c)
    **CATALYST_TAGS,
    "Fertile": {"life", "mana", "resource"},
    "Tempering": {"defences", "armour", "evasion", "energyshield"},
}


def is_affix(mod):
    return mod["domain"] == "item" and mod["generation_type"] in ("prefix", "suffix")


def first_match(mod):
    """Rule A (WRONG, kept to show the difference): the first ring/amulet/belt/default weight decides.

    It stops at `ring 0` and so drops mods that spawn on amulets or belts only (4 records,
    e.g. IncreasedEnergyShield12, AddedPhysicalDamage7..9): 312 instead of 316.
    """
    for weight in mod["spawn_weights"]:
        if weight["tag"] in JEWELLERY | {"default"}:
            return weight["weight"] > 0 and weight["tag"] in JEWELLERY
    return False


def any_positive(mod):
    """Rule B (USED, 316 records): any ring/amulet/belt spawn weight above zero, in any position."""
    return any(w["tag"] in JEWELLERY and w["weight"] > 0 for w in mod["spawn_weights"])


def positive_before_zero_default(mod):
    """Rule C: a ring/amulet/belt weight above zero that comes before a `default` entry."""
    for weight in mod["spawn_weights"]:
        if weight["tag"] in JEWELLERY and weight["weight"] > 0:
            return True
        if weight["tag"] == "default":
            return False
    return False


RULES = {"A first match": first_match, "B any positive": any_positive,
         "C positive before default": positive_before_zero_default}
for name, rule in RULES.items():
    chosen = {k: v for k, v in mods.items() if is_affix(v) and rule(v)}
    groups = {g for v in chosen.values() for g in v["groups"]}
    print(f"\n## rule {name}: {len(chosen)} records, {len(groups)} families")
    for cat, tags in CATALYST_TAGS.items():
        a = {k for k, v in chosen.items() if set(v["implicit_tags"]) & tags}
        b = {k for k, v in chosen.items() if set(v["implicit_tags"]) & POB_TAGS[cat]}
        print(f"  {cat:13s} poedb {len(a):3d} pob {len(b):3d} differ {len(a ^ b)}")
    per_mod = collections.Counter(
        sum(1 for tags in CATALYST_TAGS.values() if set(v["implicit_tags"]) & tags)
        for v in chosen.values())
    print("  catalysts matching per record:", dict(sorted(per_mod.items())))

print("\n## implicit census (released bases of ring/amulet/belt)")
for cls in ("Ring", "Amulet", "Belt"):
    with_imp = ranged = 0
    for b in bases.values():
        if b["release_state"] != "released" or b["item_class"] != cls or not b["implicits"]:
            continue
        with_imp += 1
        if any(i in mods and any(s["min"] != s["max"] for s in mods[i]["stats"])
               for i in b["implicits"]):
            ranged += 1
    print(f"  {cls}: {ranged} of {with_imp} bases have a ranged implicit")

print("\n## stat ids of rule B records and of ring/amulet/belt implicits that look unit-converted")
odd = collections.Counter()
jewellery_implicits = {
    i for b in bases.values()
    if b["release_state"] == "released" and b["item_class"] in ("Ring", "Amulet", "Belt")
    for i in b["implicits"] if i in mods}
for key, v in mods.items():
    if (is_affix(v) and any_positive(v)) or key in jewellery_implicits:
        for st in v["stats"]:
            if any(x in st["id"] for x in
                   ("per_minute", "permyriad", "_per_second", "milliseconds", "regenerat", "_rate", "recoup")):
                odd[st["id"]] += 1
for sid, n in sorted(odd.items()):
    print("  ", sid, n)


def f(ilvl):
    return max(1, min(30 * math.exp(-ilvl / 30) - 0.3, 20))


print("\n## quality per catalyst: ilvl, f, P(+floor), P(+floor+1)")
for ilvl in (60, 70, 75, 80, 84, 86, 90, 95):
    x = f(ilvl)
    print(f"  {ilvl}: f={x:.4f} floor={math.floor(x)} P(floor+1)={x - math.floor(x):.4f}")
