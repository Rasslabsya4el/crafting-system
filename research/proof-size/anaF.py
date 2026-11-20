"""t1360: at the keys no cheaper than the start (V >= V0), which row is optimal, and is its kernel one the start (or a key of the same
fractured/crafted/flags/held) also has: the 'reset' structure. python anaF.py e-ROUTE.npz"""
import sys, pickle, collections, numpy as np
e = np.load(sys.argv[1]); P = pickle.load(open(sys.argv[1] + ".parts.pkl", "rb")); labels = P["labels"]; parts = P["parts"]
V, goal = e["V"], e["goal"]; n = len(V); V0 = V[0]
rk, ro, rj, kptr, ksucc, kprob, costs = e["rk"], e["ro"], e["rj"], e["kptr"], e["ksucc"], e["kprob"], e["costs"]
m = len(kptr) - 1; kj = np.repeat(np.arange(m), np.diff(kptr))
EV = np.bincount(kj, weights=kprob * np.where(ksucc >= 0, V[np.where(ksucc >= 0, ksucc, 0)], 0.0), minlength=m)
Q = costs[ro] + EV[rj]
best = np.full(n, np.inf); np.minimum.at(best, rk, Q)
opt = Q <= best[rk] * (1 + 1e-12) + 1e-12
F = (V >= V0 * (1 - 1e-9)) & ~goal
start_kernels = set(rj[rk == 0].tolist())
c = collections.Counter(); same = 0; tot = 0
seen = set()
for r in np.flatnonzero(opt & F[rk]):
    k = rk[r]
    if k in seen: continue
    seen.add(k); tot += 1
    c[labels[ro[r]]] += 1
    same += rj[r] in start_kernels
print(sys.argv[1], "F keys", int(F.sum()), "optimal row by offer:", c.most_common(), "optimal kernel also a start kernel:", same, "of", tot)
# the erasing kernels: a kernel used by many keys (shared) -> count keys whose optimal kernel is used at >= 100 keys
use = np.bincount(rj, minlength=m)
sh = sum(1 for r in np.flatnonzero(opt & F[rk]) if use[rj[r]] >= 100)
print(" optimal rows at F keys whose kernel is shared by >= 100 keys:", sh)
nF = ~F & ~goal
c2 = collections.Counter(labels[ro[r]] for r in np.flatnonzero(opt & nF[rk]))
print(" not-F keys", int(nF.sum()), "optimal rows by offer:", c2.most_common())
# V - V0 at F keys
d = V[F] - V0
print(" V - V0 at F keys: quantiles", np.quantile(d, [0, .25, .5, .75, .9, .99, 1]).round(4).tolist())
