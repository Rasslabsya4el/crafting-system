"""R04, R14 and S02 end to end through `make_plan` on the packed solver (ticket #374, ADR-0063 point 1).

"Done when: R04, R14 and S02 give their exact value through the planner." The graphs are R04's 177,242 states and 535.9 M
transitions, R14's 816,153 states and S02's 106,002 states and 76.6 billion transitions (ticket #312): minutes to half an
hour and gigabytes each. They are therefore run by a heavy run, not by a CI shard:

    python .github/scripts/heavy_dispatch.py run --ref BRANCH --runners 1 --timeout-minutes 60 \
        --command 'CRAFTING_HEAVY=1 uv run --no-sync pytest -q -p no:cacheprovider tests/test_packed_heavy.py -k R04'

The exact values are a function of the main they were taken on (the chances of the Exalted Orb and the essences moved
between two snapshots in #312), so the goldens in `tests/golden/packed_values.json` carry the commit of that main; when
an action's draw or the data pin moves, the heavy run is repeated and the golden is rewritten with
`UPDATE_GOLDEN=1` (it rewrites the file from the values this run found).

S02 is planned as today's loaders read it (strand words removed, every currency 1 chaos, start item 10 chaos), the setting of
`tests/test_strand_routes_load.py`.
"""

import json
import os
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from test_strand_routes import without_strand_words
from test_strand_routes_load import FILES, flat_price_file

from crafting_system.cli import make_plan
from crafting_system.cli._packed import PackedPolicy
from crafting_system.cli._reach import policy_states
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target, parse_target

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden" / "packed_values.json"
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGETS = {"R04": "r04-penetrating-quiver", "R14": "r14-hunter-bow"}
HEAVY = pytest.mark.skipif(not os.environ.get("CRAFTING_HEAVY"), reason="heavy: set CRAFTING_HEAVY=1 (a heavy run of GitHub, not a CI shard or a PC)")


def golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_the_golden_values_file_names_the_main_it_was_taken_on():
    found = golden()

    assert found["main"] and set(found["routes"]) == {"R04", "R14", "S02"}
    for row in found["routes"].values():
        assert row["mean_remaining"] > 0 and row["states"] > 0 and row["error_bound"] < 1e-6


@pytest.fixture(scope="module", params=["R04", "R14", "S02"])
def planned(request):
    """(route id, plan) of one heavy route, planned once by `make_plan` (exact, the packed solver is picked by the size)."""
    data = real_game_data()
    route = request.param
    if route == "S02":
        stem = "s02-fire-res-ring-showcase"
        text = without_strand_words((FILES / "targets" / f"{stem}.yaml").read_text(encoding="utf-8"))
        plan = make_plan(data, parse_target(text, data, source=stem), flat_price_file(), start_price=10.0)
    else:
        target = load_target(ROOT / "examples" / "targets" / f"{TARGETS[route]}.yaml", data)
        plan = make_plan(data, target, load_price_file(PRICES))
    return route, plan


@HEAVY
def test_the_planner_gives_the_exact_value_of_the_route(planned):
    route, plan = planned
    expected = golden()["routes"][route]

    if os.environ.get("UPDATE_GOLDEN"):
        found = golden()
        found["routes"][route].update(
            mean_remaining=plan.mean_remaining, states=len(plan.solution.values), error_bound=plan.solution.error_bound
        )
        GOLDEN.write_text(json.dumps(found, indent=1) + "\n", encoding="utf-8")
        return
    assert plan.mean_remaining == pytest.approx(expected["mean_remaining"], rel=1e-9)
    assert len(plan.solution.values) == expected["states"]


@HEAVY
def test_the_value_is_certified_and_was_solved_packed(planned):
    _, plan = planned

    assert plan.solution.error_bound < 1e-6
    assert isinstance(plan.policy, PackedPolicy)
    assert plan.risk is not None and plan.risk.success_probability.value == pytest.approx(1.0)
    assert plan.risk.mean.value == pytest.approx(plan.mean_remaining, rel=1e-6)


@HEAVY
def test_the_policy_reaches_the_goal_from_the_start(planned):
    route, plan = planned
    if route == "S02":  # its kernels have tens of thousands of outcomes each: the walk of the policy is not what this checks
        pytest.skip("S02's policy states are not all built; the risk run above walks its merged chain")

    reached = policy_states(plan.start, plan.policy, plan.is_goal)

    assert any(plan.is_goal(state) for state in reached)
    assert all(state in plan.policy for state in reached if not plan.is_goal(state))
