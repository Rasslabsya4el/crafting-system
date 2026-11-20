# Run with bash; REPO is the repo's main folder (env).
# t1360: cert.py runs, one process each, REWEIGHT=0; args lines "ROUTE GAP LEAD"
cd "$REPO/.claude/scratch/t1360"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 REWEIGHT=${REWEIGHT:-0}
while read R G L; do
  ( timeout 100m systemd-run --scope -q -p MemoryMax=12G -p MemorySwapMax=0 lpenv/bin/python cert.py e-$R.npz $G $L > c-$R-$G-${L//[:\/]/_}.log 2>&1 ) &
done
wait
