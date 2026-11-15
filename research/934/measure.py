"""Measure what ticket #934 asks before and after its change: per kind of action, the outcomes of a kernel against the outcomes that differ
in something the goal or an enabled action reads; per exact draw, its families, classes, labels, outcomes and seconds; where the time goes.

    python research/934/measure.py (--route r04 | --case fossil-sets/small) [--seconds 300] [--out DIR]

It plans with the planner's own entry, as `research/881/profile_plan.py` does (no budget), and stops itself after `--seconds` (a heavy run
on a case that passes the memory cap would otherwise be killed with nothing written): what it counted until then is written either way.

**Outcomes that differ in what is read.** Two successors `s`, `t` of a kernel are told apart by nothing the goal or an action reads when they
have the same status (the goal reads it) and, for every enabled action `a`, the same projection `Abstraction._view(., erases(., a))`
(ticket #827: the kernel of `a` is made from that projection alone, so equal projections give equal kernels, and by induction equal values
under every policy). That is the class a kernel could be enumerated by. For each kernel built the script counts its outcomes and its classes.

Never run on a PC: `python .github/scripts/heavy_dispatch.py run --no-wait --ref <branch> --runners N --command '...'`.
"""

import argparse
import json
import os
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "881"))
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
if os.environ.get("CRAFTING_SOURCE"):
    sys.path.insert(0, os.environ["CRAFTING_SOURCE"])

import profile_plan as PP  # noqa: E402

from crafting_system.abstraction import _kernel as K  # noqa: E402
from crafting_system.actions import draw as D  # noqa: E402
from crafting_system.actions import outcomes as O  # noqa: E402

kinds: dict[str, Counter] = defaultdict(Counter)
draws: list[dict] = []
began = time.perf_counter()


def class_key(ab, state):
    erasing = {a: ab._erases(state, a) for a in ab.enabled}
    return (state.status, frozenset(ab._view(state, e) for e in erasing.values()))


kernel = K.Abstraction.kernel


def counted_kernel(self, state, action):
    out = kernel(self, state, action)
    row = kinds[type(action).__name__]
    row["kernels"] += 1
    row["outcomes"] += len(out)
    row["classes"] += len({class_key(self, s) for s in out}) if self.enabled else len(out)
    row["max_outcomes"] = max(row["max_outcomes"], len(out))
    return out


engine = D.exact_distribution


def counted_engine(pool, free, tag, totals, kept, label, blocked=frozenset()):
    t = time.perf_counter()
    out = engine(pool, free, tag, totals, kept, label, blocked)
    seconds = time.perf_counter() - t
    classes = set()
    labels = set()
    for fam in pool:
        by = Counter()
        for entry in fam.mods:
            lab = label(entry.mod)
            labels.add(lab)
            by[lab] += entry.weight
        classes.add((fam.side, tuple(sorted(by.items(), key=repr))))
    draws.append({"families": len(pool), "classes": len(classes), "labels": len(labels), "outcomes": len(out), "tag": tag is not None, "seconds": round(seconds, 4)})
    return out


def report(args, reason: str) -> dict:
    top = sorted(draws, key=lambda d: -d["seconds"])[:10]
    return {
        "name": args.case or args.route,
        "stopped": reason,
        "seconds": round(time.perf_counter() - began, 1),
        "kernels_by_kind": {k: dict(v) for k, v in sorted(kinds.items())},
        "draws": {
            "calls": len(draws),
            "seconds": round(sum(d["seconds"] for d in draws), 1),
            "outcomes": sum(d["outcomes"] for d in draws),
            "max_classes": max((d["classes"] for d in draws), default=0),
            "max_labels": max((d["labels"] for d in draws), default=0),
            "slowest": top,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route")
    parser.add_argument("--case")
    parser.add_argument("--seconds", type=float, default=300)
    parser.add_argument("--out")
    args = parser.parse_args()
    K.Abstraction.kernel = counted_kernel
    D.exact_distribution = counted_engine
    O.exact_distribution = counted_engine

    def write(reason: str) -> None:
        text = json.dumps(report(args, reason), indent=1, default=str)
        print(text, flush=True)
        if args.out:
            folder = Path(args.out)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{(args.case or args.route).replace('/', '__')}.measure.json").write_text(text + "\n", encoding="utf-8")

    def stop() -> None:
        write(f"stopped by the script after {args.seconds:.0f} s")
        os._exit(0)

    threading.Timer(args.seconds, stop).start()
    from crafting_system.cli import make_plan

    data, target, prices, start_price, solver = PP.inputs(args)
    try:
        make_plan(data, target, prices, start_price=start_price, budget=None, solver=solver, with_risk=False)
        write("planned")
    except Exception as problem:  # noqa: BLE001 - a measurement: the refusal is part of the record
        write(f"{type(problem).__name__}: {str(problem)[:300]}")
    os._exit(0)


if __name__ == "__main__":
    main()
