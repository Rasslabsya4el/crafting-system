"""The pool's wait on its workers reads an upper figure of the memory first and the proportional sizes only past it, never paced (ticket #1258).

The wait (`WorkerPool._wait`) read `parallel.held_mb()` in full at each look: the proportional size (`smaps_rollup` under `/proc`) of the caller and
of each live worker, up to 2.4 s per reading near a 12,000 MB net with four workers, about 13% of R14's run. The resident sum cannot stand in for
it there (each forked worker counts the pages it shares with the others in full, so the sum is past the net from the start), and a paced reading
let the workers pass the net by up to 3 GB (#1252). The group's figure (`parallel._group_sum`: the anonymous pages of the run's control group,
each counted once, plus the file pages each process maps) is an upper figure of the proportional sum that costs microseconds; the wait asks
`held_mb(under=limit, paced=False)`: under the limit the upper figure answers, past it the proportional sum is read at that question.

Every reading here is made by hand, except the last test, which checks on this machine's own `/proc` that the group's figure is not under the
proportional sum. No test reads the clock.
"""

import multiprocessing
import sys
import threading
from types import SimpleNamespace

import pytest
from test_memory_question import Readings

from crafting_system import parallel
from crafting_system.parallel import WorkerPool


def test_the_groups_figure_answers_under_the_net_where_the_resident_sum_cannot(monkeypatch):
    """Four forked workers: the resident sum (40,000 MB) is past the net, the group's figure counts the shared pages once and is under it."""
    memory = Readings(monkeypatch, resident=40_000.0, proportional=9_000.0, group=9_400.0)
    for paced in (True, False):
        assert [parallel.held_mb(under=12_000.0, paced=paced) for _ in range(100)] == [9_400.0] * 100
    assert memory.dear == 0


def test_past_the_upper_figure_an_unpaced_question_reads_in_full_each_time_and_stops_at_once(monkeypatch):
    """The wait's question (`paced=False`): once the upper figure reaches the limit, every question reads the proportional sum, so the net stops
    at the first question whose memory is past it. The paced question of #1252 answers the same climb with its last reading and stops late."""
    climb = [11_000.0, 11_600.0, 12_100.0, 12_700.0]
    for paced, stops_at in ((False, 2), (True, None)):
        memory = Readings(monkeypatch, resident=40_000.0, proportional=0.0, cost=2.4, group=12_400.0)
        answers = []
        for proportional in climb:
            memory.proportional = proportional
            answers.append(parallel.held_mb(under=12_000.0, paced=paced))
            memory.now += parallel.WATCH_SECONDS
        reached = [index for index, held in enumerate(answers) if held >= 12_000.0]
        if stops_at is not None:
            assert answers == climb and memory.dear == len(climb)
            assert reached[0] == stops_at  # the first question past the net
        else:
            assert reached == []  # paced: each later question got the first reading, 11,000 MB, and the net was passed by 700 MB unseen


def sleeps(piece: int) -> int:
    threading.Event().wait(30)  # a worker still at work while the wait reads the memory
    return piece


def make_base(offset: int) -> dict:
    return {"offset": offset}


def test_the_pools_wait_asks_its_nets_limit_unpaced(monkeypatch):
    asked = []
    monkeypatch.setattr(parallel, "held_mb", lambda under=None, paced=True: asked.append((under, paced)) or 12_500.0)
    with parallel.memory_net(10_000.0):
        with WorkerPool(make_base, (0,), workers=2) as pool:
            with pytest.raises(parallel.MemoryNetReached, match="12,500 MB.*10,000 MB"):
                pool.map(sleeps, [1, 2], chunk=1)
    assert asked == [(10_000.0, False)]  # one reading per look, with the limit, never paced


def test_the_pools_wait_stops_at_the_first_look_past_the_net(monkeypatch):
    """The workers climb past the net while the upper figure is past it: the wait reads the proportional sum at every look and stops at the
    look whose reading is past the net, not some looks later."""
    climb = iter([9_000.0, 11_000.0, 12_200.0, 13_000.0, 14_000.0])
    read = []
    monkeypatch.setattr(parallel, "_upper_sum", lambda: 40_000.0)
    monkeypatch.setattr(parallel, "_proportional_sum", lambda: read.append(1) or next(climb))
    monkeypatch.setattr(parallel, "WATCH_SECONDS", 0.01)
    with parallel.memory_net(12_000.0):
        with WorkerPool(make_base, (0,), workers=2) as pool:
            with pytest.raises(parallel.MemoryNetReached, match="12,200 MB.*12,000 MB"):
                pool.map(sleeps, [1, 2], chunk=1)
    assert len(read) == 3


class HandMadeProc:
    """A hand-made /proc and control group: the group of each process, its mapped file and shared pages, and the group's anonymous pages."""

    def __init__(self, monkeypatch, anon: float | None, groups: dict, mapped: dict) -> None:
        self.groups, self.mapped = groups, mapped
        monkeypatch.setattr(parallel, "_cgroup_of", lambda pid: self.groups.get(pid))
        monkeypatch.setattr(parallel, "_status_fields", lambda pid, names: self.mapped.get(pid))
        monkeypatch.setattr(parallel, "_anon_of", lambda group: anon)
        children = [SimpleNamespace(pid=int(pid)) for pid in groups if pid != "self"]
        monkeypatch.setattr(parallel.multiprocessing, "active_children", lambda: children)


def test_the_groups_figure_is_its_anonymous_pages_and_each_processs_mapped_files(monkeypatch):
    HandMadeProc(monkeypatch, 9_000.0, {"self": "/run.scope", "11": "/run.scope", "12": "/run.scope"}, {"self": [80.0, 0.0], "11": [70.0, 5.0], "12": [70.0, 5.0]})
    assert parallel._group_sum() == 9_000.0 + 80.0 + 75.0 + 75.0


@pytest.mark.parametrize(
    "anon, groups, mapped",
    [
        (9_000.0, {"self": "/run.scope", "11": "/other.scope"}, {"self": [80.0, 0.0], "11": [70.0, 0.0]}),  # a worker in another group
        (9_000.0, {"self": None, "11": "/run.scope"}, {"self": [80.0, 0.0], "11": [70.0, 0.0]}),  # no cgroup v2 (Windows, macOS, v1)
        (None, {"self": "/run.scope", "11": "/run.scope"}, {"self": [80.0, 0.0], "11": [70.0, 0.0]}),  # no memory.stat to read
        (9_000.0, {"self": "/run.scope", "11": "/run.scope"}, {"self": [80.0, 0.0]}),  # a worker whose status cannot be read
    ],
)
def test_the_groups_figure_is_not_given_where_it_would_not_be_an_upper_figure(monkeypatch, anon, groups, mapped):
    HandMadeProc(monkeypatch, anon, groups, mapped)
    assert parallel._group_sum() is None


def test_without_the_groups_figure_the_resident_sum_is_the_upper_figure(monkeypatch):
    Readings(monkeypatch, resident=11_000.0, proportional=9_000.0, group=None)
    assert parallel.held_mb(under=12_000.0, paced=False) == 11_000.0
    Readings(monkeypatch, resident=11_000.0, proportional=9_000.0, group=10_000.0)
    assert parallel.held_mb(under=12_000.0, paced=False) == 10_000.0  # the lesser of the two


def make_gate(ready, release) -> dict:
    return {"ready": ready, "release": release}


def holds(piece: int) -> int:
    block = bytearray(100 * 2**20)  # 100 MB of the worker's own, held until the test has read the memory
    parallel.context()["ready"].put(piece)
    parallel.context()["release"].wait(60)
    return len(block)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the control group and the proportional sizes are read from /proc")
def test_the_groups_figure_is_never_under_the_proportional_sum():
    """The reason the group's answer is sound, on this machine: two forked workers share 200 MB of their parent's pages and hold 100 MB each."""
    if parallel._group_sum() is None:
        pytest.skip("this process runs in no cgroup v2 group with a memory.stat")
    shared = bytearray(200 * 2**20)  # written page by page: the forked workers share these pages with the parent
    ready, release = multiprocessing.Queue(), multiprocessing.Event()
    with WorkerPool(make_gate, (ready, release), workers=2) as pool:
        executor = pool._start()
        futures = [executor.submit(parallel._run_chunk, holds, [piece]) for piece in (1, 2)]
        assert sorted(ready.get(timeout=60) for _ in futures) == [1, 2]
        proportional = parallel._proportional_sum()
        group = parallel._group_sum()
        release.set()
        assert [future.result() for future in futures] == [[100 * 2**20]] * 2
    assert len(shared) == 200 * 2**20
    assert group is not None and group >= proportional - 16.0, (group, proportional)  # 16 MB: what the processes may free between the reads
