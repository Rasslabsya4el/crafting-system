"""R08 and R09 end to end on the real 3.29.3.3 dump, at the committed prices (ticket #63).

R08 and R09 are the fossil boots of the reference routes: rare Sorcerer Boots (Energy Shield) and rare Two-Toned Boots
(Life) of item level 86, Fossils in a resonator until the boots hold the top tier of Energy Shield or Life and a
Movement Speed, then a Movement Speed from the bench. The prices are `tests/fixtures/prices/routes-allflame-fossils-2026-11-01.json`:
the other real routes' prices plus the poe.ninja fossil and resonator lines of 2026-11-01 (no Tangled Fossil line, so
the sets with a Tangled Fossil are unpriced and left out) and the trade price of the start boots (a normal base of
item level 86, the mean of the 5 cheapest instant-buyout listings, plus the Orb of Alchemy that makes it rare). These
tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`; point `CRAFTING_CACHE_DIR` at it; CI fetches it, ticket
#165) and skip cleanly without it.

Done when (the ticket): the CLI returns the policy with odds, mean and p90 and `--verify` agrees; at the same prices the
solver's mean is no more than the given route's. Times and state counts are in the PR, not asserted (ADR-0014).
"""

import datetime
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import read_json

from crafting_system.actions import ApplyFossils, BenchCraft
from crafting_system.cli import RESTART, build_report, evaluate_route, load_route, main, make_plan
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-fossils-2026-11-01.json"
RUNS = 200
ROUTES = {
    "r08": ("r08-energy-shield-boots", "R08 start boots", 29.82716, "Dense Fossil"),
    "r09": ("r09-life-boots", "R09 start boots", 5.02716, "Pristine Fossil"),
}
SPEED_CRAFTS = 3  # the bench's three Movement Speed crafts at their top tier are the only crafts that count


def paths(route: str):
    stem = ROUTES[route][0]
    return ROOT / "examples" / "targets" / f"{stem}.yaml", ROOT / "examples" / "routes" / f"{stem}.yaml"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=sorted(ROUTES))
def route(request):
    return request.param


@pytest.fixture(scope="module")
def plans(data):
    return {}


@pytest.fixture(scope="module")
def plan(data, route, plans):
    if route not in plans:
        plans[route] = make_plan(data, load_target(paths(route)[0], data), load_price_file(PRICES))
    return plans[route]


def test_the_start_boots_cost_their_trade_price_plus_an_alchemy(plan, route):
    _, name, chaos, _ = ROUTES[route]

    assert plan.start_price.name == name
    assert plan.start_price.chaos == pytest.approx(chaos)
    assert plan.start_price.source == "trade-api"


def test_the_fossil_sets_the_bench_crafts_and_the_restart_are_offered(plan, route):
    offers = {priced.label: priced for priced in plan.offers}
    guide_fossil = ROUTES[route][3]
    fossil_sets = [priced for priced in plan.offers if isinstance(priced.offer.action, ApplyFossils)]
    crafts = [priced for priced in plan.offers if isinstance(priced.offer.action, BenchCraft)]

    assert RESTART in offers
    assert len(fossil_sets) > 5_000  # 12,700 sets, the ones with a Tangled Fossil unpriced
    assert f"Fossils {guide_fossil} + Shuddering Fossil" in offers
    assert len(crafts) == SPEED_CRAFTS
    unpriced = {name for drop in plan.dropped for name in drop.missing}
    assert unpriced == {"Tangled Fossil"}


def test_the_policy_reaches_the_goal_with_exact_odds_and_mean(plan):
    assert plan.approximation is None
    risk = plan.risk

    assert risk.success_probability.value == pytest.approx(1.0)
    assert 0.0 < risk.mean.value < float("inf")
    assert plan.mean_remaining == pytest.approx(risk.mean.value, rel=1e-9)


def test_the_policy_starts_with_a_fossil_set(plan, data):
    report = build_report(plan, data)

    first = next(state for state in report.states if report.ids[plan.start] == state.id)
    assert first.action.startswith("Fossils ")


def test_the_solver_is_no_dearer_than_the_guides_given_route(plan, data, route):
    given = load_route(paths(route)[1], plan, data)
    result = evaluate_route(plan, given, data)

    assert result.gaps == ()
    assert result.risk.success_probability.value == pytest.approx(1.0)
    assert plan.risk.mean.value <= result.risk.mean.value * (1 + 1e-9)


def test_the_command_returns_the_policy_and_verify_agrees(tmp_path, data, route, capsys):
    target, given = paths(route)
    out = tmp_path / "policy.json"

    code = main(
        [str(target), "--json", str(out), "--verify", "--runs", str(RUNS), "--route", str(given), "--exact"],
        data=data,
        prices=load_price_file(PRICES),
        env={},
        today=datetime.date(2026, 11, 1),
    )

    assert code == 0
    document = read_json(out)
    totals = document["totals"]
    assert totals["success_probability"]["value"] == pytest.approx(1.0)
    assert totals["mean_cost"]["value"] > ROUTES[route][2]
    assert document["verification"]["agrees"] is True
    assert document["given_route"]["gaps"] == []
    assert totals["mean_cost"]["value"] <= document["given_route"]["mean_cost"]["value"] * (1 + 1e-9)
    assert document["states"]
    capsys.readouterr()
