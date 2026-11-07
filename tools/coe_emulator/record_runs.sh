#!/bin/bash
# Record one run of every case of a check file, for one runner of a heavy run (ticket #617):
#
#   tools/coe_emulator/record_runs.sh CHECKS.json REPEATS SEED_BASE OUT_DIR
#
# Runner i of N (RUNNER_INDEX, default 1) uses the seeds SEED_BASE + 100 * i + (the case's place in the file), so that no two runs of a case share a seed; REPEATS
# is per run. Keep a run under a minute on a PC (about 2,500 draws of a rare item); on a runner the N runs together give the sample. Merge the run files
# with `record.py merge` (see tools/coe_emulator/README.md). Needs the local copy of the site (`emulator.py fetch`) and Playwright, as `record.py` does.
set -e
checks="$1"; repeats="$2"; base="$3"; out="$4"
index="${RUNNER_INDEX:-1}"
ids=$(python -I -c "import json,sys; print(' '.join(c['id'] for c in json.load(open(sys.argv[1], encoding='utf-8'))))" "$checks")
place=0
for id in $ids; do
  seed=$((base + 100 * index + place))
  # the page sometimes fails to set the item up (a TypeError in `poec_updateActionEnabling`) or to load in time (3 of 16 runner starts in the run of #617):
  # the same seed is tried again, which repeats the counts if it works
  for attempt in 1 2 3; do
    python tools/coe_emulator/record.py run "$checks" "$id" --seed "$seed" --repeats "$repeats" --out "$out/$id-$seed.json" && break
    [ "$attempt" = 3 ] && exit 1
    echo "attempt $attempt of $id failed, trying again"
  done
  place=$((place + 1))
done
