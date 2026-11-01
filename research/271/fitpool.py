"""Ticket #271 (a): which reading of the kept tiers' weights (ADR-0042) predicts the mods the sheet saw.

Each craft of the sheet is a draw (or a run of draws) from the pool of our data. The cut keeps the K best tiers of every
mod type (ADR-0040); the readings differ in what the kept tiers weigh. The likelihood of the mods that really came out
is computed exactly under each reading and the readings are compared on it.

Usage (from the repository root, Python 3.12 or later, the pinned game data in CACHE_DIR):
    python research/271/fitpool.py RAW_DIR CACHE_DIR OUT_JSON

RAW_DIR holds foul.csv, alteration_int_body.csv and alteration_str_helm.csv, the three tabs exported by fetch_sheet.py.
Needs numpy (a project dependency) and the project package.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "src"), str(Path(__file__).resolve().parent)]

from crafting_system.data.load import load_game_data  # noqa: E402
from crafting_system.items import Influence, Item, Rarity, tier_table  # noqa: E402
from itemtext import ModLine, parse_item  # noqa: E402
import sheetpool  # noqa: E402
from sheetpool import Mapper, game_pool, read_sheet_csv  # noqa: E402

SINGLE = {"Foulborn Orb of Augmentation", "Foulborn Regal Orb", "Regal Orb", "Exalted Orb"}
MULTI = {"Orb of Alchemy", "Chaos Orb", "Scroll of Wisdom"}
# the readings of ADR-0042 as (gamma, beta): a kept tier weighs  w * (T/K)**gamma * (W_all/W_kept)**beta
READINGS = {"redistribution": (0.0, 1.0), "refactored": (1.0, 0.0), "delete_only": (0.0, 0.0)}
ALTERATION_TABS = {
    # file: (base name, item level used for the pool, label). The tab names say "ilvl 86+ int body" and "ilvl 85+ str helm";
    # the pool depends on the base only through its tags, so any top-tier base of the armour type does.
    "alteration_int_body.csv": ("Vaal Regalia", 86, "Alteration, ilvl 86+ int body armour"),
    "alteration_str_helm.csv": ("Royal Burgonet", 85, "Alteration, ilvl 85+ str helmet"),
}


FOULBORN_BONUS = 150  # twice the +75 of a Foulborn orb, in the doubled integers of ADR-0040
# how a Foulborn orb and the strands combine: "sum" is ADR-0040 (the bonus is added to the denominator); "max_emulator" is
# the beta emulator of Craft of Exile as read in #273 (a Foulborn orb alone keeps ceil(T/2) tiers, with strands the larger
# of that and the strand cut); "max_wiki" takes the larger of the strand cut and the Foulborn cut at 0 strands (D = 175)
KEEP_MODE = "sum"


def keep_count(tiers: int, strands: int, foulborn: bool) -> int:
    """ADR-0040 in integers: K = floor(100 (T-1) / D) + 1 with D = 100 + [s>=1](2.5 s + 47.5) + [Foulborn] 75,
    that is floor(200 (T-1) / (200 + [s>=1](5 s + 95) + [Foulborn] 150)) + 1."""
    strand_part = 5 * strands + 95 if strands >= 1 else 0
    if foulborn and KEEP_MODE != "sum":
        by_strands = 200 * (tiers - 1) // (200 + strand_part) + 1
        by_orb = tiers - tiers // 2 if KEEP_MODE == "max_emulator" else 200 * (tiers - 1) // (200 + FOULBORN_BONUS) + 1
        return max(by_strands, by_orb) if strands >= 1 else by_orb
    denominator = 200 + strand_part + (FOULBORN_BONUS if foulborn else 0)
    return 200 * (tiers - 1) // denominator + 1


def family_of(mod) -> str:
    return mod.families[0]


@dataclass
class Draw:
    """One craft prepared for the likelihood."""

    dataset: str
    currency: str
    strands: int
    foulborn: bool
    capacity: int  # slots per side during the craft
    excluded: frozenset  # families already on the item
    drawn: tuple  # mod ids that came out of the draws
    existing: tuple  # prefixes and suffixes already on the item, which take slots
    candidates: tuple = field(repr=False, default=())
    sheet_totals: dict = field(default_factory=dict)  # mod name -> the sheet's own count of rollable tiers


class View:
    """The pool of one (candidates, strands, Foulborn) under one reading: weights of the kept tiers, by family and side."""

    __slots__ = ("weights", "info", "fam_w", "fam_side", "side_total", "fam_ratio", "fam_rho")

    def __init__(self, candidates, strands, foulborn, gamma, beta, cut=True):
        groups = _groups(candidates)
        self.weights: dict[str, float] = {}
        self.info: dict[str, tuple] = {}
        self.fam_ratio: dict[str, float] = {}
        self.fam_rho: dict[str, float] = {}
        for (mtype, side), group in groups:
            total = len(group)
            keep = keep_count(total, strands, foulborn) if cut else total
            w_all = float(sum(c.weight for c in group))
            w_kept = float(sum(c.weight for c in group[:keep]))
            scale = (total / keep) ** gamma * (w_all / w_kept) ** beta if w_kept > 0 else 0.0
            for c in group:
                self.info[c.mod.id] = (side, family_of(c.mod), mtype, total, keep)
                self.fam_ratio[family_of(c.mod)] = total / keep
                self.fam_rho[family_of(c.mod)] = (total / keep) * (w_kept / w_all) if w_all > 0 else 1.0
            for c in group[:keep]:
                self.weights[c.mod.id] = float(c.weight) * scale
        self.fam_w: dict[str, float] = defaultdict(float)
        self.fam_side: dict[str, str] = {}
        for mod_id, x in self.weights.items():
            side, fam = self.info[mod_id][0], self.info[mod_id][1]
            self.fam_w[fam] += x
            self.fam_side[fam] = side
        self.side_total = {"prefix": 0.0, "suffix": 0.0}
        for fam, x in self.fam_w.items():
            self.side_total[self.fam_side[fam]] += x


_GROUPS: dict[int, tuple] = {}


def _groups(candidates):
    """The candidates grouped by (mod type, side), each group sorted from the highest required level (tier 1) down."""
    found = _GROUPS.get(id(candidates))
    if found is not None and found[0] is candidates:
        return found[1]
    by_type = defaultdict(list)
    for c in candidates:
        by_type[(c.mod.type, c.side)].append(c)
    out = []
    for key, group in by_type.items():
        group.sort(key=lambda c: -c.mod.required_level)
        out.append((key, tuple(group)))
    _GROUPS[id(candidates)] = (candidates, tuple(out))
    return _GROUPS[id(candidates)][1]


_VIEWS: dict[tuple, View] = {}


def view_of(draw: Draw, gamma: float, beta: float, cut: bool = True) -> View:
    key = (id(draw.candidates), draw.strands, draw.foulborn, gamma, beta, cut)
    found = _VIEWS.get(key)
    if found is None:
        if len(_VIEWS) > 20000:
            _VIEWS.clear()
        found = _VIEWS[key] = View(draw.candidates, draw.strands, draw.foulborn, gamma, beta, cut)
    return found


def log_likelihood(view: View, draw: Draw) -> float:
    """log P(the set of mods the craft produced) under the view, for draws without replacement.

    A draw takes a mod in proportion to its weight among the mods whose family is not on the item and whose side has
    room; the family of a drawn mod leaves the pool. The order is unknown, so the probability of the set sums over the
    orders; a recursion over the subsets of the drawn mods does it exactly. Returns -inf for a set the view cannot
    produce (a drawn mod cut away, or a family twice)."""
    drawn = draw.drawn
    n = len(drawn)
    w = [view.weights.get(m, 0.0) for m in drawn]
    if any(x <= 0 for x in w):
        return float("-inf")
    sides = [view.info[m][0] for m in drawn]
    fams = [view.info[m][1] for m in drawn]
    if len(set(fams)) != n:
        return float("-inf")
    excluded_w = {"prefix": 0.0, "suffix": 0.0}
    for fam in draw.excluded:
        if fam in view.fam_w:
            excluded_w[view.fam_side[fam]] += view.fam_w[fam]
    own_w = [view.fam_w[f] for f in fams]
    capacity = draw.capacity
    full = (1 << n) - 1
    prob = [0.0] * (full + 1)
    prob[0] = 1.0
    for mask in range(1, full + 1):
        total = 0.0
        for i in range(n):
            if not mask >> i & 1:
                continue
            prev = mask ^ (1 << i)
            if prob[prev] == 0.0:
                continue
            count = {"prefix": draw.existing[0], "suffix": draw.existing[1]}
            gone = dict(excluded_w)
            for j in range(n):
                if prev >> j & 1:
                    count[sides[j]] += 1
                    gone[sides[j]] += own_w[j]
            if count[sides[i]] >= capacity:
                continue
            denom = sum(view.side_total[s] - gone[s] for s in ("prefix", "suffix") if count[s] < capacity)
            total += prob[prev] * w[i] / denom
        prob[mask] = total
    p = prob[full]
    return math.log(p) if p > 0 else float("-inf")


def first_draw_probabilities(view: View, draw: Draw) -> dict[str, float]:
    """For a craft with one added mod: the chance of each family at that draw."""
    count = {"prefix": draw.existing[0], "suffix": draw.existing[1]}
    out = {}
    denom = 0.0
    for fam, x in view.fam_w.items():
        if fam in draw.excluded or count[view.fam_side[fam]] >= draw.capacity:
            continue
        out[fam] = x
        denom += x
    return {fam: x / denom for fam, x in out.items()}


def build_draws(data, mapper, rows):
    """Turn the rows of the tab "foulborn and misc currency data" into draws; also returns the counts of what was left out.

    One draw per craft: single-mod currencies have one sheet row per craft (the added mod); Alchemy, Chaos and the
    Scroll of Wisdom have one row for each mod of the result, which are grouped by their item texts."""
    dropped = Counter()
    groups: dict[tuple, list] = {}
    order = []
    for index, row in enumerate(rows):
        if not row.get("currency"):
            dropped["blank"] += 1
            continue
        key = (row["currency"], row["item_before"], row["item_after"]) if row["currency"] in MULTI else (index,)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    draws = []
    for key in order:
        members = groups[key]
        row = members[0]
        cur = row["currency"]
        before, after = parse_item(row["item_before"]), parse_item(row["item_after"])
        if before.unidentified and cur != "Scroll of Wisdom":
            dropped["unidentified"] += 1
            continue
        influences = frozenset(Influence(x.lower()) for x in before.influences)
        base_id = mapper.base_for(after)
        if base_id is None:
            dropped["no base"] += 1
            continue
        tiers = tier_table(data, base_id)
        tags = data.base_items[base_id].tags
        ids_before, ids_after = [], []
        ok = True
        for parsed, out in ((before, ids_before), (after, ids_after)):
            for line in parsed.mods:
                mod, _ = mapper.mod_for(line, base_id, tiers, tags)
                if mod is None:
                    ok = False
                    break
                out.append((line.side, mod))
            if not ok:
                break
        if not ok:
            dropped["unmapped mod"] += 1
            continue
        if cur in SINGLE:
            old = {m.id for _, m in ids_before}
            drawn = [m for _, m in ids_after if m.id not in old]
            if len(drawn) != 1 or len(ids_after) != len(ids_before) + 1:
                dropped["not one added mod"] += 1
                continue
            if cur.endswith("Augmentation") and before.rarity != "magic":
                dropped["augmentation not on a magic item"] += 1
                continue
            excluded = frozenset(family_of(m) for _, m in ids_before)
            existing = (sum(1 for sd, _ in ids_before if sd == "prefix"), sum(1 for sd, _ in ids_before if sd == "suffix"))
            capacity = 1 if cur.endswith("Augmentation") else 3
        else:
            if cur == "Orb of Alchemy" and before.rarity != "normal":
                dropped["alchemy on a non-normal item"] += 1
                continue
            drawn = [m for _, m in ids_after]
            excluded, existing, capacity = frozenset(), (0, 0), 3
        if after.item_level != before.item_level or before.item_level is None:
            dropped["item level changed"] += 1
            continue
        try:
            item = Item(base_id=base_id, item_level=before.item_level, rarity=Rarity.RARE, influences=influences)
            candidates = game_pool(data, item)
        except Exception as error:  # an influence the pool does not model
            dropped[f"pool: {type(error).__name__}"] += 1
            continue
        totals = {r["modifier"]: int(r["total_tiers"]) for r in members}
        draws.append(Draw("foulborn tab", cur, before.strands, cur.startswith("Foulborn"), capacity, excluded,
                          tuple(m.id for m in drawn), existing, candidates, totals))
    return draws, dropped


def build_alteration_draws(data, mapper, path, base_name, item_level, label):
    """One Alteration tab: a magic item with one or two mods per row, the strands before and after."""
    base = next(b for b in data.base_items.values() if b.name == base_name and b.domain == "item")
    tiers = tier_table(data, base.id)
    candidates = game_pool(data, Item(base_id=base.id, item_level=item_level, rarity=Rarity.RARE))
    dropped = Counter()
    draws = []
    for row in read_sheet_csv(path):
        start = row.get("Starting Strands", "")
        if not start.strip():
            dropped["blank"] += 1
            continue
        mods = []
        for side, word in (("prefix", "Prefix"), ("suffix", "Suffix")):
            for k in (1, 2, 3):
                name = row.get(f"{word} {k}", "").strip()
                if name:
                    mods.append((side, name, int(float(row[f"{word} {k} Tier"])), int(float(row[f"{word} {k} Total Tiers"]))))
        if not mods:
            dropped["no mods"] += 1
            continue
        ids = []
        for side, name, tier, _ in mods:
            mod, how = mapper.mod_for(ModLine(side, name, tier, ()), base.id, tiers, base.tags)
            if mod is None:
                dropped[f"unmapped mod ({how})"] += 1
                break
            ids.append(mod.id)
        else:
            if len({family_of(data.mods[m]) for m in ids}) != len(ids):
                dropped["family twice"] += 1
                continue
            draws.append(Draw(label, "Orb of Alteration", int(float(start)), False, 1, frozenset(), tuple(ids), (0, 0),
                              candidates, {name: total for _, name, _, total in mods}))
    return draws, dropped


def loglik_vector(draws, gamma, beta, cut=True):
    return np.array([log_likelihood(view_of(d, gamma, beta, cut), d) for d in draws])


def sheet_tier_agreement(data, draws):
    """How often our count of rollable tiers T equals the sheet's own `total_tiers` for the mod that came out."""
    same = differ = 0
    bad_draws = set()
    for k, d in enumerate(draws):
        view = view_of(d, 0.0, 0.0)
        for m in d.drawn:
            theirs = d.sheet_totals.get(data.mods[m].name)
            if theirs is None:
                continue
            if view.info[m][3] == theirs:
                same += 1
            else:
                differ += 1
                bad_draws.add(k)
    return same, differ, bad_draws


def pairwise(a: np.ndarray, b: np.ndarray, seed=271, boots=4000) -> dict:
    """Total log-likelihood difference a - b over the same crafts with its paired standard error and bootstrap interval."""
    d = a - b
    n = len(d)
    rng = np.random.default_rng(seed)
    sums = np.concatenate([d[rng.integers(0, n, size=(100, n))].sum(axis=1) for _ in range(boots // 100)])
    return {
        "delta_loglik": float(d.sum()),
        "se": float(d.std(ddof=1) * math.sqrt(n)),
        "z": float(d.sum() / (d.std(ddof=1) * math.sqrt(n))),
        "boot_2.5": float(np.percentile(sums, 2.5)),
        "boot_97.5": float(np.percentile(sums, 97.5)),
        "crafts_a_better": int((d > 0).sum()),
        "crafts_b_better": int((d < 0).sum()),
    }


def calibration(draws, readings=READINGS):
    """For crafts with one added mod: observed picks against the picks each reading predicts.

    Two groupings of the mod type that was drawn from. By how hard the cut trims it, the ratio T/K of its tier count.
    And by rho = (T/K) / (W_all/W_kept), the factor by which the refactored reading (weight times T/K) weighs the type
    above the redistribution reading (the type keeps its total): where rho > 1 the type loses little weight when its
    low tiers go, and reading 2 predicts it more often than reading 1 does.
    Returns {grouping: {class: {"observed": n, reading: [expected, sd]}}}."""
    groupings = {
        "T/K": ("fam_ratio", [("not trimmed (T/K = 1)", 1.0), ("T/K up to 1.5", 1.5), ("T/K up to 2", 2.0), ("T/K above 2", math.inf)]),
        "rho": ("fam_rho", [("rho up to 0.6", 0.6), ("rho 0.6 to 0.85", 0.85), ("rho 0.85 to 1.15", 1.15), ("rho 1.15 to 1.6", 1.6), ("rho above 1.6", math.inf)]),
    }
    result = {}
    n = 0
    for gname, (attr, classes) in groupings.items():
        def label(value, classes=classes):
            return next(name for name, top in classes if value <= top + 1e-12)

        out = {name: {"observed": 0, **{r: [0.0, 0.0] for r in readings}} for name, _ in classes}
        detail = defaultdict(lambda: {"observed": 0, **{r: 0.0 for r in readings}})  # the families of the lowest class
        lowest = classes[0][0]
        n = 0
        for d in draws:
            if len(d.drawn) != 1:
                continue
            n += 1
            base_view = view_of(d, 0.0, 0.0)
            ratios = getattr(base_view, attr)
            drawn_family = base_view.info[d.drawn[0]][1]
            out[label(ratios[drawn_family])]["observed"] += 1
            if gname == "rho" and label(ratios[drawn_family]) == lowest:
                detail[drawn_family]["observed"] += 1
            for r, (g, b) in readings.items():
                view = view_of(d, g, b)
                probs = first_draw_probabilities(view, d)
                per_class = defaultdict(lambda: [0.0, 0.0])
                for f, p in probs.items():
                    c = label(ratios[f])
                    per_class[c][0] += p
                    per_class[c][1] += p * (1 - p)
                    if gname == "rho" and c == lowest:
                        detail[f][r] += p
                for c, (e, v) in per_class.items():
                    out[c][r][0] += e
                    out[c][r][1] += v
        for c in out:
            for r in readings:
                out[c][r][1] = math.sqrt(out[c][r][1])
        result[gname] = out
        if gname == "rho":
            result["families_of_the_lowest_rho_class"] = {
                f: {k: (round(v, 2) if isinstance(v, float) else v) for k, v in x.items()}
                for f, x in sorted(detail.items(), key=lambda kv: -kv[1]["refactored"])
            }
    return n, result


def profile(draws, kind, values):
    """Total log-likelihood along one parameter: kind 'gamma' (beta = 0) or 'beta' (gamma = 0)."""
    result = {}
    for v in values:
        g, b = (v, 0.0) if kind == "gamma" else (0.0, v)
        result[str(v)] = float(loglik_vector(draws, g, b).sum())
    return result


def interval(draws, kind, centre, step=0.01):
    """The 95% likelihood interval of the parameter (drop of 1.92 in log-likelihood), found by walking out from `centre`."""
    def ll(v):
        g, b = (v, 0.0) if kind == "gamma" else (0.0, v)
        return float(loglik_vector(draws, g, b).sum())

    top = ll(centre)
    ends = []
    for direction in (-1, 1):
        v = centre
        while True:
            nxt = v + direction * step
            if top - ll(nxt) > 1.92:
                break
            v = nxt
            if abs(v - centre) > 2:
                break
        ends.append(round(v, 4))
    return ends


def main() -> None:
    raw, cache, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    data = load_game_data(cache_dir=cache)
    mapper = Mapper(data)
    result: dict = {"game_data_version": data.version, "datasets": {}}
    all_draws: list[Draw] = []
    draws, dropped = build_draws(data, mapper, read_sheet_csv(raw / "foul.csv"))
    sets = {"foulborn and misc currency data": (draws, dropped)}
    for file, (base_name, level, label) in ALTERATION_TABS.items():
        sets[label] = build_alteration_draws(data, mapper, raw / file, base_name, level, label)
    for label, (draws, dropped) in sets.items():
        all_draws += draws
        vectors = {r: loglik_vector(draws, g, b) for r, (g, b) in READINGS.items()}
        vectors["no_cut"] = loglik_vector(draws, 0.0, 0.0, cut=False)
        same, differ, bad = sheet_tier_agreement(data, draws)
        entry = {
            "crafts": len(draws),
            "left_out": dict(dropped),
            "loglik": {r: float(v.sum()) for r, v in vectors.items()},
            "crafts_with_zero_probability": {r: int(np.isinf(v).sum()) for r, v in vectors.items()},
            "our_T_equals_sheet_T": [same, differ],
            "pairs": {
                "refactored - redistribution": pairwise(vectors["refactored"], vectors["redistribution"]),
                "refactored - delete_only": pairwise(vectors["refactored"], vectors["delete_only"]),
                "redistribution - delete_only": pairwise(vectors["redistribution"], vectors["delete_only"]),
            },
        }
        if label == "foulborn and misc currency data":
            by_currency = {}
            for cur in sorted({d.currency for d in draws}):
                sub = [k for k, d in enumerate(draws) if d.currency == cur]
                by_currency[cur] = {"crafts": len(sub), **{r: float(vectors[r][sub].sum()) for r in vectors}}
            entry["by_currency"] = by_currency
        result["datasets"][label] = entry
        print(label, entry["crafts"], entry["loglik"], flush=True)
    vectors = {r: loglik_vector(all_draws, g, b) for r, (g, b) in READINGS.items()}
    result["all_crafts"] = {
        "crafts": len(all_draws),
        "loglik": {r: float(v.sum()) for r, v in vectors.items()},
        "pairs": {
            "refactored - redistribution": pairwise(vectors["refactored"], vectors["redistribution"]),
            "refactored - delete_only": pairwise(vectors["refactored"], vectors["delete_only"]),
        },
    }
    strands = np.array([d.strands + (30 if d.foulborn else 0) for d in all_draws])  # the effective strands of a Foulborn craft
    bands = {}
    for name, lo, hi in (("effective strands 0-19", 0, 19), ("20-49", 20, 49), ("50-79", 50, 79), ("80 and more", 80, 999)):
        sel = (strands >= lo) & (strands <= hi)
        bands[name] = {"crafts": int(sel.sum()), **{r: float(v[sel].sum()) for r, v in vectors.items()}}
    result["by_effective_strand_band"] = bands
    subsets = {
        "crafts with one added mod": [k for k, d in enumerate(all_draws) if len(d.drawn) == 1],
        "crafts with two or more added mods": [k for k, d in enumerate(all_draws) if len(d.drawn) > 1],
        "Foulborn crafts": [k for k, d in enumerate(all_draws) if d.foulborn],
        "crafts that are not Foulborn": [k for k, d in enumerate(all_draws) if not d.foulborn],
    }
    result["subsets"] = {}
    for name, sel in subsets.items():
        sel = np.array(sel)
        result["subsets"][name] = {
            "crafts": int(len(sel)), **{r: float(v[sel].sum()) for r, v in vectors.items()},
            "refactored - redistribution": pairwise(vectors["refactored"][sel], vectors["redistribution"][sel]),
        }
    # the same, on the crafts where our T equals the sheet's T for every mod that came out
    keep = []
    for label, (draws, _) in sets.items():
        _, _, bad = sheet_tier_agreement(data, draws)
        keep += [d for k, d in enumerate(draws) if k not in bad]
    v2 = {r: loglik_vector(keep, g, b) for r, (g, b) in READINGS.items()}
    result["crafts_where_T_agrees"] = {"crafts": len(keep), "loglik": {r: float(v.sum()) for r, v in v2.items()}}
    gammas = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    betas = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5]
    result["profile_gamma_beta0"] = profile(all_draws, "gamma", gammas)
    result["profile_beta_gamma0"] = profile(all_draws, "beta", betas)
    result["gamma_interval_95"] = interval(all_draws, "gamma", 1.0)
    joint = {}
    for g in (0.5, 0.75, 1.0, 1.25):
        for b in (0.0, 0.1, 0.25, 0.5):
            joint[f"{g},{b}"] = float(loglik_vector(all_draws, g, b).sum())
    result["joint_gamma_beta"] = joint
    # the size of the Foulborn bonus (the +75 of ADR-0040 is 150 in doubled integers), on the Foulborn crafts, refactored reading
    global FOULBORN_BONUS
    foul = [d for d in all_draws if d.foulborn]
    bonus = {}
    for value in (0, 50, 100, 125, 145, 150, 152, 175, 200):
        FOULBORN_BONUS = value
        _VIEWS.clear()
        total = float(loglik_vector(foul, 1.0, 0.0).sum())
        bonus[str(value / 2)] = total if math.isfinite(total) else "impossible: an observed craft has probability 0"
    FOULBORN_BONUS = 150
    _VIEWS.clear()
    result["foulborn_bonus_profile"] = {"crafts": len(foul), "loglik_by_bonus_to_the_rating": bonus}
    # a Foulborn orb on an item with strands: the bonus added to the denominator (ADR-0040) or the larger of two cuts
    global KEEP_MODE
    modes = {}
    for mode in ("sum", "max_wiki", "max_emulator"):
        KEEP_MODE = mode
        _VIEWS.clear()
        entry = {}
        for name, subset in (("all 491 Foulborn crafts", foul), ("the 42 with 10 strands or fewer", [d for d in foul if d.strands <= 10])):
            for reading, (g, b) in (("refactored", (1.0, 0.0)), ("delete_only", (0.0, 0.0))):
                v = loglik_vector(subset, g, b)
                entry[f"{name}, {reading}"] = {
                    "impossible_crafts": int(np.isinf(v).sum()),
                    "loglik": float(v.sum()) if np.isfinite(v).all() else "impossible: " + str(int(np.isinf(v).sum())) + " crafts have probability 0",
                    "loglik_of_the_possible_crafts": float(v[np.isfinite(v)].sum()),
                }
        modes[mode] = entry
    KEEP_MODE = "sum"
    _VIEWS.clear()
    result["foulborn_with_strands_sum_or_larger_cut"] = modes
    # the pool as the pinned export has it, with the four Battle Royale mods: our T against the sheet's total_tiers
    sheetpool.EXCLUDE_ROYALE = False
    unfixed, _ = build_draws(data, mapper, read_sheet_csv(raw / "foul.csv"))
    result["foulborn_tab_T_equals_sheet_T_without_leaving_out_the_royale_mods"] = list(sheet_tier_agreement(data, unfixed)[:2])
    sheetpool.EXCLUDE_ROYALE = True
    single = [d for d in all_draws if len(d.drawn) == 1]
    n, table = calibration(single)
    result["calibration_one_added_mod"] = {"crafts": n, "classes": table}
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
