"""The envelope search's warm start (ticket #568): each round starts from the last round's policy, and that start is proper or is replaced.

A round's lower graph differs from the last round's at the frontier: a tip becomes an expanded node whose fake action may be gone (all its offers are realized),
and a node that had gone to the goal by its fake now has real actions that can lead back. The policy of the last round is then not always proper on the new
graph. The solver proves the start proper by the finite chain's own test (every state reaches the goal with positive chance) and replaces it where it fails
(`tests/test_solver_packed_warm.py` pins that on constructed graphs). Pinned here, on the search itself over random graphs with cycles and a restart:

* at every round the start that the search hands the solver, once the solver has proved or repaired it, is proper on that round's graph by a dense check that
  shares no code with the solver, and the search reaches the same plan and mean as the cold search;
* a start that is improper on every round (the last round's policy replaced by a random one) is repaired each time and the search still ends at the same plan
  and mean: the fallback inside a search, not only on the constructed graphs.
"""

import numpy as np
import pytest
from envelope_support import ExplicitProblem, Graph, dense_optimum, random_graph
from test_solver_packed_warm import proper

from crafting_system.cli import _envelope
from crafting_system.cli._envelope import Search
from crafting_system.solver._packed_solve import Work, warm_policy

SIZE = 60
SEEDS = range(12)
ALPHAS = (0.98, 0.7, 0.0)


def searched(seed: int, alpha: float, warm: bool, monkeypatch, watch=None):
    graph = random_graph(seed, SIZE)
    value, _ = dense_optimum(graph)
    search = Search(ExplicitProblem(graph, value, alpha), warm=warm)
    if watch is not None:
        real = _envelope.solve_graph

        def wrapped(packed, **options):
            watch(packed, options)
            return real(packed, **options)

        monkeypatch.setattr(_envelope, "solve_graph", wrapped)
    result = search.run()
    monkeypatch.undo()
    return value, result


def test_the_start_of_every_round_is_proper_after_the_solver_has_proved_or_repaired_it(monkeypatch):
    seen = {"kept": 0, "repaired": 0, "cold": 0}

    def watch(packed, options):
        if options.get("start_policy") is None:
            seen["cold"] += 1
            return
        work = Work(packed)
        leave = work.nonself_sums(np.ones(packed.n))
        alive = leave > 0.0
        effective = np.where(alive, packed.act_cost / np.where(alive, leave, 1.0), np.inf)
        info: dict = {}
        inside, ok, policy = warm_policy(work, alive, effective, options["start_policy"], info, options["start_value"], leave)
        seen[info["warm"]] += 1
        assert proper(packed, policy)

    for seed in SEEDS:
        for alpha in ALPHAS:
            searched(seed, alpha, True, monkeypatch, watch)
    assert seen["kept"] > 0
    assert seen["cold"] >= len(SEEDS) * len(ALPHAS)  # the first round of each search (and the incumbent's, if any)


def loop_graph() -> Graph:
    """Offer 0 restarts, 1 and 2 step on, 3 jumps to the goal at a high price. State 0 steps to 1, 1 to 2, 2 to the goal; 1 and 2 may restart."""
    return Graph(
        n=4, goal={3}, costs=[1.0, 1.0, 1.0, 10.0],
        actions=[{1: {1: 1}, 3: {3: 1}}, {0: {0: 1}, 2: {2: 1}}, {0: {0: 1}, 2: {3: 1}}, {}],
        mover=[3, 2, 2, -1],
    )  # fmt: skip


@pytest.mark.parametrize("alpha", [0.0, 0.5])  # a perfect bound realizes only the optimal path, which has no closed class
def test_a_start_that_is_improper_on_the_new_graph_is_repaired_inside_a_search_and_changes_nothing(alpha, monkeypatch):
    """The previous policy 'restart at 1 and 2, step to 1 at 0' is a closed class of three states on the graph of every round that has those actions."""
    kinds = []
    real_warm = Search._warm
    real_solve = _envelope.solve_graph

    def hostile(self, graph):
        warm = real_warm(self, graph)
        if warm is None:
            return None
        wanted = {0: 1}  # tag wanted at each state: step to 1 at state 0, restart at the others
        policy = np.full(graph.n, -1, dtype=np.int64)
        for s in range(graph.n - 1):
            tags = graph.act_tag[graph.act_ptr[s] : graph.act_ptr[s + 1]].tolist()
            if wanted.get(s, 0) in tags:
                policy[s] = graph.act_ptr[s] + tags.index(wanted.get(s, 0))
        return policy, np.zeros(graph.n)

    def noting(packed, **options):
        core = real_solve(packed, **options)
        kinds.append(options["info"].get("warm"))
        return core

    monkeypatch.setattr(Search, "_warm", hostile)
    monkeypatch.setattr(_envelope, "solve_graph", noting)
    graph = loop_graph()
    value, _ = dense_optimum(graph)
    result = Search(ExplicitProblem(graph, value, alpha)).run()
    assert "repaired" in kinds, kinds
    assert result.exact
    assert result.lower == pytest.approx(value[0], rel=1e-6)
    assert value[0] == pytest.approx(3.0)


@pytest.mark.parametrize("alpha", ALPHAS)
@pytest.mark.parametrize("seed", SEEDS)
def test_the_warm_search_reaches_the_cold_search_s_plan_and_mean(seed, alpha, monkeypatch):
    value, warm = searched(seed, alpha, True, monkeypatch)
    _, cold = searched(seed, alpha, False, monkeypatch)
    assert warm.exact and cold.exact
    assert warm.lower == pytest.approx(cold.lower, rel=1e-9)
    assert warm.stats.rounds == cold.stats.rounds
    assert warm.stats.expanded == cold.stats.expanded
    assert warm.stats.realized == cold.stats.realized
    assert warm.lower == pytest.approx(value[0], rel=1e-6)
