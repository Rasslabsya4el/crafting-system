"""Tail cut on top of a coarse level (ticket #130): expand exactly the states the coarse policy visits, bound the rest by the blocks.

usage: tailcut.py <config> <theta> ...
The exact states with expected visits >= theta under the pessimistic policy of the coarse model (lifted to them) are expanded with
every legal action; any other successor is a leaf whose lower bound is the optimistic value of its block and whose upper bound is
the pessimistic value of its block. Two solves of the expanded model, one per leaf bound, bracket the exact optimum; the bracket
of the sparse solve is certified by its own residual as before.
"""
import heapq, sys, json
from levels import *


def visits(C, G, act_of_block, names=NAMES):
    """Expected number of visits of every exact state under the lifted policy (a sparse solve on the states it can reach)."""
    from scipy import sparse
    import scipy.sparse.linalg as spla
    index = {START: 0}
    order = [START]
    rows, cols, vals = [], [], []
    q = 0
    while q < len(order):
        s = order[q]
        i = q
        q += 1
        if L.is_goal(s):
            continue
        k = L.kernel(s, names[act_of_block[C.coarsen(s)]])
        for t, p in k.items():
            j = index.get(t)
            if j is None:
                j = index[t] = len(order)
                order.append(t)
            rows.append(i); cols.append(j); vals.append(p)
    n = len(order)
    goal = np.array([L.is_goal(s) for s in order])
    P = sparse.diags((~goal).astype(float)) @ sparse.csr_matrix((vals, (rows, cols)), shape=(n, n))
    A = (sparse.identity(n, format="csc") - P.T).tocsc()
    e0 = np.zeros(n)
    e0[0] = 1.0
    x = spla.spsolve(A, e0)
    return {s: float(x[i]) for i, s in enumerate(order) if not goal[i]}


def run(cfg, thetas, names=NAMES, price=PRICE):
    res, G, (Vl, Vu) = levels_run(cfg, names, price)
    ll, _ = G.bracket(Vl, G.residual("lower", Vl))
    _, uu = G.bracket(Vu, G.residual("upper", Vu))
    lowv = Vl * ll
    upv = Vu * uu
    C = G.C
    gchoice = G.gchoice
    act_of_block = {}
    for bi, blk in enumerate(G.blocks):
        gi = gchoice[bi]
        if gi >= 0:
            act_of_block[blk] = G.groups_[gi][1]
    out = [res]
    allvisits = visits(C, G, act_of_block, names)
    out[0]["policy_states"] = len(allvisits)
    for theta in thetas:
        t0 = time.time()
        E = {s: v for s, v in allvisits.items() if v >= theta}
        E[START] = allvisits[START]
        order = [START] + [s for s in E if s != START]
        index = {s: i for i, s in enumerate(order)}
        m = len(order)
        goals = {}
        leaves = {}
        table_lo, table_up = [], []
        edges = 0
        for s in order:
            acts_lo, acts_up = [], []
            for ai, nm in enumerate(names):
                k = L.kernel(s, nm)
                if k is None:
                    continue
                dist = {}
                const_lo = const_up = 0.0
                for t, p in k.items():
                    if t in index:
                        dist[index[t]] = dist.get(index[t], 0.0) + p
                    elif L.is_goal(t):
                        j = goals.setdefault(t, m + len(goals))
                        dist[j] = dist.get(j, 0.0) + p
                    else:
                        bi = G.index.get(C.coarsen(t))
                        if bi is None:
                            raise RuntimeError(f"leaf block missing from the coarse graph: {C.coarsen(t)}")
                        const_lo += p * lowv[bi]
                        const_up += p * upv[bi]
                        leaves[t] = bi
                edges += len(dist)
                acts_lo.append((True, [(price[nm] + const_lo, dist)]))
                acts_up.append((True, [(price[nm] + const_up, dist)]))
            table_lo.append(acts_lo)
            table_up.append(acts_up)
        total = m + len(goals)
        goal_flags = [False] * m + [True] * len(goals)
        for t_ in (table_lo, table_up):
            t_.extend([[] for _ in goals])
        Glo = Graph.from_tables(total, goal_flags, table_lo)
        Gup = Graph.from_tables(total, goal_flags, table_up)
        Vlo = Glo.solve_pi("lower")
        Vhi = Gup.solve_pi("lower")
        elo, ehi = Glo.residual("lower", Vlo), Gup.residual("lower", Vhi)
        low = Vlo[0] * Glo.bracket(Vlo, elo)[0]
        up = Vhi[0] * Gup.bracket(Vhi, ehi)[1]
        out.append(dict(cfg=cfg, theta=theta, expanded=m, leaves=len(leaves), edges=edges, lower=low, upper=up, gap=up / low - 1,
                        seconds=round(time.time() - t0, 1)))
    return out


def levels_run(cfg, names, price):
    return globals()["run_level"](cfg, names, price)


import levels
run_level = levels.run

if __name__ == "__main__":
    cfg = sys.argv[1]
    thetas = [float(x) for x in sys.argv[2:]]
    for row in run(cfg, thetas):
        print(json.dumps(row), flush=True)
