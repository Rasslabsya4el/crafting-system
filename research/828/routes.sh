# R24 (runner 1) or R07 (runner 2) through the planner at its default settings, with the peak memory (ticket #828). Started only through
# the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 2 --timeout-minutes 30 --command 'bash research/828/routes.sh $RUNNER_INDEX'
set -euo pipefail
out="${OUT_DIR:-out}"
mkdir -p "$out"
stem=$([ "$1" = 1 ] && echo r24-avoid-shock-boots || echo r07-minion-wand)
uv run --no-sync python research/827/peak.py "$out/peak.$stem.json" -- uv run --no-sync python -u research/828/route.py "$stem" | tee "$out/$stem.log"
cat "$out/peak.$stem.json"; echo
