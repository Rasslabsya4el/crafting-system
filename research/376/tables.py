"""Markdown tables for the note of ticket #376 from the result files of junk_bound.py.

    python research/376/tables.py R04=path/r04.bounds.json R14=path/r14.bounds.json S02=path/s02.bounds.json

Prints (1) the ratio bound / exact of every key on every route with the number of abstract states, (2) what each bound cuts
(competitive actions and reachable classes against the incumbent), (3) the time and memory of the runs.
"""

import json
import sys

routes = {}
for argument in sys.argv[1:]:
    name, _, path = argument.partition("=")
    routes[name] = json.load(open(path, encoding="utf-8"))

keys = []
for data in routes.values():
    for key in data["bounds"]:
        if key not in keys:
            keys.append(key)

print("| Key | " + " | ".join(f"{name} abstract states | {name} bound / exact" for name in routes) + " |")
print("| --- | " + " | ".join("---: | ---:" for _ in routes) + " |")
for key in keys:
    cells = []
    for data in routes.values():
        row = data["bounds"].get(key)
        if row is None:
            cells += ["-", "-"]
        elif "ratio" not in row:
            cells += [f"{row['abstract_states']:,}", "not built (edges over the limit)"]
        else:
            cells += [f"{row['abstract_states']:,}", f"{100 * row['ratio']:.2f}%"]
    print(f"| `{key}` | " + " | ".join(cells) + " |")

print()
for name, data in routes.items():
    print(f"**{name}** exact {data['exact']['start_value']:.4f}; states {data['states']:,}, classes {data['classes']:,}; optimal policy "
          f"{data['exact'].get('optimal_policy_classes', 0):,} classes; walk {data['walk_seconds']} s; whole run {data['total_seconds']} s; peak {data['peak_rss_mb']:,} MB")
    print()
    print("| Bound | Upper bound | Sweeps | Bound / exact | Competitive actions | Classes reachable | Raw states reachable |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for c in data["cuts"]:
        print(f"| `{c['key']}` | {c['upper_bound']} | {c['sweeps']} | {100 * c['lb_start_over_exact']:.3f}% | {c['competitive_actions']:,} of {c['of_actions']:,} | "
              f"{c['classes_reachable']:,} of {c['of_classes']:,} ({100 * c['classes_reachable'] / c['of_classes']:.1f}%) | "
              f"{c['raw_states_in_reached_classes']:,} of {c['of_raw_states']:,} ({100 * c['raw_states_in_reached_classes'] / c['of_raw_states']:.1f}%) |")
    print()
    if data.get("tolerance_envelopes"):
        print("| Error of the bound (every action within it of the best is kept) | Classes reachable | Raw states reachable |")
        print("| --- | ---: | ---: |")
        for t in data["tolerance_envelopes"]:
            print(f"| {100 * t['eps']:g}% | {t['classes']:,} ({100 * t['classes'] / data['classes']:.1f}%) | {t['raw_states']:,} ({100 * t['raw_states'] / data['states']:.1f}%) |")
        print()
    print("| Key | Build seconds (given the walked graph) | Abstract actions | Abstract edges | Violations |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for key, row in data["bounds"].items():
        if "ratio" in row:
            print(f"| `{key}` | {row.get('total_seconds')} | {row.get('abstract_actions'):,} | {row.get('abstract_edges'):,} | {row.get('violations')} |")
    print()
