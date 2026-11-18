# bash dled.sh DUMPDIR OUTDIR ROUTE MODE [RULE] : dled.py on DUMPDIR/k-ROUTE.pkl (first group from DUMPDIR/lead-ROUTE.txt), one process, one thread,
# 12 GB of address space, a limit of LIMIT seconds (default 10800) and a timeout of the limit plus 20 minutes; run from the worktree's root.
# Output OUTDIR/dled-ROUTE-MODE[-max].log, .tsv and .pid; the exit line is appended to the log.
D=$1; O=$2; R=$3; M=$4; export RULE=${5:-mass:0.5}; export LIMIT=${LIMIT:-10800}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
HERE=$(dirname "$(readlink -f "$0")")
ulimit -v 12000000
N=$M${MAX:+-max}  # MAX=1: the pinned variant (dled.py)
echo $$ > "$O/dled-$R-$N.pid"  # this wrapper's pid: wait on it
timeout $((LIMIT + 1200)) uv run --no-sync python -u "$HERE/dled.py" "$R" "$D/k-$R.pkl" "$D/lead-$R.txt" "$M" "$O/dled-$R-$N.tsv" > "$O/dled-$R-$N.log" 2>&1
echo "exit $? $R $M $RULE MAX=$MAX $(date +%T) load $(cut -d' ' -f1 /proc/loadavg)" >> "$O/dled-$R-$N.log"
