"""#1276: read seed/ROUTE.json (seed.py) and print, per route, what a concrete seed rule holds of the guide's labels, and its size.
Rule P(K): for each necessary goal leaf open at the start, the K offers of least cost / chance of passing that leaf in one use (chance from the pool bound, a craft 1).
Tools: offers with no chance on any leaf, by what they declare: fracture, metamod, veil chain (veils / needs the placeholder), imprint chain, other (removals, rarity moves, add/remove with no bound).
"""
import json, sys, math
from pathlib import Path
ROUTES = "R12 R10 R11 R05 R13 R08 R09 R04 R14 R17 R20 R06 R24".split()
def tool_type(r):
    d = r["decl"]
    if d["fractures"]: return "fracture"
    if d["metamod"]: return "metamod"
    if d["veils"] or d["needs_veiled"]: return "veil chain"
    if d["imprint"] or d["restore"] or d["imprints"]: return "imprint chain"
    if r["class"] == "craft" and r.get("names"): return "craft naming no goal mod"
    if r["class"] == "craft": return "removal"
    return "other"
out = []
for route in ROUTES:
    p = Path("seed") / f"{route}.json"
    if not p.exists():
        print(route, "MISSING"); continue
    j = json.loads(p.read_text())
    rows = [r for r in j["rows"] if r["class"] != "restart"]
    leaves = [str(i) for i in j["open"]]
    rank = {}  # label -> (leaf, rank, ratio)
    tops = {}
    for leaf in leaves:
        prov = sorted(((r["cost"] / r["chances"][leaf], r["cost"], r["label"]) for r in rows if r["chances"].get(leaf, 0) > 0))
        tops[leaf] = prov
        for n, (ratio, cost, label) in enumerate(prov, 1):
            if label not in rank or n < rank[label][1]:
                rank[label] = (leaf, n, ratio)
    providers = {r["label"] for r in rows if any(v > 0 for v in r["chances"].values())}
    tools = [r for r in rows if r["label"] not in providers and r["kind"] != "fossil-set" and tool_type(r) != "craft naming no goal mod"]
    inert = [r for r in rows if r["label"] not in providers and tool_type(r) == "craft naming no goal mod"]
    nec = {str(i) for i in j["necessary"]}
    by_type = {}
    for r in tools:
        by_type.setdefault(tool_type(r), []).append(r["label"])
    by_label = {r["label"]: r for r in rows}
    print(f"\n=== {route}: {j['offers']} offers ({j['after_twins']} after twins), start {j['start_rarity']}, rounds apply {j['rounds_apply']}, open leaves {len(leaves)} ({len([l for l in leaves if l in nec])} necessary, U {len(j['U'])}), providers {len(providers)}, crafts naming no goal mod {len(inert)}, tools {len(tools)}: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(by_type.items())))
    for leaf in leaves:
        print(f"  leaf {leaf}{'' if leaf in nec else ' (k-of-n)'} {j['leaf_labels'].get(leaf, '')[:70]!r}: " + "; ".join(f"{label[:44]} {ratio:.4g}" for ratio, cost, label in tops[leaf][:4]) + f"  ({len(tops[leaf])} providers)")
    held = {}
    for label in j["guide"]:
        r = by_label.get(label)
        if r is None:
            held[label] = "NOT OFFERED (or a twin's label)"
        elif label in rank:
            leaf, n, ratio = rank[label]
            held[label] = f"provider, rank {n} on leaf {leaf} (cost/chance {ratio:.4g}, cost {r['cost']:.4g})"
        else:
            held[label] = f"tool: {tool_type(r)} [{r['class']}/{r['floor_kind']}] cost {r['cost']:.4g}"
        print(f"  GUIDE {label[:60]!r}: {held[label]}")
    for K in (1, 2, 3, 5):
        seed = {label for leaf in leaves for _, _, label in tops[leaf][:K]}
        g_prov = [l for l in j["guide"] if l in rank]
        inside = [l for l in g_prov if l in seed]
        print(f"  P({K}): {len(seed)} offers; guide providers inside {len(inside)}/{len(g_prov)}; with every tool {len(seed) + len(tools)} offers; missing providers: {[l[:40] for l in g_prov if l not in seed]}")
    out.append((route, j, rank, tools, by_type))
