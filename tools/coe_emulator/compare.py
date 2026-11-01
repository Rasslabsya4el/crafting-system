"""The debug loop of ticket #198: ask our system first, then the Craft of Exile emulator, side by side.

    uv run --with playwright==1.58.0 python tools/coe_emulator/compare.py checks.json [--out report.json]

A check is written in our terms, from our system's knowledge:

    {"id": "197-shield-fire",
     "base": "Metadata/Items/Armours/Shields/ShieldInt16", "item_level": 100, "quality": 20,
     "rarity": "rare", "influences": [], "mods": ["LocalIncreasedEnergyShieldPercent8", ...],
     "fractured": ["..."],                     # mod ids among `mods` that are fractured
     "actions": ["Harvest Reforge Fire"],      # labels of our catalog; "*" for every catalog action the emulator has
     "donor": {...same fields, for an Awakener's Orb...},
     "repeats": 1000, "label": "mod"}

For each check: our item is built (`Item.build`, so our item rules check it), our catalog lists
the actions with their verdict (`outcomes` or its refusal), each asked action is translated to the
emulator's button (`coe_craft`, None when the emulator has none) and run `repeats` times on the
same item built in the emulator from the same mods (`coe_mod`: side, required level, value ranges and
mod group must agree). The report puts per action: our verdict and the code place it comes from,
the emulator's verdict and counts, and for a draw either the whole distribution of the finished
item (exact, when the action adds at most one mod or has fixed results) or, for a draw of several
mods, the frequency of each mod and of each shape (prefixes, suffixes) in a seeded sample of
20,000 of our own outcomes, with a z-score.
A row with |z| > 4, a CoE mod that maps to none of ours, or a verdict that differs is a *candidate*:
it is a finding only after the code place is confirmed by reading it.
"""

import argparse
import difflib
import inspect
import json
import math
import random
import re
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from emulator import Emulator, default_copy  # noqa: E402

from crafting_system import actions  # noqa: E402,F401  (registers every kind)
from crafting_system.actions.catalog import catalog  # noqa: E402
from crafting_system.actions.contract import Fixed  # noqa: E402
from crafting_system.actions.errors import NotApplicableError, OutOfScopeError  # noqa: E402
from crafting_system.data import load_game_data  # noqa: E402
from crafting_system.items import ExplicitMod, Influence, Item, Rarity, tier_table  # noqa: E402

TIER_WORDS = ("Whispering", "Muttering", "Weeping", "Wailing", "Screaming", "Shrieking", "Deafening")
CURRENCY = {
    "ChaosOrb": {"currency": "chaos"},
    "ExaltedOrb": {"currency": "exalted", "subaction": "normal"},
    "AnnulmentOrb": {"currency": "annul"},
    "ScouringOrb": {"currency": "scour"},
    "FracturingOrb": {"currency": "fracturing"},
    "TransmutationOrb": {"currency": "transmute"},
    "AlterationOrb": {"currency": "alteration"},
    "AugmentationOrb": {"currency": "augmentation", "subaction": "normal"},
    "RegalOrb": {"currency": "regal", "subaction": "normal"},
    "AlchemyOrb": {"currency": "alchemy"},
    "DivineOrb": {"currency": "divine"},
}
NOT_IN_EMULATOR = {
    "RemoveCraftedMods": "the emulator has no Remove Crafted Mods button (a bench mod is removed by clicking it)",
    "HarvestDamageSwap": "the emulator's Harvest menu has no damage swap",
    "WildBristleMatron": "the emulator has no Wild Bristle Matron",
    "TalismanFracture": "the emulator has no talisman fracture",
}
OUR_SAMPLES = 20000
INFLUENCE_GROUP = {"2": "shaper", "3": "elder", "4": "crusader", "5": "hunter", "6": "warlord", "7": "redeemer"}


class Coe:
    """Craft of Exile's data (poecd) and the correspondence of its mods with ours."""

    def __init__(self, copy: Path, data) -> None:
        text = (copy / "json" / "data" / "main" / "poec_data.json").read_text(encoding="utf-8")
        self.d = json.loads(text[text.index("{") :].rstrip().rstrip(";"))
        self.data = data
        self.modifiers = {m["id_modifier"]: m for m in self.d["modifiers"]["seq"]}
        self.mtypes = {m["name_mtype"].lower(): m["id_mtype"] for m in self.d["mtypes"]["seq"] if m.get("harvest") == "1"}
        self.fossils = {m["name_fossil"]: m["id_fossil"] for m in self.d["fossils"]["seq"]}
        self._coe_indexes: dict[str, list[dict]] = {}
        self._ours: list[dict] | None = None

    def bitem(self, base_id: str) -> str:
        name = self.data.base_items[base_id].name
        found = [b["id_bitem"] for b in self.d["bitems"]["seq"] if b["name_bitem"] == name and b.get("is_legacy") == "0"]
        if len(found) != 1:
            raise ValueError(f"no single Craft of Exile item named {name}")
        return found[0]

    def base_of(self, bitem: str) -> str:
        return self.d["bitems"]["seq"][self.d["bitems"]["ind"][bitem]]["id_base"]

    @staticmethod
    def _spans(ranges) -> tuple:
        spans = tuple((r, r) if isinstance(r, (int, float)) else tuple(r) for r in ranges)
        spans = tuple(span for span in spans if span != (0, 0))  # a dummy display stat of the data
        return () if all(span == (1, 1) for span in spans) else spans  # a metamod: CoE gives it no values

    def _keys(self, crafted: bool, side: str, level, ranges, groups, text: str) -> tuple:
        """The keys a mod is matched by, strictest first: (level, values, group), (values, group) for a crafted
        mod's bench level, and (level, group, stat text) for values in other units (life regeneration per minute)."""
        spans, groups = self._spans(ranges), tuple(sorted(groups))
        return ((crafted, side, int(level), spans, groups), (crafted, side, spans, groups), (crafted, side, int(level), groups, text))

    def _our_keys(self, mod) -> tuple:
        return self._keys(mod.domain == "crafted", mod.generation_type, mod.required_level,
                          [[s.min, s.max] for s in mod.stats], mod.families, mod_text(mod))

    def _coe_keys(self, coe_base: str, aid: str, index: int) -> tuple:
        modifier = self.modifiers[aid]
        tier = self.d["tiers"][aid][coe_base][index]
        return self._keys(modifier["id_mgroup"] == "11", modifier["affix"], tier["ilvl"], json.loads(tier["nvalues"]),
                          json.loads(modifier["modgroups"]), modifier["name_modifier"])

    def _coe_index(self, coe_base: str) -> list[dict]:
        if coe_base not in self._coe_indexes:
            index = [{}, {}, {}]
            for aid in map(str, self.d["basemods"].get(coe_base, [])):
                if aid not in self.modifiers or self.modifiers[aid]["affix"] not in ("prefix", "suffix"):
                    continue
                for tindex in range(len(self.d["tiers"].get(aid, {}).get(coe_base, []))):
                    for level, key in enumerate(self._coe_keys(coe_base, aid, tindex)):
                        index[level].setdefault(key, []).append((aid, tindex))
            self._coe_indexes[coe_base] = index
        return self._coe_indexes[coe_base]

    def _our_index(self) -> list[dict]:
        if self._ours is None:
            self._ours = [{}, {}, {}]
            for mod in self.data.mods.values():
                if mod.generation_type in ("prefix", "suffix"):
                    for level, key in enumerate(self._our_keys(mod)):
                        self._ours[level].setdefault(key, []).append(mod.id)
        return self._ours

    def coe_mod(self, coe_base: str, mod_id: str, among: set[str] | None = None) -> tuple[str, int]:
        """The (aid, tindex) of our mod on a CoE base (an aid of `among` when several fit)."""
        mod = self.data.mods[mod_id]
        for index, key in zip(self._coe_index(coe_base), self._our_keys(mod)):
            hits = sorted(set(index.get(key, [])))
            if among is not None and len(hits) > 1:
                hits = [hit for hit in hits if hit[0] in among] or hits
            if len(hits) > 1:
                hits = [hit for hit in hits if self.modifiers[hit[0]]["name_modifier"] == mod_text(mod)] or hits
            if len(hits) > 1:
                hits = [hit for hit in hits if self.modifiers[hit[0]]["id_mgroup"] == "1"] or hits  # not an essence's twin
            if len(hits) == 1:
                return hits[0]
            if hits:
                raise ValueError(f"{mod_id}: {len(hits)} Craft of Exile tiers fit on base {coe_base}: {hits[:5]}")
        raise ValueError(f"{mod_id}: no Craft of Exile tier fits on base {coe_base}")

    def our_mod(self, coe_base: str, entry: dict, pool=None) -> str:
        """Our mod id of a CoE result mod (preferring `pool`, the ids our item can roll); 'coe:aid:tindex' when none fits."""
        if entry["tindex"] == "e" or entry["aid"] in ("-1", "0"):
            return f"coe:{entry['aid']}:{entry['tindex']}"
        name = self.modifiers[entry["aid"]]["name_modifier"]
        for index, key in zip(self._our_index(), self._coe_keys(coe_base, entry["aid"], int(entry["tindex"]))):
            hits = index.get(key, [])
            if pool is not None and len(hits) > 1:
                hits = [h for h in hits if h in pool] or hits
            if len(hits) > 1:  # one mod group, same tiers (Fire, Cold, Spell damage): the stat text tells them apart
                hits = [h for h in hits if mod_text(self.data.mods[h]) == name] or hits
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                return f"coe:{entry['aid']}:{entry['tindex']}?{'|'.join(hits[:3])}"
        return f"coe:{entry['aid']}:{entry['tindex']}"

    def item_spec(self, item: Item, fractured: set[str]) -> dict:
        bitem = self.bitem(item.base_id)
        base = self.base_of(bitem)
        mods = []
        for entry in item.mods:
            aid, tindex = self.coe_mod(base, entry.mod_id)
            mods.append({"aid": aid, "tindex": tindex, "bench": int(entry.crafted), "frac": int(entry.mod_id in fractured)})
        spec = {"bitem": bitem, "ilvl": item.item_level, "rarity": item.rarity.value, "mods": mods,
                "influences": sorted(i.value for i in item.influences)}
        if item.quality is not None:
            spec["quality"] = item.quality.value
        if item.corrupted:
            spec["corrupted"] = 1
        return spec

    def craft(self, action, item: Item, outcomes) -> tuple[dict | None, str]:
        """The emulator's button for our action, or None and why."""
        name = type(action).__name__
        if name in CURRENCY:
            return dict(CURRENCY[name]), ""
        if name in NOT_IN_EMULATOR:
            return None, NOT_IN_EMULATOR[name]
        if name == "HarvestReforge":
            tag = "defences" if action.tag == "defence" else action.tag
            return {"action": "harvest", "subaction": "hreroll", "ssaction": self.mtypes[tag]}, ""
        if name == "HarvestReforgeInfluence":
            return {"action": "harvest", "subaction": "hreroll", "ssaction": "inf"}, ""
        if name == "HarvestReforgeLikelihood":
            return {"action": "harvest", "subaction": "hother", "ssaction": "rfmlk" if action.more else "rfllk"}, ""
        if name == "HarvestAddRemove":
            tag = {"defence": "defences"}.get(action.craft, action.craft)
            code = "inf" if tag == "influence" else self.mtypes.get(tag)
            return ({"action": "harvest", "subaction": "haugment", "ssaction": code}, "") if code else (None, f"no CoE tag {tag}")
        if name == "HarvestResistanceSwap":
            return {"action": "harvest", "subaction": "hresist", "ssaction": f"hr{action.source[0]}t{action.target[0]}"}, ""
        if name == "BeastSideSwap":
            return {"action": "beast_crafting", "subaction": "suftopre" if action.add_side.value == "prefix" else "pretosuf"}, ""
        if name == "AspectBeast":
            return {"action": "beast_crafting", "subaction": "b" + action.aspect}, ""
        if name == "ApplyFossils":
            ids = [self.fossils.get(f.removesuffix(" Fossil")) for f in action.fossils]
            return ({"action": "fossil", "subaction": ids}, "") if all(ids) else (None, f"unknown fossil in {action.fossils}")
        if name == "ApplyEssence":
            forced = outcomes.forced if outcomes is not None else None
            if forced is None:
                return None, "our essence names no forced mod here"
            base = self.base_of(self.bitem(item.base_id))
            essence_aids = {str(json.loads(e["tiers"]).get(base)) for e in self.d["essences"]["seq"]}
            aid, tindex = self.coe_mod(base, forced, essence_aids)
            return {"action": "essence", "essmod": aid, "ssaction": str(tindex)}, ""
        if name == "BenchCraft":
            aid, tindex = self.coe_mod(self.base_of(self.bitem(item.base_id)), action.mod_id)
            return {"force": {"ptype": "cb", "aid": aid, "tindex": tindex}}, ""
        return None, f"no emulator button known for {name}"


def mod_text(mod) -> str:
    """Our mod's text as Craft of Exile names a modifier: every number and range a #, lines joined by ", "."""
    text = re.sub(r"\(-?\d+(\.\d+)?--?\d+(\.\d+)?\)|-?\d+(\.\d+)?", "#", mod.text or "")
    return ", ".join(line.strip() for line in text.splitlines())


def build_item(data, spec: dict) -> Item:
    table = tier_table(data, spec["base"])
    mods = []
    for mod_id in spec.get("mods", []):
        mod = data.mods[mod_id]
        low = tuple(min(s.min, s.max) for s in mod.stats)
        mods.append(ExplicitMod(mod_id, table.get(mod_id, 1), low, fractured=mod_id in spec.get("fractured", []), crafted=mod.domain == "crafted"))
    fields = {"base_id": spec["base"], "item_level": spec.get("item_level", 100), "rarity": Rarity(spec.get("rarity", "rare")),
              "mods": tuple(mods), "influences": frozenset(Influence(i) for i in spec.get("influences", []))}
    if spec.get("corrupted"):
        fields["corrupted"] = True
    return Item.build(data, **fields)


def code_place(action) -> str:
    """The file:line of the action's `outcomes`, the place our verdict comes from."""
    method = type(action).outcomes
    file = Path(inspect.getsourcefile(method)).resolve()
    line = inspect.getsourcelines(method)[1]
    try:
        file = file.relative_to(HERE.parents[1])
    except ValueError:
        pass
    return f"{file.as_posix()}:{line}"


def ours(data, item: Item, action):
    """Our verdict on `action`: (outcomes, None) or (None, the refusal)."""
    try:
        return action.outcomes(data, item), None
    except (NotApplicableError, OutOfScopeError) as error:
        return None, f"{type(error).__name__}: {error}"


def finished_distribution(outcomes, limit: int = 400) -> dict[frozenset, Fraction] | None:
    """The exact distribution of the finished item's mod ids, when it is small; None otherwise."""
    result: Counter = Counter()
    for chance, part in outcomes.components:
        if isinstance(part, Fixed):
            result[frozenset(m.mod_id for m in part.result.mods)] += chance
            continue
        retained = frozenset(m.mod_id for m in part.retained.mods)
        draws = max(part.totals) - len(retained) if getattr(part, "totals", None) else 0
        if draws > 1:
            return None
        for outcome, inner in part.distribution(lambda mod: mod.id).items():
            new = frozenset(label for label, _ in outcome)
            result[retained | new] += chance * inner
        if len(result) > limit:
            return None
    return dict(result)


def pool_ids(outcomes) -> set[str]:
    """The mod ids our outcomes can put on the item (the pools of its draws and the fixed results)."""
    found = set()
    for _, part in outcomes.components:
        if isinstance(part, Fixed):
            found |= {m.mod_id for m in part.result.mods}
        else:
            found |= {m.mod_id for m in part.retained.mods}
            found |= {entry.mod.id for family in part.pool for entry in family.mods}
    return found


def z_score(p: float, hits: int, n: int) -> float | None:
    if n == 0 or p <= 0 or p >= 1:
        return None if (p > 0 and hits == n) or (p == 0 and hits == 0) or n == 0 else math.inf
    return (hits / n - p) / math.sqrt(p * (1 - p) / n)


def compare_action(data, coe: Coe, emulator: Emulator, item: Item, spec: dict, coe_spec: dict, donor_spec, action, repeats: int) -> dict:
    outcomes, refusal = ours(data, item, action)
    row = {"action": action.label(data), "class": type(action).__name__, "our_place": code_place(action),
           "ours": "refused" if refusal else "applies", "our_refusal": refusal}
    craft, why = coe.craft(action, item, outcomes)
    if craft is None:
        row["coe"] = f"not compared: {why}"
        return row
    row["coe_craft"] = craft
    check = {"id": spec.get("id"), "item": coe_spec, "apply": [{"craft": craft, "repeats": repeats}]}
    if donor_spec is not None:
        check["donor"] = donor_spec
    answer = emulator.check(check)
    applied = answer["apply"][0]
    n_ok = sum(applied["counts"].values())
    row["coe"] = "applies" if n_ok else "refused"
    row["coe_counts"] = {"changed": n_ok, "refused": applied["failures"]}
    row["candidates"] = []
    if (refusal is None) != (n_ok > 0):
        row["candidates"].append("verdicts differ")
    if refusal or not n_ok:
        return row
    coe_base = coe.base_of(coe_spec["bitem"])
    pool = pool_ids(outcomes) | {m.mod_id for m in item.mods}
    results: Counter = Counter()
    for key, count in applied["counts"].items():
        example = applied["examples"][key]["item"]
        mods = frozenset(coe.our_mod(coe_base, m, pool) for m in example["mods"])
        results[mods] += count
    unmapped = sorted({m for mods in results for m in mods if m.startswith("coe:")})
    if unmapped:
        row["unmapped_coe_mods"] = unmapped[:20]
    exact = finished_distribution(outcomes)
    if exact is not None:
        keys = set(exact) | set(results)
        table = []
        for key in sorted(keys, key=lambda k: -float(exact.get(k, 0))):
            p = float(exact.get(key, 0))
            table.append({"mods": sorted(key - frozenset(m.mod_id for m in item.mods)) or sorted(key), "ours": round(p, 5),
                          "coe": results.get(key, 0) / n_ok, "z": z_score(p, results.get(key, 0), n_ok)})
        row["distribution"] = table[:40]
        row["candidates"] += [f"outcome {t['mods']}: ours {t['ours']}, CoE {t['coe']:.4f}" for t in table if t["z"] is not None and abs(t["z"]) > 4]
        return row
    # a draw of several mods: our side is a seeded sample of our own model (an exact marginal per mod
    # costs seconds to minutes each), compared mod by mod and by the shape (prefixes, suffixes)
    rng = random.Random(198)
    samples = [outcomes.sample(rng) for _ in range(OUR_SAMPLES)]
    ours_seen = Counter(entry.mod_id for sample in samples for entry in sample.mods)
    seen = Counter(m for mods, count in results.items() for m in mods for _ in range(count))
    chosen = [m for m, _ in seen.most_common(25)] + [m for m, _ in ours_seen.most_common(25)]
    marginals = []
    for mod_id in dict.fromkeys(m for m in chosen if not m.startswith("coe:")):
        z = two_sample_z(ours_seen[mod_id], OUR_SAMPLES, seen[mod_id], n_ok)
        marginals.append({"mod": mod_id, "ours": round(ours_seen[mod_id] / OUR_SAMPLES, 5), "coe": round(seen[mod_id] / n_ok, 5), "z": z})
    row["marginals"] = marginals
    side = {mod_id: data.mods[mod_id].generation_type for mod_id in data.mods}
    def shape_of(mods):
        prefixes = sum(side.get(m) == "prefix" for m in mods)
        return f"{prefixes}p{len(mods) - prefixes}s"
    ours_shape = Counter(shape_of([e.mod_id for e in sample.mods]) for sample in samples)
    coe_shape = Counter()
    for mods, count in results.items():
        coe_shape[shape_of([m for m in mods if not m.startswith("coe:")])] += count
    row["shapes"] = [{"shape": k, "ours": round(ours_shape[k] / OUR_SAMPLES, 4), "coe": round(coe_shape[k] / n_ok, 4),
                      "z": two_sample_z(ours_shape[k], OUR_SAMPLES, coe_shape[k], n_ok)} for k in sorted(set(ours_shape) | set(coe_shape))]
    row["candidates"] += [f"mod {m['mod']}: ours {m['ours']}, CoE {m['coe']}" for m in marginals if m["z"] is not None and abs(m["z"]) > 4]
    row["candidates"] += [f"shape {m['shape']}: ours {m['ours']}, CoE {m['coe']}" for m in row["shapes"] if m["z"] is not None and abs(m["z"]) > 4]
    return row


def two_sample_z(hits_a: int, n_a: int, hits_b: int, n_b: int) -> float | None:
    """The z of two frequencies (pooled); None when both are 0 or both 1."""
    pooled = (hits_a + hits_b) / (n_a + n_b)
    if pooled in (0, 1):
        return None
    return round((hits_b / n_b - hits_a / n_a) / math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b)), 2)


def run_check(data, coe: Coe, emulator: Emulator, spec: dict) -> dict:
    item = build_item(data, spec)
    coe_spec = coe.item_spec(item, set(spec.get("fractured", [])))
    donor_spec = None
    if spec.get("donor"):
        donor = build_item(data, spec["donor"])
        donor_spec = coe.item_spec(donor, set(spec["donor"].get("fractured", [])))
    listed = catalog(data, item)
    by_label = {action.label(data): action for action in listed}
    wanted = spec.get("actions", ["*"])
    report = {"id": spec.get("id"), "item": spec, "coe_item": coe_spec, "our_catalog_size": len(listed), "actions": []}
    if wanted == ["*"]:
        chosen = [a for a in listed if coe.craft(a, item, None)[0] is not None or type(a).__name__ in ("ApplyEssence",)]
    else:
        chosen = []
        for label in wanted:
            if label in by_label:
                chosen.append(by_label[label])
            else:
                near = difflib.get_close_matches(label, list(by_label), n=5, cutoff=0.4)
                report["actions"].append({"action": label, "ours": "not in our catalog for this item", "near": near})
    legal = emulator.check({"id": spec.get("id"), "item": coe_spec, "legal": True})["legal"]
    report["coe_legal"] = {
        "currency": {k: v for k, v in legal["currency"].items()},
        "actions": {k: {"enabled": v["enabled"], "subsets": {s: e["enabled"] for s, e in v["subsets"].items()}} for k, v in legal["actions"].items()},
    }
    for action in chosen:
        try:
            row = compare_action(data, coe, emulator, item, spec, coe_spec, donor_spec, action, spec.get("repeats", 1000))
        except Exception as error:  # one action the harness cannot translate must not end the sweep
            row = {"action": action.label(data), "ours": "?", "coe": f"harness error: {type(error).__name__}: {error}"}
        report["actions"].append(row)
        print(f"   {spec.get('id')}: {row['action']} done", file=sys.stderr, flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("checks")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--copy", type=Path, default=None)
    arguments = parser.parse_args()
    copy = arguments.copy or default_copy()
    data = load_game_data()
    coe = Coe(copy, data)
    specs = json.loads(Path(arguments.checks).read_text(encoding="utf-8"))
    emulator = Emulator(copy)
    reports = []
    try:
        for spec in specs if isinstance(specs, list) else [specs]:
            try:
                reports.append(run_check(data, coe, emulator, spec))
            except Exception as error:  # an item the harness cannot build must not end the sweep
                reports.append({"id": spec.get("id"), "error": f"{type(error).__name__}: {error}", "actions": []})
            if arguments.out:  # written after every check, so a long sweep keeps what it has
                arguments.out.write_text(json.dumps(reports, indent=1, default=str), encoding="utf-8")
    finally:
        emulator.close()
    for report in reports:
        print(f"== {report['id']}" + (f" (harness error: {report['error']})" if report.get("error") else ""))
        for row in report["actions"]:
            flags = "; ".join(row.get("candidates", [])) or "-"
            print(f"  {row['action']}: ours {row['ours']} | CoE {row.get('coe')} | {row.get('coe_counts', '')} | candidates: {flags}{' | near: ' + str(row['near']) if row.get('near') else ''}")


if __name__ == "__main__":
    main()
