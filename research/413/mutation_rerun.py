"""Plans to measure again the mutants of a few modules that the measurement week (#399) left alive (ticket #413).

The week's plan (`measure-mutplan` of run 41490953015) picked each mutant's tests from the coverage contexts of step 3, and
that data is not at hand now. This script builds two small plans for the same modules from the week's plan and results:

* `before`: every mutant that was not killed (survived, timed out, errored) or is new in today's source (ticket #389 changed
  `planner/_packed.py` and `risk/_coarse.py`), with the tests the week gave it (new ones: the tests that import the module);
* `after`:  the same mutants, each with the tests of `before` and, in front of them, the new light test files of its module.

A mutant of today's source is matched to a mutant of the week by its text (operator, original, mutated), not by line number.
A mutant the week could not check (its tests failed clean: `skipped`) is left out of `before` and gets only the new files of its
module in `after`; the PR says so.

Both plans are in the format of `.github/scripts/mutation_plan.py`, so `.github/scripts/mutation_run.py` runs them and
`.github/scripts/mutation_summary.py` merges the results. Only the modules named are in the plan (`files`).

    python research/413/mutation_rerun.py --old-plan plan.json --old-results results --out research/413 \
        --files solver/_packed_solve.py planner/_packed.py ... --extra solver/_packed_solve.py=tests/test_x_light.py ...

Locally this only reads files and writes two JSON files (a second or two); nothing is mutated or run.
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import mutation_ops as ops  # noqa: E402
import mutation_select as select  # noqa: E402
import mutation_summary as summary  # noqa: E402

SRC = "src/crafting_system"


def key_of(mutant) -> tuple:
    if isinstance(mutant, dict):
        return (mutant["operator"], mutant["original"][:400], mutant["mutated"][:400])
    return (mutant.operator, mutant.original[:400], mutant.mutated[:400])


def set_id(tests: list[str]) -> str:
    return "s" + hashlib.sha1("\n".join(tests).encode()).hexdigest()[:10]


def build(old_plan: dict, old_results: dict, files: list[str], extra: dict[str, list[str]]) -> tuple[dict, dict]:
    """(before, after) plans."""
    index = select.build_index(ROOT / "tests", ROOT)
    graph = select.build_src_graph(ROOT / "src")
    plans = {name: {"commit": "", "trial": False, "coverage": True, "hashes": {}, "files": {}, "sets": {}, "mutants": []} for name in ("before", "after")}
    for tier_file in files:
        file = f"{SRC}/{tier_file}"
        source = (ROOT / file).read_text(encoding="utf-8").replace("\r\n", "\n")
        digest = hashlib.sha1(source.encode()).hexdigest()
        old = defaultdict(list)  # key -> old mutants of this file, in source order
        for mutant in sorted((m for m in old_plan["mutants"] if m["file"] == file), key=lambda m: (m["line"], m["col"])):
            old[key_of(mutant)].append(mutant)
        tier = next((m["tier"] for m in old_plan["mutants"] if m["file"] == file), 7)
        counts = {"before": 0, "after": 0}
        for mutant in ops.find_mutants(source, file):
            matches = old.get(key_of(mutant))
            if matches:
                was = matches.pop(0)
                outcome = old_results[was["id"]]["outcome"] if was["id"] in old_results else "not run"
                if outcome == "killed":
                    continue
                tests = old_plan["sets"][was["set"]]["tests"]
                cut = old_plan["sets"][was["set"]]["cut"]
                source_of_tests = old_plan["sets"][was["set"]]["source"]
            else:
                outcome = "new"
                tests, source_of_tests, cut = select.tests_for_line(index, graph, select.dotted_module(file), None, mutant.stmt_line)
            for name in ("before", "after"):
                if name == "before":
                    if outcome == "skipped":
                        continue
                    chosen = list(tests)
                else:
                    new = extra.get(tier_file, [])
                    chosen = [*new, *(t for t in tests if t not in new)] if outcome != "skipped" else list(new)
                if not chosen:
                    continue
                label = set_id(chosen)
                plans[name]["sets"].setdefault(label, {"tests": chosen, "source": source_of_tests, "cut": cut})
                plans[name]["mutants"].append({**mutant.to_json(), "tier": tier, "set": label, "before": outcome})
                counts[name] += 1
        for name in plans:
            plans[name]["hashes"][file] = digest
            plans[name]["files"][file] = {"tier": tier, "mutants": counts[name], "unreached": 0, "no_tests": 0}
    for plan in plans.values():
        for number, mutant in enumerate(plan["mutants"]):
            mutant["id"] = number
            mutant["original"] = mutant["original"][:400]
    return plans["before"], plans["after"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--old-plan", type=Path, required=True)
    parser.add_argument("--old-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--files", nargs="+", required=True, help="module paths under src/crafting_system")
    parser.add_argument("--extra", nargs="+", required=True, help="MODULE=TEST_FILE: a new light test file of a module (run first)")
    args = parser.parse_args()
    old_plan = json.loads(args.old_plan.read_text(encoding="utf-8"))
    old_results = summary.read_results(args.old_results)
    extra: dict[str, list[str]] = defaultdict(list)
    for entry in args.extra:
        module, _, test = entry.partition("=")
        extra[module].append(test)
    before, after = build(old_plan, old_results, args.files, extra)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, plan in (("before", before), ("after", after)):
        (args.out / f"plan-{name}.json").write_text(json.dumps(plan), encoding="utf-8")
        print(f"{name}: {len(plan['mutants'])} mutants, {len(plan['sets'])} test sets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
