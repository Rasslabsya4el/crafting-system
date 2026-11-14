"""The upper side of the envelope search and its stop at a proved gap (ticket #826, OR-32, OR-12, OR-13), on hand-worked worlds and random graphs.

The stop is sound when two things hold and not otherwise (`planner/_envelope.py`, "The stop at a proved gap"): the lower figure is a lower bound of
the cheapest plan, and the upper figure is the exact cost of a plan that can be executed. Then `mean(plan) <= U <= (1 + eps) L <= (1 + eps) V*`.

* three worlds small enough to work out by hand: the numbers of the first plan, of `L(root)` after it, of the stop and of the exact answer are
  written beside each test;
* two controls that fail: an upper figure that is not the cost of the plan returned, and a lower figure above the cheapest plan, each end the search
  on a plan that costs more than `(1 + eps) V*`, and the same check that passes everywhere else catches both;
* random graphs with a noisy bound that is still admissible and consistent (`Noisy`: it orders the offers of a state wrongly, so the first plan is
  often not the optimal one), for gaps from 0.1% to 30%: every answer is exact or within its gap of the dense optimum; `gap = 0`, and a gap whose time has
  not come, are the exact search; a stop builds no more than the exact search does;
* what a caller reads while the search runs (`watch`, `Search.standing`, `Search.plan_now`): the lower figure never above the optimum, the upper never below, the
  two closing in;
* a given start item (no restart): the first plan closes by itself, so a stop at a gap and a net both return it;
* an upper solve the solver cannot certify makes the stop wait, and the wait is counted.

The crafting problem on the fixture worlds, and what the plan and its limits say, are `tests/test_envelope_gap_stop_plan.py`.
"""

import math
from dataclasses import dataclass, field

import pytest
from envelope_support import ExplicitProblem, Graph, dense_optimum, q_value, random_graph
from test_cli_envelope import TOLERANCE, answer, check_exact

from crafting_system.planner import _envelope
from crafting_system.planner._envelope import SLACK, Net, NoPolicy, Refused, Search, Standing
from crafting_system.solver import ConvergenceError

SEEDS = range(12)
SIZE = 60


@dataclass
class Hand:
    """A world written out by hand: `actions[state][offer]` is the kernel, `la[(state, offer)]` and `lb[state]` the bounds the test chooses."""

    goal: set[int]
    costs: dict[int, float]
    actions: dict[int, dict[int, dict[int, int]]]
    la: dict[tuple[int, int], float]
    lb: dict[int, float]
    restart: int | None = None
    start: int = 0
    asked: list[tuple[int, int]] = field(default_factory=list)

    def is_goal(self, state: int) -> bool:
        return state in self.goal

    def lower(self, state: int) -> float:
        return self.lb[state]

    def candidates(self, state: int) -> list[tuple[float, int]]:
        return [(self.la[state, offer], offer) for offer in self.actions[state]]

    def cost(self, position: int) -> float:
        return self.costs[position]

    def kernel_key(self, state: int, position: int):
        return None

    def kernel(self, state: int, position: int) -> dict[int, int]:
        if position not in self.actions[state]:
            raise Refused
        self.asked.append((state, position))
        return dict(self.actions[state][position])

    def release(self) -> None:
        pass


# ---- world 1: two ways to finish, the bound prefers the dearer one ---------------------------------------------------------------------
#
# Start 0, goal 9, the start item given (no restart). Offer 1 costs 100 and finishes; offer 2 costs 99.5 and finishes: V* = 99.5.
# The bound puts offer 1 at 99.2 and offer 2 at 99.3 (both below their true cost), and the start at 99.2.
# The first plan takes the least bound, offer 1: U = 100. After it the start holds offer 1 (100) and a fake action for offer 2 (99.3): L = 99.3.
# U / L - 1 = 0.705%.  A stop at 1% returns offer 1 at 100 (0.503% above the optimum); a stop at 0.5% goes on, builds offer 2: exact, 99.5.


def two_finishes(**changes) -> Hand:
    world = Hand(
        goal={9}, costs={1: 100.0, 2: 99.5}, actions={0: {1: {9: 1}, 2: {9: 1}}, 9: {}},
        la={(0, 1): 99.2, (0, 2): 99.3}, lb={0: 99.2, 9: 0.0},
    )  # fmt: skip
    for name, value in changes.items():
        setattr(world, name, value)
    return world


def test_world_1_a_stop_at_one_percent_returns_the_first_plan_with_its_exact_cost_and_the_proof():
    world = two_finishes()
    result = Search(world, gap=0.01, gap_after=0.0).run()
    assert not result.exact and result.stopped is None and result.within == 0.01 and not result.restarts
    mean, plan = answer(result)
    assert mean == 100.0 and plan == {0: 1}  # the plan shown and its exact mean
    assert result.lower == pytest.approx(99.3, rel=1e-8) and result.lower <= 99.3  # no plan costs less
    assert result.upper == pytest.approx(100.0, rel=1e-8) and result.upper >= mean
    assert mean <= 1.01 * 99.5  # within 1% of the cheapest, 99.5
    assert world.asked == [(0, 1)]  # offer 2 was never built
    assert result.stats.first_upper == pytest.approx(100.0) and result.stats.seeded == 1 and result.stats.rounds == 1


def test_world_1_a_stop_at_half_a_percent_goes_on_to_the_exact_answer():
    world = two_finishes()
    result = Search(world, gap=0.005, gap_after=0.0).run()  # 100 > 1.005 * 99.3 = 99.7965
    assert result.exact and result.within is None
    mean, plan = answer(result)
    assert mean == 99.5 and plan == {0: 2}
    assert sorted(world.asked) == [(0, 1), (0, 2)]


@pytest.mark.parametrize("options", [{}, {"gap": 0.0, "gap_after": 0.0}, {"gap": 0.01}, {"gap": 0.01, "gap_after": 1e9}])
def test_world_1_no_gap_or_a_gap_whose_time_has_not_come_is_the_exact_search(options):
    result = Search(two_finishes(), **options).run()
    assert result.exact and answer(result) == (99.5, {0: 2})


# ---- world 2: a roll with a junk outcome, the start item bought ------------------------------------------------------------------------
#
# Start 0, good 1, junk 2, goal 9. Offer 0 is the restart (10: the start item again). Offer 1 at the start costs 1 and gives 1 with chance 1/4,
# 2 with 3/4. At 1 offer 2 costs 5 and finishes. At 2 offer 3 costs 60 and finishes, or the restart.
#   Fixing the junk:  v = 1 + 5/4 + 3/4 * 60 = 47.25.     Restarting from it:  v = 1 + 5/4 + 3/4 * (10 + v)  ->  v = 39.     V* = 39.
# The bound: the fix at 20, so the junk at 20, the start at 1 + 5/4 + 3/4 * 20 = 17.25, the restart from the junk at 10 + 17.25 = 27.25.
# The first plan takes the least bound at each state: roll, finish, and at the junk the fix (20 < 27.25). Its own cost is 47.25, but the plan
# that can be executed on what it built also holds the restart at every state: the best of them restarts from the junk, U = 39.
# After it: L(junk) = min(60, the fake 27.25) = 27.25, L(start) = 1 + 5/4 + 3/4 * 27.25 = 22.6875.   U / L - 1 = 71.9%.
# A stop at 75% returns the restart plan at 39; a stop at 50% builds the restart at the junk, and the lower graph then closes: exact, 39.


def junk_roll() -> Hand:
    return Hand(
        goal={9}, costs={0: 10.0, 1: 1.0, 2: 5.0, 3: 60.0}, restart=0,
        actions={0: {1: {1: 1, 2: 3}}, 1: {0: {0: 1}, 2: {9: 1}}, 2: {0: {0: 1}, 3: {9: 1}}, 9: {}},
        la={(0, 1): 17.25, (1, 0): 27.25, (1, 2): 5.0, (2, 0): 27.25, (2, 3): 20.0}, lb={0: 17.25, 1: 5.0, 2: 20.0, 9: 0.0},
    )  # fmt: skip


def test_world_2_the_upper_side_is_the_best_plan_of_what_was_built_with_the_restart_and_it_is_evaluated_exactly():
    world = junk_roll()
    result = Search(world, gap=0.75, gap_after=0.0).run()
    assert not result.exact and result.within == 0.75 and result.restarts
    mean, plan = answer(result)
    assert mean == pytest.approx(39.0, rel=1e-12)
    assert plan == {0: 1, 1: 2, 2: 0}  # roll, finish the good one, buy a new base on the junk
    assert result.lower == pytest.approx(22.6875, rel=1e-8) and result.lower <= 22.6875
    assert result.stats.first_upper == pytest.approx(39.0)
    assert sorted(world.asked) == [(0, 1), (1, 2), (2, 3)]  # the restart's kernel is the search's own; nothing else was built


def test_world_2_a_tighter_gap_goes_on_and_proves_the_same_plan_exact():
    world = junk_roll()
    result = Search(world, gap=0.5, gap_after=0.0).run()
    assert result.exact
    mean, plan = answer(result)
    assert mean == pytest.approx(39.0, rel=1e-12) and plan == {0: 1, 1: 2, 2: 0}
    assert result.lower == pytest.approx(39.0, rel=1e-8)


# ---- world 3: the first plan does not close, the start item given ----------------------------------------------------------------------
#
# Start 0, middle 1, goal 9, no restart. Offer 1 at the start costs 1 and leads to 1. At 1: offer 2 costs 3 and finishes with chance 1/2, else
# stays (it costs 6 on average); offer 3 costs 5 and finishes.  V* = 1 + 5 = 6.
# The bound puts offer 2 at 4 and offer 3 at 4.5: the first plan takes offer 2 and closes: U = 1 + 6 = 7.  L = 1 + 4.5 = 5.5.  U / L - 1 = 27.3%.


def slow_finish() -> Hand:
    return Hand(
        goal={9}, costs={1: 1.0, 2: 3.0, 3: 5.0}, actions={0: {1: {1: 1}}, 1: {2: {9: 1, 1: 1}, 3: {9: 1}}, 9: {}},
        la={(0, 1): 5.0, (1, 2): 4.0, (1, 3): 4.5}, lb={0: 5.0, 1: 4.0, 9: 0.0},
    )  # fmt: skip


def test_world_3_a_given_start_item_has_an_upper_side_once_the_first_plan_closes():
    result = Search(slow_finish(), gap=0.3, gap_after=0.0).run()
    assert not result.exact and result.within == 0.3 and not result.restarts
    mean, plan = answer(result)
    assert mean == pytest.approx(7.0, rel=1e-12) and plan == {0: 1, 1: 2}
    assert result.lower == pytest.approx(5.5, rel=1e-8) and mean <= 1.3 * 6.0
    exact = Search(slow_finish(), gap=0.2, gap_after=0.0).run()  # 7 > 1.2 * 5.5
    assert exact.exact and answer(exact) == (6.0, {0: 1, 1: 3})


def test_world_3_a_net_returns_the_closed_first_plan_of_a_given_start_item():
    result = Search(slow_finish(), net=Net(states=3)).run()  # the three states are known once the first plan is built: the net ends the search after its first round
    assert not result.exact and result.stopped and "limit is 3" in result.stopped and result.within is None
    assert answer(result)[0] == pytest.approx(7.0, rel=1e-12)
    assert result.upper == pytest.approx(7.0, rel=1e-8) and result.lower == pytest.approx(5.5, rel=1e-8)


def test_world_3_a_first_plan_that_has_not_closed_is_no_plan():
    with pytest.raises(NoPolicy, match="no restart"):
        Search(slow_finish(), net=Net(seconds=0.0)).run()  # the time net ends the chain at the start, before its action is built


# ---- the two conditions of the stop, each broken once ----------------------------------------------------------------------------------


def sound(result, optimum: float, gap: float) -> None:
    """What the stop promises: the plan returned costs at most `gap` more than the cheapest, and the two figures bracket the optimum."""
    mean, _ = answer(result)
    assert mean <= (1.0 + gap) * optimum * (1 + TOLERANCE), (mean, optimum)
    assert result.lower <= optimum * (1 + 1e-12)
    if not result.exact:
        assert result.upper >= mean * (1 - 1e-12) and result.upper <= (1.0 + gap) * result.lower


def test_control_an_upper_figure_that_is_not_the_cost_of_the_plan_breaks_the_stop(monkeypatch):
    """Condition 2. The upper figure is replaced by the bound's own guess of the first plan's cost (the least `la` at the start, what a search that trusted
    its heuristic would use). World 1 with offer 1 at 150: the stop fires on the guess and returns a plan 50% above the optimum."""
    world = two_finishes(costs={1: 150.0, 2: 99.5})
    real = Search._upper

    def guessed(self):
        graph, value, _ = real(self)
        return graph, value, 99.2

    monkeypatch.setattr(Search, "_upper", guessed)
    result = Search(world, gap=0.01, gap_after=0.0).run()
    assert not result.exact and answer(result)[0] == 150.0
    with pytest.raises(AssertionError):
        sound(result, 99.5, 0.01)
    monkeypatch.undo()
    honest = Search(two_finishes(costs={1: 150.0, 2: 99.5}), gap=0.01, gap_after=0.0).run()  # with the plan's exact cost the same world goes on to the optimum
    assert honest.exact and answer(honest)[0] == 99.5
    sound(honest, 99.5, 0.01)


def test_control_a_lower_figure_above_the_cheapest_plan_breaks_the_stop():
    """Condition 1. World 1 with offer 2 at a true cost of 90 while the bound still says 99.3 (above it: not a lower bound). The stop fires at 0.705%
    and returns offer 1 at 100, 11% above the optimum. The guard cannot see it: the bound is consistent at the one state there is."""
    world = two_finishes(costs={1: 100.0, 2: 90.0})
    result = Search(world, gap=0.01, gap_after=0.0).run()
    assert not result.exact and answer(result)[0] == 100.0
    with pytest.raises(AssertionError):
        sound(result, 90.0, 0.01)


def test_the_hand_worked_stops_keep_their_promise():
    sound(Search(two_finishes(), gap=0.01, gap_after=0.0).run(), 99.5, 0.01)
    sound(Search(junk_roll(), gap=0.75, gap_after=0.0).run(), 39.0, 0.75)
    sound(Search(slow_finish(), gap=0.3, gap_after=0.0).run(), 6.0, 0.3)


# ---- random graphs ---------------------------------------------------------------------------------------------------------------------


class Noisy(ExplicitProblem):
    """An admissible, consistent bound that orders the offers wrongly. A state's bound is `alpha V*`. An offer's bound is `alpha Q*` plus a fixed
    pseudo-random share of `(1 - alpha) c`, its own price: at most its backup under the states' bounds, `c + alpha (Q* - c)` (so replacing a fake
    action by the real one never lowers the graph: consistent), at most `Q*` (admissible), and at least the state's bound."""

    def _share(self, state: int, offer: int) -> float:
        return ((state * 7919 + offer * 104729) % 1000) / 1000.0

    def candidates(self, state: int) -> list[tuple[float, int]]:
        costs = self.graph.costs
        return [
            (self.alpha * q_value(self.graph, self.value, state, offer) + self._share(state, offer) * (1.0 - self.alpha) * costs[offer], offer)
            for offer in self.graph.actions[state]
        ]


def world(seed: int, alpha: float = 0.6, restart: int | None = 0):
    graph = random_graph(seed, SIZE)
    value, _ = dense_optimum(graph)
    return graph, value, Noisy(graph, value, alpha, restart=restart)


@pytest.mark.parametrize("gap", [0.001, 0.01, 0.05, 0.3])
@pytest.mark.parametrize("alpha", [0.97, 0.9, 0.5])
def test_every_answer_is_exact_or_within_its_gap_of_the_dense_optimum(gap, alpha):
    stopped = 0
    for seed in SEEDS:
        graph, value, problem = world(seed, alpha)
        result = Search(problem, gap=gap, gap_after=0.0).run()
        sound(result, value[0], gap)
        if result.exact:
            check_exact(graph, value, result)
        else:
            stopped += 1
            assert result.within == gap and result.stopped is None and result.restarts
    if gap >= 0.01 and alpha <= 0.9:
        assert stopped >= 6, stopped  # the test is not vacuous: most of these searches end at the gap (with a bound at 97% most first plans are proved exact at once)


def test_a_first_plan_that_is_not_the_optimum_is_returned_within_its_gap():
    """The noisy bound's first plan is often dearer than the optimum; a wide gap returns it as it is, and its mean is its own exact cost."""
    dearer = 0
    for seed in SEEDS:
        graph, value, problem = world(seed)
        result = Search(problem, gap=0.5, gap_after=0.0).run()
        mean, _ = answer(result)
        sound(result, value[0], 0.5)
        if mean > value[0] * (1 + 1e-6):
            dearer += 1
            assert not result.exact
    assert dearer >= 3, dearer


@pytest.mark.parametrize("options", [{"gap": 0.0, "gap_after": 0.0}, {"gap": 0.3, "gap_after": None}, {"gap": 0.3, "gap_after": 1e9}])
def test_no_gap_is_the_exact_search_on_every_graph(options):
    for seed in SEEDS:
        graph, value, problem = world(seed, 0.7)
        check_exact(graph, value, Search(problem, **options).run())


def test_a_stop_builds_no_more_than_the_exact_search_and_often_less():
    less = 0
    for seed in SEEDS:
        _, _, loose = world(seed, 0.9)
        _, _, exact = world(seed, 0.9)
        stopped = Search(loose, gap=0.3, gap_after=0.0).run()
        whole = Search(exact).run()
        assert stopped.stats.realized <= whole.stats.realized and stopped.stats.rounds <= whole.stats.rounds
        less += stopped.stats.realized < whole.stats.realized
    assert less >= 6, less


def test_a_watcher_reads_the_best_plan_so_far_and_its_proved_gap_from_the_first_plan_on():
    for seed in SEEDS:
        graph, value, problem = world(seed, 0.8)
        seen: list[Standing] = []
        plans: list[float] = []
        search = Search(problem, gap=0.02, gap_after=0.0, watch=seen.append)

        def also_the_plan(standing, search=search, plans=plans, seen=seen):
            seen.append(standing)
            held = search.plan_now()
            if held is not None:
                plans.append(answer(held)[0])
                assert plans[-1] <= held.upper * (1 + 1e-12) and not held.exact

        search.watch = also_the_plan
        result = search.run()
        assert seen and seen[0].rounds == 0 and seen[0].upper is not None  # the first plan, before any round
        assert search.standing == seen[-1]
        for before, after in zip(seen, seen[1:]):
            assert after.lower >= before.lower * (1 - 1e-6)  # the lower figure only rises
            assert after.upper <= before.upper * (1 + 1e-12)  # the upper only falls
        for standing in seen:
            assert standing.lower <= value[0] * (1 + 1e-9) <= standing.upper * (1 + 2e-9)
            assert standing.gap is None or standing.gap >= 0.0
        assert all(mean >= value[0] * (1 - 1e-9) for mean in plans) and plans
        if not result.exact:
            assert seen[-1].gap is not None and seen[-1].gap <= 0.02
        else:
            assert seen[-1].gap == pytest.approx(0.0, abs=1e-6)


def test_a_given_start_item_stops_at_a_gap_on_random_graphs_too():
    stopped = 0
    for seed in SEEDS:
        graph, value, problem = world(seed, 0.9, restart=None)
        result = Search(problem, gap=0.3, gap_after=0.0).run()
        sound(result, value[0], 0.3)
        if not result.exact:
            stopped += 1
            assert not result.restarts
    assert stopped >= 3, stopped


def test_an_upper_solve_that_cannot_be_certified_makes_the_stop_wait_and_is_counted(monkeypatch):
    """The first two solves of the upper graph are refused (#769's cases): the first plan has no upper figure, the stop waits a round, and the
    answer is still within its gap. A search with no such refusal stops at its first round on the same graph."""
    graph, value, _ = world(1, 0.9)
    plain = Search(Noisy(graph, value, 0.9), gap=0.3, gap_after=0.0).run()
    assert not plain.exact and plain.stats.rounds == 1 and plain.stats.upper_refused == 0

    real_graph = Search._graph
    real_solve = _envelope.solve_graph
    last = []
    refused = []

    def noting(self, mode):
        last.append(mode)
        return real_graph(self, mode)

    def refusing(packed, **options):
        if last[-1] == "upper" and len(refused) < 2:
            refused.append(packed.n)
            raise ConvergenceError("the solve certifies only a relative bound of 4.7e-4", 4.7e-4)
        return real_solve(packed, **options)

    monkeypatch.setattr(Search, "_graph", noting)
    monkeypatch.setattr(_envelope, "solve_graph", refusing)
    result = Search(Noisy(graph, value, 0.9), gap=0.3, gap_after=0.0).run()
    assert result.stats.upper_refused == 2 and result.stats.first_upper is None
    assert result.stats.rounds >= 2  # the first round's stop waited
    sound(result, value[0], 0.3)


def test_the_gap_is_a_share_zero_or_more():
    for wrong in (-0.01, math.inf, math.nan):
        with pytest.raises(ValueError, match="gap"):
            Search(two_finishes(), gap=wrong)


def test_the_slack_of_an_offers_bound_never_decides_a_hand_worked_figure():
    assert SLACK <= 1e-8  # the figures above are compared to 1e-8: the search lowers each `la` by `SLACK`
    assert isinstance(Graph, type)  # the support's graph is what `world` builds on


def refuse_upper_solves(monkeypatch, from_solve: int) -> list:
    """Make the solver refuse every solve of the upper graph from the `from_solve`-th on (1 is the first plan's); returns the list of the refused."""
    real_graph = Search._graph
    real_solve = _envelope.solve_graph
    last: list = []
    upper: list = []
    refused: list = []

    def noting(self, mode):
        last.append(mode)
        return real_graph(self, mode)

    def refusing(packed, **options):
        if last[-1] == "upper":
            upper.append(packed.n)
            if len(upper) >= from_solve:
                refused.append(packed.n)
                raise ConvergenceError("the solve certifies only a relative bound of 4.7e-4", 4.7e-4)
        return real_solve(packed, **options)

    monkeypatch.setattr(Search, "_graph", noting)
    monkeypatch.setattr(_envelope, "solve_graph", refusing)
    return refused


def test_a_net_keeps_the_last_plan_the_solver_certified_when_the_plan_in_hand_cannot_be(monkeypatch):
    """OR-33: a stop returns a plan, not a refusal. The first plan is certified; the search grows; at the net the plan in hand is refused by the solver
    (#769's cases): the answer is the first plan, over the states it knew, and it says so. With nothing certified before, the stop is the refusal it was."""
    graph, value, _ = world(2, 0.5)
    plain = Search(Noisy(graph, value, 0.5), net=Net(states=30)).run()
    assert not plain.exact and not plain.held and len(plain.states) >= 30
    refused = refuse_upper_solves(monkeypatch, 2)
    search = Search(Noisy(graph, value, 0.5), net=Net(states=30))
    result = search.run()
    assert refused and not result.exact and result.held and "limit is 30" in result.stopped
    assert result.graph.n == len(result.states) == len(result.index) < len(search.states)  # the states the kept plan knew: a prefix of the search's
    assert result.states == search.states[: result.graph.n]
    mean, _ = answer(result)
    assert math.isfinite(mean) and mean >= value[0] * (1 - 1e-9) and result.upper >= mean * (1 - 1e-12)
    assert result.upper == pytest.approx(result.stats.first_upper) and result.lower <= value[0] * (1 + 1e-9)
    monkeypatch.undo()
    refuse_upper_solves(monkeypatch, 1)  # not even the first plan is certified: nothing to keep
    with pytest.raises(NoPolicy, match="cannot be solved to a certified cost"):
        Search(Noisy(graph, value, 0.5), net=Net(states=30)).run()
