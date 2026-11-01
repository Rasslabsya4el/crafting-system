"""R13 end to end on the real 3.29.3.3 dump, at the committed prices (ticket #66).

R13 is the alt-regal belt of the reference routes: a normal Leather Belt of item level 86 (the poe.ninja base
price, 10 Chaos), Orbs of Transmutation and Alteration until it holds tier-1 life and a tier-1 resistance, a Regal
Orb for the second tier-1 resistance (the guide buys the belt again when the Regal gives anything else), and the
bench finish for the damage modifier. The prices are `tests/fixtures/prices/routes-allflame-2026-10-31.json`, the
same file as the other real routes, so the checks do not move with the market. These tests need the cached dump
(`<cache dir>/repoe-fork/3.29.3.3/`; point `CRAFTING_CACHE_DIR` at it; CI fetches it, ticket #165) and skip
cleanly without it.

Done when (the ticket): the CLI returns the policy with odds, mean and p90 and `--verify` agrees, and at the same
prices the solver's mean is no more than the guide's given route's. The odds and the mean are exact; p90 is not resolved
by the budget grid (the cheapest action, 0.0058 Chaos, is far below the cost scale, ticket #190) and the p90 `--verify`
simulates is labelled as not certified. Four simulated crafts cannot reject a wrong mean (the detectable error is about
the mean itself); the PR records the 20-run check.
"""

import datetime
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import read_json

from crafting_system.actions import BenchCraft, RemoveCraftedMods
from crafting_system.cli import RESTART, build_report, evaluate_route, load_route, main, make_plan
from crafting_system.cli._report import unresolved
from crafting_system.prices import load_price_file
from crafting_system.targets import KOfN, load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGET = ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml"
ROUTE = ROOT / "examples" / "routes" / "r13-life-resist-belt.yaml"
RUNS = 4  # one simulated craft takes about 50 seconds here (about 50,000 uses of an orb), so --verify gets four runs
BELT = "Leather Belt (ilvl 86)"
BELT_PRICE = 10.0  # poe.ninja BaseType overview, Allflame, 2026-11-01: a normal Leather Belt of item level 86
ORBS_OF_THE_GUIDE = {"Orb of Transmutation", "Orb of Alteration", "Regal Orb"}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def plan(data):
    return make_plan(data, load_target(TARGET, data), load_price_file(PRICES))


def counting_mods(target) -> set[str]:
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


def test_the_start_belt_costs_its_poe_ninja_base_price(plan):
    assert plan.start_price.name == BELT
    assert plan.start_price.chaos == pytest.approx(BELT_PRICE)
    assert plan.start_price.source == "poe.ninja"


def test_the_orbs_of_the_guide_and_the_restart_are_offered(plan):
    labels = {priced.label for priced in plan.offers}

    assert ORBS_OF_THE_GUIDE <= labels
    restart = next(priced for priced in plan.offers if priced.label == RESTART)
    assert restart.cost == pytest.approx(BELT_PRICE)


def test_only_the_crafts_whose_mod_counts_toward_a_requirement_are_offered(plan):
    counting = counting_mods(plan.target)
    crafts = [priced.offer.action for priced in plan.offers if isinstance(priced.offer.action, BenchCraft)]

    assert crafts and all(craft.mod_id in counting for craft in crafts)
    assert any(isinstance(priced.offer.action, RemoveCraftedMods) for priced in plan.offers)
    kinds_left, crafts_left = plan.left_out  # the kinds the target does not name, then the rest of the bench: none unpriced
    assert "chaos-orb" in kinds_left.labels and len(crafts_left.labels) > 100


def test_the_target_names_the_guides_kinds_so_no_chaos_orb_is_offered(plan):
    labels = {priced.label for priced in plan.offers}

    assert "Chaos Orb" not in labels and not any("Essence" in label or label.startswith("Harvest") for label in labels)


def test_the_policy_reaches_the_goal_with_exact_odds_and_mean_and_the_quantiles_are_unresolved(plan):
    risk = plan.risk

    assert risk.success_probability.value == pytest.approx(1.0)
    assert 0.0 < risk.mean.value < float("inf")
    assert plan.mean_remaining == pytest.approx(risk.mean.value, rel=1e-9)
    # the grid cannot step over the 0.0058 Chaos of the Orb of Transmutation: p90 is not resolved (ticket #190)
    assert unresolved(risk, risk.p50) and unresolved(risk, risk.p90)


def test_the_solver_is_no_dearer_than_the_guides_given_route(plan, data):
    route = load_route(ROUTE, plan, data)
    result = evaluate_route(plan, route, data)

    assert result.gaps == ()
    assert result.risk.success_probability.value == pytest.approx(1.0)
    assert plan.risk.mean.value <= result.risk.mean.value * (1 + 1e-9)


def test_the_policy_starts_with_the_orb_that_makes_the_belt_magic(plan, data):
    report = build_report(plan, data)

    first = next(state for state in report.states if report.ids[plan.start] == state.id)
    assert first.action in {"Orb of Transmutation", "Orb of Alchemy"}


def test_the_command_returns_the_policy_and_verify_agrees(tmp_path, data, capsys):
    out = tmp_path / "policy.json"

    code = main(
        [str(TARGET), "--json", str(out), "--verify", "--runs", str(RUNS), "--route", str(ROUTE)],
        data=data,
        prices=load_price_file(PRICES),
        env={},
        today=datetime.date(2026, 11, 1),
    )

    assert code == 0
    document = read_json(out)
    totals = document["totals"]
    assert totals["success_probability"]["value"] == pytest.approx(1.0)
    assert totals["mean_cost"]["value"] > BELT_PRICE
    assert totals["quantiles_resolved"] is False and totals["p90"]["value"] is None
    simulated = document["verification"]["simulated_p90"]
    assert simulated["value"] > document["verification"]["simulated_mean_cost"]["value"]  # simulated, not certified
    assert document["verification"]["agrees"] is True
    assert document["given_route"]["gaps"] == []
    assert totals["mean_cost"]["value"] <= document["given_route"]["mean_cost"]["value"] * (1 + 1e-9)
    assert document["states"]
    text = capsys.readouterr().out
    assert "not resolved on the grid" in text and "simulated, not certified" in text
