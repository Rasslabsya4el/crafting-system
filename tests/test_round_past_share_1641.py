"""A search with a plan in hand goes past its share while its plan still falls, never past one more share (ticket #1641, OR-39, OR-40).

At the ten-minute net a round of R08 (104 offers) and of R09 (115 offers) held a plan of the run and searched for about 22 s of a 30 s share;
its third search round made the cheap plan (R08 174.84 c, R09 119.01 c) and ended at 15 to 22 s, or a second later, past the share, and then
the run kept 278.26 c and 214.86 c (14 saved runner logs, `.claude/scratch/handoff-t1641.md`). The rule (`Net.beyond`, `Search._lowering`,
`_plan.search_net`): from each standing on, a search whose plan is below the one of the standing before by more than the run's gap may go on
past its share by the room a nearly done build has (`late`: at most one more share, at most half of what the rounds after it have); one whose
last round lowered nothing stops at its share as before.

Every test counts the work in states (a run counted in states, `Net.pieces` set): no test reads a clock. The world is a random graph of
`test_envelope_gap_stop` whose plan falls at its search rounds 2, 3, 5 and 7 (seed 2, a bound at 30% of the exact values), traced below
with no net: (round, states known, plan's cost).
"""

import pytest
from test_envelope_gap_stop import world

from crafting_system.budget import Budget
from crafting_system.planner._envelope import Net, Search
from crafting_system.planner._envelope_plan import beyond_after_build
from crafting_system.planner._plan import search_net

GAP = 0.01  # the run's gap a fall must pass (OR-39)


def falling_world():
    return world(2, 0.3)[2]


def run(states: int, beyond: int | None):
    """The search counted in `states` (its share), with `beyond` more states while its plan falls (None: the rule is off)."""
    trace: list[tuple[int, int, float | None]] = []
    net = Net(states=states, pieces=1, beyond=None if beyond is None else (None, beyond, GAP))
    result = Search(falling_world(), net=net, gap=1e-9, gap_after=0.0, watch=lambda s: trace.append((s.rounds, s.states, s.upper))).run()
    return result, trace


def test_the_world_falls_where_the_tests_read_it():
    _, trace = run(10_000, None)
    assert [(r, n) for r, n, _ in trace[:8]] == [(0, 22), (1, 22), (2, 22), (3, 24), (4, 26), (5, 30), (6, 30), (7, 31)]
    uppers = [u for _, _, u in trace[:8]]
    assert uppers[2] == pytest.approx(87.19707315686884) and uppers[3] == pytest.approx(29.47729815014795)
    assert uppers[4] == uppers[3]  # round 4 lowers nothing
    assert uppers[5] == pytest.approx(23.547422026998795)


def test_a_search_whose_last_round_lowered_its_plan_goes_past_its_share_and_keeps_the_cheaper_plan():
    # share 23: rounds 2 (302.69 -> 87.20) and 3 (-> 29.48, 24 states) lowered the plan, so the search goes on to round 4, which lowers
    # nothing (26 states): there it stops, past its share by 3 states of its 10, with 29.48 where the share alone kept 87.20
    alone, _ = run(23, None)
    wide, trace = run(23, 10)
    assert alone.stats.touched <= 23 and alone.upper == pytest.approx(87.19707315686884)
    assert wide.upper == pytest.approx(29.47729815014795)
    assert 23 < wide.stats.touched <= 26
    assert trace[-1][:2] == (4, 26)


def test_a_search_whose_last_round_lowered_nothing_stops_at_its_share_as_before():
    # share 29: round 4 (26 states) lowered nothing, so round 5's walk meets the share as it does with no rule (at 28 states: the next
    # action's outcomes would pass 29), and both keep the plan the stop priced, 23.55
    alone, alone_trace = run(29, None)
    wide, wide_trace = run(29, 10)
    assert wide.stats.touched == alone.stats.touched <= 29
    assert wide.upper == alone.upper == pytest.approx(23.547422026998593)
    assert wide_trace == alone_trace


@pytest.mark.parametrize("share", range(22, 40))
@pytest.mark.parametrize("beyond", [0, 1, 2, 5, 10])
def test_no_search_knows_more_than_its_share_and_its_room(share, beyond):
    result, _ = run(share, beyond)
    alone, _ = run(share, None)
    assert result.stats.touched <= share + beyond
    assert result.upper <= alone.upper  # going on never loses the plan in hand


def test_the_room_is_one_more_share_at_most_and_half_of_what_the_rounds_after_have():
    class Clock:  # a run counted in states: the clock's states left, never its seconds
        budget = Budget.in_states(1_000, gap=GAP)

        def left(self):
            return None

        def states_left(self):
            return 1_000

    clock = Clock()
    assert search_net(clock, 1, held=True).beyond is None  # the last round has all the states left: no room past them
    assert search_net(clock, 2, held=True).beyond == (None, 250, GAP)  # a growth round: half a share, what the round after it keeps half of
    assert search_net(clock, 5, held=True).beyond == (None, 200, GAP)  # one more share, no more
    assert search_net(clock, 5, walked=True).beyond == (None, 200, GAP)
    assert search_net(clock, 5).beyond is None  # no plan in hand: the share holds (`Net.blind`, `Share` decide those rounds)


def test_on_the_clock_the_build_takes_its_time_out_of_the_room():
    net = Net(seconds=30.0, late=1.0, beyond=(30.0, None, GAP))
    assert beyond_after_build(net, 8.0) == (30.0, None, GAP)  # search 22 s, then up to 30 s more while its plan falls: the round ends by 60 s
    assert beyond_after_build(net, 40.0) == (20.0, None, GAP)  # a build past the share left 20 s of the 60
    assert beyond_after_build(net, 70.0) == (0.0, None, GAP)
    assert beyond_after_build(Net(seconds=30.0), 8.0) is None


def test_on_the_clock_the_share_widens_by_its_seconds_only_after_a_search_round_lowered_the_plan():
    # the seconds side of the rule, stood by hand (no clock is read for the net: `_lowering` reads the standings' plans only)
    search = Search(falling_world(), net=Net(seconds=20.0, beyond=(10.0, None, GAP)))
    stand = [(0, 302.69), (1, 302.69), (2, 87.20), (3, 87.0), (4, 60.0)]  # (rounds, plan): first plan, round 1, falls, a fall under 1%, a fall
    seen = []
    for rounds, plan in stand:
        search.stats.rounds, search.upper = rounds, plan
        search._stand(0.0, 0.0)
        seen.append(search.net.seconds)
    assert seen == [20.0, 20.0, 30.0, 20.0, 30.0]  # never past share + room, back to the share once a round lowers by no more than the gap
