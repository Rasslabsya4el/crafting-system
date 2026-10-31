"""Reproduces the repoe-fork 3.29.3.3 numbers of docs/research/2026-10-31-influence.md (ticket #86).

Usage: python -I docs/research/2026-10-31-influence-repoe.py <dir with mods.json>
Read-only; prints tables to stdout.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

INF = ["shaper", "elder", "crusader", "basilisk", "eyrie", "adjudicator"]  # basilisk=Hunter, eyrie=Redeemer, adjudicator=Warlord
mods = json.loads((Path(sys.argv[1]) / "mods.json").read_text(encoding="utf8"))


def is_item_affix(v):
    return v["domain"] == "item" and v["generation_type"] in ("prefix", "suffix")


def inf_tags(v, positive_only=False):
    out = []
    for s in v["spawn_weights"]:
        if "_" in s["tag"]:
            cls, inf = s["tag"].rsplit("_", 1)
            if inf in INF and (s["weight"] > 0 or not positive_only):
                out.append((cls, inf, s["weight"]))
    return out


elevated = {k: v for k, v in mods.items() if is_item_affix(v) and "Elevated" in (v["name"] or "")}
regular = {k: v for k, v in mods.items() if is_item_affix(v) and inf_tags(v) and k not in elevated}
print("elevated mods:", len(elevated), "all weights 0:", all(w == 0 for v in elevated.values() for _, _, w in inf_tags(v)))
print("regular influence mods:", len(regular), "with a positive weight:", sum(1 for v in regular.values() if inf_tags(v, True)))
print("min required_level of a positive-weight influence mod:",
      min(v["required_level"] for v in regular.values() if inf_tags(v, True)))

# pool entries per (class, influence): a mod record is one tier
rows = defaultdict(lambda: {"prefix": [0, 0], "suffix": [0, 0]})
for v in regular.values():
    for cls, inf, w in inf_tags(v, True):
        r = rows[(cls, inf)][v["generation_type"]]
        r[0] += 1
        r[1] += w
classes = sorted({c for c, _ in rows})
print("class x influence pairs:", len(rows), "classes:", len(classes), "pairs with an empty side:",
      sum(1 for r in rows.values() if r["prefix"][0] == 0 or r["suffix"][0] == 0))
print("class".ljust(12), *[i.ljust(13) for i in INF])
for c in classes:
    print(c.ljust(12), *[f"{rows[(c, i)]['prefix'][0]}p/{rows[(c, i)]['suffix'][0]}s".ljust(13) for i in INF])


def pool(cls, inf, ilvl):
    """Entries and total weight per side at an item level (family exclusion and slot limits not applied)."""
    out = {"prefix": [0, 0], "suffix": [0, 0]}
    for v in regular.values():
        if v["required_level"] > ilvl:
            continue
        for cls2, inf2, w in inf_tags(v, True):
            if (cls2, inf2) == (cls, inf):
                out[v["generation_type"]][0] += 1
                out[v["generation_type"]][1] += w
    return out


for c, i, l in [("helmet", "shaper", 100), ("belt", "basilisk", 75), ("belt", "elder", 75), ("bow", "basilisk", 78),
                ("shield", "shaper", 100), ("body_armour", "elder", 100)]:
    print("pool", c, i, l, pool(c, i, l))

# elevated -> top regular tier by name stem
by_stem = defaultdict(list)
for k, v in regular.items():
    stem = re.sub(r"\d+$", "", re.sub(r"_+$", "", k))
    by_stem[stem].append(k)
res = Counter()
for k, v in elevated.items():
    stem = re.sub(r"_+$", "", k.replace("Maven", ""))
    cands = [x for x in by_stem.get(stem, []) if {i for _, i, _ in inf_tags(regular[x])} == {i for _, i, _ in inf_tags(v)}]
    if not cands:
        res["no stem match"] += 1
        continue
    top = max(cands, key=lambda x: regular[x]["required_level"])
    res["top tier has weight" if inf_tags(regular[top], True) else "top tier weight 0"] += 1
print("elevated -> top tier by name stem:", dict(res))
print("elevated mods per tag class:", Counter(c for v in elevated.values() for c, _, _ in inf_tags(v)))
