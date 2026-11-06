"""Lower bounds on the cost of a route that see the junk mod types (ticket #376): how much of the exact cost does each one give?

    python research/376/junk_bound.py TARGET.yaml --out DIR [--strand-stripped] [--offers twins] [--merge auto|yes|no]
        [--keys NAME,NAME,...|all] [--cut-keys NAME,...] [--seconds S] [--max-flat-edges N]

WHAT IT MEASURES. A *pattern* is a key of the state (the status of the wanted mods, the rarity, the mods per side, the crafted
mods, the kinds of the junk, ...). The *optimistic abstraction* of the pattern has one state per value of the key and offers, in
each, the action of every concrete state that has the key, with its outcomes seen through the key. A concrete policy is a policy of
that model (it takes the action of the member it is in), so the model's optimal value never exceeds a member's exact value: it is an
admissible lower bound, the pattern database of the key. It is the abstraction of research/312/exact_classes.py `--coarse-lb`, with
new keys and a vectorised build.

For every key the script reports the number of abstract states, the value of the start over the exact value of the start (the ratio
the ticket asks for), the check that no state's bound exceeds its exact value, and the seconds and memory of the build. For the
keys named in `--cut-keys` it then says what the bound would cut on the exact quotient: the competitive actions (an action whose cost
with the lower bounds does not exceed the best action's cost with the upper bounds) and the classes reachable through them, with a
perfect upper bound (f = 0, the least any exact cut leaves) and with the incumbent "buy again, then follow the optimal route" (f = 1).

The exact value, the walk and the exact classes are the research/312 code. Never run on a PC for a real route: the walk is hours of
CPU on R14. Run by `.github/scripts/heavy_dispatch.py`; a quick local run on R05, R10, R13 is fine.
"""

import argparse
import gc
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for extra in (ROOT / "research" / "312", ROOT / "research" / "376"):
    if str(extra) not in sys.path:
        sys.path.append(str(extra))

import exact_classes as E  # noqa: E402
import later_stages as L  # noqa: E402
import prune_analysis as P  # noqa: E402
from crafting_system.abstraction._kinds import TYPE_PREFIX, base_kind, kind_tags  # noqa: E402

BIG = P.BIG


def say(began: float, text: str) -> None:
    E.say(began, text)


# ---- the features of a state -------------------------------------------------------------------------------------------


def kind_weights(abstraction) -> dict[str, int]:
    """The pool weight of each numbered family type "~n": the sum of the weights of the mods of its family (what a held junk mod takes out of the pool of an Exalted Orb)."""
    out = {}
    for key, number in abstraction._numbers._numbers.items():
        out[f"{TYPE_PREFIX}{number}"] = int(sum(shape[1] for shape in key[1]))
    return out


FEATURES = (
    "goal", "status", "rarity", "sides", "fractured", "crafted", "junk_tags", "junk_weight", "junk_kinds", "junk_base", "junk_kinds_prefix",
    "junk_kinds_suffix", "junk_n_kinds", "contrib", "slots", "all",
)


def extract(g, abstraction, began) -> dict[str, np.ndarray]:
    """One integer column per feature, over the expanded states of the walk (equal values = equal feature)."""
    weights = kind_weights(abstraction)
    n = g.expanded
    cols = {name: np.empty(n, dtype=np.int64) for name in FEATURES}
    ids = {name: {} for name in FEATURES}
    raw_weight = np.zeros(n, dtype=np.int64)
    side_weight = np.zeros((n, 2), dtype=np.int64)  # held junk weight on the prefix side and on the suffix side
    for r in range(n):
        st = g.states[r]
        ordinary = [s for s in st.slots if not s.crafted]
        values = {
            "goal": int(g.goal[r]),
            "status": tuple(int(x) for x in st.status),
            "rarity": st.flags.rarity.value,
            "sides": (sum(s.side.value == "prefix" for s in st.slots), sum(s.side.value == "suffix" for s in st.slots)),
            "fractured": tuple(f.mod_id for f in st.fractured),
            "crafted": tuple(sorted((s.side.value, s.kind) for s in st.slots if s.crafted)),
            "junk_tags": tuple(sorted(Counter((s.side.value, "attack" in kind_tags(s.kind), "caster" in kind_tags(s.kind)) for s in ordinary).items())),
            "junk_kinds": tuple(sorted((s.side.value, s.kind) for s in ordinary)),
            "junk_base": tuple(sorted((s.side.value, base_kind(s.kind)) for s in ordinary)),
            "junk_kinds_prefix": tuple(sorted(s.kind for s in ordinary if s.side.value == "prefix")),
            "junk_kinds_suffix": tuple(sorted(s.kind for s in ordinary if s.side.value == "suffix")),
            "junk_n_kinds": len({(s.side.value, base_kind(s.kind)) for s in ordinary}),
            "contrib": tuple(sorted((s.side.value, tuple(int(c) for c in s.contribution)) for s in ordinary)),
            "slots": st.slots,
            "all": st,
        }
        raw_weight[r] = sum(weights.get(base_kind(s.kind), 0) for s in ordinary)
        for s in ordinary:
            side_weight[r, 0 if s.side.value == "prefix" else 1] += weights.get(base_kind(s.kind), 0)
        values["junk_weight"] = int(raw_weight[r])
        for name in FEATURES:
            table = ids[name]
            cols[name][r] = table.setdefault(values[name], len(table))
        if r % 200_000 == 199_999:
            say(began, f"features of {r + 1:,} states")
    cols["_raw_weight"] = raw_weight
    cols["_side_weight"] = side_weight
    cols["_junk_types"] = {"numbered_types": len(weights), "weights": sorted(weights.values())}
    return cols


def weight_buckets(raw_weight: np.ndarray, buckets: int) -> np.ndarray:
    """Quantile buckets of the held junk weight (equal counts of distinct values per bucket)."""
    values = np.unique(raw_weight)
    edges = np.unique(np.quantile(values, np.linspace(0, 1, buckets + 1)[1:-1])) if len(values) > buckets else values[:-1]
    return np.searchsorted(edges, raw_weight, side="right").astype(np.int64)


KEYS = {
    # the keys of #312 (replicated, for the comparison): status; + rarity, mods per side, fractured ids
    "status": ["goal", "status"],
    "312-best": ["goal", "status", "rarity", "sides", "fractured"],
    # what #312 left out: the crafted mods (the metamods), the tags of the junk
    "+crafted": ["goal", "status", "rarity", "sides", "fractured", "crafted"],
    "+crafted+tags": ["goal", "status", "rarity", "sides", "fractured", "crafted", "junk_tags"],
    # the junk types: how many different ones, their total pool weight in 4 / 16 buckets, the base kinds, the kinds
    "+crafted+nkinds": ["goal", "status", "rarity", "sides", "fractured", "crafted", "junk_n_kinds"],
    "+crafted+weight4": ["goal", "status", "rarity", "sides", "fractured", "crafted", "w4"],
    "+crafted+weight16": ["goal", "status", "rarity", "sides", "fractured", "crafted", "w16"],
    "+crafted+tags+weight16": ["goal", "status", "rarity", "sides", "fractured", "crafted", "junk_tags", "w16"],
    "+crafted+kinds": ["goal", "status", "rarity", "sides", "fractured", "crafted", "junk_kinds"],
    "+crafted+kinds+contrib": ["goal", "status", "rarity", "sides", "fractured", "crafted", "junk_kinds", "contrib"],
    "+crafted+prefix-kinds": ["goal", "status", "rarity", "sides", "fractured", "crafted", "junk_kinds_prefix"],
    "+crafted+suffix-kinds": ["goal", "status", "rarity", "sides", "fractured", "crafted", "junk_kinds_suffix"],
    # which features of the cheap key matter: each left out in turn
    "crafted-only": ["goal", "crafted"],
    "status+crafted": ["goal", "status", "crafted"],
    "+crafted -rarity": ["goal", "status", "sides", "fractured", "crafted"],
    "+crafted -sides": ["goal", "status", "rarity", "fractured", "crafted"],
    "+crafted -fractured": ["goal", "status", "rarity", "sides", "crafted"],
    "slots": ["goal", "status", "rarity", "fractured", "slots"],
    "identity": ["all"],
}


def key_map(cols: dict[str, np.ndarray], names: list[str]) -> tuple[np.ndarray, int]:
    """The abstract state of every concrete state for the key made of the named features, and the number of abstract states."""
    key = np.zeros(len(cols["goal"]), dtype=np.int64)
    for name in names:
        col = cols[name]
        width = int(col.max()) + 1
        key = np.unique(key * width + col, return_inverse=True)[1].astype(np.int64)
    return key, int(key.max()) + 1


# ---- the optimistic abstraction of a key, vectorised ----------------------------------------------------------------------


def pack_kernels(g) -> dict:
    """The kernels of the walk as flat arrays: pointer, successor, chance (float64)."""
    count = len(g.k_succ)
    sizes = np.fromiter((len(a) for a in g.k_succ), dtype=np.int64, count=count)
    ptr = np.zeros(count + 1, dtype=np.int64)
    np.cumsum(sizes, out=ptr[1:])
    succ = np.concatenate(g.k_succ).astype(np.int32) if count else np.zeros(0, dtype=np.int32)
    prob = np.empty(int(ptr[-1]), dtype=np.float64)
    for k, wt in enumerate(g.k_wt):
        if wt.dtype == object:  # weights beyond 62 bits (the essence rerolls): exact integers, divided as integers (a float would overflow)
            ints = [int(x) for x in wt.tolist()]
            total = sum(ints)
            prob[ptr[k] : ptr[k + 1]] = [x / total for x in ints]
        else:
            w = wt.astype(np.float64)
            prob[ptr[k] : ptr[k + 1]] = w / w.sum()
    return {"ptr": ptr, "sizes": sizes, "succ": succ, "prob": prob, "count": count}


def aggregate_kernels(pk: dict, cmap: np.ndarray, C: int, max_edges: int, chunk_edges: int = 20_000_000):
    """Each kernel seen through `cmap`: (pointer per kernel, abstract successor, chance), successors sorted within a kernel; None when the aggregated edges pass `max_edges`."""
    ptr, sizes = pk["ptr"], pk["sizes"]
    count = pk["count"]
    out_k, out_c, out_p = [], [], []
    k0 = 0
    total = 0
    while k0 < count:
        k1 = int(np.searchsorted(ptr, ptr[k0] + chunk_edges, side="right")) - 1
        k1 = min(max(k1, k0 + 1), count)
        e0, e1 = int(ptr[k0]), int(ptr[k1])
        kid = np.repeat(np.arange(k1 - k0, dtype=np.int64), sizes[k0:k1])
        code = kid * C + cmap[pk["succ"][e0:e1]]
        order = np.argsort(code, kind="stable")
        code = code[order]
        prob = pk["prob"][e0:e1][order]
        cut = np.flatnonzero(np.concatenate(([True], code[1:] != code[:-1])))
        total += len(cut)
        if total > max_edges:
            return None
        out_p.append(np.add.reduceat(prob, cut))
        code = code[cut]
        out_k.append((code // C + k0).astype(np.int32))
        out_c.append((code % C).astype(np.int32))
        k0 = k1
    agg_k = np.concatenate(out_k) if out_k else np.zeros(0, dtype=np.int64)
    sizes_c = np.bincount(agg_k, minlength=count).astype(np.int64)
    ck_ptr = np.zeros(count + 1, dtype=np.int64)
    np.cumsum(sizes_c, out=ck_ptr[1:])
    return ck_ptr, np.concatenate(out_c), np.concatenate(out_p)


def flatten_arrays(n: int, goal: np.ndarray, a_state: np.ndarray, a_cost: np.ndarray, sizes: np.ndarray, dst: np.ndarray, pr: np.ndarray) -> dict:
    """The dict `prune_analysis` works on (actions sorted by state, edges grouped by action), with each action's self-loop eliminated."""
    ptr = np.searchsorted(a_state, np.arange(n + 1)).astype(np.int64)
    edge_ptr = np.concatenate(([0], np.cumsum(sizes))).astype(np.int64)
    act_of_edge = np.repeat(np.arange(len(a_state), dtype=np.int32), sizes)
    is_self = dst == a_state[act_of_edge]
    nonempty = sizes > 0
    stay = np.zeros(len(a_state))
    if len(pr):
        stay[nonempty] = np.add.reduceat(pr * is_self, edge_ptr[:-1][nonempty])
    leaves = 1.0 - stay
    dead = leaves <= 1e-15
    safe = np.where(dead, 1.0, leaves)
    cost_e = np.where(dead, np.inf, a_cost / safe)
    p_e = np.where(is_self | dead[act_of_edge], 0.0, pr / safe[act_of_edge])
    return {
        "n": n, "ptr": ptr, "cost": cost_e, "cost_raw": a_cost, "stay": stay, "state": a_state.astype(np.int32), "edge_ptr": edge_ptr, "sizes": sizes,
        "dst": dst.astype(np.int32), "p": p_e, "act_of_edge": act_of_edge, "goal": goal, "offer": np.zeros(len(a_state), dtype=np.int64),
        "nonempty_state": np.flatnonzero((np.diff(ptr) > 0) & ~goal),
    }


def optimistic_value(g, pk: dict, acts: dict, cmap: np.ndarray, C: int, began: float, max_flat_edges: int, say_solve=lambda _t: None) -> tuple[np.ndarray | None, dict]:
    """V of the optimistic abstraction for `cmap` (value per abstract state), or None when its edges exceed `max_flat_edges`."""
    t0 = time.perf_counter()
    found = aggregate_kernels(pk, cmap, C, max_flat_edges)
    if found is None:
        return None, {"abstract_states": C, "skipped": f"more than {max_flat_edges:,} aggregated edges"}
    ck_ptr, ck_dst, ck_p = found
    ck_sizes = np.diff(ck_ptr)
    count = pk["count"]
    # the actions of the abstract states: the cheapest action of any member per (abstract state, kernel)
    a_abs = cmap[acts["state"]]
    code = a_abs * count + acts["kernel"]
    order = np.argsort(code, kind="stable")
    code_s = code[order]
    cost_s = acts["cost"][order]
    cut = np.flatnonzero(np.concatenate(([True], code_s[1:] != code_s[:-1]))) if len(code_s) else np.zeros(0, dtype=np.int64)
    a_cost = np.minimum.reduceat(cost_s, cut) if len(cut) else np.zeros(0)
    a_state = (code_s[cut] // count).astype(np.int64)
    a_kernel = (code_s[cut] % count).astype(np.int64)
    sizes = ck_sizes[a_kernel]
    # a content merge of equal abstract actions (same abstract successors and chances, dearer one dropped) keeps the model small
    edges = int(sizes.sum())
    info = {"abstract_states": C, "abstract_actions": len(a_state), "abstract_edges": edges, "aggregate_seconds": round(time.perf_counter() - t0, 1)}
    if edges > max_flat_edges:
        info["skipped"] = f"{edges:,} edges over the limit {max_flat_edges:,}"
        return None, info
    idx = P.expand_ranges(ck_ptr[a_kernel], ck_ptr[a_kernel + 1])
    goal = np.zeros(C, dtype=bool)
    goal[cmap[acts["goal_states"]]] = True
    flat = flatten_arrays(C, goal, a_state, a_cost, sizes, ck_dst[idx], ck_p[idx])
    del idx
    t1 = time.perf_counter()
    value, solve_info = P.solve_values(flat, flat["cost"], flat["p"], np.ones(len(flat["cost"]), dtype=bool), int(cmap[0]), say_solve)
    info.update({"solve_seconds": round(time.perf_counter() - t1, 1), "solve": solve_info, "total_seconds": round(time.perf_counter() - t0, 1)})
    return value, info


def action_arrays(g) -> dict:
    n = g.expanded
    ptr = np.array(g.act_ptr[: n + 1], dtype=np.int64)
    return {
        "state": np.repeat(np.arange(n, dtype=np.int64), np.diff(ptr)),
        "cost": np.array(g.act_cost, dtype=np.float64),
        "kernel": np.array(g.act_kernel, dtype=np.int64),
        "goal_states": np.flatnonzero(np.frombuffer(bytes(g.goal[:n]), dtype=np.uint8) == 1),
    }


def extreme_members(cmap: np.ndarray, side_weight: np.ndarray) -> np.ndarray:
    """The members of each abstract state that hold the least or the most junk weight (per side, and in total): ties are all kept.

    ADR-0023 (variants) says the best and the worst backup of an adding action over the members of a block are reached at the
    members that put the junk on the lightest or the heaviest families; this keeps those members only, to see whether the bound of
    the abstract state survives when only they are offered.
    """
    n = len(cmap)
    keep = np.zeros(n, dtype=bool)
    order = np.argsort(cmap, kind="stable")
    cs = cmap[order]
    starts = np.flatnonzero(np.concatenate(([True], cs[1:] != cs[:-1])))
    gid = np.repeat(np.arange(len(starts)), np.diff(np.concatenate((starts, [n]))))
    for vec in (side_weight[:, 0], side_weight[:, 1], side_weight.sum(axis=1)):
        v = vec[order]
        high = np.maximum.reduceat(v, starts)
        low = np.minimum.reduceat(v, starts)
        keep[order[(v == high[gid]) | (v == low[gid])]] = True
    return keep


# ---- what a bound cuts, on the exact quotient ---------------------------------------------------------------------------


def cut_rows(flat: dict, start: int, v_star: np.ndarray, lb: np.ndarray, label: str, sizes_of_class: np.ndarray, restart_cost: float, sweeps=(0, 8)) -> list[dict]:
    """The competitive actions and the classes reachable through them for a lower bound `lb` (per class), with a perfect upper bound and the incumbent f = 1."""
    state = flat["state"]
    non_goal_action = ~flat["goal"][state]
    rows = []
    n = flat["n"]
    for mode in ("perfect", "incumbent"):
        if mode == "perfect":
            ub = v_star.copy()
        else:
            ub = np.full(n, restart_cost + v_star[start])
            ub[start] = v_star[start]
        ub[flat["goal"]] = 0.0
        lb_now = np.where(flat["goal"], 0.0, np.minimum(lb, BIG))
        k = 0
        for target in sweeps:
            while k < target:
                lb_now = np.maximum(lb_now, P.state_min(flat, P.q_values(flat, lb_now)))
                ub = np.minimum(ub, P.state_min(flat, P.q_values(flat, ub)))
                k += 1
            q_low = P.q_values(flat, lb_now)
            best_up = P.state_min(flat, P.q_values(flat, ub))
            competitive = (q_low <= best_up[state] * (1 + 1e-12) + 1e-12) & non_goal_action
            seen = P.reach(flat, start, competitive)
            rows.append({
                "key": label, "upper_bound": mode, "sweeps": k, "lb_start_over_exact": float(lb_now[start] / v_star[start]),
                "competitive_actions": int(competitive.sum()), "of_actions": int(non_goal_action.sum()),
                "classes_reachable": int(seen.sum()), "of_classes": n, "raw_states_in_reached_classes": int(sizes_of_class[seen].sum()),
                "of_raw_states": int(sizes_of_class.sum()),
            })
    return rows


# ---- main ---------------------------------------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--offers", default="twins")
    parser.add_argument("--strand-stripped", action="store_true")
    parser.add_argument("--merge", default="auto", choices=("auto", "yes", "no"), help="exact classes before the exact solve (auto: when the walk holds over 50 M edges)")
    parser.add_argument("--keys", default="all")
    parser.add_argument("--cut-keys", default="", help="keys whose cuts are measured: names, or all")
    parser.add_argument("--extremes", default="+crafted,+crafted+tags", help="keys for which the bound is also built from the extreme members only")
    parser.add_argument("--cut-top", type=int, default=0, help="also the N keys with the best ratio")
    parser.add_argument("--seconds", type=float, default=3300)
    parser.add_argument("--max-rss-mb", type=float, default=13_000)
    parser.add_argument("--max-flat-edges", type=int, default=80_000_000)
    parser.add_argument("--max-states", type=int, default=5_000_000)
    parser.add_argument("--out")
    args = parser.parse_args()
    began = time.perf_counter()
    path = Path(args.target)
    data, target, goal, abstraction, start, priced, info = E.build_model(path, args.offers, True, args.strand_stripped)
    say(began, f"model built: {info}")
    g, reason, checks = E.walk(abstraction, start, priced, began, args.seconds, args.max_rss_mb, args.max_states, 0)
    say(began, f"walk {reason}: {len(g.states):,} states, {g.expanded:,} expanded, {len(g.k_succ):,} kernels, {g.edges:,} edges")
    result: dict = {"target": path.name, "walk": reason, "states": len(g.states), "kernels": len(g.k_succ), "edges": g.edges, "walk_seconds": round(time.perf_counter() - began, 1), "bounds": {}, "cuts": []}
    if reason != "finished":
        print(json.dumps(result, indent=1))
        sys.exit(1)
    restart_cost = next((p.cost for p in priced if p.label == E.RESTART), 0.0)
    n = g.expanded
    # exact classes
    merge = args.merge == "yes" or (args.merge == "auto" and g.edges > 50_000_000)
    if merge:
        blk, history = E.refine(g, priced, began, label_mode=False)
        say(began, f"exact classes: {len(np.unique(blk[:n])):,} (history {history})")
        cls = np.unique(blk[:n], return_inverse=True)[1].astype(np.int64)
        q, start_class = L.quotient(g, blk)
        qd = {"n": q.expanded, "goal": bytes(q.goal), "act_ptr": q.act_ptr, "act_offer": q.act_offer, "act_cost": q.act_cost, "act_kernel": q.act_kernel, "k_succ": q.k_succ, "k_wt": q.k_wt}
        class_sizes = np.bincount(cls)
        del q
    else:
        cls = np.arange(n, dtype=np.int64)
        start_class = 0
        qd = {"n": n, "goal": bytes(g.goal[:n]), "act_ptr": g.act_ptr[: n + 1], "act_offer": g.act_offer, "act_cost": g.act_cost, "act_kernel": g.act_kernel, "k_succ": g.k_succ, "k_wt": g.k_wt}
        class_sizes = np.ones(n, dtype=np.int64)
    result["classes"] = int(cls.max()) + 1
    gc.collect()
    say(began, f"classes {result['classes']:,}; quotient ready")
    # the features and the abstractions need the walked graph; the exact solve needs the quotient: bounds first, then free the walk
    cols = extract(g, abstraction, began)
    cols["w4"] = weight_buckets(cols["_raw_weight"], 4)
    cols["w16"] = weight_buckets(cols["_raw_weight"], 16)
    say(began, "features done; kernels packed next")
    pk = pack_kernels(g)
    acts = action_arrays(g)
    names = list(KEYS) if args.keys == "all" else [k for k in args.keys.split(",") if k]
    extremes_keys = {k for k in args.extremes.split(",") if k}
    result["junk_types"] = cols["_junk_types"]
    class_lb: dict[str, np.ndarray] = {}
    for name in names:
        t0 = time.perf_counter()
        cmap, C = key_map(cols, KEYS[name])
        value, binfo = optimistic_value(g, pk, acts, cmap, C, began, args.max_flat_edges)
        row = {"features": KEYS[name], **binfo}
        if value is not None:
            row["start_value"] = float(value[cmap[0]])
            lb = np.zeros(result["classes"])
            np.maximum.at(lb, cls, np.minimum(value[cmap], BIG))
            class_lb[name] = lb
        if value is not None and name in extremes_keys:
            keep = extreme_members(cmap, cols["_side_weight"])
            mask = keep[acts["state"]]
            sub = {"state": acts["state"][mask], "cost": acts["cost"][mask], "kernel": acts["kernel"][mask], "goal_states": acts["goal_states"]}
            value2, info2 = optimistic_value(g, pk, sub, cmap, C, began, args.max_flat_edges)
            if value2 is not None:
                row["extremes"] = {"members_kept": int(keep.sum()), "of_members": int(len(keep)), "actions_kept": int(mask.sum()), "of_actions": int(len(mask)),
                                   "start_value": float(value2[cmap[0]]), "abstract_actions": info2["abstract_actions"], "abstract_edges": info2["abstract_edges"]}
        result["bounds"][name] = row
        say(began, f"key {name}: {C:,} abstract states; {json.dumps({k: v for k, v in row.items() if k not in ('features', 'solve')})} ({time.perf_counter() - t0:.0f}s)")
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{path.stem}.partial.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    del pk, acts, cols, g
    gc.collect()
    flat = P.flatten(qd)
    del qd
    gc.collect()
    say(began, f"quotient flattened: {flat['n']:,} classes, {len(flat['cost']):,} actions, {len(flat['dst']):,} edges")
    v_star, vinfo = P.solve_values(flat, flat["cost"], flat["p"], np.ones(len(flat["cost"]), dtype=bool), start_class, lambda t: say(began, t))
    exact = float(v_star[start_class])
    result["exact"] = {"start_value": exact, **vinfo}
    say(began, f"exact V*(start) = {exact:.6f} {vinfo}")
    non_goal = ~flat["goal"]
    optimal = (P.q_values(flat, v_star) <= v_star[flat["state"]] * (1 + 1e-9) + 1e-12) & non_goal[flat["state"]]
    floor = P.reach(flat, start_class, optimal)
    result["exact"]["optimal_policy_classes"] = int(floor.sum())
    result["exact"]["optimal_policy_raw_states_at_most"] = int(class_sizes[floor].sum())
    for name, row in result["bounds"].items():
        lb = class_lb.get(name)
        if lb is None:
            continue
        row["ratio"] = row["start_value"] / exact
        if "extremes" in row:
            row["extremes"]["ratio"] = row["extremes"]["start_value"] / exact
        finite = np.isfinite(v_star) & (v_star < BIG / 10) & non_goal
        row["violations"] = int(((lb > v_star * (1 + 1e-7) + 1e-9) & finite).sum())
        row["worst_excess"] = float(np.max(np.where(finite, lb / np.maximum(v_star, 1e-300) - 1, -1)))
        inside = floor & finite
        ratios = lb[inside] / np.maximum(v_star[inside], 1e-300)
        row["ratio_in_optimal_policy"] = {"median": float(np.median(ratios)), "p10": float(np.percentile(ratios, 10)), "mean": float(ratios.mean()), "classes": int(inside.sum())}
        say(began, f"ratio {name}: {row['ratio']:.4f}, violations {row['violations']}, in the optimal policy {row['ratio_in_optimal_policy']}")
    if args.cut_keys == "all":
        cut_names = list(class_lb)
    else:
        cut_names = [k for k in args.cut_keys.split(",") if k and k in class_lb]
        best = sorted((name for name in class_lb if name not in cut_names and name != "identity"), key=lambda name: -result["bounds"][name]["ratio"])
        cut_names += best[: args.cut_top]
    result["cuts"] += cut_rows(flat, start_class, v_star, v_star.copy(), "perfect (lb = V*)", class_sizes, restart_cost, sweeps=(0,))
    for name in cut_names:
        result["cuts"] += cut_rows(flat, start_class, v_star, class_lb[name], name, class_sizes, restart_cost)
        say(began, f"cuts {name}: {result['cuts'][-1]}")
        if args.out:
            (Path(args.out) / f"{path.stem}.partial.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    if args.out:
        (Path(args.out) / f"{path.stem}.partial.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    result["peak_rss_mb"] = round(E.rss_mb())
    result["total_seconds"] = round(time.perf_counter() - began, 1)
    text = json.dumps(result, indent=1)
    print(text, flush=True)
    if args.out:
        (Path(args.out) / f"{path.stem}.bounds.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
