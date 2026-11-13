"""The process pool of ticket #250: the size comes from CRAFTING_WORKERS, and `map` gives a loop's list for any size."""

import io
import os
import random
import sys
import multiprocessing
import threading
from types import MappingProxyType

import pytest

from crafting_system import parallel
from crafting_system.parallel import WorkerPool, context, worker_count


def make_base(offset: int) -> dict:
    return {"offset": offset, "table": MappingProxyType({"k": 7})}


def add_offset(piece: int) -> tuple[int, int]:
    return piece, piece * context()["table"]["k"] + context()["offset"]


def seeded_draw(piece: int) -> float:
    return random.Random(f"{piece}:seed").random()


def test_the_size_is_the_variable_when_it_is_set():
    assert worker_count({"CRAFTING_WORKERS": "3"}) == 3
    assert worker_count({"CRAFTING_WORKERS": "1"}) == 1


def test_the_size_without_the_variable_is_at_least_one_core():
    assert worker_count({}) >= 1
    assert worker_count({"CRAFTING_WORKERS": "  "}) >= 1


@pytest.mark.parametrize("bad", ["0", "-2", "many", "1.5"])
def test_a_bad_variable_is_refused(bad):
    with pytest.raises(ValueError, match="CRAFTING_WORKERS"):
        worker_count({"CRAFTING_WORKERS": bad})


def test_the_test_suite_runs_serial_by_default():
    assert os.environ.get("CRAFTING_WORKERS") == "1"


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_map_returns_the_list_of_a_loop_for_any_size(workers):
    pieces = list(range(103))
    with WorkerPool(make_base, (5,), workers=workers) as pool:
        found = pool.map(add_offset, pieces)

    assert found == [(p, p * 7 + 5) for p in pieces]


@pytest.mark.parametrize("chunk", [1, 3, 500])
def test_the_chunk_changes_the_speed_not_the_result(chunk):
    with WorkerPool(make_base, (0,), workers=3) as pool:
        found = pool.map(add_offset, list(range(40)), chunk=chunk)

    assert found == [(p, p * 7) for p in range(40)]


def test_pieces_with_their_own_seeds_draw_the_same_for_one_and_many_workers():
    pieces = list(range(60))
    with WorkerPool(make_base, (0,), workers=1) as one, WorkerPool(make_base, (0,), workers=4) as four:
        assert one.map(seeded_draw, pieces) == four.map(seeded_draw, pieces)


def test_an_empty_job_starts_no_process():
    with WorkerPool(make_base, (0,), workers=4) as pool:
        assert pool.map(add_offset, []) == []
        assert pool._executor is None


def test_a_mapping_proxy_can_be_pickled_for_a_spawned_worker():
    import copyreg
    import pickle

    copyreg.pickle(MappingProxyType, parallel._pickle_mapping_proxy)
    again = pickle.loads(pickle.dumps(MappingProxyType({"a": 1})))

    assert dict(again) == {"a": 1}


def total_of(chunk: list) -> int:
    return sum(chunk) + context()["offset"]


@pytest.mark.parametrize("workers", [1, 3])
def test_map_chunks_gives_one_result_per_run_of_pieces_in_order(workers):
    with WorkerPool(make_base, (100,), workers=workers) as pool:
        found = pool.map_chunks(total_of, list(range(10)), chunk=4)

    assert found == [0 + 1 + 2 + 3 + 100, 4 + 5 + 6 + 7 + 100, 8 + 9 + 100]


def fails(piece: int) -> int:
    raise KeyError(piece)


def test_an_error_in_a_worker_reaches_the_caller():
    with WorkerPool(make_base, (0,), workers=2) as pool:
        with pytest.raises(KeyError):
            pool.map(fails, [1, 2, 3, 4])


def dies(piece: int) -> int:
    os._exit(3)  # a worker killed from outside (the kernel's out-of-memory killer, say) ends like this


def test_a_dead_worker_raises_in_the_caller_instead_of_leaving_it_waiting():
    from concurrent.futures.process import BrokenProcessPool

    with WorkerPool(make_base, (0,), workers=2) as pool:
        with pytest.raises(BrokenProcessPool):
            pool.map(dies, [1, 2, 3, 4])
    # #535: the pool raises at once instead of waiting forever on a worker that is gone (a hang would stall the suite)


class GatedStream(io.TextIOBase):
    """A stream whose writes take a lock, as a buffered stdout does."""

    def __init__(self):
        self.gate = threading.Lock()

    def write(self, text):
        with self.gate:
            return len(text)


def prints(piece: int) -> int:
    print(f"piece {piece}")
    return piece


@pytest.mark.skipif(not parallel.can_inherit(), reason="only forked workers inherit the parent's stream locks")
def test_a_forked_worker_prints_though_the_parent_held_its_stream_lock_at_the_fork(monkeypatch):
    gated = GatedStream()
    monkeypatch.setattr(sys, "stdout", gated)
    with gated.gate:  # held while the workers are forked, as by a progress thread writing to a slow pipe (#535)
        with WorkerPool(make_base, (0,), workers=2) as pool:
            assert pool.map(prints, [1, 2], timeout=60.0) == [1, 2]  # before #535 each worker waited on the copied lock forever


def waits_forever(piece: int) -> int:
    threading.Event().wait()  # nobody sets it: a worker that never comes back


def test_a_worker_that_never_comes_back_is_killed_at_the_timeout():
    with WorkerPool(make_base, (0,), workers=2) as pool:
        with pytest.raises(TimeoutError):
            pool.map(waits_forever, [1, 2], timeout=0.0)
        assert pool._executor is None  # abandoned: the next map starts fresh workers
        assert pool.map(add_offset, [1, 2]) == [(1, 7), (2, 14)]


def sleeps(piece: int) -> int:
    threading.Event().wait(30)  # a worker that is still at work when the memory net is read
    return piece


def test_a_pool_past_the_memory_net_is_killed_and_says_so(monkeypatch):
    """#626 (OR-12): the workers hold memory the caller's net never saw; while a net is set, the wait on them reads the memory of the caller and its
    workers and kills them once it passes the limit, instead of letting the runner run out of memory."""
    monkeypatch.setattr(parallel, "held_mb", lambda: 12_000.0)
    with parallel.memory_net(10_000):
        with WorkerPool(make_base, (0,), workers=2) as pool:
            with pytest.raises(parallel.MemoryNetReached, match="12,000 MB.*10,000 MB"):
                pool.map(sleeps, [1, 2], chunk=1)
            assert pool._executor is None  # abandoned: the workers are gone
    assert parallel.active_memory_net() is None  # the net is the run's: it ends with the block


def test_a_pool_under_the_memory_net_gives_the_list_of_a_loop(monkeypatch):
    monkeypatch.setattr(parallel, "held_mb", lambda: 100.0)
    with parallel.memory_net(10_000):
        with WorkerPool(make_base, (7,), workers=2) as pool:
            assert pool.map(add_offset, [1, 2, 3]) == [(1, 14), (2, 21), (3, 28)]
            assert pool.map_chunks(total_of, [1, 2, 3], chunk=2) == [1 + 2 + 7, 3 + 7]


def make_gate(ready, release) -> dict:
    return {"ready": ready, "release": release}


def holds(piece: int) -> int:
    block = bytearray(200 * 2**20)  # 200 MB written (a zeroed bytearray is touched page by page), held until the test has read the memory
    context()["ready"].put(piece)
    context()["release"].wait(60)
    return len(block)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the workers' memory is read from /proc")
def test_the_memory_held_counts_the_workers():
    """The memory the net reads is the caller's and its live workers' (proportional sizes, so the pages a fork shares are counted once)."""
    alone = parallel.held_mb()
    ready, release = multiprocessing.Queue(), multiprocessing.Event()
    with WorkerPool(make_gate, (ready, release), workers=2) as pool:
        executor = pool._start()
        futures = [executor.submit(parallel._run_chunk, holds, [piece]) for piece in (1, 2)]
        assert sorted(ready.get(timeout=60) for _ in futures) == [1, 2]  # both workers hold their block now
        during = parallel.held_mb()
        release.set()
        assert [future.result() for future in futures] == [[200 * 2**20]] * 2
    assert during >= alone + 300, (alone, during)


def hangs_or_fails(piece: int) -> int:
    if piece == 2:
        raise KeyError(piece)
    threading.Event().wait()  # nobody sets it: before the fix the caller waited on this one after the other had failed


@pytest.mark.parametrize("net", [None, 10_000])
def test_a_failed_chunk_ends_the_wait_at_once_and_kills_the_hung_one(monkeypatch, net):
    """A chunk that raises while another hangs: the caller gets the error now, not after the hung one, and its workers are stopped (#535 kept)."""
    monkeypatch.setattr(parallel, "held_mb", lambda: 100.0)
    with parallel.memory_net(net):
        with WorkerPool(make_base, (0,), workers=2) as pool:
            with pytest.raises(KeyError):
                pool.map(hangs_or_fails, [1, 2], chunk=1, timeout=3600.0)  # the hour is never reached: the failure ends the wait
            assert pool._executor is None
