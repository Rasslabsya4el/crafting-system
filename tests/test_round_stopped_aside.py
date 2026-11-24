"""A round its share stopped while a plan was in hand, that did not lower it, is set aside and held again by the last round (#1500, OR-13,
OR-39, OR-40, `_rounds.widen`).

Before #1500 such a round joined no later round and kept the last round, the one that holds every set-aside group with the base, from ever
being due (`_rounds._all_ended`): no round held every offer, and the answer could never be proved over every method. R12 (the lightning
amulet): the Harvest likelihood round stopped at its share of 142.7 s with the 235.04 c Chaos plan in hand, so its 4 offers and the 6
resistance swaps set aside before it were searched with the plan's Harvest reforge in no round, though the missing mods' table of a round
holding all 9,297 offers reaches the plan's own cost (39.93 c after the 1 c start) at once (`.claude/scratch/t1500/P1`).

The world here is three groups over three offers, a run with no net (the clock is the test's): offer 0 the base (its plan costs 10), offer 1
the group whose round stops, offer 2 a group beaten by the plan in hand. The rounds' searches are stand-ins that raise what a round raises.
"""

from types import SimpleNamespace

import pytest

from crafting_system.planner import _rounds

GROUPS = tuple(_rounds.Group((i,), (kind,), frozenset({"junk"})) for i, kind in enumerate(("base", "likelihood", "swap")))


def _widen(search):
    return _rounds.widen(
        GROUPS, tuple(range(len(GROUPS))), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: None, clock_now=lambda: 0.0,
    )  # fmt: skip


def _plan(cost: float):
    return SimpleNamespace(search=SimpleNamespace(lower=cost, touched=None), mean_remaining=cost)


def _world(stops, last_closes=True, stopped_plan=None):
    """The base alone gives the plan of 10; a round holding offer 1 and not every offer raises `stops` (its share ended) or, with
    `stopped_plan`, gives that plan with its search stopped; a round holding every offer is beaten by the plan in hand when `last_closes`, else
    its share stops it too; the base with offer 2 is beaten."""
    seen = []

    def search(chosen, call):
        seen.append(chosen)
        if chosen == (0,):
            return _plan(10.0)
        if chosen == (0, 1, 2):
            if last_closes:
                raise _rounds.Beaten(call.upper)
            raise _rounds.Stopped("the time limit was reached", 3.0)
        if 1 in chosen:
            if stopped_plan is not None:
                return stopped_plan
            raise stops
        raise _rounds.Beaten(call.upper)

    return search, seen


def test_a_round_stopped_with_the_plan_in_hand_is_set_aside_and_the_closed_last_round_proves_the_plan_over_every_method():
    search, seen = _world(_rounds.Stopped("the time limit of 142.703 seconds was reached", 4.0))
    widened = _widen(search)
    assert seen == [(0,), (0, 1), (0, 2), (0, 1, 2)]  # the last round holds the stopped group with every other offer
    stopped = widened.records[1]
    assert stopped.status == _rounds.STOPPED and stopped.carried and stopped.held_again and stopped.closed
    assert "the last round held them again, with every method" in stopped.reason
    assert stopped.document()["held_again"] is True
    assert _rounds.all_closed(widened.records)
    assert widened.plan.mean_remaining == 10.0


def test_when_the_last_round_does_not_close_the_stopped_round_stays_open_and_is_named_set_aside():
    search, seen = _world(_rounds.Stopped("the time limit was reached", 4.0), last_closes=False)
    widened = _widen(search)
    assert seen[-1] == (0, 1, 2)
    stopped = widened.records[1]
    assert stopped.status == _rounds.STOPPED and not stopped.carried and not stopped.held_again and not stopped.closed
    assert "held_again" not in stopped.document()
    assert not _rounds.all_closed(widened.records)
    line = _rounds.round_line(2, stopped)
    assert line.endswith("(with the methods of the rounds before it; the rounds after it did not hold them)")


def test_a_stopped_round_that_lowered_the_plan_is_not_set_aside_and_no_last_round_is_due():
    # its plan of 6 is cheaper than the 10 in hand: kept, and the round is neither set aside nor in the base, as before #1500, so the proof
    # over every method stays out of reach (`_all_ended`)
    search, seen = _world(None, stopped_plan=SimpleNamespace(search=SimpleNamespace(lower=2.0, touched=None), mean_remaining=6.0))
    widened = _rounds.widen(
        GROUPS, tuple(range(len(GROUPS))), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.STOPPED, "stopped") if plan.mean_remaining == 6.0 else (_rounds.CLOSED, ""), left=lambda: None,
        clock_now=lambda: 0.0,
    )  # fmt: skip
    assert widened.plan.mean_remaining == 6.0
    assert (0, 1, 2) not in seen
    assert widened.records[1].carried and not widened.records[1].closed
    assert not _rounds.all_closed(widened.records)


def test_a_stopped_round_with_no_plan_in_hand_still_keeps_the_last_round_from_being_due():
    # four groups: the base's round stops with no plan in hand (it is the base all the same, and not set aside); offer 1 makes the plan of 10;
    # offer 2 is beaten before the last round and set aside; offer 3 is beaten in the last. The stopped round proved nothing and no plan was
    # in hand to set it aside against, so no round of every offer is added, as before #1500
    groups = (*GROUPS[:2], _rounds.Group((2,), ("swap",), frozenset({"junk"})), _rounds.Group((3,), ("fossil",), frozenset({"junk"})))
    seen = []

    def search(chosen, call):
        seen.append(chosen)
        if chosen == (0,):
            raise _rounds.Stopped("the time limit was reached", None)
        if chosen == (0, 1):
            return _plan(10.0)
        raise _rounds.Beaten(call.upper)

    widened = _rounds.widen(
        groups, tuple(range(len(groups))), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: None, clock_now=lambda: 0.0,
    )  # fmt: skip
    assert seen == [(0,), (0, 1), (0, 1, 2), (0, 1, 3)]
    assert widened.records[0].status == _rounds.STOPPED and widened.records[0].carried and not widened.records[0].closed
    assert not widened.records[2].carried
    assert not _rounds.all_closed(widened.records)


@pytest.mark.parametrize("status", [_rounds.CLOSED, _rounds.WITHIN, _rounds.BEATEN, _rounds.NONE])
def test_held_again_is_read_only_for_a_stopped_round(status):
    record = _rounds.RoundRecord(("x",), 1, status, "", None, None, 0.0)
    assert record.closed and "held_again" not in record.document()
    assert not _rounds.RoundRecord(("x",), 1, _rounds.STOPPED, "", None, None, 0.0).closed
    assert not _rounds.RoundRecord(("x",), 1, _rounds.STOPPED, "", None, None, 0.0, carried=False, held_again=True).closed


def test_a_last_round_that_finds_a_cheaper_plan_is_the_answer_and_still_closes_the_stopped_round():
    # the round of every offer finds a plan of 7 (offer 1 with offer 2): it holds every offer, so its proof covers the stopped group
    seen = []

    def search(chosen, call):
        seen.append(chosen)
        if chosen == (0,):
            return _plan(10.0)
        if chosen == (0, 1, 2):
            return _plan(7.0)
        if 1 in chosen:
            raise _rounds.Stopped("the time limit was reached", 4.0)
        raise _rounds.Beaten(call.upper)

    widened = _widen(search)
    assert seen[-1] == (0, 1, 2) and widened.plan.mean_remaining == 7.0
    assert widened.records[1].held_again and _rounds.all_closed(widened.records)
