"""A stopped search is not a proof that no plan exists (#1168, OR-13, OR-33, OR-40), through the planner's entry, counted in states.

The fixture belt of `test_planner_blocking_crafts`: the goal is the top Life prefix, and the bench's two filler crafts add only a suffix of a
family no draw gives, so a plan made only of them never reaches the goal; an Exalted Orb does. The rounds are set by hand (`offer_groups`):
round 1 holds the fillers alone, round 2 adds the Exalted Orb.

* **Stopped.** With a states net too small for round 2, round 1 proves no plan of the fillers alone and round 2 stops before any plan of its
  own: the answer says no plan was found yet, that this does not show none exists, what round 1 showed, which net stopped round 2, and what
  the user can do. It never says that no plan of the offered actions reaches the goal: a plan exists (with the net lifted the same rounds give one).
  Round 1 itself is never stopped: its bound proves at the start that no filler reaches the goal (an infinite bound of the start is the answer
  before any net is asked, #1190), so even a net of one state lets it finish.
* **Proved.** With the fillers alone in every round, every round closes with no plan, the last over every offer: the answer is the proof.
* **One search.** A target whose offers are one search: a net that stops it before a plan says no plan found yet; with only the fillers
  offered, the search proves none and says so.
"""

import pytest
from test_planner_blocking_crafts import S, TARGET, _prices, data, every_shared_kernel_checked  # noqa: F401 (fixtures)

from crafting_system.budget import Budget
from crafting_system.planner import PlanError, PlanSettings, _offers, _rounds, plan_target
from crafting_system.planner import _plan as planner_plan
from crafting_system.targets import load_target

UNREACHABLE = "no policy of the offered actions reaches the goal"


def _target(tmp_path, data):
    path = tmp_path / "belt.yaml"
    path.write_text(TARGET, encoding="utf-8")
    return load_target(path, data)


def _settings(states: int | None, methods: tuple[str, ...] = ("exalted-orb", "bench-craft")) -> PlanSettings:
    """The run's settings: its methods (#405: the run's setting, not the target's), counted in `states` (None: no net)."""
    return PlanSettings(
        recipe_starts=False, start_price=S, solver="auto", budget=None if states is None else Budget.in_states(states), methods=methods
    )  # fmt: skip


def _by_hand(monkeypatch, *, exalted: bool):
    """Round 1 the fillers alone; round 2 adds the Exalted Orb (`exalted`), or nothing (no round reaches the goal: the last holds every offer)."""

    def groups(data, goal, target, grouped, route):
        fills = tuple(i for i, offer in enumerate(grouped) if offer.kind == "bench-craft" and "Fill" in offer.label)
        exalts = tuple(i for i, offer in enumerate(grouped) if offer.kind == "exalted-orb")
        assert fills and exalts
        second = _rounds.Group(exalts, ("exalted-orb",), frozenset()) if exalted else _rounds.Group((), ("again",), frozenset())
        return (_rounds.Group(fills, ("bench-craft",), frozenset()), second)

    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(planner_plan, "offer_groups", groups)


@pytest.mark.parametrize("states", [1, 4])
def test_through_the_entry_rounds_a_net_stops_say_no_plan_found_yet_and_never_that_none_reaches_the_goal(tmp_path, data, monkeypatch, states):
    # round 1 proves no plan of the fillers alone at its start (1 state: its bound is infinite there, #1190); 1 state: round 2 is not tried;
    # 4: round 2 stops at 3
    _by_hand(monkeypatch, exalted=True)
    target = _target(tmp_path, data)
    assert plan_target(data, target, _prices(), _settings(None)).mean_remaining == pytest.approx(133.0)  # a plan exists: 3 (c + e) + 2 S
    with pytest.raises(PlanError) as raised:
        plan_target(data, target, _prices(), _settings(states))
    said = str(raised.value)
    assert UNREACHABLE not in said and "reaches the goal" not in said
    assert said.startswith("stopped, no plan found yet: no round of the methods made a plan before the search stopped, so this does not show that no plan exists")
    assert "run again with more states or memory, or with fewer methods" in said  # counted in states: no seconds named
    assert " s)" not in said and " s:" not in said
    assert "The rounds that finished showed only that no plan made only of bench-craft reaches the target" in said
    assert "round 1 (" not in said  # a round that finished with no plan is named by what it showed, not listed as not finished
    if states == 1:
        assert "round 2 (exalted-orb; 1 actions offered, 0 states): not tried, the run's states net was used up before this round" in said
    else:
        assert "round 2 (exalted-orb; 2 actions offered, 2 states): stopped (2 states were known, the limit is 3" in said
        assert "no plan with them costs less than 133.00 Chaos" in said


def test_through_the_entry_a_net_that_stops_the_first_round_says_no_round_finished(tmp_path, data, monkeypatch):
    # the rounds the other way round: round 1 the Exalted Orb (it can reach the goal, so its bound is finite and the net can stop it), round 2
    # the fillers; 3 states stop both before a plan, and nothing is shown about any method
    def groups(data, goal, target, grouped, route):
        fills = tuple(i for i, offer in enumerate(grouped) if offer.kind == "bench-craft" and "Fill" in offer.label)
        exalts = tuple(i for i, offer in enumerate(grouped) if offer.kind == "exalted-orb")
        return (_rounds.Group(exalts, ("exalted-orb",), frozenset()), _rounds.Group(fills, ("bench-craft",), frozenset()))

    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(planner_plan, "offer_groups", groups)
    with pytest.raises(PlanError) as raised:
        plan_target(data, _target(tmp_path, data), _prices(), _settings(3))
    said = str(raised.value)
    assert UNREACHABLE not in said and "reaches the goal" not in said
    assert said.startswith("stopped, no plan found yet: no round of the methods made a plan before the search stopped")
    assert "No round finished, so nothing is shown about any method" in said
    assert "round 1 (exalted-orb; 1 actions offered, 1 states): stopped (1 states were known, the limit is 3" in said


def test_through_the_entry_rounds_that_all_finish_with_no_plan_are_the_proof(tmp_path, data, monkeypatch):
    _by_hand(monkeypatch, exalted=False)
    target = _target(tmp_path, data)
    for states in (None, 50):
        with pytest.raises(PlanError) as raised:
            plan_target(data, target, _prices(), _settings(states))
        assert str(raised.value).startswith(UNREACHABLE) and "no plan found yet" not in str(raised.value)


def test_through_the_entry_one_search_a_net_stops_says_no_plan_found_yet(tmp_path, data, monkeypatch):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", False)  # the offers are one search, not rounds
    target = _target(tmp_path, data)
    assert plan_target(data, target, _prices(), _settings(None)).search.widening == ()
    for states in (1, 3):
        with pytest.raises(PlanError) as raised:
            plan_target(data, target, _prices(), _settings(states))
        said = str(raised.value)
        assert "reaches the goal" not in said
        assert said.startswith("stopped, no plan found yet: the search found no plan before it stopped, so this does not show that no plan exists (the search stopped (")
        assert "no plan costs less than 145" in said and "run again with a larger time, states or memory limit" in said and said.endswith("or with fewer methods: a search over fewer methods is smaller and may finish where this one stopped")


def test_through_the_entry_one_search_that_finishes_with_no_plan_is_the_proof(tmp_path, data, monkeypatch):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)  # the fillers, offered by the rule: the only priced actions of a target naming the bench
    target = _target(tmp_path, data)
    for states in (None, 50):
        with pytest.raises(PlanError) as raised:
            plan_target(data, target, _prices(), _settings(states, ("bench-craft",)))
        assert str(raised.value).startswith(UNREACHABLE) and "no plan found yet" not in str(raised.value)


def test_the_words_name_the_net_a_run_on_the_clock_has_and_no_stop_leaves_the_proof_or_the_refusal_as_it_is():
    # a user's run is on the clock (no states net): its rounds name seconds, and the advice is more time; with no round stopped or untried
    # there are no such words (every round showed no plan: the proof; or one was refused: the refusal says itself)
    from crafting_system.planner._envelope import NoPolicy
    from crafting_system.planner._plan import envelope_refusal

    record = lambda status, reason="": _rounds.RoundRecord(("alteration",), 3, status, reason, None, None, 12.0)  # noqa: E731
    said = _rounds.no_plan_words([record(_rounds.NONE), record(_rounds.STOPPED, "the search stopped at the time limit of 300 s (301 s spent)")])
    assert "no plan made only of alteration reaches the target" in said and "more time or memory" in said
    assert "round 2 (alteration; 3 actions offered, 12 s): stopped (the search stopped at the time limit of 300 s (301 s spent)), with no plan" in said
    said = _rounds.no_plan_words([record(_rounds.STOPPED, "1 states were known, the limit is 1"), record(_rounds.UNTRIED, "the run's time was used up before this round")])
    assert "No round finished, so nothing is shown about any method" in said
    assert "round 1 (alteration; 3 actions offered, 12 s): stopped (1 states were known, the limit is 1), with no plan" in said
    assert "round 2 (alteration; 3 actions offered, 12 s): not tried, the run's time was used up before this round" in said
    assert _rounds.no_plan_words([record(_rounds.NONE), record(_rounds.NONE)]) is None
    assert _rounds.no_plan_words([record(_rounds.NONE), record(_rounds.REFUSED, "a refusal")]) is None
    assert _rounds.no_plan_words([record(_rounds.STOPPED, "a memory net"), record(_rounds.NONE)]) is None  # the last round held every offer
    # one search: the net's words may sit on the search's own refusal under the note of a bound cut short (`envelope_result`)
    inner = NoPolicy("the search stopped", stopped="the time limit of 30 seconds was reached", lower=120.0)
    outer = NoPolicy("the bound was cut short")
    outer.__cause__ = inner
    for solver in ("auto", "envelope"):
        assert envelope_refusal(solver, outer).startswith("stopped, no plan found yet: the search found no plan before it stopped")
    assert envelope_refusal("auto", NoPolicy("no policy of the offers reaches the goal from the start")).startswith(UNREACHABLE)
    # a stopped search whose plan could not be certified found a plan: neither "no route" nor "none found"
    from crafting_system.solver import ConvergenceError

    uncertified = NoPolicy("the search stopped and the plan it had found cannot be solved to a certified cost", stopped="the time limit", lower=1.0)
    uncertified.__cause__ = ConvergenceError("not certified", 1e-3)
    assert envelope_refusal("auto", uncertified).startswith("a plan was found, but its average cost could not be worked out")
    assert envelope_refusal("envelope", uncertified).startswith("the envelope search cannot answer this target")
