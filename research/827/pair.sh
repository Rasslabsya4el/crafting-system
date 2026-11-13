# One paired measurement of ticket #827 on one GitHub runner: the same plan on `main` (commit $2) and on this branch, one after the other,
# so the two times are of one machine (runners differ by up to 2 times). Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 8 --command 'bash research/827/pair.sh $RUNNER_INDEX <sha of main>'
# The plan is line $1 of research/827/pairs.txt, planned by research/881/profile_plan.py (no budget: the exact proof, the same work on both
# sides). Order: main, branch, main, branch (plain), then the branch with stage stopwatches. `time -v` gives each run's peak memory.
set -euo pipefail
job="$1"
base="$2"
out="${OUT_DIR:-out}"
mkdir -p "$out"
plan="$(sed -n "${job}p" research/827/pairs.txt)"
[ -n "$plan" ] || { echo "no job $job"; exit 2; }
git fetch --depth 1 origin "$base"
git worktree add --detach main-src FETCH_HEAD
run() {  # $1: tag, $2: source folder or "", $3: mode
  CRAFTING_SOURCE="$2" /usr/bin/time -v -o "$out/time$1.txt" uv run --no-sync python -u research/881/profile_plan.py $plan --mode "$3" --tag "$1" --out "$out" > "$out/log$1.txt" 2>&1 || { tail -40 "$out/log$1.txt"; exit 1; }
  grep -E '"seconds"|"mean_remaining"' "$out/log$1.txt" | head -2
  grep -E "Maximum resident" "$out/time$1.txt"
}
run .main-1 "$PWD/main-src/src" plain
run .branch-1 "" plain
run .main-2 "$PWD/main-src/src" plain
run .branch-2 "" plain
run .branch-timers "" timers
