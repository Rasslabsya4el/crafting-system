"""Encoding B: a dedicated routine.  States are enumerated once; the wide (Chromatic-type) actions share one outcome
table per shell (n, qual) and one aggregate per sweep; the excluded outcome is a per-state correction."""

import time

import numpy as np

from red import GOAL


class Built:
    pass


def build(red, start, max_states=5_000_000):
    t0 = time.time()
    idx = {start: 1}
    keys = [None, start]  # 0 is the goal sentinel
    small_rows = []  # (state, cost, [(target, prob)])
    wide_tabs = {}  # (shell, mode) -> int array of target idx per reduced outcome, probs
    wide_rows = {}  # mode -> list of (state, cost, shell_id, e)
    shell_ids = {}
    labels_small = []
    queue = 1

    def get(k):
        if red.is_goal(k):
            return 0
        i = idx.get(k)
        if i is None:
            i = len(keys)
            idx[k] = i
            keys.append(k)
            if len(keys) > max_states:
                raise MemoryError("too many states")
        return i

    start_goal = red.is_goal(start)
    i = 1
    while i < len(keys):
        k = keys[i]
        for label, cost, outs in red.small(k):
            tot = sum(w for _, w in outs)
            merged = {}
            for kk, w in outs:
                j = get(kk)
                merged[j] = merged.get(j, 0) + w
            small_rows.append((i, cost, [(j, w / tot) for j, w in merged.items()]))
            labels_small.append(label)
        for wspec in red.wide(k):
            label, cost, mode, excl = wspec
            sh = (red.shell(k), mode)
            if sh not in wide_tabs:
                tab, real, D = red.chrom_table(k[0], mode)
                n, qual = k[0], k[2]
                tg = np.array([get((n, c, qual)) for c, _ in tab], dtype=np.int64)
                pw = np.array([w / D for _, w in tab])
                wide_tabs[sh] = (tg, pw, real, D)
                shell_ids[sh] = len(shell_ids)
            tg, pw, real, D = wide_tabs[sh]
            e = (real.get(excl, 0) / D) if excl is not None else 0.0
            wide_rows.setdefault(label if isinstance(label, str) else label, []).append((i, cost, shell_ids[sh], e))
        i += 1
    B = Built()
    B.keys, B.idx = keys, idx
    B.N = len(keys)
    B.start_goal = start_goal
    # small actions as flat arrays
    B.s_state = np.array([r[0] for r in small_rows], dtype=np.int64)
    B.s_cost = np.array([r[1] for r in small_rows], dtype=float)
    lens = [len(r[2]) for r in small_rows]
    B.s_start = np.concatenate([[0], np.cumsum(lens)[:-1]]).astype(np.int64) if small_rows else np.zeros(0, np.int64)
    B.s_t = np.array([t for r in small_rows for t, _ in r[2]], dtype=np.int64)
    B.s_p = np.array([p for r in small_rows for _, p in r[2]])
    # wide actions grouped by label
    B.w = {}
    for label, rows in wide_rows.items():
        st = np.array([r[0] for r in rows], dtype=np.int64)
        co = np.array([r[1] for r in rows])
        sh = np.array([r[2] for r in rows], dtype=np.int64)
        ee = np.array([r[3] for r in rows])
        B.w[label] = (st, co, sh, ee)
    B.tabs = [None] * len(shell_ids)
    for sh, (tg, pw, real, D) in wide_tabs.items():
        B.tabs[shell_ids[sh]] = (tg, pw)
    B.n_shell_entries = sum(len(t[0]) for t in B.tabs)
    B.n_small_edges = len(B.s_t)
    B.n_wide_actions = sum(len(v[0]) for v in B.w.values())
    B.dense_wide_edges = sum(len(B.tabs[sh][0]) for v in B.w.values() for sh in v[2])
    B.dense_edges = B.dense_wide_edges + B.n_small_edges
    B.secs_build = time.time() - t0
    return B


def sweep_q(B, V):
    """One Bellman backup over all states (Jacobi): returns the new value vector."""
    new = np.full(B.N, np.inf)
    if len(B.s_cost):
        contrib = B.s_p * V[B.s_t]
        q = B.s_cost + np.add.reduceat(contrib, B.s_start)
        np.minimum.at(new, B.s_state, q)
    if B.tabs:
        S = np.array([float(pw @ V[tg]) for tg, pw in B.tabs])
        for label, (st, co, sh, ee) in B.w.items():
            q = co * (1.0 - ee) + S[sh]
            new[st] = np.minimum(new[st], q)
    new[0] = 0.0
    return new


def solve(B, tol=1e-12, max_sweeps=2_000_000, report=None):
    V = np.zeros(B.N)
    t0 = time.time()
    for it in range(1, max_sweeps + 1):
        new = sweep_q(B, V)
        d = np.max(np.abs(new[1:] - V[1:])) if B.N > 1 else 0.0
        V = new
        if d < 1e-11:
            break
        if report and it % report == 0:
            print("  sweep", it, d, V[1], flush=True)
    return V, it, time.time() - t0


def prepare(B):
    """Group the small rows by state (they are contiguous) so a sweep needs no scatter."""
    if len(B.s_cost):
        change = np.flatnonzero(np.diff(B.s_state)) + 1
        B.g_start = np.concatenate([[0], change]).astype(np.int64)
        B.g_state = B.s_state[B.g_start]
    return B


def sweep_fast(B, V):
    new = np.full(B.N, np.inf)
    if len(B.s_cost):
        q = B.s_cost + np.add.reduceat(B.s_p * V[B.s_t], B.s_start)
        new[B.g_state] = np.minimum.reduceat(q, B.g_start)
    if B.tabs:
        S = np.fromiter((pw @ V[tg] for tg, pw in B.tabs), dtype=float, count=len(B.tabs))
        for st, co, sh, ee in B.w.values():
            new[st] = np.minimum(new[st], co * (1.0 - ee) + S[sh])
    new[0] = 0.0
    return new


def solve_anderson(B, m=6, tol=1e-11, max_sweeps=200000, report=None):
    """Value iteration with Anderson acceleration, safeguarded by the Bellman residual."""
    prepare(B)
    V = np.zeros(B.N)
    t0 = time.time()
    F = []  # residuals T(V)-V
    X = []  # iterates V
    TV = sweep_fast(B, V)
    r = TV - V
    nres = np.max(np.abs(r[1:]))
    it = 1
    while nres >= tol and it < max_sweeps:
        X.append(V.copy())
        F.append(r.copy())
        if len(F) > m:
            X.pop(0)
            F.pop(0)
        cand = TV  # plain step
        if len(F) >= 2:
            dF = np.stack([F[i + 1] - F[i] for i in range(len(F) - 1)], axis=1)
            dX = np.stack([X[i + 1] - X[i] for i in range(len(X) - 1)], axis=1)
            try:
                gamma, *_ = np.linalg.lstsq(dF[1:], r[1:], rcond=None)
                acc = V + r - (dX + dF) @ gamma
                acc[0] = 0.0
                if np.all(acc[1:] >= 0):
                    Tacc = sweep_fast(B, acc)
                    it += 1
                    racc = np.max(np.abs(Tacc[1:] - acc[1:]))
                    if racc < nres:
                        V, TV = acc, Tacc
                        r = TV - V
                        nres = racc
                        continue
            except np.linalg.LinAlgError:
                pass
        V = TV
        TV = sweep_fast(B, V)
        it += 1
        r = TV - V
        nres = np.max(np.abs(r[1:]))
        if report and it % report == 0:
            print("  sweep", it, nres, V[1], flush=True)
    return TV, it, time.time() - t0, nres
