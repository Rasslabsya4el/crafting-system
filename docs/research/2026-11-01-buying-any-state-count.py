"""How many buy offers would "the planner chooses what to buy" need on R05, R08 and R13 (ticket #337).

Run by the `Run a command` workflow through `.github/scripts/heavy_dispatch.py`, never on a PC:

    python docs/research/2026-11-01-buying-any-state-count.py --routes r05,r08,r13 --part 1/3 --out $OUT_DIR

Each route is solved as `make_plan` solves it today (exact, fixture prices, the restart offer in), then every state of
the solved graph is projected to the *buy key* a trade query could name:

    key = (rarity, influences, fractured mods, status of each target leaf)          ("junk dropped")
    key+ = key plus the number of other prefixes and suffixes                       ("side counts pinned", the
                                                                                       pseudo stats # Prefix / # Suffix Modifiers)

The script writes, per route, the counts of states and keys and, for a made-up price model, how many keys a lazy
search with a monotone price bound would have to query. The model is the *only* made-up part (no price of a rare
item in a state is known); it is swept, not asserted. Nothing here calls the network.

Price model: price(key) = P0 * rho ** (m(key) - m(start key)), where m counts the constraints a query puts on the
listing (a status BELOW counts 1, PASSING 2, a fractured mod 1, an influence 1) and P0 is the start item's price.
Lazy rule: a key is queried when  LB(key) + LV(key) < C,  where C = P0 + V(start) is the cost of the plan without any
new buy, LB(key) is the largest known price of a query that key dominates (a listing that matches more filters costs
at least as much as one that matches fewer), and LV(key) is a lower bound on the cost of finishing from the key:
"zero" (no bound on the crafting side), or "oracle" (the solved V of the cheapest state of the key, the best any bound
could do). The truth of an ADR-0031-style bound lies between the two.
"""

import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path

from crafting_system.cli import make_plan
from crafting_system.data import load_game_data
from crafting_system.items import Side
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
ROUTES = {"r05": "r05-strength-ring", "r08": "r08-energy-shield-boots", "r13": "r13-life-resist-belt"}
RHOS = (2.0, 4.0, 8.0, 16.0)
MAX_GENERAL_KEYS = 6000  # the dominance pass is quadratic


def key_of(state, with_counts: bool):
    flags = state.flags
    key = (
        str(flags.rarity.value),
        tuple(sorted(str(i.value) for i in flags.influences)),
        tuple(sorted(f.mod_id for f in state.fractured)),
        tuple(int(s) for s in state.status),
    )
    if with_counts:
        key += (state.count(Side.PREFIX), state.count(Side.SUFFIX))
    return key


def constraints(key) -> int:
    return sum(key[3]) + len(key[2]) + len(key[1])


def dominates(big, small) -> bool:
    """A listing that matches `big` also matches `small` (so price(big) >= price(small))."""
    if big[0] != small[0]:
        return False
    if not set(small[1]) <= set(big[1]):
        return False
    remaining = list(big[2])
    for mod in small[2]:
        if mod not in remaining:
            return False
        remaining.remove(mod)
    return all(a >= b for a, b in zip(big[3], small[3]))


def lazy_queries(keys, vmin, price, ceiling, bound: str):
    """(queried keys, keys whose price + best continuation beats `ceiling`) under the monotone-bound lazy rule."""
    order = sorted(keys, key=lambda k: (constraints(k), k))
    queried: dict = {}
    lower: dict = {}
    for k in order:
        lb = 0.0
        for j in lower:
            if dominates(k, j) and j != k:
                lb = max(lb, price[j] if j in queried else lower[j])
        lower[k] = lb
        continuation = vmin[k] if bound == "oracle" else 0.0
        if lb + continuation < ceiling:
            queried[k] = True
    useful = [k for k in queried if price[k] + vmin[k] < ceiling]
    return len(queried), len(useful)


def _pool_groups(data, target) -> list:
    """Item levels 70..100 grouped by the spawnable pool of the target's base (equal pools are one plan)."""
    from crafting_system.actions import build_pool
    from crafting_system.items import Item, Rarity

    seen: dict = {}
    for ilvl in range(70, 101):
        item = Item.build(data, base_id=target.base_id, item_level=ilvl, rarity=Rarity.RARE)
        ids = frozenset(e.mod.id for fam in build_pool(data, item) for e in fam.mods)
        seen.setdefault(ids, []).append(ilvl)
    return [[group[0], group[-1], len(ids)] for ids, group in seen.items()]


def measure(route: str, data, prices) -> dict:
    stem = ROUTES[route]
    target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
    began = time.perf_counter()
    plan = make_plan(data, target, prices)
    seconds = time.perf_counter() - began
    values = plan.solution.values
    start = plan.start
    p0 = plan.start_price.chaos
    v0 = values[start]
    ceiling = p0 + v0
    is_goal = plan.abstraction.is_goal
    finite = {s: v for s, v in values.items() if v != float("inf")}
    pools = _pool_groups(data, target)
    out = {
        "route": route,
        "ilvl_pool_groups": pools,
        "plan_seconds": round(seconds, 1),
        "start_price": p0,
        "v_start": v0,
        "cost_without_new_buy": ceiling,
        "states": len(values),
        "states_finite": len(finite),
        "goal_states": sum(1 for s in finite if is_goal(s)),
        "offers": len(plan.offers),
    }
    for name, with_counts in (("key", False), ("key_counts", True)):
        spread = defaultdict(list)
        for s, v in finite.items():
            spread[key_of(s, with_counts)].append(v)
        vmin = {k: min(vs) for k, vs in spread.items()}
        vmax = {k: max(vs) for k, vs in spread.items()}
        ratios = sorted(vmax[k] / vmin[k] for k in spread if vmin[k] > 0)
        out[f"{name}s"] = len(spread)
        out[f"{name}s_multi_state"] = sum(1 for vs in spread.values() if len(vs) > 1)
        out[f"{name}_max_states"] = max(len(vs) for vs in spread.values())
        out[f"{name}_value_spread_median"] = ratios[len(ratios) // 2] if ratios else None
        out[f"{name}_value_spread_max"] = ratios[-1] if ratios else None
        # constraint count of each key, and how many keys could be cheaper to buy than to craft from the start at all
        out[f"{name}_by_constraints"] = {str(m): sum(1 for k in spread if constraints(k) == m) for m in sorted({constraints(k) for k in spread})}
        out[f"{name}_with_cost_below_plan"] = sum(1 for k in spread if vmin[k] < ceiling)
        # the value of finishing from a state that already carries 1 or 2 constraints: what a one- or two-mod item would save
        out[f"{name}_small_keys"] = sorted(
            (
                {"key": [list(map(str, part)) if isinstance(part, tuple) else part for part in k], "constraints": constraints(k),
                 "states": len(spread[k]), "v_min": vmin[k], "v_max": vmax[k]}
                for k in spread
                if constraints(k) <= 2
            ),
            key=lambda row: (row["constraints"], row["v_min"]),
        )[:60]
        if len(spread) > MAX_GENERAL_KEYS:
            out[f"{name}_lazy"] = "skipped: too many keys for the quadratic dominance pass"
            continue
        start_key = key_of(start, with_counts)
        m0 = constraints(start_key)
        lazy = {}
        for rho in RHOS:
            price = {k: p0 * rho ** (constraints(k) - m0) for k in spread}
            best = min((price[k] + vmin[k] for k in spread), default=ceiling)
            row = {"best_total_with_buys": min(best, ceiling)}
            for bound in ("zero", "oracle"):
                queried, useful = lazy_queries(list(spread), vmin, price, ceiling, bound)
                row[f"queried_{bound}"] = queried
                row[f"useful_{bound}"] = useful
            lazy[str(rho)] = row
        out[f"{name}_lazy"] = lazy
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", default="r05,r08,r13")
    parser.add_argument("--part", default="1/1", help="I/N: the I-th of N slices of the route list")
    parser.add_argument("--out", default=os.environ.get("OUT_DIR", "."))
    args = parser.parse_args()
    index, count = (int(x) for x in args.part.split("/"))
    routes = [r for i, r in enumerate(args.routes.split(",")) if i % count == index - 1]
    data = load_game_data()
    prices = load_price_file(PRICES)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for route in routes:
        result = measure(route, data, prices)
        (out / f"{route}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
