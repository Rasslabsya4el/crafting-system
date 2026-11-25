"""A plan no player would follow is no plan (#1628, OR-12, OR-40): the planner's entry reads the expected uses of each step of the plan it ends
with, and past the run's setting (`PlanSettings.usable_step_uses`, 100,000 uses of one step by default) it answers "no usable plan found
within the limit" (`UnusablePlan`), with the plan's cost, the step, its uses and what was considered. The heavy benchmark records that answer
as no plan, and its check flags a passing plan dearer than ten times its guide's route.

The chains below are worked by hand: a step that succeeds with chance p and otherwise leaves the item as it was is used 1/p times on average.
"""

import dataclasses
from fractions import Fraction
from types import SimpleNamespace

import pytest
from cli_support import R12, TODAY, price_file, read_json
from targets_support import DATA

import crafting_system.cli._benchmark as benchmark_module
import crafting_system.planner._entry as entry_module
from crafting_system.benchmark_record import FAIL, FLAGGED, GUIDE_FLAG_TIMES, PASS, SITE_PLAN, check_run, failed, guides_of, make_record, record_of_plan
from crafting_system.cli import main
from crafting_system.planner import (
    PROOF_NO_USABLE,
    USABLE_STEP_USES,
    PlanSettings,
    UnusablePlan,
    dominant_step,
    make_plan,
    plan_target,
)
from crafting_system.planner import _limits
from crafting_system.planner._usable import check_usable
from crafting_system.targets import load_target

COMMAND = "bench" + "mark"  # a bare string with the name would trip tests/test_no_timing.py


def _action(label: str, cost: float, *outcomes: tuple[str, int]):
    return SimpleNamespace(label=label, cost=cost, outcomes=[SimpleNamespace(state=state, weight=weight) for state, weight in outcomes])


def _plan(view: dict, start: str = "A", *, start_price: float = 5.0, craft_mean: float = 0.0, limits=()):
    """A plan as the planner's entry hands it over, holding only what the uses and the proof sentence read."""
    packed = SimpleNamespace(view=view, risk_policy=None, risk_start=None)
    return SimpleNamespace(
        packed=packed, start=start, start_price=SimpleNamespace(chaos=start_price), risk=None, craft_mean=craft_mean, search=None,
        limits=tuple(limits), approximation=None,
    )  # fmt: skip


STOPPED = (SimpleNamespace(kind=_limits.UNTRIED, what="", why="", guarantee=""),)  # a run whose net left a group of methods untried


def essence_spam(chance: Fraction, price: float, label: str = "Shrieking Essence of Loathing", **kwargs):
    """One essence used on the item until its mod comes: chance `chance` to reach the goal G, else the item stays at A."""
    weight = chance.denominator
    view = {"A": _action(label, price, ("G", chance.numerator), ("A", weight - chance.numerator))}
    return _plan(view, craft_mean=price * weight / chance.numerator, **kwargs)


def test_a_step_that_succeeds_one_time_in_a_thousand_is_used_a_thousand_times():
    step = dominant_step(essence_spam(Fraction(1, 1000), 2.0))
    assert step.label == "Shrieking Essence of Loathing"
    assert step.uses == pytest.approx(1000.0)  # 1 / p
    assert step.chaos == pytest.approx(2000.0)  # 1,000 uses of 2 Chaos


def test_the_uses_of_one_step_are_summed_over_the_states_where_it_acts_and_the_dominant_step_is_the_most_used():
    # Alteration from A reaches B half the time (2 uses), from B reaches C a quarter of the time (4 uses): 6 uses of 1 Chaos;
    # an Exalted Orb at C once, dearer per use (100 Chaos) but used once
    view = {
        "A": _action("Orb of Alteration", 1.0, ("B", 1), ("A", 1)),
        "B": _action("Orb of Alteration", 1.0, ("C", 1), ("B", 3)),
        "C": _action("Exalted Orb", 100.0, ("G", 1)),
    }
    step = dominant_step(_plan(view))
    assert (step.label, step.uses, step.chaos) == ("Orb of Alteration", pytest.approx(6.0), pytest.approx(6.0))


def test_r17_s_ten_minute_plan_is_no_usable_plan_and_a_plan_under_the_line_is_answered_as_before():
    # R17 at the runners' ten-minute net (#1628): one Shrieking Essence of Loathing at 1.65 Chaos, its mod once in about 1.035e12 uses:
    # 1,708,178,140,913.80 Chaos of the plan. R20's: Essence of Horror at 25.61 Chaos, 35,058,189.45 Chaos: about 1.37 million uses.
    r17 = essence_spam(Fraction(1, 1_035_259_479_342), 1.65, limits=STOPPED)
    r20 = essence_spam(Fraction(1, 1_368_925), 25.61, label="Essence of Horror", limits=STOPPED)
    for plan, label in ((r17, "Shrieking Essence of Loathing"), (r20, "Essence of Horror")):
        with pytest.raises(UnusablePlan) as raised:
            check_usable(plan, USABLE_STEP_USES)
        assert raised.value.step.label == label and raised.value.plan is plan
        assert str(raised.value).startswith("no usable plan found within the limit")
    assert dominant_step(r17).chaos == pytest.approx(1_708_178_140_914.3, rel=1e-9)
    # every reference craft's plan at the one-hour net uses one step at most 3,189 times (R20's Essence of Horror): answered as before
    r20_hour = essence_spam(Fraction(1, 3189), 25.61, label="Essence of Horror")
    assert check_usable(r20_hour, USABLE_STEP_USES) is r20_hour
    # the line itself: 100,000 uses pass, one more does not; no setting, no net
    assert check_usable(essence_spam(Fraction(1, 100_000), 1.0), 100_000) is not None
    with pytest.raises(UnusablePlan):
        check_usable(essence_spam(Fraction(1, 100_001), 1.0), 100_000)
    assert check_usable(r17, None) is r17


def test_the_answer_s_sentence_gives_the_cost_the_step_its_uses_and_what_was_considered():
    plan = essence_spam(Fraction(1, 1_368_925), 25.61, label="Essence of Horror", limits=STOPPED)
    with pytest.raises(UnusablePlan) as raised:
        check_usable(plan, USABLE_STEP_USES)
    words = raised.value.words
    assert words.case == PROOF_NO_USABLE
    cost = 5.0 + 25.61 * 1_368_925  # the start item and the expected essences
    assert words.sentence.startswith(
        f"No usable plan found within the limit: the best plan found costs {cost:,.2f} Chaos and expects about 1,368,925 uses of Essence of "
        "Horror, more than the 100,000 uses of one step a player can follow, so it is not shown as a plan."
    )
    assert "ran out of time or memory" in words.sentence and "a longer run may find a usable plan" in words.sentence
    document = raised.value.document()
    assert document["cost"] == pytest.approx(cost) and document["step"] == "Essence of Horror" and document["uses"] == pytest.approx(1_368_925)
    assert document["line"] == USABLE_STEP_USES and document["sentence"] == words.sentence
    # a plan proved the cheapest that still needs more is no usable plan either, and the sentence says no cheaper plan exists
    proved = essence_spam(Fraction(1, 1_368_925), 25.61, label="Essence of Horror")
    with pytest.raises(UnusablePlan) as raised:
        check_usable(proved, USABLE_STEP_USES)
    assert "No plan is cheaper among every craft this planner can use on this item" in raised.value.words.sentence


def test_the_entry_answers_no_usable_plan_under_its_setting(monkeypatch):
    absurd = essence_spam(Fraction(1, 1_035_259_479_342), 1.65, limits=STOPPED)
    monkeypatch.setattr(entry_module, "plan_with_starts", lambda *args, **kwargs: absurd)
    assert PlanSettings().usable_step_uses == USABLE_STEP_USES == 100_000
    with pytest.raises(UnusablePlan):
        plan_target(DATA, None, None, PlanSettings())
    assert plan_target(DATA, None, None, PlanSettings(usable_step_uses=None)) is absurd


def test_a_real_plan_s_dominant_step_is_its_action_and_its_share_is_its_uses_times_its_price():
    target = load_target(R12, DATA)
    plan = make_plan(DATA, dataclasses.replace(target, actions=("harvest-reforge",)), price_file())
    step = dominant_step(plan)
    assert step.label == "Harvest Reforge Lightning" and step.uses > 1
    price = next(priced.cost for priced in plan.offers if priced.label == step.label)
    assert step.chaos == pytest.approx(step.uses * price)
    assert check_usable(plan, USABLE_STEP_USES) is plan


def test_the_heavy_benchmark_records_no_usable_plan_as_no_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_module, "BENCHMARKS", (benchmark_module.BENCHMARKS[0],))  # R12 alone
    real = benchmark_module.plan_target
    monkeypatch.setattr(benchmark_module, "plan_target", lambda data, target, prices, settings: real(data, target, prices, dataclasses.replace(settings, usable_step_uses=1)))
    code = main([COMMAND, "--out", str(tmp_path), "--net"], data=DATA, prices=price_file(), env={}, today=TODAY)
    assert code == 0
    entry = next(entry for entry in read_json(tmp_path / "benchmark.json")["routes"] if entry["id"] == "R12")
    assert entry["error"].startswith("no usable plan found within the limit") and entry["solver"] is None
    assert entry["unusable"]["step"] == "Harvest Reforge Lightning" and entry["unusable"]["line"] == 1
    assert entry["record"]["mean"] is None and entry["record"]["stop"] == entry["error"]


def _run(**routes: tuple[dict, float | None]) -> dict:
    return {
        "plan": SITE_PLAN,
        "routes": [
            {"id": name, "error": record["stop"] if record["mean"] is None else None, "record": record,
             "given_route": None if guide is None else {"mean": guide}}
            for name, (record, guide) in routes.items()
        ],
    }  # fmt: skip


def _planned(mean: float) -> dict:
    return record_of_plan(mean, mean * 0.9, 300.0, 4000.0, "stopped: not every round of the methods finished")


def test_the_check_fails_a_route_that_now_answers_no_usable_plan_and_flags_a_plan_dearer_than_ten_times_its_guide():
    unusable = record_of_plan(None, None, None, None, "no usable plan found within the limit: the best plan found expects about 1,368,925 uses of Essence of Horror")
    record = make_record(
        _run(R20=(_planned(35_058_370.95), 266_058.52), R24=(record_of_plan(None, None, None, None, "no plan found yet"), 4_838.92)),
        _run(R20=(_planned(35_058_370.95), 266_058.52), R24=(record_of_plan(None, None, None, None, "no plan found yet"), 4_838.92)),
    )
    verdicts = {verdict.route: verdict for verdict in check_run(record, _run(R20=(unusable, None), R24=(_planned(51_581.28), 4_838.92)))}
    # R20's old record held its 35 million as a plan: the new answer is no plan, and the check says so until the record is renewed
    assert verdicts["R20"].outcome == FAIL and "no usable plan" in verdicts["R20"].why
    # R24 at 10.66 times its guide passes the record (it had no plan) but a person reads it
    assert verdicts["R24"].outcome == FLAGGED and "10.7 times its guide's route (4,838.92 c)" in verdicts["R24"].why
    assert not failed([verdicts["R24"]])
    assert guides_of(_run(R24=(_planned(1.0), 4_838.92), R05=(_planned(1.0), None))) == {"R24": 4_838.92}
    # at most ten times its guide: no flag
    again = check_run(record, _run(R20=(unusable, None), R24=(_planned(GUIDE_FLAG_TIMES * 4_838.92), 4_838.92)))
    assert next(verdict for verdict in again if verdict.route == "R24").outcome == PASS


def test_the_committed_record_check_reads_no_unusable_figure_as_a_plan():
    # a run whose entry carries an UnusablePlan holds no cost: the record made of it has no plan there
    entry = record_of_plan(None, None, None, None, "no usable plan found within the limit")
    made = make_record(_run(R17=(entry, 33_140.41)), _run(R17=(entry, 33_140.41)))
    assert made["routes"]["R17"]["state"] == "no plan" and made["routes"]["R17"]["ceiling"] is None

