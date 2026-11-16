"""The website's service (#961, OR-35, OR-36): the planner behind an HTTP API. May import every module before it, `planner` and `cli` only
through their public names (ADR-0018, `tests/test_layering.py`).

It holds no planning code: a job calls the planner's one entry (`planner.plan_target`), and the figures, the JSON policy and the route page
are the command's own (`cli.build_report`, `cli.policy_document`, `cli.route_page`).

* `create_app(services)`: the Starlette app, one `Service` per game under `/api/v1/<game>/` (`_app` lists the API).
* `Service(store, world_source, workers=..., clock=...)`: requests become jobs run in worker processes; finished routes are stored and
  answer every later request with the same key (`_service`, `_request`).
* `Store`, `SqliteStore`: the repository interface and its SQLite form (`_store`).
* `World`, `load_world`: the game data, the price snapshot and the machine's planner settings a service plans with (`_world`).
* `python -m crafting_system.web`: the server (`__main__`; `docs/web.md`).
"""

from ._app import create_app, job_document, route_document
from ._request import Request, RequestError, parse_request, target_form
from ._service import STOPPED_WORDS, Service
from ._store import ACTIVE, DONE, FAILED, QUEUED, RUNNING, STANDING, STATES, STOPPED, JobRecord, RouteRecord, SqliteStore, Store
from ._work import plan_request, standing_document
from ._world import PLANNER_VERSION, World, WorldSource, load_world, snapshot_age, stamp_of

__all__ = [
    "ACTIVE",
    "DONE",
    "FAILED",
    "PLANNER_VERSION",
    "QUEUED",
    "RUNNING",
    "STANDING",
    "STATES",
    "STOPPED",
    "STOPPED_WORDS",
    "JobRecord",
    "Request",
    "RequestError",
    "RouteRecord",
    "Service",
    "SqliteStore",
    "Store",
    "World",
    "WorldSource",
    "create_app",
    "job_document",
    "load_world",
    "parse_request",
    "plan_request",
    "route_document",
    "snapshot_age",
    "stamp_of",
    "standing_document",
    "target_form",
]
