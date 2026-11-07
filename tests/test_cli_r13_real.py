"""R13 end to end on the real 3.29.3.3 dump, at the committed prices (ticket #66).

R13 is the alt-regal belt of the reference routes: a Magic Leather Belt of item level 86 (a trade price, #576: the guide opens
with "Alt spam for T1 Life and a resist" and names no Transmutation Orb), Orbs of Alteration until it holds tier-1 life and a tier-1 resistance, a Regal
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

import contextlib
import datetime
import io
import math
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import read_json
from limits_support import labels_of, only

from crafting_system.actions import BenchCraft, RemoveCraftedMods
from crafting_system.cli import RESTART, build_report, evaluate_route, load_route, main, make_plan
from crafting_system.cli._report import unresolved
from crafting_system.items import Rarity
from crafting_system.prices import load_price_file
from crafting_system.targets import KOfN, load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGET = ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml"
ROUTE = ROOT / "examples" / "routes" / "r13-life-resist-belt.yaml"
RUNS = 8  # a simulated craft is about 50,000 orb uses and takes 10 s or more here, so --verify gets eight runs
BELT = "Leather Belt, magic, item level 86-100"
BELT_PRICE = 15.234  # the trade API, Allflame, 2026-11-07: the mean of the 5 cheapest instant-buyout listings of a magic Leather Belt of item level 86 or more, 28 on the site
ORBS_OF_THE_GUIDE = {"Orb of Alteration", "Regal Orb"}


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


def test_the_start_belt_is_a_magic_belt_that_costs_its_trade_price(plan):
    assert plan.start_price.name == BELT
    assert plan.start_price.chaos == pytest.approx(BELT_PRICE)
    assert plan.start_price.source == "trade-api"
    assert plan.target.start_item.rarity is Rarity.MAGIC


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
    kinds_left = labels_of(plan.limits, "kinds-not-named")  # none of it unpriced
    crafts_left = only(plan.limits, "crafts").labels  # a list: two crafts may read alike
    assert "Chaos Orb" in kinds_left and len(crafts_left) > 50  # 81 belt crafts


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
    # The route is read on the packed graph: the same mean as the object read (`test_packed_plan_real.py`), in seconds and not in the 10 minutes the object read
    # of this route takes since the Magic start (#622); the shard has 25 minutes for this file and the command test below already holds one such read.
    packed = make_plan(data, plan.target, load_price_file(PRICES), solver="packed", with_risk=False)
    route = load_route(ROUTE, packed, data)
    result = evaluate_route(packed, route, data)

    assert result.gaps == ()
    assert result.risk.success_probability.value == pytest.approx(1.0)
    assert plan.risk.mean.value <= result.risk.mean.value * (1 + 1e-9)


def test_the_policy_does_not_open_with_a_transmutation_and_none_is_offered(plan, data):
    """#576: the guide opens with "Alt spam for T1 Life and a resist" on a Magic belt; a Transmutation Orb it never names is not a step of the plan."""
    report = build_report(plan, data)

    first = next(state for state in report.states if report.ids[plan.start] == state.id)
    assert first.action in {"Orb of Alteration", "Orb of Augmentation"}  # the bought belt is Magic with no mod: the cheapest way on is an Augmentation, the Alterations follow
    assert "Orb of Transmutation" not in {priced.label for priced in plan.offers}
    assert "Orb of Transmutation" not in {state.action for state in report.states}


@pytest.fixture(scope="module")
def command(tmp_path_factory, data):
    """(exit code, JSON document, printed text) of the CLI on R13 with `--verify` and the guide's route: one run, shared by the tests below."""
    out = tmp_path_factory.mktemp("r13") / "policy.json"
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        code = main(
            [str(TARGET), "--json", str(out), "--verify", "--runs", str(RUNS), "--route", str(ROUTE)],
            data=data,
            prices=load_price_file(PRICES),
            env={},
            today=datetime.date(2026, 11, 1),
        )
    return code, read_json(out), printed.getvalue()


def test_the_command_returns_the_policy_and_verify_agrees(command):
    code, document, text = command

    assert code == 0
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
    assert "simulated, not certified" in text


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#622: since the Magic start of #576 (PR #607) the object risk read of R13's given route leaves its percentiles unresolved (about 480 s, then 'not computed'); it fails loudly the day #622 is fixed, delete this mark then",
)
def test_the_given_routes_percentiles_are_resolved_in_the_printed_report(command):
    _, _, text = command

    assert "far above its cheapest step" not in text
