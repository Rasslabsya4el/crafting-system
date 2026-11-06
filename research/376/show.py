"""Print the bounds and cuts of a junk_bound.py result file as short tables: python research/376/show.py FILE.json"""

import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
print({k: d.get(k) for k in ("target", "states", "classes", "walk_seconds", "total_seconds", "peak_rss_mb")})
print("exact", d.get("exact"))
print(f"{'key':28s} {'abstract':>9s} {'ratio':>8s} {'viol':>5s} {'sec':>6s}  in optimal policy (median / p10)")
for k, v in d["bounds"].items():
    r = v.get("ratio")
    inside = v.get("ratio_in_optimal_policy") or {}
    print(f"{k:28s} {v.get('abstract_states', 0):9,d} {'-' if r is None else format(r, '8.4f'):>8s} {str(v.get('violations', '-')):>5s} {v.get('total_seconds', '-')!s:>6s}  {inside.get('median', '-')} / {inside.get('p10', '-')}")
print()
print(f"{'key':28s} {'ub':9s} {'sw':>3s} {'lb/exact':>9s} {'comp.actions':>13s} {'of':>9s} {'classes':>9s} {'of':>9s} {'raw states':>11s} {'of':>9s}")
for c in d["cuts"]:
    print(f"{c['key']:28s} {c['upper_bound']:9s} {c['sweeps']:3d} {c['lb_start_over_exact']:9.4f} {c['competitive_actions']:13,d} {c['of_actions']:9,d} {c['classes_reachable']:9,d} {c['of_classes']:9,d} {c['raw_states_in_reached_classes']:11,d} {c['of_raw_states']:9,d}")
