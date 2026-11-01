"""`--verify` of an approximate answer (ticket #128, ADR-0023) on the committed fixture of `coarse_support.py`.

The lifted policy (concrete item -> compress -> block -> policy table -> step) is run with a fixed seed. The
simulated mean must meet the certified interval, a bound that is moved by 40% must be caught, and nothing the
text or the JSON shows for a p90 or a CVaR may look certified. The runs are few (thousands) and no time is asserted.
"""

import dataclasses
import datetime
import json

import pytest
from cli_support import read_json
from coarse_support import COLD, DATA, MANA
from test_cli_approximate import OFFERS, PRICES, RATES, TARGET, candidate, priced

from crafting_system.abstraction import Coarsening
from crafting_system.cli import _main, build_report, main, make_plan, policy_document, render_text, verify
from crafting_system.cli._approx import climb
from crafting_system.cli._decide import Decision
from crafting_system.cli._lift import lift
from crafting_system.cli._marking import SIMULATED
from crafting_system.cli._verify import CVAR_LEVEL
from crafting_system.simulator import Step, simulate
from crafting_system.targets import parse_target

RUNS = 3_000


@pytest.fixture(scope="module")
def target():
    return parse_target(TARGET, DATA, source="t.yaml")


@pytest.fixture(scope="module")
def exact(target):
    return make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0)


@pytest.fixture(scope="module")
def budget(exact):
    forecast = exact.abstraction.estimate([exact.start], [offer.action for offer in OFFERS])
    pooling = Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    return (forecast.seconds(1.0, 1.0) + forecast.coarsened(pooling).seconds(1.0, 1.0)) / 2


@pytest.fixture(scope="module")
def approximate(target, budget):
    return make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0, budget=budget, rates=RATES)


@pytest.fixture(scope="module")
def check(approximate):
    return verify(DATA, approximate, runs=RUNS, seed=7)


def moved(plan, factor):
    """The plan with both certified bounds scaled (a test double of a wrong solver)."""
    found = plan.approximation
    return dataclasses.replace(plan, approximation=dataclasses.replace(found, lower=found.lower * factor, upper=found.upper * factor))


def steps_of(plan):
    return {
        block: Step(plan.offer_of(action).offer.action, plan.offer_of(action).cost) for block, action in plan.policy.items()
    }


# --- the verdict ------------------------------------------------------------------------------------------------


def test_the_simulated_mean_meets_the_certified_interval(approximate, check):
    found = approximate.approximation
    shift = approximate.start_price.chaos
    cost = check.report.cost

    assert check.bounds == (found.lower + shift, found.upper + shift)
    assert cost.value - 5 * cost.standard_error <= found.upper + shift
    assert cost.value + 5 * cost.standard_error >= found.lower + shift
    assert check.agrees and check.reason == ""
    assert check.report.successes == RUNS and check.report.unfinished == 0 and check.report.stopped == 0
    assert check.computed_p90 is None


@pytest.mark.parametrize(("factor", "side"), [(1.4, "below"), (0.6, "above")])
def test_a_bound_moved_by_40_percent_is_caught(approximate, factor, side):
    wrong = verify(DATA, moved(approximate, factor), runs=RUNS, seed=7)

    assert not wrong.agrees
    assert f"lies {side} the certified interval" in wrong.reason and "standard errors" in wrong.reason
    assert wrong.bounds[0] <= wrong.bounds[1]


def test_the_detectable_error_is_read_against_the_middle_of_the_bounds(approximate, check):
    middle = sum(check.bounds) / 2

    assert check.detectable_error == pytest.approx(5 * check.report.cost.standard_error / middle)
    assert 0 < check.detectable_error < 0.2


def test_the_same_seed_gives_the_same_report_twice(approximate, check):
    again = verify(DATA, approximate, runs=RUNS, seed=7)

    assert again.report == check.report and again.agrees == check.agrees


def test_the_cvar_is_that_of_the_report_at_the_level_of_risk_evaluate(check):
    assert CVAR_LEVEL == 0.9
    assert check.cvar == check.report.cvar(0.9)
    assert check.cvar.value >= check.p90.value and check.cvar.low <= check.cvar.value <= check.cvar.high


# --- the command ------------------------------------------------------------------------------------------------


@pytest.fixture
def command(tmp_path, monkeypatch):
    """The command on the fixture amulet; the plan is made with the fixture's offers and rates."""
    path = tmp_path / "amulet.yaml"
    path.write_text(TARGET, encoding="utf-8")
    real = _main.plan_with_starts
    monkeypatch.setattr(_main, "plan_with_starts", lambda *a, **k: real(*a, **{**k, "offers": OFFERS, "rates": RATES}))
    monkeypatch.setattr(_main, "write_route_page", lambda path, *a, **k: path)

    def run(*arguments):
        out = tmp_path / "policy.json"
        code = main([str(path), "--json", str(out), "--start-price", "0", *arguments], data=DATA, prices=PRICES, env={}, today=datetime.date(2026, 10, 31))
        return code, out

    return run


def test_the_text_shows_no_p90_or_cvar_that_looks_certified(command, budget, capsys):
    code, _ = command("--budget", str(budget), "--verify", "--runs", "1500", "--seed", "7")

    text = capsys.readouterr().out
    assert code == 0
    assert "Verification by simulation, not certified (1,500 runs, seed 7" in text
    assert "simulated p90" in text and "simulated CVaR 90%" in text
    assert "AGREES: the simulated mean is consistent with the certified interval" in text
    assert "AGREES with the computed mean" not in text and "computed p90" not in text
    for line in text.splitlines():
        if line.startswith("JSON policy written to"):
            continue  # a path that holds the test's name
        if "p90" in line or "CVaR" in line:
            if line.strip().startswith("success, p50, p90, CVaR  not given for an approximate answer"):
                continue
            assert "simulated" in line and "not certified" in line, line
    assert text.isascii()


def test_the_json_labels_the_verification_and_has_no_certified_p90(command, budget):
    code, out = command("--budget", str(budget), "--verify", "--runs", "1500", "--seed", "7")

    document = read_json(out)
    block = document["verification"]
    assert code == 0 and document["answer"]["approximate"] is True and document["answer"]["within_tolerance"] is True
    assert block["label"] == SIMULATED == "simulated, not certified"
    assert block["runs"] == 1500 and block["seed"] == 7 and block["agrees"] is True and block["reason"] == ""
    for key in ("simulated_mean_cost", "simulated_p90", "simulated_cvar"):
        assert set(block[key]) >= {"value", "standard_error", "low", "high"}
    assert block["simulated_cvar"]["level"] == 0.9
    assert block["certified_interval"] == {"lower": document["answer"]["lower"], "upper": document["answer"]["upper"]}
    assert "computed_p90" not in block and "computed_mean_cost" not in block
    assert block["unfinished"] == 0 and block["stopped"] == 0 and block["detectable_relative_error"] > 0


def test_the_document_is_strict_json(approximate, check):
    document = policy_document(build_report(approximate, DATA), check, target_name="amulet.yaml")

    json.dumps(document, allow_nan=False)
    assert document["answer"] == policy_document(build_report(approximate, DATA))["answer"]  # the marking is the same with and without
    assert render_text(build_report(approximate, DATA), check).count(SIMULATED) == 3  # the mean, the p90 and the CVaR


def test_the_command_exits_with_2_when_a_bound_is_wrong(command, budget, monkeypatch, capsys):
    real = _main.verify
    monkeypatch.setattr(_main, "verify", lambda data, plan, **fields: real(data, moved(plan, 1.4), **fields))

    code, out = command("--budget", str(budget), "--verify", "--runs", "1500", "--seed", "7")

    assert code == 2
    assert "DOES NOT AGREE: the simulated mean" in capsys.readouterr().out
    assert read_json(out)["verification"]["agrees"] is False


# --- the lift ---------------------------------------------------------------------------------------------------


def test_the_start_item_goes_to_the_step_of_the_start_block(approximate, target):
    steps = steps_of(approximate)

    assert lift(approximate, steps)(target.start_item) is steps[approximate.start]


def test_an_item_whose_block_is_not_in_the_table_gets_no_step(approximate, target):
    steps = steps_of(approximate)
    del steps[approximate.start]

    assert lift(approximate, steps)(target.start_item) is None
    assert lift(approximate, {})(target.start_item) is None


def test_an_exact_state_in_the_table_is_found_before_its_block(approximate, target):
    state = approximate.abstraction.compress(target.start_item)
    block = approximate.approximation.coarsening.coarsen(state)
    assert state != block  # the start item holds a pooled family, so the two keys differ
    steps = steps_of(approximate)
    exact_step = Step(OFFERS[0].action, 99.0)

    assert lift(approximate, {**steps, state: exact_step})(target.start_item) is exact_step
    assert lift(approximate, steps)(target.start_item) is steps[block]


def test_every_item_a_run_reaches_has_its_block_in_the_policy(approximate, target):
    steps = steps_of(approximate)
    policy = lift(approximate, steps)
    coarsen = approximate.approximation.coarsening.coarsen
    seen = set()

    def watching(item):
        seen.add(coarsen(approximate.abstraction.compress(item)))
        return policy(item)

    report = simulate(
        DATA, watching, target.start_item, target.is_met_by,
        runs=300, seed=3, start_cost=0.0, max_steps=2_000,
    )  # fmt: skip

    assert report.stopped == 0 and report.unfinished == 0 and report.successes == 300
    assert seen and seen <= set(approximate.policy)


def test_an_exact_plan_is_lifted_by_the_compressed_state_alone(exact, target):
    steps = {state: Step(OFFERS[0].action, 1.0) for state in exact.policy}

    assert lift(exact, steps)(target.start_item) is steps[exact.start]
    assert lift(exact, {})(target.start_item) is None


def test_a_hand_built_level_that_is_not_on_the_ladder_still_lifts_and_verifies(approximate):
    hand = candidate(approximate, [{MANA, "LightningResistance"}])
    start = approximate.abstraction.compress(approximate.target.start_item)
    solved = climb(Decision("approximate", (hand,), transitions=10), start, priced())
    plan = dataclasses.replace(approximate, solution=solved.solution, start=solved.start, approximation=solved.approximation)
    assert plan.approximation.level == hand.level.name

    assert lift(plan, steps_of(plan))(plan.target.start_item) is not None
    again = verify(DATA, plan, runs=2_000, seed=7)

    assert again.agrees, again.reason
    assert again.report.stopped == 0 and again.report.unfinished == 0


def test_a_level_that_pools_a_blocker_of_the_goal_is_still_inside_its_certified_interval(approximate):
    wide = candidate(approximate, [{COLD, MANA}])
    start = approximate.abstraction.compress(approximate.target.start_item)
    solved = climb(Decision("approximate", (wide,), transitions=10), start, priced())
    plan = dataclasses.replace(approximate, solution=solved.solution, start=solved.start, approximation=solved.approximation)

    check = verify(DATA, plan, runs=2_000, seed=7)

    assert not plan.approximation.within_tolerance and plan.approximation.gap > 0.01
    assert check.agrees, check.reason  # the policy of a wide gap still costs no more than its upper bound



def test_a_run_with_no_spread_meets_a_bound_it_equals_up_to_rounding():
    from types import SimpleNamespace

    from crafting_system.cli._verify import _approximate_reason
    from crafting_system.simulator import SampledEstimate

    cost = 0.1 * 3  # 0.30000000000000004
    report = SimpleNamespace(unfinished=0, stopped=0, cost=SampledEstimate(cost, 0.0, cost, cost))

    assert _approximate_reason(report, (0.3, 0.3), 100) == ""
    assert "lies above" in _approximate_reason(report, (0.2, 0.25), 100)
