"""Plan R04 or R14 on the packed solver (`solver="packed"`) and dump the merged chain of the policy for offline work on its risk (ticket #70).

    python .github/scripts/chain_dump.py --route r04|r14 --out DIR [--risk]

Writes `<route>.chain.npz`: per class of the merged chain the policy's cost, its goal flag, the CSR of its successors with
float probabilities, the label index and the labels, the class of the start and the exact mean. With `--risk` it also
evaluates the risk of the plan with the product code and writes its numbers to `<route>.risk.json`.

Never run on a PC: the walk of R04 and R14 takes 8 to 25 minutes and several GB. Run by `.github/scripts/heavy_dispatch.py`.
"""

import argparse
import cProfile
import json
import pstats
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from packed_routes import inputs, peak_mb, risk_row  # noqa: E402

from crafting_system.cli import _packed, make_plan  # noqa: E402
from crafting_system.cli._limits import limit_document  # noqa: E402
from crafting_system.cli._plan import add_risk  # noqa: E402


def dump(plan, path: Path) -> dict:
    packed = plan.packed
    policy = packed.risk_policy
    classes = sorted(policy.keys() | {c for action in policy.values() for c, _ in action.outcomes} | {packed.risk_start})
    index = {c: i for i, c in enumerate(classes)}
    n = len(classes)
    cost = np.zeros(n)
    goal = np.zeros(n, dtype=bool)
    label = np.full(n, -1, dtype=np.int32)
    labels: list[str] = []
    ptr = np.zeros(n + 1, dtype=np.int64)
    succ: list[int] = []
    prob: list[float] = []
    for i, c in enumerate(classes):
        goal[i] = packed.risk_is_goal(c)
        action = policy.get(c)
        if action is not None:
            total = sum(weight for _, weight in action.outcomes)
            cost[i] = action.cost
            if action.label not in labels:
                labels.append(action.label)
            label[i] = labels.index(action.label)
            merged: dict[int, int] = {}
            for target, weight in action.outcomes:
                if weight:
                    merged[index[target]] = merged.get(index[target], 0) + weight
            for j, weight in merged.items():
                succ.append(j)
                prob.append(weight / total)
        ptr[i + 1] = len(succ)
    np.savez_compressed(
        path, cost=cost, goal=goal, label=label, ptr=ptr, succ=np.array(succ, dtype=np.int32), prob=np.array(prob),
        labels=np.array(labels), start=index[packed.risk_start], mean=plan.mean_remaining,
    )
    return {"classes": n, "expanded": int((label >= 0).sum()), "transitions": len(succ), "goals": int(goal.sum()), "labels": labels}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True, choices=("r04", "r14"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--risk", action="store_true")
    arguments = parser.parse_args()
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {peak_mb()} MB] {line}", flush=True)

    _packed.PROGRESS = say
    data, target, prices, start_price = inputs(arguments.route)
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, with_risk=False, solver="packed")  # the packed solver, as the title says: since #535 `auto` is the envelope search, which dumps another chain
    say(f"planned: mean {plan.mean_remaining!r}, {plan.solve_seconds:.0f} s")
    info = dump(plan, out / f"{arguments.route}.chain.npz")
    info.update(mean=plan.mean_remaining, solve_seconds=plan.solve_seconds, states=len(plan.solution.values), peak_mb=peak_mb())
    say(f"dumped {info['classes']:,} classes, {info['transitions']:,} transitions")
    (out / f"{arguments.route}.dump.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    if arguments.risk:
        profiler = cProfile.Profile()
        profiler.enable()
        risky = add_risk(plan)
        profiler.disable()
        pstats.Stats(profiler).sort_stats("cumulative").print_stats(30)
        row = risk_row(risky) or {}
        row.update(risk_seconds=risky.risk_seconds, limits=[limit_document(limit) for limit in risky.limits if limit.kind in ("how-solved", "display", "risk")], peak_mb=peak_mb())
        if risky.risk is not None:
            grid = risky.risk.grid
            row["grid"] = {"step": grid.step, "exact": grid.exact, "bins": grid.bins, "unresolved": grid.unresolved_mass}
        say(f"risk: {row}")
        (out / f"{arguments.route}.risk.json").write_text(json.dumps(row, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
