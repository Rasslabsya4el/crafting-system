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
by the ordinary budget grid (the cheapest action, 0.0058 Chaos, is far below the cost scale); the coarse grid of
ticket #190 resolves it with a certified interval, and the p90 `--verify` simulates is labelled as not certified. Eight simulated crafts cannot reject a wrong mean (the detectable error is about
the mean itself); the PR records the 20-run check.
"""

import datetime
import math
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
RUNS = 8  # a simulated craft is about 50,000 orb uses and takes 10 s or more here, so --verify gets eight runs
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
    left = {entry.reason.split(",")[0]: entry.labels for entry in plan.left_out}  # none of it unpriced
    kinds_left = next(labels for reason, labels in left.items() if "does not name these kinds" in reason)
    crafts_left = next(labels for reason, labels in left.items() if "counts toward no requirement" in reason)
    assert "chaos-orb" in kinds_left and len(crafts_left) > 50  # 81 belt crafts


def test_the_target_names_the_guides_kinds_so_no_chaos_orb_is_offered(plan):
    labels = {priced.label for priced in plan.offers}

    assert "Chaos Orb" not in labels and not any("Essence" in label or label.startswith("Harvest") for label in labels)


def test_the_policy_reaches_the_goal_with_exact_odds_and_mean_and_certified_quantiles(plan):
    risk = plan.risk

    assert risk.success_probability.value == pytest.approx(1.0)
    assert 0.0 < risk.mean.value < float("inf")
    assert plan.mean_remaining == pytest.approx(risk.mean.value, rel=1e-9)
    # the 0.0058 Chaos of the Orb of Transmutation is far below the cost scale: the coarse grid (ticket #190) resolves p50 and p90
    assert not unresolved(risk, risk.p50) and not unresolved(risk, risk.p90)
    assert risk.grid.step > 0.0058 and not risk.grid.exact
    assert risk.p50.low <= risk.p50.value <= risk.p50.high < risk.p90.low
    assert 10_000 < risk.p90.low <= risk.p90.high < 20_000
    assert risk.p90.high - risk.p90.low < 0.05 * risk.p90.value
    assert math.isfinite(risk.cvar.value) and risk.cvar.value > risk.p90.low  # the mean of the worst tenth is above p90
    assert risk.cvar.high - risk.cvar.low < 0.5 * risk.cvar.value  # the lower end is a tail mean, not just the quantile


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
    assert totals["quantiles_resolved"] is True and 10_000 < totals["p90"]["value"] < 20_000
    simulated = document["verification"]["simulated_p90"]
    assert simulated["value"] > document["verification"]["simulated_mean_cost"]["value"]  # simulated, not certified
    assert document["verification"]["agrees"] is True
    assert document["given_route"]["gaps"] == []
    assert totals["mean_cost"]["value"] <= document["given_route"]["mean_cost"]["value"] * (1 + 1e-9)
    assert document["states"]
    text = capsys.readouterr().out
    assert "not resolved on the grid" not in text and "simulated, not certified" in text
