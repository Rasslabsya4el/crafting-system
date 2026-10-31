"""An approximate answer end to end (ticket #127, ADR-0023) on the committed fixture of `coarse_support.py`.

The plan is made twice: exactly, and with a budget that the exact forecast exceeds and the first coarse level fits (the
rates are injected, so no machine decides). The interval must bracket the exact optimum, the marking must say so in
words and in JSON, and a level that cannot reach 1% must say that instead of rounding the gap down. The golden texts
below are the marking as the owner reads it.
"""

import dataclasses
import json

import pytest
from abstraction_pool import MANA_1
from cli_support import read_json
from coarse_support import CHAOS, COLD, CRAFTS, DATA, FIRE, HYBRID_CRAFT, MANA, REMOVE

from crafting_system.abstraction import Coarsening
from crafting_system.cli import Offer, PlanError, build_report, main, make_plan, policy_document, render_text
from crafting_system.cli import _main
from crafting_system.cli._approx import Approximation, climb
from crafting_system.cli._decide import LADDER, Candidate, Decision, Level, Rates
from crafting_system.cli._marking import marking_document, marking_lines
from crafting_system.cli._offers import PricedOffer
from crafting_system.prices import PriceFile
from crafting_system.targets import parse_target

import datetime

CH = "Chaos Orb"
TARGET = f"""\
base: Paua Amulet
item_level: 84
requirements:
  - family: ColdResistance
    mod: {HYBRID_CRAFT}
  - family: IncreasedLife
start_item:
  rarity: rare
  mods:
    - mod: {MANA_1}
      tier: 1
      values: {[min(stat.min, stat.max) for stat in DATA.mods[MANA_1].stats]}
"""
OFFERS = [
    Offer("Chaos Orb", CHAOS, {CH: 1}),
    *(Offer(f"Craft {craft.mod_id}", craft, {CH: 2}) for craft in CRAFTS),
    Offer("Remove Crafted Mods", REMOVE, {CH: 1}),
]
PRICES = PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {})
RATES = Rates(1.0, 1.0)


@pytest.fixture(scope="module")
def target():
    return parse_target(TARGET, DATA, source="t.yaml")


@pytest.fixture(scope="module")
def exact(target):
    return make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0)


@pytest.fixture(scope="module")
def budget(exact):
    """Between the forecast of the first coarse level and the exact one, at rates of 1 second a unit."""
    forecast = exact.abstraction.estimate([exact.start], [offer.action for offer in OFFERS])
    pooling = Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    return (forecast.seconds(1.0, 1.0) + forecast.coarsened(pooling).seconds(1.0, 1.0)) / 2


@pytest.fixture(scope="module")
def approximate(target, budget):
    return make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0, budget=budget, rates=RATES)


def priced():
    return tuple(PricedOffer(offer, float(sum(offer.resources.values())), ()) for offer in OFFERS)


# --- the answer -------------------------------------------------------------------------------------------------


def test_a_query_over_the_budget_is_answered_by_the_first_coarse_level_with_an_interval_around_the_exact_mean(exact, approximate):
    found = approximate.approximation

    assert found is not None and found.level == LADDER[0].name
    assert found.lower <= exact.mean_remaining <= found.upper
    assert found.gap <= found.tolerance == 0.01 and found.within_tolerance and found.message == ""
    assert approximate.mean_remaining == found.upper  # the policy shown costs the upper bound
    assert approximate.risk is None and approximate.risk_seconds == 0.0
    assert found.blocks < len(exact.solution.values)


def test_the_policy_is_a_policy_of_blocks_that_starts_at_the_start_block(approximate):
    start = approximate.start

    assert start == approximate.approximation.coarsening.coarsen(start)
    assert start in approximate.policy
    assert not approximate.is_goal(start)


def test_the_same_query_inside_the_budget_is_exact_and_unmarked(target, exact):
    plan = make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0, budget=1e12, rates=RATES)

    assert plan.approximation is None and plan.risk is not None and plan.note == ""
    assert plan.mean_remaining == exact.mean_remaining
    assert marking_lines(plan.approximation, 0.0, 300.0) == []


def test_an_exact_answer_has_the_same_text_as_before_and_an_unmarked_json(exact):
    report = build_report(exact, DATA)

    text = render_text(report)
    document = policy_document(report)

    assert "approximate" not in text.lower() and "Answer:" not in text
    assert document["answer"] == {"approximate": False} and document["note"] == ""
    assert document["totals"]["p90"]["value"] is not None


def test_the_text_marks_the_answer_and_gives_no_risk_numbers(approximate):
    text = render_text(build_report(approximate, DATA))
    head, _, tail = text.partition("\nRequirements:")

    assert head.startswith("Answer: approximate (certified within ")
    assert " of the exact mean)" in head and "Level: family groups, all irrelevant families in one group;" in head
    assert "Blocks solved: " in text
    assert "  success, p50, p90, CVaR  not given for an approximate answer" in text
    assert "p90   " not in text and "success chance" not in text
    assert "Run time: both solvers" in text


def test_the_json_marks_the_answer_and_holds_the_interval(approximate, exact):
    document = policy_document(build_report(approximate, DATA))

    answer = document["answer"]
    assert answer["approximate"] is True and answer["level"] == LADDER[0].name
    assert answer["lower"] <= exact.mean_remaining <= answer["upper"]
    assert answer["gap"] == approximate.approximation.gap <= 0.01
    assert answer["within_tolerance"] is True and answer["tolerance"] == 0.01 and answer["blocks"] > 0
    assert set(document["totals"]) == {"mean_cost", "mean_cost_divine", "mean_cost_without_start", "solver_error_bound"}
    assert document["totals"]["mean_cost"]["high"] == answer["upper"] and document["totals"]["mean_cost"]["low"] == answer["lower"]
    assert document["timings_seconds"]["risk_evaluate"] is None
    json.dumps(document, allow_nan=False)  # strict JSON: no infinity, no NaN


# --- the ladder and the message when no level reaches 1% ---------------------------------------------------------


def candidate(approximate, groups) -> Candidate:
    return Candidate(Level("groups", None, f"groups {sorted(map(sorted, groups))}"), None, Coarsening(approximate.abstraction, groups))


def climbed(approximate, *candidates, transitions=6213):
    decision = Decision("approximate", tuple(candidates), predicted=900.0, transitions=transitions)
    return climb(decision, approximate.start if False else approximate.abstraction.compress(approximate.target.start_item), priced())


def test_pooling_a_blocker_of_the_goal_craft_gives_a_gap_above_one_percent_and_the_message_says_it(approximate, exact):
    bad = candidate(approximate, [{COLD, MANA}])

    solved = climbed(approximate, bad)

    found = solved.approximation
    assert found.gap > 0.01 and not found.within_tolerance
    assert found.lower <= exact.mean_remaining <= found.upper  # still certified
    assert found.message.startswith(f"No level reaches 1%: the narrowest certified interval has a gap of {found.gap:.2%} ")
    assert "run again with --exact (6,213 transitions, predicted at about 15 min)" in found.message


def test_the_message_is_not_rounded_down_in_the_headline(approximate):
    found = climbed(approximate, candidate(approximate, [{COLD, MANA}])).approximation

    headline = marking_lines(found, 0.0, 300.0)[0]

    shown = float(headline.split("gap is ")[1].split("%")[0])
    assert headline.startswith("Answer: approximate (the certified gap is ") and "above the 1% tolerance" in headline
    assert shown >= found.gap * 100 - 1e-9


def test_a_gap_over_the_largest_exact_size_says_the_exact_run_is_not_offered(approximate):
    found = climbed(approximate, candidate(approximate, [{COLD, MANA}]), transitions=22_994_524).approximation

    assert "not offered" in found.message and "22,994,524 transitions" in found.message and "--exact" not in found.message


def tail(coarse: Candidate, theta: float) -> Candidate:
    level = Level("tail", None, f"tail cut at theta {theta:g} over {coarse.level.name}", theta)
    return Candidate(level, None, coarse.coarsening)


def test_the_ladder_goes_on_to_the_tail_cut_when_the_coarse_level_misses_the_tolerance(approximate, exact):
    bad = candidate(approximate, [{COLD, MANA}])
    start = approximate.abstraction.compress(approximate.target.start_item)

    coarse = climbed(approximate, bad).approximation
    solved = climbed(approximate, bad, tail(bad, 0.0))

    found = solved.approximation
    assert coarse.gap > 0.01 and found.level == f"tail cut at theta 0 over {bad.level.name}"
    assert found.expanded > 0 and found.gap < coarse.gap  # the cut narrows what the coarse level left
    assert found.lower >= coarse.lower and found.upper <= coarse.upper
    assert found.lower <= exact.mean_remaining <= found.upper  # still certified
    assert solved.start == start and solved.start in solved.solution.policy  # the policy starts at the exact start item
    assert solved.solution.values[start] == found.upper
    assert found.message.startswith("No level reaches 1%")  # this one is still above it, and says so


def test_the_tail_cut_policy_can_be_walked_from_the_start_through_expanded_states_and_blocks(approximate):
    bad = candidate(approximate, [{COLD, MANA}])
    start = approximate.abstraction.compress(approximate.target.start_item)
    solved = climbed(approximate, bad, tail(bad, 0.0))
    policy = solved.solution.policy

    seen, queue = {start}, [start]
    while queue:
        state = queue.pop()
        if approximate.abstraction.is_goal(state):
            continue
        assert state in policy, "every state reached has an action: an expanded one, or the coarse policy of its block"
        for outcome in policy[state].outcomes:
            if outcome.state not in seen:
                seen.add(outcome.state)
                queue.append(outcome.state)

    assert len(seen) > 1


def test_a_tail_cut_that_expands_nothing_is_the_coarse_level(approximate):
    bad = candidate(approximate, [{COLD, MANA}])

    found = climbed(approximate, bad, tail(bad, float("inf"))).approximation

    assert found.expanded == 0 and found.gap == climbed(approximate, bad).approximation.gap


def test_a_tail_cut_over_a_coarse_level_with_no_policy_is_skipped_not_an_error(approximate):
    wide = candidate(approximate, [{COLD, MANA}, {FIRE, "LightningResistance"}])  # the pessimistic model cannot reach the goal
    good = candidate(approximate, [{MANA, "LightningResistance"}])

    solved = climbed(approximate, tail(wide, 0.0), good)

    assert solved.approximation.level == good.level.name


def test_the_ladder_stops_at_the_first_level_within_the_tolerance(approximate):
    bad, good = candidate(approximate, [{COLD, MANA}]), candidate(approximate, [{MANA, "LightningResistance"}])
    never = Candidate(Level("groups", None, "never tried"), None, None)

    solved = climbed(approximate, bad, good, never)

    assert solved.approximation.within_tolerance and solved.approximation.level == good.level.name


def test_with_no_level_within_the_tolerance_the_narrowest_interval_is_kept(approximate):
    wide = candidate(approximate, [{COLD, MANA}])
    wider = candidate(approximate, [{COLD, FIRE, MANA}])

    one, two = climbed(approximate, wide).approximation, climbed(approximate, wider).approximation
    both = climbed(approximate, wider, wide).approximation

    assert two.gap > one.gap > 0.01
    assert both.gap == one.gap and both.level == wide.level.name


def test_a_ladder_with_no_policy_at_any_level_is_an_error(approximate, target):
    nothing = [Offer("Remove Crafted Mods", REMOVE, {CH: 1})]  # cannot reach the goal
    start = approximate.abstraction.compress(target.start_item)
    decision = Decision("approximate", (candidate(approximate, [{MANA, "LightningResistance"}]),), transitions=10)

    with pytest.raises(ValueError, match="no coarse level has a policy"):
        climb(decision, start, tuple(PricedOffer(offer, 1.0, ()) for offer in nothing))


# --- the marking in words and in JSON ---------------------------------------------------------------------------


def hand(lower, upper, level, blocks, message="", gap=None) -> Approximation:
    return Approximation(lower, upper, upper / lower - 1 if gap is None else gap, level, blocks, 0.01, None, message)


def test_golden_text_of_a_marking_within_the_tolerance():
    found = hand(1234.5, 1239.1, "family groups of 8", 1582)

    assert marking_lines(found, 10.0, 200.0) == [
        "Answer: approximate (certified within 0.38% of the exact mean)",
        "  The exact mean cost, the start item included, is between 1,244.50 and 1,249.10 Chaos",
        "  (6.22 to 6.25 Divine); the policy below costs no more than the upper figure.",
        "  Level: family groups of 8; 1,582 blocks solved.",
    ]


def test_golden_text_of_a_marking_above_the_tolerance():
    found = hand(100.0, 103.0, "family groups of 4", 4295, gap=0.03, message="No level reaches 1%: the narrowest certified interval has a gap of 3.00% (level: family groups of 4).")

    assert marking_lines(found, 0.0, 200.0) == [
        "Answer: approximate (the certified gap is 3.00%, above the 1% tolerance)",
        "  The exact mean cost, the start item included, is between 100.00 and 103.00 Chaos",
        "  (0.5 to 0.515 Divine); the policy below costs no more than the upper figure.",
        "  Level: family groups of 4; 4,295 blocks solved.",
        "  No level reaches 1%: the narrowest certified interval has a gap of 3.00% (level: family groups of 4).",
    ]


def test_golden_text_of_a_gap_too_small_to_print_is_rounded_up_never_to_zero():
    found = hand(8.282194804552427, 8.282194805480033, "family groups, all irrelevant families in one group", 67)

    assert marking_lines(found, 0.0, 300.0)[0] == "Answer: approximate (certified within 0.0001% of the exact mean)"


def test_golden_text_of_a_tail_cut_says_how_many_exact_states_it_expanded():
    found = dataclasses.replace(hand(100.0, 100.5, "tail cut at theta 0.01 over family groups of 4", 4400), expanded=105)

    assert marking_lines(found, 0.0, 200.0)[3] == (
        "  Level: tail cut at theta 0.01 over family groups of 4; 4,400 blocks solved, 105 of them exact states expanded by the tail cut."
    )
    assert marking_document(found, 0.0)["expanded"] == 105


def test_golden_json_of_the_marking():
    found = hand(1234.5, 1239.1, "family groups of 8", 1582)

    assert marking_document(found, 10.0) == {
        "approximate": True,
        "lower": 1244.5,
        "upper": 1249.1,
        "gap": 1239.1 / 1234.5 - 1,
        "level": "family groups of 8",
        "blocks": 1582,
        "expanded": 0,
        "tolerance": 0.01,
        "within_tolerance": True,
        "message": "",
    }
    assert marking_document(None, 10.0) == {"approximate": False}


def test_an_infinite_bound_is_null_in_json_and_never_in_text():
    found = Approximation(5.0, float("inf"), float("inf"), "x", 3, 0.01, None)

    document = marking_document(found, 0.0)

    assert document["upper"] is None and document["gap"] is None and document["within_tolerance"] is False
    assert "never" in marking_lines(found, 0.0, 300.0)[1] and "unbounded" in marking_lines(found, 0.0, 300.0)[0]


# --- the command ------------------------------------------------------------------------------------------------------


@pytest.fixture
def command(tmp_path, monkeypatch, budget):
    """The command on the fixture amulet; the plan is made with the fixture's offers and rates (the catalog would offer other crafts)."""
    path = tmp_path / "amulet.yaml"
    path.write_text(TARGET, encoding="utf-8")
    real = _main.make_plan
    monkeypatch.setattr(_main, "make_plan", lambda *a, **k: real(*a, **{**k, "offers": OFFERS, "rates": RATES}))
    monkeypatch.setattr(_main, "write_route_page", lambda path, *a, **k: path)  # the route card needs mods that the fixture pool lacks

    def run(*arguments):
        out = tmp_path / "policy.json"
        code = main([str(path), "--json", str(out), "--start-price", "0", *arguments], data=DATA, prices=PRICES, env={}, today=datetime.date(2026, 10, 31))
        return code, out

    return run


def test_the_command_prints_the_marking_and_writes_it_to_the_json(command, budget, capsys):
    code, out = command("--budget", str(budget))

    shown = capsys.readouterr().out
    document = read_json(out)
    assert code == 0
    assert shown.startswith("Target: amulet.yaml\nAnswer: approximate (certified within ")
    assert document["answer"]["approximate"] is True and document["answer"]["within_tolerance"] is True
    assert "Route view not written: it is not built for an approximate answer yet." in shown


def test_exact_forces_the_exact_run_whatever_the_forecast(command, capsys):
    code, out = command("--exact", "--budget", "0")

    assert code == 0 and read_json(out)["answer"] == {"approximate": False}
    assert "Answer:" not in capsys.readouterr().out


def test_verify_and_a_given_route_are_refused_for_an_approximate_answer(command, budget, capsys, tmp_path):
    code, _ = command("--budget", str(budget), "--verify")

    assert code == 1 and "not available for an approximate answer yet" in capsys.readouterr().err


def test_a_query_that_cannot_be_pooled_runs_exactly_and_says_why(tmp_path, capsys):
    from cli_support import price_file, run

    code, out = run(tmp_path, "--budget", "0", prices=price_file())

    text = capsys.readouterr().out
    assert code == 0 and "no approximate level available" in text and "is run as it is" in text
    assert read_json(out)["answer"] == {"approximate": False} and "no approximate level" in read_json(out)["note"]


def test_a_gap_just_above_the_tolerance_never_prints_as_the_tolerance():
    found = hand(100.0, 101.0000000004, "x", 3)

    assert marking_lines(found, 0.0, 300.0)[0] == "Answer: approximate (the certified gap is 1.01%, above the 1% tolerance)"
    assert marking_lines(hand(100.0, 103.0, "x", 3, gap=0.03), 0.0, 300.0)[0].startswith("Answer: approximate (the certified gap is 3.00%")


def test_the_block_count_is_one_number_in_the_text_and_the_json(approximate):
    text = render_text(build_report(approximate, DATA))
    document = policy_document(build_report(approximate, DATA))

    blocks = approximate.approximation.blocks
    assert f"Blocks solved: {blocks:,}" in text and f"{blocks:,} blocks solved." in text
    assert document["answer"]["blocks"] == blocks


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "soon"])
def test_a_budget_that_is_not_a_number_of_seconds_is_refused(command, value, capsys):
    with pytest.raises(SystemExit):
        command("--budget", value)

    assert "argument --budget: " in capsys.readouterr().err
