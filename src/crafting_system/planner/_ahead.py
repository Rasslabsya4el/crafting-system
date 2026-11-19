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

When a pool pays (`Ahead.workers_for`). A pool is forked for a round only when the kernels it would make save more time than the pool costs, both
measured in this run: the saving is the round's tips times the seconds of kernel making per tip of the last round (made here or in a worker),
times `1 - 1/workers`; the cost is the seconds of the fork of each worker, as the last pool's fork measured them (the first `submit`, where the
workers are forked: it grows with the process's size and the workers' number), plus, per tip, what the pooled rounds lost beyond their useful
work spread over the workers (sending, waiting on the slowest chunk, kernels made and not asked for). The round forks the number of workers, up to
the machine's, that saves the most, or none when none saves anything; before this run forked one, a worker's fork is taken to cost `FORK_PRIOR`. No number here is sized for a route (OR-12): the worker count and the memory
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
# Seconds the fork of one worker costs before this run measured one: `_prime`'s measure on R04 (about 60 ms a pool, #1193), taken for a pool of
# four. The first fork's own measure replaces it; it only decides whether the first pool is tried.
FORK_PRIOR = 0.015


def _hold(search: object) -> object:
    return search


def _list(states: Sequence[object]) -> tuple[dict, dict[object, tuple], float]:
    """In a worker: the listings of these states (`Search.listing`), by state, for the first plan's chain."""
    search = parallel.context()
    listed: dict[object, tuple] = {}
    began = time.perf_counter()
    with budget.unasked():
        for state in states:
            try:
                listed[state] = search.listing(state)
            except Exception:  # left to the parent, which meets it at this state
                break
            finally:
                search.p.release()
    return {}, listed, time.perf_counter() - began


def _make(tips: Sequence[int]) -> tuple[dict[int, dict[int, tuple[object, float]]], dict[object, tuple], float]:
    """In a worker: realize these tips as `Search.run` does and return the kernels made, by tip and offer, each with its seconds, and the
    listings of the tips it expanded, by state (`Search.listing`)."""
    search = parallel.context()
    made: dict[int, dict[int, tuple[object, float]]] = {}
    began = time.perf_counter()
    search.kernels.room = None  # the workers' memory is read by the pool's wait (`parallel.WorkerPool`), not by this copy of the search
    listed = search._made_listed = {}
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
    return made, listed, time.perf_counter() - began


class Ahead:
    """What a search measured of its rounds' work and of its pools, and the rule that decides whether a round forks one (the module's note)."""

    def __init__(self, workers: int, poll: float, *, always: bool = False) -> None:
        self.workers = workers
        self.poll = poll
        self.always = always  # a pool at every round of two tips or more, whatever the measures (the tests: they never read the clock)
        self.stopped: str | None = None  # the memory net a pool met: no pool again in this search
        self.fork: float | None = None  # seconds of the fork of one worker, at the last pool (its first `submit`, over its workers)
        self.lost = 0.0  # seconds the pooled rounds waited beyond the useful work spread over the workers, the forks left out
        self.lost_tips = 0  # the tips of those rounds
        self.making = 0.0  # seconds of kernel making in this round so far: here, or in a worker for the kernels taken from it
        self.per_tip: float | None = None  # seconds of kernel making per tip, of the last round that had tips
        self.pooled = 0  # rounds that forked a pool
        self.processes = 1  # processes at work in the last round (this one and its workers)

    def workers_for(self, tips: int, per_item: float | None = None) -> int:
        """The workers a round of `tips` tips forks (or a chain with that many states ahead, `per_item` seconds each): the count that saves the
        most time by the measures (the module's note), or 0."""
        if tips < 2 or self.workers < 2 or self.stopped is not None:
            return 0
        if self.always:
            return self.workers
        pace = self.per_tip if per_item is None else per_item
        if pace is None:
            return 0
        fork = FORK_PRIOR if self.fork is None else self.fork
        lost = (self.lost / self.lost_tips if self.lost_tips else 0.0) * tips
        best, choice = 0.0, 0
        for count in range(2, self.workers + 1):
            gain = pace * tips * (1.0 - 1.0 / count) - fork * count - lost
            if gain > best:
                best, choice = gain, count
        return choice

    def window(self, workers: int, per_item: float | None = None) -> int:
        """Items per window: about `WINDOW` polls of work per worker at the pace measured (the last round's per tip, unless another is
        given), and at least a chunk per worker."""
        least = workers * CHUNKS
        pace = self.per_tip if per_item is None else per_item
        if pace is None or pace <= 0.0:
            return least
        return max(least, int(WINDOW * self.poll * workers / pace))

    def end_round(self, tips: int) -> None:
        if tips:
            self.per_tip = self.making / tips
        self.making = 0.0


class Round:
    """A pool that makes ahead, in windows, the work of a list of nodes the search walks in its order, and hands it over node by node (`at`):
    the tips of a round (`_make`: kernels and listings), or the states of the first plan's chain (`_list`: listings; the chain's queue grows as it
    is walked, and a window is sent once the queue holds one)."""

    def __init__(self, search: object, items: list[int], ahead: Ahead, workers: int, *, chain: bool = False, per_item: float | None = None) -> None:
        self.search = search
        self.ahead = ahead
        self.items = items  # the search's own list: a chain's queue grows while it is walked
        self.chain = chain
        self.workers = workers
        self.size = ahead.window(workers, per_item)
        self.pool: parallel.WorkerPool | None = parallel.WorkerPool(_hold, (search,), workers=self.workers)
        self.pending: list[tuple[int, list[Future]]] = []  # (first item's place, futures of its chunks), oldest first
        self.next = 0  # the place of the first item not yet sent
        self.memo: dict[int, dict[int, tuple[object, float]]] = {}
        self.waited = 0.0
        self.useful = 0.0  # the workers' seconds of the work the search took from them (added by `Search._kernel` and `Search.expand`)
        self.forked = False
        ahead.pooled += 1
        ahead.processes = 1 + self.workers

    def _send(self, place: int) -> bool:
        start = max(self.next, place + 1 if self.chain else place)
        window = self.items[start : start + self.size]
        if self.chain:  # the states, sent as they are: the workers forked before the chain met them
            if len(window) < min(self.size, self.workers * CHUNKS):
                return False
            search = self.search
            pieces = [search.states[j] for j in window if not search.expanded[j] and not search.goal[j]]  # the chain expands no goal
        else:
            pieces = window
        if not window:
            return False
        step = max(1, -(-len(pieces) // (self.workers * CHUNKS)))
        mark = time.perf_counter()
        try:
            futures = [self.pool.submit(_list if self.chain else _make, pieces[at : at + step]) for at in range(0, len(pieces), step)]
        except Exception:  # the fork failed (no memory) or the pool broke: this process goes on alone, as with one worker
            self._drop()
            return False
        if not self.forked and futures:  # the workers are forked at the first submit
            self.forked = True
            self.ahead.fork = (time.perf_counter() - mark) / self.workers
        self.pending.append((start, futures))
        self.next = start + len(window)
        return True

    def at(self, place: int, tip: int) -> dict[int, tuple[object, float]] | None:
        """The kernels made ahead at the node at this place (offer -> (weights, seconds)), or None: the search makes them. The listings made
        ahead go to the search's `_listed`, where `expand` takes them."""
        while self.pool is not None and len(self.pending) < 2 and self._send(place):
            pass
        if self.pool is not None and self.pending and self.pending[0][0] <= place:
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
                for made, listed, _ in results:
                    self.memo.update(made)
                    self.search._listed.update(listed)
                while self.pool is not None and len(self.pending) < 2 and self._send(place):
                    pass
        return self.memo.pop(tip, None)

    def give_room(self, limit: float, growth: float = 0.0) -> None:
        """Drop the pool when this process and its workers hold `limit` MB or more, with `growth` MB to come: the search's own memory net reads the
        workers too (`resident_mb`), and a net they took it to is met by stopping them, the search going on alone as one process does (no pool
        again in this search)."""
        if self.pool is None:
            return
        held = parallel.held_mb(under=limit - growth, paced=False)
        if held is not None and held + growth >= limit:
            self.ahead.stopped = f"this process and its workers held {held:,.0f} MB, the limit is {limit:,.0f} MB; the workers were stopped"
            self._drop()

    def _drop(self) -> None:
        pool, self.pool = self.pool, None
        self.pending.clear()
        self.memo.clear()
        self.search._listed.clear()
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
        self.search._listed.clear()
        if tips_walked:
            self.ahead.lost += max(0.0, self.waited - self.useful / self.workers)
            self.ahead.lost_tips += tips_walked
