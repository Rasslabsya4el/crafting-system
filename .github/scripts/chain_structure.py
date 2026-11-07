"""The cycle structure of a route's policy chain: where its strongly connected components are, and which rows cut them small (tickets #572, #490).

    python .github/scripts/chain_structure.py --route r04|r14 [--out DIR]

Plans the route as the page does, makes the item-state chain of the planner's policy (`chain_of_plan`), keeps the states that can finish, and prints
the components of the chain (how many, the biggest), the rows that several states share (how many, how many states take them) and the components
that remain when those rows are cut: the numbers `solver/_packed_chain.py` works from (the cost of the exact visit chances is `q` solves, `q` the
shared rows). The result is `<route>.structure.json`. Never run on a PC: the plan walks for minutes. Run by `.github/scripts/heavy_dispatch.py`,
see `docs/ci.md`.
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
from crafting_system.cli._route_flow import _can_finish, _entries, _solved
from crafting_system.solver._packed_chain import _row_groups, _without_rows, components


def csr_among(chain, finishing: np.ndarray):
    """`(n, ptr, col, weight)` of the chain on the states that can finish, no self-loops: the matrix `P` of `solver/_packed_chain.py` up to the scaling."""
    m = chain.m
    src = np.repeat(np.arange(m), np.diff(chain.ptr))
    inside = finishing[src] & (chain.dst < m)
    inside[inside] = finishing[chain.dst[inside]]
    inside &= src != chain.dst
    position = np.cumsum(finishing) - 1
    row, col = position[src[inside]], position[chain.dst[inside]]
    n = int(finishing.sum())
    return n, np.searchsorted(row, np.arange(n + 1)), col, chain.prob[inside]


def describe(n: int, ptr: np.ndarray, col: np.ndarray, weight: np.ndarray) -> dict:
    label, count = components(n, ptr, col)
    sizes = np.bincount(label, minlength=count)
    groups = _row_groups(ptr, col, weight, np.arange(n))
    shared = [g for g in groups if len(g) > 1]
    cut = np.zeros(n, dtype=bool)
    for g in shared:
        cut[g] = True
    after_ptr, after_col, _ = _without_rows(n, ptr, col, weight, cut)
    after, after_count = components(n, after_ptr, after_col)
    after_sizes = np.bincount(after, minlength=after_count)
    return {
        "states": n,
        "edges": len(col),
        "components": count,
        "nontrivial": int((sizes > 1).sum()),
        "biggest": [int(x) for x in np.sort(sizes)[::-1][:8]],
        "distinct_rows": len(groups),
        "shared_rows": len(shared),
        "states_in_shared_rows": int(cut.sum()),
        "biggest_shared_groups": sorted((len(g) for g in shared), reverse=True)[:8],
        "components_without_the_shared_rows": after_count,
        "biggest_without_the_shared_rows": [int(x) for x in np.sort(after_sizes)[::-1][:8]],
    }


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
    finishing = _can_finish(m, src, chain.dst, chain.dst >= m, chain.dst < m)
    say(f"chain: {m:,} states, {len(chain.dst):,} edges, {int(finishing.sum()):,} can finish")
    done = _solved(chain)
    say(f"visits solved: {done.solved}, entry chances unsettled: {_entries(chain)[1]}; sum of visits x cost {float((done.visits * chain.cost).sum()):.4f}, plan mean {plan.mean_remaining:.4f}")
    result = describe(*csr_among(chain, finishing))
    say(f"structure: {result}")
    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{arguments.route}.structure.json").write_text(json.dumps({"route": arguments.route, **result}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
