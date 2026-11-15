"""Fail unless the two plain runs of a pair (research/829/pair.sh) gave one mean, to 1e-9 of itself; print both runs' seconds, peak and search counts.

The search counts are printed, not compared: on main a fossil case of 40 offers or more is the bound pruning, or an envelope search whose model
grows, and on the branch of #829 it is the envelope search with each offer's own floor.
"""

import json
import sys
from pathlib import Path

folder = Path(sys.argv[1])
runs = {path.name.split(".")[-2]: json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.plain.*.json"))}
peaks = {path.name.split(".")[-2]: path.read_text(encoding="utf-8").strip() for path in sorted(folder.glob("peak.*.json"))}

for name, run in sorted(runs.items()):
    search = run.get("search") or {}
    whole = {key: value for key, value in (search.get("stats") or {}).items() if isinstance(value, (int, float)) and not isinstance(value, bool)}
    print(name, run["seconds"], "s, mean", repr(run["mean_remaining"]), "peak", peaks.get(name), flush=True)
    print("  search", json.dumps(whole, sort_keys=True), "states", search.get("states_known"), flush=True)
if set(runs) != {"main", "branch"}:
    print("expected one run of main and one of the branch, found", sorted(runs), flush=True)
    sys.exit(1)
if bool(runs["main"].get("source")) is not True or runs["branch"].get("source"):
    print("a run planned with the wrong package:", {name: run.get("source") for name, run in runs.items()}, flush=True)
    sys.exit(1)
main, branch = runs["main"]["mean_remaining"], runs["branch"]["mean_remaining"]
if abs(main - branch) > 1e-9 * max(abs(main), 1e-300):
    print(f"the means differ: main {main!r}, branch {branch!r}", flush=True)
    sys.exit(1)
print(f"one mean on main and on the branch: {branch!r}", flush=True)
