"""#1321: the exact build led from below AND from above (an incumbent plan, as in bounded RTDP / LAO* with an upper bound), counted on a
COMPLETE dump of kd.py. Builds nothing; research only.

    python uled.py DUMP.pkl LEAD [ROUNDS.tsv]      (env RULE=gap:0.5 | mass:F | all; UPPER=restart | none; LIMIT=seconds, default 3600)

LEAD, the LOWER value of a tip (a key found and not worked out), as led.py: `floor` (the cheapest offer's price: what the planner's build
gives a tip today), `exact` (the complete model's value: the perfect lead, a reference), a coarse key of ka.py merged from the complete model
(`tags,counts`, `tags+sum`, ...; not a lead a build has: a reference), or `file:PATH`, a numpy array of one lead per key (the fixed DIRECT lead
of #1324, saved by `dled.py` with SAVELEAD). Every lead is checked to be at or under the complete value at every key before it is used.

The UPPER value. Every non-goal key of both dumps has the restart offer (R04 3.2 c, R24 50 c), whose one outcome is the start key. So in the
dump's model V(k) <= c_r + V(start) at every key k, and for any plan with value U(start), c_r + U(start) is an upper value of every tip. The
incumbent of a round is the best plan that uses only the rows of the keys worked out so far and restarts at every tip: the worked model with
each tip's one action "restart" (cost c_r, to the start), solved by the planner's solver. Its start value U is the value of a real policy of
the dump's model, so U >= V(start) (checked every round). With UPPER=none a tip has no upper value (infinite): the incumbent is then the best
plan that never meets a tip (the worked keys from which some plan surely avoids every tip; infinite until the start is among them).
Both incumbents are solved and written every round; UPPER only says which one weighs the tips. UPPER=oracle weighs a tip by its visits
times (its complete value - its lead): the best upper value a tip can have; it reads the truth, so no build can, and it bounds what any
sharper upper stand-in could do to the order of the work (with it the incumbent would be the complete value from the first round).

A round: the lower model (tips at their lead, led.py's) and the two upper models are solved; L = the lower start value. The cheapest policy
of the lower model is walked from the start, and the expected visits of each key under it counted over 400 steps (led.py's). The gap of
that policy, sum over its tips of visits x (c_r + U - lead), is written as `policy_gap` (a reading, not used by the stop). STOP (the run's 1%, OR-39): the first round with L >= 0.99 x U, for each
incumbent. The run goes on to "no tip on the lower policy" (led.py's end), so both stops and the end are counted in one run.

RULE, which tips the lower policy meets are worked out in a round:
  gap:F   the ticket's rule: the tips with the largest visits x (upper value - lower value), the fewest that hold the share F of that sum
          (the upper value of a tip is c_r + U for UPPER=restart; with UPPER=none every gap is infinite and the rule is mass:F)
  mass:F  led.py's: by visits alone
  all     every tip the lower policy meets
Nothing is cut (OR-12): the upper value only orders the work and says when the run's 1% is reached.
"""
import math, os, pickle, sys, time
from collections import defaultdict
from fractions import Fraction
from types import SimpleNamespace
import numpy as np
from crafting_system.abstraction._pattern import CHOICE, ChoiceNode, PatternModel, PatternStats
from crafting_system.planner import _pattern_bound as pb
from crafting_system.solver import PackedBuilder, solve_packed

FOLDS = {"sum": lambda c: sum(c), "cap1": lambda c: tuple(min(x, 1) for x in c), "cap2": lambda c: tuple(min(x, 2) for x in c), "prefix": lambda c: c[0], "suffix": lambda c: c[1]}
BIG = 1e15
dump, lead = sys.argv[1], sys.argv[2]
RULE = os.environ.get("RULE", "gap:0.5")
UPPER = os.environ.get("UPPER", "restart")
LIMIT = float(os.environ.get("LIMIT", "3600"))
assert UPPER in ("restart", "none", "oracle") and RULE.split(":")[0] in ("gap", "mass", "all")
SHARE = float(RULE.split(":")[1]) if ":" in RULE else None
d = pickle.load(open(dump, "rb"))
keys, goal, actions, kernels, exp = d["keys"], d["goal"], d["actions"], d["kernels"], d["expanded"]
labels, costs, cheapest = d["labels"], d["costs"], d["cheapest"]
n = len(keys)
assert all(exp), "a complete dump only"
choice = [isinstance(k, ChoiceNode) for k in keys]
offers = [SimpleNamespace(cost=c) for c in costs]
RESTART = labels.index("restart")
CR = costs[RESTART]
# the restart is an offer at every non-goal key, with the start key as its one outcome: the upper value of a tip rests on it
has_restart = [any(oi == RESTART and tuple(kernels[kid][0]) == (0,) for oi, kid in actions[i]) for i in range(n)]
missing = [i for i in range(n) if not goal[i] and not choice[i] and not has_restart[i]]
assert missing in ([], [0]), f"keys without the restart to the start: {missing[:5]}"  # the start's own restart is a self-loop the builder drops


def solve_all(model_keys, g, rows, kern, e):
    model = PatternModel(model_keys, g, rows, kern, PatternStats(), {}, e, None)
    return solve_packed(pb.pack_pattern_model(model, offers, None), progress=None, refuse_above=math.inf)


began = time.perf_counter()
V = np.asarray(solve_all(keys, goal, actions, kernels, exp).value[:n], dtype=float)
print(f"dump {dump}: keys {n}, goals {sum(goal)}, offers {len(labels)}, restart {CR} c, complete start value {V[0]!r} (dump's {d['start_value']!r})", flush=True)

coarse = 0
if lead == "floor":
    h = np.full(n, cheapest)
elif lead == "exact":
    h = V.copy()
elif lead.startswith("file:"):
    h = np.load(lead[5:])
    assert h.shape == (n,)
    lead = "direct:" + os.path.basename(lead[5:]).removesuffix(".npy")
else:  # a coarse key of ka.py, merged from the complete model (led.py's merge_lead with nothing split)
    drop, *folds = lead.split("+")
    drop, fc, fj = (() if drop == "none" else tuple(drop.split(","))), next((FOLDS[f] for f in folds if f in FOLDS), None), next((f for f in folds if f in ("fj", "fa")), None)
    cid, cls = {}, [0] * n
    for i, k in enumerate(keys):
        pk = ("choice", i) if choice[i] else k._replace(**{f: None for f in drop})
        if fc is not None and not choice[i]:
            pk = pk._replace(counts=fc(k.counts))
        if fj and not choice[i] and k.fractured:
            pk = pk._replace(fractured=tuple(sorted("junk" if (fj == "fa" or m.mod_id.startswith("~")) and not any(int(x) for x in m.contribution) else repr(m) for m in k.fractured)))
        cls[i] = cid.setdefault(pk, len(cid))
    nc = len(cid)
    g, rows, kidx, newk, kmap = [False] * nc, [set() for _ in range(nc)], {}, [], {}
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
    h = np.asarray(solve_all(reps, g, [sorted(r) for r in rows], newk, [True] * nc).value, dtype=float)[np.asarray(cls)]
    coarse = nc - sum(choice)
    if os.environ.get("BEST"):  # led.py's BEST: the least complete value inside the coarse key (reads the truth; a reference, no build has it)
        lo = np.full(nc, np.inf)
        np.minimum.at(lo, np.asarray(cls), V)
        h = lo[np.asarray(cls)]
        lead += "@best"
tip = np.array([not choice[i] and not goal[i] for i in range(n)])
over = int(np.sum((h > V * (1 + 1e-7) + 1e-9) & tip))
print(f"lead {lead}: coarse keys {coarse}; at the start {h[0]!r} ({100 * h[0] / V[0]:.2f}%); above the complete value at {over} keys (must be 0)", flush=True)
assert over == 0
print(f"the upper stand-in c_r + V(start) over the complete values: median (c_r + V0)/V {float(np.median(((CR + V[0]) / np.maximum(V, 1e-300))[tip])):.2f}", flush=True)

prob, arr = {}, {}


def kernel(kid):
    p = prob.get(kid)
    if p is None:
        succ, w = kernels[kid]
        tot = sum(w)
        p = prob[kid] = (succ, [float(Fraction(x, tot)) for x in w])
    return p


worked, reached, order = set(), {}, []


def reach(i):
    if i not in reached:
        reached[i] = len(order)
        order.append(i)
        if choice[i] or goal[i]:
            work(i)


def work(i):
    worked.add(i)
    for _oi, kid in actions[i]:
        for s in kernels[kid][0]:
            if s >= 0:
                reach(s)


def safe_set():
    """The worked keys from which some plan reaches a goal with probability 1 and never meets a tip (the standard almost-sure reach: the
    greatest set C where each key has an action whose outcomes all stay in C or are goals, and from which a goal can be reached by such
    actions). Exact, so the 'none' incumbent is finite exactly when the start is in it."""
    cand = {i for i in order if i in worked and not goal[i]}
    isgoal = lambda s: s < 0 or goal[s]
    while True:
        users, clean, bad = defaultdict(list), {}, [i for i in order if not goal[i] and i not in cand]
        for i in cand:
            clean[i] = len(actions[i])
            for j, (_oi, kid) in enumerate(actions[i]):
                for s in set(kernels[kid][0]):
                    if not isgoal(s):
                        users[s].append((i, j))
        dirty, out_ = set(), set(bad)
        while bad:
            s = bad.pop()
            for i, j in users.get(s, ()):
                if (i, j) not in dirty:
                    dirty.add((i, j))
                    clean[i] -= 1
                    if clean[i] == 0 and i not in out_:
                        out_.add(i)
                        bad.append(i)
        stay = cand - out_  # keys with an action that keeps every outcome in stay or a goal
        good = {i: [kid for j, (_oi, kid) in enumerate(actions[i]) if (i, j) not in dirty] for i in stay}
        back, reach_g = defaultdict(set), set()
        for i, kids in good.items():
            for kid in kids:
                succ = kernels[kid][0]
                if any(isgoal(s) for s in succ):
                    reach_g.add(i)
                for s in succ:
                    if not isgoal(s):
                        back[s].add(i)
        todo = list(reach_g)
        while todo:
            s = todo.pop()
            for i in back.get(s, ()):
                if i not in reach_g:
                    reach_g.add(i)
                    todo.append(i)
        if reach_g == cand:
            return cand | {i for i in order if goal[i]}
        cand = reach_g


def solve_round(tipmode):
    """tipmode: 'lead' (a tip's one action costs its lead and ends), 'restart' (costs c_r, to the start), 'none' (a tip, and a worked key
    from which every plan can meet a tip, has one action costing BIG that ends: the value is infinite unless the start is safe)."""
    m = len(order)
    b, built, sink, back = PackedBuilder(), {}, None, None
    safe = safe_set() if tipmode == "none" else None
    for i in order:
        if i in worked and (safe is None or i in safe):
            for oi, kid in actions[i]:
                made = built.get(kid)
                if made is None:
                    succ, w = kernels[kid]
                    made = built[kid] = b.kernel([m if s < 0 else reached[s] for s in succ], w)
                b.action(oi, pb.FLOOR_COST if oi == CHOICE else costs[oi], made)
        elif not goal[i] or (safe is not None and i not in safe):
            if tipmode == "restart":
                if back is None:
                    back = b.kernel([reached[0]], [1])
                b.action(RESTART, CR, back)
            else:
                if sink is None:
                    sink = b.kernel([m], [1])
                b.action(pb.FAKE, max(float(h[i]), pb.FLOOR_COST) if tipmode == "lead" else BIG, sink)
        b.close_state(goal[i])
    b.close_state(True)
    return solve_packed(b.build(), progress=None, refuse_above=math.inf).value


reach(0)
if 0 not in worked:
    work(0)
counted = lambda: sum(1 for i in worked if not choice[i] and not goal[i])
total = int(tip.sum())
out = open(sys.argv[3], "w") if len(sys.argv) > 3 else None
if out:
    out.write("round\tworked_out\tL\tU_restart\tU_none\tL_share\tL_over_U_restart\tL_over_U_none\tpolicy_gap\ttips_on_policy\ttip_visits\tseconds\n")
rounds = 0
stop_r = stop_n = at99 = None
stopped = False
while True:
    rounds += 1
    v = solve_round("lead")
    ur = float(solve_round("restart")[0])
    un = float(solve_round("none")[0]) if 0 in safe_set() else math.inf
    L = float(v[0])
    assert ur >= V[0] * (1 - 1e-9) - 1e-9 and un >= V[0] * (1 - 1e-9) - 1e-9, (ur, un, V[0])  # the incumbents are real plans
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
    visits = {}
    if tips:  # expected visits of each key under the lower policy, over 400 steps from the start (led.py's)
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
        x = np.zeros(len(loc))
        x[loc[0]] = 1.0
        vis = x.copy()
        if pr:
            src, dst, pr = np.concatenate(src), np.array(dst), np.concatenate(pr)
            for _ in range(400):
                x = np.bincount(dst, weights=pr * x[src], minlength=len(loc))
                vis += x
        visits = {i: float(vis[loc[i]]) for i in tips}
    utip = CR + ur
    gap = {i: visits[i] * max(utip - float(h[i]), 0.0) if visits[i] > 0 else 0.0 for i in tips}
    pgap = sum(gap.values())
    c = counted()
    if stop_r is None and L >= 0.99 * ur:
        stop_r = (c, rounds, L / ur)
    if stop_n is None and L >= 0.99 * un:
        stop_n = (c, rounds, L / un)
    if at99 is None and L >= 0.99 * V[0]:
        at99 = (c, rounds)
    sec = time.perf_counter() - began
    if out:
        out.write(f"{rounds}\t{c}\t{L!r}\t{ur!r}\t{un!r}\t{L / V[0]:.6f}\t{L / ur:.6f}\t{L / un if un < math.inf else 0.0:.6f}\t{pgap!r}\t{len(tips)}\t{sum(visits.values())!r}\t{sec:.0f}\n")
        out.flush()
    if rounds <= 5 or rounds % 20 == 0 or not tips:
        print(f"  round {rounds}: worked out {c}, L {L:.4f} ({100 * L / V[0]:.2f}% of V), U restart {ur:.4f} (L/U {100 * L / ur:.2f}%), U none {un:.4f}, "
              f"tips on the policy {len(tips)} (visits {sum(visits.values()):.3g}), policy gap {pgap:.4g}, {sec:.0f} s, load {os.getloadavg()[0]:.1f}", flush=True)
    if not tips:
        break
    if sec > LIMIT:
        stopped = True
        print(f"  STOPPED at the limit: round {rounds}, worked out {c}, L/V {100 * L / V[0]:.2f}%, L/U restart {100 * L / ur:.2f}%", flush=True)
        break
    if SHARE is not None and len(tips) > 1:
        # with no plan in hand yet (U infinite) every gap is infinite: the tips are then weighed by visits alone, as mass:F
        if UPPER == "oracle":  # the best upper value a tip can have, its complete value (reads the truth: led.py's oracle rule)
            wt = {i: visits[i] * max(V[i] - float(h[i]), 0.0) for i in tips}
        else:
            wt = {i: (visits[i] if (RULE.startswith("mass") or UPPER == "none" or not math.isfinite(utip)) else gap[i]) for i in tips}
        if sum(wt.values()) > 0:
            tips.sort(key=lambda i: -wt[i])
            goal_mass, acc, cut = sum(wt.values()) * SHARE, 0.0, 0
            while cut < len(tips) and (acc < goal_mass or cut == 0):
                acc += wt[tips[cut]]
                cut += 1
            tips = tips[:cut]
    for i in tips:
        work(i)
fmt = lambda a: "never" if not a else f"{a[0]} keys ({100 * a[0] / total:.2f}%), round {a[1]}" + (f", L/U {100 * a[2]:.2f}%" if len(a) > 2 else "")
print(f"RESULT {os.path.basename(dump)} lead {lead} rule {RULE} upper-weights {UPPER}: coarse keys {coarse}; complete build {total} keys; "
      f"{'STOPPED at the limit after' if stopped else 'no tip on the lower policy after'} {counted()} keys ({100 * counted() / total:.2f}%), {rounds} rounds; "
      f"stop L >= 0.99 U (restart upper) after {fmt(stop_r)}; stop L >= 0.99 U (no upper at tips) after {fmt(stop_n)}; "
      f"L within 1% of the complete value after {fmt(at99)}; final L {L!r} against the complete {V[0]!r}; {time.perf_counter() - began:.0f} s; "
      f"peak memory {__import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss / 1e6:.2f} GB", flush=True)
