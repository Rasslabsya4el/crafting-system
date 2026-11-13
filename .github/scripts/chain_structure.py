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

from crafting_system.cli import make_plan

from crafting_system.planner import _packed
from crafting_system.cli._route_chain import chain_of_plan
from crafting_system.cli._route_flow import _can_finish, _entries, _entry_chance, _solved, _system, reach_of
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
    after_ptr, after_col, _ = _without_rows(ptr, col, weight, cut)
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
    parser.add_argument("--check", type=int, default=0, help="check the visit chance of the K most visited states against one absorbing solve each")
    parser.add_argument("--dump", action="store_true", help="also write the arrays of the chain to <out>/<route>.chain.npz (only for a chain of a few million edges)")
    arguments = parser.parse_args()
    threading.Thread(target=watch_memory, daemon=True).start()
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {peak_mb()} MB] {line}", flush=True)

    _packed.PROGRESS = say
    data, target, prices, start_price = inputs(arguments.route)
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver="packed")  # the chain of the walk: with "auto" (the envelope search since #535) it would be the chain of the states the search touched
    say(f"planned: {len(plan.policy):,} policy states")
    chain = chain_of_plan(plan)
    m = chain.m
    finishing = _can_finish(chain)
    say(f"chain: {m:,} states, {len(chain.dst):,} edges, {int(finishing.sum()):,} can finish")
    done = _solved(chain)
    say(f"visits solved: {done.solved}, entry chances unsettled: {_entries(chain)[1]}; sum of visits x cost {float((done.visits * chain.cost).sum()):.4f}, plan mean {plan.mean_remaining:.4f}")
    if arguments.out and arguments.dump:  # the chain itself, for work on its cycles away from the 40-minute plan (R14: 372,000 edges, a few MB)
        Path(arguments.out).mkdir(parents=True, exist_ok=True)
        np.savez_compressed(Path(arguments.out) / f"{arguments.route}.chain.npz", ptr=chain.ptr, dst=chain.dst, prob=chain.prob, cost=chain.cost, key=chain.key, visits=done.visits)
        say("chain written")
    result = describe(*csr_among(chain, finishing))
    say(f"structure: {result}")
    if arguments.check:  # the visit chance of the most visited states, by the cycles of the chain and by one absorbing solve each (two methods, one number)
        order = [int(i) for i in np.argsort(-done.visits) if i != 0][: arguments.check]
        found = reach_of(chain, order)
        system = _system(chain, finishing)
        checks = []
        for i, reach in zip(order, found):
            absorbing = np.zeros(system.nt, dtype=bool)
            absorbing[system.position[i]] = True
            single = _entry_chance(system, absorbing)
            checks.append({"state": i, "visits": float(done.visits[i]), "cycles": reach.chance, "single_solve": single})
            say(f"check: state {i}: visits {done.visits[i]:.6g}, chance by the cycles {reach.chance}, by one absorbing solve {single}")
        result["checks"] = checks
        result["worst_difference"] = max(abs(c["cycles"] - c["single_solve"]) / max(c["single_solve"], 1e-300) for c in checks if c["cycles"] is not None and c["single_solve"] is not None)
        say(f"check: the worst relative difference {result['worst_difference']:.3g}")
    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{arguments.route}.structure.json").write_text(json.dumps({"route": arguments.route, **result}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
