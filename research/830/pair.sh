# One paired measurement of ticket #830 on one GitHub runner: main (commit $2) and this branch one after the other, so the two times are
# of one machine. Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners N --command 'bash research/830/pair.sh $RUNNER_INDEX <sha of main>'
# Line $1 of research/830/pairs.txt is either `r10 ARGS` (research/830/r10_roll.py ARGS, on each side's source) or `family IDS` (the family
# cases IDS with the family benchmark's settings, research/829/family_pair.sh).
set -euo pipefail
job="$1"
base="$2"
out="${OUT_DIR:-out}"
mkdir -p "$out"
line="$(sed -n "${job}p" research/830/pairs.txt)"
[ -n "$line" ] || { echo "no job $job"; exit 2; }
kind="${line%% *}"
args="${line#* }"
if [ "$kind" = family ]; then
  exec bash research/829/family_pair.sh "$base" "$args"
fi
git fetch --depth 1 origin "$base"
git worktree add --detach main-src FETCH_HEAD
for side in main branch; do
  echo "== $side"
  if [ "$side" = main ]; then src="$PWD/main-src/src"; else src="$PWD/src"; fi
  PYTHONPATH="$src" uv run --no-sync python research/827/peak.py "$out/peak.$side.json" -- \
    env PYTHONPATH="$src" uv run --no-sync python -u research/830/r10_roll.py $args | tee "$out/r10.$side.json"
  cat "$out/peak.$side.json"; echo
done
