# bash uled.sh DUMPDIR OUTDIR ROUTE LEAD [RULE] [UPPER] : uled.py on DUMPDIR/k-ROUTE.pkl, one process, one thread, 12 GB of address space,
# LIMIT seconds (default 3000) and a timeout of the limit plus 10 minutes; run from the worktree's root. LEAD file:NAME reads OUTDIR/NAME.npy.
# Output OUTDIR/u-ROUTE-LEAD-RULE-UPPER.log and .tsv; the exit line is appended to the log.
D=$1; O=$2; R=$3; L=$4; [ "$7" = BEST=1 ] && export BEST=1; export RULE=${5:-gap:0.5} UPPER=${6:-restart} LIMIT=${LIMIT:-3000}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
HERE=$(dirname "$(readlink -f "$0")")
ulimit -v 12000000
case $L in file:*) A="file:$O/${L#file:}.npy" ;; *) A=$L ;; esac
N=$(echo "$R-$L${BEST:+@best}-$RULE-$UPPER" | sed 's/,/_/g; s/[+:]/-/g')
timeout $((LIMIT + 600)) uv run --no-sync python -u "$HERE/uled.py" "$D/k-$R.pkl" "$A" "$O/u-$N.tsv" > "$O/u-$N.log" 2>&1
echo "exit $? $R $L $RULE $UPPER $(date +%T) load $(uptime | sed 's/.*load average: //; s/,.*//')" >> "$O/u-$N.log"
