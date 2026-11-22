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
by offer, so a count stops where one process stops. The figures of work that hang on a process's memos may differ (the members made and the
kernels made, which a memo that let a list or a kernel go makes again, and the refusals shared): never a key, a row or a value. What is left
to this process: a key whose kernels found a slot the universe lacked, or met an influence set whose family types were not numbered yet (the
universe or the numbers that name slots then differ from this process's, `PatternBuilder.version`, and a pool forked before is closed: the
next one forks from what this process has then), a relaxed draw (its choice nodes are numbered in the order the build makes them), a key a
worker failed at, and every key while no pool pays. A key holding imprints is sent with the snapshots this process's members of it hold (the
first met, `Pattern.held_of`), and an outcome holding imprints whose key is new comes back as its state, whose key this process reads itself,
so the snapshots it meets first are the ones one process meets.

A pool is forked once a pass has measured its keys: the work left (its keys still to expand times the seconds a key took, here or in a worker)
times `1 - 1/workers` must save more than the fork costs (each worker's fork, as the last pool measured it, `FORK_PRIOR` before one) and what
the pools of this build lost per key beyond their work spread over the workers. The keys are sent in windows of about `WINDOW` polls of work
per worker, cut in `CHUNKS` chunks per worker; two windows are in flight while this process takes the one before. No number here is sized for a
route (OR-12): the worker count and the memory net are the machine's settings (OR-40). The rule decides only when work is done, never a result.

Memory. The workers are forked: they share this process's pages until they write them (`parallel.WorkerPool` freezes the objects for the fork,
#1345), and what they make is their own. A worker's memos (`computed`, the members kept, the members' feasibility, the label distributions)
keep what they held at the fork and grow only by what that worker makes (`Recent.refresh` off: an entry read is not written again, so the
reads of a pass never push out what the fork gave). A pass's workers together make about what one process makes in that pass, each its
share of the keys, and the pool closes at the pass end; what comes back is the rows and the outcomes of the kernels made, never a memo. (With
each memo cut to `1/workers` of its size, the reads of a pass pushed the inherited entries out: on R04's spread pass of model 10, 229 s with
six workers where one process took 123 s, its kernels made again.) The wait on the workers reads this process's and their memory against the run's
net (`parallel.WorkerPool.gather`); once it is reached the workers are stopped, and the next pool forks one worker fewer (`_cut`): a worker
holds what it copied of this process's pages (a fork shares them until either side writes, and reading an object writes its count) and what
it made, so where the net is near fewer of them fit. Below two workers no pool forks again in this build. The build's own net, asked between
two offers or keys, reads the workers too: reached with a pool open, the pool is cut and the net asked again (`asked`), so the workers never
stop a build one process would have built whole (R17).

A pool whose rows cost this process what they save (`_idle`: taking a row, its kernels' outcomes numbered here, takes as long as a worker took
to make it) is let go for the rest of the pass (R17: keys of 100,000 kernels each). Tried and dropped: a pool kept from pass to pass (its
workers lacked each other's kernel keys: R04's spread passes ran slower than one process), and a pool made afresh once its workers held half
the room the net leaves (on R04 it threw away windows ten times a round and gave back the gain).
"""

import os
import time
from concurrent.futures import Future

from crafting_system import budget, parallel


CHUNKS = 4  # the chunks of a window per worker: a slow chunk holds one worker for a part of the window (speed only, never a result)
WINDOW = 4  # the polls of work per worker a window holds (`POLL_SECONDS` of `_pattern`): the nets are asked between two windows too
IDLE_WINDOWS = 4  # the windows of rows a pool's cost here is measured on before it may be let go for the pass (`_idle`; speed only)
MOST_PER_CHUNK = 256  # the most keys a chunk holds: with keys of microseconds a window of polls would be 10^5 keys and their pickles (speed only)
FORK_PRIOR = 0.015  # seconds the fork of one worker costs before this build measured one (`_ahead.FORK_PRIOR`, #1340); the first fork's measure replaces it
ALWAYS = False  # a pool at every pass with keys to send, whatever the measures (the tests: they never read the clock)


def _hold(builder: object, workers: int) -> object:
    """In a worker, once: its memos keep what they held at the fork, and grow only by what this worker makes (the module's note)."""
    for memo in builder.memos():
        memo.refresh = False
    return builder


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
        self.workers = workers  # the machine's setting (`CRAFTING_WORKERS`)
        self.count = workers  # the workers a pool forks: one fewer each time a pool met the memory net, none below two (`_cut`)
        self.poll = poll
        self.stopped: str | None = None  # the memory net a pool met: no pool again in this build
        self.fork: float | None = None  # seconds of the fork of one worker, at the last pool (its first `submit`, over its workers)
        self.lost = 0.0  # seconds the pools waited beyond the work of the keys taken spread over the workers
        self.lost_keys = 0
        self.spent = 0.0  # seconds of work of the keys expanded so far, here or in a worker
        self.replay = 0.0  # seconds this process spent taking workers' rows (`applied`)
        self.replayed = 0
        self.replayed_at_fork = self.keys_at_fork = 0
        self.worker_keys = 0  # keys the workers made (`_gather`)
        self.replay_at_fork = self.useful_at_fork = 0.0
        self.keys = 0  # those keys
        self.pool: parallel.WorkerPool | None = None
        self.pending: list[tuple[int, int, list[Future]]] = []  # (first key's number, the number after the last, futures of its chunks), oldest first
        self.next = 0  # the number of the first key not yet sent
        self.memo: dict[int, tuple] = {}  # key number -> (worker pid, the worker's row)
        self.tables: dict[int, dict[int, int]] = {}  # worker pid -> its kernel ids -> this process's, of the kernels taken from it (`_apply`)
        self.fork_version: tuple = ()  # what the workers' members and states are made of, at the fork (`PatternBuilder.version`): a worker's rows hold while both are at it
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
        self.pass_off = False  # no pool again in this pass (`_gather`)
        self.gathered = 0  # windows of this pass that came back (`_idle`)
        self.worked = 0.0  # the workers' seconds of this pass

    @property
    def open(self) -> bool:
        return self.pool is not None

    def applied(self, seconds: float) -> None:
        """A worker's row taken here (`PatternBuilder._apply`): its seconds, for the rule."""
        self.replay += seconds
        self.replayed += 1
        self.since += seconds

    def alone(self, seconds: float) -> None:
        """A key expanded here: its seconds go to the pace of the keys."""
        self.spent += seconds
        self.keys += 1
        self.since += seconds

    def take(self, i: int) -> tuple | None:
        """The row of key number `i` made in a worker, `(worker pid, row)`, or None: this process expands the key itself."""
        if self.pool is not None and self.builder.version() != self.fork_version:  # this process's universe grew, or it numbered a family type: the workers' members are stale
            self.close()
        if self.pool is None:
            if self.memo and self.builder.version() != self.fork_version:  # rows `_apply` would refuse: let them go, a pool may fork at once
                self.memo.clear()
            if self.memo:  # rows of a pool closed to be made afresh (`_fill`): taken first, with that pool's numbers
                return self.memo.pop(i, None)
            if not self._pays(i):
                return None
            self._fork(i)
        self._fill(i)
        while self.pool is not None and self.pending and self.pending[0][0] <= i:  # the window that holds this key: wait for it
            self._gather()
            self._fill(i)
        return self.memo.pop(i, None)

    def _fill(self, i: int) -> None:
        if self.pool is not None and self._idle():
            pool, self.pool = self.pool, None  # (the rows already in stay, as above)
            if self.pending:
                pool.abandon()
                self.pending.clear()
            else:
                pool.close()
            self._account()
            self.pass_off = True
            if self.builder.progress is not None:
                self.builder.progress("keys' workers: let go for this pass (taking their rows here costs about what making them does)")
            return
        while self.pool is not None and len(self.pending) < 2 and self._send(i):
            pass

    def _pays(self, i: int) -> bool:
        """Whether a pool forked now saves time, by this build's measures (the module's note); asked once a poll of work done here."""
        if self.count < 2 or self.stopped is not None or self.pass_off:
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
        # (what taking a worker's row costs here is asked of each pool once a window of its rows was taken, `_idle`: a figure of the whole
        # build kept pools from R04's later passes, whose rows cost little, after model 2's new keys, whose rows cost more)
        return per_key * left * (1.0 - 1.0 / self.count) > fork * self.count + lost * left

    def _fork(self, i: int) -> None:
        net = parallel.active_memory_net()
        held = parallel.held_mb(under=net, paced=False) if net is not None else None
        if net is not None and held is not None and held >= net:  # no room for the workers' own memory: they would be stopped at once
            return
        builder = self.builder
        self.pool = parallel.WorkerPool(_hold, (builder, self.count), workers=self.count)
        self.fork_version, self.base, self.keys_base = builder.version(), len(builder.kernels), len(builder.keys)
        self.next, self.forked, self.waited, self.useful = i, False, 0.0, 0.0
        self.tables = {}
        self.pools += 1

    def _size(self) -> int:
        least = self.count * CHUNKS
        per_key = self.spent / self.keys if self.keys else None
        if per_key is None or per_key <= 0.0:
            return least
        return min(least * MOST_PER_CHUNK, max(least, int(WINDOW * self.poll * self.count / per_key)))

    def _send(self, i: int) -> bool:
        builder = self.builder
        start = max(self.next, i)
        tasks, end = builder.tasks_from(start, self._size())
        if not tasks:
            self.next = max(self.next, end)
            return False
        step = max(1, -(-len(tasks) // (self.count * CHUNKS)))
        mark = time.perf_counter()
        try:
            futures = [self.pool.submit(_rows, tasks[at : at + step]) for at in range(0, len(tasks), step)]
        except Exception:  # noqa: BLE001  (the fork failed, no memory, or the pool broke: this process goes on alone, as with one worker)
            self._drop()
            return False
        if not self.forked:  # the workers are forked at the first submit
            self.forked = True
            self.fork = (time.perf_counter() - mark) / self.count
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
        except (parallel.MemoryNetReached, budget.BudgetExceeded) as reached:  # the workers' memory passed the net (or the run's net was met):
            self._cut(str(reached))  # they are stopped, and the next pool forks one worker fewer
            return
        except parallel.Stopped as reached:  # the build's net was met while waiting (the workers' memory counts in it): stopped as in `asked`
            self._cut(f"the build's net was reached with the workers alive: {reached}")
            return
        except Exception as failed:  # noqa: BLE001  (the pool broke: this process goes on alone, and forks none again in this build)
            self._stop(f"the pool of the keys failed: {failed!r}")
            return
        self.waited += time.perf_counter() - mark
        self.gathered += 1
        if self.gathered == 2:  # `_idle` is told from the pass's second window on: the first's rows are taken by now (R04: its first window after the key
            # of 1,245 offers held its 22 other keys given them, whose rows cost this process more than the new keys after them)
            self.replayed_at_fork, self.replay_at_fork = self.replayed, self.replay
            self.keys_at_fork, self.useful_at_fork = self.worker_keys, self.worked
        for pid, made, seconds in results:
            self.useful += seconds
            self.worked += seconds  # (over the pass: `_idle` is told over the pools of a pass, a pool cut by the memory net included)
            self.spent += seconds
            self.keys += len(made)
            self.worker_keys += len(made)
            for k, row in made:
                if row is not None:
                    self.memo[k] = (pid, row)
                else:
                    self.left += 1

    def _idle(self) -> bool:
        """Whether this pool's rows cost this process what they save: once `IDLE_WINDOWS` windows of its rows were taken, the seconds taking a row
        took here are at least the seconds a worker took to make one (the workers make rows while this process takes them, so a pool goes at
        the pace of the slower: R04's new keys, about 3 ms a row here against 7 ms a key in a worker, went 3.5 times one process's pace). On R17's keys of 100,000 kernels,
        taking a row (its kernels' outcomes numbered here) cost what making it did, and the keys after the pool made again here the label
        distributions the workers had made (#1384)."""
        taken = self.replayed - self.replayed_at_fork
        made = self.worker_keys - self.keys_at_fork  # the keys its workers made (the keys this process expanded meanwhile are not in `useful`)
        if self.gathered < 2 or taken < IDLE_WINDOWS * self._size() or made <= 0:
            return False
        replay = (self.replay - self.replay_at_fork) / taken
        worker = (self.worked - self.useful_at_fork) / made
        return replay >= worker  # the workers make rows while this process takes them: a pool's pace is the slower of the two

    def asked(self, stop) -> str | None:
        """The build's net, asked between two offers or two keys: where it is reached while a pool is open, the pool is stopped first (one
        worker fewer next time, `_cut`) and the net asked again, since the workers' memory counts in it (R17: a bound of 773,092 kernels the
        one process built whole was stopped at 12,543 MB with six workers beside it, #1384)."""
        reason = stop()
        if reason is not None and self.pool is not None:
            self._cut(f"the build's net was reached with the workers alive: {reason}")
            reason = stop()
        return reason

    def _cut(self, reason: str) -> None:
        """A pool met the memory net: the next forks one worker fewer, and below two none forks again in this build. A worker's own memory is
        what it copied of this process's pages and what it made in its pass (R04, 12 GB net: six workers took about 1.2 GB each beside this
        process's 4.8 GB, #1384), so fewer of them fit where the net is near."""
        self.count = min(self.count, self.pool.workers if self.pool is not None else self.count) - 1
        parallel.forget_reading()  # the next question reads the memory anew: the last full reading held the workers stopped here
        if self.count < 2:
            self._stop(reason)
            return
        self._drop()
        if self.builder.progress is not None:
            self.builder.progress(f"keys' workers: stopped ({reason}); the next pool forks {self.count}")

    def _stop(self, reason: str) -> None:
        """No pool again in this build: the build says why, and goes on in this process alone."""
        self.stopped = reason
        self._drop()
        if self.builder.progress is not None:
            self.builder.progress(f"keys' workers: stopped ({reason}); the build goes on in one process")

    def _drop(self) -> None:
        pool, self.pool = self.pool, None
        self.pending.clear()
        self.memo.clear()
        if pool is not None:
            pool.abandon()

    def close(self) -> None:
        """End the pass's pool (workers still making a window are stopped) and add what it lost to the measures."""
        self.memo.clear()  # (rows of a pool closed to be made afresh, `_fill`, too)
        if self.pool is None:
            return
        pool, self.pool = self.pool, None
        if self.pending:
            pool.abandon()
        else:
            pool.close()
        self.pending.clear()
        self._account()

    def end_pass(self) -> None:
        """The pass is over: its pool is closed, and the next pass may fork one again."""
        self.close()
        self.pass_off, self.gathered, self.worked, self.worker_keys = False, 0, 0.0, 0
        self.replayed = self.replayed_at_fork = self.keys_at_fork = 0
        self.replay = self.replay_at_fork = self.useful_at_fork = 0.0

    def _account(self) -> None:
        """Add what a closed pool lost to the measures (`_pays`)."""
        if self.sent:
            self.lost += max(0.0, self.waited - self.useful / self.count)
            self.lost_keys += self.sent
        self.waited = self.useful = 0.0
        self.sent = 0


__all__ = ["KeysAhead"]
