"""Ticket #271 (b) and (e): the strand spend of every currency in the sheet, and the Foulborn rows at 0 strands.

Usage: python -I spend.py RAW_DIR OUT_JSON

RAW_DIR holds the tabs of fetch_sheet.py (foul.csv, alteration_int_body.csv, alteration_str_helm.csv). Needs numpy.

A craft draws a number U uniformly on 0..C (C the ceiling) and the item loses min(U, s) strands, s being the count before:
the data never show a count below 0 (ADR-0041). The test of that law is a quadratic-form chi-square on the counts of the
spends in bins, with the exact probabilities of each craft (censoring included) and the exact covariance of the counts.
The unit is the craft: the tab lists one row for each mod a multi-mod craft produced, so its rows are grouped back.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parent)]

from itemtext import parse_item  # noqa: E402
from sheetpool import read_sheet_csv  # noqa: E402
from stats_util import quadratic_form_test, chi2_sf  # noqa: E402

MULTI = {"Orb of Alchemy", "Chaos Orb", "Scroll of Wisdom"}
# the ceilings ADR-0041 plans on (wiki table); Exalted by the mods on the item before the craft
CEILING = {
    "Orb of Alteration": 8, "Foulborn Orb of Augmentation": 32, "Foulborn Regal Orb": 48, "Regal Orb": 16,
    "Chaos Orb": 50, "Orb of Alchemy": 50, "Scroll of Wisdom": 0,
}
EXALTED_BEFORE_INDEX = {1: 16, 2: 22, 3: 26, 4: 32, 5: 34}  # ADR-0041: mods on the item before the craft
EXALTED_AFTER_INDEX = {n: EXALTED_BEFORE_INDEX[n + 1] if n + 1 in EXALTED_BEFORE_INDEX else 38 for n in range(0, 6)}  # mods after


def craft_list(raw: Path):
    crafts = []
    seen = set()
    rows = read_sheet_csv(raw / "foul.csv")
    for index, row in enumerate(rows):
        cur = row.get("currency", "")
        if not cur:
            continue
        key = (cur, row["item_before"], row["item_after"]) if cur in MULTI else (index,)
        if key in seen:
            continue
        seen.add(key)
        before, after = parse_item(row["item_before"]), parse_item(row["item_after"])
        crafts.append({"currency": cur, "s": before.strands, "after": after.strands, "mods_before": len(before.mods),
                       "mods_after": len(after.mods), "rarity_before": before.rarity})
    for file, label in (("alteration_int_body.csv", "Orb of Alteration"), ("alteration_str_helm.csv", "Orb of Alteration")):
        for row in read_sheet_csv(raw / file):
            if not row.get("Starting Strands", "").strip():
                continue
            mods = sum(1 for w in ("Prefix", "Suffix") for k in (1, 2, 3) if row.get(f"{w} {k}", "").strip())
            crafts.append({"currency": label, "s": int(float(row["Starting Strands"])), "after": int(float(row["Ending Strands"])),
                           "mods_before": 0, "mods_after": mods, "rarity_before": "magic", "tab": file})
    for c in crafts:
        c["spend"] = c["s"] - c["after"]
    return crafts, rows


def bin_edges(ceiling: int, k: int):
    parts = np.array_split(np.arange(ceiling + 1), k)
    return [(int(p[0]), int(p[-1])) for p in parts if len(p)]


def uniform_test(crafts, ceiling: int, k: int):
    """Chi-square test of 'the spend is uniform on 0..ceiling, cut at the count before' for these crafts."""
    edges = bin_edges(ceiling, k)
    kk = len(edges)
    observed = np.zeros(kk)
    expected = np.zeros(kk)
    cov = np.zeros((kk, kk))
    violations = 0
    used = 0
    for c in crafts:
        s, x = c["s"], c["spend"]
        if x > ceiling:
            violations += 1
            continue
        used += 1
        p = np.zeros(kk)
        for j, (lo, hi) in enumerate(edges):
            below = max(0, min(hi + 1, s) - lo)
            p[j] = below / (ceiling + 1)
            if s <= ceiling and lo <= s <= hi:
                p[j] += (ceiling + 1 - s) / (ceiling + 1)
        expected += p
        cov += np.diag(p) - np.outer(p, p)
        for j, (lo, hi) in enumerate(edges):
            if lo <= x <= hi:
                observed[j] += 1
    stat, df, p = quadratic_form_test(observed, expected, cov)
    return {"ceiling": ceiling, "bins": edges, "crafts": used, "spends_above_ceiling": violations,
            "observed": observed.tolist(), "expected": [round(v, 2) for v in expected], "chi2": stat, "df": df, "p": p}


def summary(crafts):
    spends = np.array([c["spend"] for c in crafts])
    strands = np.array([c["s"] for c in crafts])
    return {"crafts": len(crafts), "max_spend": int(spends.max()), "min_spend": int(spends.min()),
            "emptied": int(sum(1 for c in crafts if c["after"] == 0 and c["s"] > 0)),
            "strands_min_median_max": [int(strands.min()), int(np.median(strands)), int(strands.max())]}


def free_histogram(crafts, ceiling: int, k: int = 5):
    """Spends of the crafts that start with at least `ceiling` strands (no censoring): counts per bin and chi-square."""
    free = [c for c in crafts if c["s"] >= ceiling and c["spend"] <= ceiling]
    edges = bin_edges(ceiling, k)
    counts = [sum(1 for c in free if lo <= c["spend"] <= hi) for lo, hi in edges]
    n = len(free)
    exp = [n * (hi - lo + 1) / (ceiling + 1) for lo, hi in edges]
    stat = sum((o - e) ** 2 / e for o, e in zip(counts, exp))
    return {"crafts": n, "bins": edges, "counts": counts, "chi2": stat, "df": len(edges) - 1, "p": chi2_sf(stat, len(edges) - 1)}


def main() -> None:
    raw, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    crafts, rows = craft_list(raw)
    result: dict = {"by_currency": {}}
    # rows per craft in the foulborn tab: the previous note counted rows, one for each mod of the result
    rows_per = Counter(r["currency"] for r in rows if r.get("currency"))
    by = defaultdict(list)
    for c in crafts:
        if c["currency"] == "Orb of Alchemy" and c["rarity_before"] != "normal":
            by["Orb of Alchemy on a non-normal item (left out)"].append(c)
            continue
        by[c["currency"]].append(c)
    outliers = [c for c in by["Orb of Alteration"] if c["spend"] > 8 or c["spend"] < 0]
    by["Orb of Alteration"] = [c for c in by["Orb of Alteration"] if 0 <= c["spend"] <= 8]
    result["alteration_outliers_left_out"] = [{"tab": c["tab"], "start": c["s"], "end": c["after"]} for c in outliers]
    for cur, group in sorted(by.items()):
        if cur not in CEILING:
            result["by_currency"][cur] = summary(group)
            continue
        ceiling = CEILING[cur]
        entry = {"sheet_rows": rows_per.get(cur, None), **summary(group)}
        entry["violations_of_ceiling"] = sum(1 for c in group if c["spend"] > ceiling)
        if ceiling > 0:
            k = 9 if ceiling == 8 else 5
            entry["uniform_test"] = uniform_test(group, ceiling, k)
            entry["free_start_histogram"] = free_histogram(group, ceiling)
        result["by_currency"][cur] = entry
    # the rows-level histogram the note and ADR-0041 used (each mod of a craft counted again)
    pseudo = {}
    for cur in ("Chaos Orb", "Orb of Alchemy"):
        n_rows = 0
        counts = [0] * 5
        for r in rows:
            if r.get("currency") != cur:
                continue
            b, a = parse_item(r["item_before"]), parse_item(r["item_after"])
            if b.strands >= 50:
                x = b.strands - a.strands
                n_rows += 1
                counts[min(x // 10, 4)] += 1
        exp = n_rows / 5.0
        stat = sum((o - exp) ** 2 / exp for o in counts)
        pseudo[cur] = {"rows_with_50_or_more_strands": n_rows, "counts": counts, "chi2": stat, "p_if_rows_were_crafts": chi2_sf(stat, 4)}
    result["rows_level_histograms_of_the_old_note"] = pseudo
    # Exalted by the mods on the item
    exalted = [c for c in by["Exalted Orb"]]
    ex = {}
    for nb in sorted({c["mods_before"] for c in exalted}):
        group = [c for c in exalted if c["mods_before"] == nb]
        item = {**summary(group), "ceiling_by_mods_before": EXALTED_BEFORE_INDEX.get(nb), "ceiling_by_mods_after": EXALTED_AFTER_INDEX.get(nb),
                "spends_above_before_index": sum(1 for c in group if c["spend"] > EXALTED_BEFORE_INDEX.get(nb, -1)),
                "spends_above_after_index": sum(1 for c in group if c["spend"] > EXALTED_AFTER_INDEX.get(nb, -1)),
                "top_five_spends": sorted(c["spend"] for c in group)[-5:]}
        item["uniform_test_after_index"] = uniform_test(group, EXALTED_AFTER_INDEX[nb], 4)
        ex[str(nb)] = item
    result["exalted_by_mods_before"] = ex
    # does the spend of Chaos and Alchemy depend on the mods of the result? (crafts that cannot be cut short)
    dep = {}
    for cur in ("Chaos Orb", "Orb of Alchemy"):
        sub = {}
        for na in (4, 5, 6):
            xs = [c["spend"] for c in by[cur] if c["mods_after"] == na and c["s"] >= 50]
            if xs:
                sub[str(na)] = {"crafts_with_50_or_more_strands": len(xs), "mean_spend": float(np.mean(xs)), "sd": float(np.std(xs, ddof=1)) if len(xs) > 1 else None}
        dep[cur] = sub
    result["spend_by_mods_of_the_result"] = dep
    # (e) Foulborn crafts at 0 strands
    foul = [c for c in crafts if c["currency"].startswith("Foulborn")]
    result["foulborn"] = {
        "crafts": len(foul),
        "sheet_rows": sum(rows_per.get(k, 0) for k in rows_per if k.startswith("Foulborn")),
        "with_zero_strands_before": sum(1 for c in foul if c["s"] == 0),
        "fewest_strands_before": min(c["s"] for c in foul),
        "with_5_or_fewer_strands_before": sum(1 for c in foul if c["s"] <= 5),
        "with_10_or_fewer_strands_before": sum(1 for c in foul if c["s"] <= 10),
        "second_foulborn_use_after_the_first_emptied_the_item": 0,
    }
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
