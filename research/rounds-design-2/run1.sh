#!/bin/bash
# run1.sh TAG ROUTE PROCS [ENV=VAL...] : traced benchmark_routes.py ROUTE --net (site settings) in worktree t1276x (main 2028e28b);
# waits for load+PROCS+1<=22 and 20 GB available; 16 GB scope, planner memory net 12 GB, 30 min timeout
TAG=$1; R=$2; P=$3; shift 3
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CRAFTING_CACHE_DIR="/root/projects/crafting system/.claude/scratch/crafting-cache" CRAFTING_WORKERS=$P
S="/root/projects/crafting system/.claude/scratch/t1276c"
W="${WT:-/root/projects/crafting system/.claude/worktrees/t1276x}"
sleep $(( RANDOM % 20 ))
until [ $(( $(awk '{print int($1+0.5)}' /proc/loadavg) + P + 1 )) -le 22 ] && [ $(free -g | awk '/Mem:/{print $7}') -ge 20 ]; do sleep 30; done
echo "start $(date +%T) load $(cut -d' ' -f1 /proc/loadavg) head $(git -C "$W" rev-parse --short HEAD) workers $P $*" > "$S/$TAG.log"
cd "$W" && env "$@" PYTHONPATH="$W/src" timeout ${TMO:-30m} systemd-run --scope -q -p MemoryMax=16G -p MemorySwapMax=0 "$W/.venv/bin/python" -u -c "import sys, runpy; import crafting_system.budget as b; b.MEMORY_SHARE = 12000 / (b.physical_mb() or 60000); sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')" "$S/tp.py" .github/scripts/benchmark_routes.py $R "$S/$TAG" --net >> "$S/$TAG.log" 2>&1
echo "exit $? end $(date +%T) load $(cut -d' ' -f1 /proc/loadavg)" >> "$S/$TAG.log"
