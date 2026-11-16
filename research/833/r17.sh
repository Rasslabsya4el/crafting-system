# R17 (the lightning Talisman, its imprint) through the command at the planner's default settings, judged against the guide's route, with
# the peak memory and the route page (ticket #833). Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 1 --timeout-minutes 45 --command 'bash research/833/r17.sh'
# `bash research/833/r17.sh plan` plans without the guide's route: with `--route` a target of fewer than MIN_OFFERS offers is walked first to
# know its size (`_plan.make_plan`, #986), so the envelope search is measured alone this way.
set -euo pipefail
out="${OUT_DIR:-out}"
mkdir -p "$out"
stem=r17-lightning-talisman
start=$(date +%s)
uv run --no-sync python research/827/peak.py "$out/peak.$stem.json" -- uv run --no-sync python -u -m crafting_system.cli \
  "examples/targets/$stem.yaml" $([ "${1:-}" = plan ] || echo --route "examples/routes/$stem.yaml") --progress --verify --json "$out/$stem.policy.json" > "$out/$stem.txt" 2> "$out/$stem.log" || echo "exit $?"
echo "seconds $(( $(date +%s) - start ))"
cat "$out/peak.$stem.json"; echo
tail -40 "$out/$stem.log"
head -60 "$out/$stem.txt"
