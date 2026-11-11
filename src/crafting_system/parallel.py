"""A process pool that gives the same answers for any number of workers (ticket #250).

Shared infrastructure, outside the eleven modules: it imports none of them (like `config.py`).

`worker_count()` is the pool size: the cores of the machine, or `CRAFTING_WORKERS` (1 means serial: no process is
started and the callers run their own serial code, unchanged). A caller that can split a job into independent
pieces makes a `WorkerPool(factory, args)` and `map`s a module-level function over the pieces:

* the pieces are cut in fixed-size chunks in the order given, and the results come back in that order, so the list
  `map` returns is the list a plain loop would build, whatever the number of workers or the order they finish in;
* each worker builds its own state once, `factory(*args)`, and the function reads it with `context()`; nothing is shared
  between workers, so what a piece returns may depend only on the piece and on what the factory built from `args`;
* a piece never draws from a random stream shared with another piece (a random job gives each piece its own seed).

Where `fork` exists (Linux, macOS) the workers are forked, so `args` are inherited and not pickled; elsewhere (Windows)
they are spawned and `args` are pickled once per worker, which is why the game data's read-only mappings get a pickler
here (`types.MappingProxyType` has none).
"""

import copyreg
import multiprocessing
import os
import sys
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor, wait
from types import MappingProxyType

WORKERS_ENV = "CRAFTING_WORKERS"
MIN_CHUNK = 1  # a chunk is never smaller than this many pieces

_context: object = None  # the state of this process's worker (set by `_initialise`)


def worker_count(env: dict[str, str] | None = None) -> int:
    """The pool size: `CRAFTING_WORKERS` if set (a whole number of 1 or more), else the cores this process may use."""
    value = (os.environ if env is None else env).get(WORKERS_ENV, "").strip()
    if value:
        try:
            count = int(value)
        except ValueError:
            count = 0
        if count < 1:
            raise ValueError(f"{WORKERS_ENV} must be a whole number of 1 or more, got {value!r}")
        return count
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:  # no affinity call on Windows and macOS
        return max(1, os.cpu_count() or 1)


def can_inherit() -> bool:
    """Whether workers can be forked, so that what a caller cannot pickle (a closure) reaches them anyway."""
    return "fork" in multiprocessing.get_all_start_methods()


def context() -> object:
    """What the factory built in this worker process (read by the functions `WorkerPool.map` runs)."""
    return _context


def _fresh_streams() -> None:
    """New `sys.stdout` and `sys.stderr` on the same files, for a forked worker (ticket #535).

    A fork copies the parent's stream objects with their locks as they were at that moment. When another thread of the parent
    was writing (a progress thread printing to a slow pipe), the copy's lock is held by a thread that does not exist in the
    worker, and the worker's first print waits on it forever: R14's risk hung so in heavy runs 42946872857 and 42957520245,
    caught by py-spy in 42964753874 (a worker in `print`, `PyThread_acquire_lock`, its attempt run done).
    """
    for name, number in (("stdout", 1), ("stderr", 2)):
        old = getattr(sys, name)
        if old is None:
            continue
        try:
            fresh = open(number, "w", encoding=getattr(old, "encoding", None), errors=getattr(old, "errors", None), buffering=1, closefd=False)
        except OSError:
            continue
        setattr(sys, name, fresh)


def _initialise(factory: Callable[..., object], args: tuple, forked: bool = False) -> None:
    global _context
    if forked:
        _fresh_streams()
    _context = factory(*args)


def _run_chunk(function: Callable, chunk: Sequence) -> list:
    return [function(piece) for piece in chunk]


def _run_whole(function: Callable, chunk: Sequence) -> object:
    return function(chunk)


def _read_only(mapping: dict) -> MappingProxyType:
    return MappingProxyType(mapping)


def _pickle_mapping_proxy(proxy: MappingProxyType) -> tuple:
    return _read_only, (dict(proxy),)


class WorkerPool:
    """Workers that each hold `factory(*args)`; `map` runs a function over pieces and returns the results in order.

    Use it as a context manager. With `workers` below 2 there is no pool: `map` runs the function in this process
    on a context built here, the same code the workers run (this is how the tests compare 1 and N).
    """

    def __init__(self, factory: Callable[..., object], args: tuple = (), *, workers: int | None = None) -> None:
        self.workers = worker_count() if workers is None else workers
        if self.workers < 1:
            raise ValueError(f"workers must be 1 or more, got {self.workers}")
        self._factory, self._args = factory, args
        self._executor: ProcessPoolExecutor | None = None
        self._local: object = None
        self._have_local = False

    def __enter__(self) -> "WorkerPool":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

    def abandon(self) -> None:
        """Kill the workers and drop the pool without waiting on them (a worker that does not return must not hold the caller, #535)."""
        executor, self._executor = self._executor, None
        if executor is None:
            return
        processes = list((executor._processes or {}).values())  # the executor keeps no public handle on its workers
        for process in processes:
            process.kill()
        executor.shutdown(wait=False, cancel_futures=True)
        for process in processes:
            process.join(5.0)

    def _start(self) -> ProcessPoolExecutor:
        if self._executor is None:
            methods = multiprocessing.get_all_start_methods()
            method = "fork" if "fork" in methods else "spawn"
            if method != "fork":
                copyreg.pickle(MappingProxyType, _pickle_mapping_proxy)
            self._executor = ProcessPoolExecutor(
                max_workers=self.workers,
                mp_context=multiprocessing.get_context(method),
                initializer=_initialise,
                initargs=(self._factory, self._args, method == "fork"),
            )
        return self._executor

    def map(self, function: Callable, pieces: Iterable, *, chunk: int | None = None, timeout: float | None = None) -> list:
        """`[function(p) for p in pieces]`, in that order, spread over the workers.

        `function` must be a module-level function (it is sent by name). `chunk` is how many pieces go to a worker
        at a time; the default cuts about eight chunks per worker. It changes the speed, never the result.

        `timeout` (seconds) bounds the wait on the workers: when a chunk has not come back by then the workers are killed
        (`abandon`) and `TimeoutError` is raised. A worker that dies raises `BrokenProcessPool` either way. Without
        workers (`workers` below 2) the pieces run here and `timeout` is not applied.
        """
        items = list(pieces)
        if self.workers < 2 or len(items) < 2:
            global _context
            if not self._have_local:
                self._local, self._have_local = self._factory(*self._args), True
            saved, _context = _context, self._local
            try:
                return [function(piece) for piece in items]
            finally:
                _context = saved
        size = chunk if chunk is not None else max(MIN_CHUNK, -(-len(items) // (self.workers * 8)))
        chunks = [items[start : start + size] for start in range(0, len(items), size)]
        executor = self._start()
        results: list = []
        if timeout is None:
            for part in executor.map(_run_chunk, [function] * len(chunks), chunks):
                results.extend(part)
            return results
        futures = [executor.submit(_run_chunk, function, part) for part in chunks]
        _, waiting = wait(futures, timeout=max(0.0, timeout))
        if waiting:
            self.abandon()
            raise TimeoutError(f"{len(waiting)} of {len(futures)} chunks did not come back in {timeout:.0f} s; their workers were stopped")
        for future in futures:
            results.extend(future.result())
        return results

    def map_chunks(self, function: Callable, pieces: Iterable, *, chunk: int) -> list:
        """`[function(c) for c in chunks]`, where the chunks are consecutive runs of `chunk` pieces (the last may be shorter).

        For a function that can share work, or compact what it sends back, across the pieces of a chunk. The results come
        back in chunk order; a caller whose answer must not depend on the chunking joins them in a way that does not.
        """
        items = list(pieces)
        chunks = [items[start : start + chunk] for start in range(0, len(items), chunk)]
        if self.workers < 2 or len(chunks) < 2:
            global _context
            if not self._have_local:
                self._local, self._have_local = self._factory(*self._args), True
            saved, _context = _context, self._local
            try:
                return [function(part) for part in chunks]
            finally:
                _context = saved
        executor = self._start()
        return list(executor.map(_run_whole, [function] * len(chunks), chunks))
