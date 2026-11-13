"""The risk of the optimal policies of R04 and R14, from their lumped chains (ticket #70).

`tests/fixtures/chains/r04-lumped.npz` and `r14-lumped.npz` are the optimal policy's chain of each route after the exact lumping
(`solver._packed_lump`), as `.github/scripts/chain_dump.py` writes it: per block the cost of its action, the goal flag, the successors with
float chances and the exact mean of the plan at the committed prices (`tests/fixtures/prices/routes-allflame-2026-07-31.json`, main of
2026-11-02, packed goldens). R04's 552 blocks and 2,746 transitions are run in seconds and their p90 is pinned here; R14's 14,743 blocks
and 79,536 transitions take minutes (one attempt at a time, `risk._regen`), so they run in a heavy run (`CRAFTING_HEAVY=1`).

What the p90 is. Both are certified brackets: the true 90th percentile of the total cost lies between `low` and `high`, whatever the
grid. R04 (coarse grid, step 1.528) is bracketed within 1.9% of its value, R14 (attempts of 0.4062 Chaos bins) within 14.5%
(1,774.5 Chaos wide at 12,278.1; the ladder ends at the restart cost over 32).
"""

import math
import os
from pathlib import Path

import numpy as np
import pytest

from crafting_system.cli._packed import PackedResult
from crafting_system.cli._plan import packed_risk
from crafting_system.solver import Action, Outcome

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "chains"
HEAVY = pytest.mark.skipif(not os.environ.get("CRAFTING_HEAVY"), reason="heavy: set CRAFTING_HEAVY=1 (a heavy run of GitHub, not a CI shard or a PC)")


def chain_result(name: str) -> tuple[PackedResult, float]:
    """The dumped chain as the `PackedResult` the planner hands to `packed_risk`, and the plan's exact mean."""
    d = np.load(FIXTURES / f"{name}-lumped.npz")
    cost, goal, label, ptr, succ, prob, labels = (d[k] for k in ("cost", "goal", "label", "ptr", "succ", "prob", "labels"))
    policy = {}
    for s in range(len(cost)):
        if goal[s] or label[s] < 0:
            continue
        lo, hi = ptr[s], ptr[s + 1]
        outcomes = tuple(Outcome(int(j), int(round(p * 2**52))) for j, p in zip(succ[lo:hi].tolist(), prob[lo:hi].tolist()) if p > 0)
        policy[s] = Action(str(labels[label[s]]), float(cost[s]), outcomes)
    goals = {s for s in range(len(cost)) if goal[s]}
    return PackedResult(None, policy, int(d["start"]), lambda b: b in goals, {}), float(d["mean"])


def relative_width(estimate) -> float:
    return (estimate.high - estimate.low) / estimate.value


def test_r04_has_a_p90_within_two_percent_and_the_exact_mean():
    result, mean = chain_result("r04")

    risk, found = packed_risk(result, mean, None)

    assert found == () and risk.success_probability.value == 1.0
    assert risk.mean.value == pytest.approx(69257.5365, abs=1e-3)
    assert risk.p50.low <= 48_537.7 <= risk.p50.high and relative_width(risk.p50) < 0.02
    assert risk.p90.low <= 157_293.1 <= risk.p90.high and relative_width(risk.p90) < 0.02
    assert math.isfinite(risk.cvar.high) and risk.p90.low < risk.cvar.low
    assert risk.grid.step > 0.3668  # above the cheapest action (Remove Crafted Mods): the coarse grid, not the ordinary one


@HEAVY
def test_r14_has_a_p90_within_fifteen_percent_and_the_exact_mean():
    result, mean = chain_result("r14")

    risk, found = packed_risk(result, mean, None)

    assert found == () and risk.success_probability.value == 1.0
    assert risk.mean.value == pytest.approx(5784.4887, abs=1e-3)
    assert risk.p50.low <= 4_570.3 <= risk.p50.high and relative_width(risk.p50) < 0.15
    assert risk.p90.low <= 12_278.1 <= risk.p90.high and relative_width(risk.p90) < 0.15
    assert math.isfinite(risk.cvar.high)
    assert risk.grid.step < 1.0  # attempt by attempt, on a step of the restart's cost over 32 at the finest
