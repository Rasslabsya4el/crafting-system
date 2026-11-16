"""The service of one game: requests become jobs, jobs run in worker processes, finished routes go to the store and answer later requests.

**A run is a job.** `submit` checks a request and answers at once: from the store when a route with the request's key is stored (a job that
is done when it is made, `from_store`), with the job already open when the same request is queued or running (two identical requests at once
plan once), or with a new queued job. A dispatcher thread starts a worker process for each queued job, at most `workers` at a time (a
setting of the machine, OR-40); a plan takes seconds to minutes, so it never runs in the server's own process. The worker sends where the
search stands while the proof goes on (the job is then `standing`, #906, OR-39) and then the route or the planner's own words of a refusal.
A user may stop a job: a queued one is never started, a running one's process is killed.

**Restarts.** The store keeps every job. A service started on a store that holds jobs still owing an answer (the server stopped while they
were queued or running) queues them again, oldest first.

**Time.** The service reads the time only through `clock` (when a job was made and changed, and the day a snapshot's age is counted to),
so a test gives its own. A plan judges its prices on the day of its snapshot (`World.price_day`), never on the calendar; the API says how
old that snapshot is on the clock's day (`price_age`, #976).

**A price refresh** (#968). Each request is checked and keyed on the world as it stands: when a file the world was read from has changed
(`World.outdated`, a price file replaced by the scheduled refresh of OR-9), the service loads a new world first, so new requests are keyed on
the new snapshot without a restart. A new world that cannot be loaded (a broken file) leaves the old one in use, and is not tried again
until the files change once more; the fault goes to the log.

**Faults of the store.** A store that fails never leaves a job running for ever nor a thread dead: a job whose end cannot be stored is
failed with the error (when even that write fails, the job stays as it was until a restart queues it again), its place is freed in any
case, and the dispatcher outlives a failed read and tries again.
"""

import contextlib
import logging
import multiprocessing
import os
import secrets
import signal
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from multiprocessing.connection import wait

from ._request import Request, parse_request
from ._store import ACTIVE, DONE, FAILED, QUEUED, RUNNING, STANDING, STOPPED, JobRecord, RouteRecord, Store
from ._work import Work, plan_request, run_job
from ._world import SNAPSHOT_TIME_FORMAT, Stamp, World, WorldSource, snapshot_age, stamp_of

Clock = Callable[[], datetime]

STOPPED_WORDS = "stopped by the user"
VANISHED_WORDS = "the worker process ended without an answer (exit code {code})"
WAIT_LIMIT_SECONDS = 60.0  # the longest a `wait` holds a request open; a caller asks again
RETRY_SECONDS = 1.0  # how long the dispatcher waits after a fault of the store before it reads the queue again

_log = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _new_id() -> str:
    return secrets.token_hex(8)


class Service:
    """Jobs and routes of one game (see the module text). `start` loads the world and begins taking jobs; `close` stops every worker."""

    def __init__(
        self,
        store: Store,
        world_source: WorldSource,
        *,
        game: str = "poe1",
        workers: int = 1,
        clock: Clock = _utc_now,
        work: Work = plan_request,
    ) -> None:
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
            raise ValueError(f"a service runs at least one worker, not {workers!r}")
        self.store = store
        self.game = game
        self.workers = workers
        self._world_source = world_source
        self._work = work
        self._clock = clock
        self._world: World | None = None
        self._reload = threading.Lock()  # one reload of the world at a time
        self._refused: Stamp | None = None  # the files as they stood when a new world could not be loaded from them
        self._changed = threading.Condition()  # held for every change of a job's state; waiters are woken by it
        self._running: dict[str, _Running] = {}
        self._closing = False
        self._dispatcher: threading.Thread | None = None
        self._context = multiprocessing.get_context("spawn")  # the same on Linux and Windows; a worker inherits no thread or lock
        self.started = 0  # worker processes started since `start`: a plan run each

    # --- life ---------------------------------------------------------------------------------------------------------------------

    @property
    def world(self) -> World:
        """The world requests are checked and keyed with: loaded again first when a file it was read from has changed (#968)."""
        world = self._world
        if world is None:
            raise RuntimeError("the service is not started")
        if not world.outdated():
            return world
        with self._reload:
            world = self._world
            stamp = stamp_of(world.sources)
            if stamp == world.stamp or stamp == self._refused:  # loaded by another request meanwhile, or known to fail
                return world
            try:
                self._world = self._world_source()
            except Exception:  # noqa: BLE001  (a broken refresh never takes the site down: the old snapshot stays in use)
                _log.exception("the world of %s could not be loaded again after its files changed; the old one stays in use", self.game)
                self._refused = stamp
            return self._world

    def start(self) -> None:
        self._world = self._world_source()
        with self._changed:
            for job in self.store.jobs_in((RUNNING, STANDING)):  # a server stopped under them: they are planned again, in their order
                self.store.update_job(job.id, state=QUEUED, standing=None, updated_at=self._now())
        self._dispatcher = threading.Thread(target=self._dispatch, name=f"{self.game}-dispatcher", daemon=True)
        self._dispatcher.start()

    def close(self) -> None:
        with self._changed:
            self._closing = True
            running = list(self._running.values())
            self._changed.notify_all()
        for run in running:
            run.stopping = True
            _kill(run.process)
        if self._dispatcher is not None:
            self._dispatcher.join()
        for run in running:  # each listener puts its job's end into the store before the store may be closed
            if run.listener is not None:
                run.listener.join()

    def _now(self) -> str:
        return _stamp(self._clock())

    # --- the age of a price snapshot (#976) ---------------------------------------------------------------------------------------

    def today(self) -> date:
        """The day a snapshot's age is counted to: the clock's, in UTC."""
        return self._clock().astimezone(UTC).date()

    def price_age(self) -> dict:
        """How old the snapshot new requests are keyed and planned with is today (`snapshot_age`)."""
        prices = self.world.prices
        return snapshot_age(prices.league, prices.fetched_at, self.today())

    def route_price_age(self, route: RouteRecord) -> dict | None:
        """How old the snapshot a route was planned on is today, or None for a route stored before routes named it."""
        snapshot = route.summary.get("snapshot") if isinstance(route.summary, dict) else None
        if not isinstance(snapshot, dict):
            return None
        fetched_at = datetime.strptime(snapshot["fetched_at"], SNAPSHOT_TIME_FORMAT).replace(tzinfo=UTC)
        return snapshot_age(snapshot["league"], fetched_at, self.today())

    def job_price_age(self, job: JobRecord) -> dict | None:
        """How old a job's snapshot is today: its route's, once it has one; the snapshot it is keyed and planned with while it owes an
        answer; None for a job that ended with no route (failed or stopped)."""
        if job.route_id is not None:
            route = self.store.route(job.route_id)
            return None if route is None else self.route_price_age(route)
        return self.price_age() if job.state in ACTIVE else None

    # --- requests -----------------------------------------------------------------------------------------------------------------

    def check(self, body: object) -> Request:
        """The request checked and keyed; raises `RequestError` with what is wrong."""
        return parse_request(body, self.game, self.world)

    def submit(self, body: object) -> JobRecord:
        """The job that answers `body`: done at once from the store, the open job of the same request, or a new queued one."""
        request = self.check(body)
        with self._changed:
            now = self._now()
            stored = self.store.route_by_key(request.key)
            if stored is not None:
                job = JobRecord(_new_id(), request.key, request.document, DONE, now, now, from_store=True, route_id=stored.id)
                self.store.add_job(job)
                return job
            open_job = self.store.active_job(request.key)
            if open_job is not None:
                return open_job
            job = JobRecord(_new_id(), request.key, request.document, QUEUED, now, now)
            self.store.add_job(job)
            self._changed.notify_all()
            return job

    def job(self, job_id: str) -> JobRecord | None:
        return self.store.job(job_id)

    def wait(self, job_id: str, seconds: float, seen: str | None = None) -> JobRecord | None:
        """The job once its state is not `seen` (or, with no `seen`, once it no longer owes an answer), or as it is after `seconds`."""
        seconds = max(0.0, min(seconds, WAIT_LIMIT_SECONDS))

        def moved() -> bool:
            job = self.store.job(job_id)
            return job is None or (job.state != seen if seen is not None else job.state not in ACTIVE)

        with self._changed:
            self._changed.wait_for(moved, timeout=seconds)
        return self.store.job(job_id)

    def stop(self, job_id: str) -> JobRecord | None:
        """Stop a job that still owes an answer; a job that has ended is given back as it is."""
        with self._changed:
            job = self.store.job(job_id)
            if job is None or job.state not in ACTIVE:
                return job
            run = self._running.get(job_id)
            job = self.store.update_job(job_id, state=STOPPED, error=STOPPED_WORDS, updated_at=self._now())
            self._changed.notify_all()
        if run is not None:
            run.stopping = True
            _kill(run.process)
        return job

    # --- workers ------------------------------------------------------------------------------------------------------------------

    def _dispatch(self) -> None:
        while True:
            try:
                if self._dispatch_one():
                    return
            except Exception:  # a fault of the store: the dispatcher waits a little and reads the queue again, it never dies of it
                _log.exception("the dispatcher of %s could not read or change the queue", self.game)
                with self._changed:
                    if self._closing:
                        return
                    self._changed.wait(RETRY_SECONDS)

    def _dispatch_one(self) -> bool:
        """Start the next queued job once a place is free; True when the service is closing."""
        with self._changed:
            self._changed.wait_for(lambda: self._closing or (len(self._running) < self.workers and self._next() is not None))
            if self._closing:
                return True
            job = self._next()
            if job is None:
                return False
            try:
                run = self._start_worker(job)
            except Exception as error:  # noqa: BLE001  (a worker that cannot start fails its job, never the dispatcher)
                if not self._fail(job.id, f"internal error: the worker did not start: {type(error).__name__}: {error}"):
                    raise  # the job is still queued: the dispatcher waits before it tries again, never spawns in a loop
                return False
            self._running[job.id] = run
            try:
                run.listener.start()  # under the lock, so `close` never finds a run whose listener has not started
            except Exception as error:  # noqa: BLE001  (no thread to read the worker: it is ended and its job failed)
                del self._running[job.id]
                _end(run)
                if not self._fail(job.id, f"internal error: the worker could not be listened to: {type(error).__name__}: {error}"):
                    raise
                return False
            self.started += 1
            self._changed.notify_all()
        return False

    def _start_worker(self, job: JobRecord) -> "_Running":
        reader, writer = self._context.Pipe(duplex=False)
        # not a daemon: a daemonic process may not start children, and the planner's own pool does (`parallel.WorkerPool`)
        process = self._context.Process(
            target=_worker_main, args=(self._world_source, self._work, job.request, self.game, writer), name=f"{self.game}-job-{job.id}"
        )
        try:
            process.start()
        except BaseException:
            reader.close()
            raise
        finally:
            writer.close()  # the worker holds the only writing end
        run = _Running(process, reader)
        try:
            self.store.update_job(job.id, state=RUNNING, updated_at=self._now())
        except BaseException:  # no listener will ever read this worker: it is ended here, and the caller fails the job
            _end(run)
            raise
        run.listener = threading.Thread(target=self._listen, args=(job.id, run), name=f"{self.game}-listen-{job.id}", daemon=True)
        return run

    def _fail(self, job_id: str, error: str) -> bool:
        """Fail a job with `error` and wake the waiters; False when the store cannot take even that: the job is left as it is (a restart
        queues it again), and the fault goes to the log."""
        try:
            self.store.update_job(job_id, state=FAILED, error=error, updated_at=self._now())
            return True
        except Exception:
            _log.exception("job %s of %s could not be failed with: %s", job_id, self.game, error)
            return False
        finally:
            self._changed.notify_all()

    def _next(self) -> JobRecord | None:
        waiting = [job for job in self.store.jobs_in((QUEUED,)) if job.id not in self._running]
        return waiting[0] if waiting else None

    def _listen(self, job_id: str, run: "_Running") -> None:
        """Read one worker's words until it has ended, then put its last word into the store and free its place, whatever happens."""
        last: tuple | None = None
        try:
            for message in _messages(run):
                if message[0] == "standing":
                    with self._changed:
                        job = self.store.job(job_id)
                        if job is not None and job.state in (RUNNING, STANDING):
                            self.store.update_job(job_id, state=STANDING, standing=message[1], updated_at=self._now())
                            self._changed.notify_all()
                else:
                    last = message
        except Exception as error:  # noqa: BLE001  (an unreadable word fails the job; the place is freed below)
            last = ("failed", f"internal error: the worker's answer could not be read: {type(error).__name__}: {error}")
            _kill(run.process)
        finally:
            run.process.join()
            run.reader.close()  # type: ignore[attr-defined]
            with self._changed:
                try:
                    self._finish(job_id, run, last)
                except Exception as error:  # noqa: BLE001  (the end could not be stored: the job is failed with it, never left running)
                    self._fail(job_id, f"internal error: the job's end could not be stored: {type(error).__name__}: {error}")
                finally:
                    del self._running[job_id]
                    self._changed.notify_all()

    def _finish(self, job_id: str, run: "_Running", last: tuple | None) -> None:
        job = self.store.job(job_id)
        if job is None or job.state not in (RUNNING, STANDING) or run.stopping:
            return  # stopped by the user, or the service is closing: the job keeps the state that says so
        now = self._now()
        if last is not None and last[0] == "done":
            route, key = last[1], last[2]  # the key of what the worker planned with: a price file refreshed since the job was keyed counts
            stored = self.store.route_by_key(key)
            if stored is None:
                stored = RouteRecord(_new_id(), key, job.request, now, route["summary"], route["policy"], route["page"])
                self.store.add_route(stored)
            self.store.update_job(job_id, state=DONE, route_id=stored.id, updated_at=now)
        elif last is not None and last[0] == "failed":
            self.store.update_job(job_id, state=FAILED, error=last[1], updated_at=now)
        else:
            self.store.update_job(job_id, state=FAILED, error=VANISHED_WORDS.format(code=run.process.exitcode), updated_at=now)


class _Running:
    """A job's worker process, the end of the pipe it talks through, and the thread that listens to it."""

    def __init__(self, process: multiprocessing.process.BaseProcess, reader: object) -> None:
        self.process = process
        self.reader = reader
        self.stopping = False
        self.listener: threading.Thread | None = None


def _messages(run: _Running) -> Iterator[tuple]:
    """The worker's words in order, until its pipe ends or the worker has ended and nothing is left to read (on Linux a pool process that
    outlived it may still hold the pipe open, so the end of the worker counts, not only the end of the pipe)."""
    reader = run.reader
    while True:
        ready = wait([reader, run.process.sentinel])  # type: ignore[list-item]
        if reader not in ready:  # the worker has ended: what it sent before is still in the pipe
            while reader.poll():  # type: ignore[attr-defined]
                try:
                    yield reader.recv()  # type: ignore[attr-defined]
                except (EOFError, OSError):
                    return
            return
        try:
            yield reader.recv()  # type: ignore[attr-defined]
        except (EOFError, OSError):
            return


def _end(run: _Running) -> None:
    """End a worker that no listener reads: kill it, reap it and close its pipe."""
    _kill(run.process)
    run.process.join()
    run.reader.close()  # type: ignore[attr-defined]


def _kill(process: multiprocessing.process.BaseProcess) -> None:
    """Kill a worker and, on Linux and macOS, every process it started (it leads a process group of its own, `_worker_main`), so the
    planner's pool does not run on after a stop. On Windows only the worker is killed: its pool's processes may outlive it (#971)."""
    if os.name == "posix" and process.pid is not None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    process.kill()


def _worker_main(world_source: WorldSource, work: Work, request: dict, game: str, writer) -> None:
    """A worker process: one job, every word through `writer`."""
    if os.name == "posix":
        os.setsid()  # a session and process group of its own, so a stop kills the planner's pool with it (`_kill`)
    try:
        run_job(world_source, work, request, game, writer.send)
    finally:
        writer.close()
