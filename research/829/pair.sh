# One paired measurement of ticket #829 on one GitHub runner: the same exact plan (no budget, gap 0) on `main` (commit $2) and on this
# branch, one after the other, so the two times are of one machine (runners differ by up to 2 times). Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 7 --command 'bash research/829/pair.sh $RUNNER_INDEX <sha of main>'
# Line $1 of research/829/pairs.txt holds the arguments of research/881/profile_plan.py. On main a fossil case of 40 offers or more is the
# bound pruning (`solve_pruned`) and the envelope search grows its model; on the branch both are the envelope search with each offer's floor.
# So the search counts may differ: the job fails only when the two means differ by more than 1e-9 of themselves (research/829/same.py).
# A third argument `main` or `branch` runs that side alone (R08: the two sides in sequence pass the hour), and compares nothing.
set -euo pipefail
job="$1"
base="$2"
side="${3:-both}"
out="${OUT_DIR:-out}"
mkdir -p "$out"
args="$(sed -n "${job}p" research/829/pairs.txt)"
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
[ "$side" = branch ] || run .main "$main_src"
[ "$side" = main ] || run .branch ""
[ "$side" != both ] || uv run --no-sync python research/829/same.py "$out"
