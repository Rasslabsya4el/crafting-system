"""Player samples of the Heist enchant pools (ticket #100): what the two public Google sheets say about the weights.

Usage: python -I docs/research/2026-10-31-enchantments-samples.py <repoe-fork 3.29.3.3 folder> <data folder>

<data folder> holds the CSV exports of the two sheets (see docs/research/2026-10-31-enchantments-data/README.md):
  curio_summary.csv  "PoE Curio Case Rates", sheet Summary (tracked Heist Curio Display rewards, 3.23-3.28)
  tailoring_tally.csv "PoE Tailoring Orb weights", Sheet1 (a tally of Tailoring Orb clicks, header 330)
Prints: totals, per-tier shares of the 3.29 pool (obsolete rows removed and the rest renormalised), the
"Can have 1 additional Crafted Modifier" rate with a 95% interval, and the tally-vs-Curio comparison.
"""
import csv
import json
import math
import re
import sys

REMOVED_STATS = {
    "local_has_X_white_sockets",
    "local_all_sockets_are_red",
    "local_all_sockets_are_green",
    "local_all_sockets_are_blue",
}


def norm(text):
    """One key for the three spellings: the dump and the tally break lines, the Curio sheet writes '; '."""
    return re.sub(r"\s*;\s*|\s*\n\s*", "|", text.strip())


def read_curio(folder):
    rows = list(csv.reader(open(folder + "/curio_summary.csv", encoding="utf8")))
    out = {"Weapon Enchant": {}, "Armor Enchant": {}}
    seen = {}
    for r in rows:
        if r[0] in out:
            out[r[0]][norm(r[2])] = int(r[3])
        elif r[2] in ("Wings run:", "Items seen:"):
            seen[r[2]] = int(r[3])
        elif r[0] == "Currency" and r[2] in ("Tempering Orb", "Tailoring Orb"):
            seen[r[2]] = int(r[3])
    return out, seen


def read_tally(folder):
    tally = {}
    rows = list(csv.reader(open(folder + "/tailoring_tally.csv", encoding="utf8")))
    header = rows[0]
    for r in rows[1:]:
        text = norm(r[1])
        if not text:
            continue
        try:
            n = int(float(r[2]))
        except ValueError:
            n = 0
        tally[text] = tally.get(text, 0) + n
    return header, tally


def shape(text):
    """Shape of an enchant line pair, for the by-kind table."""
    if "additional Crafted" in text:
        return "extra crafted modifier"
    parts = text.split("|")
    first = parts[0]
    if len(parts) == 1:
        if first.startswith("40% reduced"):
            return "40% reduced attribute requirements"
        if first == "All Sockets Linked":
            return "all sockets linked"
        return "single 8% tag"
    second = parts[1]
    if second.startswith("Has no"):
        return "8% + no colour"
    if second == "All Sockets Linked":
        return "6% + all sockets linked"
    if second.startswith("25% reduced Attribute"):
        return "6% + 25% less attribute requirements"
    if "% increased Explicit" in second and second.startswith("6%"):
        return "6% + 6% two tags"
    if second.startswith("200% increased"):
        return "15% + 200% attribute requirements"
    if second.startswith("-3 to"):
        return "15% + -3 maximum sockets"
    if "reduced Explicit" in second:
        return "10-12% + 25-50% less on another tag"
    return "other"


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


SOCKET_STATS = {
    "local_all_sockets_linked",
    "local_cannot_have_red_sockets",
    "local_cannot_have_green_sockets",
    "local_cannot_have_blue_sockets",
    "local_maximum_sockets_+",
}


def examples(mods, curio):
    """Probability per click of reaching a target set, if the Curio shares are the orb weights."""
    groups = {"Armor Enchant": "EnchantmentHeistArmour", "Weapon Enchant": "EnchantmentHeistWeapon"}
    targets = [
        ("Armor Enchant", "heist_enchantment_life_mod_effect_+%"),
        ("Armor Enchant", "heist_enchantment_resistance_mod_effect_+%"),
        ("Weapon Enchant", "heist_enchantment_physical_mod_effect_+%"),
        ("Weapon Enchant", "heist_enchantment_critical_mod_effect_+%"),
        ("Weapon Enchant", "heist_enchantment_speed_mod_effect_+%"),
        ("Weapon Enchant", "heist_enchantment_caster_damage_mod_effect_+%"),
    ]
    print("\n== example target sets, probability per click from the Curio shares of the 3.29 pool")
    for kind_, stat in targets:
        stat = stat.replace("caster_damage", "casterdamage")
        live = {}
        for v in mods.values():
            if v["groups"] == [groups[kind_]]:
                st = {s["id"]: s["min"] for s in v["stats"]}
                if set(st) & REMOVED_STATS:
                    continue
                live[norm(v["text"])] = st
        total = sum(curio[kind_][t] for t in live)

        def ok(st, clean):
            if st.get(stat, 0) <= 0:
                return False
            down = any(k.startswith("heist_enchantment_") and v < 0 for k, v in st.items())
            down |= st.get("local_attribute_requirements_+%", 0) > 0 or "local_maximum_sockets_+" in st
            if down:
                return False
            return not (clean and set(st) & SOCKET_STATS)

        for clean in (False, True):
            hit = [t for t, st in live.items() if ok(st, clean)]
            p = sum(curio[kind_][t] for t in hit) / total
            print(f"   {kind_:15s} {stat.split('_mod')[0][18:]:14s} {'clean' if clean else 'any  '} {len(hit):3d} enchants  p={100 * p:5.2f}%  expected orbs {1 / p:6.1f}")


def pool_texts(mods):
    """Current pool by stat, text normalised like the sheets (the dump uses \\n between lines)."""
    pools = {}
    for name, group in (("Weapon Enchant", "EnchantmentHeistWeapon"), ("Armor Enchant", "EnchantmentHeistArmour")):
        keep = {}
        for v in mods.values():
            if v["groups"] == [group] and not ({s["id"] for s in v["stats"]} & REMOVED_STATS):
                keep[norm(v["text"])] = v["required_level"]
        pools[name] = keep
    return pools


def main(dump, data):
    mods = json.load(open(dump + "/mods.json", encoding="utf8"))
    pools = pool_texts(mods)
    curio, seen = read_curio(data)
    print("Curio sheet: wings", seen["Wings run:"], "items", seen["Items seen:"], "orbs seen", seen["Tempering Orb"], seen["Tailoring Orb"])
    for kind in ("Weapon Enchant", "Armor Enchant"):
        counts = curio[kind]
        total = sum(counts.values())
        live = {t: c for t, c in counts.items() if t in pools[kind]}
        missing = [t for t in pools[kind] if t not in counts]
        live_total = sum(live.values())
        print(f"\n== {kind}: sheet total {total}, rows {len(counts)}; in the 3.29 pool {len(live)} rows with {live_total} items; pool texts missing in sheet: {len(missing)}")
        crafted = [t for t in counts if "additional Crafted" in t][0]
        k = counts[crafted]
        lo, hi = wilson(k, total)
        print(f"   'Can have 1 additional Crafted Modifier': {k} of {total} = {100 * k / total:.2f}% (95% {100 * lo:.2f}-{100 * hi:.2f}%), 1 in {total / k:.0f}; of the 3.29 pool {100 * k / live_total:.2f}%")
        ordered = sorted(live.items(), key=lambda x: -x[1])
        print("   top 3.29-pool enchants (count, share of 3.29 pool, required level):")
        for t, c in ordered[:12]:
            print(f"     {c:5d} {100 * c / live_total:6.2f}%  L{pools[kind][t]:<3d} {t}")
        by_level = {}
        for t, c in live.items():
            lv = pools[kind][t]
            n, s = by_level.get(lv, (0, 0))
            by_level[lv] = (n + 1, s + c)
        print("   by required level: level: enchants, share of pool, mean count per enchant")
        for lv in sorted(by_level):
            n, s = by_level[lv]
            print(f"     L{lv:<3d} {n:3d} enchants  {100 * s / live_total:6.2f}%  {s / n:7.1f} each")
        kinds = {}
        for t, c in live.items():
            n, sm = kinds.get(shape(t), (0, 0))
            kinds[shape(t)] = (n + 1, sm + c)
        print("   by kind (3.29 pool): kind: enchants, share of pool, mean count each")
        for kd, (n, sm) in sorted(kinds.items(), key=lambda x: -x[1][1] / x[1][0]):
            print(f"     {kd:40s} {n:3d}  {100 * sm / live_total:6.2f}%  {sm / n:7.1f}")
        singles = {t: c for t, c in live.items() if "|" not in t}
        print("   enchants with no rider (single line):", len(singles), "holding", f"{100 * sum(singles.values()) / live_total:.1f}% of the pool")
        mean = live_total / len(live)
        chi = sum((c - mean) ** 2 / mean for c in live.values())
        print(f"   chi-square against a uniform pool of {len(live)}: {chi:,.0f} (df {len(live) - 1})")
    examples(mods, curio)
    header, tally = read_tally(data)
    ctal = {t: c for t, c in curio["Armor Enchant"].items()}
    print("\n== Tailoring tally sheet: header", header[2], "clicks; rows", len(tally), "sum of rows", sum(tally.values()))
    common = [t for t in tally if t in ctal]
    print("   rows found in the Curio armour list:", len(common), "of", len(tally))
    in_tally = {t: tally[t] for t in common}
    n = sum(in_tally.values())
    ct = sum(ctal[t] for t in common)
    chi = 0.0
    df = -1
    small_o = small_e = 0.0
    for t in common:
        e = n * ctal[t] / ct
        o = in_tally[t]
        if e >= 5:
            chi += (o - e) ** 2 / e
            df += 1
        else:
            small_o += o
            small_e += e
    if small_e > 0:
        chi += (small_o - small_e) ** 2 / small_e
        df += 1
    print(f"   chi-square of the tally against Curio shares, restricted to the {len(common)} common rows (n={n}): {chi:.1f}, df {df}")
    missing_big = sorted(((c, t) for t, c in ctal.items() if t not in tally), reverse=True)[:6]
    print("   largest Curio armour rows absent from the tally sheet:", [(c, t) for c, t in missing_big])
    absent = sum(c for t, c in ctal.items() if t not in tally) / sum(ctal.values())
    print(f"   share of Curio armour items on rows absent from the tally: {100 * absent:.1f}%")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
