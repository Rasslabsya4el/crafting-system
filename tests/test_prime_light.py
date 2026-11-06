"""`abstraction._prime.prime` on the committed fixture pool, without a process pool (ticket #413).

The measurement week (#399) found that the light suite left 13 of 18 mutants of `_prime.py` alive: the real checks run
on routes and need several cores. Here the pool is replaced by `parallel.WorkerPool` with one worker, which runs every
piece in this process by the code the workers run, and `can_inherit` is switched on, so the tests run on every system.

The expected numbers are counted by hand from the fixture: the 80 amulets that `concrete_items` lists from five mods
(three or fewer on an item) fall into six pool signatures under the Chaos Orb (three of the five mods have a family
that blocks the others), so a request over all of them is six pools, not eighty.
"""

import pytest
from abstraction_pool import COLD_RESIST, LIFE_1, MANA_1, RESIST_1
from coarse_support import CHAOS, DATA, REMOVE, abstraction, concrete_items

from crafting_system import parallel
from crafting_system.abstraction import _prime
from crafting_system.actions import ScouringOrb

MODS = [MANA_1, LIFE_1, RESIST_1, COLD_RESIST, "FireResist1"]
POOLS = 6  # distinct Chaos Orb pools among the 80 items of `MODS` (counted by hand, see the module text)


def states_of(ab):
    return [ab.compress(entry) for entry in concrete_items(DATA, MODS, largest=3)]


def one_per_pool(ab, states):
    """The first state of each distinct Chaos Orb pool signature, in the order met (the abstraction's own signature, not `prime`'s)."""
    found = {}
    for state in states:
        found.setdefault(tuple(ab._signatures_of(ab._prepared(state, CHAOS))), state)
    return list(found.values())


class PoolSpy(parallel.WorkerPool):
    """The real pool run with one worker (everything in this process), noting what `prime` asked of it.

    A forked worker computes on a copy of the abstraction, so what it books in the caches and the counter is lost
    when it ends; `map` puts them back after the pieces ran, as the fork would leave them.
    """

    made: list = []
    mapped: list = []

    def __init__(self, factory, args=(), *, workers=None):
        PoolSpy.made.append(workers)
        super().__init__(factory, args, workers=1)
        self._abstraction = args[0]

    def map(self, function, pieces, *, chunk=None):
        pieces = list(pieces)
        PoolSpy.mapped.append((len(pieces), chunk))
        ab = self._abstraction
        cache, fractures, kernels = dict(ab._cache), dict(ab._fractures), ab._kernels
        try:
            return super().map(function, pieces, chunk=chunk)
        finally:
            ab._cache.clear()
            ab._cache.update(cache)
            ab._fractures.clear()
            ab._fractures.update(fractures)
            ab._kernels = kernels


@pytest.fixture
def pool(monkeypatch):
    PoolSpy.made, PoolSpy.mapped = [], []
    monkeypatch.setattr(parallel, "WorkerPool", PoolSpy)
    monkeypatch.setattr(parallel, "can_inherit", lambda: True)
    return PoolSpy


def test_the_fixture_has_the_six_pools_the_other_tests_count_by():
    ab = abstraction()
    assert len(one_per_pool(ab, states_of(ab))) == POOLS


def test_prime_computes_each_uncached_pool_once_and_says_how_many(pool):
    ab = abstraction()
    requests = [(state, CHAOS) for state in states_of(ab)]  # eighty requests, six pools

    made = _prime.prime(ab, requests, workers=4)

    assert made == POOLS
    assert len(ab._cache) == POOLS
    assert ab._kernels == POOLS  # one unit of work booked per distribution stored
    assert pool.made == [4]  # min(workers asked, pools to compute)
    assert pool.mapped == [(POOLS, 1)]  # one piece per pool, handed one at a time


def test_the_pool_is_no_larger_than_the_number_of_pools_to_compute(pool):
    ab = abstraction()

    _prime.prime(ab, [(state, CHAOS) for state in states_of(ab)], workers=64)

    assert pool.made == [POOLS]


def test_what_prime_stored_is_what_a_serial_run_computes(pool):
    primed, plain = abstraction(), abstraction()
    states = states_of(primed)
    _prime.prime(primed, [(state, CHAOS) for state in states], workers=4)

    for state in one_per_pool(primed, states):
        assert primed.kernel(state, CHAOS) == plain.kernel(state, CHAOS)
    assert len(primed._cache) == POOLS  # the kernels found everything ready: no pool was computed again


def test_a_second_prime_finds_everything_cached_and_starts_no_pool(pool):
    ab = abstraction()
    requests = [(state, CHAOS) for state in states_of(ab)]
    _prime.prime(ab, requests, workers=4)
    pool.made.clear()

    assert _prime.prime(ab, requests, workers=4) == 0
    assert pool.made == []
    assert ab._kernels == POOLS


def test_two_pools_are_primed_and_one_is_left_to_the_kernel_call(pool):
    ab = abstraction()
    reps = one_per_pool(ab, states_of(ab))

    assert _prime.prime(ab, [(state, CHAOS) for state in reps[:1]], workers=4) == 0  # one pool: nothing to share out
    assert pool.made == [] and not ab._cache and ab._kernels == 0

    assert _prime.prime(ab, [(state, CHAOS) for state in reps[:2]], workers=4) == 2  # MIN_JOBS pools are enough
    assert pool.made == [2] and len(ab._cache) == 2 and ab._kernels == 2


@pytest.mark.parametrize("workers", [0, 1])
def test_fewer_than_two_workers_primes_nothing(pool, workers):
    ab = abstraction()

    assert _prime.prime(ab, [(state, CHAOS) for state in states_of(ab)], workers=workers) == 0
    assert pool.made == [] and not ab._cache and ab._kernels == 0


def test_two_workers_are_enough(pool):
    ab = abstraction()

    assert _prime.prime(ab, [(state, CHAOS) for state in states_of(ab)], workers=2) == POOLS
    assert pool.made == [2]


def test_without_fork_prime_does_nothing(pool, monkeypatch):
    monkeypatch.setattr(parallel, "can_inherit", lambda: False)
    ab = abstraction()

    assert _prime.prime(ab, [(state, CHAOS) for state in states_of(ab)], workers=4) == 0
    assert pool.made == [] and not ab._cache and ab._kernels == 0


def test_a_request_the_kernel_would_refuse_is_left_out_and_does_not_stop_the_others(pool):
    ab = abstraction()
    states = states_of(ab)
    refused = [(states[0], ScouringOrb()), (states[1], REMOVE)]  # a Scouring Orb is not enabled in the fixture; Remove Crafted Mods has no crafted mod to remove

    assert _prime.prime(ab, [*refused, *((state, CHAOS) for state in states)], workers=4) == POOLS


def test_a_worker_that_fails_stores_nothing_and_primes_nothing(pool, monkeypatch):
    def broken(self, function, pieces, *, chunk=None):
        raise RuntimeError("a worker died")

    monkeypatch.setattr(PoolSpy, "map", broken)
    ab = abstraction()

    assert _prime.prime(ab, [(state, CHAOS) for state in states_of(ab)], workers=4) == 0
    assert not ab._cache and ab._kernels == 0
