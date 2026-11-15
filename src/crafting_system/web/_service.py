"""The service of one game: requests become jobs, jobs run in worker processes, finished routes go to the store and answer later requests.

**A run is a job.** `submit` checks a request and answers at once: from the store when a route with the request's key is stored (a job that
is done when it is made, `from_store`), with the job already open when the same request is queued or running (two identical requests at once
plan once), or with a new queued job. A dispatcher thread starts a worker process for each queued job, at most `workers` at a time (a
setting of the machine, OR-40); a plan takes seconds to minutes, so it never runs in the server's own process. The worker sends where the
search stands while the proof goes on (the job is then `standing`, #906, OR-39) and then the route or the planner's own words of a refusal.
A user may stop a job: a queued one is never started, a running one's process is killed.

**Restarts.** The store keeps every job. A service started on a store that holds jobs still owing an answer (the server stopped while they
were queued or running) queues them again, oldest first.

**Time.** The service reads the time only through `clock` (when a job was made and changed, and the day a plan judges its prices on), so a
test gives its own.
"""

import multiprocessing
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from ._request import Request, parse_request
from ._store import ACTIVE, DONE, FAILED, QUEUED, RUNNING, STANDING, STOPPED, JobRecord, RouteRecord, Store
from ._work import Work, plan_request, run_job
from ._world import World, WorldSource

Clock = Callable[[], datetime]

STOPPED_WORDS = "stopped by the user"
VANISHED_WORDS = "the worker process ended without an answer (exit code {code})"
WAIT_LIMIT_SECONDS = 60.0  # the longest a `wait` holds a request open; a caller asks again


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _new_id() -> str:
    return secrets.token_hex(8)


class _Running:
    """A job's worker process and the end of the pipe it talks through."""

    def __init__(self, process: multiprocessing.process.BaseProcess, reader: object) -> None:
        self.process = process
        self.reader = reader
        self.stopping = False


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
        self._changed = threading.Condition()  # held for every change of a job's state; waiters are woken by it
        self._running: dict[str, _Running] = {}
        self._closing = False
        self._dispatcher: threading.Thread | None = None
        self._context = multiprocessing.get_context("spawn")  # the same on Linux and Windows; a worker inherits no thread or lock
        self.started = 0  # worker processes started since `start`: a plan run each

    # --- life ---------------------------------------------------------------------------------------------------------------------

    @property
    def world(self) -> World:
        if self._world is None:
            raise RuntimeError("the service is not started")
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
            run.process.kill()
        for run in running:
            run.process.join()
        if self._dispatcher is not None:
            self._dispatcher.join()

    def _now(self) -> str:
        return _stamp(self._clock())

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
            run.process.kill()
        return job

    # --- workers ------------------------------------------------------------------------------------------------------------------

    def _dispatch(self) -> None:
        while True:
            with self._changed:
                self._changed.wait_for(lambda: self._closing or (len(self._running) < self.workers and self._next() is not None))
                if self._closing:
                    return
                job = self._next()
                assert job is not None
                job = self.store.update_job(job.id, state=RUNNING, updated_at=self._now())
                today = self._clock().date()
                reader, writer = self._context.Pipe(duplex=False)
                process = self._context.Process(
                    target=_worker_main, args=(self._world_source, self._work, job.request, self.game, today, writer),
                    name=f"{self.game}-job-{job.id}", daemon=True,
                )  # fmt: skip
                process.start()
                writer.close()  # the worker holds the only writing end, so its death ends the pipe
                self._running[job.id] = _Running(process, reader)
                self.started += 1
                self._changed.notify_all()
            threading.Thread(target=self._listen, args=(job.id,), name=f"{self.game}-listen-{job.id}", daemon=True).start()

    def _next(self) -> JobRecord | None:
        waiting = [job for job in self.store.jobs_in((QUEUED,)) if job.id not in self._running]
        return waiting[0] if waiting else None

    def _listen(self, job_id: str) -> None:
        """Read one worker's words until its pipe ends, then put its last word into the store."""
        run = self._running[job_id]
        last: tuple | None = None
        while True:
            try:
                message = run.reader.recv()  # type: ignore[attr-defined]
            except (EOFError, OSError):
                break
            if message[0] == "standing":
                with self._changed:
                    job = self.store.job(job_id)
                    if job is not None and job.state in (RUNNING, STANDING):
                        self.store.update_job(job_id, state=STANDING, standing=message[1], updated_at=self._now())
                        self._changed.notify_all()
            else:
                last = message
        run.process.join()
        run.reader.close()  # type: ignore[attr-defined]
        with self._changed:
            self._finish(job_id, run, last)
            del self._running[job_id]
            self._changed.notify_all()

    def _finish(self, job_id: str, run: _Running, last: tuple | None) -> None:
        job = self.store.job(job_id)
        if job is None or job.state not in (RUNNING, STANDING) or run.stopping:
            return  # stopped by the user, or the service is closing: the job keeps the state that says so
        now = self._now()
        if last is not None and last[0] == "done":
            route = last[1]
            stored = self.store.route_by_key(job.key)
            if stored is None:
                stored = RouteRecord(_new_id(), job.key, job.request, now, route["summary"], route["policy"], route["page"])
                self.store.add_route(stored)
            self.store.update_job(job_id, state=DONE, route_id=stored.id, updated_at=now)
        elif last is not None and last[0] == "failed":
            self.store.update_job(job_id, state=FAILED, error=last[1], updated_at=now)
        else:
            self.store.update_job(job_id, state=FAILED, error=VANISHED_WORDS.format(code=run.process.exitcode), updated_at=now)


def _worker_main(world_source: WorldSource, work: Work, request: dict, game: str, today, writer) -> None:
    """A worker process: one job, every word through `writer`."""
    try:
        run_job(world_source, work, request, game, today, writer.send)
    finally:
        writer.close()
