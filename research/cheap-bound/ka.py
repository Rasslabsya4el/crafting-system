"""#1310: what the parts of the bound's key cost and what a coarser key could still prove. Reads a dump of kd.py.

    python ka.py DUMP.pkl

1. The keys by part: the distinct values of each part, and the keys left when one part is dropped.
2. For each coarser key (a set of parts dropped): the model MERGED on it (a merged key takes every action of every key it holds, each kernel
   pushed to the merged keys; it is a goal when one of its keys is; it has the tip's floor when one of its keys was not worked out), solved by
   the planner's own solver. Its start value is at most the full model's (every policy of the full model is one of the merged model), and it
   is the MOST any bound stated on that coarser key can prove on these offers: the ceiling of that candidate, not the candidate.
3. The offers the merged model's cheapest policy uses from the start."""
import math, pickle, sys
from fractions import Fraction
from collections import Counter, defaultdict
from types import SimpleNamespace
from crafting_system.abstraction._pattern import CHOICE, ChoiceNode, PatternKey, PatternModel, PatternStats
from crafting_system.planner import _pattern_bound as pb

d = pickle.load(open(sys.argv[1], "rb"))
keys, goal, actions, kernels, exp = d["keys"], d["goal"], d["actions"], d["kernels"], d["expanded"]
labels, costs = d["labels"], d["costs"]
n = len(keys)
real = [i for i, k in enumerate(keys) if not isinstance(k, ChoiceNode)]
print(f"dump {sys.argv[1]}: keys {n} (choice nodes {n - len(real)}), worked out {sum(exp)}, kernels {len(kernels)}, rows {sum(len(a) for a in actions)}, offers {len(labels)}, start value {d['start_value']!r}, stopped {str(d['stopped'])[:80]}")
print("offers:", "; ".join(f"{l} {c:.4g}" for l, c in zip(labels, costs)))
F = PatternKey._fields
print("PARTS  part: distinct values | keys left when this part alone is dropped")
for f in F:
    print(f"  {f:9s} {len({getattr(keys[i], f) for i in real}):7d} | {len({keys[i]._replace(**{f: None}) for i in real}):7d}")
for f, top in (("counts", 20), ("crafted", 12), ("fractured", 8), ("flags", 6), ("tags", 6)):
    c = Counter(getattr(keys[i], f) for i in real)
    print(f"  {f}: " + " ; ".join(f"{str(v)[:110]} x{k}" for v, k in c.most_common(top)))
st = Counter(sum(1 for x in keys[i].status if "PASSING" in repr(x).upper()) for i in real)
print("  a status:", repr(keys[real[-1]].status)[:200])
print("  leaves in the status:", len(keys[real[0]].status), "; keys by leaves PASSING:", dict(sorted(st.items())))

PROJ = [("full key", ()), ("without tags", ("tags",)), ("without tags, counts", ("tags", "counts")), ("without tags, counts, veiled", ("tags", "counts", "veiled")),
        ("without tags, counts, crafted", ("tags", "counts", "crafted")), ("flags, fractured, status only", ("tags", "counts", "crafted", "held", "veiled")),
        ("flags, status only", ("tags", "counts", "crafted", "held", "veiled", "fractured")), ("status only", ("tags", "counts", "crafted", "held", "veiled", "fractured", "flags"))]
import os
if os.environ.get("COUNTS"):  # the junk counts kept coarser, the tags dropped: which coarser count keeps the value
    PROJ = [("without tags; counts as their total", ("tags",), lambda c: sum(c)), ("without tags; counts capped at 1 a side", ("tags",), lambda c: tuple(min(x, 1) for x in c)),
            ("without tags; counts capped at 2 a side", ("tags",), lambda c: tuple(min(x, 2) for x in c)), ("without tags; prefix count only", ("tags",), lambda c: c[0]), ("without tags; suffix count only", ("tags",), lambda c: c[1])]
else:
    PROJ = [(a, b, None) for a, b in PROJ]
offers = [SimpleNamespace(cost=c) for c in costs]
cheapest = d["cheapest"]
for name, drop, fc in PROJ:
    cid, cls = {}, [0] * n
    for i, k in enumerate(keys):
        pk = ("choice", i) if isinstance(k, ChoiceNode) else k._replace(**{f: None for f in drop})
        if fc is not None and not isinstance(k, ChoiceNode):
            pk = pk._replace(counts=fc(k.counts))
        cls[i] = cid.setdefault(pk, len(cid))
    nc = len(cid)
    g, e, rows = [False] * nc, [True] * nc, [set() for _ in range(nc)]
    kmap, kidx, newk = {}, {}, []
    for i in range(n):
        c = cls[i]
        g[c] = g[c] or goal[i]
        e[c] = e[c] and exp[i]
        for oi, kid in actions[i]:
            r = kmap.get(kid)
            if r is None:
                acc = defaultdict(int)
                for s, w in zip(*kernels[kid]):
                    acc[-1 if s < 0 else cls[s]] += w
                t = tuple(sorted(acc.items()))
                r = kidx.get(t)
                if r is None:
                    r = kidx[t] = len(newk)
                    newk.append((tuple(s for s, _ in t), tuple(w for _, w in t)))
                kmap[kid] = r
            if newk[r][0] != (c,):  # an action that only leads back to its own merged key is never part of a cheapest policy
                rows[c].add((oi, r))
    reps = [None] * nc
    for i in range(n):
        if reps[cls[i]] is None:
            reps[cls[i]] = keys[i]
    model = PatternModel(reps, g, [sorted(r) for r in rows], newk, PatternStats(), {}, e, None)
    graph = pb.pack_pattern_model(model, offers, lambda _k, was: None if was else cheapest)
    try:
        solved = pb.solve_packed(graph, progress=None, refuse_above=math.inf)
    except Exception as error:
        print(f"MERGED {name}: {nc} keys; solve failed: {type(error).__name__} {str(error)[:200]}")
        continue
    v = solved.value
    val = lambda s: 0.0 if s < 0 else float(v[s])
    used, seen, todo, floor_used = Counter(), {cls[0]}, [cls[0]], 0
    while todo:
        c = todo.pop()
        if g[c]:
            continue
        best, arg = (cheapest, None) if not e[c] else (math.inf, None)
        for oi, r in rows[c]:
            succ, w = newk[r]
            tot = sum(w)
            q = (0.0 if oi == CHOICE else costs[oi]) + sum(float(Fraction(x) / Fraction(tot)) * val(s) for s, x in zip(succ, w))
            if q < best:
                best, arg = q, (oi, r)
        if arg is None:
            floor_used += 1
            continue
        used["(choice)" if arg[0] == CHOICE else labels[arg[0]]] += 1
        for s in newk[arg[1]][0]:
            if s >= 0 and s not in seen:
                seen.add(s); todo.append(s)
    print(f"MERGED {name}: {nc - (n - len(real))} keys, {len(newk)} kernels, {sum(len(r) for r in rows)} rows; start value {float(v[cls[0]])!r} (solver's error {float(solved.error_bound):.2g}); "
          f"policy from the start visits {len(seen)} keys ({floor_used} at a tip's floor) and uses: " + "; ".join(f"{l} x{k}" for l, k in used.most_common()), flush=True)
