"""The stages after the exact classes (ticket #312): the quotient, its exact solve, rails, and lumping of rare outcomes.

All of it works on a `Graph` of `exact_classes.py` (the walked graph, or a quotient of it, both numpy kernels).

* `quotient(g, blk)`: one state per class; its actions are the (cost, distribution over classes) pairs of one member,
  the dearer of two actions with one distribution dropped. Solving it gives the exact optimal value of the whole graph.
* `rail(q, ceiling)`: the actions whose expected number of uses in a row, 1 / (1 - chance to stay in the class),
  exceeds `ceiling` are not offered.
* `lump(q, tau, mode)`: every outcome of an action whose chance is below `tau` is lumped into one:
  `pess` (pessimistic) sends the lumped mass to the start state and charges the price of buying the start item again
  for it (the value of every state is at most one restart plus the value of the start, so the model is never cheaper
  than the real one: its value is an upper bound of the exact value), `opt` (optimistic) sends it to the goal for free
  (a lower bound). The two values bracket the exact value.
"""

import math
import time
from collections import defaultdict

import numpy as np

from exact_classes import Graph, say


def dist_of(b: np.ndarray, wt: np.ndarray):
    """(sorted block ids, gcd-reduced weights) of a kernel seen through the block of each successor."""
    if len(b) == 1:
        return b.copy(), np.array([1], dtype=np.int64)
    order = np.argsort(b, kind="stable")
    bs = b[order]
    ws = wt[order]
    cut = np.flatnonzero(np.concatenate(([True], bs[1:] != bs[:-1])))
    ub = bs[cut]
    if len(cut) == len(bs):
        sums = ws
    elif ws.dtype == object:
        ends = [*cut[1:], len(ws)]
        sums = np.array([sum(int(x) for x in ws[a:z]) for a, z in zip(cut, ends)], dtype=object)
    else:
        sums = np.add.reduceat(ws, cut)
    if len(sums) == 1:
        return ub, np.array([1], dtype=np.int64)
    div = math.gcd(*[int(x) for x in sums])
    return ub, (np.array([int(x) // div for x in sums], dtype=object) if sums.dtype == object else sums // div)


def new_graph(n: int) -> Graph:
    q = Graph()
    q.states = [None] * n
    q.goal = bytearray(n)
    q.expanded = n
    return q


def quotient(g: Graph, blk: np.ndarray, start_index: int = 0) -> tuple[Graph, int]:
    """The quotient of a completely walked graph by `blk`: (graph, index of the start class)."""
    n = g.expanded
    assert n == len(g.states), "the quotient needs a complete walk"
    uniq, cls = np.unique(blk[:n], return_inverse=True)
    k = len(uniq)
    rep = np.full(k, n, dtype=np.int64)
    np.minimum.at(rep, cls, np.arange(n))
    q = new_graph(k)
    agg: dict[int, int] = {}
    content: dict = {}
    act_ptr = [0]
    for c in range(k):
        r = int(rep[c])
        if g.goal[r]:
            q.goal[c] = 1
            act_ptr.append(len(q.act_offer))
            continue
        best: dict[int, tuple[float, int]] = {}
        for t in range(g.act_ptr[r], g.act_ptr[r + 1]):
            kid = g.act_kernel[t]
            qk = agg.get(kid)
            if qk is None:
                ub, ws = dist_of(cls[g.k_succ[kid]], g.k_wt[kid])
                key = (ub.tobytes(), ws.tobytes() if ws.dtype != object else tuple(int(x) for x in ws))
                qk = content.get(key)
                if qk is None:
                    qk = len(q.k_succ)
                    content[key] = qk
                    q.k_succ.append(ub.astype(np.int32))
                    q.k_wt.append(ws)
                    q.k_big.append(ws.dtype == object)
                agg[kid] = qk
            cost = g.act_cost[t]
            if qk not in best or cost < best[qk][0]:
                best[qk] = (cost, g.act_offer[t])
        for qk, (cost, offer) in best.items():
            q.act_offer.append(offer)
            q.act_cost.append(cost)
            q.act_kernel.append(qk)
        act_ptr.append(len(q.act_offer))
    q.act_ptr = act_ptr
    q.edges = int(sum(len(q.k_succ[x]) for x in q.act_kernel))
    return q, int(cls[start_index])


def reachable_mask(q: Graph, start: int) -> np.ndarray:
    seen = np.zeros(q.expanded, dtype=bool)
    seen[start] = True
    stack = [start]
    while stack:
        s = stack.pop()
        if q.goal[s]:
            continue
        for t in range(q.act_ptr[s], q.act_ptr[s + 1]):
            for j in q.k_succ[q.act_kernel[t]].tolist():
                if not seen[j]:
                    seen[j] = True
                    stack.append(j)
    return seen


def subgraph(q: Graph, keep: np.ndarray, start: int) -> tuple[Graph, int]:
    """The part of `q` on the states `keep` (closed under successors), reindexed."""
    idx = np.full(q.expanded, -1, dtype=np.int64)
    kept = np.flatnonzero(keep)
    idx[kept] = np.arange(len(kept))
    r = new_graph(len(kept))
    kmap: dict[int, int] = {}
    ptr = [0]
    for s in kept.tolist():
        r.goal[idx[s]] = q.goal[s]
        for t in range(q.act_ptr[s], q.act_ptr[s + 1]):
            kid = q.act_kernel[t]
            nk = kmap.get(kid)
            if nk is None:
                nk = len(r.k_succ)
                kmap[kid] = nk
                r.k_succ.append(idx[q.k_succ[kid]].astype(np.int32))
                r.k_wt.append(q.k_wt[kid])
                r.k_big.append(q.k_big[kid] if kid < len(q.k_big) else False)
            r.act_offer.append(q.act_offer[t])
            r.act_cost.append(q.act_cost[t])
            r.act_kernel.append(nk)
        ptr.append(len(r.act_offer))
    r.act_ptr = ptr
    r.edges = int(sum(len(r.k_succ[x]) for x in r.act_kernel))
    return r, int(idx[start])


def solve_graph(q: Graph, priced, start: int):
    """The product solver on a graph; the `Solution` (values by state index)."""
    from crafting_system.solver import Action, Outcome, TabularModel, solve

    goals = [s for s in range(q.expanded) if q.goal[s]]
    table = {}
    for s in range(q.expanded):
        if q.goal[s]:
            continue
        acts = []
        for t in range(q.act_ptr[s], q.act_ptr[s + 1]):
            k = q.act_kernel[t]
            label = priced[q.act_offer[t]].label if priced is not None else str(q.act_offer[t])
            acts.append(Action(label, q.act_cost[t], tuple(Outcome(int(a), int(w)) for a, w in zip(q.k_succ[k].tolist(), q.k_wt[k].tolist()))))
        table[s] = acts
    return solve(TabularModel(goals, table), [start])


def stay_chance(q: Graph, s: int, t: int) -> float:
    """The chance that action entry `t` of state `s` leaves the item in the same state (class)."""
    k = q.act_kernel[t]
    succ, wt = q.k_succ[k], q.k_wt[k]
    total = sum(int(x) for x in wt.tolist())
    mine = sum(int(w) for a, w in zip(succ.tolist(), wt.tolist()) if a == s)
    return mine / total if total else 0.0


def uses_in_a_row(p_stay: float) -> float:
    return math.inf if p_stay >= 1.0 else 1.0 / (1.0 - p_stay)


def policy_uses(q: Graph, priced, solution, top: int = 8):
    """The expected uses in a row of the action the optimal policy takes in each state: the biggest ones."""
    rows = []
    for s, action in solution.policy.items():
        total = sum(o.weight for o in action.outcomes)
        mine = sum(o.weight for o in action.outcomes if o.state == s)
        rows.append((uses_in_a_row(mine / total), action.label, s))
    rows.sort(reverse=True)
    return [{"expected_uses_in_a_row": round(u, 2), "action": label, "class": s} for u, label, s in rows[:top]]


def rail(q: Graph, ceiling: float) -> tuple[Graph, int]:
    """`q` without the actions whose expected uses in a row exceed `ceiling` (the actions are cut, the states stay)."""
    r = new_graph(q.expanded)
    r.goal = bytearray(q.goal)
    r.k_succ, r.k_wt, r.k_big = q.k_succ, q.k_wt, q.k_big
    ptr = [0]
    dropped = 0
    for s in range(q.expanded):
        for t in range(q.act_ptr[s], q.act_ptr[s + 1]):
            if not q.goal[s] and uses_in_a_row(stay_chance(q, s, t)) > ceiling:
                dropped += 1
                continue
            r.act_offer.append(q.act_offer[t])
            r.act_cost.append(q.act_cost[t])
            r.act_kernel.append(q.act_kernel[t])
        ptr.append(len(r.act_offer))
    r.act_ptr = ptr
    r.dropped_actions = dropped  # type: ignore[attr-defined]
    return r, dropped


def lump(q: Graph, tau: float, mode: str, start: int, goal_class: int, restart_cost: float) -> tuple[Graph, dict]:
    """Outcomes of chance below `tau` lumped into one (`pess`: to the start, paying a restart; `opt`: to the goal)."""
    r = new_graph(q.expanded)
    r.goal = bytearray(q.goal)
    lumped_kernel: dict[int, tuple[int, float]] = {}
    lumped_total = 0.0
    n_lumped = 0
    for kid, (succ, wt) in enumerate(zip(q.k_succ, q.k_wt)):
        total = sum(int(x) for x in wt.tolist())
        probs = np.array([int(x) / total for x in wt.tolist()])
        light = probs < tau
        if not light.any() or light.all() and len(wt) == 1:
            lumped_kernel[kid] = (len(r.k_succ), 0.0)
            r.k_succ.append(succ)
            r.k_wt.append(wt)
            r.k_big.append(False)
            continue
        heavy = ~light
        mass_w = sum(int(x) for x in wt[light].tolist())
        target = start if mode == "pess" else goal_class
        new_succ = np.concatenate((succ[heavy], np.array([target], dtype=succ.dtype)))
        new_wt = np.array([int(x) for x in wt[heavy].tolist()] + [mass_w], dtype=object)
        lumped_kernel[kid] = (len(r.k_succ), mass_w / total)
        r.k_succ.append(new_succ)
        r.k_wt.append(new_wt)
        r.k_big.append(True)
        n_lumped += 1
    ptr = [0]
    masses = []
    for s in range(q.expanded):
        for t in range(q.act_ptr[s], q.act_ptr[s + 1]):
            nk, m = lumped_kernel[q.act_kernel[t]]
            r.act_offer.append(q.act_offer[t])
            r.act_cost.append(q.act_cost[t] + (m * restart_cost if mode == "pess" else 0.0))
            r.act_kernel.append(nk)
            if m:
                masses.append(m)
        ptr.append(len(r.act_offer))
    r.act_ptr = ptr
    info = {"kernels_with_a_lump": n_lumped, "actions_with_a_lump": len(masses), "largest_lumped_mass": max(masses, default=0.0)}
    return r, info


def solve_timed(q: Graph, priced, start: int, seconds: int):
    """`solve_graph` with a wall-clock limit (Linux: SIGALRM); (solution or None, reason)."""
    import signal

    class Timeout(Exception):
        pass

    def handler(signum, frame):
        raise Timeout

    has_alarm = hasattr(signal, "SIGALRM")
    if has_alarm:
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(int(seconds))
    try:
        return solve_graph(q, priced, start), "solved"
    except Timeout:
        return None, f"stopped after {seconds} s"
    except Exception as error:  # noqa: BLE001 (a measurement script reports, it does not stop)
        return None, f"{type(error).__name__}: {error}"
    finally:
        if has_alarm:
            signal.alarm(0)


def raw_reach(g: Graph, start_index: int, tau: float | None = None, ceiling: float | None = None) -> dict:
    """States reachable in the raw graph when edges of chance below `tau` are dropped (lumped to the start) and/or the
    actions whose expected uses in a row exceed `ceiling` are cut. Counts only; no value."""
    heavy_cache: dict[int, np.ndarray] = {}

    def heavy(kid: int) -> np.ndarray:
        found = heavy_cache.get(kid)
        if found is None:
            wt = g.k_wt[kid]
            total = sum(int(x) for x in wt.tolist())
            probs = np.array([int(x) / total for x in wt.tolist()])
            found = g.k_succ[kid][probs >= tau] if tau is not None else g.k_succ[kid]
            if len(found) == 0:
                found = g.k_succ[kid][:0]
            heavy_cache[kid] = found
        return found

    seen = np.zeros(g.expanded, dtype=bool)
    seen[start_index] = True
    stack = [start_index]
    while stack:
        s = stack.pop()
        if g.goal[s]:
            continue
        for t in range(g.act_ptr[s], g.act_ptr[s + 1]):
            kid = g.act_kernel[t]
            if ceiling is not None:
                succ, wt = g.k_succ[kid], g.k_wt[kid]
                total = sum(int(x) for x in wt.tolist())
                mine = sum(int(w) for a, w in zip(succ.tolist(), wt.tolist()) if a == s)
                if uses_in_a_row(mine / total) > ceiling:
                    continue
            for j in heavy(kid).tolist():
                if not seen[j]:
                    seen[j] = True
                    stack.append(j)
    return {"reachable_states": int(seen.sum())}


def policy_total_uses(solution, start: int, max_states: int = 4000) -> dict | None:
    """Expected number of uses, over a whole run from `start`, of each action label under the optimal policy
    (a dense solve of (I - P) x = c on the policy's states; None when there are too many states)."""
    states = list(solution.policy)
    if not states or len(states) > max_states or start not in solution.policy:
        return None
    index = {s: i for i, s in enumerate(states)}
    labels = sorted({str(a.label) for a in solution.policy.values()})
    column = {label: j for j, label in enumerate(labels)}
    n = len(states)
    P = np.zeros((n, n))
    C = np.zeros((n, len(labels)))
    for s, action in solution.policy.items():
        i = index[s]
        total = sum(o.weight for o in action.outcomes)
        C[i, column[str(action.label)]] = 1.0
        for o in action.outcomes:
            j = index.get(o.state)
            if j is not None:
                P[i, j] += o.weight / total
    X = np.linalg.solve(np.eye(n) - P, C)
    row = X[index[start]]
    ranked = sorted(((float(row[j]), label) for label, j in column.items()), reverse=True)
    return {label: round(value, 3) for value, label in ranked[:8]}
