# One paired measurement of ticket #934 on one GitHub runner: the same plan on `main` (commit $2) and on this branch, one after the other,
# so the two times are of one machine (runners differ by up to 2 times). Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners N --command 'bash research/934/pair.sh $RUNNER_INDEX <sha of main>'
# Line $1 of research/934/pairs.txt is either
#   plan <args of research/881/profile_plan.py>   no budget, the exact proof: main, branch, the branch with stage stopwatches; the job fails
#                                                 when the two plain runs do not give one mean and the same counts of the search (827/same.py);
#   bench <case id>                                the family benchmark's own run of one case (`--aim-seconds 60 --gap 0.01`, its 10-minute net
#                                                 and 13 GB cap) on main, then on the branch; the job fails when both planned and the means differ.
# Each run also writes `research/934/measure.py`'s counts for the branch (outcomes against what is read, the exact draws), and its peak memory.
set -euo pipefail
job="$1"
base="$2"
out="${OUT_DIR:-out}"
mkdir -p "$out"
line="$(sed -n "${job}p" research/934/pairs.txt)"
[ -n "$line" ] || { echo "no job $job"; exit 2; }
kind="${line%% *}"
args="${line#* }"
git fetch --depth 1 origin "$base"
git worktree add --detach main-src FETCH_HEAD
main_src="$PWD/main-src/src"
if [ "$kind" = plan ]; then
  run() {  # $1: tag, $2: source folder or "", $3: mode
    CRAFTING_SOURCE="$2" uv run --no-sync python research/827/peak.py "$out/peak$1.json" -- \
      uv run --no-sync python -u research/881/profile_plan.py $args --mode "$3" --tag "$1" --out "$out" > "$out/log$1.txt" 2>&1 || { tail -40 "$out/log$1.txt"; exit 1; }
    grep -E '"seconds"|"mean_remaining"' "$out/log$1.txt" | head -2
    tail -1 "$out/log$1.txt"
  }
  run .main-1 "$main_src" plain
  run .branch-1 "" plain
  run .branch-timers "" timers
  cp "$out"/*.plain.main-1.json "$out/copy.plain.main-2.json"  # same.py wants four plain runs; one per side here, each counted twice
  cp "$out"/*.plain.branch-1.json "$out/copy.plain.branch-2.json"
  uv run --no-sync python research/827/same.py "$out"
  (ulimit -v 14000000; uv run --no-sync python -u research/934/measure.py $args --seconds 900 --out "$out" > "$out/log.measure.txt" 2>&1) || true
else
  for side in main branch; do
    src=""; [ "$side" = main ] && src="$main_src"
    PYTHONPATH="$src" uv run --no-sync python -c "import crafting_system; print('$side plans with', crafting_system.__file__)"
    PYTHONPATH="$src" uv run --no-sync python -u .github/scripts/family_bench.py run --part 1/1 --only "$args" --aim-seconds 60 --gap 0.01 --out "$out/$side" > "$out/log.$side.txt" 2>&1 || true
    tail -3 "$out/log.$side.txt"
  done
  uv run --no-sync python research/934/same_bench.py "$out" "$args"
  (ulimit -v 14000000; uv run --no-sync python -u research/934/measure.py --case "$args" --seconds 600 --out "$out" > "$out/log.measure.txt" 2>&1) || true
fi
