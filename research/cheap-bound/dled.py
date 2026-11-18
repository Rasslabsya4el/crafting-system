"""#1322: the exact build led by a coarse model solved again each round (`worked` of led.py), the coarse model built DIRECTLY, on the dump's offers.

    python dled.py ROUTE DUMP.pkl LEADFILE MODE [ROUNDS.tsv]       (env RULE=mass:0.5 | all; LIMIT=seconds of the whole run, default 7200)

The same offers on both sides. The direct model is built from the planner's own inputs of the round the dump was made in: the run of kd.py
(`benchmark_routes.py ROUTE --net`, its first group set by LEADFILE) is started again and stopped at its call of `pattern_lower_bound`; the
abstraction, the start and the priced offers of that call are taken, and the offers kept are those of the dump, in the dump's order (R04: 20 and
the restart; R24: 10 and the restart). So the direct model, the dump's exact model and the led build hold the same offers, and the check
"lead at or under the true value" compares two lower bounds on the same offers.

The direct model (the coarse key `tags,counts`: the bound's key without the ordinary slots' counts and protected tags; sdm.py's method, #1315).
A coarse key holds REPRESENTATIVES, concrete states a kernel produced. An offer is taken at a representative as the bound's builder takes it at a
member (`PatternBuilder._offers_of_key`: the key's refusal, the quality pruning, the lumped twin of an erasing action, LUMP_ERASING), and its
kernel's successors are pushed to their coarse keys; the row is
  - EXACT (the pushed kernel) when `Pattern.mode_of` is `ANY` at the representative's key (one member stands for the key whatever its junk) or
    the pushed kernel has one successor;
  - else ANGELIC: one certain row to each coarse key the kernel reaches, at the offer's cost.
A key is worked out at its first representative and again at a later one whose number of ordinary mods is outside those worked out before.
A coarse key that a kernel reached only through the lumped twin, or that the exact build met first, gets its representative from the bound's
own members (`Pattern.members(key, ANY)` of a full key holding it). A coarse key not worked out is valued at the cheapest offer's price; one
worked out keeps its rows while a new representative of it waits to be worked out (as sdm.py's solve). Not a proof; the check below is its test.

MODE: which coarse keys the direct model works out, and how the exact build is led.
  floor    the direct model is built along its OWN cheapest policy from the start until that policy meets no tip of it (sdm.py's order), then
           held: a coarse key it did not work out is valued at the cheapest offer's price. The exact build is then led, `worked` (below).
  demand   as floor, and in each round the coarse keys the led model's cheapest policy meets unworked (below the exact build's tips) are
           worked out in the direct model too.
  static   the direct model of `floor`, solved once; its value at a tip's coarse key is the tip's lead, held fixed (led.py's static lead).

`worked` (led.py REFINE=worked, #1318): each round one model is solved: the direct model's coarse states (their direct rows, plus the dump's rows
of every exact key worked out that they hold), and each worked-out exact key as a state of its own with the dump's rows, whose outcomes go to the
exact key where it is worked out and to its coarse state otherwise. The cheapest policy is walked from the start; the exact tips it meets are worked
out (RULE, as led.py); the run ends when it meets no exact tip. At every round the value of every coarse state is compared with the dump's complete
value at every exact key it holds (the lead must be at or under it), and the value of every worked key's own state with its complete value.

MAX=1 (not in #1318's `worked`): with direct rows, a worked key's rows can be worth less than its coarse lead (its outcomes land on coarse keys
the direct model values at the floor), and the member rows that `worked` adds to a coarse state can only lower it (they are more actions in a
minimum). With MAX=1 the coarse states keep their direct rows only, and a worked key whose rows are worth less than its coarse state's value is
PINNED: its state's one action leads to its coarse state at no cost, so its value is its lead. Both are lower bounds of the key, so the larger is
too if the coarse lead is (shown here by count only); the pins are set again after each solve until none changes (at most 12 solves a round). The walk
for tips follows a pinned key's rows.

RATCHET=1: each round the direct model is solved alone, and a coarse key's lead is the largest value it had in any round so far (each was checked
under the truth); the exact part is solved with its tips at those leads (and the pins of MAX=1). ONE=exact: an offer whose mode at the
representative is `ONE` takes the representative's exact kernel instead of the angelic stand-in (more optimistic in kind than the builder, which
takes several members; checked by count like the rest).

What is counted: exact keys worked out (until no tip, and until within 1% and 10%), the direct model's coarse keys found and worked out, its
representatives, kernels and seconds, the run's peak memory (ru_maxrss), the 1-minute load, and the lead check."""
import math, os, pickle, resource, runpy, sys, tempfile, time
from collections import Counter, defaultdict
from fractions import Fraction

T0 = time.perf_counter()
ROUTE, DUMP, LEADFILE, MODE = sys.argv[1:5]
OUT = sys.argv[5] if len(sys.argv) > 5 else None
RULE = os.environ.get("RULE", "mass:0.5")
MASS = float(RULE.split(":")[1]) if RULE.startswith("mass:") else None
LIMIT = float(os.environ.get("LIMIT", "7200"))
MAX = os.environ.get("MAX") == "1"
RATCHET = os.environ.get("RATCHET") == "1"  # each coarse key's lead is the largest value it had in any round (finding 1 of the checker)
ONE_EXACT = os.environ.get("ONE") == "exact"  # `ONE` rows take the representative's exact kernel instead of the angelic stand-in (finding 2)  # a worked key is valued at the larger of its rows' value and its coarse lead (see the docstring, `MAX=1`)
assert MODE in ("floor", "demand", "static")

import numpy as np
from crafting_system.abstraction._pattern import LUMP_ERASING, Mode, Pattern, PatternModel, PatternStats, _refused_by_key
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.planner import _envelope_plan as _ep
from crafting_system.planner import _pattern_bound as pb
from crafting_system.planner import _rounds
from crafting_system.solver import PackedBuilder, solve_packed

os.environ.setdefault("NET", "3600")
from crafting_system import config as _config

_config.TIME_LIMIT_SECONDS = float(os.environ["NET"])
_ep.SEARCH_PER_BUILD = 0.02
LEAD = open(LEADFILE).read().strip().removeprefix("LEAD=")
real_groups = _rounds.round_groups


def groups(offers, named, added):
    return real_groups(offers, (*(named or ()), *LEAD.split(":", 1)[1].split("|")), added)


class Captured(BaseException):
    pass


got = {}


def capture(abstraction, start, priced, **kw):
    got.update(ab=abstraction, start=start, priced=list(priced), tags=kw.get("tags"))
    raise Captured


_rounds.round_groups = groups
_ep.pattern_lower_bound = capture
argv = sys.argv
sys.argv = [".github/scripts/benchmark_routes.py", ROUTE, tempfile.mkdtemp(), "--net"]
try:
    runpy.run_path(".github/scripts/benchmark_routes.py", run_name="__main__")
except Captured:
    pass
except SystemExit:
    pass
sys.argv = argv
assert got, "the run did not reach pattern_lower_bound"
setup_s = time.perf_counter() - T0

d = pickle.load(open(DUMP, "rb"))
keys, goal, actions, kernels = d["keys"], d["goal"], d["actions"], d["kernels"]
costs, cheapest = d["costs"], d["cheapest"]
n = len(keys)
ab, start = got["ab"], got["start"]
by_label = {p.label: p for p in got["priced"]}
assert len(by_label) == len(got["priced"]), "two priced offers share a label"
assert all(l in by_label for l in d["labels"]), ("offers differ", [l for l in d["labels"] if l not in by_label])
offers = pb.pattern_offers([by_label[l] for l in d["labels"]])
assert [o.label for o in offers] == d["labels"] and all(abs(o.cost - c) <= 1e-9 * max(1, c) for o, c in zip(offers, costs)), "offer costs differ"
P = Pattern(ab, got["tags"], [o.action for o in offers if o.action is not None])
P.note(start)
assert P.key(start) == keys[0], ("start key differs", P.key(start), keys[0])

full = solve_packed(pb.pack_pattern_model(PatternModel(keys, goal, actions, kernels, PatternStats(), {}, [True] * n, None), offers, None), progress=None, refuse_above=math.inf)
V = np.asarray(full.value[:n], dtype=float)
print(f"{ROUTE} {MODE} rule {RULE}: setup {setup_s:.0f} s; dump {n} keys, {len(offers)} offers (the same as the direct model's: {', '.join(o.label for o in offers)}); complete start value {V[0]!r}; load {os.getloadavg()[0]:.1f}", flush=True)

# ---- the direct model ----------------------------------------------------------------------------------------------------------------
coarse_of = lambda k: k._replace(counts=None, tags=None)
CK = [coarse_of(k) for k in keys]
cindex, ckeys, cgoal, reps, span, exact_rows, angel_rows, worked_c = {}, [], [], [], [], [], [], []
stats = Counter()
memo = {}
build_s = 0.0
from_lumped = defaultdict(set)  # coarse id -> full keys that reached it only through the lumped twin (no concrete state kept)


def cid(ck):
    i = cindex.get(ck)
    if i is None:
        i = cindex[ck] = len(ckeys)
        ckeys.append(ck)
        cgoal.append(False)
        reps.append([])
        span.append(None)
        exact_rows.append({})
        angel_rows.append({})
        worked_c.append(False)
    return i


def offer_rep(c, junk, key, state):
    s = span[c]
    if (s is None and not reps[c]) or (s is not None and (junk < s[0] or junk > s[1]) and all(j != junk for j, _k, _s in reps[c])):
        reps[c].append((junk, key, state))


def seen_state(state):
    P.note(state)
    key = P.key(state)
    c = cid(coarse_of(key))
    if ab.is_goal(state):
        cgoal[c] = True
    offer_rep(c, key.counts[0] + key.counts[1], key, state)
    return c


def seen_key(key, goal_flag):  # a key met without a concrete state (a lumped outcome, an exact key): its state is a member, made when it is worked out
    c = cid(coarse_of(key))
    if goal_flag:
        cgoal[c] = True
    junk = key.counts[0] + key.counts[1]
    s = span[c]
    if (s is None and not reps[c]) or (s is not None and (junk < s[0] or junk > s[1]) and all(j != junk for j, _k, _s in reps[c])):
        reps[c].append((junk, key, None))
    return c


def work_coarse(c):
    global build_s
    t = time.perf_counter()
    waiting, reps[c] = reps[c], []
    worked_c[c] = True
    for junk, key, state in waiting:
        if state is None:
            members = P.members(key, Mode.ANY)
            stats["members asked"] += 1
            if not members:
                stats["key with no member"] += 1
                continue
            state = members[0]
        s = span[c]
        span[c] = [junk, junk] if s is None else [min(s[0], junk), max(s[1], junk)]
        stats["representatives"] += 1
        for oi, offer in enumerate(offers):
            action = offer.action
            if action is None:
                if c != 0:
                    row = ((0, Fraction(1)),)
                    if row not in exact_rows[c] or exact_rows[c][row][0] > offer.cost:
                        exact_rows[c][row] = (offer.cost, oi)
                continue
            if _refused_by_key(P, action, key):
                stats["refused by key"] += 1
                continue
            assert action.imprint_move() is None
            last = ab.quality_last_action(action)
            if ab.quality_offer_pruned(state, action) if last else ab.quality_finish_only(state, action):
                stats["quality pruned"] += 1
                continue
            try:
                kk = ab.kernel_key(state, action)
                pushed = memo.get(kk)
                if pushed is None:
                    lumped = LUMP_ERASING and ab.lumps(state, action)
                    out = P.twin.kernel(state, action) if lumped else ab.kernel(state, action)
                    stats["kernels"] += 1
                    acc = defaultdict(Fraction)
                    for succ, ch in out.items():
                        if lumped:
                            P.note_lumped()
                            acc[seen_key(P.key(succ), ab.is_goal(succ))] += ch
                        else:
                            acc[seen_state(succ)] += ch
                    pushed = memo[kk] = tuple(sorted(acc.items()))
                stats["pairs"] += 1
            except (NotApplicableError, OutOfScopeError, ValueError) as e:
                stats["refused " + type(e).__name__] += 1
                continue
            if len(pushed) == 1 and pushed[0][0] == c:
                continue
            try:
                mode = P.mode_of(action, key)
            except Exception:  # noqa: BLE001  (no mode: the angelic row)
                stats["mode_of failed: angelic"] += 1
                mode = Mode.ALL
            if len(pushed) == 1 or mode is Mode.ANY or (ONE_EXACT and mode is Mode.ONE):
                stats[f"exact rows ({'certain' if len(pushed) == 1 else 'any'}) {offer.label}"] += 1
                if pushed not in exact_rows[c] or exact_rows[c][pushed][0] > offer.cost:
                    exact_rows[c][pushed] = (offer.cost, oi)
            else:
                stats[f"angelic rows ({mode.value}) {offer.label}"] += 1
                for s2, _ch in pushed:
                    if s2 != c and (s2 not in angel_rows[c] or angel_rows[c][s2][0] > offer.cost):
                        angel_rows[c][s2] = (offer.cost, oi)
    build_s += time.perf_counter() - t


def int_weights(pushed):
    den = math.lcm(*(x.denominator for _s, x in pushed))
    return [int(x * den) for _s, x in pushed]


# ---- one solve of the led model ------------------------------------------------------------------------------------------------------
worked, reached, order = set(), {}, []  # exact keys: worked out; reached -> found


def reach(i):
    if i not in reached:
        reached[i] = len(order)
        order.append(i)
        cid_of_exact(i)
        if goal[i]:
            worked.add(i)


cc = {}


def cid_of_exact(i):
    c = cc.get(i)
    if c is None:
        if MODE == "demand":  # the exact key is a member the direct model may work out
            c = cc[i] = seen_key(keys[i], goal[i])
        else:  # the direct model is held: the key only names its coarse state (a new one is a tip at the floor)
            c = cc[i] = cid(CK[i])
            cgoal[c] = cgoal[c] or goal[i]
    return c


def work_exact(i):
    worked.add(i)
    for _oi, kid in actions[i]:
        for s in kernels[kid][0]:
            if s >= 0:
                reach(s)


def solve(with_exact=True):
    """The led model: coarse states 0..C-1, then each worked exact key's own state, then the sink. Returns values, the tags list."""
    C = len(ckeys)
    own = {i: C + j for j, i in enumerate(sorted(worked))} if with_exact else {}
    sink = C + len(own)
    b, tags = PackedBuilder(), []
    by_coarse = defaultdict(list)
    for i in own if not MAX else ():
        by_coarse[cc[i]].append(i)
    memo_k = {}

    def target(s):
        if s < 0 or goal[s]:
            return sink
        return own.get(s, cc[s]) if s in cc else own[s]

    def exact_rows_of(i):
        for oi, kid in actions[i]:
            k = memo_k.get(kid)
            if k is None:
                succ, w = kernels[kid]
                k = memo_k[kid] = (b.kernel([target(s) for s in succ], list(w)), [target(s) for s in succ])
            yield oi, k

    def act(cost, kern, succ, what):
        b.action(len(tags), cost, kern)
        tags.append((what, succ))

    for c in range(C):
        if not cgoal[c]:
            if worked_c[c]:
                for pushed, (cost, oi) in exact_rows[c].items():
                    act(cost, b.kernel([s for s, _x in pushed], int_weights(pushed)), [s for s, _x in pushed], ("coarse", oi))
                for s2, (cost, oi) in angel_rows[c].items():
                    act(cost, b.kernel([s2], [1]), [s2], ("angel", oi))
            if not worked_c[c]:  # a key worked out keeps its rows while a new representative waits (sdm.py's solve)
                act(max(cheapest, pb.FLOOR_COST), b.kernel([sink], [1]), [], ("floor", None))
            for i in by_coarse.get(c, ()):  # a worked member's own rows sit on its coarse state too
                for oi, (k, succ) in exact_rows_of(i):
                    act(costs[oi], k, succ, ("member", oi))
        b.close_state(cgoal[c])
    for i in own:
        if i in PIN and not goal[i]:
            act(pb.FLOOR_COST, b.kernel([cc[i]], [1]), [cc[i]], ("pin", None))
        elif not goal[i]:
            for oi, (k, succ) in exact_rows_of(i):
                act(costs[oi], k, succ, ("own", oi))
        b.close_state(goal[i])
    b.close_state(True)
    solved = solve_packed(b.build(), progress=None, refuse_above=math.inf)
    return np.asarray(solved.value, dtype=float), np.asarray(solved.action), own, tags


PIN = set()


def check(v, own):
    """The lead at or under the complete value: every coarse state against every exact key it holds, every own state against its key."""
    bad, worst = 0, 0.0
    for i in range(n):
        if goal[i]:
            continue
        c = cindex.get(CK[i])
        x = v[own[i]] if i in own else (v[c] if c is not None else cheapest)
        if x > V[i] * (1 + 1e-7) + 1e-9:
            bad += 1
            worst = max(worst, (x - V[i]) / max(V[i], 1e-300))
    return bad, worst


def grow_direct(budget_s):
    """sdm.py's order: the direct model alone (tips at the cheapest offer), worked out where its own cheapest policy goes, until no tip."""
    rounds = 0
    while True:
        rounds += 1
        v, act_, _own, tags = solve(with_exact=False)
        seen, todo, tips = {0}, [0], []
        while todo:
            c = todo.pop()
            if cgoal[c]:
                continue
            if not worked_c[c] or reps[c]:
                tips.append(c)
            a = int(act_[c])
            if a < 0:
                continue
            for s in tags[a][1]:
                if s < len(ckeys) and s not in seen:
                    seen.add(s)
                    todo.append(s)
        if rounds <= 3 or rounds % 25 == 0 or not tips:
            print(f"  direct round {rounds}: coarse keys {len(ckeys)}, worked out {sum(worked_c)}, start value {v[0]:.4f}, tips on its policy {len(tips)}, build {build_s:.0f} s, {time.perf_counter() - T0:.0f} s, load {os.getloadavg()[0]:.1f}", flush=True)
        if not tips:
            return v[0], rounds, None
        if time.perf_counter() - T0 > budget_s:
            return v[0], rounds, "limit"
        for c in tips:
            work_coarse(c)


seen_key(keys[0], goal[0])
reps[0] = [(0, keys[0], start)]
own_t = time.perf_counter()
dv, drounds, dstop = grow_direct(LIMIT / 2)
direct_s = time.perf_counter() - own_t
peak_direct = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
d_found, d_worked = len(ckeys), sum(worked_c)
print(f"DIRECT {ROUTE}: own-policy build {'stopped at the limit' if dstop else 'complete (its policy meets no tip)'}: coarse keys found {d_found}, worked out {d_worked}, rounds {drounds}, "
      f"start value {dv!r} ({100 * dv / V[0]:.2f}% of the exact), {direct_s:.0f} s (kernels and rows {build_s:.0f} s), peak memory {peak_direct:.2f} GB, load {os.getloadavg()[0]:.1f}; "
      + "; ".join(f"{k} {x}" for k, x in sorted(stats.items())), flush=True)
if dstop:
    print("RESULT none: the direct model was not complete along its own policy within half the limit", flush=True)
    sys.exit(0)

total = sum(1 for i in range(n) if not goal[i])
out = open(OUT, "w") if OUT else None
if out:
    out.write("round\tworked_out\tstart_value\tshare\texact_tips\tcoarse_tips\tcoarse_found\tcoarse_worked\tbad\tseconds\n")
static_h = None
if MODE == "static":
    v0, _a, _o, _t = solve(with_exact=False)
    static_h = np.array([v0[cindex[CK[i]]] if CK[i] in cindex else cheapest for i in range(n)])
    over = int(np.sum((static_h > V * (1 + 1e-7) + 1e-9) & ~np.asarray(goal)))
    print(f"static lead: at the start {static_h[0]!r} ({100 * static_h[0] / V[0]:.2f}%); above the complete value at {over} keys", flush=True)

reach(0)
work_exact(0)
prob = {}


def kernel(kid):
    p = prob.get(kid)
    if p is None:
        succ, w = kernels[kid]
        tot = sum(w)
        p = prob[kid] = (succ, [x / tot for x in w])
    return p


KARR = {}


def karr(kid):
    k = KARR.get(kid)
    if k is None:
        succ, w = kernels[kid]
        tot = sum(w)
        k = KARR[kid] = (np.array([n if x < 0 else x for x in succ]), np.array([x / tot for x in w]))
    return k


rounds, at99, at90, bad_total, worst_total, stop = 0, None, None, 0, 0.0, None
HC = np.zeros(0)
while True:
    rounds += 1
    if MODE == "static" or RATCHET:
        if RATCHET:  # the direct model alone; each coarse key's lead is the largest value it had in any round (each was checked under the truth)
            v0, act_, _own0, tags = solve(with_exact=False)
            C = len(ckeys)
            if len(HC) < C:
                HC = np.concatenate([HC, np.zeros(C - len(HC))])
            HC = np.maximum(HC, v0[:C])
            lead_of = lambda i: float(HC[cc[i]]) if not cgoal[cc[i]] else 0.0
        else:
            lead_of = lambda i: float(static_h[i])
        m = len(order)
        sv_all = None
        for _again in range(12 if MAX else 1):  # MAX: a worked key whose rows are worth less than its lead is pinned at its lead
            b = PackedBuilder()
            built = {}
            for i in order:
                if i in worked and i not in PIN and not goal[i]:
                    for oi, kid in actions[i]:
                        k = built.get(kid)
                        if k is None:
                            succ, w = kernels[kid]
                            k = built[kid] = b.kernel([m if s < 0 else reached[s] for s in succ], list(w))
                        b.action(oi, costs[oi], k)
                elif not goal[i]:
                    b.action(pb.FAKE, max(lead_of(i), pb.FLOOR_COST), b.kernel([m], [1]))
                b.close_state(goal[i])
            b.close_state(True)
            sv_all = np.asarray(solve_packed(b.build(), progress=None, refuse_above=math.inf).value, dtype=float)
            if not MAX:
                break
            arr = np.zeros(n + 1)
            for s_, j in reached.items():
                arr[s_] = 0.0 if goal[s_] else sv_all[j]
            changed = 0
            for i in worked:
                if goal[i]:
                    continue
                q = min((costs[oi] + float(karr(kid)[1] @ arr[karr(kid)[0]]) for oi, kid in actions[i]), default=math.inf) if i in PIN else float(sv_all[reached[i]])
                if i not in PIN and q < lead_of(i) * (1 - 1e-9) - 1e-12:
                    PIN.add(i)
                    changed += 1
                elif i in PIN and q > lead_of(i) * (1 + 1e-9) + 1e-12:
                    PIN.discard(i)
                    changed += 1
            if not changed:
                break
        val = lambda s: 0.0 if s < 0 or goal[s] else float(sv_all[reached[s]])
        sv = float(sv_all[0])
        ctips = []
        if RATCHET:  # the check: every coarse key's lead against every exact key it holds, every worked key's value against its own
            bad, worst = 0, 0.0
            for i in range(n):
                if goal[i]:
                    continue
                c = cindex.get(CK[i])
                x = float(sv_all[reached[i]]) if i in worked else (float(HC[c]) if c is not None and c < len(HC) else cheapest)
                if x > V[i] * (1 + 1e-7) + 1e-9:
                    bad += 1
                    worst = max(worst, (x - V[i]) / max(V[i], 1e-300))
            bad_total += bad
            worst_total = max(worst_total, worst)
        else:
            bad, worst = 0, 0.0  # the static lead is fixed: it was checked once, before the first round
    else:
        v, act_, own, tags = solve()
        val = lambda s: 0.0 if s < 0 or goal[s] else float(v[own[s]] if s in own else v[cc[s]])
        for _again in range(11 if MAX else 0):  # the pins: a worked key valued at the larger of its rows and its lead
            changed = 0
            arr = np.zeros(n + 1)  # the value of every key reached, as this solve has it (its own state, else its coarse state); goals and the sink 0
            for s, _j in reached.items():
                if not goal[s]:
                    arr[s] = v[own[s]] if s in own else v[cc[s]]
            for i in worked:
                if goal[i]:
                    continue
                if i in PIN:
                    q = min((costs[oi] + float(karr(kid)[1] @ arr[karr(kid)[0]]) for oi, kid in actions[i]), default=math.inf)
                else:
                    q = float(v[own[i]])  # an unpinned key's state holds its rows alone: the solve's value is their minimum
                lead_i = float(v[cc[i]])
                if i not in PIN and q < lead_i * (1 - 1e-9) - 1e-12:
                    PIN.add(i)
                    changed += 1
                elif i in PIN and q > lead_i * (1 + 1e-9) + 1e-12:
                    PIN.discard(i)
                    changed += 1
            if not changed:
                break
            v, act_, own, tags = solve()
        sv = float(v[own[0]])
        if MAX and sv < getattr(sys.modules[__name__], "_last_sv", 0.0) * (1 - 1e-9):
            print(f"  round {rounds}: the start value went DOWN, {sv!r}", flush=True)
        globals()["_last_sv"] = sv
        bad, worst = check(v, own)
        bad_total += bad
        worst_total = max(worst_total, worst)
        ctips = []
    # the exact tips the cheapest policy meets (as led.py), and, below each, the coarse tips of the direct model's part of the policy
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
            q = costs[oi] + sum(x * val(s) for s, x in zip(succ, p))
            if q < best:
                best, arg = q, kid
        if arg is None:
            continue
        pol[i] = arg
        for s in kernels[arg][0]:
            if s >= 0 and s not in seen:
                seen.add(s)
                todo.append(s)
    if MODE == "demand" and tips:
        cseen, ctodo = set(cc[i] for i in tips), [cc[i] for i in tips]
        cseen = set(ctodo)
        while ctodo:
            c = ctodo.pop()
            if cgoal[c]:
                continue
            if not worked_c[c] or reps[c]:
                ctips.append(c)
            a = int(act_[c])
            if a < 0:
                continue
            for s in tags[a][1]:
                if s < len(ckeys) and s not in cseen:
                    cseen.add(s)
                    ctodo.append(s)
    c_now = sum(1 for i in worked if not goal[i])
    share = sv / V[0]
    at90 = at90 or (share >= 0.90 and (c_now, rounds))
    at99 = at99 or (share >= 0.99 and (c_now, rounds))
    el = time.perf_counter() - T0
    if out:
        out.write(f"{rounds}\t{c_now}\t{sv!r}\t{share:.6f}\t{len(tips)}\t{len(ctips)}\t{len(ckeys)}\t{sum(worked_c)}\t{bad}\t{el:.0f}\n")
        out.flush()
    if rounds <= 5 or rounds % 20 == 0 or not tips:
        print(f"  round {rounds}: worked out {c_now}, start value {sv:.6f} ({100 * share:.2f}%), exact tips {len(tips)}, coarse tips {len(ctips)}, coarse keys {len(ckeys)} "
              f"(worked {sum(worked_c)}), lead above the truth at {bad} keys (worst {worst:.2e}), {el:.0f} s, load {os.getloadavg()[0]:.1f}", flush=True)
    if not tips:
        break
    if el > LIMIT:
        stop = f"the limit of {LIMIT:.0f} s"
        break
    if MASS is not None and len(tips) > 1:
        loc = {i: j for j, i in enumerate(seen)}
        src, dst, pr = [], [], []
        for i, kid in pol.items():
            succ, p = kernel(kid)
            keep = [j for j, s in enumerate(succ) if s >= 0]
            dst.extend(loc[succ[j]] for j in keep)
            src.append(np.full(len(keep), loc[i]))
            pr.append(np.array([p[j] for j in keep]))
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
        work_exact(i)
    for c in ctips:
        work_coarse(c)

fmt = lambda a: "never" if not a else f"{a[0]} keys ({100 * a[0] / total:.2f}%), round {a[1]}"
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
print(f"RESULT {ROUTE} {MODE}{' MAX' if MAX else ''}{' RATCHET' if RATCHET else ''}{' ONE=exact' if ONE_EXACT else ''} rule {RULE}: pinned at the end {len(PIN)}; offers {len(offers)}; direct model on its own policy: {d_found} coarse keys found, {d_worked} worked out, {direct_s:.0f} s, start value {dv!r} "
      f"({100 * dv / V[0]:.2f}%); after the led build: {len(ckeys)} coarse keys found, {sum(worked_c)} worked out, kernels and rows {build_s:.0f} s in all; exact build works out "
      f"{c_now} of {total} keys ({100 * c_now / total:.2f}%) {'STOPPED at ' + stop if stop else 'until no tip'}, {rounds} rounds; within 1% after {fmt(at99)}; within 10% after {fmt(at90)}; "
      f"final start value {sv!r} against {V[0]!r}; lead above the truth: {bad_total} key-rounds, worst {worst_total:.2e}; {time.perf_counter() - T0:.0f} s, peak memory {peak:.2f} GB, load {os.getloadavg()[0]:.1f}; "
      f"direct model's work in all: " + "; ".join(f"{k} {x}" for k, x in sorted(stats.items()) if not k.startswith(("exact rows", "angelic rows"))), flush=True)
