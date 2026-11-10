"""The mean, the first actions and the state counts of R08, R09, R13 and R14 with and without the draw of a bought item's mods (ticket #640, ADR-0064).

    python .github/scripts/start_draw_measure.py ROUTE [--old] [--out DIR]

`ROUTE` is r08, r09, r13 or r14. The plan is `make_plan(solver="auto")` at the committed prices, exact (since #535 the envelope search where its bound can be built, so `states` counts the states it touched). With `--old` the start is the item with no mods
as before #640 (the draw is switched off), so one commit measures both sides. Writes `<route>.<new|old>.json`: the mean cost from the start item (the mean
still to pay and the whole, with the start price), the certified error bound, the states of the graph and of the policy, the seconds, and the first
actions: what the policy does at the start and, for the new model, how the outcomes of the draw split by the action chosen on each (and by the number of
mods the state tracks, when it tracks them). Never run on a PC for R14 or R08 and R09: they walk for minutes. Run by `heavy_dispatch.py`.
"""

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from crafting_system.cli import _plan, make_plan
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGETS = {"r08": "r08-energy-shield-boots", "r09": "r09-life-boots", "r13": "r13-life-resist-belt", "r14": "r14-hunter-bow"}


def first_actions(plan) -> dict:
    """What the policy does at the start, and how the outcomes of a first draw split by the action chosen on each."""
    first = plan.policy[plan.start]
    if not plan.start.flags.unopened:
        return {"start_action": first.label, "outcomes": None}
    total = sum(weight for _, weight in first.outcomes)
    by_action: Counter = Counter()
    by_mods: Counter = Counter()
    for state, weight in first.outcomes:
        chosen = "goal" if plan.is_goal(state) else plan.policy[state].label if state in plan.policy else "no action"
        by_action[chosen] += weight / total
        mods = len(state.slots) + len(state.fractured)
        by_mods[f"{mods if state.slots else 'junk not tracked'} mods: {chosen}"] += weight / total
    return {
        "start_action": first.label,
        "draw_outcomes": len(first.outcomes),
        "by_action": {key: round(value, 6) for key, value in by_action.most_common()},
        "by_mods_and_action": {key: round(value, 6) for key, value in sorted(by_mods.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("route", choices=sorted(TARGETS))
    parser.add_argument("--old", action="store_true", help="the start as before #640: the item with no mods, no draw")
    parser.add_argument("--out")
    arguments = parser.parse_args()
    if arguments.old:
        _plan.unopened_listing = lambda data, start: None  # the rule off: the start is the target's own item
    data = load_game_data()
    target = load_target(ROOT / "examples" / "targets" / f"{TARGETS[arguments.route]}.yaml", data)
    began = time.perf_counter()
    plan = make_plan(data, target, load_price_file(PRICES), solver="auto")
    result = {
        "route": arguments.route,
        "model": "old" if arguments.old else "new",
        "mean_remaining": plan.mean_remaining,
        "start_price": plan.start_price.chaos,
        "mean_total": plan.mean_remaining + plan.start_price.chaos,
        "error_bound": plan.solution.error_bound,
        "states": len(plan.solution.values),
        "policy_states": len(plan.policy),
        "offers": len(plan.offers),
        "seconds": round(time.perf_counter() - began, 1),
        **first_actions(plan),
    }
    text = json.dumps(result, indent=2)
    print(text)
    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{arguments.route}.{result['model']}.json").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
