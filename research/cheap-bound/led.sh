# bash led.sh DUMPDIR OUTDIR ROUTE RULE LEAD... : led.py on DUMPDIR/k-ROUTE.pkl for each LEAD in turn, one process, one thread
# output OUTDIR/led-ROUTE-LEAD-RULE.log and .tsv (commas, plus signs and colons of the names written as _ and -)
D=$1; O=$2; R=$3; RU=$4; shift 4
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
HERE=$(dirname "$(readlink -f "$0")")
for L in "$@"; do
  N=$(echo "$L-$RU" | sed 's/,/_/g; s/[+:]/-/g')
  RULE=$RU timeout 80m python -u "$HERE/led.py" "$D/k-$R.pkl" "$L" "$O/led-$R-$N.tsv" > "$O/led-$R-$N.log" 2>&1
  echo "exit $? $R $L $RU $(date +%T)"
done
