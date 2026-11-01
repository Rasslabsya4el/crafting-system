"""The solver's actions of many states built at once in a process pool (ticket #250).

`solve` explores the states breadth first and asks the model for the actions of each one; building them (the kernel of
every offer, and which equal kernels merge) is most of that time. A `StatePool` holds worker processes that each rebuild
the `Abstraction` of the plan and the offers once; `_Model.prefetch` hands it the pending states of the queue and gets
back, for each, exactly the list `solver_actions` returns. The answer cannot depend on the number of workers because a
state's actions are a function of the state, the offers and the abstraction alone (a worker's caches only save work), and
the results are taken in the order the states were given.

With one worker (`CRAFTING_WORKERS=1`) `open_pool` gives None and nothing here runs.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from crafting_system import parallel
from crafting_system.abstraction import Abstraction, CompressedState

from ._offers import PricedOffer
from ._prune import solver_actions

MIN_PENDING = 24  # fewer pending states than this are built here: the round trip would cost more than it saves


class _Worker:
    """What one worker process holds: its own abstraction, the offers by position, and a cache of built actions."""

    def __init__(self, spec: tuple, start: CompressedState, offers: Sequence[PricedOffer], merge_equal: bool) -> None:
        data, goal, base_id, item_level, enabled, metamods = spec
        self.abstraction = Abstraction(data, goal, base_id, item_level, enabled, metamods=metamods)
        self.start, self.offers, self.merge_equal = start, tuple(offers), merge_equal
        self.cache: dict = {}


def _actions_of(task: tuple[CompressedState, tuple[int, ...]]) -> list:
    state, positions = task
    worker: _Worker = parallel.context()  # type: ignore[assignment]
    offers = [worker.offers[position] for position in positions]
    return solver_actions(worker.abstraction, offers, state, worker.start, merge_equal=worker.merge_equal, cache=worker.cache)


class StatePool:
    """Workers that build `solver_actions` for a plan's offers; `position_of` says where an offer sits in the pool's list."""

    def __init__(self, abstraction: Abstraction, start: CompressedState, offers: Sequence[PricedOffer], merge_equal: bool, workers: int) -> None:
        spec = (abstraction.data, abstraction.goal, abstraction.base_id, abstraction.item_level, abstraction.enabled, abstraction.models_metamods)
        self.offers = tuple(offers)
        self.merge_equal = merge_equal
        self.position_of = {id(offer): position for position, offer in enumerate(self.offers)}
        self._pool = parallel.WorkerPool(_Worker, (spec, start, self.offers, merge_equal), workers=workers)

    def positions(self, offers: Sequence[PricedOffer]) -> tuple[int, ...] | None:
        """The positions of `offers` in this pool's list, or None when one of them is not from it."""
        try:
            return tuple(self.position_of[id(offer)] for offer in offers)
        except KeyError:
            return None

    def actions_of(self, states: Sequence[CompressedState], positions: tuple[int, ...]) -> list[list]:
        return self._pool.map(_actions_of, [(state, positions) for state in states])

    def close(self) -> None:
        self._pool.close()


@contextmanager
def open_pool(
    abstraction: Abstraction, start: CompressedState, offers: Sequence[PricedOffer], merge_equal: bool
) -> Iterator[StatePool | None]:
    """A `StatePool` for the length of the block, or None when `CRAFTING_WORKERS` is 1 (or the machine has one core)."""
    workers = parallel.worker_count()
    if workers < 2:
        yield None
        return
    pool = StatePool(abstraction, start, offers, merge_equal, workers)
    try:
        yield pool
    finally:
        pool.close()
