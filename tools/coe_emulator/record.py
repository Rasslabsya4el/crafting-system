"""Record Craft of Exile emulator counts as our own measurement (ticket #544).

    PYTHONPATH=src python tools/coe_emulator/record.py run   cases.json CASE_ID --seed 5440 --repeats 1000 --out run.json
    PYTHONPATH=src python tools/coe_emulator/record.py merge cases.json run1.json run2.json ... --out counts.json [--into counts.json]

`run` applies the ONE action of the case CASE_ID `--repeats` times in the emulator (headless, from the
git-ignored local copy, one process, seeded: `driver.js` replaces the page's `Math.random` by a seeded
generator, so the same seed on the same copy gives the same counts) and writes the counts of the finished
items, as sets of OUR mod ids. Keep each run under a minute; get a bigger sample from several runs with
different seeds. `merge` adds the runs of each case into the file that is committed
(`tests/fixtures/coe_recorded/b1_core.json`): the sample sizes, the seeds, the date, and the hashes of the copy's
`package.js` and `poec_data.json` (the Craft of Exile version). Craft of Exile's code is never written
into it: only counts and provenance.

A case is a check of `compare.py` (our base, mods, rarity, `actions` with ONE label of our catalog) plus
`note` (why this item and action) and `route` (the benchmark route the base comes from). A case with `roll_stats`
(a list of stat texts, as our catalog writes them: "+# to maximum Life") also records, for each, how many finished items
carry each rolled value of each of our mods with that text (ticket #573): the roll of a goal line that asks one.

A case with `target` (the path of a target file, ticket #617) also records how many finished items MEET it, read by the planner's own
judge (`crafting_system.cli._benchmark_use.reading_of`): the item is the target (`goal`), or one sure bench craft short of it (`short`:
R08's top Energy Shield with an open prefix, whose Movement Speed the guide and the planner both craft at the bench). This is the joint
"the target is met" count; it needs the prices only for the offers to exist, so the committed snapshot is used.
"""

import argparse
import datetime
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compare  # noqa: E402
from emulator import Emulator, default_copy  # noqa: E402
from target_judge import TargetJudge  # noqa: E402

from crafting_system.actions.catalog import catalog  # noqa: E402
from crafting_system.data import load_game_data  # noqa: E402


def load_cases(path: Path) -> dict[str, dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    return {case["id"]: case for case in cases}


def run_case(spec: dict, seed: int, repeats: int, copy: Path) -> dict:
    data = load_game_data()
    coe = compare.Coe(copy, data)
    item = compare.build_item(data, spec)
    coe_spec = coe.item_spec(item, set(spec.get("fractured", [])))
    (label,) = spec["actions"]
    by_label = {action.label(data): action for action in catalog(data, item)}
    action = by_label[label]
    outcomes, refusal = compare.ours(data, item, action)
    if refusal:
        raise SystemExit(f"our system refuses {label} on {spec['id']}: {refusal}")
    craft, why = coe.craft(action, item, outcomes)
    if craft is None:
        raise SystemExit(f"no emulator button for {label}: {why}")
    emulator = Emulator(copy)
    try:
        started = time.time()
        step = {"craft": craft, "repeats": repeats, "seed": seed}
        if spec.get("roll_stats"):
            step["track"] = list(spec["roll_stats"])
        answer = emulator.check({"id": spec["id"], "item": coe_spec, "apply": [step]})
        seconds = round(time.time() - started, 1)
    finally:
        emulator.close()
    applied = answer["apply"][0]
    coe_base = coe.base_of(coe_spec["bitem"])
    pool = compare.pool_ids(outcomes) | {m.mod_id for m in item.mods}
    results: Counter = Counter()
    for key, count in applied["counts"].items():
        mods = sorted(coe.our_mod(coe_base, m, pool) for m in applied["examples"][key]["item"]["mods"])
        results[json.dumps(mods)] += count
    readings: Counter = Counter()  # the finished items by what they are next to the target (ticket #617)
    if spec.get("target"):
        judge = TargetJudge(data, spec["target"], spec.get("rarity"))
        for key, count in results.items():
            found = json.loads(key)
            if any(mod_id.startswith("coe:") for mod_id in found):
                raise SystemExit(f"{spec['id']}: a finished item holds a Craft of Exile mod that maps to none of ours: {found}")
            readings[judge.reading(found)] += count
    rolls: dict[str, dict[str, Counter]] = {}  # stat text -> our mod id -> rolled value -> finished items
    for key, values in applied.get("rolls", {}).items():
        aid, tindex = key.split(":")
        mod_id = coe.our_mod(coe_base, {"aid": aid, "tindex": int(tindex)}, pool)
        stat = coe.modifiers[aid]["name_modifier"]
        if mod_id.startswith("coe:"):
            raise SystemExit(f"{spec['id']}: the tracked mod {stat} ({key}) maps to none of ours")
        for rolled, count in values.items():
            (value,) = json.loads(rolled)  # a tracked mod has one stat
            rolls.setdefault(stat, {}).setdefault(mod_id, Counter())[json.dumps(value)] += count
    return {
        "case": spec["id"], "action": label, "seed": seed, "repeats": repeats, "seconds": seconds,
        "applied": sum(applied["counts"].values()), "refused": applied["failures"],
        "outcomes": dict(results), "page_errors": answer.get("page_errors", []),
        **({"rolls": {stat: {mod: dict(c) for mod, c in mods.items()} for stat, mods in rolls.items()}} if rolls else {}),
        **({"readings": dict(readings)} if readings else {}),
    }  # fmt: skip


def merge(cases: dict[str, dict], runs: list[dict], copy: Path) -> dict:
    mods_of_data = load_game_data().mods
    side = {mod_id: mod.generation_type for mod_id, mod in mods_of_data.items()}
    families = {mod_id: frozenset(mod.families) for mod_id, mod in mods_of_data.items()}
    manifest = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    by_case: dict[str, list[dict]] = {}
    for run in runs:
        by_case.setdefault(run["case"], []).append(run)
    recorded = {}
    for case_id, case_runs in sorted(by_case.items()):
        spec = cases[case_id]
        outcomes: Counter = Counter()
        for run in case_runs:
            outcomes.update(run["outcomes"])
        mods: Counter = Counter()
        for key, count in outcomes.items():
            for mod_id in json.loads(key):
                mods[mod_id] += count
        shapes: Counter = Counter()  # the finished items by their number of prefixes and suffixes
        for key, count in outcomes.items():
            found = json.loads(key)
            prefixes = sum(side[mod_id] == "prefix" for mod_id in found)
            shapes[f"{prefixes}p{len(found) - prefixes}s"] += count
        joints: Counter = Counter()  # items that hold a mod of each of several families (the C02 question)
        for names in spec.get("joint_families", []):
            for key, count in outcomes.items():
                found = json.loads(key)
                if all(any(name in families[mod_id] for mod_id in found) for name in names):
                    joints["+".join(names)] += count
        rolled: dict[str, dict[str, Counter]] = {}
        for run in case_runs:
            for stat, per_mod in run.get("rolls", {}).items():
                for mod_id, values in per_mod.items():
                    rolled.setdefault(stat, {}).setdefault(mod_id, Counter()).update(values)
        readings: Counter = Counter()
        for run in case_runs:
            readings.update(run.get("readings", {}))
        applied = sum(run["applied"] for run in case_runs)
        recorded[case_id] = {
            "route": spec.get("route"), "note": spec.get("note"),
            "item": {k: spec[k] for k in ("base", "item_level", "rarity", "influences", "mods", "fractured") if k in spec},
            "action": spec["actions"][0],
            "applied": applied, "refused": sum(sum(run["refused"].values()) for run in case_runs),
            "runs": [{"seed": run["seed"], "repeats": run["repeats"], "seconds": run["seconds"]} for run in case_runs],
            "mods": dict(sorted(mods.items(), key=lambda pair: (-pair[1], pair[0]))),
            "shapes": dict(sorted(shapes.items())),
            **({"rolls": {stat: {mod: dict(sorted(c.items(), key=lambda pair: float(pair[0]))) for mod, c in sorted(mods.items())} for stat, mods in sorted(rolled.items())}} if rolled else {}),
            **({"target": {"file": spec["target"], "goal": readings["goal"], "short": readings["short"], "other": readings["other"]}} if spec.get("target") else {}),
            **({"joints": {name: joints.get(name, 0) for name in ("+".join(n) for n in spec["joint_families"])}} if spec.get("joint_families") else {}),
            # the whole finished items are kept only when they are few (a single draw); a draw of several mods is
            # recorded by the frequency of each mod
            "outcomes": {key: count for key, count in sorted(outcomes.items(), key=lambda pair: -pair[1])} if len(outcomes) <= 600 else None,
        }
    return {
        "provenance": {
            "what": "counts of finished items from the Craft of Exile emulator (Wraecrafter Ultra), our measurement; no Craft of Exile code",
            "emulator": "https://www.craftofexile.com/?game=poe1 , run headless from a local copy by tools/coe_emulator/record.py",
            "copy_fetched": manifest["fetched"],
            "recorded": datetime.date.today().isoformat(),
            "package_js_sha256": files["packages/package.js"]["sha256"],
            "poec_data_json_sha256": files["json/data/main/poec_data.json"]["sha256"],
            "coe_data_version": "3.29.0.3 (tools/coe_emulator/README.md; our pin is repoe-fork 3.29.3.3)",
            "seeded": "driver.js seeds the page's Math.random (mulberry32); the same seed on the same copy repeats the counts",
        },
        "cases": recorded,
    }  # fmt: skip


def add_to(existing: dict, merged: dict) -> dict:
    """`existing` with the cases of `merged` added (a case of the same name is replaced).

    The two must come from the same Craft of Exile code and data (the hashes of `package.js` and `poec_data.json`); the provenance of `existing` stays
    and lists the added cases with the day and the fetch time of the copy they were recorded on.
    """
    old, new = existing["provenance"], merged["provenance"]
    for key in ("package_js_sha256", "poec_data_json_sha256"):
        if old[key] != new[key]:
            raise SystemExit(f"the copy differs from the recorded file's ({key}): record every case again with `merge` instead of adding")
    provenance = dict(old)
    provenance["also_recorded"] = [
        *old.get("also_recorded", []),
        {"cases": sorted(merged["cases"]), "recorded": new["recorded"], "copy_fetched": new["copy_fetched"]},
    ]
    return {"provenance": provenance, "cases": {**existing["cases"], **merged["cases"]}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run")
    one.add_argument("cases")
    one.add_argument("case_id")
    one.add_argument("--seed", type=int, required=True)
    one.add_argument("--repeats", type=int, default=1000)
    one.add_argument("--out", type=Path, required=True)
    many = sub.add_parser("merge")
    many.add_argument("cases")
    many.add_argument("runs", nargs="+")
    many.add_argument("--out", type=Path, required=True)
    many.add_argument("--into", type=Path, help="a recorded file to add the cases to (ticket #617): its other cases and its provenance stay, the copy must be the same")
    arguments = parser.parse_args()
    copy = default_copy()
    cases = load_cases(Path(arguments.cases))
    if arguments.command == "run":
        result = run_case(cases[arguments.case_id], arguments.seed, arguments.repeats, copy)
        arguments.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"{result['case']}: seed {result['seed']}, {result['applied']} applied, {result['refused']} refused, {result['seconds']} s")
        return
    runs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in arguments.runs]
    merged = merge(cases, runs, copy)
    if arguments.into is not None:
        merged = add_to(json.loads(arguments.into.read_text(encoding="utf-8")), merged)
    arguments.out.write_text(json.dumps(merged, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {arguments.out}")


if __name__ == "__main__":
    main()
