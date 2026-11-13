"""Fail unless the plain runs of a pair (research/827/pair.sh) gave one mean and the same counts of the search; print the pair's line."""

import json
import sys
from pathlib import Path

folder = Path(sys.argv[1])
runs = {path.name.split(".")[-2]: json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.plain.*.json"))}


def counts(run: dict) -> str:
    """The whole-number figures of the search (states, kernels, rounds): not its seconds."""
    search = run.get("search") or {}
    whole = {key: value for key, value in (search.get("stats") or {}).items() if isinstance(value, int)}
    return json.dumps([whole, search.get("states_known"), search.get("shared_kernel_hits")], sort_keys=True)


facts = {name: (run["mean_remaining"], counts(run)) for name, run in runs.items()}
for name, run in runs.items():
    print(name, run["seconds"], "s, mean", repr(run["mean_remaining"]), flush=True)
sides = {name: bool(run.get("source")) for name, run in runs.items()}  # a run of main planned with the copy of main's package
if any(planned_by_main != name.startswith("main") for name, planned_by_main in sides.items()):
    print("a run planned with the wrong package:", sides, flush=True)
    sys.exit(1)
if len(runs) < 4 or len(set(facts.values())) != 1:
    print("the runs differ:", {name: fact[0] for name, fact in facts.items()}, flush=True)
    sys.exit(1)
print("one mean, the same search counts on main and on the branch", flush=True)
