"""The HTTP API: JSON in and out, versioned and carrying the game (`/api/v1/<game>/...`), one `Service` per game (OR-50).

    POST /api/v1/<game>/jobs                 a request (`_request`) -> 202 and the queued or open job, or 200 and a job done from the store
    GET  /api/v1/<game>/jobs/<id>            the job; `?wait=SECONDS` holds the answer until the job no longer owes one (or, with
                                             `&seen=<state>`, until its state is not that one), at most a minute
    POST /api/v1/<game>/jobs/<id>/stop       stop the job
    GET  /api/v1/<game>/routes               stored routes, newest first (`?limit=` up to 100, `&offset=`)
    GET  /api/v1/<game>/routes/<id>          one route: its request and figures
    GET  /api/v1/<game>/routes/<id>/policy   its JSON policy, as the command writes it
    GET  /api/v1/<game>/routes/<id>/page     its route page (HTML), as the command writes it
    GET  /api/v1/<game>                      what the service plans with: the game data version, the price snapshot, the workers

Every job, every route and the game's own document carry `price_age`: how old the price snapshot behind it is on the server's day, with a
warning past the limit the command warns at (`snapshot_age`, #976). A job's is its route's once it has one, else the snapshot it is planned
with while it owes an answer, else null; a route stored before routes named their snapshot has null.

An error is `{"error": "<what is wrong>"}` with 400 (a request that cannot be planned as written) or 404 (no such job, route, page or game).
"""

import contextlib
import math

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from ._request import RequestError
from ._service import WAIT_LIMIT_SECONDS, Service
from ._store import DONE, STATES, JobRecord, RouteRecord
from ._world import snapshot_age

API = "/api/v1"
ROUTES_PAGE_LIMIT = 100
MAX_BODY_BYTES = 1_000_000  # a target is a few kB; a larger body is refused before it is read whole


def _error(status: int, text: str) -> JSONResponse:
    return JSONResponse({"error": text}, status_code=status)


def job_document(job: JobRecord, game: str, price_age: dict | None = None) -> dict:
    return {
        "id": job.id,
        "state": job.state,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "from_store": job.from_store,
        "request": job.request,
        "standing": job.standing,
        "route": None if job.route_id is None else {"id": job.route_id, "url": f"{API}/{game}/routes/{job.route_id}"},
        "error": job.error,
        "key": job.key,
        "price_age": price_age,
    }


def route_document(route: RouteRecord, game: str, price_age: dict | None = None) -> dict:
    base = f"{API}/{game}/routes/{route.id}"
    return {
        "id": route.id,
        "created_at": route.created_at,
        "request": route.request,
        "summary": route.summary,
        "key": route.key,
        "policy_url": f"{base}/policy",
        "page_url": None if route.page is None else f"{base}/page",
        "price_age": price_age,
    }


def _whole(text: str | None, default: int, low: int, high: int, name: str) -> int:
    if text is None:
        return default
    try:
        value = int(text)
    except ValueError:
        raise RequestError(f"{name} must be a whole number") from None
    if not low <= value <= high:
        raise RequestError(f"{name} must be from {low} to {high}")
    return value


def create_app(services: dict[str, Service], *, manage: bool = True) -> Starlette:
    """The HTTP app over `services`, one per game (`{"poe1": Service(...)}`). With `manage` the app starts and closes them with itself."""

    def service_of(request: Request) -> Service | None:
        return services.get(request.path_params["game"])

    async def job_response(service: Service, job: JobRecord, status: int = 200) -> JSONResponse:
        # in a thread: the snapshot's age may load a refreshed world (`Service.world`), which never runs on the event loop
        price_age = await run_in_threadpool(service.job_price_age, job)
        return JSONResponse(job_document(job, service.game, price_age), status_code=status)

    def route_json(service: Service, route: RouteRecord) -> dict:
        return route_document(route, service.game, service.route_price_age(route))

    async def info(request: Request) -> JSONResponse:
        service = service_of(request)
        if service is None:
            return _error(404, f"no game {request.path_params['game']!r}; the site plans {sorted(services)}")
        world = await run_in_threadpool(lambda: service.world)  # may load a refreshed world (#968): never on the event loop
        price_age = snapshot_age(world.prices.league, world.prices.fetched_at, service.today())  # of the very world shown
        return JSONResponse(
            {"game": service.game, "data_version": world.data.version, "price_snapshot": world.price_snapshot, "planner": world.planner_version,
             "workers": service.workers, "machine": world.machine, "price_age": price_age}
        )  # fmt: skip

    async def submit(request: Request) -> JSONResponse:
        service = service_of(request)
        if service is None:
            return _error(404, f"no game {request.path_params['game']!r}; the site plans {sorted(services)}")
        try:
            body = await request.json()
        except (ValueError, RecursionError):
            return _error(400, "the request body must be JSON, nested at most a few hundred deep")
        try:
            job = await run_in_threadpool(service.submit, body)
        except RequestError as problem:
            return _error(400, str(problem))
        except RecursionError:
            return _error(400, "the request is nested too deep to be a target")
        return await job_response(service, job, 200 if job.state == DONE else 202)

    async def job(request: Request) -> JSONResponse:
        service = service_of(request)
        if service is None:
            return _error(404, f"no game {request.path_params['game']!r}")
        job_id = request.path_params["job_id"]
        wait = request.query_params.get("wait")
        seen = request.query_params.get("seen")
        if seen is not None and seen not in STATES:
            return _error(400, f"seen must be one of {list(STATES)}")
        if wait is not None:
            try:
                seconds = float(wait)
            except ValueError:
                seconds = math.nan
            if not (seconds >= 0 and math.isfinite(seconds)):
                return _error(400, f"wait is a number of seconds from 0 to {WAIT_LIMIT_SECONDS:g}")
            found = await run_in_threadpool(service.wait, job_id, seconds, seen)
        else:
            found = service.job(job_id)
        if found is None:
            return _error(404, f"no job {job_id!r}")
        return await job_response(service, found)

    async def stop(request: Request) -> JSONResponse:
        service = service_of(request)
        if service is None:
            return _error(404, f"no game {request.path_params['game']!r}")
        found = await run_in_threadpool(service.stop, request.path_params["job_id"])
        if found is None:
            return _error(404, f"no job {request.path_params['job_id']!r}")
        return await job_response(service, found)

    async def routes(request: Request) -> JSONResponse:
        service = service_of(request)
        if service is None:
            return _error(404, f"no game {request.path_params['game']!r}")
        try:
            limit = _whole(request.query_params.get("limit"), 20, 1, ROUTES_PAGE_LIMIT, "limit")
            offset = _whole(request.query_params.get("offset"), 0, 0, 10**9, "offset")
        except RequestError as problem:
            return _error(400, str(problem))
        found = service.store.routes(limit, offset)
        return JSONResponse({"routes": [route_json(service, route) for route in found], "limit": limit, "offset": offset})

    def one_route(request: Request) -> tuple[Service | None, RouteRecord | None]:
        service = service_of(request)
        return service, None if service is None else service.store.route(request.path_params["route_id"])

    async def route(request: Request) -> JSONResponse:
        service, found = one_route(request)
        if service is None or found is None:
            return _error(404, f"no route {request.path_params['route_id']!r}")
        return JSONResponse(route_json(service, found))

    async def policy(request: Request) -> JSONResponse:
        service, found = one_route(request)
        if service is None or found is None:
            return _error(404, f"no route {request.path_params['route_id']!r}")
        return JSONResponse(found.policy)

    async def page(request: Request) -> HTMLResponse | JSONResponse:
        service, found = one_route(request)
        if service is None or found is None:
            return _error(404, f"no route {request.path_params['route_id']!r}")
        if found.page is None:
            return _error(404, "this answer is approximate, and the route page is not built for an approximate answer yet")
        return HTMLResponse(found.page)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        if manage:
            for service in services.values():
                await run_in_threadpool(service.start)
        try:
            yield
        finally:
            if manage:
                for service in services.values():
                    await run_in_threadpool(service.close)

    base = API + "/{game}"
    return Starlette(
        routes=[
            Route(base, info, methods=["GET"]),
            Route(base + "/jobs", submit, methods=["POST"]),
            Route(base + "/jobs/{job_id}", job, methods=["GET"]),
            Route(base + "/jobs/{job_id}/stop", stop, methods=["POST"]),
            Route(base + "/routes", routes, methods=["GET"]),
            Route(base + "/routes/{route_id}", route, methods=["GET"]),
            Route(base + "/routes/{route_id}/policy", policy, methods=["GET"]),
            Route(base + "/routes/{route_id}/page", page, methods=["GET"]),
        ],
        lifespan=lifespan,
        max_body_size=MAX_BODY_BYTES,
    )


__all__ = ["create_app", "job_document", "route_document"]
