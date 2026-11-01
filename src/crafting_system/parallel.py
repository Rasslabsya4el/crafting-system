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
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
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


def context() -> object:
    """What the factory built in this worker process (read by the functions `WorkerPool.map` runs)."""
    return _context


def _initialise(factory: Callable[..., object], args: tuple) -> None:
    global _context
    _context = factory(*args)


def _run_chunk(function: Callable, chunk: Sequence) -> list:
    return [function(piece) for piece in chunk]


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
                initargs=(self._factory, self._args),
            )
        return self._executor

    def map(self, function: Callable, pieces: Iterable, *, chunk: int | None = None) -> list:
        """`[function(p) for p in pieces]`, in that order, spread over the workers.

        `function` must be a module-level function (it is sent by name). `chunk` is how many pieces go to a worker
        at a time; the default cuts about eight chunks per worker. It changes the speed, never the result.
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
        for part in executor.map(_run_chunk, [function] * len(chunks), chunks):
            results.extend(part)
        return results
