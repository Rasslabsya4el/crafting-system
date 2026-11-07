"""A limit made from a cause is in player words, and the developer's text behind it is in the JSON (tickets #557, #618; OR-13, OR-26).

`test_cause_words.py` reads the sentences where they are written. This test builds the limits that carry them, by the real code that builds them, and reads
what a person reads of each (`what`, the reason with its names, the text of the limit) with the same rule as the report (`faults_in`), and checks that the
developer's text is not in that text but is in `Limit.detail` and so in the JSON policy (`limit_document`):

* the model gap ("Left out where the model has no rule"), with more causes than are shown: `detail` follows the shown names one for one, the count of the
  rest last;
* the whole search (G12, G13), made from a refusal of the size estimate and from the reason no coarse level exists;
* the skipped levels (M3), the fall-back of the bound pruning (M2) and the timing run (M2).
"""

from coarse_support import COLD, FIRE, MANA
from limits_support import of_kind
from test_cli_approximate import approximate, budget, candidate, climbed, exact, tail, target  # noqa: F401  (the fixtures of the module and the helpers)
from test_cli_limits_506 import calibration_layers, plan_of
from test_cli_player_words import faults_in
from types import SimpleNamespace

from crafting_system.abstraction import Abstraction, EstimateRefused, Gap, ModelGaps
from crafting_system.actions import OutOfScopeError
from crafting_system.cli import _bound_prune, _decide, _plan
from crafting_system.cli._limits import SHOWN_CAUSES, limit_document, limit_text, model_gap_limits
from crafting_system.cli._plan import skipped_level_limits, whole_search_limit
from crafting_system.solver import ConvergenceError

SECRET = "ADR-0023 ticket #212 IncreasedLifeEssence6 size_estimate"  # what only a developer reads


def reads_as_words(limit, secret: str = SECRET) -> None:
    """What a person reads of the limit holds no internal name and none of the developer's text; the JSON has it in `detail`."""
    shown = [limit.what, limit.reason(), limit.guarantee, limit_text(limit), *limit.labels]
    for text in shown:
        assert faults_in(text) == [], text
        assert secret not in text and "ADR" not in text
    assert limit.detail, "the developer's text is in the limit"
    document = limit_document(limit)
    assert document["detail"] == list(limit.detail) and any(secret in each for each in limit.detail)
    assert document["why"] == limit.reason() and secret not in document["why"]


def test_a_model_gap_names_its_causes_in_words_and_keeps_the_developers_text_one_for_one():
    gaps = ModelGaps()
    for number in range(SHOWN_CAUSES + 2):
        refusal = OutOfScopeError(f"cause {number} of the model, in words", detail=f"{SECRET} {number}")
        gaps.note(f"Orb {number}", f"state-{number}", refusal)
    (limit,) = model_gap_limits(gaps.entries())

    assert len(limit.names) == len(limit.detail) == SHOWN_CAUSES + 1  # the shown causes and the count of the rest
    assert limit.names[-1] == limit.detail[-1] == "2 more causes"
    assert all(SECRET in detail and str(number) in detail for number, detail in enumerate(limit.detail[:SHOWN_CAUSES]))
    reads_as_words(limit)


def test_a_model_gap_with_no_developer_text_has_no_detail():
    (limit,) = model_gap_limits([Gap("Orb", 1, "no rule", False)])
    assert limit.detail == () and "detail" not in limit_document(limit)


def test_the_whole_search_made_from_a_refused_forecast_carries_the_refusals_detail(monkeypatch):
    def refused(self, starts, actions, **options):
        raise EstimateRefused("a state holds a fracture made during the craft, which the size estimate has no rule for", detail=f"{SECRET}: state 1")

    monkeypatch.setattr(Abstraction, "estimate", refused)
    made = plan_of(budget=60.0)

    (limit,) = [each for each in of_kind(made.limits, "how-solved") if each.what == "The whole search was run"]
    assert "a fracture made during the craft" in limit.why
    reads_as_words(limit)


def test_the_whole_search_made_from_a_reason_no_coarse_level_exists_carries_its_detail(monkeypatch):
    monkeypatch.setattr(_decide, "coarse_cause", lambda abstraction, actions: ("an approximate answer cannot include Regal Orb: a reason in words", f"{SECRET}: Regal Orb"))
    made = plan_of(budget=1e-9)  # a forecast over the budget and no coarse level: the whole search runs

    (limit,) = [each for each in of_kind(made.limits, "how-solved") if each.what == "The whole search was run"]
    assert "an approximate answer cannot include Regal Orb" in limit.why
    reads_as_words(limit)


def test_the_whole_search_limit_of_a_decision_carries_the_decisions_detail():
    limit = whole_search_limit("a reason in words", f"{SECRET}: the decision")
    assert limit.detail == (f"{SECRET}: the decision",)
    reads_as_words(limit)
    assert whole_search_limit("a reason in words").detail == ()


def test_a_skipped_level_carries_the_detail_of_its_cause_one_for_one_with_its_names():
    (limit,) = skipped_level_limits(
        [
            ("tail cut at 0.01", "it gave no plan to follow", f"{SECRET}: no proper policy from the start"),
            ("tail cut at 0.02", "its values did not settle", f"{SECRET}: no luck in 3000 sweeps"),
            ("tail cut at 0.03", "its values did not settle", "the same cause again, once"),
        ]
    )
    assert limit.names == ("it gave no plan to follow", "its values did not settle")
    assert len(limit.detail) == len(limit.names) and "no proper policy" in limit.detail[0] and "no luck" in limit.detail[1]
    reads_as_words(limit)
    assert skipped_level_limits([("a level", "it gave no plan to follow")])[0].detail == ()  # a two-part entry has no developer text


def test_the_ladder_keeps_the_developers_text_of_a_skipped_level(approximate):
    wide = candidate(approximate, [{COLD, MANA}, {FIRE, "LightningResistance"}])
    good = candidate(approximate, [{MANA, "LightningResistance"}])
    skipped = tail(wide, 0.0)

    solved = climbed(approximate, skipped, good)
    (limit,) = skipped_level_limits(solved.skipped)

    assert len(solved.skipped[0]) == 3 and solved.skipped[0][2]
    assert faults_in(limit.reason()) == [] and solved.skipped[0][2] not in limit_text(limit)
    assert limit_document(limit)["detail"] == [solved.skipped[0][2]]


def test_the_fall_back_of_the_bound_pruning_carries_the_solvers_text(monkeypatch):
    real_solve = _bound_prune.solve
    calls = []

    def failing_once(model, starts):
        calls.append(1)
        if len(calls) == 1:
            raise ConvergenceError(f"{SECRET}: no luck in 3000 sweeps", float("inf"))
        return real_solve(model, starts)

    monkeypatch.setattr(_plan, "MIN_OFFERS_TO_PRUNE", 2)
    monkeypatch.setattr(_bound_prune, "solve", failing_once)
    made = plan_of()

    (limit,) = [each for each in made.limits if each.what == "All the actions were solved"]
    assert made.pruned.fell_back and "did not settle" in made.pruned.why and SECRET in made.pruned.detail
    reads_as_words(limit)


def test_the_timing_run_carries_the_solvers_text(monkeypatch):
    estimate, table = calibration_layers(60)
    abstraction = SimpleNamespace(data=None, is_goal=lambda state: state == len(table))
    monkeypatch.setattr(_decide, "solve", lambda model, starts: (_ for _ in ()).throw(ConvergenceError(f"{SECRET}: no luck in 3000 sweeps", float("inf"))))

    rate, why, detail = _decide.measure_solve_rate_detail(abstraction, 0, estimate, {})
    limit = _plan.guessed_rate_limit(why, detail)

    assert rate == _decide.SOLVE_RATE_FALLBACK and why == "the timing run did not finish" and SECRET in detail
    reads_as_words(limit)
    assert _decide.measure_solve_rate(abstraction, 0, estimate, {}) == (rate, why)  # the two-part form is the old one


def test_an_estimate_refusal_and_the_coarse_cause_reach_the_decision_with_their_detail():
    refused = EstimateRefused("an offered action rerolls the values of mods, which the size estimate has no rule for", detail=f"{SECRET}: rerolls")
    decision = _decide.choose(None, 0.0, 0.0, 60.0, refusal=refused.player, refusal_detail=refused.detail)
    assert decision.detail == refused.detail and refused.player in decision.message and SECRET not in decision.message


def test_a_plan_without_a_cause_has_no_detail_in_its_limits():
    made = plan_of(budget=60.0)
    assert not [limit for limit in made.limits if limit.detail]
