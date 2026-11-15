"""Shared helpers for the website tests (#961): the fixture world, works that stand still, a fixed clock and a client on a fresh store.

The world sources and works here are module-level so a worker process (spawned, on every system) can import them by name.
"""

import contextlib
import datetime
import threading
from pathlib import Path

import yaml
from cli_support import R12, price_file
from starlette.testclient import TestClient
from targets_support import DATA

from crafting_system.budget import Budget
from crafting_system.config import load_config
from crafting_system.planner import Standing
from crafting_system.web import STANDING, Service, SqliteStore, World, create_app, standing_document

API = "/api/v1/poe1"
MOMENT = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.UTC)  # the fixture price file is of 2026-10-30


class FixtureWorld(World):
    """The fixture world with no time or memory net: these tests check the service, and the nets are `tests/test_budget.py`'s."""

    @property
    def budget(self) -> Budget:  # type: ignore[override]
        return Budget(seconds=None, memory_mb=None)


def fixture_world() -> World:
    """The fixture game data and the R12 price file in memory, with the settings file's defaults (as `cli_support.run`)."""
    return FixtureWorld(DATA, price_file(), load_config({}))


def r12_target(**changes: object) -> dict:
    """R12's target as the JSON object a page sends: the YAML file read, without the price file the site does not take."""
    target = yaml.safe_load(R12.read_text(encoding="utf-8"))
    target.pop("price_file", None)
    target.update(changes)
    return target


def stand_still(world, request, game, today, watch) -> dict:
    """A work that says where it stands once and then waits until its process is killed."""
    watch(standing_document(Standing(lower=90.0, upper=100.0, rounds=3, seconds=1.5)))
    threading.Event().wait()
    raise AssertionError("unreachable")


def fixed_clock() -> datetime.datetime:
    return MOMENT


@contextlib.contextmanager
def client(db: Path | str = ":memory:", *, workers: int = 2, work=None):
    """A test client of the app over one service of the fixture world, started and closed with it."""
    kwargs = {} if work is None else {"work": work}
    service = Service(SqliteStore(db), fixture_world, workers=workers, clock=fixed_clock, **kwargs)
    with TestClient(create_app({"poe1": service})) as http:
        yield http, service


def wait_until_done(http: TestClient, job_id: str) -> dict:
    """Poll the job with the API's own wait until it no longer owes an answer."""
    for _ in range(20):
        job = http.get(f"{API}/jobs/{job_id}", params={"wait": 60}).json()
        if job["state"] not in ("queued", "running", STANDING):
            return job
    raise AssertionError(f"job {job_id} owes an answer after 20 minutes: {job}")


def wait_until(http: TestClient, job_id: str, state: str) -> dict:
    """Poll the job until it is in `state` (or past it)."""
    job = http.get(f"{API}/jobs/{job_id}").json()
    for _ in range(20):
        if job["state"] == state:
            return job
        job = http.get(f"{API}/jobs/{job_id}", params={"wait": 60, "seen": job["state"]}).json()
    raise AssertionError(f"job {job_id} never reached {state}: {job}")
