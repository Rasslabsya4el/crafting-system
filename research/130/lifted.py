"""The exact cost of the lifted pessimistic policy of a coarse level, and the exact states it visits (ADR-0023's last column).

usage: lifted.py <config> ...
"""
import sys, json
from scipy import sparse
import scipy.sparse.linalg as spla
from levels import *
import levels


def lifted(cfg, names=NAMES, price=PRICE):
    res, G, (Vl, Vu) = levels.run(cfg, names, price)
    C = G.C
    act_of_block = {}
    for bi, blk in enumerate(G.blocks):
        gi = G.gchoice[bi]
        if gi >= 0:
            act_of_block[blk] = G.groups_[gi][1]
    index = {START: 0}
    order = [START]
    rows, cols, vals = [], [], []
    cost = []
    q = 0
    while q < len(order):
        s = order[q]
        i = q
        q += 1
        if L.is_goal(s):
            cost.append(0.0)
            continue
        a = act_of_block[C.coarsen(s)]
        k = L.kernel(s, names[a])
        assert k is not None, (s, names[a])
        cost.append(price[names[a]])
        for t, p in k.items():
            j = index.get(t)
            if j is None:
                j = index[t] = len(order)
                order.append(t)
            rows.append(i)
            cols.append(j)
            vals.append(p)
    n = len(order)
    goal = np.array([L.is_goal(s) for s in order])
    P = sparse.csr_matrix((vals, (rows, cols)), shape=(n, n))
    P = sparse.diags((~goal).astype(float)) @ P
    A = (sparse.identity(n, format="csc") - P).tocsc()
    J = spla.spsolve(A, np.array(cost))
    res.update(lifted_cost=float(J[0]), lifted_states=n)
    return res


if __name__ == "__main__":
    for cfg in sys.argv[1:]:
        print(json.dumps(lifted(cfg)), flush=True)
