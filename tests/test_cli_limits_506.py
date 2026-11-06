"""The silent limits that were left after #459 are `Limit` records (ticket #506; rows of #467 and #480; OR-12, OR-13, OR-23, OR-26, OR-29).

One test per source, by the row of the fact base (`docs/research/2026-11-06-rebuild-3-5-inventory.md`, Part B). The model gaps (K14, G6) and the
two refusal families are in `test_cli_model_gaps.py`; the other sources are tested where their module is tested, and listed here:

* G17 the twins left out on the packed path and in an approximate answer: `test_prune_forecast.py::test_g17_*`.
* K13 corrupting and quality offers left out of states that cannot use them: `test_actions_corrupting_toy.py::test_k13_*` and
  `test_abstraction_quality.py::test_k13_*`; the wiring into the plan: `test_k13_*` below.
* C15, V8 the reach chance above 400 transient states: `test_c15_*`. V4 the state line: `test_v4_*`.
* C19, M1 a refused forecast keeps its text: `test_m1_*`. M2 the guessed solver speed `test_m2_rate_*` and the fall-back of the bound pruning
  `test_m2_prune_*`. M3 a skipped tail-cut level: `test_cli_approximate.py::test_m3_*`.
* M7 a policy that needs more runs than it makes: `test_risk_inputs.py::test_m7_*`.
* C24, C23 the free-action methods that gave up: `test_risk_free_actions.py::test_c24_*`, `test_c23_*`. C25 the attempt-wise run:
  `test_risk_regen.py::test_c25_*`. C27 the coarse grid the dense engine cannot hold: `test_risk_coarse_first.py::test_c27_*`.
* Shown not to change an answer (the inventory marks them): C26 the mass the nested run drops, C27 the packed moments, C31 the elimination that
  gives up: `test_risk_inputs.py::test_c26_*`, `test_c27_*` and `test_solver_branching.py::test_c31_*`.

Then what the three surfaces show of the new kinds, and that every new guarantee is in player words.
"""

import dataclasses
import re
from html import escape
from types import SimpleNamespace

import pytest
from cli_support import R12, price_file
from limits_support import of_kind
from targets_support import DATA

from crafting_system.actions import ChaosOrb
from crafting_system.abstraction import PRUNED_CORRUPTING, PRUNED_QUALITY, Abstraction, EstimateRefused, Gap
from crafting_system.cli import Limit, build_report, make_plan, policy_document, render_text
from crafting_system.cli import _decide, _plan, _reach
from crafting_system.cli._limits import GROUPS, SHOWN_LABELS, STATE_LINE, WITHIN_GAP, grouped, limit_text, model_gap_limits, pruning_limits, risk_limits
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.solver import ConvergenceError
from crafting_system.targets import load_target


def plan_of(**options):
    return make_plan(DATA, load_target(R12, DATA), price_file(), **options)


@pytest.fixture(scope="module")
def plan():
    return plan_of()


# --- M1: a refused forecast keeps its own text -------------------------------------------------------------------------------


def test_m1_a_refused_forecast_puts_its_own_text_in_the_limit_and_the_answer_stays_exact(monkeypatch):
    def refused(self, starts, actions, **options):
        raise EstimateRefused("a state holds a fracture made during the craft, which the size forecast has no rule for")

    monkeypatch.setattr(Abstraction, "estimate", refused)

    made = plan_of(budget=60.0)

    (whole,) = [limit for limit in of_kind(made.limits, "how-solved") if limit.what == "The whole search was run"]
    assert made.approximation is None and made.risk is not None
    assert whole.why == (
        "the size of the exact search could not be forecast "
        "(a state holds a fracture made during the craft, which the size forecast has no rule for), so it was run in full"
    )
    assert whole.guarantee == "The answer is exact among the methods offered."


# --- M2: the solver's speed that could not be measured -----------------------------------------------------------------------


def calibration_layers(states: int):
    """A chain of `states` states that goes on with chance 1/2 and ends in the goal otherwise: 2 transitions a state."""
    table = {n: [(ChaosOrb(), [(n + 1, 1), (states, 1)])] for n in range(states)}
    return SimpleNamespace(first_layers=lambda edges: table), table


def test_m2_rate_a_calibration_that_cannot_run_names_why_and_a_measured_one_says_nothing(monkeypatch):
    estimate, table = calibration_layers(60)
    last = len(table)
    abstraction = SimpleNamespace(data=None, is_goal=lambda state: state == last)

    measured = _decide.measure_solve_rate(abstraction, 0, estimate, {})
    monkeypatch.setattr(_decide, "solve", lambda model, starts: (_ for _ in ()).throw(ConvergenceError("no luck in 3000 sweeps", float("inf"))))
    failed = _decide.measure_solve_rate(abstraction, 0, estimate, {})
    few = _decide.measure_solve_rate(abstraction, 0, calibration_layers(10)[0], {})

    assert measured[1] == "" and measured[0] != _decide.SOLVE_RATE_FALLBACK
    assert failed == (_decide.SOLVE_RATE_FALLBACK, "the timing run did not finish (no luck in 3000 sweeps)")
    assert few == (_decide.SOLVE_RATE_FALLBACK, "the forecast covers only 20 possible moves between states, too few to time the search on")
    assert _decide.calibrate_solve_rate(abstraction, 0, estimate, {}) == _decide.SOLVE_RATE_FALLBACK  # the old function keeps its answer


def test_m2_rate_a_plan_whose_forecast_used_the_guessed_speed_says_so_and_a_given_rate_does_not():
    guessed = plan_of(budget=1e-9)  # no rates given, a forecast above the budget: the solver is timed, and R12's pilot graph is too small to time
    given = plan_of(budget=1e-9, rates=_decide.Rates(1.0, 1.0))

    (limit,) = [each for each in guessed.limits if each.what == "The time of the search was guessed"]
    assert limit.kind == "how-solved" and "too few to time the search on" in limit.why and limit.why.endswith("so the forecast used a fixed speed")
    assert limit.guarantee == "The answer's own guarantee does not depend on it: the forecast only chose between the exact run and an approximate one."
    assert not [each for each in given.limits if each.what == "The time of the search was guessed"]


# --- M2: the fall-back of the bound pruning ----------------------------------------------------------------------------------


def test_m2_prune_a_bound_pruning_that_fell_back_to_all_the_actions_says_why(monkeypatch):
    real = _plan.solve_pruned
    monkeypatch.setattr(_plan, "MIN_OFFERS_TO_PRUNE", 2)  # R12 has 6 offers: the pruning runs
    monkeypatch.setattr(_plan, "solve_pruned", lambda *args, **options: real(*args, **{**options, "rounds": 0}))  # no round to prove anything in

    made = plan_of()

    assert made.pruned is not None and made.pruned.fell_back
    (limit,) = [each for each in made.limits if each.what == "All the actions were solved"]
    assert limit.kind == "how-solved" and made.pruned.why == "the certificate did not close within 0 rounds"
    assert limit.why == "the search first solved a smaller set of actions and could not prove it enough (the certificate did not close within 0 rounds)"
    assert limit.guarantee == "The answer is exact among the methods offered."
    monkeypatch.setattr(_plan, "solve_pruned", real)
    clean = plan_of()
    assert clean.pruned is not None and not clean.pruned.fell_back and not [each for each in clean.limits if each.what == "All the actions were solved"]


# --- C15, V8: the chance of reaching a state ---------------------------------------------------------------------------------


def test_c15_above_the_transient_limit_the_chance_of_reaching_a_state_is_absent_and_the_limit_says_so(monkeypatch):
    shown = plan_of()
    assert not of_kind(shown.limits, STATE_LINE)[1:] and build_report(shown, DATA).states[0].reach is not None  # R12's policy is within the limit

    monkeypatch.setattr(_reach, "MAX_TRANSIENT", 0)
    cut = plan_of()
    report = build_report(cut, DATA)

    limit = [each for each in cut.limits if each.what == "The chance of reaching each state is not shown"]
    assert len(limit) == 1 and limit[0].kind == STATE_LINE and limit[0].why.endswith("and the calculation takes at most 0")
    assert limit[0].guarantee == "The plan, its cost and its odds are as stated; only that chance is missing."
    assert report.states[0].reach is None  # what the limit is about
    assert policy_document(report)["states"][0]["reach_probability"] is None
    assert limit_text(limit[0]) in render_text(report)


# --- V4: what a state line shows ---------------------------------------------------------------------------------------------


def test_v4_the_state_line_limit_says_whether_the_model_tracks_the_other_mods_and_follows_the_abstraction(plan):
    (limit,) = [each for each in plan.limits if each.kind == STATE_LINE]

    assert plan.abstraction.keeps_junk is False  # R12 offers no action that reads the other mods
    assert limit.what == "A state does not list the other mods" and limit.guarantee == "The odds and costs do not depend on them: no offered action reads them."
    tracked = _plan.states_limit(True)
    assert tracked.what == "A state lists the other mods only as a count per side" and tracked.guarantee == "The odds and costs count every one of them."
    assert limit_text(limit) in render_text(build_report(plan, DATA))
    assert not any(each.kind == STATE_LINE for each in plan_of(solve_it=False).limits)  # nothing is described when nothing is solved


# --- K13: the wiring of the prunings into the plan ----------------------------------------------------------------------------


def test_k13_the_prunings_the_walk_wrote_are_in_the_limits_of_the_finished_plan(plan):
    abstraction = plan.abstraction
    abstraction.prunings.note("Vaal Orb", PRUNED_CORRUPTING)
    abstraction.prunings.note("Intrinsic Catalyst", PRUNED_QUALITY)
    abstraction.prunings.note("Vaal Orb", PRUNED_CORRUPTING)

    made = _plan.finished(dataclasses.replace(plan, limits=()))

    corrupting, quality = of_kind(made.limits, "proved-unneeded")
    assert corrupting.labels == ("Vaal Orb",) and quality.labels == ("Intrinsic Catalyst",)  # once each, in the order met
    assert corrupting.guarantee == quality.guarantee == "The plan is the cheapest among the methods offered. Offering them in the other states would change no cost."
    abstraction.prunings._labels.clear()
    assert pruning_limits(abstraction.prunings) == ()


# --- the slower method that finished -----------------------------------------------------------------------------------------


def test_the_percentiles_a_slower_method_gave_are_a_limit_that_marks_the_unreached_ones(plan):
    gave_up = dataclasses.replace(plan.risk.grid, gave_up=("a loop of states that cost almost nothing is longer than the 1 states the quicker percentile methods can follow",))
    risk = dataclasses.replace(plan.risk, grid=gave_up)

    (limit,) = risk_limits(risk)

    assert limit.what == "Percentiles by a slower method" and limit.why == gave_up.gave_up[0]
    assert limit.guarantee == "Each percentile shown is certified by the method that finished; one it could not reach is marked as not computed."
    assert risk_limits(plan.risk) == ()


# --- the three surfaces and the words ----------------------------------------------------------------------------------------


def every_new_limit(plan) -> list[Limit]:
    """One of each limit this ticket adds, as the sources write them."""
    risk = dataclasses.replace(plan.risk, grid=dataclasses.replace(plan.risk.grid, gave_up=("a quicker percentile method would need more than the 1 figures it can hold in memory",), cause="unordered"))
    return [
        *model_gap_limits([Gap("Harvest Reforge Defence", 3, "the model has no rule for a pool with a family on both sides", False), Gap("Toy Graft", 7, "consumes", True)]),
        _plan.states_limit(True),
        *risk_limits(risk),
        _plan.guessed_rate_limit("the forecast covers only 20 possible moves between states, too few to time the search on"),
        *_plan.skipped_level_limits([("tail cut at theta 0.01 over family groups of 8", "no proper policy")]),
        _plan.whole_search_limit("the size of the exact search could not be forecast (a reason), so it was run in full"),
    ]


def test_every_guarantee_this_ticket_adds_is_in_player_words_and_a_cheapness_claim_has_its_gapped_form(plan):
    for limit in every_new_limit(plan):
        assert limit.guarantee.endswith(".") and limit.guarantee[0].isupper()
        assert not re.search(r"[a-z]+-[a-z]+-?[a-z]*|_|`|#\d|ticket|ADR|OR-\d|\bkind\b=", limit.guarantee), limit.guarantee
        if "cheapest" in limit.guarantee:
            assert WITHIN_GAP in limit.approximate  # the claim comes from `claim()`: an approximate answer says "within the stated gap"


def test_the_new_kinds_have_a_title_and_show_in_the_text_the_json_and_the_page(plan):
    added = every_new_limit(plan)
    carrying = dataclasses.replace(plan, limits=(*plan.limits, *added))
    report = build_report(carrying, DATA)
    text = render_text(report)
    document = policy_document(report)
    page = render_page(Page("x", (build_section(route_input(carrying), DATA),)))

    kinds = {limit.kind for limit in added}
    assert {"model-gap", "consumes-items", "state-line", "risk", "how-solved"} <= kinds
    assert all(kind in dict(GROUPS) for kind in kinds)  # every kind has its title
    assert {title for title, _ in grouped(added)} >= {"Actions the model has no rule for in some states", "Actions that consume other items", "What a state line shows"}
    for limit in added:
        assert limit_text(limit) in text
        assert escape(limit_text(limit, SHOWN_LABELS)) in page
        assert any(entry["what"] == limit.what and entry["guarantee"] == limit.guarantee for entry in document["limits"])


def test_the_gapped_form_of_every_new_cheapness_claim_replaces_the_claim_on_an_approximate_answer(plan):
    from crafting_system.cli._limits import approximate_limits

    for limit in approximate_limits(every_new_limit(plan)):
        assert not limit.guarantee.startswith("The plan is the cheapest")
    assert [limit.guarantee for limit in approximate_limits(model_gap_limits([Gap("Orb", 1, "no rule", False)]))] == [
        "The plan is within the stated gap of the cheapest among the actions the model can apply in each state. An action the model has no rule for could make it cheaper."
    ]

