"""#1340: the rounds' tips realized ahead in forked workers (`planner._ahead`) give the search of one process, state for state.

The searches here fork a pool at every round of two tips or more (`ahead_always`), so that the rule that decides it on the clock is never read:
what they compare is what a pool changes, which must be nothing but which process made a kernel.
"""

import numpy as np
import pytest
from envelope_support import ExplicitProblem, dense_optimum, random_graph

from crafting_system import parallel
from crafting_system.planner import _ahead
from crafting_system.planner._envelope import Net, Search

pytestmark = pytest.mark.skipif(not parallel.can_inherit(), reason="no fork here: the search runs in one process (OR-57)")

ARRAYS = ("goal", "act_ptr", "act_tag", "act_cost", "act_kernel", "k_ptr", "k_succ", "k_wt", "k_prob")


def _search(seed: int, alpha: float, net: Net | None = None, **options):
    graph = random_graph(seed, 400)
    value, _ = dense_optimum(graph)
    problem = ExplicitProblem(graph, value, alpha)
    search = Search(problem, net=net, **options)
    return search, problem, search.run()


def _same(one, other) -> None:
    assert other.states == one.states and other.index == one.index
    for name in ARRAYS:
        assert np.array_equal(getattr(other.graph, name), getattr(one.graph, name)), name
    assert (other.lower, other.upper, other.exact, other.stopped) == (one.lower, one.upper, one.exact, one.stopped)
    assert (other.stats.expanded, other.stats.realized, other.stats.kernels, other.stats.rounds) == (
        one.stats.expanded, one.stats.realized, one.stats.kernels, one.stats.rounds,
    )


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
@pytest.mark.parametrize("alpha", [0.0, 0.5, 0.9])
def test_a_search_with_workers_is_the_search_of_one_process_and_its_workers_made_kernels(seed, alpha):
    one, asked_one, alone = _search(seed, alpha, workers=1)
    pooled, asked_pooled, ahead = _search(seed, alpha, workers=3, ahead_always=True)
    _same(alone, ahead)
    assert one.ahead.pooled == 0
    if pooled.ahead.pooled:  # this process made fewer kernels: the others came from the workers, and they are the same ones
        assert len(asked_pooled.asked) < len(asked_one.asked)
        assert set(asked_pooled.asked) <= set(asked_one.asked)


def test_the_number_of_workers_changes_nothing():
    results = [_search(5, 0.3, workers=count, ahead_always=True)[2] for count in (2, 3, 5)]
    for other in results[1:]:
        _same(results[0], other)


def test_a_states_net_stops_a_pooled_round_where_it_stops_one_process():
    for seed in (1, 2, 3):
        _, _, alone = _search(seed, 0.3, net=Net(states=150), workers=1)
        _, _, ahead = _search(seed, 0.3, net=Net(states=150), workers=3, ahead_always=True)
        _same(alone, ahead)


def test_a_run_counted_in_states_forks_no_pool():
    search, _, _ = _search(2, 0.3, net=Net(states=200, pieces=10_000), workers=3, ahead_always=True)
    assert search.counted and search.ahead.pooled == 0


def test_a_pool_that_meets_the_memory_net_is_dropped_and_the_search_goes_on_alone(monkeypatch):
    def reached(self, futures):
        raise parallel.MemoryNetReached("this process and its workers held 9 MB, the limit is 8 MB; the workers were stopped")

    monkeypatch.setattr(parallel.WorkerPool, "gather", reached)
    _, _, alone = _search(3, 0.3, workers=1)
    pooled, asked, ahead = _search(3, 0.3, workers=3, ahead_always=True)
    _same(alone, ahead)
    assert pooled.ahead.stopped is not None and pooled.ahead.pooled == 1  # one pool, dropped at its first window: no other round forks


def test_the_rule_forks_when_the_saving_passes_the_fork_and_the_loss_per_tip():
    ahead = _ahead.Ahead(4, 0.5)
    assert not ahead.pays(1000)  # nothing measured yet: the first round's pace is unknown
    ahead.per_tip = 0.001  # 1 ms of kernels per tip: 100 tips save 75 ms on 4 workers
    assert ahead.pays(100) == (0.075 > _ahead.FORK_PRIOR)
    ahead.fork = 0.2
    assert not ahead.pays(100) and ahead.pays(300)  # 225 ms > 200 ms
    ahead.lost, ahead.lost_tips = 1.0, 2000  # half a millisecond lost per tip: 300 tips cost 200 + 150 ms, save 225
    assert not ahead.pays(300) and ahead.pays(2000)  # 1,500 ms > 200 + 1,000
    assert not _ahead.Ahead(1, 0.5, always=True).pays(1000)  # one worker: never
    assert not _ahead.Ahead(4, 0.5, always=True).pays(1)


def test_a_window_holds_a_few_polls_of_work_per_worker_and_a_chunk_per_worker_at_least():
    ahead = _ahead.Ahead(4, 0.5)
    assert ahead.window() == 4 * _ahead.CHUNKS
    ahead.per_tip = 0.01
    assert ahead.window() == int(_ahead.WINDOW * 0.5 * 4 / 0.01)
    ahead.per_tip = 10.0
    assert ahead.window() == 4 * _ahead.CHUNKS
