"""Dense reference: the explicit graph of every reachable state, built once; value iteration then policy iteration."""

import time

import numpy as np


class Graph:
    """Explicit transitions of a model whose states do not depend on the target (goal handled by a mask)."""

    def __init__(self, model, start, expand_goals=True):
        index = {start: 0}
        states = [start]
        rows = []
        i = 0
        while i < len(states):
            s = states[i]
            if not expand_goals and model.is_goal(s):
                rows.append([])
                i += 1
                continue
            out = []
            for label, cost, dist in model.actions(s):
                tl = []
                for t, pr in dist.items():
                    j = index.get(t)
                    if j is None:
                        j = len(states)
                        index[t] = j
                        states.append(t)
                    tl.append((j, float(pr)))
                out.append((label, float(cost), tl))
            rows.append(out)
            i += 1
        self.states, self.index, self.rows = states, index, rows
        N = len(states)
        self.N = N
        fc, fs, et, ep, res = [], [], [], [], []
        for s, acts in enumerate(rows):
            for label, cost, tl in acts:
                fc.append(cost)
                fs.append(s)
                res.append(len(et))
                for t, p in tl:
                    et.append(t)
                    ep.append(p)
        self.fc = np.array(fc)
        self.fs = np.array(fs)
        self.et = np.array(et)
        self.ep = np.array(ep)
        self.res = np.array(res)
        self.ends = np.append(self.res[1:], len(et))
        self.edge_row = np.repeat(np.arange(len(fc)), self.ends - self.res)
        self.row_first = np.searchsorted(self.fs, np.arange(N))
        self.nrows = np.array([len(a) for a in rows])
        self.edges = len(et)


def solve(G, goal, sweeps=150):
    """Optimal expected cost from state 0 with `goal` (bool array over G.states) absorbing at cost 0.

    Returns (V, resid) or None when a state reachable from the start cannot reach a goal."""
    N = G.N
    # states reachable from the start without leaving a goal
    seen = np.zeros(N, bool)
    seen[0] = True
    stack = [0]
    pred = {}
    while stack:
        s = stack.pop()
        if goal[s]:
            continue
        for label, cost, tl in G.rows[s]:
            for t, p in tl:
                pred.setdefault(t, set()).add(s)
                if not seen[t]:
                    seen[t] = True
                    stack.append(t)
    # dead-end check: every reachable non-goal state must reach a goal
    ok = goal & seen
    stack = list(np.where(ok)[0])
    while stack:
        t = stack.pop()
        for s in pred.get(t, ()):
            if not ok[s]:
                ok[s] = True
                stack.append(s)
    if not ok[0]:
        return None
    reach_ng = seen & ~goal
    if (reach_ng & ~ok).any():
        return None
    active = reach_ng
    V = np.zeros(N)
    gz = goal

    def q_of(V):
        contrib = G.ep * np.where(gz[G.et], 0.0, V[G.et])
        return G.fc + np.add.reduceat(contrib, G.res)

    has = (G.nrows > 0) & active
    for _ in range(sweeps):  # warm start
        Q = q_of(V)
        mins = np.minimum.reduceat(Q, G.row_first[G.nrows > 0])
        newV = np.zeros(N)
        sel = np.where(G.nrows > 0)[0]
        newV[sel] = mins
        newV[~active] = 0.0
        V = newV
    Q = q_of(V)
    hs = np.where(G.nrows > 0)[0]
    rf = G.row_first[hs]
    rowstate = G.fs
    nrow = len(G.fc)
    ridx = np.arange(nrow)

    def greedy(Q, pol=None):
        mins = np.minimum.reduceat(Q, rf)
        mrow = np.full(N, np.inf)
        mrow[hs] = mins
        cand = np.where(Q <= mrow[rowstate], ridx, nrow + 1)
        best = np.full(N, -1)
        best[hs] = np.minimum.reduceat(cand, rf)
        return best, mrow

    pol, _ = greedy(Q)
    nonterm = np.where(has)[0]
    nonidx = -np.ones(N, int)
    nonidx[nonterm] = np.arange(len(nonterm))
    M = len(nonterm)
    for it in range(100):
        A = np.eye(M)
        b = G.fc[pol[nonterm]]
        chosen = np.zeros(len(G.fc), bool)
        chosen[pol[nonterm]] = True
        sel = chosen[G.edge_row] & (nonidx[G.et] >= 0)
        np.add.at(A, (nonidx[G.fs[G.edge_row[sel]]], nonidx[G.et[sel]]), -G.ep[sel])
        sol = np.linalg.solve(A, b)
        V = np.zeros(N)
        V[nonterm] = sol
        Q = q_of(V)
        best, mrow = greedy(Q)
        cur = Q[np.where(pol >= 0, pol, 0)]
        improve = (pol >= 0) & has & (mrow < cur - 1e-12 * np.maximum(1.0, cur))
        if not improve.any():
            break
        pol = np.where(improve, best, pol)
    Q = q_of(V)
    mins = np.minimum.reduceat(Q, rf)
    resid = 0.0
    cmp = (np.abs(mins - V[hs]) / np.maximum(1.0, V[hs]))[has[hs]]
    resid = float(cmp.max()) if len(cmp) else 0.0
    return V, resid, len(nonterm)


def run(model, start):
    t0 = time.time()
    G = Graph(model, start, expand_goals=False)
    goal = np.array([model.is_goal(s) for s in G.states])
    r = solve(G, goal)
    return {"states": G.N, "edges": G.edges, "start": r[0][0] if r else None, "resid": r[1] if r else None,
            "secs": time.time() - t0}
