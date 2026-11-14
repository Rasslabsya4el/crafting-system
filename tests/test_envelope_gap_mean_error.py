"""What a plan that is not proved exact says of its mean, its gap and its interval when the mean itself carries a certified error (ticket #867).

The reading of OR-32 of 2026-11-14 (`docs/owner-rules.md`): of a search that stopped at a gap or at a net, the gap stated holds every error its
figures carry. The upper figure is the mean with its certified error added (`certified_upper`), the lower figure is the bound with its error
taken off (the search's `lower`), and nothing printed of that plan calls its mean exact. The exact search keeps "the mean is exact" at the
solver's 1e-6 and refuses a plan it cannot certify to that (`tests/test_solver_packed_many_steps_certificate.py`).

By hand, with no plan of 99 Chaos or less and a mean of 100 Chaos certified to 5e-4 of itself: the plan costs at most 100.05, so the interval is
[99.00, 100.05] and the gap `100.05 / 99 - 1 = 1.0606%`, not the `100 / 99 - 1 = 1.0101%` of the bare mean. When the search itself certified
the same plan at 100.02 at most, that lower figure is the upper end: `100.02 / 99 - 1 = 1.0303%`.

The last test reads the three surfaces of one plan (the text report, the JSON, the route page): each says the same gap and the same interval.
"""

import dataclasses
import json
import re
from html import escape
from types import SimpleNamespace

import pytest
from cli_support import R12, price_file
from targets_support import DATA
from test_envelope_gap_stop_plan import at_once

from crafting_system.cli import build_report, make_plan, policy_document, render_text
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.planner import _envelope_plan
from crafting_system.planner._envelope_plan import (
    EnvelopeInfo,
    certificate_gap,
    certificate_gap_text,
    certificate_text,
    certified_upper,
    envelope_limits,
    mean_error_text,
)
from crafting_system.planner._limits import SHOWN_LABELS, SOLVE, limit_text
from crafting_system.planner._plan import envelope_refusal
from crafting_system.planner._envelope import NoPolicy
from crafting_system.planner._starts import _proved
from crafting_system.solver import ConvergenceError
from crafting_system.targets import load_target

EXACT_WORD = re.compile(r"\bexact", re.I)


def info(**fields) -> EnvelopeInfo:
    """A search over 99.00 (no plan costs less) and 100.00 (the mean shown), ended as `fields` say."""
    return EnvelopeInfo(fields.pop("exact", False), fields.pop("stopped", None), 99.0, 100.0, 4, 30, 20, 25, 60, 0, False, None, 9, 0.0, 0.0, None, **fields)


NET = "the time limit of 600 seconds was reached"


def test_the_upper_figure_of_a_plan_not_proved_exact_is_its_mean_with_the_certified_error_added():
    assert certified_upper(info(within=0.02, mean_error=5e-4)) == 100.0 * (1.0 + 5e-4)
    assert certified_upper(info(stopped=NET, mean_error=5e-4)) == 100.0 * (1.0 + 5e-4)
    assert certified_upper(info(within=0.02, mean_error=5e-4, proved_upper=100.02)) == 100.02  # the search's own figure of the same plan is lower
    assert certified_upper(info(within=0.02, mean_error=5e-4, proved_upper=100.3)) == 100.0 * (1.0 + 5e-4)
    assert certified_upper(info(exact=True)) == 100.0  # the exact search: its mean is certified to 1e-6 or the plan is refused


def test_the_gap_holds_the_means_error():
    assert certificate_gap(info(within=0.02)) == pytest.approx(100.0 / 99.0 - 1.0, rel=1e-12)
    assert certificate_gap(info(within=0.02, mean_error=5e-4)) == pytest.approx(100.05 / 99.0 - 1.0, rel=1e-12)
    assert certificate_gap(info(within=0.02, mean_error=5e-4, proved_upper=100.02)) == pytest.approx(100.02 / 99.0 - 1.0, rel=1e-12)
    assert certificate_gap_text(certificate_gap(info(within=0.02))) == "1.01%"
    assert certificate_gap_text(certificate_gap(info(within=0.02, mean_error=5e-4))) == "1.06%"
    assert certificate_gap_text(certificate_gap(info(stopped=NET, mean_error=5e-4))) == "1.06%"


def test_the_interval_ends_at_the_certified_upper_figure_and_the_sentence_names_the_error():
    loose = info(within=0.02, mean_error=5e-4)
    text = certificate_text(loose)
    assert "The best possible cost lies in [99.00, 100.05] Chaos after the start item" in text
    assert "The plan costs at most 1.06% more than the best possible cost." in text
    assert mean_error_text(loose) == (
        "The plan takes so many steps that its average cost is worked out only to within 0.0005 of itself (0.05 Chaos either way); "
        "the gap stated allows for that. "
    )
    assert mean_error_text(info(within=0.02, mean_error=1e-6)) == "" and mean_error_text(info(within=0.02)) == ""  # the solver's 1e-6: nothing to say


@pytest.mark.parametrize("ended", [{"within": 0.02}, {"stopped": NET}])
@pytest.mark.parametrize("error", [0.0, 3e-10, 5e-4])
def test_no_text_of_a_plan_not_proved_exact_calls_its_mean_exact(ended, error):
    found = info(mean_error=error, **ended)
    (limit,) = envelope_limits(found)
    text = limit_text(limit)
    assert not EXACT_WORD.search(text), text
    assert "100.00 Chaos on average after the start item" in text and "the average of the plan shown itself" in text
    assert ("worked out only to within 0.0005 of itself" in text) == (error > 1e-6)
    assert f"at most {certificate_gap_text(certificate_gap(found))} more than the best possible cost" in text
    row = _proved(SimpleNamespace(search=found))
    assert not EXACT_WORD.search(row) and f"proved at most {certificate_gap_text(certificate_gap(found))} above the cheapest plan from it" in row


def test_the_exact_search_still_says_its_cut_is_exact():
    (limit,) = envelope_limits(info(exact=True))
    assert "The cut is exact" in limit_text(limit) and "the mean cost is that of the best plan" in limit_text(limit)


def test_a_plan_whose_cost_cannot_be_certified_is_not_called_no_route():
    refused = ConvergenceError("the policy iteration on 9 states certifies only a relative bound of 0.02", 0.02)
    try:
        try:
            raise refused
        except ConvergenceError as error:
            raise NoPolicy("the search stopped (the time limit) and the plan it had found over 9 states cannot be solved to a certified cost") from error
    except NoPolicy as inner:
        try:
            raise NoPolicy(f"{inner}. The count was stopped") from inner  # the note of a bound cut short is raised from the refusal
        except NoPolicy as outer:
            text = envelope_refusal("auto", outer)
            direct = envelope_refusal("auto", inner)
    for said in (text, direct):
        assert said.startswith("a plan was found, but its average cost could not be worked out to a certified figure, so it is not shown")
        assert "reaches the goal" not in said
    assert envelope_refusal("auto", NoPolicy("no policy of the offers reaches the goal from the start")).startswith("no policy of the offered actions reaches the goal")


def test_the_text_report_the_json_and_the_page_say_one_gap_and_one_interval(monkeypatch):
    """The fixture world's R12, its search made to end at a gap of 20% with a bound 10% lower, its final solve certified only to 5e-4 and the
    search's own figure of the plan higher still: what `make_plan` then writes, read on each surface."""
    solve_walked, run = _envelope_plan.solve_walked, _envelope_plan.Search.run

    def loose_solve(*args, **kwargs):
        packed = solve_walked(*args, **kwargs)
        return dataclasses.replace(packed, solution=dataclasses.replace(packed.solution, error_bound=5e-4))

    def loose_run(self, *args, **kwargs):
        result = run(self, *args, **kwargs)
        return dataclasses.replace(result, exact=False, within=0.2, lower=result.lower * 0.9, upper=result.lower * 1.001)

    monkeypatch.setattr(_envelope_plan, "solve_walked", loose_solve)
    monkeypatch.setattr(_envelope_plan.Search, "run", loose_run)
    plan = make_plan(DATA, load_target(R12, DATA), price_file(), solver="envelope", budget=at_once(0.2))
    found = plan.search
    assert not found.exact and found.within == 0.2 and found.mean_error == 5e-4 and found.proved_upper > found.upper * 1.0005

    upper = found.upper * (1.0 + 5e-4)  # by hand: the mean with its certified error
    gap = certificate_gap_text(upper / found.lower - 1.0)
    assert gap != certificate_gap_text(found.upper / found.lower - 1.0)  # the bare mean would state a smaller gap
    said = (
        f"The best possible cost lies in [{found.lower:,.2f}, {upper:,.2f}] Chaos after the start item",
        f"The plan costs at most {gap} more than the best possible cost.",
        f"worked out only to within 0.0005 of itself ({found.upper * 5e-4:,.2f} Chaos either way); the gap stated allows for that.",
        f"it costs {found.upper:,.2f} Chaos on average after the start item",
    )
    (cut,) = [limit for limit in plan.limits if limit.kind == SOLVE and limit.what.startswith("The search stopped once")]
    report = build_report(plan, DATA)
    text = render_text(report)
    (entry,) = [entry for entry in policy_document(report)["limits"] if entry["what"] == cut.what]
    page = render_page(Page("x", (build_section(route_input(plan), DATA),)))
    assert limit_text(cut) in text and escape(limit_text(cut, SHOWN_LABELS)) in page
    for sentence in said:
        assert sentence in text, sentence
        assert sentence in entry["guarantee"], sentence
        assert escape(sentence) in page, sentence
    assert not EXACT_WORD.search(text) and not EXACT_WORD.search(json.dumps(policy_document(report))) and not EXACT_WORD.search(page)
