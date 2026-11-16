# Family cases of ticket #833 on main ($1, a commit) and on this branch, one after the other on one GitHub runner, with the family bench's
# default settings (no aim: the net alone) and no walk, so the two outcomes are of one machine. $1 is a full sha (a fetch by a short one
# fails). $2: the case ids, comma-separated; with $3 (the runner's index) only the $3-th of them, so one dispatch pairs each case on its own runner.
# Started only through the dispatcher:
#   python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners 1 --timeout-minutes 55 --command 'bash research/833/pair.sh <main sha> <ids> $RUNNER_INDEX'
set -euo pipefail
base="$1"
only="$2"
if [ -n "${3:-}" ]; then only="$(echo "$2" | cut -d, -f"$3")"; fi
[ -n "$only" ] || { echo "no case $3"; exit 2; }
out="${OUT_DIR:-out}"
mkdir -p "$out/main" "$out/branch"
git fetch --depth 1 origin "$base"
git worktree add --detach main-src FETCH_HEAD
settings="--part 1/1 --walk-seconds 1 --deadline-minutes 50"
PYTHONPATH="$PWD/main-src/src" uv run --no-sync python -u main-src/.github/scripts/family_bench.py run --only "$only" --out "$out/main" $settings
uv run --no-sync python -u .github/scripts/family_bench.py run --only "$only" --out "$out/branch" $settings
for side in main branch; do
  echo "== $side"
  uv run --no-sync python - "$out/$side" <<'EOF'
import json, pathlib, sys
for p in sorted(pathlib.Path(sys.argv[1]).glob("part-*.json")):
    for r in json.loads(p.read_text(encoding="utf-8"))["records"]:
        plan = r.get("plan") or {}
        print(json.dumps({"case": r["case"]["id"], "status": r.get("status"), "reason": (r.get("reason") or "")[:300], "mean": plan.get("mean_remaining"),
                          "reach": plan.get("reach"), "wall": r.get("wall_seconds"), "lower": r.get("lower"), "upper": r.get("upper")}))
EOF
done
