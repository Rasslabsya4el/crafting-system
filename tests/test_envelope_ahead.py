"""#1340: the rounds' tips realized ahead in forked workers (`planner._ahead`) give the search of one process, state for state.

The searches here fork a pool at every round of two tips or more (`ahead_always`), so that the rule that decides it on the clock is never read:
what they compare is what a pool changes, which must be nothing but which process made a kernel.
"""

import os
import threading
from dataclasses import dataclass, field

import numpy as np
import pytest
from envelope_support import ExplicitProblem, dense_optimum, q_value, random_graph

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
    def reached(self, futures, stop=None):
        raise parallel.MemoryNetReached("this process and its workers held 9 MB, the limit is 8 MB; the workers were stopped")

    monkeypatch.setattr(parallel.WorkerPool, "gather", reached)
    _, _, alone = _search(3, 0.3, workers=1)
    pooled, asked, ahead = _search(3, 0.3, workers=3, ahead_always=True)
    _same(alone, ahead)
    assert pooled.ahead.stopped is not None and pooled.ahead.pooled == 1  # one pool, dropped at its first window: no other round forks


def test_the_rule_forks_the_workers_that_save_the_most_or_none():
    ahead = _ahead.Ahead(4, 0.5)
    assert ahead.workers_for(1000) == 0  # nothing measured yet: the first round's pace is unknown
    ahead.per_tip, ahead.fork = 0.001, 0.02  # 1 ms of kernels per tip, 20 ms to fork a worker
    # 100 tips: two workers save 50 - 40 ms, three 66.7 - 60, four 75 - 80: two
    assert ahead.workers_for(100) == 2
    assert ahead.workers_for(60) == 0  # two save 30 ms for a 40 ms fork
    assert ahead.workers_for(10_000) == 4  # 7,500 - 80 ms
    ahead.lost, ahead.lost_tips = 1.0, 2000  # half a millisecond lost per tip: 10,000 tips lose 5 s more, and four still save 2.42 s
    assert ahead.workers_for(10_000) == 4 and ahead.workers_for(200) == 0  # 200 tips lose 100 ms, more than any count saves past its fork
    assert _ahead.Ahead(1, 0.5, always=True).workers_for(1000) == 0  # one worker: never
    assert _ahead.Ahead(4, 0.5, always=True).workers_for(1) == 0
    assert _ahead.Ahead(4, 0.5, always=True).workers_for(2) == 4


def test_a_window_holds_a_few_polls_of_work_per_worker_and_a_chunk_per_worker_at_least():
    ahead = _ahead.Ahead(4, 0.5)
    assert ahead.window(4) == 4 * _ahead.CHUNKS
    ahead.per_tip = 0.01
    assert ahead.window(3) == int(_ahead.WINDOW * 0.5 * 3 / 0.01)
    ahead.per_tip = 10.0
    assert ahead.window(4) == 4 * _ahead.CHUNKS


def test_workers_that_take_the_search_to_its_memory_net_are_stopped_and_the_search_goes_on_as_one_process(monkeypatch):
    # the memory read is planted: past the net while a pool is open (its fork holds the objects frozen), under it once the workers are stopped
    monkeypatch.setattr(parallel, "held_mb", lambda under=None, paced=True: 2e9 if parallel._frozen[0] else 1.0)
    net = Net(memory_mb=1e9)
    _, _, alone = _search(2, 0.0, net=net, workers=1)
    pooled, _, ahead = _search(2, 0.0, net=net, workers=3, ahead_always=True)
    _same(alone, ahead)
    assert alone.stopped is None and pooled.ahead.stopped is not None and "the workers were stopped" in pooled.ahead.stopped


@dataclass
class ListedProblem(ExplicitProblem):
    """A problem whose listings a worker can make (`listing`): each writes a note, as the prunings are written, and the floors `tighten` lifts
    change the listings after it, as the offers' floors do (`Problem.listing_version`)."""

    lifted: dict[int, int] = field(default_factory=dict)
    written: list[str] = field(default_factory=list)
    listed_here: int = 0
    _held: list[str] | None = None

    def _floor(self, position: int) -> float:
        return 1.0 - 0.5 ** (self.lifted.get(position, 0) + 1)

    def lower(self, state: int) -> float:
        return 0.5 * super().lower(state)  # under the least floor of the offers (a half of theirs), so the bound stays consistent

    def candidates(self, state: int) -> list[tuple[float, int]]:
        (self._held if self._held is not None else self.written).append(f"listed {state}")
        return [(la * self._floor(offer), offer) for la, offer in super().candidates(state)]

    def split_candidates(self, state: int):
        if self._held is None:
            self.listed_here += 1
        out = self.candidates(state)
        return [entry for entry in out if entry[1] % 2], [entry for entry in out if not entry[1] % 2]

    def tighten(self, state: int, position: int, best: float) -> float | None:
        level = self.lifted.get(position, 0)
        if level < 3 and state % 5 == 0:
            self.lifted[position] = level + 1
        return self.alpha * q_value(self.graph, self.value, state, position) * self._floor(position)

    def listing(self, state: int):
        self._held = []
        try:
            own, rest = self.split_candidates(state)
            return self.listing_version(), own, rest, self._held
        finally:
            self._held = None

    def listing_version(self):
        return tuple(sorted(self.lifted.items()))

    def relisted(self, notes) -> None:
        self.written.extend(notes)


@pytest.mark.parametrize("seed", [1, 5])  # seeds whose made-up floors keep the search's guards quiet (most raise `BoundError`, alone as with workers)
def test_listings_made_by_workers_are_taken_only_on_the_floors_they_read_and_write_their_notes_in_order(seed):
    graph = random_graph(seed, 400)
    value, _ = dense_optimum(graph)
    runs = []
    for options in ({"workers": 1}, {"workers": 3, "ahead_always": True}):
        problem = ListedProblem(graph, value, 0.3)
        search = Search(problem, **options)
        runs.append((search, problem, search.run()))
    (_, alone, one), (pooled, ahead, other) = runs
    _same(one, other)
    assert ahead.written == alone.written and ahead.lifted == alone.lifted
    assert pooled.ahead.pooled and ahead.listed_here < alone.listed_here  # workers listed some of the states this process expanded


def test_a_fork_that_fails_leaves_the_search_to_this_process(monkeypatch):
    def failed(self, function, pieces):
        raise OSError(12, "Cannot allocate memory")

    monkeypatch.setattr(parallel.WorkerPool, "submit", failed)
    _, _, alone = _search(4, 0.3, workers=1)
    pooled, _, ahead = _search(4, 0.3, workers=3, ahead_always=True)
    _same(alone, ahead)
    assert pooled.ahead.pooled


def test_the_pace_is_that_of_all_the_rounds_so_a_round_that_needed_nothing_does_not_make_the_next_look_free():
    ahead = _ahead.Ahead(4, 0.5)
    ahead.making = 2.0
    ahead.end_round(100)  # 20 ms a tip
    ahead.end_round(89)  # tips listed and realized before: no work
    assert ahead.per_tip == pytest.approx(2.0 / 189)
    ahead.fork = 0.04
    assert ahead.workers_for(1539) == 4


@dataclass
class HangingProblem(ExplicitProblem):
    """A problem whose kernels never come back in a forked worker: a kernel there that the search's net would cut (R12, #1340)."""

    home: int = field(default_factory=os.getpid)

    def kernel(self, state: int, position: int) -> dict[int, int]:
        if os.getpid() != self.home:
            threading.Event().wait()
        return super().kernel(state, position)


def test_a_search_waiting_on_its_workers_asks_its_own_net_and_goes_on_alone_once_it_is_reached(monkeypatch):
    # the net a kernel's making asks (`Search._kernel_ask`) is planted as reached: each pool's wait is stopped by it, and its workers with it;
    # this process makes the kernels itself, as one process does (the explicit kernels never ask it), and the search ends the same
    monkeypatch.setattr(Search, "_kernel_ask", lambda self: lambda: "the test's net was reached")
    graph = random_graph(3, 120)
    value, _ = dense_optimum(graph)
    runs = []
    for options in ({"workers": 1}, {"workers": 3, "ahead_always": True}):
        search = Search(HangingProblem(graph, value, 0.3), **options)
        runs.append((search, search.run()))
    (_, alone), (pooled, ahead) = runs
    _same(alone, ahead)
    assert pooled.ahead.pooled and pooled.ahead.stopped is None  # the search's own net stops a pool, not this search's pools: the next round forks again


def _hang(pieces):
    threading.Event().wait()


def test_a_wait_on_workers_ends_at_the_callers_reason_and_kills_them():
    pool = parallel.WorkerPool(_ahead._hold, (None,), workers=2)
    futures = [pool.submit(_hang, [1]), pool.submit(_hang, [2])]
    asked = []

    def stop():
        asked.append(1)
        return "reached" if len(asked) >= 2 else None

    with pytest.raises(parallel.Stopped, match="reached"):
        pool.gather(futures, stop=stop)
    assert len(asked) == 2 and pool._executor is None  # asked at each watch, and the workers killed at the reason
