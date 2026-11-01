"""Ticket #175: turn the guide author's sheet tabs into rows of pools and kept mods.

Usage: python -I build_rows.py RAW_DIR MODS_JSON OUT_JSON

RAW_DIR holds the tabs exported as CSV (gloves.csv, misc.csv, discord_wands.csv, temple.csv, wands.csv,
practical.csv, crafted.csv, ring_crafted.csv, infl_chest.csv, highmod.csv, examples.csv). MODS_JSON is the pinned
repoe-fork export (`mods.json`, patch 3.29.3.3). The output is one record per (combine, side): the pooled entries
with their spawn weight, the kept groups and, when the side cannot be used, the reason.

Standard library only, so it runs on any Python 3.10+ with `-I`.
"""
import csv
import json
import re
import sys
from pathlib import Path

ARMOUR_TYPES = ["str_armour", "dex_armour", "int_armour", "str_dex_armour", "str_int_armour", "dex_int_armour"]
CLASS_TAGS = {"gloves": "gloves", "boots": "boots", "helm": "helmet", "wand": "wand"}


class Mods:
    def __init__(self, path):
        raw = json.load(open(path, encoding="utf-8"))
        self.by_group = {}
        for key, mod in raw.items():
            if mod["domain"] != "item" or mod["generation_type"] not in ("prefix", "suffix"):
                continue
            if key.startswith("Hellscape") or mod.get("is_essence_only") or not mod["groups"]:
                continue
            self.by_group.setdefault(mod["groups"][0], []).append((mod["required_level"], key, mod))

    @staticmethod
    def spawn(mod, tags):
        for entry in mod["spawn_weights"]:
            if entry["tag"] in tags:
                return entry["weight"]
        return 0

    def side(self, group):
        return self.by_group[group][0][2]["generation_type"]

    def ladder(self, group, tags):
        rows = [(lvl, self.spawn(mod, tags)) for lvl, _, mod in self.by_group[group]]
        rows = [r for r in rows if r[1] > 0]
        rows.sort(key=lambda r: -r[0])
        return [w for _, w in rows]

    def weight(self, group, tier, cls, typed):
        """(central weight, alternative weight, tier-and-better weight) of tier `tier` (1 = best) of `group` on
        class `cls`; the last is the sum of the weights of tiers 1..tier. `typed` groups hold one ladder per armour
        type; the base type of the author's gloves is not recorded, so the ladder with the largest weight is the
        central reading and the smallest positive one the alternative."""
        base = {CLASS_TAGS[cls], "armour", "default"} if cls != "wand" else {"wand", "weapon", "default"}
        variants = [self.ladder(group, base | {t}) for t in ARMOUR_TYPES] if typed else [self.ladder(group, base)]
        picked = []
        for ladder in variants:
            if not ladder:
                continue
            idx = min((tier - 1) if tier else 0, len(ladder) - 1)
            picked.append((ladder[idx], sum(ladder[: idx + 1])))
        if not picked:
            return None, None, None
        best = max(picked)
        return best[0], min(w for w, _ in picked), best[1]


# stem (lower case, spaces removed, tier stripped) -> (group, typed, ambiguous)
# 'cold', 'fire', 'light', 'rarity' mean a damage mod in a prefix cell and a resistance in a suffix cell.
STEMS = {
    "defflat": ("BaseLocalDefences", True, False), "deflat": ("BaseLocalDefences", True, False),
    "esflat": ("BaseLocalDefences", True, False), "evflat": ("BaseLocalDefences", True, False),
    "arflat": ("BaseLocalDefences", True, False), "ar/esflat": ("BaseLocalDefences", True, False),
    "ar/evflat": ("BaseLocalDefences", True, False),
    "def%": ("DefencesPercent", True, False), "es%": ("DefencesPercent", True, False),
    "ev%": ("DefencesPercent", True, False), "eva%": ("DefencesPercent", True, False),
    "ar%": ("DefencesPercent", True, False), "ar/es%": ("DefencesPercent", True, False),
    "def": ("DefencesPercent", True, True),
    "def%h": ("DefencesPercentAndStunRecovery", True, False), "es%h": ("DefencesPercentAndStunRecovery", True, False),
    "ev%h": ("DefencesPercentAndStunRecovery", True, False),
    "ar/es%h": ("DefencesPercentAndStunRecovery", True, False),
    "ar/ev%h": ("DefencesPercentAndStunRecovery", True, False),
    "life": ("IncreasedLife", False, False), "mana": ("IncreasedMana", True, False),
    "flatphys": ("PhysicalDamage", False, False), "ms": ("MovementVelocity", False, False),
    "flatcold": ("ColdDamage", False, False), "fireflat": ("FireDamage", False, False),
    "lightflat": ("LightningDamage", False, False),
    "codl": ("ColdDamage", False, False),
    "strength": ("Strength", True, False), "str": ("Strength", True, False), "dex": ("Dexterity", False, False),
    "int": ("Intelligence", True, False), "chaos": ("ChaosResistance", False, False),
    "chaosres": ("ChaosResistance", False, False), "coldres": ("ColdResistance", False, False),
    "fireres": ("FireResistance", False, False), "lightres": ("LightningResistance", False, False),
    "acc": ("IncreasedAccuracy", False, False), "atkspd": ("IncreasedAttackSpeed", False, False),
    "esrech": ("EnergyShieldRegeneration", True, False), "recharge": ("EnergyShieldRegeneration", True, False),
    "flatregen": ("LifeRegeneration", False, False), "regenflat": ("LifeRegeneration", False, False),
    "regen": ("LifeRegeneration", False, True), "liferegen": ("LifeRegenerationRate", True, False),
    "lifekill": ("LifeGainedFromEnemyDeath", False, False), "manakill": ("ManaGainedFromEnemyDeath", False, False),
    "lifegain": ("LifeGainPerTarget", False, False), "supp": ("ChanceToSuppressSpells", True, False),
    "lifeleech": ("LifeLeech", False, False), "physleech": ("LifeLeech", False, False),
    "physmanaleech": ("ManaLeech", False, False), "physleechmana": ("ManaLeech", False, False),
}
SIDE_DEPENDENT = {"cold": ("ColdDamage", "ColdResistance"), "fire": ("FireDamage", "FireResistance"),
                  "light": ("LightningDamage", "LightningResistance"),
                  "rarity": ("ItemFoundRarityIncreasePrefix", "ItemFoundRarityIncrease")}
CRAFTED = re.compile(r"craft|\(ess\)|\bess\b|temple|\(inf\)|\(breach\)|aspect|multimod|elreon", re.I)


def parse_cell(text):
    """('stem', tier or None) from a cell like 'def% t3', 'mana 12' or 'chaos t1'."""
    t = re.sub(r"\s+", " ", text.strip().lower())
    t = re.sub(r"\(crafted\)", "craft", t)
    tier = None
    m = re.search(r"\s*t?\s*(\d+)$", t)
    if m and (m.group(0).strip().startswith("t") or " " in m.group(0) or t[: m.start()].endswith(("%", "h"))):
        tier = int(m.group(1))
        t = t[: m.start()]
    return t.replace(" ", ""), tier


def cell_entry(mods, text, col_side, cls, mode):
    """One pool or kept entry. `mode` 'central' or 'low' picks the typed-ladder reading."""
    stem, tier = parse_cell(text)
    entry = {"cell": text.strip(), "col_side": col_side}
    if CRAFTED.search(text):
        entry.update(kind="crafted", group="crafted:" + stem, weight=None)
        return entry
    if stem in SIDE_DEPENDENT:
        group = SIDE_DEPENDENT[stem][0 if col_side == "prefix" else 1]
        typed, ambiguous = False, False
    elif stem in STEMS:
        group, typed, ambiguous = STEMS[stem]
    else:
        entry.update(kind="unmapped", group="unmapped:" + stem, weight=None)
        return entry
    hi, lo, cum = mods.weight(group, tier, cls, typed)
    if hi is None:
        entry.update(kind="unmapped", group=group, weight=None, note="no weight on this class")
        return entry
    entry.update(kind="natural", group=group, side=mods.side(group), tier=tier, typed=typed,
                 ambiguous=ambiguous, weight=hi, weight_low=lo, weight_cum=cum)
    return entry


def read_rows(path):
    return list(csv.reader(open(path, encoding="utf-8")))


def grid_tab(mods, rows, tab, only_classes):
    """The standard layout of the gloves and misc tabs: item 1 in columns 1-6, item 2 in 7-12, the base
    picked in 13, the kept mods in 14-19 and the author's initial/final counts in 20-23."""
    out = []
    for lineno, row in enumerate(rows, start=1):
        if len(row) < 20 or row[0].strip().lower() not in only_classes:
            continue
        cls = row[0].strip().lower()
        cols_side = ["prefix"] * 3 + ["suffix"] * 3

        def cells(lo, hi):
            return [(row[i].strip(), cols_side[(i - lo) % 6]) for i in range(lo, hi) if row[i].strip()]
        pool = cells(1, 7) + cells(7, 13)
        kept = cells(14, 20)
        record = {"tab": tab, "line": lineno, "cls": cls, "base_picked": row[13].strip(),
                  "author_counts": row[20:24] if len(row) >= 24 else []}
        record["pool_cells"] = [c for c, _ in pool]
        record["kept_cells"] = [c for c, _ in kept]
        record["pool"] = [cell_entry(mods, c, s, cls, "central") for c, s in pool]
        record["kept"] = [cell_entry(mods, c, s, cls, "central") for c, s in kept]
        out.append(record)
    return out


def sides_of(record):
    """Split a grid record into its prefix and suffix observations."""
    out = []
    for side in ("prefix", "suffix"):
        pool = [e for e in record["pool"] if e.get("side", e["col_side"]) == side]
        kept = [e for e in record["kept"] if e.get("side", e["col_side"]) == side]
        out.append({"tab": record["tab"], "line": record["line"], "cls": record["cls"], "side": side,
                    "pool": pool, "kept": kept, "author_counts": record["author_counts"],
                    "side_mismatch": any(e["col_side"] != e.get("side", e["col_side"]) for e in record["pool"] + record["kept"]
                                         if e["kind"] == "natural")})
    return out


def classify(side):
    """Reason to drop a side, or None. Order matters: the first reason found is reported."""
    pool, kept = side["pool"], side["kept"]
    if not pool:
        return "empty side"
    if any(e["kind"] == "crafted" for e in pool + kept):
        return "bench-crafted or exclusive mod in the pool (weight unknown, exclusivity rules)"
    if any(e["kind"] == "unmapped" for e in pool + kept):
        return "mod name not resolvable to a game mod"
    if side["side_mismatch"]:
        return "mod sits in the wrong column (data-entry slip)"
    groups = {e["group"] for e in pool}
    if any(e["group"] not in groups for e in kept):
        return "kept mod not in the pool (typo or lost context)"
    if len({e["group"] for e in kept}) != len(kept):
        return "two kept mods of one group"
    if len(groups) <= 1:
        return "one mod group in the pool: no choice"
    ac = side["author_counts"]
    if len(ac) == 4:
        try:
            ini, fin = (int(ac[0]), int(ac[1])) if side["side"] == "prefix" else (int(ac[2]), int(ac[3]))
        except ValueError:
            ini = fin = None
        if ini is not None and (ini != len(pool) or fin != len(kept)):
            return "the author's own counts disagree with the cells"
    if len(kept) == 0:
        return "nothing kept"
    if len(kept) >= len(groups):
        return "everything kept: no information"
    if all(e["weight"] == pool[0]["weight"] for e in pool):
        return "all weights equal in the pool: no information"
    return None


def discord_sides(rows):
    """Rusty's wand data: one prefix on each item, always a '+1 gem level' (250 or 200) and a spell-damage mod of
    unrecorded tier, so its weight is a nuisance parameter. The suffix, when present, is one mod on both items."""
    out = []
    for lineno, row in enumerate(rows, start=1):
        if len(row) < 10 or row[1].strip().lower() not in ("gem 250", "gem 200") or row[3].strip().lower() != "spell":
            continue
        gem_weight = int(row[1].split()[1])
        gem_kept = row[5].strip().lower() == "gem"
        spell_kept = row[6].strip().lower() == "spell"
        n_final = int(row[9])
        out.append({"tab": "discord_wands", "line": lineno, "cls": "wand", "side": "prefix",
                    "pool": [{"cell": row[1].strip(), "kind": "natural", "group": "gem", "weight": gem_weight, "tier": None},
                             {"cell": "Spell", "kind": "nuisance", "group": "spell", "weight": None}],
                    "kept": ([{"cell": "Gem", "group": "gem", "kind": "natural", "weight": gem_weight}] if gem_kept else [])
                    + ([{"cell": "Spell", "group": "spell", "kind": "nuisance", "weight": None}] if spell_kept else []),
                    "n_final_author": n_final})
    return out


EXCLUSIVE = re.compile(r"craft|\(ess\)|\bess\b|temple|\(inf\)|\(breach\)|aspect|multimod|multi craft|elreon|tora|runic|"
                       r"dictator|merciless|haku|\bwed\b|breach|\binf\b", re.I)
OTHER_TABS = {
    "wands": "crafted spell/cold damage mod in every row (weight unknown)",
    "practical": "crafted and exclusive mods (aspect, multimod, Tora, elemental penetration) in every row",
    "crafted": "tests of crafted-mod weights: every row holds bench-crafted mods",
    "ring_crafted": "header: 'ALL MODS HERE ARE CRAFTED' (crafted against crafted, no natural weight)",
    "temple": "Temple mod (influence-like, exclusive) in every row",
    "infl_chest": "breach and influence exclusive mods in every row; the author collects count statistics only",
}


def inventory(raw):
    """Rows of the tabs that are not parsed into pools, with the reason they are out."""
    out = []
    for tab, reason in OTHER_TABS.items():
        rows = read_rows(raw / f"{tab}.csv")
        data = flagged = 0
        for row in rows:
            cells = [c.strip() for c in row[1:] if c.strip() and not c.strip().isdigit()]
            cells = [c for c in cells if not re.match(r"^(P|S)\d?( |$)|\(item|^no\. |^sum |base picked|^item \d|^before|^after|^exclusive|^final", c, re.I)]
            if len(cells) < 3:
                continue
            data += 1
            flagged += bool(any(EXCLUSIVE.search(c) for c in cells))
        out.append({"tab": tab, "rows": data, "rows_with_crafted_or_exclusive_cells": flagged, "reason": reason})
    out.append({"tab": "agg", "rows": 0, "reason": "counts only (final mods per pooled count), no mod names"})
    out.append({"tab": "highmod", "rows": 0, "reason": "counts only (6 to 10 mods pooled), no mod names"})
    out.append({"tab": "examples, noncrafted", "rows": 0, "reason": "notes, no pools"})
    out.append({"tab": "costs (Recomb costs)", "rows": 0, "reason": "the CSV export is empty"})
    return out


def main(raw_dir, mods_json, out_json):
    raw, mods = Path(raw_dir), Mods(mods_json)
    sides, dropped_tabs = [], []
    for tab, classes in (("gloves", {"gloves"}), ("misc", {"gloves", "boots", "helm"})):
        for record in grid_tab(mods, read_rows(raw / f"{tab}.csv"), tab, classes):
            sides.extend(sides_of(record))
    sides.extend(discord_sides(read_rows(raw / "discord_wands.csv")))
    for side in sides:
        side["drop_reason"] = None if side["tab"] == "discord_wands" else classify(side)
        if side["tab"] == "discord_wands":
            if len(side["kept"]) != side["n_final_author"]:
                side["drop_reason"] = "the author's final count disagrees with the cells"
            elif len(side["kept"]) >= 2:
                side["drop_reason"] = "everything kept: no information"
    json.dump({"mods_patch": "3.29.3.3", "sides": sides, "other_tabs": inventory(raw)}, open(out_json, "w", encoding="utf-8"), indent=1)
    kept = [s for s in sides if not s["drop_reason"]]
    print(len(sides), "sides,", len(kept), "usable")


if __name__ == "__main__":
    main(*sys.argv[1:4])
