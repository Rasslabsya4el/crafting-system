"""t1360, question 3: the smallest exact certificate that the start value is at least (1-GAP) * V0, for the exact bound's model of a complete dump.

A certificate is a set S of keys worked out (their every row is read) and a value W on S such that W(k) <= c_a + sum_s P(s) W(s) for every row
(k, a) with k in S, where a key s outside S (a tip) has W(s) = h(s), the lead the build gives a tip, and W(start) >= (1-GAP) V0.
Then W <= the value of the model with S worked out and tips at h, which is a lower bound of the craft's cost (the build's own soundness).

h = the cheapest offer's price (the floor, what a tip is valued at today) is CONSISTENT: h(k) <= c_a + sum P h(s) for every row (every cost is at
least the cheapest price, a goal or the sink is 0, a choice node's h is 0 and its rows cost 0). For a consistent h, writing W = h + u with u >= 0
and imposing the row constraint at EVERY key is no loss: at a tip u = 0 and the row holds by consistency. So the LP
    min sum_k u_k / (V_k - h_k)   s.t.  u_k - y_j <= c_a + sum P h - h_k  (every row k,a,j),  y_j <= sum_s P_j(s) u_s,  u_0 >= (1-GAP)V0 - h_0,  0 <= u_k <= V_k - h_k
has optimum <= |S| for every certificate S (u_k/(V_k-h_k) <= 1 on S, 0 off it): a LOWER bound on the smallest certificate. Its support (after
reweighting, REWEIGHT rounds) is a certificate: an UPPER bound, not re-solved exactly (the note says so under "Not done").
python cert.py e-ROUTE.npz GAP [LEAD.npy] [OUT.npy]  -- LEAD: h per key (not checked consistent: then only the upper bound is valid)."""
import sys, time, os
import numpy as np, scipy.sparse as sp
from scipy.optimize import linprog
e = np.load(sys.argv[1]); GAP = float(sys.argv[2])
V, goal, choice = e["V"], e["goal"], e["choice"]; n = len(V)
rk, ro, rj, kptr, ksucc, kprob, costs = e["rk"], e["ro"], e["rj"], e["kptr"], e["ksucc"], e["kprob"], e["costs"]
CH = int(e["choice_index"]) if "choice_index" in e.files else -999
rowcost = np.where(ro == CH, 0.0, costs[np.where(ro == CH, 0, ro)])
lead = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "floor" else None
if lead and lead.startswith("alpha:"):  # h = alpha V (and at least the floor): consistent for alpha <= 1, since V is a fixed point
    h = np.maximum(float(lead[6:]) * V, float(e["cheapest"]))
elif lead:
    h = np.load(lead).astype(float)
else:
    h = np.full(n, float(e["cheapest"]))
h = np.where(goal | choice, 0.0, np.minimum(h, V))
consistent = lead is None or lead.startswith('alpha:')
m = len(kptr) - 1
# kernel matrix: K[j, s] = P_j(s) over non-goal s >= 0 ; sink (-1) and goals have u = 0 and h = 0
kj = np.repeat(np.arange(m), np.diff(kptr))
ok = ksucc >= 0
ss = np.where(ok, ksucc, 0)
hs = np.where(ok, h[ss], 0.0)
Kh = np.bincount(kj, weights=kprob * hs, minlength=m)  # sum P h per kernel
live = ok & ~goal[ss]
K = sp.csr_matrix((kprob[live], (kj[live], ss[live])), shape=(m, n))
b_row = rowcost + Kh[rj] - h[rk]
assert not consistent or b_row.min() > -1e-9, b_row.min()
ng = ~goal
span = np.maximum(V - h, 0.0)
var = ng & (span > 1e-12)  # a key whose V equals h needs no work: u = 0
idx = -np.ones(n, dtype=np.int64); idx[var] = np.arange(var.sum()); nv = int(var.sum())
# variables: u (nv), y (m)
FREE = os.environ.get("FREE")  # oracle | ruin | mode | a lemma spec .npz (t1363); keys whose value a lemma gives without working them out: their rows go, one row to the start takes their place
free = np.zeros(n, bool); free_cost = 0.0
if FREE == "oracle":  # every key no cheaper than the start (V >= V0): the most a 'no better than the start' lemma could give; reads the truth
    free = (V >= V[0] - 1e-9 * V[0]) & ~goal
elif FREE == "ruin":  # keys from which no goal is reachable without the restart: their value is the restart and the start's, exactly
    restart = len(costs) - 1
    nz = ksucc >= 0
    kj_all = np.repeat(np.arange(m), np.diff(kptr))
    pred = sp.csr_matrix((np.ones(nz.sum()), (ksucc[nz], kj_all[nz])), shape=(n, m))  # succ -> kernel
    nr = ro != restart
    kern2key = sp.csr_matrix((np.ones(nr.sum()), (rj[nr], rk[nr])), shape=(m, n))
    reach = goal.copy() | False
    # a key reaches a goal if a kernel of one of its non-restart rows has a successor that does (or the sink: -1 is a goal)
    sinkk = np.zeros(m, bool); sinkk[np.unique(kj_all[~nz])] = True
    kr = sinkk.copy()
    while True:
        kr2 = kr | (pred.T @ reach.astype(float) > 0)
        reach2 = reach | (kern2key.T @ kr2.astype(float) > 0)
        if reach2.sum() == reach.sum() and kr2.sum() == kr.sum():
            break
        reach, kr = reach2, kr2
    free = ~reach & ~goal
    free_cost = float(costs[restart])
anchor = 0
if FREE == "mode":  # keys no cheaper than the most common value (the value of a reset: an erasing reroll's, or the start's): one free row to a key of that value; reads the truth
    vals, cnt = np.unique(np.round(V[~goal], 6), return_counts=True); vm = vals[cnt.argmax()]
    anchor = int(np.flatnonzero((np.abs(V - vm) < 1e-6) & ~goal)[0])
    free = (V >= V[anchor] - 1e-9 * V[anchor]) & ~goal
    print(f"anchor key {anchor} value {V[anchor]} (keys at that value {cnt.max()})", flush=True)
spec = None
if FREE and FREE.endswith(".npz"):  # a lemma's spec (t1363 lemma.py): keys F valued by one shared variable z <= every raiser row (c_a + K_a W)
    spec = np.load(FREE); free = spec["free"] & ~goal
free[0] = False; free[anchor] = False
print(f"free keys ({FREE}): {int(free.sum())}", flush=True)
var = var & ~free | (free & var)
keep = var[rk] & ~free[rk]  # a row of a key with u fixed 0 holds: 0 - y <= b needs y >= -b, y >= 0 ... y appears with u; keep rows of variable keys only
# rows at fixed keys: 0 <= b + y holds when b >= 0 (consistent); for a lead that is not consistent the fixed keys have u=0 and are tips (no row)
A1 = sp.csr_matrix((np.r_[np.ones(keep.sum()), -np.ones(keep.sum())], (np.r_[np.arange(keep.sum()), np.arange(keep.sum())], np.r_[idx[rk[keep]], nv + rj[keep]])), shape=(keep.sum(), nv + m))
Kv = K[:, np.flatnonzero(var)]
A2 = sp.hstack([-Kv, sp.identity(m)]).tocsr()
fv = np.flatnonzero(free & var) if spec is None else np.zeros(0, dtype=np.int64)
A3 = sp.csr_matrix((np.r_[np.ones(len(fv)), -np.ones(len(fv))], (np.r_[np.arange(len(fv)), np.arange(len(fv))], np.r_[idx[fv], np.full(len(fv), idx[anchor])])), shape=(len(fv), nv + m))
A = sp.vstack([A1, A2, A3]).tocsr()
b = np.r_[b_row[keep], np.zeros(m), free_cost + h[anchor] - h[fv]]
need = (1 - GAP) * V[0] - h[0]
lo = np.zeros(nv + m); hi = np.r_[span[var], np.full(m, np.inf)]
if spec is not None and os.environ.get("ONEZ"):  # v1: one variable z (last): h_k + u_k - z <= 0 at free keys; z - y_j <= c_a + K_j h for every raiser pair
    fk = np.flatnonzero(free & var); po, pj = spec["offers"], spec["kernels"]; nf, npair = len(fk), len(po)
    A = sp.hstack([A, sp.csr_matrix((A.shape[0], 1))]).tocsr()
    A4 = sp.csr_matrix((np.r_[np.ones(nf), -np.ones(nf)], (np.r_[np.arange(nf), np.arange(nf)], np.r_[idx[fk], np.full(nf, nv + m)])), shape=(nf, nv + m + 1))
    A5 = sp.csr_matrix((np.r_[np.ones(npair), -np.ones(npair)], (np.r_[np.arange(npair), np.arange(npair)], np.r_[np.full(npair, nv + m), nv + pj])), shape=(npair, nv + m + 1))
    A = sp.vstack([A, A4, A5]).tocsr()
    b = np.r_[b, -h[fk], costs[po] + Kh[pj]]
    lo = np.r_[lo, -np.inf]; hi = np.r_[hi, np.inf]; nz = 1
    print(f"lemma spec {FREE} (one z): free keys with a span {nf}, raiser pairs {npair}, B {float(spec['B']):.6f}", flush=True)
elif spec is not None:  # v2: one variable z_X per context X (after u and y): W(k) <= z_ctx(k); z_X <= c_a + K_a W (raisers of X); z_X <= c_b + z_Y (moves)
    nz = int(spec["nctx"]); Z = nv + m; ctx = spec["ctx"]
    fk = np.flatnonzero(free & var); nf = len(fk)
    pc, po, pj = spec["p_ctx"], spec["p_off"], spec["p_ker"]; npair = len(po)
    mf, mt, mc = spec["m_from"], spec["m_to"], spec["m_cost"]; nm = len(mf)
    A = sp.hstack([A, sp.csr_matrix((A.shape[0], nz))]).tocsr(); N = nv + m + nz
    A4 = sp.csr_matrix((np.r_[np.ones(nf), -np.ones(nf)], (np.r_[np.arange(nf), np.arange(nf)], np.r_[idx[fk], Z + ctx[fk]])), shape=(nf, N))
    A5 = sp.csr_matrix((np.r_[np.ones(npair), -np.ones(npair)], (np.r_[np.arange(npair), np.arange(npair)], np.r_[Z + pc, nv + pj])), shape=(npair, N))
    A6 = sp.csr_matrix((np.r_[np.ones(nm), -np.ones(nm)], (np.r_[np.arange(nm), np.arange(nm)], np.r_[Z + mf, Z + mt])), shape=(nm, N))
    A = sp.vstack([A, A4, A5, A6]).tocsr()
    b = np.r_[b, -h[fk], costs[po] + Kh[pj], mc]
    lo = np.r_[lo, np.full(nz, -np.inf)]; hi = np.r_[hi, np.full(nz, np.inf)]
    print(f"lemma spec {FREE}: contexts {nz}, free keys with a span {nf}, raiser triples {npair}, moves {nm}", flush=True)
else:
    nz = 0
lo[idx[0]] = need
w = np.where(choice[var] | free[var], 0.0, 1.0 / span[var])
REW = int(os.environ.get("REWEIGHT", "3"))
t0 = time.time(); res = []
for it in range(REW + 1):
    c = np.r_[w, np.zeros(m + nz)]
    if os.environ.get("MAXSTART"):  # t1363: the lower model's own value at the start (the largest W(start) the rows allow), no 1% demand
        c = np.zeros(nv + m + nz); c[idx[0]] = -1.0; lo[idx[0]] = 0.0
    r = linprog(c, A_ub=A, b_ub=b, bounds=np.c_[lo, hi], method=os.environ.get("METHOD", "highs"))
    assert r.status == 0, r.message
    u = r.x[:nv]; frac = u / span[var]
    supp = (frac > 1e-7) & ~choice[var] & ~free[var]
    if it == 0:
        lb = r.fun
    res.append(int(supp.sum()))
    print(f"iter {it}: LP {r.fun:.2f} support {supp.sum()} (choice nodes in support {((frac>1e-7)&choice[var]).sum()}) {time.time()-t0:.0f}s", flush=True)
    w = np.where(choice[var] | free[var], 0.0, 1.0 / (frac + 1e-3))
best = min(res)
print(f"RESULT {sys.argv[1]} gap {GAP} lead {lead or 'floor'} free {FREE} {int(free.sum())} keys {n} nongoal {int(ng.sum())} worth-work {nv} LOWER {lb:.2f} UPPER(last support) {res[-1]} min-support {best}", flush=True)
if len(sys.argv) > 4:
    S = np.zeros(n, bool); S[np.flatnonzero(var)[supp]] = True; np.save(sys.argv[4], S)
