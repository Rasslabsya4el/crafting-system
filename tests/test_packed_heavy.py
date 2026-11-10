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

import golden_diff
import pytest
from abstraction_support import real_game_data
from test_strand_routes import without_strand_words
from test_strand_routes_load import FILES, flat_price_file

from crafting_system.actions import DRAW_LABEL
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
    """(route id, plan) of one heavy route, planned once by `make_plan` on the packed solver by name (`auto` is the envelope search since #535, which walks less)."""
    data = real_game_data()
    route = request.param
    if route == "S02":
        stem = "s02-fire-res-ring-showcase"
        text = without_strand_words((FILES / "targets" / f"{stem}.yaml").read_text(encoding="utf-8"))
        plan = make_plan(data, parse_target(text, data, source=stem), flat_price_file(), start_price=10.0, solver="packed")
    else:
        target = load_target(ROOT / "examples" / "targets" / f"{TARGETS[route]}.yaml", data)
        plan = make_plan(data, target, load_price_file(PRICES), solver="packed")
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
    golden_diff.check_objects(  # the tolerance of pytest.approx on the mean (rel 1e-9); the states exactly
        {"mean_remaining": expected["mean_remaining"], "states": expected["states"]},
        {"mean_remaining": plan.mean_remaining, "states": len(plan.solution.values)},
        f"{route}: the exact value differs from tests/golden/packed_values.json", rel=1e-9,
    )  # fmt: skip


@HEAVY
def test_the_value_is_certified_and_was_solved_packed(planned):
    _, plan = planned

    assert plan.solution.error_bound < 1e-6
    assert isinstance(plan.policy, PackedPolicy)
    assert plan.risk is not None and plan.risk.success_probability.value == pytest.approx(1.0)
    assert plan.risk.mean.value == pytest.approx(plan.mean_remaining, rel=1e-6)


@HEAVY
def test_r14_does_not_open_with_a_transmutation_on_its_magic_bow_and_offers_none(planned):
    """#576: R14 starts from a Magic bow (the guide opens with Alteration, no Transmutation Orb is named), so the plan's first step is not a Transmutation Orb."""
    route, plan = planned
    if route != "R14":
        pytest.skip("only R14 is a Magic start")

    assert plan.target.start_item.rarity.value == "magic"
    first = plan.policy[plan.start]
    assert first.label == DRAW_LABEL  # the bought bow is the item the market sells (ADR-0064): the draw comes first, then the decision on each outcome of it
    chosen = {plan.policy[state].label for state, _ in first.outcomes if state in plan.policy}
    assert {"Orb of Alteration", "Orb of Augmentation"} <= chosen  # an Augmentation where the bow holds 1 mod, an Alteration where it holds 2
    assert "Orb of Transmutation" not in chosen
    assert "Orb of Transmutation" not in {offer.label for offer in plan.offers}


@HEAVY
def test_the_policy_reaches_the_goal_from_the_start(planned):
    _, plan = planned
    packed = plan.packed

    # on the merged chain (every state of the concrete policy stands for a class there); the concrete policy of R04 holds
    # 18,696 states with hundreds of outcomes each, which a 16 GB runner cannot also hold next to the walked graph
    reached = policy_states(packed.risk_start, packed.risk_policy, packed.risk_is_goal)
    assert any(packed.risk_is_goal(c) for c in reached)
    assert all(c in packed.risk_policy for c in reached if not packed.risk_is_goal(c))
    assert len(plan.policy) >= len(packed.risk_policy)

    first = [state for _, state in zip(range(20), plan.policy)]  # a few concrete actions are built on demand and are sound
    for state in first:
        action = plan.policy[state]
        assert action.cost > 0 and action.outcomes and action.label in {offer.label for offer in plan.offers}
