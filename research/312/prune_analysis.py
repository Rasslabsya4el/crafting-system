"""Cuts by cost bounds on an exact quotient graph (ticket #312, the owner's correction): what each kind of cut removes.

    python research/312/prune_analysis.py QUOTIENT.pkl [--factors 1.0,1.5,3.0] [--steps 0,1,2,4,8,16,32] [--dr-step 8] [--out FILE.json]

The input is the `*.quotient.pkl` that `exact_classes.py` writes (one state per exact class, kernels as numpy arrays).
Everything is numpy over the whole quotient (R04's has 90,000 classes and 171 million edges), no solver objects.

VALUES. Every action has its self-loop eliminated (`cost / chance to leave`, outcomes renormalised): the model of the
production solver. V* is found by policy iteration started from a proper policy (the shortest-path tree of LB_0: every
step has a positive chance to lower the distance to the goal, so the policy is proper) and BiCGSTAB for each policy
evaluation. It is a research number, not a certificate: the residual of the Bellman equation is reported with it.

BOUNDS. LB_0(s) is the cost of the cheapest path to the goal when every use gets its luckiest outcome (a shortest path on
the actions' costs per exit): it never exceeds V*(s). UB_0(s) is the price of a known route: f * V*(start) for the start
(the incumbent; f = 1 is a perfect incumbent) and one restart plus that for every other state, because from any other state
the route "buy the start item again, then follow the incumbent" is available. Both are then improved by k Bellman backups
(value iteration from below and from above); each backup keeps LB <= V* <= UB. k is the effort spent on the bound.

EXACT CUT (branch and bound, ADR-0031 at the level of states). An action `a` at state `s` is COMPETITIVE when
cost(a) + sum_p p * LB(s') <= min_b ( cost(b) + sum_p p * UB(s') ). Any other action is worse than a known one,
so it is never part of an optimal route: cutting it changes no answer. The graph that remains is what is
reachable from the start through competitive actions. With LB = UB = V* (k infinite) the competitive actions
are the optimal ones: that is the least any exact cut can leave.

DECISION-RELEVANCE CUT (the answer is bounded, not exact). At a state with several competitive actions the margin is
the best other action's lower Q minus the best action's upper Q (when positive the choice is settled by the bounds);
at a state with one competitive action the choice is forced. An outcome of a competitive action is LUMPED when
its swing p * (UB - LB) is at most the allowance of its state: margin / (2 * outcomes of the action) at a state with
a positive margin, 0 elsewhere (a forced choice has no margin to spend, so nothing is lumped there: the value would
drift without anything to show for it). Lumped mass goes to the goal and the action is charged p * UB (pessimistic
model) or p * LB (optimistic model). The two models bracket the exact value, V_opt <= V* <= V_pess.
"""

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np

BIG = 1e30


def rss_mb() -> float:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:
        return 0.0


def load(path: Path) -> dict:
    with open(path, "rb") as handle:
        return pickle.load(handle)


def flatten(g: dict) -> dict:
    """Arrays over the action entries (state, cost, edge range) and over the edges (destination, chance to leave-normalised)."""
    n = g["n"]
    ptr = np.array(g["act_ptr"], dtype=np.int64)
    cost = np.array(g["act_cost"], dtype=np.float64)
    kernel = np.array(g["act_kernel"], dtype=np.int64)
    state = np.repeat(np.arange(n, dtype=np.int32), np.diff(ptr))
    probs = []
    for wt in g["k_wt"]:
        ints = [int(x) for x in wt.tolist()]
        total = sum(ints)
        probs.append(np.array([x / total for x in ints]))
    sizes = np.array([len(g["k_succ"][k]) for k in kernel], dtype=np.int64)
    edge_ptr = np.concatenate(([0], np.cumsum(sizes)))
    dst = np.concatenate([g["k_succ"][k] for k in kernel]).astype(np.int32) if len(kernel) else np.zeros(0, dtype=np.int32)
    pr = np.concatenate([probs[k] for k in kernel]) if len(kernel) else np.zeros(0)
    act_of_edge = np.repeat(np.arange(len(kernel), dtype=np.int32), sizes)
    is_self = dst == state[act_of_edge]
    nonempty = sizes > 0
    stay = np.zeros(len(kernel))
    if len(pr):
        stay[nonempty] = np.add.reduceat(pr * is_self, edge_ptr[:-1][nonempty])
    leaves = 1.0 - stay
    dead = leaves <= 1e-15
    safe = np.where(dead, 1.0, leaves)
    cost_e = np.where(dead, np.inf, cost / safe)
    p_e = np.where(is_self | dead[act_of_edge], 0.0, pr / safe[act_of_edge])
    del pr, is_self
    goal = np.frombuffer(g["goal"], dtype=np.uint8) == 1
    return {
        "n": n, "ptr": ptr, "cost": cost_e, "cost_raw": cost, "stay": stay, "state": state, "edge_ptr": edge_ptr, "sizes": sizes,
        "dst": dst, "p": p_e, "act_of_edge": act_of_edge, "goal": goal,
        "nonempty_state": np.flatnonzero((np.diff(ptr) > 0) & ~goal),
    }


def sums_over_actions(flat: dict, per_edge: np.ndarray) -> np.ndarray:
    out = np.zeros(len(flat["cost"]))
    ok = flat["sizes"] > 0
    if len(per_edge):
        out[ok] = np.add.reduceat(per_edge, flat["edge_ptr"][:-1][ok])
    return out


def q_values(flat: dict, v: np.ndarray, cost: np.ndarray | None = None, p: np.ndarray | None = None) -> np.ndarray:
    """cost + sum p * v(dst) for every action entry."""
    p = flat["p"] if p is None else p
    cost = flat["cost"] if cost is None else cost
    return cost + sums_over_actions(flat, p * v[flat["dst"]])


def state_min(flat: dict, q: np.ndarray) -> np.ndarray:
    """Best q per state (0 for a goal state, BIG for a state without a usable action)."""
    best = np.full(flat["n"], BIG)
    s = flat["nonempty_state"]
    if len(s):
        best[s] = np.minimum.reduceat(q, flat["ptr"][s])
    best = np.minimum(best, BIG)
    best[flat["goal"]] = 0.0
    return best


def state_argmin(flat: dict, q: np.ndarray, best: np.ndarray) -> np.ndarray:
    """The first action entry reaching the best q of its state (-1 for a state without actions)."""
    idx = np.where(q <= best[flat["state"]] * (1 + 1e-13) + 1e-13, np.arange(len(q)), len(q))
    pol = np.full(flat["n"], -1, dtype=np.int64)
    s = flat["nonempty_state"]
    if len(s):
        pol[s] = np.minimum.reduceat(idx, flat["ptr"][s])
    pol[pol >= len(q)] = -1
    return pol


def expand_ranges(starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """The concatenation of range(a, b) for each pair."""
    lens = ends - starts
    total = int(lens.sum())
    if total == 0:
        return np.zeros(0, dtype=np.int64)
    first = np.repeat(starts - np.concatenate(([0], np.cumsum(lens)[:-1])), lens)
    return first + np.arange(total)


def shortest_to_goal(flat: dict) -> np.ndarray:
    """LB_0: the cheapest path to the goal over the actions' per-exit costs (Dijkstra backwards with a heap over vectorised relaxations)."""
    import heapq

    n = flat["n"]
    # reverse adjacency per action entry: (source state, cost) -> destinations; built as sorted edge arrays
    src = flat["state"][flat["act_of_edge"]].astype(np.int32)
    keep = (flat["dst"] != src) & (flat["p"] > 0)
    d_dst = flat["dst"][keep]
    d_src = src[keep]
    d_cost = flat["cost"][flat["act_of_edge"][keep]]
    order = np.argsort(d_dst, kind="stable")
    d_dst, d_src, d_cost = d_dst[order], d_src[order], d_cost[order]
    start_of = np.searchsorted(d_dst, np.arange(n + 1))
    dist = np.full(n, np.inf)
    heap = []
    for s in np.flatnonzero(flat["goal"]).tolist():
        dist[s] = 0.0
        heap.append((0.0, s))
    heapq.heapify(heap)
    while heap:
        d, s = heapq.heappop(heap)
        if d > dist[s]:
            continue
        a, b = start_of[s], start_of[s + 1]
        if a == b:
            continue
        us, cs = d_src[a:b], d_cost[a:b]
        cand = d + cs
        better = cand < dist[us]
        if better.any():
            for u, c in zip(us[better].tolist(), cand[better].tolist()):
                if c < dist[u]:
                    dist[u] = c
                    heapq.heappush(heap, (c, u))
    return dist


def reach(flat: dict, start: int, keep: np.ndarray) -> np.ndarray:
    """States reachable from `start` through the action entries marked in `keep` (level by level, vectorised)."""
    n = flat["n"]
    seen = np.zeros(n, dtype=bool)
    seen[start] = True
    frontier = np.array([start], dtype=np.int64)
    ptr, edge_ptr, dst = flat["ptr"], flat["edge_ptr"], flat["dst"]
    while len(frontier):
        frontier = frontier[~flat["goal"][frontier]]
        ts = expand_ranges(ptr[frontier], ptr[frontier + 1])
        ts = ts[keep[ts]]
        es = expand_ranges(edge_ptr[ts], edge_ptr[ts + 1])
        new = np.unique(dst[es])
        new = new[~seen[new]]
        seen[new] = True
        frontier = new.astype(np.int64)
    return seen


# ---- values ---------------------------------------------------------------------------------------------------------


def policy_values(flat: dict, pol: np.ndarray, cost: np.ndarray, p: np.ndarray, v0: np.ndarray, tol: float = 1e-12, max_iter: int = 4000):
    """Value of the proper policy `pol` (an action entry per non-goal state): solve (I - A) v = c by BiCGSTAB. Returns (v, residual, iterations)."""
    n = flat["n"]
    states = np.flatnonzero(~flat["goal"] & (pol >= 0))
    ts = pol[states]
    e_idx = expand_ranges(flat["edge_ptr"][ts], flat["edge_ptr"][ts + 1])
    sizes = flat["sizes"][ts]
    starts = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    dst_p = flat["dst"][e_idx]
    p_p = p[e_idx]
    c = cost[ts]
    has = sizes > 0

    def matvec(x: np.ndarray) -> np.ndarray:
        """(I - A) x on the non-goal states; x is a full-length vector, goal entries are 0."""
        ax = np.zeros(n)
        if len(p_p):
            ax[states[has]] = np.add.reduceat(p_p * x[dst_p], starts[has])
        out = x - ax
        out[flat["goal"]] = 0.0
        return out

    b = np.zeros(n)
    b[states] = c
    x = v0.copy()
    x[flat["goal"]] = 0.0
    r = b - matvec(x)
    r0 = r.copy()
    rho = alpha = omega = 1.0
    v = np.zeros(n)
    pv = np.zeros(n)
    bnorm = max(np.linalg.norm(b), 1e-300)
    it = 0
    while it < max_iter and np.linalg.norm(r) > tol * bnorm:
        it += 1
        rho_new = float(r0 @ r)
        if rho_new == 0.0:
            break
        beta = (rho_new / rho) * (alpha / omega)
        pv = r + beta * (pv - omega * v)
        v = matvec(pv)
        alpha = rho_new / float(r0 @ v)
        s = r - alpha * v
        if np.linalg.norm(s) <= tol * bnorm:
            x = x + alpha * pv
            r = s
            break
        t = matvec(s)
        omega = float(t @ s) / float(t @ t)
        x = x + alpha * pv + omega * s
        r = s - omega * t
        rho = rho_new
    return x, float(np.linalg.norm(r) / bnorm), it


def solve_values(flat: dict, cost: np.ndarray, p: np.ndarray, active: np.ndarray, start: int, say=print, max_rounds: int = 40):
    """V* of the model (cost, p) restricted to the `active` action entries: policy iteration from a proper policy.

    Returns (v, info). `info` has the Bellman residual max_s |min_a Q(s,a) - V(s)| / V(start) of the result.
    """
    t0 = time.perf_counter()
    cost_a = np.where(active, cost, np.inf)
    # a proper start policy: the action whose luckiest outcome lowers the distance to the goal the most
    lb0 = shortest_to_goal({**flat, "cost": cost_a, "p": p})
    lb0_cap = np.where(np.isfinite(lb0), lb0, BIG)
    # the luckiest successor of each action (the minimum of lb0 over the outcomes with a chance)
    mins = np.full(len(cost), BIG)
    ok = flat["sizes"] > 0
    if len(p):
        masked = np.where(p > 0, lb0_cap[flat["dst"]], BIG)
        mins[ok] = np.minimum.reduceat(masked, flat["edge_ptr"][:-1][ok])
    q0 = cost_a + mins
    best = state_min(flat, q0)
    live = reach(flat, start, active) & ~flat["goal"]
    pol = np.where(live, state_argmin(flat, q0, best), -1)
    v = np.where(np.isfinite(lb0), lb0, 0.0)
    value = None
    rounds = 0
    resid = None
    for rounds in range(1, max_rounds + 1):
        value, resid, iterations = policy_values(flat, pol, cost_a, p, v)
        q = cost_a + sums_over_actions(flat, p * value[flat["dst"]])
        best = state_min(flat, q)
        new_pol = state_argmin(flat, q, best)
        better = live & (q[np.maximum(new_pol, 0)] < q[np.maximum(pol, 0)] - 1e-10 * np.maximum(1.0, np.abs(value)))
        improved = int(better.sum())
        say(f"  policy iteration {rounds}: v(start) {value[start]:.6f}, linear residual {resid:.1e} in {iterations} iterations, {improved} states improve")
        v = value
        if improved == 0:
            break
        pol = np.where(better, new_pol, pol)
    q = cost_a + sums_over_actions(flat, p * value[flat["dst"]])
    best = state_min(flat, q)
    mask = live & (best < BIG)
    bellman = float(np.max(np.abs(best[mask] - value[mask])) / max(value[start], 1e-300)) if mask.any() else 0.0
    return value, {"rounds": rounds, "bellman_residual_over_start": bellman, "linear_residual": resid, "seconds": round(time.perf_counter() - t0, 1)}


# ---- the analysis ----------------------------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pickle")
    parser.add_argument("--factors", default="0,1.0,1.5", help="incumbent factors f (the start is priced f * V*, every other state one restart more); 0 = a perfect incumbent in every state (UB = V*)")
    parser.add_argument("--steps", default="0,1,2,4,8,16,32")
    parser.add_argument("--dr-step", type=int, default=8)
    parser.add_argument("--lb-steps", default="0,8", help="sweeps on top of a coarse-model lower bound")
    parser.add_argument("--out")
    args = parser.parse_args()
    began = time.perf_counter()

    def say(text: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s] {text}", flush=True)

    data = load(Path(args.pickle))
    g, start, goal_class, restart_cost = data["graph"], data["start"], data["goal_class"], data["restart_cost"]
    flat = flatten(g)
    say(f"peak memory after flattening {rss_mb():,.0f} MB")
    flat["class_sizes"] = np.asarray(data.get("class_sizes", np.ones(g["n"], dtype=np.int64)), dtype=np.int64)
    result_raw = data.get("raw")
    lb_arrays = data.get("lb_arrays") or {}
    del data, g
    n = flat["n"]
    say(f"flat: {n:,} classes, {len(flat['cost']):,} actions, {len(flat['dst']):,} edges")
    result = {"classes": n, "actions": len(flat["cost"]), "edges": len(flat["dst"]), "raw_graph": result_raw, "raw_states_in_all_classes": int(flat["class_sizes"].sum())}
    all_active = np.ones(len(flat["cost"]), dtype=bool)
    v_star, info = solve_values(flat, flat["cost"], flat["p"], all_active, start, say)
    result["exact_value_of_start"] = float(v_star[start])
    result["value_solve"] = info
    say(f"V*(start) = {v_star[start]:.6f}; {info}")
    q_star = q_values(flat, v_star)
    non_goal_action = ~flat["goal"][flat["state"]]
    optimal = (q_star <= v_star[flat["state"]] * (1 + 1e-9) + 1e-12) & non_goal_action
    # how far from optimal the other actions are (relative to the value of their state), among the actions of the classes the optimal policy reaches
    gap = (q_star - v_star[flat["state"]]) / np.maximum(v_star[flat["state"]], 1e-300)
    in_floor = reach(flat, start, optimal)[flat["state"]] & non_goal_action & ~optimal
    edges_of = [0.0, 1e-9, 1e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0, 10.0, float("inf")]
    counts_ = np.histogram(np.minimum(gap[in_floor], 1e9), bins=[0.0, 1e-9, 1e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0, 10.0, 1e10])[0]
    result["action_gap_histogram_in_optimal_reach"] = dict(zip(["<=1e-9 (ties)", "<=0.1%", "<=1%", "<=3%", "<=10%", "<=30%", "<=100%", "<=10x", ">10x"], counts_.tolist()))
    floor = reach(flat, start, optimal)
    result["floor"] = {"classes_reachable_by_optimal_actions": int(floor.sum()), "optimal_action_entries": int(optimal.sum()), "raw_states_in_those_classes": int(flat["class_sizes"][floor].sum())}
    say(f"the optimal policy reaches {int(floor.sum())} of {n} classes through {int(optimal.sum())} actions")
    lb0 = shortest_to_goal(flat)
    lb0_finite = np.where(np.isfinite(lb0), lb0, 0.0)
    result["lb0_of_start"] = float(lb0[start])
    result["lb0_over_exact_start"] = float(lb0[start] / v_star[start])
    steps = sorted({int(x) for x in args.steps.split(",") if x})
    rows = []
    sizes = flat["sizes"]
    for f in [float(x) for x in args.factors.split(",") if x]:
        cap = restart_cost + f * v_star[start]
        ub = np.full(n, cap)
        ub[start] = f * v_star[start]
        if f == 0:  # the best case for any cut: every state's upper bound is its own optimal value
            ub = v_star.copy()
        ub[flat["goal"]] = 0.0
        lb = lb0.copy()
        lb[~np.isfinite(lb)] = 0.0
        k = 0
        for target in steps:
            t_backup = time.perf_counter()
            while k < target:
                lb = state_min(flat, q_values(flat, lb))
                ub = np.minimum(ub, state_min(flat, q_values(flat, ub)))  # never above the incumbent bound either
                k += 1
            backup_seconds = time.perf_counter() - t_backup
            q_low = q_values(flat, lb)
            q_up = q_values(flat, ub)
            best_up = state_min(flat, q_up)
            competitive = (q_low <= best_up[flat["state"]] * (1 + 1e-12) + 1e-12) & non_goal_action
            seen = reach(flat, start, competitive)
            reached_actions = competitive & seen[flat["state"]]
            row = {
                "incumbent_factor": f, "backups": k, "backup_seconds_since_last_row": round(backup_seconds, 1),
                "competitive_actions": int(competitive.sum()), "of_actions": int(non_goal_action.sum()),
                "competitive_actions_reached": int(reached_actions.sum()), "edges_of_those": int(sizes[reached_actions].sum()), "of_edges": int(sizes[non_goal_action].sum()),
                "classes_reachable": int(seen.sum()), "raw_states_in_reached_classes": int(flat["class_sizes"][seen].sum()), "lb_of_start_over_exact": float(lb[start] / v_star[start]), "ub_of_start_over_exact": float(ub[start] / v_star[start]),
            }
            rows.append(row)
            say(str(row))
            if k == args.dr_step and f != 0:
                result.setdefault("decision_relevance", []).append(decision_relevance(flat, start, v_star, lb, ub, q_low, q_up, competitive, f, k, say))
    # lower bounds from the optimistic coarse models (exact_classes.py --coarse-lb): max of the model's bound and the sweeps' bound
    for name, entry in lb_arrays.items():
        for f in [float(x) for x in args.factors.split(",") if x]:
            cap = restart_cost + f * v_star[start]
            ub = np.full(n, cap)
            ub[start] = f * v_star[start]
            if f == 0:
                ub = v_star.copy()
            ub[flat["goal"]] = 0.0
            lb = np.maximum(lb0_finite, entry["lb"])
            lb[flat["goal"]] = 0.0
            k = 0
            for target in sorted({int(x) for x in args.lb_steps.split(",") if x}):
                while k < target:
                    lb = np.maximum(lb, state_min(flat, q_values(flat, lb)))
                    ub = np.minimum(ub, state_min(flat, q_values(flat, ub)))
                    k += 1
                q_low = q_values(flat, lb)
                q_up = q_values(flat, ub)
                best_up = state_min(flat, q_up)
                competitive = (q_low <= best_up[flat["state"]] * (1 + 1e-12) + 1e-12) & non_goal_action
                seen = reach(flat, start, competitive)
                reached_actions = competitive & seen[flat["state"]]
                row = {
                    "lb_source": name, "coarse_states": entry["coarse_states"], "incumbent_factor": f, "backups": k,
                    "competitive_actions": int(competitive.sum()), "of_actions": int(non_goal_action.sum()), "competitive_actions_reached": int(reached_actions.sum()),
                    "edges_of_those": int(sizes[reached_actions].sum()), "of_edges": int(sizes[non_goal_action].sum()), "classes_reachable": int(seen.sum()),
                    "raw_states_in_reached_classes": int(flat["class_sizes"][seen].sum()), "lb_of_start_over_exact": float(lb[start] / v_star[start]),
                    "ub_of_start_over_exact": float(ub[start] / v_star[start]),
                }
                rows.append(row)
                say(str(row))
                if k == args.dr_step and f == 1.0:
                    dr = decision_relevance(flat, start, v_star, lb, ub, q_low, q_up, competitive, f, k, say)
                    dr["lb_source"] = name
                    result.setdefault("decision_relevance", []).append(dr)
    result["branch_and_bound"] = rows
    result["peak_rss_mb"] = round(rss_mb())
    text = json.dumps(result, indent=1)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


def decision_relevance(flat, start, v_star, lb, ub, q_low, q_up, competitive, f, k, say):
    """Lump the outcomes whose swing cannot change a settled choice; solve the pessimistic and the optimistic model.

    The margin of a state is taken over ALL its actions: the best action by upper Q against the lowest lower Q of the others.
    A positive margin means the bounds settle the choice (the others were cut by the exact rule); only then the outcomes of the
    chosen action get an allowance, margin / (2 * outcomes). A state with one action has no choice and no margin to spend.
    """
    n = flat["n"]
    seen = reach(flat, start, competitive)
    best_up = state_min(flat, q_up)
    state = flat["state"]
    non_goal_action = ~flat["goal"][state]
    top = state_argmin(flat, np.where(non_goal_action, q_up, np.inf), best_up)
    is_top = np.arange(len(state)) == top[state]
    low_others = np.where(is_top | ~non_goal_action, np.inf, q_low)
    others = np.full(n, np.inf)
    s = flat["nonempty_state"]
    if len(s):
        others[s] = np.minimum.reduceat(low_others, flat["ptr"][s])
    margin = others - np.where(top >= 0, q_up[np.maximum(top, 0)], np.inf)
    n_actions = np.diff(flat["ptr"])
    relevant = seen & ~flat["goal"]
    forced = relevant & (n_actions <= 1)
    settled = relevant & (n_actions > 1) & (margin > 0)
    allowance = np.where(is_top & settled[state], margin[state] / (2.0 * np.maximum(1, flat["sizes"])), 0.0)
    swing = flat["p"] * (ub[flat["dst"]] - lb[flat["dst"]])
    a_edge = allowance[flat["act_of_edge"]]
    not_goal_dst = ~flat["goal"][flat["dst"]]
    lumpable = (a_edge > 0) & (flat["p"] > 0) & (swing <= a_edge) & not_goal_dst
    row = {
        "incumbent_factor": f, "backups": k, "relevant_states": int(relevant.sum()), "states_with_forced_choice": int(forced.sum()),
        "states_with_positive_margin": int(settled.sum()), "edges_lumped": int((lumpable & competitive[flat["act_of_edge"]]).sum()),
    }
    out = {}
    for name, bound in (("pess", ub), ("opt", lb)):
        extra = sums_over_actions(flat, np.where(lumpable, flat["p"] * bound[flat["dst"]], 0.0))
        p2 = np.where(lumpable, 0.0, flat["p"])
        value, info = solve_values(flat, flat["cost"] + extra, p2, competitive, start, lambda _t: None)
        out[name] = float(value[start])
        row[f"value_{name}"] = float(value[start])
        row[f"residual_{name}"] = info["bellman_residual_over_start"]
        row[f"edges_kept_{name}"] = int(((~lumpable) & (flat["p"] > 0) & competitive[flat["act_of_edge"]] & seen[state[flat["act_of_edge"]]]).sum())
    row["relative_gap"] = (out["pess"] - out["opt"]) / v_star[start]
    row["pess_over_exact"] = out["pess"] / v_star[start] - 1
    row["opt_over_exact"] = out["opt"] / v_star[start] - 1
    say("DR " + str(row))
    return row


if __name__ == "__main__":
    main()
