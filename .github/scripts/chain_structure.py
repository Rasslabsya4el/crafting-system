"""The cycle structure of a route's policy chain: where its strongly connected components are, and how few states cut them small (ticket #584/#572 measurement).

    python .github/scripts/chain_structure.py --route r04|r14 [--out DIR]

Plans the route as the page does, makes the item-state chain of the planner's policy (`chain_of_plan`), keeps the states that can finish, and prints, for
the chain as it is and with the edges INTO the k most visited states cut (k = 1, 4, 16, ...), the strongly connected components: how many, the biggest,
and the sum of their cubes (the cost of a dense inverse of each). The result is `<route>.structure.json`. Never run on a PC: the plan walks for
minutes. Run by `.github/scripts/heavy_dispatch.py`, see `docs/ci.md`.
"""

import argparse
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
from packed_routes import inputs, peak_mb, watch_memory

from crafting_system.cli import _packed, make_plan
from crafting_system.cli._route_chain import chain_of_plan
from crafting_system.cli._route_flow import _can_finish, _solved


def components(m: int, s: np.ndarray, d: np.ndarray, nodes: np.ndarray):
    """`(label, sizes)`: the strongly connected components of the graph of the edges `s -> d` among the `nodes` (a boolean mask), Tarjan on numpy slices."""
    order = np.argsort(s, kind="stable")
    d = d[order]
    ptr = np.searchsorted(s[order], np.arange(m + 1))
    index = np.full(m, -1, dtype=np.int64)
    low = np.zeros(m, dtype=np.int64)
    on = np.zeros(m, dtype=bool)
    label = np.full(m, -1, dtype=np.int64)
    sizes: list[int] = []
    counter = 0
    stack: list[int] = []
    for root in np.flatnonzero(nodes).tolist():
        if index[root] >= 0:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on[root] = True
        calls = [[root, iter(())]]
        nb = d[ptr[root] : ptr[root + 1]]
        if len(nb):
            seen = index[nb]
            hit = on[nb]
            if hit.any():
                low[root] = min(low[root], int(seen[hit].min()))
            calls[-1][1] = iter(nb[seen < 0].tolist())
        while calls:
            v, children = calls[-1]
            advanced = False
            for w in children:
                if index[w] >= 0:
                    continue
                index[w] = low[w] = counter
                counter += 1
                stack.append(w)
                on[w] = True
                nbw = d[ptr[w] : ptr[w + 1]]
                it: object = iter(())
                if len(nbw):
                    seen = index[nbw]
                    hit = on[nbw]
                    if hit.any():
                        low[w] = min(low[w], int(seen[hit].min()))
                    it = iter(nbw[seen < 0].tolist())
                calls.append([w, it])
                advanced = True
                break
            if advanced:
                continue
            calls.pop()
            if calls and low[v] < low[calls[-1][0]]:
                low[calls[-1][0]] = low[v]
            if low[v] == index[v]:
                size = 0
                while True:
                    w = stack.pop()
                    on[w] = False
                    label[w] = len(sizes)
                    size += 1
                    if w == v:
                        break
                sizes.append(size)
    return label, np.array(sizes, dtype=np.int64)


def shared_rows(chain, m: int, finishing: np.ndarray, say) -> dict:
    """How many distinct rows the states of the chain have, and the components of the chain without the edges of the rows that several states share."""
    ptr, dst, prob = chain.ptr, chain.dst, chain.prob
    seen: dict[bytes, list[int]] = {}
    for i in np.flatnonzero(finishing).tolist():
        a, b = int(ptr[i]), int(ptr[i + 1])
        if b > a:
            seen.setdefault(dst[a:b].tobytes() + prob[a:b].tobytes(), []).append(i)
    groups = [g for g in seen.values() if len(g) > 1]
    in_shared = np.zeros(m, dtype=bool)
    for g in groups:
        in_shared[g] = True
    sizes = sorted((len(g) for g in groups), reverse=True)
    say(f"rows: {len(seen):,} distinct among {int(finishing.sum()):,} states; {len(groups):,} rows shared by {int(in_shared.sum()):,} states, the biggest groups {sizes[:8]}")
    src = np.repeat(np.arange(m), np.diff(ptr))
    inside = finishing[src] & (dst < m)
    inside[inside] = finishing[dst[inside]]
    keep = inside & ~in_shared[src] & (src != dst)
    _, comp = components(m, src[keep], dst[keep], finishing)
    big = np.sort(comp)[::-1]
    row = {
        "distinct_rows": len(seen), "shared_rows": len(groups), "states_in_shared_rows": int(in_shared.sum()), "biggest_groups": sizes[:8],
        "unshared_components": len(comp), "unshared_nontrivial": int((comp > 1).sum()), "unshared_biggest": [int(x) for x in big[:8]],
        "unshared_sum_cubes": float((comp.astype(float) ** 3).sum()),
    }
    say(f"without the shared rows' edges: {row}")
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--out")
    arguments = parser.parse_args()
    threading.Thread(target=watch_memory, daemon=True).start()
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {peak_mb()} MB] {line}", flush=True)

    _packed.PROGRESS = say
    data, target, prices, start_price = inputs(arguments.route)
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver="auto")
    say(f"planned: {len(plan.policy):,} policy states")
    chain = chain_of_plan(plan)
    m = chain.m
    src = np.repeat(np.arange(m), np.diff(chain.ptr))
    dst = chain.dst
    finishing = _can_finish(m, src, dst, dst >= m, dst < m)
    say(f"chain: {m:,} states, {len(dst):,} edges, {int(finishing.sum()):,} can finish")
    done = _solved(chain)
    visits, solved = done.visits, done.solved
    say(f"visits solved: {solved}; sum of visits x cost {float((visits * chain.cost).sum()):.4f}, plan mean {plan.mean_remaining:.4f}")
    inside = finishing[src] & (dst < m) & finishing[np.minimum(dst, m - 1)]
    s, d = src[inside], dst[inside]
    say(f"edges among the finishing states: {len(s):,}; self loops {int((s == d).sum()):,}; into the start {int((d == 0).sum()):,}")
    order = np.argsort(-visits)
    result = {"route": arguments.route, "states": m, "edges": len(dst), "finishing": int(finishing.sum()), "cuts": []}
    for k in (0, 1, 4, 16, 64, 256, 1024):
        cut = np.zeros(m, dtype=bool)
        cut[0] = True
        cut[order[:k]] = True
        keep = ~cut[d] & (s != d)
        label, sizes = components(m, s[keep], d[keep], finishing)
        big = np.sort(sizes)[::-1]
        row = {
            "cut_most_visited": k,
            "cut_states": int(cut.sum()),
            "components": len(sizes),
            "nontrivial": int((sizes > 1).sum()),
            "biggest": [int(x) for x in big[:8]],
            "sum_cubes": float((sizes.astype(float) ** 3).sum()),
            "sum_squares": float((sizes.astype(float) ** 2).sum()),
        }
        say(f"cut the start and the {k} most visited: {row}")
        result["cuts"].append(row)
    result["shared"] = shared_rows(chain, m, finishing, say)
    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{arguments.route}.structure.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
