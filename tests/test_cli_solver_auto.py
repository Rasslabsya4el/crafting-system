"""`solver="auto"` is the envelope search wherever its bound can be built, and the command has `--solver` (ticket #535, ADR-0063; OR-11, OR-12, OR-13).

* `pattern_refusal(abstraction)` is the one check: None where the crafted-pattern bound can be built, a text where it cannot, and `Pattern` raises that text;
* `make_plan(solver="auto")` asks it before any solve: the envelope search where it is None, whatever the `budget` (the answer is exact, never approximate);
  where it refuses, the path it was (the budget decision, the walk, the object solver for a small graph);
* an envelope search that cannot answer under `auto` is a `PlanError` that says why and names `--solver packed`: no silent walk;
* the command's `--solver` choices are the planner's, `auto` by default, and reach `make_plan` through `plan_with_starts`.

Real routes: `test_cli_envelope_real.py`. Fixture world, no game dump needed.
"""

import dataclasses

import pytest
from cli_support import R12, TODAY, price_file, run
from targets_support import DATA

from crafting_system.abstraction import Pattern, pattern_refusal
from crafting_system.actions import OutOfScopeError
from crafting_system.cli import _plan, _starts, evaluate_route, load_route, main
from crafting_system.cli._envelope import NoPolicy
from crafting_system.cli._packed import SOLVERS
from crafting_system.cli._plan import PlanError, make_plan
from crafting_system.targets import load_target


@pytest.fixture(scope="module")
def packed():
    return make_plan(DATA, load_target(R12, DATA), price_file(), solver="packed")


def unsolved():
    return make_plan(DATA, load_target(R12, DATA), price_file(), solve_it=False)


def test_the_bound_can_be_built_for_r12_and_the_refusal_names_each_cause():
    abstraction = unsolved().abstraction

    assert pattern_refusal(abstraction) is None
    Pattern(abstraction)  # builds

    abstraction._has_laws = True
    text = pattern_refusal(abstraction)
    assert text is not None and "a roll limit" in text
    with pytest.raises(OutOfScopeError) as raised:
        Pattern(abstraction)
    assert str(raised.value) == text  # one check, one text: `Pattern` and `make_plan` read the same


def test_the_text_of_the_refusal_names_every_cause_there_is(monkeypatch):
    abstraction = unsolved().abstraction
    abstraction._has_laws = True
    for name in ("rerolls_values", "tracks_offer", "tracks_imprints"):
        monkeypatch.setattr(type(abstraction), name, property(lambda self: True), raising=False)

    text = pattern_refusal(abstraction)

    assert all(words in text for words in ("a roll limit", "rerolls the values", "unveil offer", "imprints"))


def test_auto_is_the_envelope_search_where_the_bound_can_be_built_and_gives_the_walks_mean(packed):
    auto = make_plan(DATA, load_target(R12, DATA), price_file())

    assert auto.packed is not None and auto.packed.info["envelope"].exact
    assert auto.mean_remaining == pytest.approx(packed.mean_remaining, rel=1e-9)
    assert [limit for limit in auto.limits if limit.what == "The search expanded only what could matter"]


def test_auto_ignores_the_budget_because_the_envelope_search_is_always_exact(packed):
    for budget in (0.0, 1e-9, 60.0):
        auto = make_plan(DATA, load_target(R12, DATA), price_file(), budget=budget)

        assert auto.approximation is None and auto.packed.info["envelope"].exact
        assert not [limit for limit in auto.limits if limit.what.startswith("The whole search")]
        assert auto.mean_remaining == pytest.approx(packed.mean_remaining, rel=1e-9)


def test_auto_where_the_bound_is_refused_is_the_old_path_with_its_budget_decision(monkeypatch, packed):
    monkeypatch.setattr(_plan, "pattern_refusal", lambda _abstraction: "planted for the test")

    small = make_plan(DATA, load_target(R12, DATA), price_file(), budget=1e12)
    over = make_plan(DATA, load_target(R12, DATA), price_file(), budget=1e-9)

    assert small.packed is None and small.mean_remaining == pytest.approx(packed.mean_remaining, rel=1e-9)  # the object solver, as always
    assert not hasattr(small, "packed") or small.packed is None
    assert [limit for limit in over.limits if limit.what.startswith("The whole search")]  # the budget decision ran: the forecast was over it


def test_envelope_by_name_still_refuses_where_the_bound_is_refused(monkeypatch):
    from crafting_system.cli import _envelope_plan

    def refuse(*_args, **_kwargs):
        raise OutOfScopeError("a goal with a roll limit has no members")

    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", refuse)
    with pytest.raises(PlanError, match="the envelope search cannot answer this target: a goal with a roll limit"):
        make_plan(DATA, load_target(R12, DATA), price_file(), solver="envelope", with_risk=False)


def refused_under_auto(monkeypatch, error) -> str:
    """The `PlanError` text of a plan under `auto` whose envelope search raises `error`; the walk must never run after it."""

    def refuse(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(_plan, "envelope_result", refuse)
    monkeypatch.setattr(_plan, "packed_result", lambda *_a, **_k: pytest.fail("auto walked after the envelope search had started"))
    with pytest.raises(PlanError) as raised:
        make_plan(DATA, load_target(R12, DATA), price_file(), with_risk=False)
    return str(raised.value)


def test_an_envelope_search_that_cannot_answer_under_auto_is_a_plan_error_that_names_the_walk_not_a_walk(monkeypatch):
    text = refused_under_auto(monkeypatch, OutOfScopeError("a model gap"))

    assert "a model gap" in text and "`--solver packed`" in text and "envelope" not in text


def test_no_route_under_auto_says_so_as_the_walk_does_and_does_not_advise_the_walk(monkeypatch):
    text = refused_under_auto(monkeypatch, NoPolicy("no policy of the offers reaches the goal from the start"))

    assert text.startswith("no policy of the offered actions reaches the goal from the start item") and "--solver" not in text


def build_refusals():
    """The two refusals of the bound's build, made by their own functions (`_pattern._gap`, `_pattern._no_member`) on a key like a real one."""
    from types import SimpleNamespace

    from crafting_system.abstraction import _pattern
    from crafting_system.items import Rarity

    key = SimpleNamespace(status=(0, 2), crafted=(), counts=(1, 2), tags=None, flags=SimpleNamespace(rarity=Rarity.RARE), fractured=())
    gap = _pattern._gap(SimpleNamespace(label="Orb of Annulment"), key, OutOfScopeError("no admitted rule removes a mod of this item"))
    return [gap, _pattern._no_member(key)]


@pytest.mark.parametrize("error", build_refusals(), ids=["model gap at a member", "no member of a key"])
def test_a_refusal_of_the_bounds_build_reaches_the_player_as_a_cause_not_the_developers_text(monkeypatch, error):
    """OR-13: under `auto` the player reads what went wrong in his words; the key, the member builder and the rule numbers stay in the developer's text."""
    text = refused_under_auto(monkeypatch, error)

    assert error.player in text and "`--solver packed`" in text
    for internal in ("status [", "counts (", "member", "key", "OR-1", "defect", "crafted-pattern"):
        assert internal not in text, internal
    assert "(status [0, 2]" in str(error)  # the developer's text is still the error's own


def test_a_start_item_that_already_meets_the_target_costs_nothing_under_the_default_search():
    target = load_target(R12, DATA)
    met = dataclasses.replace(target, requirements=tuple(r for r in target.requirements if "Lightning Skill Gems" not in str(r)))
    assert len(met.requirements) == len(target.requirements) - 1

    plan = make_plan(DATA, met, price_file())

    assert plan.is_goal(plan.start) and plan.mean_remaining == 0.0
    assert plan.risk is not None and plan.risk.success_probability.value == pytest.approx(1.0) and plan.risk.mean.value == pytest.approx(0.0)


def test_with_40_offers_or_more_auto_keeps_the_bound_pruning_until_742(monkeypatch, packed):
    """#535: on fossil-set worlds the envelope search is 1.2 to 40 times slower than the bound pruning (#696, #742) and refuses R09 (#731), so `auto`
    keeps the existing switch to the bound pruning at `MIN_OFFERS_TO_PRUNE`; `envelope` by name still searches. Both are exact."""
    monkeypatch.setattr(_plan, "MIN_OFFERS_TO_PRUNE", 2)  # R12 has 6 offers: they count as many
    real = _plan.envelope_result
    monkeypatch.setattr(_plan, "envelope_result", lambda *_a, **_k: pytest.fail("auto searched with 40 offers or more"))

    plan = make_plan(DATA, load_target(R12, DATA), price_file())

    assert plan.pruned is not None and plan.packed is None
    assert plan.mean_remaining == pytest.approx(packed.mean_remaining, rel=1e-9)
    monkeypatch.setattr(_plan, "envelope_result", real)
    assert make_plan(DATA, load_target(R12, DATA), price_file(), solver="envelope", with_risk=False).packed.info["envelope"].exact


def test_the_command_has_the_planners_solver_choices_and_auto_by_default(monkeypatch, tmp_path):
    seen = []
    real = make_plan

    def spy(*args, **kwargs):
        seen.append(kwargs.get("solver"))
        return real(*args, **kwargs)

    monkeypatch.setattr(_starts, "make_plan", spy)

    assert run(tmp_path, "--no-recipe-starts", prices=price_file())[0] == 0
    for solver in SOLVERS:
        assert run(tmp_path, "--no-recipe-starts", "--solver", solver, prices=price_file())[0] == 0

    assert seen == ["auto", *SOLVERS]


ROUTE = R12.parents[1] / "routes" / "r12-lightning-amulet.yaml"


def test_a_plan_a_route_is_judged_against_walks_under_auto_and_judges_the_route_with_no_false_gap(packed):
    """Option A of #535 (#732 is the route judged without the walk): the envelope search never decides the states it proves irrelevant, so a
    plan a given route is judged against is made on the walk, decided before solving; the route reads the same as on the packed plan."""
    judged = make_plan(DATA, load_target(R12, DATA), price_file(), judges_route=True)
    route = load_route(ROUTE, judged, DATA)

    assert judged.packed is None or "envelope" not in judged.packed.info
    assert judged.mean_remaining == pytest.approx(packed.mean_remaining, rel=1e-9)
    assert evaluate_route(judged, route, DATA).gaps == evaluate_route(packed, load_route(ROUTE, packed, DATA), DATA).gaps


def test_a_route_judged_against_an_envelope_plan_is_refused_in_words_not_read_as_gaps():
    envelope = make_plan(DATA, load_target(R12, DATA), price_file())

    with pytest.raises(PlanError, match="judged against the planner's choice at every state the route reaches"):
        evaluate_route(envelope, load_route(ROUTE, envelope, DATA), DATA)


def test_the_command_with_a_route_asks_for_a_plan_a_route_is_judged_against(monkeypatch, tmp_path):
    seen = []
    real = make_plan

    def spy(*args, **kwargs):
        seen.append(kwargs.get("judges_route"))
        return real(*args, **kwargs)

    monkeypatch.setattr(_starts, "make_plan", spy)

    assert run(tmp_path, "--route", str(ROUTE), prices=price_file())[0] == 0
    assert run(tmp_path, "--no-recipe-starts", prices=price_file())[0] == 0
    assert seen == [True, False]


def test_the_command_refuses_a_solver_it_does_not_have(capsys, tmp_path):
    with pytest.raises(SystemExit):
        main([str(R12), "--json", str(tmp_path / "p.json"), "--solver", "fast"], data=DATA, prices=price_file(), env={}, today=TODAY)

    assert "invalid choice: 'fast'" in capsys.readouterr().err


def test_the_help_says_what_each_choice_does(capsys):
    with pytest.raises(SystemExit):
        main(["--help"], data=DATA, prices=price_file(), env={}, today=TODAY)

    text = " ".join(capsys.readouterr().out.split())
    assert "--solver {auto,object,packed,envelope}" in text
    for word in ("auto (default)", "envelope:", "packed:", "object:", "same exact mean"):
        assert word in text
