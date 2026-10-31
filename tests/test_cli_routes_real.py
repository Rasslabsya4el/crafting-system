"""R10, R11 and R05 end to end on the real 3.29.3.3 dump, at the committed prices (ticket #60).

The prices are `tests/fixtures/prices/routes-allflame-2026-10-31.json`: poe.ninja (and, for the tiers it
does not list, poe.watch and an earlier league, each stamped in the file) of 2026-10-31 and the trade-API
price of each start item, so the checks do not move with the market. These tests need the cached dump
(`<cache dir>/repoe-fork/3.29.3.3/`; point `CRAFTING_CACHE_DIR` at it) and skip cleanly without it, as in
CI. Each route is planned once for the whole module; R05 takes minutes.

Done when (the ticket): the CLI returns the policy with odds, mean and p90 and `--verify` agrees, and at the
same prices the solver's mean is no more than the guide's given route's.
"""

from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import BenchCraft, RemoveCraftedMods
from crafting_system.cli import RESTART, evaluate_route, load_route, make_plan, verify
from crafting_system.prices import load_price_file
from crafting_system.targets import KOfN, load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
RUNS = 3_000
UNPRICED_ESSENCES = {
    f"{level} Essence of {name}"
    for level, name in [
        ("Screaming", "Greed"), ("Screaming", "Sorrow"), ("Screaming", "Wrath"), ("Screaming", "Doubt"),
        ("Screaming", "Scorn"), ("Shrieking", "Doubt"), ("Shrieking", "Dread"),
    ]
}  # fmt: skip

#         target file stem            crafts kept by the rule (mod ids that count toward a requirement)
ROUTES = {
    "R10": "r10-fractured-boots",
    "R11": "r11-reservation-helmet",
    "R05": "r05-strength-ring",
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=list(ROUTES))
def solved(request, data):
    """(route id, target, plan) for one benchmark route."""
    stem = ROUTES[request.param]
    target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
    plan = make_plan(data, target, load_price_file(PRICES))
    return request.param, stem, target, plan


def leaf_mods(target) -> set[str]:
    found: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, KOfN):
            for member in node.of:
                walk(member)
        elif not node.not_crafted:
            found.update(node.mod_ids)

    for requirement in target.requirements:
        walk(requirement)
    return found


def test_the_policy_reaches_the_goal_with_odds_mean_and_p90(solved):
    _, _, _, plan = solved

    risk = plan.risk
    assert risk.success_probability.value == pytest.approx(1.0)
    assert 0.0 < risk.mean.value < float("inf")
    assert risk.p90.value >= risk.p50.value > 0.0
    assert plan.mean_remaining == pytest.approx(risk.mean.value, rel=1e-9)
    # only some essences that no source prices (poe.ninja, poe.watch, an earlier league) are dropped
    assert {drop.label for drop in plan.dropped} <= UNPRICED_ESSENCES


def test_verify_agrees_with_the_computed_mean(solved, data):
    _, _, _, plan = solved

    check = verify(data, plan, runs=RUNS, seed=11)

    assert check.agrees, check.reason
    assert check.report.successes == RUNS


def test_only_the_crafts_whose_mod_counts_toward_a_requirement_are_offered(solved):
    _, _, target, plan = solved

    counting = leaf_mods(target)
    crafts = [priced.offer.action for priced in plan.offers if isinstance(priced.offer.action, BenchCraft)]
    assert all(craft.mod_id in counting for craft in crafts)
    (left,) = plan.left_out  # the rest of the bench is left out and listed, none of it unpriced
    assert len(left.labels) > 100
    assert any(isinstance(priced.offer.action, RemoveCraftedMods) for priced in plan.offers) == bool(crafts)


def test_the_start_item_can_be_bought_again_from_every_state_but_the_start(solved):
    _, _, _, plan = solved

    restart = next(priced for priced in plan.offers if priced.label == RESTART)

    assert restart.cost == plan.start_price.chaos > 0


def test_the_solver_is_no_dearer_than_the_guides_given_route(solved, data):
    route_id, stem, _, plan = solved

    route = load_route(ROOT / "examples" / "routes" / f"{stem}.yaml", plan, data)
    result = evaluate_route(plan, route, data)

    assert result.gaps == ()
    assert result.risk.success_probability.value == pytest.approx(1.0)
    # R11: the target cannot ask for "at least Shrieking" until #71, so the solver may use the weaker
    # Screaming essence and this comparison proves less there (see the target file)
    assert plan.risk.mean.value <= result.risk.mean.value * (1 + 1e-9), route_id


def test_the_states_of_a_policy_with_crafts_show_the_crafted_and_the_other_mods(solved, data):
    from crafting_system.cli import build_report

    route_id, _, _, plan = solved
    if route_id == "R11":
        pytest.skip("no craft counts toward R11, so its states keep no other mods")

    text = " | ".join(state.description for state in build_report(plan, data).states)

    assert "other mods:" in text
