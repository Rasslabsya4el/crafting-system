"""Print one family case planned on main and on the branch (research/934/pair.sh, `bench` jobs); fail when both planned and the means differ.

    python research/934/same_bench.py OUT_DIR CASE_ID
"""

import json
import sys
from pathlib import Path

folder, case = Path(sys.argv[1]), sys.argv[2]
rows = {}
for side in ("main", "branch"):
    found = list((folder / side).glob(f"**/cases/{case.replace('/', '__')}.plan.json"))
    if not found:
        print(side, "no record")
        rows[side] = None
        continue
    record = json.loads(found[0].read_text(encoding="utf-8"))
    plan = (record.get("stages") or {}).get("plan") or {}
    rows[side] = record
    print(side, record.get("status"), f"{plan.get('seconds')} s", f"peak {plan.get('peak_mb')} MB", "mean", repr(record.get("plan", {}).get("mean_remaining")), str(record.get("reason") or "")[:160], flush=True)
both = [rows[side] for side in ("main", "branch") if rows[side] is not None and rows[side].get("status") == "planned"]
if len(both) == 2 and both[0]["plan"]["mean_remaining"] != both[1]["plan"]["mean_remaining"]:
    print("the means differ", flush=True)
    sys.exit(1)
print("planned on both, one mean" if len(both) == 2 else "not planned on both: no mean to compare", flush=True)
