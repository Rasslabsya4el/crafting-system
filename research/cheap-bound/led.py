"""#1315, point 1: the exact model worked out lazily, its tips valued by a coarser model. Reads a COMPLETE dump of kd.py; builds nothing.

    python led.py DUMP.pkl LEAD [ROUNDS.tsv]        (env RULE=all | mass:F, default all)

LEAD names what values a key that is not worked out yet (a tip):
    floor      the price of the cheapest offer (what the planner's build does today, `_tip_floor`)
    exact      the complete model's own value (the perfect lead: the least any lead can need)
    a coarse key of ka.py (section 4 of the note), by its parts dropped and its fold of the junk counts:
    tags | tags,counts | tags,counts,veiled | tags,counts,crafted | tags,counts,crafted,held,veiled | ...,fractured | ...,fractured,flags
    tags+sum | tags+cap1 | tags+cap2 | tags+prefix | tags+suffix
    +fj after any of them (none+fj for it alone): a fractured junk mod that the key knows by its family type ("~3") and that gives no leaf
    anything is one value, whatever the type; +fa: the same for EVERY fractured mod that gives no leaf anything (a fractured craft too)

The count. Start: only the start key is worked out. A round: the model of the keys worked out so far, each tip a state whose one action costs
its lead value and ends (the planner's own floor action, `pack_pattern_model`), is solved by the planner's solver; the cheapest policy is
walked from the start; every tip it meets is worked out (its rows taken from the dump). The count ends when the policy meets no tip: the start
value is then the complete model's (checked against the dump at the end). A goal key and a choice node are never counted: neither is a key
the build works out with members. "Gap 1%" is the first round whose start value is at least 99% of the complete model's start value.

RULE says which of the tips the policy meets are worked out in a round. `all`: every one (the plain rule of LAO*). `mass:F`: the tips the
policy visits most (expected visits from the start under the cheapest policy, counted over 400 steps), the fewest that hold the share F of
all its visits to tips: a build that goes first where the plan goes most often. The end is the same under either rule (no tip on the policy).

The lead is checked to be a lower bound of the complete model's value at every key before it is used (the merge lemma, by count)."""
import math, os, pickle, sys, time
from collections import defaultdict
from fractions import Fraction
from types import SimpleNamespace
import numpy as np
from crafting_system.abstraction._pattern import CHOICE, ChoiceNode, PatternModel, PatternStats
from crafting_system.planner import _pattern_bound as pb
from crafting_system.solver import PackedBuilder, solve_packed

FOLDS = {"sum": lambda c: sum(c), "cap1": lambda c: tuple(min(x, 1) for x in c), "cap2": lambda c: tuple(min(x, 2) for x in c), "prefix": lambda c: c[0], "suffix": lambda c: c[1]}
dump, lead = sys.argv[1], sys.argv[2]
RULE = os.environ.get("RULE", "all")
MASS = float(RULE.split(":")[1]) if RULE.startswith("mass:") else None
d = pickle.load(open(dump, "rb"))
keys, goal, actions, kernels, exp = d["keys"], d["goal"], d["actions"], d["kernels"], d["expanded"]
labels, costs, cheapest = d["labels"], d["costs"], d["cheapest"]
n = len(keys)
assert all(exp), "a complete dump only: a tip of the dump has no value to lead toward"
choice = [isinstance(k, ChoiceNode) for k in keys]
offers = [SimpleNamespace(cost=c) for c in costs]


def solve_all(model_keys, g, rows, kern, e, floor):
    model = PatternModel(model_keys, g, rows, kern, PatternStats(), {}, e, None)
    return solve_packed(pb.pack_pattern_model(model, offers, floor), progress=None, refuse_above=math.inf)


began = time.perf_counter()
full = solve_all(keys, goal, actions, kernels, exp, None)
V = np.asarray(full.value[:n], dtype=float)
print(f"dump {dump}: keys {n} (choice nodes {sum(choice)}, goals {sum(goal)}), offers {len(labels)}, complete start value {V[0]!r} (dump's {d['start_value']!r})", flush=True)

if lead == "floor":
    h, coarse = np.full(n, cheapest), 0
elif lead == "exact":
    h, coarse = V.copy(), 0
else:
    drop, *folds = lead.split("+")
    drop, fc, fj = (() if drop == "none" else tuple(drop.split(","))), next((FOLDS[f] for f in folds if f in FOLDS), None), next((f for f in folds if f in ("fj", "fa")), None)
    cid, cls = {}, [0] * n
    for i, k in enumerate(keys):
        pk = ("choice", i) if choice[i] else k._replace(**{f: None for f in drop})
        if fc is not None and not choice[i]:
            pk = pk._replace(counts=fc(k.counts))
        if fj and not choice[i] and k.fractured:  # fj: a fractured junk mod known by its family type ("~3"); fa: every fractured mod that gives no leaf anything
            pk = pk._replace(fractured=tuple(sorted("junk" if (fj == "fa" or m.mod_id.startswith("~")) and not any(int(x) for x in m.contribution) else repr(m) for m in k.fractured)))
        cls[i] = cid.setdefault(pk, len(cid))
    nc = len(cid)
    g, rows = [False] * nc, [set() for _ in range(nc)]
    kmap, kidx, newk = {}, {}, []
    for i in range(n):
        c = cls[i]
        g[c] = g[c] or goal[i]
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
            if newk[r][0] != (c,):
                rows[c].add((oi, r))
    reps = [None] * nc
    for i in range(n):
        if reps[cls[i]] is None:
            reps[cls[i]] = keys[i]
    merged = solve_all(reps, g, [sorted(r) for r in rows], newk, [True] * nc, None)
    h = np.asarray(merged.value, dtype=float)[np.asarray(cls)]
    coarse = nc - sum(choice)
    print(f"lead {lead}: coarse keys {coarse}, coarse start value {h[0]!r} ({100 * h[0] / V[0]:.2f}% of the complete model's)", flush=True)
tip = np.array([not choice[i] and not goal[i] for i in range(n)])  # a goal and a choice node are never tips: their lead is never read
over = int(np.sum((h > V * (1 + 1e-7) + 1e-9) & tip))
print(f"lead above the complete value at {over} keys of {n} (the lemma says 0); lead/exact over the keys that can be tips: median {float(np.median((h / np.maximum(V, 1e-300))[tip])):.4f}", flush=True)
assert over == 0

prob, arr = {}, {}


def kernel(kid):
    p = prob.get(kid)
    if p is None:
        succ, w = kernels[kid]
        tot = sum(w)
        p = prob[kid] = (succ, [float(Fraction(x, tot)) for x in w])
    return p


worked, reached, order = set(), {}, []  # worked: keys whose rows are in the model; reached: key -> local state


def reach(i):
    if i not in reached:
        reached[i] = len(order)
        order.append(i)
        if choice[i] or goal[i]:  # neither is worked out by members: in the model as soon as it is seen
            work(i)


def work(i):
    worked.add(i)
    for _oi, kid in actions[i]:
        for s in kernels[kid][0]:
            if s >= 0:
                reach(s)


reach(0)
if 0 not in worked:
    work(0)
counted = lambda: sum(1 for i in worked if not choice[i] and not goal[i])
total = sum(1 for i in range(n) if not choice[i] and not goal[i])
out = open(sys.argv[3], "w") if len(sys.argv) > 3 else None
if out:
    out.write("round\tworked_out\tin_model\tstart_value\tshare_of_complete\ttips_on_policy\tseconds\n")
rounds, at99, at90, at50 = 0, None, None, None
while True:
    rounds += 1
    m = len(order)
    b, built = PackedBuilder(), {}
    sink = None
    for i in order:
        if i in worked:
            for oi, kid in actions[i]:
                made = built.get(kid)
                if made is None:
                    succ, w = kernels[kid]
                    made = built[kid] = b.kernel([m if s < 0 else reached[s] for s in succ], w)
                b.action(oi, pb.FLOOR_COST if oi == CHOICE else costs[oi], made)
        elif not goal[i]:
            if sink is None:
                sink = b.kernel([m], [1])
            b.action(pb.FAKE, max(float(h[i]), pb.FLOOR_COST), sink)
        b.close_state(goal[i])
    b.close_state(True)
    solved = solve_packed(b.build(), progress=None, refuse_above=math.inf)
    v = solved.value
    val = lambda s: 0.0 if s < 0 else float(v[reached[s]])
    seen, todo, tips, pol = {0}, [0], [], {}
    while todo:
        i = todo.pop()
        if goal[i]:
            continue
        if i not in worked:
            tips.append(i)
            continue
        best, arg = math.inf, None
        for oi, kid in actions[i]:
            succ, p = kernel(kid)
            q = (0.0 if oi == CHOICE else costs[oi]) + sum(x * val(s) for s, x in zip(succ, p))
            if q < best:
                best, arg = q, kid
        if arg is None:
            continue
        pol[i] = arg
        for s in kernels[arg][0]:
            if s >= 0 and s not in seen:
                seen.add(s)
                todo.append(s)
    sv, c = float(v[0]), counted()
    share = sv / V[0]
    at50 = at50 or (share >= 0.50 and (c, rounds))
    at90 = at90 or (share >= 0.90 and (c, rounds))
    at99 = at99 or (share >= 0.99 and (c, rounds))
    if out:
        out.write(f"{rounds}\t{c}\t{m}\t{sv!r}\t{share:.6f}\t{len(tips)}\t{time.perf_counter() - began:.0f}\n")
        out.flush()
    if rounds <= 5 or rounds % 20 == 0 or not tips:
        print(f"  round {rounds}: worked out {c}, in the model {m}, start value {sv:.6f} ({100 * share:.2f}%), tips on the cheapest policy {len(tips)}, policy keys {len(seen)}, {time.perf_counter() - began:.0f} s", flush=True)
    if not tips:
        break
    if MASS is not None and len(tips) > 1:  # the expected visits of each key under the policy, over 400 steps from the start
        loc = {i: j for j, i in enumerate(seen)}
        src, dst, pr = [], [], []
        for i, kid in pol.items():
            a = arr.get(kid)
            if a is None:
                succ, p = kernel(kid)
                keep = [j for j, s in enumerate(succ) if s >= 0]
                a = arr[kid] = ([succ[j] for j in keep], np.array([p[j] for j in keep]))
            dst.extend(loc[s] for s in a[0])
            src.append(np.full(len(a[0]), loc[i]))
            pr.append(a[1])
        src, dst, pr = np.concatenate(src), np.array(dst), np.concatenate(pr)
        x = np.zeros(len(loc))
        x[loc[0]] = 1.0
        visits = x.copy()
        for _ in range(400):
            x = np.bincount(dst, weights=pr * x[src], minlength=len(loc))
            visits += x
        tips.sort(key=lambda i: -visits[loc[i]])
        mass, acc, cut = sum(visits[loc[i]] for i in tips) * MASS, 0.0, 0
        while cut < len(tips) and (acc < mass or cut == 0):
            acc += visits[loc[tips[cut]]]
            cut += 1
        tips = tips[:cut]
    for i in tips:
        work(i)
fmt = lambda a: "never" if not a else f"{a[0]} keys ({100 * a[0] / total:.2f}%), round {a[1]}"
print(f"RESULT {os.path.basename(dump)} lead {lead} rule {RULE}: coarse keys {coarse}; complete build works out {total} keys; led: no tip on the cheapest policy after {counted()} keys "
      f"({100 * counted() / total:.2f}%), {rounds} rounds; within 1% of the complete value after {fmt(at99)}; within 10% after {fmt(at90)}; half after {fmt(at50)}; "
      f"final start value {sv!r} against the complete {V[0]!r} (difference {abs(sv - V[0]) / V[0]:.2e}); {time.perf_counter() - began:.0f} s", flush=True)
