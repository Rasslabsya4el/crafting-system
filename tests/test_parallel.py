"""The process pool of ticket #250: the size comes from CRAFTING_WORKERS, and `map` gives a loop's list for any size."""

import os
import random
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
