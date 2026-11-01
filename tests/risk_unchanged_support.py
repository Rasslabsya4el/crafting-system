"""The risk output of plans without a free action, as it was on main before ticket #349 (not collected as tests).

`snapshot()` runs `risk.evaluate` and the planner's `evaluate_risk` on policies none of whose actions is free (no action priced at the epsilon of
`price_offers`), and the R12 fixture plan; every report is kept as its `repr`, so every float is compared digit for digit. The file
`tests/golden/risk_unchanged_349.json` was made on main (at 00f667c, before the free-action grid of #349) by `python tests/risk_unchanged_support.py`.
"""

import json
import sys
from pathlib import Path

from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome

GOLDEN = Path(__file__).parent / "golden" / "risk_unchanged_349.json"
GOAL = "goal"


def is_goal(state):
    return state == GOAL


def policies() -> dict:
    """Policies whose costs are all ordinary (nothing priced at an epsilon), each with the start state and the mean the planner would pass."""
    return {
        "geometric": ({"S": Action("try", 1.0, (Outcome(GOAL, 1), Outcome("S", 3)))}, "S", 4.0),
        "cheap-orb-then-spam": (
            {
                "S": Action("orb", 0.01, (Outcome("A", 1),)),
                "A": Action("spam", 0.1, (Outcome(GOAL, 1), Outcome("A", 18), Outcome("B", 1))),
                "B": Action("restart", 1.0, (Outcome("S", 1),)),
            },
            "S",
            4.0,
        ),
        "restart-after-a-cheap-step": (
            {"R": Action("restart", 1.0, (Outcome(GOAL, 1), Outcome("L", 3))), "L": Action("cheap", 0.001, (Outcome("R", 1),))},
            "R",
            4.0,
        ),
        "far-above-the-cheapest": ({"S": Action("use", 0.001, (Outcome("S", 999_999), Outcome(GOAL, 1)))}, "S", 1000.0),
        "inexact-grid": (
            {
                "S": Action("a", 0.3, (Outcome("T", 2), Outcome(GOAL, 1))),
                "T": Action("b", 1.0 / 3.0, (Outcome("S", 1), Outcome("T", 1), Outcome(GOAL, 1))),
            },
            "S",
            2.0,
        ),
        "can-fail": (
            {"S": Action("use", 1.0, (Outcome("S", 1), Outcome(GOAL, 2), Outcome("dead", 1))), "dead": Action("stay", 1.0, (Outcome("dead", 1),))},
            "S",
            float("inf"),
        ),
        "an-input": (
            {
                "S": Action("craft", 2.0, (Outcome("S", 1), Outcome(GOAL, 1)), extra_inputs=("D",)),
                "D": Action("make-donor", 0.5, (Outcome("D", 1), Outcome(GOAL, 3))),
            },
            "S",
            6.0,
        ),
    }


def r12_risk() -> str:
    """`repr` of the risk report of the R12 fixture plan at the test prices."""
    from cli_support import R12, price_file
    from targets_support import DATA

    from crafting_system.cli import make_plan
    from crafting_system.targets import load_target

    return repr(make_plan(DATA, load_target(R12, DATA), price_file()).risk)


def snapshot() -> dict:
    from crafting_system.cli._plan import evaluate_risk

    found: dict[str, str] = {}
    for name, (policy, start, mean) in policies().items():
        found[f"evaluate {name}"] = repr(evaluate(policy, start, is_goal))
        found[f"evaluate_risk {name}"] = repr(evaluate_risk(policy, start, is_goal, mean))
    found["r12 plan"] = r12_risk()
    return found


if __name__ == "__main__":  # regenerate the golden file (only on a tree whose risk output is the one to keep)
    sys.path[:0] = [str(Path(__file__).parent)]
    GOLDEN.write_text(json.dumps(snapshot(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN}")
