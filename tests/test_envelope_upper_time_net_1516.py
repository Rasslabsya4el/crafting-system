"""The pricing of the plan in hand keeps the search's time net (#1516, OR-40, OR-39).

The upper side prices the plan in hand by solving the realized actions (`Search._upper` -> `solve_graph`). Its first step,
`proper_states`, carries the cheapest paths to a goal one step per sweep of the graph, so a plan whose chain reaches a goal only at its far end
takes as many sweeps as the chain has states: on R17 (th27c, 210,847 states) each pricing took about 800 s and a run with a 1 h net ran on to its
outer kill at 85 min. On main the solve asked no clock. Here the chain has 12,000 states that move on with chance 1 in 1,000,001 (a plan of about
1.2e10 c): on main each of its three pricings takes about 4 s, so a 2 s net ends after 10 s and more; with the deadline the search stops within
its net and says the plan could not be priced in time.
"""

import time

import numpy as np
import pytest

from crafting_system.planner._envelope import LAST_PRICING, Net, NoPolicy, Search
from crafting_system.solver import Late, PackedGraph
from crafting_system.solver._packed_solve import solve_graph

GOAL = -1


class Chain:
    """States 0..n-1 in a row: offer 1 (1 c) moves on with weight 1 and stays with weight `stay`; the last state's offer 1 reaches the goal.
    Offer 2 (1e9 c) goes to the goal at once, so the bound stays admissible, but the first plan takes offer 1 at every state."""

    start = 0
    restart = None

    def __init__(self, n: int, stay: int) -> None:
        self.n, self.stay = n, stay

    def is_goal(self, state: int) -> bool:
        return state == GOAL

    def lower(self, state: int) -> float:
        return 0.0

    def candidates(self, state: int) -> list[tuple[float, int]]:
        return [] if state == GOAL else [(0.0, 1), (0.0, 2)]

    def first_choice(self, state: int) -> list[int]:
        return [1]

    def cost(self, position: int) -> float:
        return 1.0 if position == 1 else 1e9

    def kernel_key(self, state: int, position: int) -> None:
        return None

    def kernel(self, state: int, position: int) -> dict[int, int]:
        if position == 2:
            return {GOAL: 1}
        return {GOAL if state == self.n - 1 else state + 1: 1, state: self.stay}

    def release(self) -> None:
        pass


def test_a_pricing_too_long_for_the_net_ends_within_it() -> None:
    net = 2.0
    said: list[str] = []
    search = Search(Chain(12_000, 1_000_000), net=Net(seconds=net), progress=said.append, gap=0.01, gap_after=0.0)
    began = time.perf_counter()
    with pytest.raises(NoPolicy, match="could not be priced within the time limit"):
        search.run()
    wall = time.perf_counter() - began
    assert wall <= net * (1.0 + LAST_PRICING) + 1.0, wall  # main: about 12 s (three pricings of about 4 s each)
    assert search.stats.upper_late >= 1
    assert any("it was not priced within the time limit" in line for line in said), said


def test_a_short_chain_is_still_priced() -> None:
    """The control: the same plan on 50 states prices well inside the net, so the net changes nothing there."""
    result = Search(Chain(50, 1_000_000), net=Net(seconds=60.0), gap=0.01, gap_after=0.0).run()
    assert result.stats.first_upper == pytest.approx(50 * 1_000_001, rel=1e-5)  # the first plan was priced
    assert result.stats.upper_late == 0


def test_the_solver_stops_at_a_deadline_already_past() -> None:
    """`solve_graph` with a deadline already passed raises `Late` after its first sweep; with none it solves the same graph."""
    n = 30  # states 0..n-1, each with one action of 1 c that moves on with chance 1/4 and stays with 3/4; n is the goal: V(0) = 4 n
    goal = np.zeros(n + 1, dtype=bool)
    goal[n] = True
    graph = PackedGraph(
        goal=goal, act_ptr=np.concatenate((np.arange(n + 1, dtype=np.int64), [n])), act_tag=np.ones(n, dtype=np.int32), act_cost=np.ones(n),
        act_kernel=np.arange(n, dtype=np.int32), k_ptr=np.arange(0, 2 * n + 1, 2, dtype=np.int64),
        k_succ=np.array([t for s in range(n) for t in (s + 1, s)], dtype=np.int32), k_wt=np.tile(np.array([1, 3], dtype=np.int64), n),
        k_prob=np.tile(np.array([0.25, 0.75]), n),
    )
    with pytest.raises(Late, match="before a sweep of the cheapest paths to a goal"):
        solve_graph(graph, deadline=time.perf_counter() - 1.0)
    assert solve_graph(graph).value[0] == pytest.approx(4.0 * n)
