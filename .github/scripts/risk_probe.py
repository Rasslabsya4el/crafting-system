"""Evaluate the risk of a dumped policy chain with the product code, with the trace of each step (ticket #70).

    python .github/scripts/risk_probe.py CHAIN.npz [--out DIR]

`CHAIN.npz` is what `chain_dump.py` writes (or `tests/fixtures/chains/r14-lumped.npz`): per block of the lumped chain the cost, the goal
flag, the CSR of its successors with float probabilities (turned back into integer weights at 2**52) and the start. It runs the
steps `packed_risk` runs (the ordinary grid, then the coarse grid or attempt by attempt) and prints the seconds of each. Never run on a PC.
"""

import argparse
import faulthandler
import json
import sys
import time
from pathlib import Path

import numpy as np

from crafting_system.cli._plan import evaluate_risk
from crafting_system.risk import _regen
from crafting_system.solver import Action, Outcome


def load(path: Path):
    d = np.load(path)
    cost, goal, label, ptr, succ, prob, labels = (d[k] for k in ("cost", "goal", "label", "ptr", "succ", "prob", "labels"))
    policy = {}
    for s in range(len(cost)):
        if goal[s] or label[s] < 0:
            continue
        lo, hi = ptr[s], ptr[s + 1]
        outcomes = tuple(Outcome(int(j), int(round(p * 2**52))) for j, p in zip(succ[lo:hi].tolist(), prob[lo:hi].tolist()) if p > 0)
        policy[s] = Action(str(labels[label[s]]), float(cost[s]), outcomes)
    goals = {s for s in range(len(cost)) if goal[s]}
    return policy, int(d["start"]), goals, float(d["mean"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chain")
    parser.add_argument("--out")
    arguments = parser.parse_args()
    faulthandler.dump_traceback_later(600, repeat=True, file=sys.stderr)
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:8.1f} s] {line}", flush=True)

    policy, start, goals, mean = load(Path(arguments.chain))
    say(f"{len(policy):,} blocks with an action, mean {mean!r}")
    _regen.TRACE = say
    result = {}
    for name, extra in (("ordinary", {}), ("coarse_then_attempts", {"coarse_first": True, "regenerative": True})):
        started = time.perf_counter()
        risk = evaluate_risk(policy, start, lambda b: b in goals, mean, free_cost=None, packed_moments=True, **extra)
        seconds = time.perf_counter() - started
        say(f"{name}: {seconds:.1f} s: p50 {risk.p50}, p90 {risk.p90}, cvar {risk.cvar}, grid {risk.grid}")
        result[name] = {
            "seconds": seconds, "p50": [risk.p50.low, risk.p50.value, risk.p50.high], "p90": [risk.p90.low, risk.p90.value, risk.p90.high],
            "cvar": [risk.cvar.low, risk.cvar.value, risk.cvar.high], "step": risk.grid.step,
        }
        if all(np.isfinite(e.high) for e in (risk.p50, risk.p90, risk.cvar)):
            break
    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "risk_probe.json").write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
