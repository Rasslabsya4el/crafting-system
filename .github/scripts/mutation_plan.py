"""The plan of the mutation step (ticket #399, step 5): every mutant of the core, in priority order, with its tests.

Design, in short (the reasons are in `docs/ci.md`'s measurement section and the ticket's report):

Tool: a small AST mutator of our own (`mutation_ops.py`), not mutmut 3 or cosmic-ray. mutmut 3 rewrites every
function into a trampoline with all its mutants inside, picks its tests from its own run statistics (not from our
coverage contexts), keeps its state in a `mutants/` folder, and is built for one machine; cosmic-ray keeps a session
database that does not split across runners. Here a mutant is a row (file, span, replacement text) in `plan.json`,
numbered by its place in one deterministic order, so any runner can take any slice by number, and the tests of a
line come straight from step 3's data. `src/` is never edited: a runner mutates a copy of the package.

Scope, in priority order (a wrong line here silently changes what a route costs or how likely it is):
  1. the draw and the pool: `actions/` draw, pool, add, magic, outcomes, mixture, chaos, exalted, annul, scour,
     finite, rolls, cut, and `items/` spawn and tiers (which mods can roll, with what weight). Every probability a
     route reads starts here.
  2. `abstraction/`: the kernel (successors and weights of every state, shared by the solver), the goal, the state,
     the roll classes, the bound.
  3. `solver/`: the values, the policy, the merge of equal states, the certificate.
  4. `risk/` (the mean, odds and quantiles of a policy: `_evaluate`, `_mean`, `_moments`, `_fold`, `_chain`...) and
     the route's packed solve and decision in `cli/` (`_packed`, `_decide`, `_plan`).
  5. the other actions, where a wrong line changes one orb's result.
  6. targets (when is the item done), the item model, prices (what an action costs).
  7. every other module of the package (page rendering, data loading, the CLI): last, to fill the machines.
The ticket names `cli/_route_packed.py`; the file is `cli/_packed.py` (the packed solve of a plan).

Order: tier by tier; inside a tier the files are interleaved by position (the first 1% of every file, then the next
1%), so a stop at the deadline leaves every file of the tier partly measured, not one file whole and one untouched.
Rank in the plan is the mutant's number; a round takes the next pending numbers, so priority holds across rounds.

Reachability: only function bodies (see `mutation_ops.py`), and only statements that some test ran. With the
coverage data present, a mutant on a line no test ran is counted as "unreached" and is not planned (the coverage
step lists such code); the trial plans it with the import-based tests. The mutants of a file are checked to parse.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mutation_ops as ops  # noqa: E402
import mutation_select as select  # noqa: E402

SRC = "src/crafting_system"
TIERS: list[tuple[int, str, list[str]]] = [
    (1, "draw and pool", [
        "actions/draw.py", "actions/pool.py", "actions/magic.py", "actions/add.py", "actions/outcomes.py",
        "actions/mixture.py", "actions/chaos.py", "actions/exalted.py", "actions/annul.py", "actions/scour.py",
        "actions/finite.py", "actions/rolls.py", "actions/cut.py", "items/spawn.py", "items/tiers.py",
    ]),
    (2, "abstraction", [
        "abstraction/_kernel.py", "abstraction/_goal.py", "abstraction/_state.py", "abstraction/_rolls.py",
        "abstraction/_inputs.py", "abstraction/_bound.py", "abstraction/_kinds.py", "abstraction/__init__.py",
    ]),
    (3, "solver", ["solver/*.py"]),
    (4, "risk and route", ["risk/_evaluate.py", "risk/*.py", "cli/_packed.py", "cli/_decide.py", "cli/_plan.py"]),
    (5, "other actions", ["actions/*.py", "abstraction/*.py"]),
    (6, "targets, items, prices", ["targets/*.py", "items/*.py", "prices/price_file.py", "prices/trade_pricing.py"]),
    (7, "the rest of the package", ["**/*.py"]),
]  # fmt: skip
TRIAL_FILE = "solver/_sparse.py"
TRIAL_MUTANTS = 20


def tier_files(root: Path) -> list[tuple[int, str]]:
    """(tier, path relative to the repo root) of every scoped file, once, in priority order."""
    seen: set[str] = set()
    result: list[tuple[int, str]] = []
    for tier, _name, patterns in TIERS:
        for pattern in patterns:
            for path in sorted((root / SRC).glob(pattern)):
                relative = path.relative_to(root).as_posix()
                if relative not in seen and path.is_file() and "__pycache__" not in relative and path.name != "__main__.py":
                    seen.add(relative)
                    result.append((tier, relative))
    return result


def set_id(tests: list[str]) -> str:
    return "s" + hashlib.sha1("\n".join(tests).encode()).hexdigest()[:10]


def interleave(per_file: list[tuple[int, str, list]]) -> list[tuple[int, str, object]]:
    """Tier by tier, the files' mutants merged by relative position inside the file (ties: file order)."""
    keyed = []
    for order, (tier, file, items) in enumerate(per_file):
        keyed += [((tier, (k + 0.5) / len(items), order), file, item) for k, item in enumerate(items)]
    keyed.sort(key=lambda entry: entry[0])
    return [(key[0], file, item) for key, file, item in keyed]


def build_plan(
    root: Path,
    coverage_file: Path | None,
    durations_file: Path | None,
    trial: bool,
    commit: str = "",
) -> dict:
    """The whole plan as a JSON-ready dict: the numbered mutants, the test sets they use, the counts of the rest."""
    index = select.build_index(root / "tests", root)
    graph = select.build_src_graph(root / "src")
    costs = select.file_costs(json.loads(durations_file.read_text(encoding="utf-8"))) if durations_file and durations_file.exists() else {}
    has_data = coverage_file is not None and coverage_file.exists()
    files = [(3, f"{SRC}/{TRIAL_FILE}")] if trial else tier_files(root)

    per_file: list[tuple[int, str, list]] = []
    sets: dict[str, dict] = {}
    file_info: dict[str, dict] = {}
    hashes: dict[str, str] = {}
    for tier, file in files:
        source = (root / file).read_text(encoding="utf-8").replace("\r\n", "\n")
        hashes[file] = hashlib.sha1(source.encode()).hexdigest()
        module = select.dotted_module(file)
        contexts = (select.read_line_contexts(coverage_file, file) or {}) if has_data else None
        planned, unreached, no_tests = [], 0, 0
        for mutant in ops.find_mutants(source, file):
            tests, origin, cut = select.tests_for_line(index, graph, module, contexts, mutant.stmt_line, costs, reach_fallback=trial)
            if not tests:
                unreached += 1 if has_data else 0
                no_tests += 0 if has_data else 1
                continue
            name = set_id(tests)
            sets.setdefault(name, {"tests": tests, "source": origin, "cut": cut})
            planned.append({**mutant.to_json(), "tier": tier, "set": name})
        if trial:
            step = max(1, len(planned) // TRIAL_MUTANTS)
            planned = planned[::step][:TRIAL_MUTANTS]
        file_info[file] = {"tier": tier, "mutants": len(planned), "unreached": unreached, "no_tests": no_tests}
        if planned:
            per_file.append((tier, file, planned))

    ordered = interleave(per_file)
    mutants = []
    for number, (_key, _file, entry) in enumerate(ordered):
        entry = dict(entry)
        entry["id"] = number
        entry["original"] = entry["original"][:400]
        mutants.append(entry)
    return {
        "commit": commit, "trial": trial, "coverage": has_data, "hashes": hashes, "files": file_info,
        "sets": sets, "mutants": mutants,
    }  # fmt: skip


def sample_plan(plan: dict, count: int) -> dict:
    """A plan of `count` evenly spaced mutants of `plan`, renumbered (a quick look at the whole scope, for a check run)."""
    step = max(1, len(plan["mutants"]) // count)
    kept = [dict(mutant) for mutant in plan["mutants"][::step][:count]]
    for number, mutant in enumerate(kept):
        mutant["id"] = number
    used = {mutant["set"] for mutant in kept}
    return {**plan, "mutants": kept, "sets": {name: entry for name, entry in plan["sets"].items() if name in used}}


def git_head(root: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--coverage", type=Path, help="the combined .coverage data file of step 3 (may be missing)")
    parser.add_argument("--durations", type=Path, default=Path("tests/shard_durations.json"))
    parser.add_argument("--trial", action="store_true", help=f"{TRIAL_MUTANTS} mutants of {TRIAL_FILE}")
    parser.add_argument("--sample", type=int, help="keep only this many evenly spaced mutants (a check run, not the week)")
    parser.add_argument("--out", type=Path, required=True, help="folder for plan.json")
    args = parser.parse_args()
    root = args.root.resolve()
    plan = build_plan(root, args.coverage, root / args.durations if not args.durations.is_absolute() else args.durations, args.trial, git_head(root))
    if args.sample:
        plan = sample_plan(plan, args.sample)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    unreached = sum(info["unreached"] for info in plan["files"].values())
    print(f"{len(plan['mutants'])} mutants in {len(plan['sets'])} test sets; {unreached} on lines no test runs; coverage data: {plan['coverage']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
