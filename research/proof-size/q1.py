"""t1360, question 1: each key against the keys of the cheapest plan's path (visited with positive chance from the start under the optimal
policy of the complete model): the fewest key parts in which it differs from SOME plan key. Classes by those parts:
 junk  = counts and/or tags only;  slots = also/only crafted, held, veiled;  status = the status (with or without junk/slots);  fractured/flags = those.
Also for a set of keys given as a boolean .npy (a certificate's support). python q1.py e-ROUTE.npz [S.npy ...]"""
import sys, pickle, itertools, collections, numpy as np
e = np.load(sys.argv[1]); P = pickle.load(open(sys.argv[1] + ".parts.pkl", "rb")); fields, parts = P["fields"], P["parts"]
V, goal = e["V"], e["goal"]; n = len(V)
rk, ro, rj, kptr, ksucc, kprob, costs = e["rk"], e["ro"], e["rj"], e["kptr"], e["ksucc"], e["kprob"], e["costs"]
m = len(kptr) - 1; kj = np.repeat(np.arange(m), np.diff(kptr))
EV = np.bincount(kj, weights=kprob * np.where(ksucc >= 0, V[np.where(ksucc >= 0, ksucc, 0)], 0.0), minlength=m)
Q = costs[ro] + EV[rj]
best = np.full(n, np.inf); np.minimum.at(best, rk, Q)
pol = {}
for r in np.argsort(Q):
    k = rk[r]
    if k not in pol and Q[r] <= best[k] * (1 + 1e-12) + 1e-12:
        pol[k] = rj[r]
path = {0}; stack = [0]
while stack:
    k = stack.pop()
    if goal[k] or k not in pol: continue
    j = pol[k]
    for s in ksucc[kptr[j]:kptr[j + 1]].tolist():
        if s >= 0 and s not in path:
            path.add(s); stack.append(s)
path_ng = [k for k in path if not goal[k]]
F = list(fields); NF = len(F)
subsets = sorted((frozenset(c) for r in range(NF + 1) for c in itertools.combinations(range(NF), r)), key=len)
index = {}
for D in subsets:
    keep = [i for i in range(NF) if i not in D]
    index[D] = {tuple(parts[k][i] for i in keep) for k in path_ng}
def klass(k):
    for D in subsets:
        keep = [i for i in range(NF) if i not in D]
        if tuple(parts[k][i] for i in keep) in index[D]:
            names = {F[i] for i in D}
            if not names: return "on the path"
            if names <= {"counts", "tags"}: return "junk only (counts, tags)"
            if names <= {"counts", "tags", "crafted", "held", "veiled"}: return "slots (crafted, held, veiled) and junk"
            if names <= {"counts", "tags", "crafted", "held", "veiled", "status"}: return "status (and slots, junk)"
            return "fractured or flags (and others)"
    return "nothing in common"
cls = [None if goal[k] else klass(k) for k in range(n)]
print(f"{sys.argv[1]}: plan path {len(path)} keys ({len(path_ng)} not goals)")
def report(name, mask):
    c = collections.Counter(cls[k] for k in np.flatnonzero(mask) if cls[k])
    tot = sum(c.values())
    print(f"  {name} ({tot} keys): " + "; ".join(f"{a} {b} ({100*b/tot:.1f}%)" for a, b in c.most_common()))
report("all keys", ~goal)
for f in sys.argv[2:]:
    report(f, np.load(f))
np.save(sys.argv[1].replace(".npz", "-path.npy"), np.isin(np.arange(n), list(path)))
