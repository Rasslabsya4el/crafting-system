"""A round with no plan in hand whose bound's build ends before it is complete gives way at its share (#1268, OR-33, OR-40).

Until #1268 a round that began with no plan in hand took all the time left until its search held a plan: the answer must hold one (OR-33),
and a later round was taken not to give one sooner. R04's site plan broke that: its bench crafts' round (the eighth) built for the quarter of
the time left, was not complete, and searched the rest with no plan; on main after #973 its bench crafts' round was refused and the fossil
sets' round took the 321 s left the same way. The rounds that hold the guide's methods (essences, the Exalted and the Fracturing Orb) were
never tried. Now such a round keeps its build's quarter, and a search on a bound not complete gives way once it has used the round's share
(the time left over the rounds left, from the search's own start) with no plan in hand (`_envelope.Net.yield_at`, `_envelope.YIELDED`). A round that gave way runs again, with all the time left, when no round after it made
a plan, and under its share once a round after it made the first plan (`_rounds.widen`). Every figure here is counted in states or read off a clock set by the test (never the machine's)."""

from types import SimpleNamespace

import pytest

from crafting_system.planner import _envelope, _envelope_plan, _rounds
from crafting_system.planner import _plan as planner_plan
from crafting_system.planner._envelope import YIELDED


def _widen(groups, search, given=100):
    meter = _rounds.StatesMeter(given)
    return _rounds.widen(
        groups, tuple(range(len(groups))), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: pytest.fail("a run counted in states reads no time left"),
        clock_now=lambda: 0.0, meter=meter,
    )  # fmt: skip


def _gave_way(states: int) -> _rounds.Stopped:
    stop = _rounds.Stopped(f"{YIELDED} ({states} states known)", None)
    stop.states = states  # what its search knew (`_rounds.states_of`)
    return stop


def _none(states: int) -> _rounds.NoPlan:
    none = _rounds.NoPlan("no plan of these offers alone reaches the target")
    none.states = states
    return none


def _plan(cost: float, states: int):
    return SimpleNamespace(search=SimpleNamespace(lower=cost, touched=states), mean_remaining=cost)


GROUPS = tuple(_rounds.Group((i,), (kind,), frozenset({"junk"})) for i, kind in enumerate(("alone", "bench", "essence")))


def test_a_round_that_gives_way_with_no_plan_leaves_the_rounds_after_it_their_turn_and_does_not_join_the_base():
    # 100 states, three rounds. Round 1 (offer 0) shows no plan of its offer: 4 states, and it joins the base. Round 2 (offers 0 and 1) begins
    # with no plan in hand and two rounds left (`blind` 2): its build is not complete and its search gives way with no plan at its share
    # (96 // 2 = 48 states). Round 3 (offers 0 and 2, not 1: a round that gave way is not in the base) is the last: all the 48 states left,
    # no `blind`, and it makes the first plan, 10. Round 2's group then runs again after it (a round that gave way is in no later round's
    # offers otherwise), with the base round 3 closed into (offers 0, 1 and 2), the states left and no `blind`, and finds the cheaper plan, 7.
    calls = []

    def search(chosen, call):
        calls.append((chosen, call.blind, call.states))
        if chosen == (0,):
            raise _none(4)
        if 1 in chosen and call.blind is not None:
            raise _gave_way(call.states // call.blind)
        if 1 in chosen:
            return _plan(7.0, 5)
        return _plan(10.0, 20)

    widened = _widen(GROUPS, search)
    assert calls == [((0,), 3, 100), ((0, 1), 2, 96), ((0, 2), None, 48), ((0, 1, 2), None, 28)]
    assert [record.status for record in widened.records] == [_rounds.NONE, _rounds.STOPPED, _rounds.CLOSED, _rounds.CLOSED]
    assert widened.records[1].reason.startswith(YIELDED) and widened.records[1].states == 48
    assert widened.records[1].reason.endswith("a round after it made the first plan, so it ran again after the rounds left")
    assert widened.plan.mean_remaining == 7.0


def test_a_round_that_gave_way_runs_again_with_all_that_is_left_when_no_round_after_it_made_a_plan():
    # The rounds above, but round 3 shows no plan of its offers either (10 states), and joins the base. The queue has ended with no plan in
    # hand, so round 2's group runs again after it, with the base it closed into (offers 0, 1 and 2), all the 38 states left and no `blind`:
    # this time its search may take them all, as every round with no plan in hand did before #1268, and it makes the plan, 30 (OR-33).
    calls = []

    def search(chosen, call):
        calls.append((chosen, call.blind, call.states))
        if chosen == (0,):
            raise _none(4)
        if 1 in chosen and call.blind is not None:
            raise _gave_way(call.states // call.blind)
        if 1 not in chosen:
            raise _none(10)
        return _plan(30.0, 38)

    widened = _widen(GROUPS, search)
    assert calls == [((0,), 3, 100), ((0, 1), 2, 96), ((0, 2), None, 48), ((0, 1, 2), None, 38)]
    assert [record.status for record in widened.records] == [_rounds.NONE, _rounds.STOPPED, _rounds.NONE, _rounds.CLOSED]
    assert widened.records[1].reason.endswith("the rounds after it made no plan, so it ran again after the last")
    assert widened.plan.mean_remaining == 30.0


def test_a_round_with_a_plan_in_hand_or_the_last_round_has_no_blind_share():
    # `blind` is for a round with no plan in hand and other rounds after it: round 1 of three has it (3), round 2 holds round 1's plan and
    # has none, nor has round 3, the last; the search's net carries it only then (`_plan.search_net`).
    calls = []

    def search(chosen, call):
        calls.append(call.blind)
        return _plan(10.0 - len(chosen), 5)

    _widen(GROUPS, search)
    assert calls == [3, None, None]
    assert _plan_net(blind=3).blind == 3 and _plan_net(blind=1).blind is None and _plan_net(blind=3, held=True).blind is None


def _plan_net(**kwargs):
    from crafting_system.budget import Budget, Clock

    return planner_plan.search_net(Clock(Budget.in_states(90)), **kwargs)


def test_the_build_of_a_round_with_no_plan_in_hand_keeps_its_whole_quarter_whatever_the_rounds_left(monkeypatch):
    # On a clock set here: a round with no plan in hand and 10 rounds left, its net the 100 s left. Its build is not cut to its share (10 s):
    # it has the quarter (25 s), as every round with no plan in hand had before #1268. R10's and R13's first plans come from such a build,
    # not complete, that took its whole quarter (149 s, 146 s) and then held the plan in seconds; cut to the share, both had no plan.
    now = [0.0]
    monkeypatch.setattr(_envelope_plan.time, "perf_counter", lambda: now[0])
    net = _envelope.Net(seconds=100.0, blind=10)
    assert _envelope_plan.room_of(net) is None
    stop = _envelope_plan.build_stop(net, 0.0)
    now[0] = 24.9
    assert stop() is None
    now[0] = 25.0
    assert stop() is not None


def test_a_search_with_no_plan_in_hand_gives_way_at_its_share_and_one_that_holds_a_plan_does_not():
    # A world by hand (`test_envelope_gap_stop.Hand`), no restart. At the start the bound sends the first plan's chain to state 5, a loop that
    # never reaches the goal (offer 1, 0.1); offer 2 (10) reaches the goal 9 at once. With `Net.yield_at` of 2 states (a round's share on a
    # bound not complete, set by `_envelope_plan`) the search knows the start and state 5, holds no plan, and gives way with `YIELDED`; with
    # no `yield_at` it goes on and proves the plan of 10. A search that holds a plan (the chain sent to the goal) does not give way there.
    from test_envelope_gap_stop import Hand

    def world(first: int):
        return Hand(
            goal={9}, costs={1: 0.1, 2: 10.0}, actions={0: {1: {5: 1}, 2: {9: 1}}, 5: {1: {5: 1}}, 9: {}},
            la={(0, 1): 0.1 if first == 1 else 20.0, (0, 2): 10.0, (5, 1): 0.1}, lb={0: 0.0, 5: 0.0, 9: 0.0},
        )  # fmt: skip

    with pytest.raises(_envelope.NoPolicy) as stopped:
        _envelope.Search(world(1), net=_envelope.Net(states=100, yield_at=(None, 2))).run()
    assert stopped.value.stopped == f"{YIELDED} (2 states known)"
    assert _envelope.Search(world(1), net=_envelope.Net(states=100)).run().exact
    held = _envelope.Search(world(2), net=_envelope.Net(states=100, yield_at=(None, 1))).run()
    assert held.exact


GROUPS5 = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate("abcde"))


def _first_plan_then(floor, *, meter=None, left=lambda: 600.0, clock_now=lambda: 0.0):
    def search(chosen, call):
        assert not call.floors
        return SimpleNamespace(search=SimpleNamespace(lower=1.0, touched=100), mean_remaining=100.0 if chosen == ("a",) else 90.0)

    return _rounds.widen(
        GROUPS5, tuple("abcde"), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.CLOSED, ""), left=left, clock_now=clock_now, meter=meter, floor=floor,
    )  # fmt: skip


def test_counted_in_states_the_order_pass_shares_one_round_s_states_among_its_groups_and_a_group_it_cannot_finish_goes_last():
    # #1241 (R20's site plan: the floors pass took 228 s of the 600 s net, each of its 16 groups a whole share). 600 states; round 1 (a) makes
    # the first plan knowing 100, so 500 are left for the 4 rounds left: one round's share is 125 states, and each group's floors have a
    # quarter of it, 31 (their pieces of work follow from them, `_plan.search_net`). The floors of b, d and e need 10, 5 and 1 states' worth
    # and give 75, 75 and 50; c's need 40, more than its 31: no figure, and c goes last although its figure would be the lowest (10).
    needs = {"b": (10, 75.0), "c": (40, 10.0), "d": (5, 75.0), "e": (1, 50.0)}
    asked = []

    def floor(chosen, call):
        asked.append((chosen[-1], call.states, call.seconds))
        need, figure = needs[chosen[-1]]
        return figure if need <= call.states else None

    widened = _first_plan_then(floor, meter=_rounds.StatesMeter(600), left=lambda: pytest.fail("counted in states: no time read"))
    assert asked == [("b", 31, None), ("c", 31, None), ("d", 31, None), ("e", 31, None)]
    assert [record.kinds for record in widened.records][:5] == [("a",), ("e",), ("b",), ("d",), ("c",)]


def test_on_the_clock_the_order_pass_takes_one_round_s_share_and_the_groups_it_did_not_reach_go_last_in_their_order():
    # The same rounds on a clock set here: 600 s left and 4 rounds left after round 1, so the pass has 150 s. Each floors call is asked with
    # what is left of them (150, 90, 30 s) and takes 60 s; then the 150 s are used and e is not asked: b, c, d by their figures, e last.
    now = [0.0]
    figures = {"b": 75.0, "c": 10.0, "d": 50.0, "e": 1.0}
    asked = []

    def floor(chosen, call):
        asked.append((chosen[-1], call.seconds))
        now[0] += 60.0
        return figures[chosen[-1]]

    widened = _first_plan_then(floor, left=lambda: 600.0, clock_now=lambda: now[0])
    assert asked == [("b", 150.0), ("c", 90.0), ("d", 30.0)]
    assert [record.kinds for record in widened.records][:5] == [("a",), ("c",), ("d",), ("b",), ("e",)]
