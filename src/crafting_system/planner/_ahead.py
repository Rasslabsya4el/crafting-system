"""The kernels of a round's tips made side by side in forked workers (#1340): the envelope search on several cores.

A round of the search expands its tips one after the other (`_envelope.Search.run`): at each, `realize` makes the kernels of the offers whose
lower bound is below the best realized so far there. What it decides at a tip reads the last solve's values, the bound of the states
(`Problem.lower`) and the kernels it makes at that tip, never what an earlier tip of the round made: a successor first met in the round takes its
bound either way. So a worker forked at the round's start that runs the same `realize` over some of the tips makes the kernels this process will
ask for there, and this process takes them from it in place of making them (`Search._kernel`). This process still walks every tip in its order
and decides everything itself: the states and their numbers, the kernels shared by key, the offers realized and the values are those of one
process, whatever the number of workers. A kernel is a function of its state and its offer (`Abstraction.kernel`: its caches only make it
faster), so the one a worker made is the one this process would make. Where a worker decides otherwise than this process (an offer's floor it
tightened on another cache, a kernel key that an earlier chunk of its own met), it only makes a kernel that is not asked for, or leaves one to
this process.

The tips are cut into windows and each window into chunks, `CHUNKS` per worker; the workers make the next window while this process walks the
tips of the one before, and between two windows this process asks its nets as it does between two tips. A window holds about `WINDOW` polls of
the round's work per worker (`POLL_SECONDS`), so the nets are asked about as often as with one process.

When a pool pays (`Ahead.pays`). A pool is forked for a round only when the kernels it would make save more time than the pool costs, both
measured in this run: the saving is the round's tips times the seconds of kernel making per tip of the last round (made here or in a worker),
times `1 - 1/workers`; the cost is the seconds the last fork took (the first `submit`, where the workers are forked) plus, per tip, what the
pooled rounds lost beyond their useful work spread over the workers (sending, waiting on the slowest chunk, kernels made and not asked for).
Before this run forked one, a fork is taken to cost `FORK_PRIOR`. No number here is sized for a route (OR-12): the worker count and the memory
net are the machine's settings (OR-40). The rule decides only when work is done, never a result.

Not used with one worker (`CRAFTING_WORKERS=1`), where there is no fork (Windows, OR-57), in a run counted in states (`Search.counted`: the count
is made in this process as each kernel is made, #1105), and, for the rest of the search, once a pool met the memory net: the workers' own memory
counts against it (`parallel.WorkerPool`, #626).
"""

import time
from collections.abc import Sequence
from concurrent.futures import Future

from crafting_system import budget, parallel

CHUNKS = 4  # the chunks of a window per worker: a slow chunk holds one worker for a part of the window (speed only, never a result)
WINDOW = 4  # the polls of work per worker a window holds (`POLL_SECONDS`): the nets are asked between two windows
# Seconds a pool costs before this run measured one: `_prime`'s measure on R04 (about 60 ms a pool, #1193). The first fork's own measure
# replaces it; it only decides whether the first pool is tried.
FORK_PRIOR = 0.06


def _hold(search: object) -> object:
    return search


def _make(tips: Sequence[int]) -> tuple[dict[int, dict[int, tuple[object, float]]], float]:
    """In a worker: realize these tips as `Search.run` does and return the kernels made, by tip and offer, each with its seconds."""
    search = parallel.context()
    made: dict[int, dict[int, tuple[object, float]]] = {}
    began = time.perf_counter()
    search.kernels.room = None  # the workers' memory is read by the pool's wait (`parallel.WorkerPool`), not by this copy of the search
    search._made = made
    try:
        with budget.unasked():  # a forked worker holds its parent's net: the parent asks it between two windows
            for i in tips:
                try:
                    if not search.expanded[i]:
                        search.expand(i)
                    search.realize(i, force=True)
                except Exception:  # left to the parent, which meets it at this tip and raises it there in its own order
                    break
                finally:
                    search.p.release()
    finally:
        search._made = None
    return made, time.perf_counter() - began


class Ahead:
    """What a search measured of its rounds' work and of its pools, and the rule that decides whether a round forks one (the module's note)."""

    def __init__(self, workers: int, poll: float, *, always: bool = False) -> None:
        self.workers = workers
        self.poll = poll
        self.always = always  # a pool at every round of two tips or more, whatever the measures (the tests: they never read the clock)
        self.stopped: str | None = None  # the memory net a pool met: no pool again in this search
        self.fork: float | None = None  # seconds of the last fork (the first `submit` of a round's pool)
        self.lost = 0.0  # seconds the pooled rounds waited beyond the useful work spread over the workers, the forks left out
        self.lost_tips = 0  # the tips of those rounds
        self.making = 0.0  # seconds of kernel making in this round so far: here, or in a worker for the kernels taken from it
        self.per_tip: float | None = None  # seconds of kernel making per tip, of the last round that had tips
        self.pooled = 0  # rounds that forked a pool
        self.processes = 1  # processes at work in the last round (this one and its workers)

    def pays(self, tips: int) -> bool:
        if tips < 2 or self.workers < 2 or self.stopped is not None:
            return False
        if self.always:
            return True
        if self.per_tip is None:
            return False
        saving = self.per_tip * tips * (1.0 - 1.0 / self.workers)
        cost = (FORK_PRIOR if self.fork is None else self.fork) + (self.lost / self.lost_tips if self.lost_tips else 0.0) * tips
        return saving > cost

    def window(self) -> int:
        """Tips per window: about `WINDOW` polls of work per worker at the last round's pace, and at least a chunk per worker."""
        least = self.workers * CHUNKS
        if self.per_tip is None or self.per_tip <= 0.0:
            return least
        return max(least, int(WINDOW * self.poll * self.workers / self.per_tip))

    def end_round(self, tips: int) -> None:
        if tips:
            self.per_tip = self.making / tips
        self.making = 0.0


class Round:
    """The pool of one round: windows of its tips made ahead in the workers, handed to the search tip by tip (`at`)."""

    def __init__(self, search: object, tips: Sequence[int], ahead: Ahead) -> None:
        self.ahead = ahead
        self.tips = list(tips)
        self.size = ahead.window()
        self.workers = min(ahead.workers, max(2, -(-len(self.tips) // CHUNKS)))
        self.pool: parallel.WorkerPool | None = parallel.WorkerPool(_hold, (search,), workers=self.workers)
        self.pending: list[tuple[int, list[Future]]] = []  # (first tip's place, futures of its chunks), oldest first
        self.next = 0  # the place of the first tip not yet sent
        self.memo: dict[int, dict[int, tuple[object, float]]] = {}
        self.waited = 0.0
        self.useful = 0.0  # the workers' seconds of the kernels the search took from them (added by `Search._kernel`)
        self.forked = False
        ahead.pooled += 1
        ahead.processes = 1 + self.workers

    def _send(self) -> None:
        if self.pool is None or self.next >= len(self.tips):
            return
        window = self.tips[self.next : self.next + self.size]
        step = max(1, -(-len(window) // (self.workers * CHUNKS)))
        mark = time.perf_counter()
        futures = [self.pool.submit(_make, window[start : start + step]) for start in range(0, len(window), step)]
        if not self.forked:  # the workers are forked at the first submit
            self.forked = True
            self.ahead.fork = time.perf_counter() - mark
        self.pending.append((self.next, futures))
        self.next += len(window)

    def at(self, place: int, tip: int) -> dict[int, tuple[object, float]] | None:
        """The kernels made ahead at the tip at this place of the round (offer -> (weights, seconds)), or None: the search makes them."""
        if self.pool is not None and place == 0:
            self._send()
            self._send()
        if self.pool is not None and self.pending and self.pending[0][0] == place:
            _, futures = self.pending.pop(0)
            mark = time.perf_counter()
            try:
                results = self.pool.gather(futures)
            except parallel.MemoryNetReached as reached:  # the workers' memory passed the net: they are stopped, and no pool forks again in this search
                self.ahead.stopped = str(reached)
                self._drop()
            except (Exception, budget.BudgetExceeded):  # a worker failed, or the run's net was met while waiting: this process goes on alone and meets it itself
                self._drop()
            else:
                self.waited += time.perf_counter() - mark
                for made, _ in results:
                    self.memo.update(made)
                self._send()
        return self.memo.pop(tip, None)

    def _drop(self) -> None:
        pool, self.pool = self.pool, None
        self.pending.clear()
        self.memo.clear()
        if pool is not None:
            pool.abandon()

    def close(self, tips_walked: int) -> None:
        """End the round's pool (the workers still making a window are stopped) and add what it lost to the measures."""
        if self.pool is not None:
            pool, self.pool = self.pool, None
            if self.pending:
                pool.abandon()
            else:
                pool.close()
        self.memo.clear()
        if tips_walked:
            self.ahead.lost += max(0.0, self.waited - self.useful / self.workers)
            self.ahead.lost_tips += tips_walked
