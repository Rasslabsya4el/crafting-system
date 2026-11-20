"""t1360, question 2 on a dump: per offer, the keys where it is the cheapest row (argmin), within 1% of it, and rows it has. python q2.py e-ROUTE.npz"""
import sys, pickle, numpy as np
e = np.load(sys.argv[1]); labels = pickle.load(open(sys.argv[1] + ".parts.pkl", "rb"))["labels"]
V, goal = e["V"], e["goal"]; n = len(V)
rk, ro, rj, kptr, ksucc, kprob, costs = e["rk"], e["ro"], e["rj"], e["kptr"], e["ksucc"], e["kprob"], e["costs"]
m = len(kptr) - 1; kj = np.repeat(np.arange(m), np.diff(kptr))
EV = np.bincount(kj, weights=kprob * np.where(ksucc >= 0, V[np.where(ksucc >= 0, ksucc, 0)], 0.0), minlength=m)
Q = costs[ro] + EV[rj]
best = np.full(n, np.inf); np.minimum.at(best, rk, Q)
arg = Q <= best[rk] * (1 + 1e-12) + 1e-12
near = Q <= best[rk] * 1.01
path = np.load(sys.argv[1].replace(".npz", "-path.npy"))
print(sys.argv[1], "offers", len(labels))
for o in range(len(labels)):
    s = ro == o
    print(f"  {labels[o][:48]:48s} rows {int(s.sum()):7d} argmin at {int((s & arg).sum()):7d} keys (on the plan path {int((s & arg & path[rk]).sum()):4d}); within 1% at {int((s & near).sum()):7d}")
print("  offers argmin at some key:", int(sum(((ro == o) & arg).any() for o in range(len(labels)))), "; argmin at a path key:", int(sum(((ro == o) & arg & path[rk]).any() for o in range(len(labels)))))
