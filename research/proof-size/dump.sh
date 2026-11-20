#!/bin/bash
# t1360: dump the first bound's model of ROUTE (kd2.py) on this worktree's main; 3 workers, 12 GB net, 16 GB cgroup.
R=$1; S="/root/projects/crafting system/.claude/scratch/t1360"; W="/root/projects/crafting system/.claude/worktrees/t1360"
export CRAFTING_CONFIG="/root/projects/crafting system/.claude/scratch/t1341/net12g.toml" CRAFTING_CACHE_DIR="/root/projects/crafting system/.claude/scratch/crafting-cache"
export CRAFTING_WORKERS=3 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONUNBUFFERED=1 DUMP="$S/k-$R.pkl" MINKEYS=${MINKEYS:-1000}
cd "$W"
echo "$(date '+%F %T') START $R head $(git rev-parse --short HEAD) load $(cut -d' ' -f1 /proc/loadavg)" > "$S/k-$R.log"
systemd-run --scope -q --unit "t1360-k-$R" -p MemoryMax=16G -p MemorySwapMax=0 timeout -k 60 90m .venv/bin/python -u "$S/kd2.py" .github/scripts/benchmark_routes.py $R "$S/out-$R" --net >> "$S/k-$R.log" 2>&1
echo "$(date '+%F %T') END exit $?" >> "$S/k-$R.log"
