"""#1310: the leaf-level bound counted on the reference targets, from the output of research/rounds-design/seed.py (no search).

    uv run --no-project --with scipy python leaflp.py seed/R04.json ...

For every NECESSARY wanted mod that is open at the start (a leaf l), any plan must make l pass a first time. If one use of offer a makes an open
leaf l pass with chance at most p_l(a) at every state, then (Wald, per leaf) the expected uses x_a of a plan obey sum_a p_l(a) x_a >= 1 for
every l, so the plan costs at least  min sum_a c_a x_a  s.t. those rows, x >= 0  (the "expected uses" LP).
seed.py's chances are read at the shapes the floors know (the start's fractured mods, no metamod): they are NOT yet proofs over every state.
Two figures: LO counts an offer with no bound today (floor kind terminal, a skipped fossil set) as chance 1 on every leaf (what today's
declarations prove); HI counts it as 0 (the most the LP could prove if every method had a per-leaf bound as favourable to the bound as possible)."""
import json, sys
from scipy.optimize import linprog

def lp(rows, leaves, mode):
    c, cols = [], []
    for r in rows:
        ch = [r["chances"].get(str(l), 0.0) for l in leaves]
        if r["unknown"] or r["floor_kind"] == "terminal":
            ch = [1.0 if mode == "LO" else x for x in ch] if mode == "LO" else ch
        if r["floor_kind"] == "refused" or not any(ch):
            continue
        c.append(r["cost"]); cols.append((r, ch))
    if not cols:
        return None, []
    A = [[-ch[i] for _, ch in cols] for i in range(len(leaves))]
    res = linprog(c, A_ub=A, b_ub=[-1.0] * len(leaves), bounds=(0, None), method="highs")
    if res.status != 0:
        return None, []
    return res.fun, sorted(((x, r["label"], r["cost"]) for x, (r, _) in zip(res.x, cols) if x > 1e-9), reverse=True)

for path in sys.argv[1:]:
    d = json.load(open(path))
    rows = d["rows"]
    leaves = [l for l in d["open"] if l in d["necessary"]]
    guide = d["guide"]
    by = {r["label"]: r for r in rows}
    out = [f"{d['route']}: offers {d['after_twins']}, open leaves {len(d['open'])} (necessary {len(leaves)}), today's floor rho {d['rho']:.4g}"]
    for mode in ("LO", "HI"):
        val, sup = lp(rows, leaves, mode)
        out.append(f"  LP {mode}: {val if val is None else round(val, 2)} ; offers used: " + "; ".join(f"{l} x{x:.2f} ({c:.4g} c)" for x, l, c in sup[:8]))
        if mode == "HI":
            names = {l for _, l, _ in sup}
            out.append(f"  guide's labels: {len(guide)}; in the LP's offers: {sorted(g for g in guide if g in names)}; with a chance on a necessary open leaf: "
                       f"{sorted(g for g in guide if g in by and any(by[g]['chances'].get(str(l), 0) > 0 for l in leaves))}; with none: "
                       f"{sorted(g for g in guide if g in by and not any(by[g]['chances'].get(str(l), 0) > 0 for l in leaves))}; not offered under that label: {sorted(g for g in guide if g not in by)}")
    per = []
    for l in leaves:
        best = min(((r["cost"] / r["chances"][str(l)], r["label"]) for r in rows if r["chances"].get(str(l), 0) > 0 and r["floor_kind"] != "refused"), default=(None, "-"))
        per.append(f"{d['leaf_labels'][str(l)][:40]}: {best[0] if best[0] is None else round(best[0], 2)} by {best[1]}")
    out.append("  per leaf, least cost over chance: " + " | ".join(per))
    kinds = {}
    for r in rows:
        kinds[r["floor_kind"]] = kinds.get(r["floor_kind"], 0) + 1
    out.append(f"  offers by floor kind: {kinds}; with no per-leaf bound today: {sum(1 for r in rows if r['unknown'] or r['floor_kind'] == 'terminal')}")
    print("\n".join(out), flush=True)
