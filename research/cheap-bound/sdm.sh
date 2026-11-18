# bash sdm.sh OUTDIR LIMIT ROUTE... : sdm.py over every offer of each ROUTE at once (one process and one thread each, 20 GB of address space each)
O=$1; export LIMIT=$2; shift 2
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
HERE=$(dirname "$(readlink -f "$0")")
for R in "$@"; do
  (ulimit -v 20000000; timeout $((LIMIT + 600)) python -u "$HERE/sdm.py" "$R" "$O/sdm-$R-${OFFERS:-all}.json" > "$O/sdm-$R-${OFFERS:-all}.log" 2>&1; echo "exit $? $R $(date +%T)") &
done
wait
