#!/bin/bash
# r.sh TAG ROUTE PROCS WORKTREE LEADFILE [ENV=VAL...] : kd.py on ROUTE with the src of WORKTREE (python of t1310's venv); waits for load+PROCS<=22 and 20 GB free
TAG=$1; R=$2; P=$3; WT=$4; LF=$(readlink -f "$5"); shift 5
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CRAFTING_CACHE_DIR="/root/projects/crafting system/.claude/scratch/crafting-cache" CRAFTING_WORKERS=$P
S="/root/projects/crafting system/.claude/scratch/t1310"
W="/root/projects/crafting system/.claude/worktrees/$WT"
PY="/root/projects/crafting system/.claude/worktrees/t1310/.venv/bin/python"
until [ $(( $(awk '{print int($1+0.5)}' /proc/loadavg) + P )) -le 22 ] && [ $(free -g | awk '/Mem:/{print $7}') -ge 20 ]; do sleep 30; done
echo "start $(date +%T) load $(cut -d' ' -f1 /proc/loadavg) head $(git -C "$W" rev-parse --short HEAD) workers $P $*" > "$S/$TAG.log"
cd "$W" && env "$@" LEAD="$(cat "$LF" | sed 's/^LEAD=//')" DUMP="$S/$TAG.pkl" PYTHONPATH="$W/src" timeout 80m systemd-run --scope -q -p MemoryMax=16G -p MemorySwapMax=0 "$PY" -u "$S/kd.py" .github/scripts/benchmark_routes.py $R "$S/$TAG" --net >> "$S/$TAG.log" 2>&1
echo "exit $? end $(date +%T) load $(cut -d' ' -f1 /proc/loadavg)" >> "$S/$TAG.log"
