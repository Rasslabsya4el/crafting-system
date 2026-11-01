"""The report of an answer that reads a rule axis (ticket #221; ADR-0012 amended, 0022, 0028, 0035).

Done when:
* a golden report of the tiny case (text head, JSON and route page);
* the JSON has `approximate_inputs` with the claim ids and reasons (and the spread of the alpha grid and the cost rule);
* an answer with no recombinator says nothing about alpha.

Behind them: the numbers of the block are those of the interval driver and of an independent simulation, the cost rule's ends are what
the claims say, and a plan whose smallest worst case is another route names that route.
"""

import json
import random
from dataclasses import replace
from fractions import Fraction

import pytest
from interval_support import (
    BUY_P,
    GAMBLE,
    GRID,
    RECOMBINE,
    SAFE,
    Tiny,
    gamble_answer,
    tiny_answer,
    toy_report_plan,
)
from items_support import DATA
from route_view_support import assert_golden

from crafting_system.actions.contract import Reading
from crafting_system.actions.recombinator import ALPHA_AXIS
from crafting_system.cli._interval import build_interval_answer
from crafting_system.cli._report import build_report, policy_document, render_text, with_interval
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.risk import has_inputs, solve_readings
from crafting_system.solver import Acquisition

ALPHA = ALPHA_AXIS.name


def rounded(value, digits: int = 8):
    """The document with every float rounded: the last digits of a certified bound are the platform's (the BLAS of the runner), not the report's."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {key: rounded(item, digits) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item, digits) for item in value]
    return value


def head(text: str) -> str:
    """The report up to its requirements: the part that holds the answer, the interval and the approximate inputs (no run times)."""
    return text[: text.index("Requirements:")]


def reading(alpha) -> Reading:
    return Reading.of({ALPHA: Fraction(alpha)})


@pytest.fixture(scope="module")
def tiny():
    answer, result, plan = tiny_answer()
    return answer, result, plan, with_interval(build_report(plan, DATA), answer)


# --- the golden report of the tiny case -----------------------------------------------------------------------------------------


def test_golden_text_head_of_the_tiny_case(tiny):
    _, _, _, report = tiny
    assert_golden("interval_tiny", head(render_text(report)), "txt")


def test_golden_json_interval_of_the_tiny_case(tiny):
    _, _, _, report = tiny
    document = policy_document(report)
    shown = rounded({"interval": document["interval"], "approximate_inputs": document["approximate_inputs"]})
    assert_golden("interval_tiny", json.dumps(shown, indent=2, sort_keys=True) + "\n", "json")


def test_golden_route_page_of_the_tiny_case(tiny):
    _, _, plan, report = tiny
    page = Page("Tiny recombinator case", (build_section(route_input(plan, report.interval), DATA, anchor="policy"),))
    html = render_page(page)
    assert "Without recombinators" in html and "Dust and Gold prices" in html and "Thaumaturgic Dust at 100,000 per Chaos Orb" in html
    assert_golden("interval_tiny", html)


# --- the numbers are the driver's and the claims' ------------------------------------------------------------------------------------


def test_the_block_carries_the_plan_its_interval_over_the_whole_grid_and_the_route_without_recombinators(tiny):
    answer, result, plan, _ = tiny
    shift = plan.start_price.chaos
    assert answer.plan_reading == "alpha = 1"
    assert answer.plan.value == pytest.approx(result.plan.costs[reading(1)].value + shift)
    assert (answer.best.value, answer.worst.value) == pytest.approx(tuple(v + shift for v in result.plan.interval))
    assert [row.reading for row in answer.rows] == ["alpha = 0.4", "alpha = 0.7", "alpha = 1", "alpha = 1.3", "alpha = 1.6"]
    assert answer.baseline.value == pytest.approx(result.baseline.value.value + shift)
    assert answer.baseline.value > answer.worst.value  # the plan with recombinators is cheaper at every reading of this case
    assert answer.best_reading == "alpha = 0.4" and answer.worst_reading == "alpha = 1.6"
    assert not answer.robust_differs and answer.proven_optimal


def test_the_expected_number_of_recombinations_agrees_with_a_simulation_of_the_plan(tiny):
    answer, result, _, _ = tiny
    model = Acquisition(Tiny(Fraction(1)))
    policy, goal = result.plan.policy, model.is_goal
    rng = random.Random(221)

    def run(state) -> int:
        count = 0
        while not goal(state):
            action = policy[state]
            count += action.label == RECOMBINE
            count += sum(run(need) for need in action.extra_inputs)
            state = rng.choices([t for t, _ in action.outcomes], [w for _, w in action.outcomes])[0]
        return count

    runs = [run(model.start("E")) for _ in range(20_000)]
    mean = sum(runs) / len(runs)
    error = (sum((n - mean) ** 2 for n in runs) / (len(runs) - 1) / len(runs)) ** 0.5
    assert abs(answer.recombinations.value - mean) < 5 * error + 1e-9
    assert answer.recombinations.low <= answer.recombinations.value <= answer.recombinations.high
    assert answer.combines[0].uses.value == pytest.approx(answer.recombinations.value)


def test_the_cost_rule_alone_moves_the_mean_by_the_expected_recombinations_times_the_ends_of_one_combine(tiny):
    answer, _, _, _ = tiny
    row = answer.combines[0]
    # 100,000 Dust at 1/100,000 Chaos and 12,000 Gold at 0.0005: 1 + 6; the ends 25,000 + 8,000 Gold and 250,000 + 20,000 Gold
    assert row.chaos == pytest.approx(7.0)
    assert row.chaos_low == pytest.approx(0.25 + 4.0)
    assert row.chaos_high == pytest.approx(2.5 + 10.0)
    low, high = answer.cost_rule_mean
    n = answer.recombinations.value
    assert low.value == pytest.approx(answer.plan.value - n * (row.chaos - row.chaos_low))
    assert high.value == pytest.approx(answer.plan.value + n * (row.chaos_high - row.chaos))
    assert low.low <= low.value <= low.high and high.low <= high.value <= high.high


def test_the_text_says_when_the_cost_rule_alone_could_make_the_plan_dearer_than_the_route_without_recombinators(tiny):
    answer, _, _, report = tiny
    assert answer.cost_rule_mean[1].value > answer.baseline.value  # 78.90 against 69.00 in the tiny case
    text = render_text(report)
    assert "the cost of a recombination is approximate too: at the high end of its reports the plan costs 78.90 Chaos at alpha = 1, more than this route" in text
    cheap = replace(answer, cost_rule_mean=(answer.cost_rule_mean[0], answer.plan))
    assert "approximate too" not in " ".join(cheap.text_lines(300.0))


def test_the_dust_and_gold_prices_are_named_with_their_source(tiny):
    answer, _, _, report = tiny
    assert {(p.name, p.source) for p in answer.prices} == {("Thaumaturgic Dust", "default"), ("Gold", "default")}
    text = render_text(report)
    assert "Thaumaturgic Dust at 100,000 per Chaos Orb [default]" in text
    assert "Gold at 500 Chaos Orbs per million [default]" in text
    assert "hand price in price_overrides.toml" in text


def test_a_plan_with_the_smallest_worst_case_elsewhere_names_that_route():
    answer, result = gamble_answer()
    assert answer.robust_differs and result.robust_differs
    text = "\n".join(answer.text_lines(300.0))
    assert "the route made for alpha = 0.7" in text
    assert "it is not the plan" in text
    assert answer.robust_worst.value == pytest.approx(result.robust.worst.value + 6.0)
    assert answer.worst.value > answer.robust_worst.value
    assert answer.proven_optimal
    assert "the smallest worst case any route can have is" in text
    assert [name for name, _ in answer.robust_costs] == [row.reading for row in answer.rows]


def test_a_gap_in_the_bracket_is_worded_as_a_gap_not_as_an_optimum():
    answer, _ = gamble_answer()
    from crafting_system.risk import Estimate

    open_gap = replace(answer, lower=Estimate(answer.upper.value - 4.0, 0.0, 0.0), proven_optimal=False)
    text = "\n".join(open_gap.text_lines(300.0))
    assert "lies between" in text and "gap 4.00" in text and "reaches the upper figure" in text


# --- the approximate inputs ---------------------------------------------------------------------------------------------------------


def test_the_json_names_the_claims_alpha_the_count_table_and_the_cost_rule_with_reasons_and_spreads(tiny):
    _, _, _, report = tiny
    inputs = {item["claim"]: item for item in policy_document(report)["approximate_inputs"]}
    alpha = inputs["recombinator.selection_weighted_formula_unknown"]
    assert alpha["reason"].startswith("Fitted on 40 + 28 observations")
    assert alpha["interval"]["grid"] == [0.4, 0.7, 1.0, 1.3, 1.6] and alpha["interval"]["plan"] == 1.0
    for table in ("recombinator.count_table", "recombinator.count_table_wiki"):
        assert inputs[table]["interval"]["largest_difference_points"] == 2.0
    dust = inputs["recombinator_cost.dust_per_combine_reports_3_26"]["interval"]
    assert (dust["low"], dust["point"], dust["high"]) == (25_000.0, 100_000.0, 250_000.0)
    gold = inputs["recombinator_cost.gold_per_combine_reports_3_26"]["interval"]
    assert (gold["low"], gold["point"], gold["high"]) == (8_000.0, 12_000.0, 20_000.0)
    factor = inputs["recombinator_cost.junk_craft_halves_dust_3_26"]["interval"]
    assert (factor["low"], factor["point"], factor["high"]) == (0.11, 0.5, 0.5)
    assert all(item["reason"] for item in inputs.values())
    assert "interval" not in inputs["recombinator.exclusive_mod_weight"]  # a claim with no spread says only why it is approximate


def test_the_text_lists_the_same_claims_with_their_spread(tiny):
    _, _, _, report = tiny
    text = render_text(report)
    assert "recombinator.selection_weighted_formula_unknown: Fitted on 40 + 28 observations" in text
    assert "spread: the planner is run at 1; its cost is read at 0.4, 0.7, 1, 1.3, 1.6" in text
    assert "spread: the planner uses 100,000; reports range from 25,000 to 250,000 (Thaumaturgic Dust per combine)" in text
    assert "spread: the planner uses 12,000; reports range from 8,000 to 20,000 (Gold per combine)" in text


def test_the_claims_of_the_route_without_recombinators_and_of_the_robust_route_are_listed_too():
    answer, _ = gamble_answer()
    # the plan is the gamble (a recombinator offer here), the safe route a stand-in: the list is the union of what the routes show
    claims = {item.claim for item in answer.approximate_inputs}
    assert "recombinator.selection_weighted_formula_unknown" in claims
    assert SAFE != GAMBLE


# --- an answer with no recombinator says nothing about alpha -------------------------------------------------------------------


def no_recombinator_case():
    models = {reading(alpha): Acquisition(Tiny(alpha, recombine=False)) for alpha in GRID}
    acquisition = next(iter(models.values()))
    start = acquisition.start("E")
    result = solve_readings(models, start, plan=reading(1), without=has_inputs)
    return result, start, acquisition.is_goal


def test_a_plan_that_uses_no_recombinator_has_no_interval_block():
    result, start, is_goal = no_recombinator_case()
    plan = toy_report_plan()
    assert build_interval_answer(result, plan, DATA, start=start, is_goal=is_goal) is None


def test_such_an_answer_says_nothing_about_alpha_in_text_json_or_page():
    result, start, is_goal = no_recombinator_case()
    plan = toy_report_plan()
    answer = build_interval_answer(result, plan, DATA, start=start, is_goal=is_goal)
    plain = build_report(plan, DATA)
    report = with_interval(plain, answer)
    assert report is plain
    text, document = render_text(report), json.dumps(policy_document(report))
    html = render_page(Page("Plain", (build_section(route_input(plan, report.interval), DATA, anchor="policy"),)))
    for words in (text, document, html):
        assert "alpha" not in words.lower()
        assert "recombinator" not in words.lower()
    assert "interval" not in policy_document(report)
    assert "approximate_inputs" in policy_document(report)  # the key stays, as for every answer; here it lists nothing of the recombinator
    assert not any(item.claim.startswith("recombinator") for item in report.approximate_inputs)


def test_the_plain_report_is_what_it_was_before_the_ticket():
    plan = toy_report_plan()
    report = build_report(plan, DATA)
    assert report.interval is None
    assert "interval" not in policy_document(report)
    assert "Plan and its interval" not in render_text(report)


def test_the_unused_axis_of_a_plan_is_not_named():
    # the plan reads only alpha; a second axis nothing reads is in the readings of the model but not in the words
    models = {}
    for alpha in GRID:
        for conflict in ("receiver", "donor"):
            models[Reading.of({ALPHA: alpha, "awakener.group_conflict": conflict})] = Acquisition(Tiny(alpha))
    plan_reading = Reading.of({ALPHA: Fraction(1), "awakener.group_conflict": "receiver"})
    acquisition = next(iter(models.values()))
    start = acquisition.start("E")
    result = solve_readings(models, start, plan=plan_reading, without=has_inputs)
    answer = build_interval_answer(result, toy_report_plan(), DATA, start=start, is_goal=acquisition.is_goal)
    assert answer.axes == (ALPHA,)
    assert [row.reading for row in answer.rows] == ["alpha = 0.4", "alpha = 0.7", "alpha = 1", "alpha = 1.3", "alpha = 1.6"]
    assert "group_conflict" not in "\n".join(answer.text_lines(300.0))
    assert all(row.best_cost is None for row in answer.rows)  # the best route of a merged row is not one number: not shown
    assert BUY_P  # the labels of the case are the ones of the support module
