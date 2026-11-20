"""t1360, question 1: the coarsest exact merge of a complete dump's model (probabilistic bisimulation, costs of rows by price).
Two keys are in one block when they have the same set of rows (price, distribution of the successor over blocks); goals are one block.
Any merge of keys that a lemma could prove exact for EVERY price list and keep the model's rows is at most this coarse; the block count is the
least number of states an exact model of these offers can have when it is built row by row. Also: distinct values (relative 1e-9).
python bisim.py e-ROUTE.npz"""
import sys, numpy as np
e = np.load(sys.argv[1]); V, goal = e["V"], e["goal"]; n = len(V)
rk, ro, rj, kptr, ksucc, kprob, costs = e["rk"], e["ro"], e["rj"], e["kptr"], e["ksucc"], e["kprob"], e["costs"]
m = len(kptr) - 1
blk = np.where(goal, 0, 1).astype(np.int64)
sink = 0  # the sink is a goal
order = np.argsort(rk, kind="stable"); rk2, ro2, rj2 = rk[order], ro[order], rj[order]
starts = np.searchsorted(rk2, np.arange(n + 1))
price = np.round(costs, 9)
for it in range(200):
    kb = np.where(ksucc >= 0, blk[np.where(ksucc >= 0, ksucc, 0)], 0)
    ksig = {}
    kid = np.empty(m, dtype=np.int64)
    for j in range(m):
        a, b = kptr[j], kptr[j + 1]
        d = {}
        for s, p in zip(kb[a:b].tolist(), kprob[a:b].tolist()):
            d[s] = d.get(s, 0.0) + p
        sig = tuple(sorted((s, round(p, 11)) for s, p in d.items()))
        kid[j] = ksig.setdefault(sig, len(ksig))
    sigs = {}
    new = np.empty(n, dtype=np.int64)
    for k in range(n):
        if goal[k]:
            new[k] = sigs.setdefault(("goal",), len(sigs)); continue
        rows = frozenset(zip(price[ro2[starts[k]:starts[k + 1]]].tolist(), kid[rj2[starts[k]:starts[k + 1]]].tolist()))
        new[k] = sigs.setdefault((blk[k], rows), len(sigs))
    nb, ob = len(sigs), len(np.unique(blk))
    print(f"iter {it}: blocks {nb}", flush=True)
    blk = new
    if nb == ob:
        break
vals = len(np.unique(np.round(np.log(np.maximum(V[~goal], 1e-300)), 9)))
print(f"RESULT {sys.argv[1]} keys {n} goals {int(goal.sum())} bisimulation blocks {nb} distinct values {vals}")
np.save(sys.argv[1].replace(".npz", "-bisim.npy"), blk)
