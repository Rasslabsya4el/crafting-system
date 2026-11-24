"""A round its share stopped, set aside, is read against the plan the run ended with (#1559, OR-13, OR-39, OR-40, `_rounds.beaten_later`).

Such a round was cut against the plan in hand when it ran, and a plan found after it can cost less than its lower figure: R09's Augmentation
round stopped at 198.73 c against 209.71 c in hand and the run ended at 113.87 c (`.claude/scratch/t1552/R09-branch/out/rounds.json`). When
its stated lower figure reaches the final plan's certified upper figure (the search's own rule, `_envelope.reaches`), it counts as beaten,
as it would have, had that plan been in hand; it stays set aside, since beaten says nothing of plans joining its group with later offers.

Through the planner's entry, on the hand-worked belt of `test_planner_blocking_crafts.py` (its module text: 16e/3 + 2S = 153.33 with the
Exalted Orb alone, 3(c + e) + 2S = 133 with the filler crafted first). Three groups: the Exalted Orb (its plan of 153.33), a stand-in group
whose round its share stops at a lower figure the test gives, and the fillers (the plan of 133, found after the stopped round). The last round,
which holds the set-aside group again with every offer, is stopped too here, as R09's would be, so the stopped group is read only by the rule.
"""

import pytest
from test_planner_blocking_crafts import C, E, S, _prices, data, target  # noqa: F401 (the fixtures)

from crafting_system.planner import PlanSettings, _growth, _offers, _rounds, plan_target
from crafting_system.planner import _plan as planner_plan
from crafting_system.cli._route_proof import batch_line

STOP = "the time limit of 600 seconds was reached"


@pytest.fixture
def stopped_second(monkeypatch):
    """The belt in three rounds (the Exalted Orb; a stand-in group whose round raises `Stopped` at the figure set on the returned list; the
    fillers), the order kept as given, and the last round (every offer again) stopped. Returns the list to set the stopped figure in."""
    real_groups, real_make = _rounds.round_groups, planner_plan._make_plan
    figure: list[float] = []
    calls = []

    def three(offers, named, added):
        head, *rest = real_groups(offers, named, added)
        asked = tuple(i for i in head.positions if offers[i].blocks is None)
        fillers = tuple(i for i in head.positions if i not in asked)
        return (_rounds.Group(asked, (), frozenset()), _rounds.Group((), ("stand-in",), frozenset()), _rounds.Group(fillers, ("bench-craft",), head.features), *rest)

    def make(*args, round_call=None, **kwargs):
        if round_call is not None and not round_call.floors:
            calls.append(round_call)
            if len(calls) == 2:  # the stand-in group: its share ended its search before a plan of its own closed
                raise _rounds.Stopped(STOP, figure[0])
            if len(calls) == 4:  # the last round, every offer again: stopped too
                raise _rounds.Stopped(STOP, 1.0)
        return real_make(*args, round_call=round_call, **kwargs)

    monkeypatch.setattr(_growth, "GROWS", False)
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(_rounds, "round_groups", three)
    monkeypatch.setattr(_rounds, "by_floor", lambda groups, figure: list(groups))  # the order as given (the floors would put the fillers first)
    monkeypatch.setattr(planner_plan, "_make_plan", make)
    return figure


def _belt(data, target):  # noqa: F811
    return plan_target(data, target, _prices(), PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))


def test_a_stopped_round_whose_figure_reaches_the_plan_found_after_it_counts_beaten(data, target, stopped_second):  # noqa: F811
    stopped_second.append(140.0)  # under the 153.33 in hand when it ran, above the 133 found after it
    plan = _belt(data, target)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    first, stand_in, fillers, last = plan.search.widening
    assert first.upper == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9) and fillers.status == "closed" and last.status == "stopped"
    assert stand_in.status == _rounds.BEATEN and stand_in.beaten_later and stand_in.lower == 140.0 and stand_in.within is None
    assert stand_in.reason.startswith(STOP) and "beaten by the plan found after it" in stand_in.reason
    assert stand_in.document()["beaten_later"] is True and stand_in.document()["status"] == "beaten"
    # it stays set aside: beaten proves nothing of a plan that joins its group with the fillers, so the proof over every method is not claimed
    assert not stand_in.carried and not stand_in.closed and not plan.search.exact and plan.search.stopped
    line = _rounds.round_line(2, stand_in)
    assert "stopped, then beaten" in line and line.endswith("the rounds after it did not hold them)")
    page = batch_line(2, stand_in)
    assert "then beaten" in page and "the batches after it did not hold these methods" in page


def test_a_stopped_round_whose_figure_is_under_the_final_plan_stays_open(data, target, stopped_second):  # noqa: F811
    stopped_second.append(120.0)  # under the 133 the run ends with: a plan with its methods may still cost less
    plan = _belt(data, target)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    stand_in = plan.search.widening[1]
    assert stand_in.status == _rounds.STOPPED and not stand_in.beaten_later and stand_in.lower == 120.0 and not stand_in.carried
    assert "beaten_later" not in stand_in.document()
    untried = next(limit for limit in plan.limits if limit.what == "Not finished")
    assert "stand-in" in untried.labels


def _record(status=_rounds.STOPPED, lower=10.0, carried=False, growth=None):
    return _rounds.RoundRecord(("x",), 1, status, "stopped", lower, None, 0.0, carried=carried, growth=growth)


def test_the_rule_is_the_search_s_own_and_reads_only_set_aside_stopped_rounds_of_the_widening():
    # exactly at the plan's upper figure, to the certified 1e-6 (OR-32): beaten; a cent under it: open
    assert _rounds.beaten_later([_record(lower=10.0)], 10.0)[0].beaten_later
    assert _rounds.beaten_later([_record(lower=10.0 * (1 - 1e-9))], 10.0)[0].beaten_later
    assert not _rounds.beaten_later([_record(lower=9.99)], 10.0)[0].beaten_later
    # within the run's gap (OR-39): beaten within it, and said so
    gapped = _rounds.beaten_later([_record(lower=9.95)], 10.0, gap=0.01)[0]
    assert gapped.beaten_later and gapped.within == 0.01 and "to within the gap of 1.00%" in gapped.reason
    assert not _rounds.beaten_later([_record(lower=9.8)], 10.0, gap=0.01)[0].beaten_later
    # never a carried round (it may have stopped with no plan in hand, its group in no later round), a growth round, one with no figure,
    # one already closed or beaten, or a run with no plan
    untouched = [_record(carried=True), _record(growth="the seed"), _record(lower=None), _record(status=_rounds.CLOSED), _record(status=_rounds.BEATEN)]
    assert _rounds.beaten_later(untouched, 5.0) == untouched
    assert _rounds.beaten_later([_record()], None)[0].status == _rounds.STOPPED
