# One paired measurement of ticket #868 on one GitHub runner: the same plan on `main` (commit $2) and on this branch, one after the
# other, so the two times are of one machine (runners differ by up to 2 times). Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 4 --command 'bash research/868/pair.sh $RUNNER_INDEX <sha of main>'
# Line $1 of research/868/pairs.txt holds the arguments of research/881/profile_plan.py (no budget, the exact proof); the job fails when the
# two runs do not give one mean and the same counts of the search (research/827/same.py). Each run's peak memory is in peak.<side>.json.
set -euo pipefail
job="$1"
base="$2"
out="${OUT_DIR:-out}"
mkdir -p "$out"
args="$(sed -n "${job}p" research/868/pairs.txt)"
[ -n "$args" ] || { echo "no job $job"; exit 2; }
git fetch --depth 1 origin "$base"
git worktree add --detach main-src FETCH_HEAD
main_src="$PWD/main-src/src"
run() {  # $1: tag, $2: source folder or ""
  CRAFTING_SOURCE="$2" uv run --no-sync python research/827/peak.py "$out/peak$1.json" -- \
    uv run --no-sync python -u research/881/profile_plan.py $args --mode plain --tag "$1" --out "$out" > "$out/log$1.txt" 2>&1 || { tail -40 "$out/log$1.txt"; exit 1; }
  grep -E '"seconds"|"mean_remaining"' "$out/log$1.txt" | head -2
  cat "$out/peak$1.json"; echo
}
run .main-1 "$main_src"
run .branch-1 ""
cp "$out"/*.plain.main-1.json "$out/copy.plain.main-2.json"  # same.py wants four plain runs; one per side here, each counted twice
cp "$out"/*.plain.branch-1.json "$out/copy.plain.branch-2.json"
uv run --no-sync python research/827/same.py "$out"
