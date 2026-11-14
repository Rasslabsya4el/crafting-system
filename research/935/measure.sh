# The measurement of ticket #935 on GitHub runners, started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 7 --command 'bash research/935/measure.sh $RUNNER_INDEX'
# Line $1 of research/935/measure.txt: a plan and how it is measured (by_action.py, or profile_plan.py --mode cprofile).
set -euo pipefail
job="$1"
out="${OUT_DIR:-out}"
mkdir -p "$out"
line="$(sed -n "${job}p" research/935/measure.txt)"
[ -n "$line" ] || { echo "no job $job"; exit 2; }
how="${line%% *}"
plan="${line#* }"
case "$how" in
  by_action) uv run --no-sync python -u research/935/by_action.py $plan --out "$out" ;;
  cprofile) uv run --no-sync python -u research/881/profile_plan.py $plan --mode cprofile --top 80 --out "$out" ;;
  *) echo "no way $how"; exit 2 ;;
esac
