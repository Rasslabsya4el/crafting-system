"""The actions of many states built at once in a process pool (ticket #250).

`solve` explores the states breadth first and asks the model for the actions of each one; the model chooses which
offers apply at a state (`_prune.chosen_offers`: the kernel keys, here) and builds the kernel of each chosen offer (the
expensive part). A `StatePool` holds worker processes that each rebuild the `Abstraction` of the plan and the offers
once; `_Model.prefetch` gives it the (state, offer) pairs of the pending states whose action is not built yet and
stores what comes back in the cache `solver_actions` reads, so the serial code that follows finds every action ready.
The answer cannot depend on the number of workers: an action is a function of the state, the offer and the abstraction
alone (a worker's caches only save work), and the results are taken in the order the pairs were given.

With one worker (`CRAFTING_WORKERS=1`) `open_pool` gives None and nothing here runs.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from crafting_system import parallel
from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.actions import ActionError

from ._offers import PricedOffer

MIN_PENDING = 24  # fewer pairs than this are built here: the round trip would cost more than it saves


class _Worker:
    """What one worker process holds: its own abstraction, the start state and the offers by position."""

    def __init__(self, spec: tuple, start: CompressedState, offers: Sequence[PricedOffer]) -> None:
        data, goal, base_id, item_level, enabled, metamods = spec
        self.abstraction = Abstraction(data, goal, base_id, item_level, enabled, metamods=metamods)
        self.start, self.offers = start, tuple(offers)


def _build(task: tuple[CompressedState, tuple[int, ...]]) -> list:
    """The solver action of each offer (by position) at the state; None where the game refuses it there."""
    from ._plan import offer_action  # _plan imports this module

    state, positions = task
    worker: _Worker = parallel.context()  # type: ignore[assignment]
    built = []
    for position in positions:
        try:
            built.append(offer_action(worker.abstraction, worker.offers[position], state, worker.start))
        except ActionError:
            built.append(None)
    return built


class StatePool:
    """Workers that build the solver action of an offer at a state; `positions` says where an offer sits in the pool's list."""

    def __init__(self, abstraction: Abstraction, start: CompressedState, offers: Sequence[PricedOffer], workers: int) -> None:
        spec = (abstraction.data, abstraction.goal, abstraction.base_id, abstraction.item_level, abstraction.enabled, abstraction.models_metamods)
        self.offers = tuple(offers)
        self.position_of = {id(offer): position for position, offer in enumerate(self.offers)}
        self._pool = parallel.WorkerPool(_Worker, (spec, start, self.offers), workers=workers)

    def positions(self, offers: Sequence[PricedOffer]) -> tuple[int, ...] | None:
        """The positions of `offers` in this pool's list, or None when one of them is not from it."""
        try:
            return tuple(self.position_of[id(offer)] for offer in offers)
        except KeyError:
            return None

    def build(self, tasks: Sequence[tuple[CompressedState, tuple[int, ...]]]) -> list[list]:
        """For each (state, positions) the list of actions (None for a refusal), in the order given."""
        return self._pool.map(_build, tasks)

    def close(self) -> None:
        self._pool.close()


@contextmanager
def open_pool(abstraction: Abstraction, start: CompressedState, offers: Sequence[PricedOffer]) -> Iterator[StatePool | None]:
    """A `StatePool` for the length of the block, or None when `CRAFTING_WORKERS` is 1 (or the machine has one core)."""
    workers = parallel.worker_count()
    if workers < 2:
        yield None
        return
    pool = StatePool(abstraction, start, offers, workers)
    try:
        yield pool
    finally:
        pool.close()
