# Family cases of ticket #829 on main ($1, a commit) and on this branch, one after the other on one GitHub runner, with the family
# benchmark's settings (`--aim-seconds 60 --gap 0.01`), so the two times are of one machine. $2: the case ids, comma-separated.
# Started only through the dispatcher (research/829/pair.sh pattern). Main's side runs main's own family_bench.py with main's source first
# on the path. Prints each side's records (status, seconds, gap, reach, peak).
set -euo pipefail
base="$1"
only="$2"
out="${OUT_DIR:-out}"
mkdir -p "$out/main" "$out/branch"
git fetch --depth 1 origin "$base"
git worktree add --detach main-src FETCH_HEAD
settings="--aim-seconds 60 --gap 0.01 --deadline-minutes 50"
PYTHONPATH="$PWD/main-src/src" uv run --no-sync python -u main-src/.github/scripts/family_bench.py run --only "$only" --out "$out/main" $settings
uv run --no-sync python -u .github/scripts/family_bench.py run --only "$only" --out "$out/branch" $settings
for side in main branch; do
  echo "== $side"
  uv run --no-sync python - "$out/$side" <<'EOF'
import json, pathlib, sys
for p in sorted(pathlib.Path(sys.argv[1]).glob("part-*.json")):
    for r in json.loads(p.read_text(encoding="utf-8"))["records"]:
        e = r.get("envelope") or {}
        case = r.get("case") or {}
        print(json.dumps({"case": case.get("id") if isinstance(case, dict) else case, "status": r.get("status"), "reason": r.get("reason"),
                          "upper": r.get("upper"), **{k: e.get(k) for k in ("seconds", "gap", "first_upper", "expanded", "realized", "tightened", "rounds", "peak_mb")}})[:700])
EOF
done
