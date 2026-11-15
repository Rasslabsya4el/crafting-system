"""The store of the website: jobs and routes behind a small repository interface (`Store`), SQLite for the beta (`SqliteStore`).

A caller reads and writes records only through `Store`'s methods, so a server database can replace SQLite without touching the service or
the HTTP layer. A job is one request being answered; a route is a finished answer, kept for every later request with the same key (OR-36).
"""

import json
import sqlite3
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

QUEUED = "queued"
RUNNING = "running"
STANDING = "standing"  # a plan exists while the proof goes on (#906, OR-39)
DONE = "done"
FAILED = "failed"
STOPPED = "stopped"

ACTIVE = (QUEUED, RUNNING, STANDING)  # a job in one of these states still owes an answer
STATES = (*ACTIVE, DONE, FAILED, STOPPED)


@dataclass(frozen=True)
class JobRecord:
    """One request being answered. `standing` is the last word of the search (a JSON object, see `Service`), `route_id` the stored route
    of a job that is done, `error` the planner's own words of a job that failed."""

    id: str
    key: str
    request: dict
    state: str
    created_at: str
    updated_at: str
    from_store: bool = False
    standing: dict | None = None
    route_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class RouteRecord:
    """A finished answer: the request it answers, its figures as the planner states them (`summary`), the JSON policy and the route page
    (None for an answer the page cannot show yet)."""

    id: str
    key: str
    request: dict
    created_at: str
    summary: dict
    policy: dict
    page: str | None


class Store(Protocol):
    """What the service needs of a store. Every method is safe to call from several threads."""

    def add_job(self, job: JobRecord) -> None: ...

    def update_job(self, job_id: str, **fields: object) -> JobRecord: ...

    def job(self, job_id: str) -> JobRecord | None: ...

    def active_job(self, key: str) -> JobRecord | None:
        """The oldest job with this key that still owes an answer."""
        ...

    def jobs_in(self, states: Iterable[str]) -> list[JobRecord]:
        """Jobs in these states, oldest first."""
        ...

    def add_route(self, route: RouteRecord) -> None: ...

    def route(self, route_id: str) -> RouteRecord | None: ...

    def route_by_key(self, key: str) -> RouteRecord | None: ...

    def routes(self, limit: int, offset: int = 0) -> list[RouteRecord]:
        """Stored routes, newest first."""
        ...

    def close(self) -> None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    key TEXT NOT NULL,
    request TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    from_store INTEGER NOT NULL,
    standing TEXT,
    route_id TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS jobs_key ON jobs (key, state);
CREATE TABLE IF NOT EXISTS routes (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    key TEXT NOT NULL UNIQUE,
    request TEXT NOT NULL,
    created_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    policy TEXT NOT NULL,
    page TEXT
);
"""

_JOB_COLUMNS = "id, key, request, state, created_at, updated_at, from_store, standing, route_id, error"
_ROUTE_COLUMNS = "id, key, request, created_at, summary, policy, page"
_JSON_FIELDS = ("request", "standing")


def _dump(value: object) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def _load(text: str | None) -> object:
    return None if text is None else json.loads(text)


class SqliteStore:
    """`Store` in one SQLite file (or in memory with `":memory:"`). One connection behind a lock: the beta's load is a few writes a minute."""

    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def add_job(self, job: JobRecord) -> None:
        with self._lock:
            self._db.execute(
                f"INSERT INTO jobs ({_JOB_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job.id, job.key, _dump(job.request), job.state, job.created_at, job.updated_at, int(job.from_store), _dump(job.standing),
                 job.route_id, job.error),
            )  # fmt: skip

    def update_job(self, job_id: str, **fields: object) -> JobRecord:
        unknown = set(fields) - set(JobRecord.__dataclass_fields__) - {"id"}
        if unknown or "id" in fields:
            raise ValueError(f"a job has no field to change named {sorted(unknown or {'id'})}")
        with self._lock:
            assignments = ", ".join(f"{name} = ?" for name in fields)
            values = [_dump(value) if name in _JSON_FIELDS else int(value) if name == "from_store" else value for name, value in fields.items()]  # type: ignore[arg-type]
            self._db.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", (*values, job_id))
            found = self._job(job_id)
        if found is None:
            raise KeyError(job_id)
        return found

    def job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._job(job_id)

    def _job(self, job_id: str) -> JobRecord | None:
        row = self._db.execute(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return None if row is None else _job_of(row)

    def active_job(self, key: str) -> JobRecord | None:
        marks = ", ".join("?" for _ in ACTIVE)
        with self._lock:
            row = self._db.execute(
                f"SELECT {_JOB_COLUMNS} FROM jobs WHERE key = ? AND state IN ({marks}) ORDER BY seq LIMIT 1", (key, *ACTIVE)
            ).fetchone()
        return None if row is None else _job_of(row)

    def jobs_in(self, states: Iterable[str]) -> list[JobRecord]:
        wanted = tuple(states)
        marks = ", ".join("?" for _ in wanted)
        with self._lock:
            rows = self._db.execute(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE state IN ({marks}) ORDER BY seq", wanted).fetchall()
        return [_job_of(row) for row in rows]

    def add_route(self, route: RouteRecord) -> None:
        with self._lock:
            self._db.execute(
                f"INSERT INTO routes ({_ROUTE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (route.id, route.key, _dump(route.request), route.created_at, _dump(route.summary), _dump(route.policy), route.page),
            )

    def route(self, route_id: str) -> RouteRecord | None:
        return self._one_route("id", route_id)

    def route_by_key(self, key: str) -> RouteRecord | None:
        return self._one_route("key", key)

    def _one_route(self, column: str, value: str) -> RouteRecord | None:
        with self._lock:
            row = self._db.execute(f"SELECT {_ROUTE_COLUMNS} FROM routes WHERE {column} = ?", (value,)).fetchone()
        return None if row is None else _route_of(row)

    def routes(self, limit: int, offset: int = 0) -> list[RouteRecord]:
        with self._lock:
            rows = self._db.execute(f"SELECT {_ROUTE_COLUMNS} FROM routes ORDER BY seq DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [_route_of(row) for row in rows]


def _job_of(row: tuple) -> JobRecord:
    job_id, key, request, state, created, updated, from_store, standing, route_id, error = row
    return JobRecord(job_id, key, _load(request), state, created, updated, bool(from_store), _load(standing), route_id, error)  # type: ignore[arg-type]


def _route_of(row: tuple) -> RouteRecord:
    route_id, key, request, created, summary, policy, page = row
    return RouteRecord(route_id, key, _load(request), created, _load(summary), _load(policy), page)  # type: ignore[arg-type]


__all__ = ["ACTIVE", "DONE", "FAILED", "QUEUED", "RUNNING", "STANDING", "STATES", "STOPPED", "JobRecord", "RouteRecord", "SqliteStore", "Store"]
