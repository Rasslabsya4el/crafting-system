"""t1363: candidate lemma 'only a raiser makes the predicate true'. For a route: a predicate Pass(status) on the key's leaf statuses
that the goal needs, and the offers declared (by game mechanics) as the only ones that can turn it from false to true (the raisers).
F = non-goal keys where Pass is false. Lemma: every plan from k in F applies a raiser row at some key of F before the goal, so
V(k) >= B = min over raiser rows at keys of F of (c_a + K_a V). Checks on the dump:
  (1) mechanics: rows of undeclared offers at F keys never have a successor outside F (else the declaration is wrong);
  (2) values: V(k) >= B - tol at every k in F (implied by (1) on an exact dump);
and writes a FREE spec for cert.py: the mask F and the distinct (offer, kernel) pairs of the raiser rows at F keys.
python lemma.py ROUTE VARIANT  (run in the folder of the e-ROUTE.npz dumps)"""
import sys, re, pickle, collections, numpy as np
r, var = sys.argv[1], sys.argv[2]
e = np.load(f"e-{r}.npz"); P = pickle.load(open(f"e-{r}.npz.parts.pkl", "rb"))
parts, fields, L = P["parts"], P["fields"], P["labels"]
V, goal = e["V"], e["goal"]; n = len(V)
rk, ro, rj, kptr, ksucc, kprob, costs = e["rk"], e["ro"], e["rj"], e["kptr"], e["ksucc"], e["kprob"], e["costs"]
si, ci, fi = fields.index("status"), fields.index("crafted"), fields.index("flags")
def status(k): return tuple(int(x) for x in re.findall(r": (\d)>", parts[k][si]))
ST = [status(k) if parts[k] is not None else None for k in range(n)]
lab = {x: i for i, x in enumerate(L)}
def locked_suffixes(k): return "CannotChangeSuffixes" in parts[k][ci]
def locked_prefixes(k): return "CannotChangePrefixes" in parts[k][ci]
# --- the route's predicate and raisers (game mechanics, stated in the note) ---
if r == "R24":
    # leaves: 0 Mana (fractured), 1 MoveSpeed veiled, 2 Avoid Shock essence mod, 3 Suppress T1, 4-6 res T2 (at least one)
    if var == "shock":   # Avoid Shock: an essence-only mod; only the Deafening Essence of Torment adds it
        ok = lambda s: s[2] == 2
        raiser = lambda o, k: L[o] == "Deafening Essence of Torment"
    elif var == "core":  # Avoid Shock and T1 Suppress: suppress is a suffix without the fire tag; only the essence and a Veiled Chaos Orb on unlocked suffixes reroll suffixes
        ok = lambda s: s[2] == 2 and s[3] == 2
        raiser = lambda o, k: L[o] == "Deafening Essence of Torment" or (L[o] == "Veiled Chaos Orb" and not locked_suffixes(k))
    elif var == "split":  # as corelock, the keys split by what they lack: no Avoid Shock (only the essence raises) / Avoid Shock but no T1 Suppress (essence or any Veiled Chaos Orb)
        ok = lambda s: s[2] == 2 and s[3] == 2
        raiser = lambda o, k: L[o] == "Deafening Essence of Torment" or (L[o] == "Veiled Chaos Orb" and ST[k][2] == 2)
    elif var == "corelock":  # as core, but every Veiled Chaos Orb row declared a raiser (no lock reading)
        ok = lambda s: s[2] == 2 and s[3] == 2
        raiser = lambda o, k: L[o] in ("Deafening Essence of Torment", "Veiled Chaos Orb")
elif r == "R13":
    # leaves: 0 Life T1, 1-3 Fire/Cold/Lightning T1 (at least 2), all not crafted; 4-6 bench crafts
    ok = lambda s: s[0] == 2 and sum(x == 2 for x in s[1:4]) >= 2
    if var == "natural":  # a natural mod is added only by a roll: reforges, Chaos, essences, Veiled Chaos, Alteration/Transmutation/Alchemy, the bought item
        nonraise = lambda o: L[o].startswith("Bench craft") or L[o] in ("Remove Crafted Mods", "Orb of Annulment", "Orb of Scouring", "restart")
        raiser = lambda o, k: not nonraise(o)
elif r == "R04":
    # leaves: 0 Pierce essence mod, 1 Strength essence mod, 2 arrow, 3 Life, 4 Bow damage, 5-8 crafted res/speed (at least one)
    if var == "frac":  # as essence, on keys with a fractured mod only (a fracture is never undone); the restart, which leaves for the unfractured start, a raiser too
        fr = fields.index("fractured")
        ok = lambda s: s[0] == 2 and s[1] == 2
        okk = lambda k: ok(ST[k]) or parts[k][fr] == "()"
        raiser = lambda o, k: L[o] in ("Deafening Essence of Rage", "Essence of Insanity", "restart")
    elif var == "essence":  # both essence mods are essence-only; only an essence adds one (rare: rerolls keeping fractured; normal: makes it rare)
        ok = lambda s: s[0] == 2 and s[1] == 2
        raiser = lambda o, k: L[o] in ("Deafening Essence of Rage", "Essence of Insanity")
else:
    raise SystemExit("no spec")
# the context: what a raiser's outcome may depend on besides its own draw (rarity, fractured mods); non-raisers that change it are 'moves'
if r == "R24": ctxof = (lambda k: int(ST[k][2] == 2)) if var == "split" else (lambda k: 0)
elif r == "R13": ctxof = lambda k: parts[k][fi]
else: ctxof = lambda k: (parts[k][fi], parts[k][fields.index("fractured")])
if "okk" not in globals(): okk = lambda k: ok(ST[k])
F = np.array([(not goal[k]) and ST[k] is not None and not okk(k) for k in range(n)])
m = len(kptr) - 1
kv = np.zeros(m)
for j in range(m):
    s, p = ksucc[kptr[j]:kptr[j + 1]], kprob[kptr[j]:kptr[j + 1]]
    kv[j] = float(np.sum(p * np.where(s >= 0, V[np.maximum(s, 0)], 0.0)))
rowv = costs[ro] + kv[rj]
# kernels that leave F (some successor outside F: a goal, the sink, or a key where the predicate holds)
leaves = np.zeros(m, bool)
for j in range(m):
    s = ksucc[kptr[j]:kptr[j + 1]]
    leaves[j] = bool(np.any((s < 0) | ~F[np.maximum(s, 0)]))
atF = F[rk]
isr = np.array([raiser(o, k) for o, k in zip(ro.tolist(), rk.tolist())])
bad = atF & ~isr & leaves[rj]
print(f"{r} {var}: keys {n} F {int(F.sum())} ({F.sum()/n:.1%})  rows at F {int(atF.sum())}, raiser rows at F {int((atF&isr).sum())}")
print(f"  (1) mechanics check: undeclared rows at F keys that leave F: {int(bad.sum())}", collections.Counter(L[o] for o in ro[bad]).most_common(5))
rr = atF & isr
B = rowv[rr].min()
pairs = sorted(set(zip(ro[rr].tolist(), rj[rr].tolist())))
po = collections.Counter(L[o] for o, _ in pairs)
print(f"  raiser (offer, kernel) pairs at F: {len(pairs)} {dict(po)}; B = {B:.6f} (V0 {V[0]:.6f}); argmin offer {L[ro[rr][rowv[rr].argmin()]]}")
tol = 1e-6 * B
viol = F & (V < B - tol)
print(f"  (2) value check: keys of F with V < B: {int(viol.sum())}; at B (rel 1e-9): {int((F & (np.abs(V-B) <= 1e-9*B)).sum())}; V-B over F: max {np.max(V[F]-B):.4f}")
print(f"  keys with V >= V0 (oracle's free set) {int(((V >= V[0]*(1-1e-9)) & ~goal).sum())}, of them in F {int(((V >= V[0]*(1-1e-9)) & ~goal & F).sum())}")
blk = np.load(f"e-{r}-bisim.npy")
bF = collections.defaultdict(set)
for k in range(n):
    if not goal[k]: bF[blk[k]].add(bool(F[k]))
print(f"  bisim blocks split by F: {sum(len(s) > 1 for s in bF.values())} of {len(bF)}; blocks wholly in F {sum(s == {True} for s in bF.values())}")
# contexts and moves (v2): z_X <= c_a + K_a W for raiser rows of context X; z_X <= c_b + z_Y for a non-raiser row at an F key of X with an F successor in Y
cid = {}; ctx = np.full(n, -1)
for k in np.flatnonzero(F): ctx[k] = cid.setdefault(ctxof(k), len(cid))
pairs3 = sorted(set(zip(ctx[rk[rr]].tolist(), ro[rr].tolist(), rj[rr].tolist())))
mv = {}
nr = np.flatnonzero(atF & ~isr)
for i in nr:
    X, j = ctx[rk[i]], rj[i]
    for s_ in ksucc[kptr[j]:kptr[j + 1]]:
        if s_ >= 0 and F[s_] and ctx[s_] != X:
            key = (X, int(ctx[s_])); mv[key] = min(mv.get(key, np.inf), float(costs[ro[i]]))
print(f"  contexts {len(cid)}; raiser (context, offer, kernel) triples {len(pairs3)}; moves {len(mv)}: {[(a, b, round(c, 4)) for (a, b), c in sorted(mv.items())][:12]}")
# per-context bound with the dump's values: B_X = min(raiser rows of X, c_b + B_Y over moves), then V(k) >= B_ctx(k) on F
BX = np.full(len(cid), np.inf)
for X, o, j in pairs3: BX[X] = min(BX[X], costs[o] + kv[j])
for _ in range(len(cid) + 1):
    for (a, b_), c in mv.items(): BX[a] = min(BX[a], c + BX[b_])
vF = F & (V < BX[np.maximum(ctx, 0)] * (1 - 1e-9))
print(f"  (3) per-context value check: keys of F with V < B_ctx: {int(vF.sum())}; B per context {np.round(BX, 4).tolist()[:8]}")
noraise = [x for x in range(len(cid)) if x not in {p[0] for p in pairs3}]
print(f"  contexts with no raiser row: {len(noraise)}")
np.savez(f"free-{r}-{var}.npz", free=F, offers=np.array([o for o, _ in pairs]), kernels=np.array([j for _, j in pairs]), B=B,
         ctx=ctx, p_ctx=np.array([p[0] for p in pairs3]), p_off=np.array([p[1] for p in pairs3]), p_ker=np.array([p[2] for p in pairs3]),
         m_from=np.array([a for a, _ in mv], dtype=int), m_to=np.array([b for _, b in mv], dtype=int), m_cost=np.array(list(mv.values())), nctx=len(cid))
