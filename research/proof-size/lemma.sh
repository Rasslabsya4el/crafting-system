#!/bin/bash
# Run with bash; REPO is the repo's main folder (env). t1363: the reroll lemma's checks, its lower model's value and its certificates.
# The dumps (e-ROUTE.npz, their .parts.pkl and -bisim.npy, from #1360's export.py and bisim.py) and the scipy venv lpenv are #1360's,
# under .claude/scratch/t1360; the run works in .claude/scratch/t1363 with copies of the dumps. One process at a time, one thread.
set -e
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
T="$REPO/.claude/scratch/t1363"; S="$REPO/.claude/scratch/t1360"; P="$S/lpenv/bin/python"; HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$T"; cd "$T"; cp -n "$S"/e-R24.npz* "$S"/e-R13.npz* "$S"/e-R04.npz* "$S"/e-R24-bisim.npy "$S"/e-R13-bisim.npy "$S"/e-R04-bisim.npy .
cap() { timeout 90m systemd-run --scope -q -p MemoryMax=16G -p MemorySwapMax=0 "$@"; }
for a in "R24 shock" "R24 core" "R24 corelock" "R24 split" "R13 natural" "R04 essence" "R04 frac"; do
  set -- $a; "$P" "$HERE/lemma.py" $1 $2 > lemma-$1-$2.log 2>&1
done
for a in "R24 shock" "R24 corelock" "R24 split" "R13 natural"; do
  set -- $a; FREE=free-$1-$2.npz REWEIGHT=1 cap "$P" "$HERE/cert.py" e-$1.npz 0.01 floor > c-$1-$2.log 2>&1 || true
done
FREE=free-R13-natural.npz ONEZ=1 REWEIGHT=1 cap "$P" "$HERE/cert.py" e-R13.npz 0.01 floor > c-R13-natural-onez.log 2>&1 || true
for g in 0.01 0.05 0.10; do FREE=free-R04-essence.npz REWEIGHT=1 cap "$P" "$HERE/cert.py" e-R04.npz $g floor > c-R04-essence-$g.log 2>&1 || true; done
for g in 0.01 0.05; do FREE=free-R04-frac.npz REWEIGHT=1 cap "$P" "$HERE/cert.py" e-R04.npz $g floor > c-R04-frac-$g.log 2>&1 || true; done
for a in "R24 split" "R13 natural" "R04 essence" "R04 frac"; do set -- $a; "$P" "$HERE/vi.py" $1 free-$1-$2.npz > vi-$1-$2.log 2>&1; done
"$P" "$HERE/bnames.py" R24 free-R24-split.npz > bnames-R24.log 2>&1; "$P" "$HERE/bnames.py" R13 free-R13-natural.npz > bnames-R13.log 2>&1
