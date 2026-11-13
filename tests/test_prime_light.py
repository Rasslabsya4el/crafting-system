"""`abstraction._prime.prime` on the committed fixture pool, without a process pool (ticket #413).

The measurement week (#399) found that the light suite left 13 of 18 mutants of `_prime.py` alive: the real checks run
on routes and need several cores. Here the pool is replaced by `parallel.WorkerPool` with one worker, which runs every
piece in this process by the code the workers run, and `can_inherit` is switched on, so the tests run on every system.

The expected numbers are counted by hand from the fixture: the 80 amulets that `concrete_items` lists from five mods
(three or fewer on an item) fall into six pool signatures under the Chaos Orb (three of the five mods have a family
that blocks the others), so a request over all of them is six pools, not eighty.
"""

import dataclasses

import pytest
from abstraction_pool import COLD_RESIST, LEVEL, LIFE_1, MANA_1, RESIST_1
from coarse_support import CHAOS, DATA, ENABLED, GOAL, REMOVE, abstraction, concrete_items, item, roll
from items_support import AMULET

from crafting_system import parallel
from crafting_system.abstraction import Abstraction, _prime
from crafting_system.actions import ApplyFossils, ScouringOrb
from crafting_system.data.model import Fossil

MODS = [MANA_1, LIFE_1, RESIST_1, COLD_RESIST, "FireResist1"]
POOLS = 6  # distinct Chaos Orb pools among the 80 items of `MODS` (counted by hand, see the module text)


def states_of(ab):
    return [ab.compress(entry) for entry in concrete_items(DATA, MODS, largest=3)]


def one_per_pool(ab, states=None):
    """One state for each of the six Chaos Orb pools, picked by hand (`states` is not looked at; the argument is kept for the callers).

    A Chaos Orb rerolls every mod that is not fractured, so the pool it draws from is decided by the fractured mod alone: no mod is
    fractured (one pool: the whole item is redrawn, whatever it holds), or exactly one of the five mods is, and that mod and its family stay
    (five pools, because the five mods are of five different families: Mana Leech, Life, and the Lightning, Cold and Fire resistances).
    That is 1 + 5 = 6, and no signature function of the abstraction is used to say so.
    """
    return [ab.compress(item(roll(MANA_1))), *(ab.compress(item(roll(mod, fractured=True))) for mod in MODS)]


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
    # counted by the pools the kernel calls fill, not by `prime`'s own signature: the eighty items fill six, and the six chosen by hand
    # fill the same six (one each: a seventh or a repeat would show in the size of the cache)
    everything, by_hand = abstraction(), abstraction()
    for state in states_of(everything):
        everything.kernel(state, CHAOS)
    for state in one_per_pool(by_hand):
        by_hand.kernel(state, CHAOS)

    assert len(everything._cache) == POOLS and len(by_hand._cache) == POOLS
    assert set(everything._cache) == set(by_hand._cache)
    assert len(states_of(by_hand)) == 80  # 25 items with no fractured mod, 11 for each of the five that is fractured: 25 + 55


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


# --- a draw that fractures one mod: the Fractured Fossil (ticket #435) ------------------------------------------------------

# The fixture has no Fractured Fossil, so one is added here: a record with the name the rules give it ("Fractured Fossil") and no tag weights,
# so that a resonator with it alone draws from the plain pool of the amulet. `Scorched Fossil` (fixture record: fire mods ten times as likely,
# cold mods impossible) changes the pool; the set of the two is therefore a second pool.
FRACTURED = Fossil("Metadata/Items/Currency/CurrencyDelveCraftingFractured", "Fractured Fossil", (), (), (), (), (), (), False, False, False, False, 0)
FOSSIL_DATA = dataclasses.replace(DATA, fossils={**DATA.fossils, FRACTURED.id: FRACTURED})
PLAIN_FRACTURE = ApplyFossils(("Fractured Fossil",))
SCORCHED_FRACTURE = ApplyFossils(("Fractured Fossil", "Scorched Fossil"))


def fossil_abstraction():
    return Abstraction(FOSSIL_DATA, GOAL, AMULET, LEVEL, ENABLED)


def fossil_requests(ab):
    """Six requests over two pools: every state is erased by the resonator (only a fractured mod stays, and these items have none), so the
    pool depends on the fossils alone, two sets, two pools; the three items are an empty rare amulet and two holding one mod."""
    states = [ab.compress(item()), ab.compress(item(roll(MANA_1))), ab.compress(item(roll(LIFE_1), roll(RESIST_1)))]
    return [(state, action) for state in states for action in (PLAIN_FRACTURE, SCORCHED_FRACTURE)]


def test_a_draw_that_fractures_a_mod_is_computed_once_for_each_pool_and_stored_where_the_kernel_looks(pool):
    ab = fossil_abstraction()

    made = _prime.prime(ab, fossil_requests(ab), workers=4)

    assert made == 2  # two pools, six requests
    assert len(ab._fractures) == 2 and not ab._cache  # the fracture entries, not the plain distributions
    assert ab._kernels == 2
    assert pool.made == [2] and pool.mapped == [(2, 1)]


def test_a_second_prime_finds_the_fracture_entries_stored_and_starts_no_pool(pool):
    ab = fossil_abstraction()
    requests = fossil_requests(ab)
    _prime.prime(ab, requests, workers=4)
    pool.made.clear()

    assert _prime.prime(ab, requests, workers=4) == 0
    assert pool.made == [] and len(ab._fractures) == 2 and ab._kernels == 2


def test_what_prime_stored_for_a_fracturing_draw_is_what_a_serial_run_computes_and_the_kernel_adds_nothing(pool):
    primed, plain = fossil_abstraction(), fossil_abstraction()
    requests = fossil_requests(primed)
    _prime.prime(primed, requests, workers=4)

    for state, action in requests:
        assert primed.kernel(state, action) == plain.kernel(state, action)
    assert len(primed._fractures) == 2  # the kernels found everything ready
    assert primed._fractures == plain._fractures


def test_one_fracturing_pool_alone_is_left_to_the_kernel_and_joins_a_plain_pool_to_make_two(pool):
    ab = fossil_abstraction()
    empty = ab.compress(item())

    assert _prime.prime(ab, [(empty, PLAIN_FRACTURE)], workers=4) == 0  # one pool: nothing to share out
    assert pool.made == [] and not ab._fractures

    assert _prime.prime(ab, [(empty, PLAIN_FRACTURE), (empty, CHAOS)], workers=4) == 2  # a fracturing pool and a plain one
    assert len(ab._fractures) == 1 and len(ab._cache) == 1 and ab._kernels == 2


class StoppedPool(PoolSpy):
    """A pool whose workers the run's memory net killed (#626): `map` raises as `parallel.WorkerPool._wait` does."""

    def map(self, function, pieces, *, chunk=None):
        PoolSpy.mapped.append((len(list(pieces)), chunk))
        raise parallel.MemoryNetReached("this process and its workers held 12,000 MB, the limit is 10,000 MB; the workers were stopped")


def test_a_pool_the_memory_net_stopped_stores_nothing_and_no_pool_is_started_again(monkeypatch):
    PoolSpy.made, PoolSpy.mapped = [], []
    monkeypatch.setattr(parallel, "WorkerPool", StoppedPool)
    monkeypatch.setattr(parallel, "can_inherit", lambda: True)
    ab = abstraction()
    requests = [(state, CHAOS) for state in states_of(ab)]

    assert _prime.prime(ab, requests, workers=4) == 0
    assert not ab._cache and ab._kernels == 0  # nothing stored: the kernels compute them alone, the same values
    assert "12,000 MB" in ab.prime_stopped
    assert _prime.prime(ab, requests, workers=4) == 0
    assert PoolSpy.made == [4]  # the second call forked no pool: the net said the memory is not there
