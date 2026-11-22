"""The keys of a bound's build expanded side by side in forked workers (#1384): the build of the model, and its growth, on several cores.

A pass of the build (`PatternBuilder._pass_keys`) expands its keys one after the other: at each, `_offers_of_key` makes the key's members for
each offer it is given, asks the kernel key of every (member, offer) pair, takes the kernel of a key met before (`computed`) and makes the
others. Measured on R04 and R13 (`.claude/scratch/t1384`), nearly all of a pass is that work at a key: the members, the pairs' refusal classes
and kernel keys, the loop over the pairs. What a key's row holds reads the key, the offers it is given, the universe of slots (which decides its
members) and the abstraction, never what another key of the pass made: a kernel is a function of its pair, and a kernel met before only saves
its making. So a worker forked from this process that runs the same `_offers_of_key` at a key makes the row this process would make there,
with its own numbers for the kernels and keys it made after the fork.

This process still walks every key in its order and decides everything that numbers the model (`PatternBuilder._apply`): it takes the row, its
kernels made before the fork as they are, and does again, in the order the worker met them, what the worker made that this process numbers:
each kernel the worker made (`_replay`) is looked up by its kernel key in this process's `computed`, as `_offers_of_key` would look it up here,
and made here from the worker's outcomes only where this process has none (the outcomes noted in the universe and their keys numbered, as
there). So the keys, their numbers, the kernels and their numbers, the rows and the values are those of one process, whatever the number of
workers. The net is asked at each offer as one process asks it, and the pieces of work of a run counted in pieces (`Tally`) are added offer
by offer, so a count stops where one process stops. What is left to this process: a key whose kernels found a slot the universe lacked (the
universe then differs from this process's, and a pool forked before it is closed: the next one forks from the grown universe), a relaxed
draw (its choice nodes are numbered in the order the build makes them), a key a worker failed at, and every key while no pool pays.

A pool is forked once a pass has measured its keys: the work left (its keys still to expand times the seconds a key took, here or in a worker)
times `1 - 1/workers` must save more than the fork costs (each worker's fork, as the last pool measured it, `FORK_PRIOR` before one) and what
the pools of this build lost per key beyond their work spread over the workers. The keys are sent in windows of about `WINDOW` polls of work
per worker, cut in `CHUNKS` chunks per worker; two windows are in flight while this process takes the one before. No number here is sized for a
route (OR-12): the worker count and the memory net are the machine's settings (OR-40). The rule decides only when work is done, never a result.

Memory. The workers are forked: they share this process's pages until they write them (`parallel.WorkerPool` freezes the objects for the fork,
#1345), and what they make is their own. Each worker's memos (`computed`, the members kept, the members' feasibility, the label distributions)
keep `1/workers` of the share of the net this process's memos keep, so the pool's memos hold the share one process holds; what comes back is
the rows and the outcomes of the kernels made, never a memo. The wait on the workers reads this process's and their memory against the run's
net (`parallel.WorkerPool.gather`); once it is reached the workers are stopped and no pool forks again in this build.
"""

import os
import time
from concurrent.futures import Future

from crafting_system import budget, parallel

from ._recent import FEWEST_KEPT, Recent

CHUNKS = 4  # the chunks of a window per worker: a slow chunk holds one worker for a part of the window (speed only, never a result)
WINDOW = 4  # the polls of work per worker a window holds (`POLL_SECONDS` of `_pattern`): the nets are asked between two windows too
FORK_PRIOR = 0.015  # seconds the fork of one worker costs before this build measured one (`_ahead.FORK_PRIOR`, #1340); the first fork's measure replaces it
ALWAYS = False  # a pool at every pass with keys to send, whatever the measures (the tests: they never read the clock)


def _hold(builder: object, workers: int) -> object:
    """In a worker, once: its memos keep `1/workers` of what this process's keep (the module's note)."""
    for memo in builder.memos():
        _share(memo, workers)
    return builder


def _share(memo: Recent, workers: int) -> None:
    size = memo.size
    if callable(size):
        memo.size = lambda size=size: max(FEWEST_KEPT, size() // workers)
    else:
        memo.size = max(FEWEST_KEPT, size // workers)


def _rows(tasks: list[tuple]) -> tuple[int, list[tuple[int, tuple | None]], float]:
    """In a worker: the rows of these keys (`PatternBuilder.row_ahead`), each with its key's number, and the seconds they took."""
    builder = parallel.context()
    began = time.perf_counter()
    made = []
    with budget.unasked():  # a forked worker holds its parent's net: the parent asks it between two keys and while it waits
        for task in tasks:
            made.append((task[0], builder.row_ahead(task)))
    return os.getpid(), made, time.perf_counter() - began


class KeysAhead:
    """The pool of a pass, its windows of keys, and the measures that decide whether a pass forks one (the module's note)."""

    def __init__(self, builder: object, workers: int, *, poll: float = 0.5) -> None:
        self.builder = builder
        self.workers = workers
        self.poll = poll
        self.stopped: str | None = None  # the memory net a pool met: no pool again in this build
        self.fork: float | None = None  # seconds of the fork of one worker, at the last pool (its first `submit`, over its workers)
        self.lost = 0.0  # seconds the pools waited beyond the work of the keys taken spread over the workers
        self.lost_keys = 0
        self.spent = 0.0  # seconds of work of the keys expanded so far, here or in a worker
        self.keys = 0  # those keys
        self.pool: parallel.WorkerPool | None = None
        self.pending: list[tuple[int, int, list[Future]]] = []  # (first key's number, the number after the last, futures of its chunks), oldest first
        self.next = 0  # the number of the first key not yet sent
        self.memo: dict[int, tuple] = {}  # key number -> (worker pid, the worker's row)
        self.tables: dict[int, dict[int, int]] = {}  # worker pid -> its kernel ids -> this process's, of the kernels taken from it (`_apply`)
        self.fork_grew = 0  # the universe's growth count at the fork (`Pattern.grew`): a worker's rows hold while both are at it
        self.base = 0  # the kernels this process had at the fork: a worker's kernel ids below it are this process's
        self.keys_base = 0  # and the keys: a worker's key numbers below it are this process's
        self.waited = 0.0
        self.useful = 0.0  # the workers' seconds of the keys this process took from them
        self.forked = False
        self.since = 0.0  # seconds of work done here since the rule was last asked
        self.pools = 0  # pools forked in this build
        self.taken = 0  # rows taken from the workers (`PatternBuilder._apply`)
        self.sent = 0  # keys sent to them
        self.left = 0  # keys a worker left to this process (`PatternBuilder.row_ahead` gave None)

    @property
    def open(self) -> bool:
        return self.pool is not None

    def alone(self, seconds: float) -> None:
        """A key expanded here: its seconds go to the pace of the keys."""
        self.spent += seconds
        self.keys += 1
        self.since += seconds

    def take(self, i: int) -> tuple | None:
        """The row of key number `i` made in a worker, `(worker pid, row)`, or None: this process expands the key itself."""
        if self.pool is not None and self.builder.pattern.grew != self.fork_grew:  # this process's universe grew: the workers' members are stale
            self.close()
        if self.pool is None:
            if not self._pays(i):
                return None
            self._fork(i)
        self._fill(i)
        while self.pool is not None and self.pending and self.pending[0][0] <= i:  # the window that holds this key: wait for it
            self._gather()
            self._fill(i)
        return self.memo.pop(i, None)

    def _fill(self, i: int) -> None:
        while self.pool is not None and len(self.pending) < 2 and self._send(i):
            pass

    def _pays(self, i: int) -> bool:
        """Whether a pool forked now saves time, by this build's measures (the module's note); asked once a poll of work done here."""
        if self.workers < 2 or self.stopped is not None:
            return False
        if ALWAYS:
            return True
        if self.keys == 0 or self.since < self.poll:
            return False
        self.since = 0.0
        left = self.builder.keys_to_expand(i)
        per_key = self.spent / self.keys
        fork = FORK_PRIOR if self.fork is None else self.fork
        lost = self.lost / self.lost_keys if self.lost_keys else 0.0
        return per_key * left * (1.0 - 1.0 / self.workers) > fork * self.workers + lost * left

    def _fork(self, i: int) -> None:
        net = parallel.active_memory_net()
        held = parallel.held_mb(under=net, paced=False) if net is not None else None
        if net is not None and held is not None and held >= net:  # no room for the workers' own memory: they would be stopped at once
            return
        builder = self.builder
        self.pool = parallel.WorkerPool(_hold, (builder, self.workers), workers=self.workers)
        self.fork_grew, self.base, self.keys_base = builder.pattern.grew, len(builder.kernels), len(builder.keys)
        self.next, self.forked, self.waited, self.useful = i, False, 0.0, 0.0
        self.tables = {}
        self.pools += 1

    def _size(self) -> int:
        least = self.workers * CHUNKS
        per_key = self.spent / self.keys if self.keys else None
        if per_key is None or per_key <= 0.0:
            return least
        return max(least, int(WINDOW * self.poll * self.workers / per_key))

    def _send(self, i: int) -> bool:
        builder = self.builder
        start = max(self.next, i)
        tasks, end = builder.tasks_from(start, self._size())
        if not tasks:
            self.next = max(self.next, end)
            return False
        step = max(1, -(-len(tasks) // (self.workers * CHUNKS)))
        mark = time.perf_counter()
        try:
            futures = [self.pool.submit(_rows, tasks[at : at + step]) for at in range(0, len(tasks), step)]
        except Exception:  # noqa: BLE001  (the fork failed, no memory, or the pool broke: this process goes on alone, as with one worker)
            self._drop()
            return False
        if not self.forked:  # the workers are forked at the first submit
            self.forked = True
            self.fork = (time.perf_counter() - mark) / self.workers
        self.pending.append((start, end, futures))
        self.next = end
        self.sent += len(tasks)
        return True

    def _gather(self) -> None:
        _, _, futures = self.pending.pop(0)
        mark = time.perf_counter()
        try:
            tally = self.builder.tally  # the net on the clock, asked while this process waits as it is asked between two offers (a count is not)
            results = self.pool.gather(futures, stop=self.builder.stop if tally is None else tally.then)
        except parallel.MemoryNetReached as reached:  # the workers' memory passed the net: they are stopped, and no pool forks again in this build
            self.stopped = str(reached)
            self._drop()
            return
        except (Exception, budget.BudgetExceeded):  # noqa: BLE001  (a worker failed, or a net was met while waiting: this process goes on alone and meets it itself)
            self._drop()
            return
        self.waited += time.perf_counter() - mark
        for pid, made, seconds in results:
            self.useful += seconds
            self.spent += seconds
            self.keys += len(made)
            for k, row in made:
                if row is not None:
                    self.memo[k] = (pid, row)
                else:
                    self.left += 1

    def _drop(self) -> None:
        pool, self.pool = self.pool, None
        self.pending.clear()
        self.memo.clear()
        if pool is not None:
            pool.abandon()

    def close(self) -> None:
        """End the pass's pool (workers still making a window are stopped) and add what it lost to the measures."""
        if self.pool is None:
            return
        pool, self.pool = self.pool, None
        if self.pending:
            pool.abandon()
        else:
            pool.close()
        self.pending.clear()
        self.memo.clear()
        if self.sent:
            self.lost += max(0.0, self.waited - self.useful / self.workers)
            self.lost_keys += self.sent
        self.waited = self.useful = 0.0
        self.sent = 0


__all__ = ["KeysAhead"]
