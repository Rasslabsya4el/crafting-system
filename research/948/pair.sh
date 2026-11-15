# One paired measurement of ticket #948 on one GitHub runner: the same plan under the default budget on `main` (commit $2) and on this branch, one
# after the other, so the two times are of one machine (runners differ by up to 2 times). Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 6 --command 'bash research/948/pair.sh $RUNNER_INDEX <sha of main>'
# The plan is line $1 of research/948/pairs.txt, planned by research/948/pair_plan.py. Order: main, branch, main, branch. The job fails when the
# four runs do not give one mean and the same counts of the search. `research/827/peak.py` gives each run's peak memory.
set -euo pipefail
job="$1"
base="$2"
out="${OUT_DIR:-out}"
mkdir -p "$out"
plan="$(sed -n "${job}p" research/948/pairs.txt)"
[ -n "$plan" ] || { echo "no job $job"; exit 2; }
git fetch --depth 1 origin "$base"
git worktree add --detach main-src FETCH_HEAD
run() {  # $1: tag, $2: source folder or ""
  CRAFTING_SOURCE="$2" uv run --no-sync python research/827/peak.py "$out/peak$1.json" -- \
    uv run --no-sync python -u research/948/pair_plan.py $plan --tag "$1" --out "$out" > "$out/log$1.txt" 2>&1 || { tail -40 "$out/log$1.txt"; exit 1; }
  grep -E '"seconds"|"mean_remaining"' "$out/log$1.txt" | head -2
}
run .main-1 "$PWD/main-src/src"
run .branch-1 ""
run .main-2 "$PWD/main-src/src"
run .branch-2 ""
uv run --no-sync python research/948/same.py "$out"
