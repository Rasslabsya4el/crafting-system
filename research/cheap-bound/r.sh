# bash r.sh TAG ROUTE PROCS WORKTREE LEADFILE [ENV=VAL...] : kd.py on ROUTE with the src of WORKTREE (python of t1310's venv); waits for load+PROCS<=22 and 20 GB free
TAG=$1; R=$2; P=$3; WT=$4; LF=$(readlink -f "$5"); shift 5
ROOT=$(dirname "$(git -C "$(dirname "$(readlink -f "$0")")" rev-parse --path-format=absolute --git-common-dir)")  # the main folder of the repository
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CRAFTING_CACHE_DIR="$ROOT/.claude/scratch/crafting-cache" CRAFTING_WORKERS=$P
S="$ROOT/.claude/scratch/t1310"
W="$ROOT/.claude/worktrees/$WT"
PY="$ROOT/.claude/worktrees/t1310/.venv/bin/python"
until [ $(( $(uptime | awk -F'load average: ' '{print int($2+0.5)}') + P )) -le 22 ] && [ $(free -g | awk '/Mem:/{print $7}') -ge 20 ]; do sleep 30; done
echo "start $(date +%T) load $(uptime | awk -F'load average: ' '{print $2+0}') head $(git -C "$W" rev-parse --short HEAD) workers $P $*" > "$S/$TAG.log"
cd "$W" && env "$@" LEAD="$(cat "$LF" | sed 's/^LEAD=//')" DUMP="$S/$TAG.pkl" PYTHONPATH="$W/src" timeout 80m systemd-run --scope -q -p MemoryMax=16G -p MemorySwapMax=0 "$PY" -u "$S/kd.py" .github/scripts/benchmark_routes.py $R "$S/$TAG" --net >> "$S/$TAG.log" 2>&1
echo "exit $? end $(date +%T) load $(uptime | awk -F'load average: ' '{print $2+0}')" >> "$S/$TAG.log"
