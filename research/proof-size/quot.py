"""t1360: the bisimulation quotient of a dump (bisim.py's blocks) as a model in export.py's format: one state per block, the rows of one
key of it, kernels pushed onto blocks. Its values equal the dump's (checked). python quot.py e-ROUTE.npz e-ROUTEq.npz"""
import sys, numpy as np
e = np.load(sys.argv[1]); blk = np.load(sys.argv[1].replace(".npz", "-bisim.npy"))
V, goal = e["V"], e["goal"]; n = len(V)
rk, ro, rj, kptr, ksucc, kprob = e["rk"], e["ro"], e["rj"], e["kptr"], e["ksucc"], e["kprob"]
# renumber blocks so that the start's block is 0
uniq = {}; order = [blk[0]] + [b for b in blk.tolist()]
for b in order:
    uniq.setdefault(b, len(uniq))
B = np.array([uniq[b] for b in blk.tolist()]); nb = len(uniq)
rep = np.full(nb, -1); 
for k in range(n - 1, -1, -1): rep[B[k]] = k
newk = {}; kp = [0]; ks = []; kpb = []
nrk, nro, nrj = [], [], []
sel = np.isin(rk, rep)
for r in np.flatnonzero(sel):
    k = rk[r]
    if rep[B[k]] != k: continue
    j = rj[r]
    if j not in newk:
        d = {}
        for s, p in zip(ksucc[kptr[j]:kptr[j + 1]].tolist(), kprob[kptr[j]:kptr[j + 1]].tolist()):
            t = -1 if s < 0 else int(B[s]); d[t] = d.get(t, 0.0) + p
        newk[j] = len(newk); ks += list(d.keys()); kpb += list(d.values()); kp.append(len(ks))
    nrk.append(B[k]); nro.append(ro[r]); nrj.append(newk[j])
Vb = V[rep]; gb = goal[rep]
spread = max(abs(V[k] - Vb[B[k]]) / max(V[k], 1e-12) for k in range(n))
print("blocks", nb, "rows", len(nrk), "kernels", len(newk), "largest relative spread of V in a block", spread)
np.savez_compressed(sys.argv[2], V=Vb, goal=gb, choice=np.zeros(nb, bool), expanded=np.ones(nb, bool), rk=np.array(nrk), ro=np.array(nro), rj=np.array(nrj),
    kptr=np.array(kp), ksucc=np.array(ks), kprob=np.array(kpb), costs=e["costs"], cheapest=e["cheapest"], start_value=e["start_value"], choice_cost=0.0)
