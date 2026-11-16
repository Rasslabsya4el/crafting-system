# R03's Eldritch implicit (ticket #835): the research target r03-implicits.yaml (R03's finished explicits given, the implicit wish asked)
# through the command at the planner's default settings, with --verify, the peak memory and the route page. R03 itself stops at its
# missing start price (#483). Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 1 --timeout-minutes 30 --command 'bash research/835/r03.sh'
set -euo pipefail
out="${OUT_DIR:-out}"
mkdir -p "$out"
stem=r03-implicits
start=$(date +%s)
uv run --no-sync python research/827/peak.py "$out/peak.$stem.json" -- uv run --no-sync python -u -m crafting_system.cli \
  "research/835/$stem.yaml" --progress --verify --json "$out/$stem.policy.json" > "$out/$stem.txt" 2> "$out/$stem.log" || echo "exit $?"
echo "seconds $(( $(date +%s) - start ))"
cat "$out/peak.$stem.json"; echo
tail -40 "$out/$stem.log"
head -80 "$out/$stem.txt"
