"""Cuts by cost bounds on an exact quotient graph (ticket #312, the owner's correction): what each kind of cut removes.

    python research/312/prune_analysis.py QUOTIENT.pkl [--factors 1.0,1.5,3.0] [--steps 0,1,2,4,8,16,32] [--out FILE.json]

The input is the `*.quotient.pkl` that `exact_classes.py` writes (one state per exact class, kernels as numpy arrays).
Everything here is about the quotient, which is small, so it runs in seconds to minutes on one core.

BOUNDS. LB_0(s) is the cost of the cheapest path to the goal when every use gets its luckiest outcome (a shortest
path on the actions' costs): it never exceeds the optimal value V*(s). UB_0(s) is the price of a known route:
f * V*(start) for the start (the incumbent; f = 1 is a perfect incumbent) and one restart plus that for every
other state, because from any other state the route "buy the start item again, then follow the incumbent" is
available. Both are then improved by k Bellman backups (value iteration from below and from above); each backup
keeps LB <= V* <= UB. k is the effort spent on the bound.

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
model) or p * LB (optimistic model). The two models bracket the exact value, V_opt <= V* <= V_pess, and the choice
at every state with a positive margin cannot change by the lumping.
"""

import argparse
import heapq
import json
import math
import pickle
import time
from pathlib import Path

import numpy as np


def load(path: Path) -> dict:
    with open(path, "rb") as handle:
        return pickle.load(handle)


def flatten(g: dict):
    """Arrays over the action entries: state, cost, kernel; edges: destination and probability (float64)."""
    n = g["n"]
    ptr = np.array(g["act_ptr"], dtype=np.int64)
    cost = np.array(g["act_cost"], dtype=np.float64)
    kernel = np.array(g["act_kernel"], dtype=np.int64)
    state = np.repeat(np.arange(n), np.diff(ptr))
    probs = []
    for wt in g["k_wt"]:
        ints = [int(x) for x in wt.tolist()]
        total = sum(ints)
        probs.append(np.array([x / total for x in ints]))
    sizes = np.array([len(g["k_succ"][k]) for k in kernel], dtype=np.int64)
    edge_ptr = np.concatenate(([0], np.cumsum(sizes)))
    dst = np.concatenate([g["k_succ"][k] for k in kernel]).astype(np.int64) if len(kernel) else np.zeros(0, dtype=np.int64)
    pr = np.concatenate([probs[k] for k in kernel]) if len(kernel) else np.zeros(0)
    return {"n": n, "ptr": ptr, "cost": cost, "state": state, "edge_ptr": edge_ptr, "dst": dst, "p": pr, "goal": np.frombuffer(g["goal"], dtype=np.uint8) == 1}


def q_values(flat: dict, v: np.ndarray) -> np.ndarray:
    """cost + sum p * v(dst) for every action entry."""
    contribution = flat["p"] * v[flat["dst"]]
    sums = np.add.reduceat(contribution, flat["edge_ptr"][:-1]) if len(contribution) else np.zeros(0)
    sizes = np.diff(flat["edge_ptr"])
    sums[sizes == 0] = 0.0
    return flat["cost"] + sums


def state_min(flat: dict, q: np.ndarray) -> np.ndarray:
    n = flat["n"]
    best = np.full(n, np.inf)
    np.minimum.at(best, flat["state"], q)
    best[flat["goal"]] = 0.0
    return best


def shortest_to_goal(flat: dict) -> np.ndarray:
    """LB_0: the cheapest path to the goal over the actions' costs, a use that leaves the state counted (Dijkstra backwards)."""
    n = flat["n"]
    incoming: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for t in range(len(flat["cost"])):
        s = int(flat["state"][t])
        c = float(flat["cost"][t])
        for d in np.unique(flat["dst"][flat["edge_ptr"][t] : flat["edge_ptr"][t + 1]]).tolist():
            if d != s:
                incoming[d].append((s, c))
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
        for u, c in incoming[s]:
            if d + c < dist[u]:
                dist[u] = d + c
                heapq.heappush(heap, (d + c, u))
    return dist


def reach(flat: dict, start: int, keep: np.ndarray) -> np.ndarray:
    """States reachable from `start` through the action entries marked in `keep`."""
    seen = np.zeros(flat["n"], dtype=bool)
    seen[start] = True
    stack = [start]
    ptr = flat["ptr"]
    while stack:
        s = stack.pop()
        if flat["goal"][s]:
            continue
        for t in range(ptr[s], ptr[s + 1]):
            if not keep[t]:
                continue
            for d in flat["dst"][flat["edge_ptr"][t] : flat["edge_ptr"][t + 1]].tolist():
                if not seen[d]:
                    seen[d] = True
                    stack.append(d)
    return seen


def exact_values(g: dict, start: int):
    from crafting_system.solver import Action, Outcome, TabularModel, solve

    goals = [s for s in range(g["n"]) if g["goal"][s]]
    table = {}
    for s in range(g["n"]):
        if g["goal"][s]:
            continue
        acts = []
        for t in range(g["act_ptr"][s], g["act_ptr"][s + 1]):
            k = g["act_kernel"][t]
            acts.append(Action(str(g["act_offer"][t]), g["act_cost"][t], tuple(Outcome(int(a), int(w)) for a, w in zip(g["k_succ"][k].tolist(), g["k_wt"][k].tolist()))))
        table[s] = acts
    solution = solve(TabularModel(goals, table), [start])
    v = np.full(g["n"], np.inf)
    for s, value in solution.values.items():
        v[s] = value
    return v


def solve_lumped(g: dict, flat: dict, start: int, keep: np.ndarray, allowance: np.ndarray, bound: np.ndarray, mode: str, goal_class: int):
    """Value of the model where, in every kept action, outcomes of swing <= allowance are lumped (to the goal, charged `bound`)."""
    from crafting_system.solver import Action, Outcome, TabularModel, solve

    sizes_total = 0
    table = {}
    goals = [goal_class]
    reachable = reach(flat, start, keep)
    for s in np.flatnonzero(reachable).tolist():
        if flat["goal"][s]:
            continue
        acts = []
        for t in range(flat["ptr"][s], flat["ptr"][s + 1]):
            if not keep[t]:
                continue
            k = g["act_kernel"][t]
            succ = g["k_succ"][k].tolist()
            wts = [int(x) for x in g["k_wt"][k].tolist()]
            total = sum(wts)
            lump_w = 0
            extra = 0.0
            outs = []
            for d, w in zip(succ, wts):
                swing_ok = allowance[t] > 0 and (w / total) * (UB_CACHE[d] - LB_CACHE[d]) <= allowance[t] and not flat["goal"][d]
                if swing_ok:
                    lump_w += w
                    extra += (w / total) * bound[d]
                else:
                    outs.append(Outcome(int(d), w))
            if lump_w:
                outs.append(Outcome(goal_class, lump_w))
            sizes_total += len(outs)
            acts.append(Action(f"a{t}", flat["cost"][t] + extra, tuple(outs)))
        table[s] = acts
    solution = solve(TabularModel(goals, table), [start])
    return solution.values[start], int(reachable.sum()), sizes_total


UB_CACHE: np.ndarray = np.zeros(0)
LB_CACHE: np.ndarray = np.zeros(0)


def main() -> None:
    global UB_CACHE, LB_CACHE
    parser = argparse.ArgumentParser()
    parser.add_argument("pickle")
    parser.add_argument("--factors", default="1.0,1.5,3.0")
    parser.add_argument("--steps", default="0,1,2,4,8,16,32")
    parser.add_argument("--dr-step", type=int, default=8)
    parser.add_argument("--out")
    args = parser.parse_args()
    began = time.perf_counter()
    data = load(Path(args.pickle))
    g, start, goal_class, restart_cost = data["graph"], data["start"], data["goal_class"], data["restart_cost"]
    flat = flatten(g)
    n = g["n"]
    result = {"classes": n, "actions": len(flat["cost"]), "edges": len(flat["dst"])}
    v_star = exact_values(g, start)
    result["exact_value_of_start"] = float(v_star[start])
    q_star = q_values(flat, v_star)
    optimal = q_star <= v_star[flat["state"]] * (1 + 1e-9) + 1e-12
    optimal &= ~flat["goal"][flat["state"]]
    floor = reach(flat, start, optimal)
    result["floor"] = {"classes_reachable_by_optimal_actions": int(floor.sum()), "optimal_action_entries": int(optimal.sum())}
    print(f"[{time.perf_counter() - began:.1f}s] exact {v_star[start]:.4f}; the optimal policy reaches {int(floor.sum())} of {n} classes", flush=True)
    lb0 = shortest_to_goal(flat)
    result["lb0_of_start"] = float(lb0[start])
    result["lb0_over_exact_start"] = float(lb0[start] / v_star[start])
    steps = sorted({int(x) for x in args.steps.split(",") if x})
    rows = []
    for f in [float(x) for x in args.factors.split(",") if x]:
        cap = restart_cost + f * v_star[start]
        ub = np.full(n, cap)
        ub[start] = f * v_star[start]
        ub[flat["goal"]] = 0.0
        lb = lb0.copy()
        lb[~np.isfinite(lb)] = 0.0
        k = 0
        for target in steps:
            while k < target:
                lb = state_min(flat, q_values(flat, lb))
                ub = np.minimum(ub, state_min(flat, q_values(flat, ub)))  # never above the incumbent bound either
                k += 1
            q_low = q_values(flat, lb)
            q_up = q_values(flat, ub)
            best_up = state_min(flat, q_up)
            competitive = (q_low <= best_up[flat["state"]] * (1 + 1e-12) + 1e-12) & ~flat["goal"][flat["state"]]
            seen = reach(flat, start, competitive)
            row = {
                "incumbent_factor": f, "backups": k, "competitive_actions": int(competitive.sum()), "of_actions": int((~flat["goal"][flat["state"]]).sum()),
                "classes_reachable": int(seen.sum()), "lb_of_start_over_exact": float(lb[start] / v_star[start]), "ub_of_start_over_exact": float(ub[start] / v_star[start]),
            }
            rows.append(row)
            print(f"[{time.perf_counter() - began:.1f}s] {row}", flush=True)
            if k == args.dr_step:
                # decision relevance at this effort
                UB_CACHE, LB_CACHE = ub.copy(), lb.copy()
                allowance = np.zeros(len(flat["cost"]))
                relevant = reach(flat, start, competitive)
                forced = 0
                settled = 0
                for s in np.flatnonzero(relevant).tolist():
                    if flat["goal"][s]:
                        continue
                    ts = [t for t in range(flat["ptr"][s], flat["ptr"][s + 1]) if competitive[t]]
                    if len(ts) <= 1:
                        forced += 1
                        continue
                    order = sorted(ts, key=lambda t: q_up[t])
                    others = min(q_low[t] for t in order[1:])
                    margin = others - q_up[order[0]]
                    if margin > 0:
                        settled += 1
                        for t in ts:
                            allowance[t] = margin / (2 * max(1, int(flat["edge_ptr"][t + 1] - flat["edge_ptr"][t])))
                dr = {"incumbent_factor": f, "backups": k, "relevant_states": int(relevant.sum()), "states_with_forced_choice": forced, "states_with_positive_margin": settled}
                try:
                    pess, reach_p, edges_p = solve_lumped(g, flat, start, competitive, allowance, ub, "pess", goal_class)
                    opt, reach_o, edges_o = solve_lumped(g, flat, start, competitive, allowance, lb, "opt", goal_class)
                    dr.update({"value_pessimistic": pess, "value_optimistic": opt, "relative_gap": (pess - opt) / v_star[start], "pess_over_exact": pess / v_star[start] - 1, "opt_over_exact": opt / v_star[start] - 1, "edges_after_lumping": edges_p})
                except Exception as error:  # noqa: BLE001
                    dr["error"] = f"{type(error).__name__}: {error}"
                result.setdefault("decision_relevance", []).append(dr)
                print(f"[{time.perf_counter() - began:.1f}s] DR {dr}", flush=True)
    result["branch_and_bound"] = rows
    text = json.dumps(result, indent=1)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
