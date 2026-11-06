"""The crafted-pattern lower bound built without the walk (ticket #497): its start value, time, memory and kernels, and (--check) its soundness on the walked graph.

    python research/497/pattern_bound.py TARGET.yaml --out DIR [--strand-stripped] [--tags auto,yes,no] [--check] [--seconds S]

Without `--check` it builds the optimistic model of the key from the `Abstraction` and the priced offers (`cli/_pattern_bound.py`, no walk), solves
it, and writes the number of abstract states, the kernels it evaluated, the start value, the seconds and the peak memory. With `--check` it then
walks the concrete graph (the research/312 walker), solves it exactly, and reports

* `violations`: walked states whose key is in the model but whose bound is above their exact value (must be 0);
* `keys_missing`: walked states whose key is not a key of the model (must be 0: every reachable state is a member the model reached);
* the start value over the exact one, and over the member-union bound of research #376 for the same key (`+crafted` or `+crafted+tags`),
  built from the same walk by `research/376/junk_bound.py`;
* the kernels the member-union experiment needed for the extreme members and for all members, against the kernels this build evaluated.

Never run on a PC for a real route: the walk is hours of CPU on R14. Run by `.github/scripts/heavy_dispatch.py`; a quick local run on R13 is fine.
"""

import argparse
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for extra in (ROOT / "research" / "312", ROOT / "research" / "376"):
    if str(extra) not in sys.path:
        sys.path.append(str(extra))

import exact_classes as E  # noqa: E402
import junk_bound as J  # noqa: E402
import later_stages as L  # noqa: E402
import prune_analysis as P  # noqa: E402
from crafting_system.abstraction._pattern import Pattern  # noqa: E402
from crafting_system.cli._pattern_bound import pattern_lower_bound  # noqa: E402


def say(began: float, text: str) -> None:
    E.say(began, text)


def stats_row(bound) -> dict:
    s = bound.stats
    return {
        "abstract_states": s.keys, "goal_keys": s.goal_keys, "members_offered": s.members, "member_action_pairs": s.pairs, "kernels_evaluated": s.kernels,
        "abstract_actions": s.abstract_actions, "abstract_edges": s.abstract_edges, "refused_pairs": s.refused_pairs, "universe_growth": s.universe_growth,
        "extremes_fallbacks": s.fallbacks, "modes": {f"{mode}/{name}": count for (mode, name), count in sorted(s.modes.items())},
        "build_seconds": round(bound.build_seconds, 1), "solve_seconds": round(bound.solve_seconds, 1), "start_value": bound.start_value,
        "lower": bound.lower, "error_bound": bound.error_bound,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--strand-stripped", action="store_true")
    parser.add_argument("--tags", default="auto", help="the keys to build, comma separated: auto (tags when the metamods are modelled), yes, no")
    parser.add_argument("--check", action="store_true", help="walk the concrete graph and check the bound against its exact values")
    parser.add_argument("--seconds", type=float, default=3300)
    parser.add_argument("--max-rss-mb", type=float, default=13_000)
    parser.add_argument("--max-states", type=int, default=5_000_000)
    parser.add_argument("--merge", default="auto", choices=("auto", "yes", "no"))
    parser.add_argument("--max-keys", type=int)
    parser.add_argument("--out")
    args = parser.parse_args()
    began = time.perf_counter()
    path = Path(args.target)
    settings = [{"auto": None, "yes": True, "no": False}[name] for name in args.tags.split(",")]
    data, target, goal, abstraction, start, priced, info = E.build_model(path, "twins", True, args.strand_stripped)
    say(began, f"model built: {info}")
    result: dict = {"target": path.name, "offers": len(priced), "bounds": {}}
    bounds = []
    for name, tags in zip(args.tags.split(","), settings):
        bound = pattern_lower_bound(abstraction, start, priced, tags=tags, progress=lambda t: say(began, t), max_keys=args.max_keys)
        bounds.append((name, tags, bound))
        row = stats_row(bound)
        row["peak_rss_mb_after_bound"] = round(E.rss_mb())
        result["bounds"][name] = row
        say(began, f"bound {name}: {json.dumps(row)}")
    out = Path(args.out) if args.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{path.stem}.pattern.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    if not args.check:
        result["peak_rss_mb"] = round(E.rss_mb())
        print(json.dumps(result, indent=1), flush=True)
        return
    g, reason, _checks = E.walk(abstraction, start, priced, began, args.seconds, args.max_rss_mb, args.max_states, 0)
    say(began, f"walk {reason}: {len(g.states):,} states, {g.expanded:,} expanded, {len(g.k_succ):,} kernels, {g.edges:,} edges")
    result["walk"] = {"reason": reason, "states": len(g.states), "expanded": g.expanded, "kernels": len(g.k_succ), "edges": g.edges}
    if reason != "finished":
        print(json.dumps(result, indent=1))
        sys.exit(1)
    n = g.expanded
    merge = args.merge == "yes" or (args.merge == "auto" and g.edges > 50_000_000)
    if merge:
        blk, history = E.refine(g, priced, began, label_mode=False)
        cls = np.unique(blk[:n], return_inverse=True)[1].astype(np.int64)
        q, start_class = L.quotient(g, blk)
        qd = {"n": q.expanded, "goal": bytes(q.goal), "act_ptr": q.act_ptr, "act_offer": q.act_offer, "act_cost": q.act_cost, "act_kernel": q.act_kernel, "k_succ": q.k_succ, "k_wt": q.k_wt}
        del q
    else:
        cls = np.arange(n, dtype=np.int64)
        start_class = 0
        qd = {"n": n, "goal": bytes(g.goal[:n]), "act_ptr": g.act_ptr[: n + 1], "act_offer": g.act_offer, "act_cost": g.act_cost, "act_kernel": g.act_kernel, "k_succ": g.k_succ, "k_wt": g.k_wt}
    gc.collect()
    # the member-union bound of #376 on this walk (needs the walked graph), before the walk is freed
    cols = J.extract(g, abstraction, began)
    pk = J.pack_kernels(g)
    acts = J.action_arrays(g)
    per_variant = {}
    for name, tags, bound in bounds:
        pattern = Pattern(abstraction, tags)
        union_name = "+crafted+tags" if pattern.tags else "+crafted"
        cmap, C = J.key_map(cols, J.KEYS[union_name])
        union_value, union_info = J.optimistic_value(g, pk, acts, cmap, C, began, 80_000_000)
        keep = J.extreme_members(cmap, cols["_side_weight"])
        mask = keep[acts["state"]]
        union = {
            "key": union_name, "abstract_states": C, "start_value": float(union_value[cmap[0]]) if union_value is not None else None,
            "kernels_all_members": int(len(np.unique(acts["kernel"]))), "kernels_extreme_members": int(len(np.unique(acts["kernel"][mask]))), "of_kernels": int(pk["count"]),
            "members_extreme": int(keep.sum()), "of_members": int(len(keep)),
        }
        say(began, f"member union {name}: {json.dumps(union)}")
        # the keys of the walked states, against the model
        keys_missing = 0
        state_value = np.full(n, np.nan)
        missing_keys = set()
        for r in range(n):
            found = bound.model.index.get(pattern.key(g.states[r]))
            if found is None:
                keys_missing += 1
                missing_keys.add(pattern.key(g.states[r]))
            else:
                state_value[r] = bound.value[found]
        say(began, f"keys looked up; missing {keys_missing} states, {len(missing_keys)} keys")
        per_variant[name] = (union, keys_missing, len(missing_keys), state_value)
    del pk, acts, cols, g
    gc.collect()
    flat = P.flatten(qd)
    del qd
    gc.collect()
    v_star, vinfo = P.solve_values(flat, flat["cost"], flat["p"], np.ones(len(flat["cost"]), dtype=bool), start_class, lambda t: say(began, t))
    exact = float(v_star[start_class])
    per_state = v_star[cls]
    result["exact"] = {"start_value": exact, **vinfo}
    result["member_union"] = {}
    result["check"] = {}
    for name, tags, bound in bounds:
        union, keys_missing, keys_missing_distinct, state_value = per_variant[name]
        finite = np.isfinite(per_state) & (per_state < J.BIG / 10) & ~np.isnan(state_value)
        over = (state_value > per_state * (1 + 1e-7) + 1e-9) & finite
        result["member_union"][name] = union
        result["check"][name] = {
            "walked_states": n, "keys_missing_states": keys_missing, "keys_missing": keys_missing_distinct, "compared": int(finite.sum()), "violations": int(over.sum()),
            "worst_excess": float(np.max(np.where(finite, state_value / np.maximum(per_state, 1e-300) - 1, -1))),
            "start_over_exact": bound.start_value / exact, "lower_over_exact": bound.lower / exact,
            "member_union_over_exact": (union["start_value"] / exact) if union["start_value"] is not None else None,
            "start_over_member_union": (bound.start_value / union["start_value"]) if union["start_value"] else None,
            "kernels_evaluated": bound.stats.kernels, "keys": bound.stats.keys,
        }
        say(began, f"check {name}: {json.dumps(result['check'][name])}")
    result["peak_rss_mb"] = round(E.rss_mb())
    result["total_seconds"] = round(time.perf_counter() - began, 1)
    text = json.dumps(result, indent=1)
    print(text, flush=True)
    if out:
        (out / f"{path.stem}.pattern.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
