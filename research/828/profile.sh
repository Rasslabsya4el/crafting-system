# Profile R07 (runner 1) or R24 (runner 2) through the planner for a fixed time (ticket #828). Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 2 --timeout-minutes 30 --command 'bash research/828/profile.sh $RUNNER_INDEX 1200'
set -euo pipefail
out="${OUT_DIR:-out}"
mkdir -p "$out"
stem=$([ "$1" = 1 ] && echo r07-minion-wand || echo r24-avoid-shock-boots)
uv run --no-sync python -u research/828/profile_route.py "$stem" "$2" | tee "$out/profile.$stem.log"
