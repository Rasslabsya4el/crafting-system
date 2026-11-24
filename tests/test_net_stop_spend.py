"""What a net's stop spends after the net (#1566, #1553, OR-40): a plan the search priced already is never priced again.

On R17 (th50, 1 h net) the search priced its first plan at minute 51; the next round priced the same graph again for 507 s, until the net; the
stop priced it a third time for 204 s past the net, gave up and kept the first plan's pricing; then the answer solved that graph once more
(merge, policy iteration, certificates: 283 s). Each of those works on a graph whose price was already known.

* **The same graph.** `Search._upper` asked again for a graph it priced returns that pricing (nothing is swept again).
* **A graph whose pricing met the net.** At the stop, a graph whose pricing already ran to the time limit is not priced again when an earlier
  plan was priced: that plan is the answer, at once. The toy `Side` has a first plan that prices at once and a round that adds a side branch;
  the pricing of the grown graph is made to run to the net (the solver is told its time is up), as R17's 507 s did.
* **The answer's solve.** `solver.packed_of_core` takes the answer from the search's own pricing of the graph: the same values and the same
  lumped plan as `solve_packed`, which solves it again.
"""

import numpy as np
import pytest
from test_envelope_upper_time_net_1516 import GOAL, Chain, clock  # noqa: F401  (the hand clock and the chain of #1516)

from crafting_system.planner import _envelope
from crafting_system.planner._envelope import Net, Search
from crafting_system.solver import Late, lump_policy, packed_of_core, solve_packed
from crafting_system.solver._packed_solve import solve_graph


def test_a_graph_priced_already_is_not_priced_again(clock) -> None:  # noqa: F811
    search = Search(Chain(50, 1_000_000), net=Net(seconds=60.0), gap=0.01, gap_after=0.0)
    search.run()
    first = search._upper(clock.now + 1e9)
    solves, before = search.stats.upper_solves, clock.now
    again = search._upper(clock.now + 1e9)
    assert again[0] is first[0] and again[1:] == first[1:]
    assert search.stats.upper_solves == solves and clock.now == before  # no sweep of the solver: the hand clock did not move


SIDE = 1000  # a side state of the chain state s is SIDE + s


class Side:
    """A bought start (offer 0 restarts, 1 c). At chain state s < n, offer 1 (1 c) moves on (the last one reaches the goal); offer 2 (1 c) goes
    to the side state SIDE + s, whose offer 1 reaches the goal with weight 1 and stays with weight 3. The first plan takes offer 1 everywhere
    (n c); the bound sees offer 2 at 1 c and a side state at 0, so a round realizes offer 2 and its side state is a tip."""

    start = 0
    restart = 0

    def __init__(self, n: int) -> None:
        self.n = n

    def is_goal(self, state: int) -> bool:
        return state == GOAL

    def lower(self, state: int) -> float:
        return 0.0

    def candidates(self, state: int) -> list[tuple[float, int]]:
        if state == GOAL:
            return []
        return [(0.0, 1)] if state >= SIDE else [(0.0, 1), (0.0, 2)]

    def first_choice(self, state: int) -> list[int]:
        return [1]

    def cost(self, position: int) -> float:
        return 1.0

    def kernel_key(self, state: int, position: int) -> None:
        return None

    def kernel(self, state: int, position: int) -> dict[int, int]:
        if position == 0:
            return {0: 1}
        if state >= SIDE:
            return {GOAL: 1, state: 3}
        if position == 2:
            return {SIDE + state: 1}
        return {GOAL if state == self.n - 1 else state + 1: 1}

    def release(self) -> None:
        pass


def test_at_the_stop_a_graph_whose_pricing_met_the_net_is_not_priced_again(clock, monkeypatch) -> None:  # noqa: F811
    net = 100.0
    calls: list[bool] = []

    def pricing(graph, **kwargs):
        if kwargs.get("late") is None:  # the round's lower solve, which no limit asks
            return solve_graph(graph, **kwargs)
        calls.append(True)
        if len(calls) == 1:
            return solve_graph(graph, **kwargs)  # the first plan prices at once
        clock.now += net  # every later pricing runs to the net, as R17's did
        raise Late("the solve stopped at its caller's time limit (the test's)", net, "a round of policy iteration")

    monkeypatch.setattr(_envelope, "solve_graph", pricing)
    said: list[str] = []
    search = Search(Side(5), net=Net(seconds=net), progress=said.append, gap=0.01, gap_after=0.0)
    began = clock.now
    result = search.run()
    assert result.stopped is not None and result.held and result.upper == pytest.approx(5.0, rel=1e-6)  # the first plan, priced before the net
    assert len(calls) == 2, said  # the first plan's pricing, and the round's that met the net; main priced the grown graph again at the stop
    assert clock.now - began <= 2 * net + 1.0
    assert any("not priced again at the stop" in line for line in said), said


def test_the_answer_taken_from_the_search_s_pricing_is_the_answer_solve_packed_gives(clock) -> None:  # noqa: F811
    search = Search(Chain(40, 3), net=Net(seconds=1e9), gap=0.0, gap_after=None)
    search.run()
    graph = search._upper()[0]
    core = search.priced(graph)
    assert core is not None
    taken, solved = packed_of_core(graph, core), solve_packed(graph)
    assert taken.value[0] == pytest.approx(solved.value[0], rel=1e-9) and taken.error_bound <= 1e-6
    assert np.array_equal(taken.cls, solved.cls) and np.array_equal(taken.action, solved.action)
    lumped = lump_policy(taken.quotient, taken.class_action, int(taken.cls[0]))
    again = lump_policy(solved.quotient, solved.class_action, int(solved.cls[0]))
    assert lumped.count == again.count and lumped.transitions == again.transitions
