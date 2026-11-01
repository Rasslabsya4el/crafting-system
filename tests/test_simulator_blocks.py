"""Simulated runs in blocks (ticket #250): the report is the same for any number of workers, and one block is the old stream."""

import pytest
from simulator_support import DATA, ITEMS, chain_policy, holds_target

from crafting_system.simulator import simulate

COIN = {"S": (2.0, (("goal", 1), ("S", 2), ("T", 1)))}
CHAIN = chain_policy({**COIN, "T": (1.5, (("goal", 1), ("S", 1)))})


def run(**arguments):
    return simulate(DATA, CHAIN, ITEMS["S"], holds_target, seed=11, **arguments)


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_the_blocks_give_the_same_report_for_any_number_of_workers(workers):
    serial = run(runs=1_000, block=100, workers=1)
    pooled = run(runs=1_000, block=100, workers=workers)

    assert pooled == serial


def test_the_blocks_are_cut_in_order_and_the_last_one_is_short():
    report = run(runs=250, block=100, workers=2)

    assert report.runs == 250 and len(report.costs) == 250


def test_a_block_as_long_as_the_runs_is_the_single_stream_of_before():
    assert run(runs=400, block=400, workers=2) == run(runs=400)
    assert run(runs=400, block=5_000, workers=1) == run(runs=400)


def test_the_first_block_is_the_old_stream():
    whole = run(runs=300)
    blocked = run(runs=300, block=100)

    assert blocked.costs[:100] == whole.costs[:100]
    assert blocked.costs[100:200] != whole.costs[100:200]


@pytest.mark.parametrize("block", [0, -1, 1.5, True])
def test_a_bad_block_is_refused(block):
    with pytest.raises(ValueError, match="block"):
        run(runs=10, block=block)
