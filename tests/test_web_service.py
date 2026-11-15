"""The website's service through HTTP on the fixture world (#961): submit, poll to done, the store answers the same request, a stopped job,
a failed job in the planner's own words, two identical requests at once plan once, and a restart that plans again what was cut off."""

import pytest
from targets_support import DATA
from web_support import (
    API,
    MOMENT,
    client,
    fixture_world,
    r12_target,
    stand_still,
    stuck_in_a_pool,
    wait_until,
    wait_until_done,
    with_a_pool,
    world_with_newer_prices_in_workers,
)

from crafting_system.web import QUEUED, RUNNING, STOPPED_WORDS, JobRecord, RequestError, Service, SqliteStore, parse_request

DAY = MOMENT.date()


def test_a_request_is_planned_as_a_job_and_its_route_is_stored_with_its_page():
    with client() as (http, service):
        posted = http.post(f"{API}/jobs", json={"target": r12_target()})
        assert posted.status_code == 202
        queued = posted.json()
        assert queued["state"] in ("queued", "running") and queued["from_store"] is False

        job = wait_until_done(http, queued["id"])

        assert job["state"] == "done" and job["error"] is None, job
        route = http.get(job["route"]["url"]).json()
        assert route["request"]["methods"] == {"recipe_starts": True, "strands": False}  # the machine's defaults, filled in
        assert route["summary"]["totals"]["mean_cost"]["value"] > 0
        assert route["summary"]["answer"] == {"approximate": False}
        page = http.get(route["page_url"])
        assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
        assert "<html" in page.text and "Paua Amulet" in page.text
        policy = http.get(route["policy_url"]).json()
        assert policy["totals"] == route["summary"]["totals"]
        listed = http.get(f"{API}/routes").json()["routes"]
        assert [entry["id"] for entry in listed] == [route["id"]]
        assert service.started == 1


def test_the_same_request_is_answered_from_the_store_without_a_plan_run():
    with client() as (http, service):
        first = wait_until_done(http, http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"])
        reordered = {"settings": {"price_source": "both"}, "target": dict(reversed(list(r12_target().items())))}  # same request, other spelling

        again = http.post(f"{API}/jobs", json=reordered)

        assert again.status_code == 200
        assert again.json()["state"] == "done" and again.json()["from_store"] is True
        assert again.json()["route"]["id"] == first["route"]["id"]
        assert service.started == 1  # no second plan run
        other = http.post(f"{API}/jobs", json={"target": r12_target(), "methods": {"recipe_starts": False}})
        assert other.status_code == 202  # another method switch is another request


def test_two_identical_requests_at_once_plan_once():
    with client(workers=2) as (http, service):
        first = http.post(f"{API}/jobs", json={"target": r12_target()}).json()
        second = http.post(f"{API}/jobs", json={"target": r12_target()}).json()

        assert second["id"] == first["id"]
        done = wait_until_done(http, first["id"])
        assert done["state"] == "done"
        assert service.started == 1
        assert len(http.get(f"{API}/routes").json()["routes"]) == 1


def test_a_failed_job_says_why_in_the_planners_own_words():
    given = r12_target(start="given")
    with client() as (http, service):
        job = wait_until_done(http, http.post(f"{API}/jobs", json={"target": given, "settings": {"start_price": 5.0}}).json()["id"])

    assert job["state"] == "failed" and job["route"] is None
    assert "given" in job["error"] and "internal error" not in job["error"]
    assert job["error"] == planner_words_for_a_priced_given_start()


def planner_words_for_a_priced_given_start() -> str:
    from cli_support import price_file

    from crafting_system.planner import PlanError, PlanSettings, plan_target

    world = fixture_world()
    request = parse_request({"target": r12_target(start="given"), "settings": {"start_price": 5.0}}, "poe1", world, DAY)
    with pytest.raises(PlanError) as refused:
        plan_target(DATA, request.target, price_file(), PlanSettings(start_price=5.0))
    return str(refused.value)


def test_a_job_shows_where_the_search_stands_and_the_user_can_stop_it():
    with client(work=stand_still) as (http, service):
        job_id = http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"]
        standing = wait_until(http, job_id, "standing")
        assert standing["standing"] == {"plan_cost_without_start": 100.0, "lower_bound_without_start": 90.0, "gap": pytest.approx(1 / 9), "rounds": 3, "seconds": 1.5}

        stopped = http.post(f"{API}/jobs/{job_id}/stop").json()

        assert stopped["state"] == "stopped" and stopped["error"] == STOPPED_WORDS
        assert wait_until_done(http, job_id)["state"] == "stopped"  # the worker's end does not overwrite it
        assert http.get(f"{API}/routes").json()["routes"] == []
        again = http.post(f"{API}/jobs", json={"target": r12_target()}).json()
        assert again["id"] != job_id and again["state"] in ("queued", "running")  # a stopped request is planned again when asked again
        http.post(f"{API}/jobs/{again['id']}/stop")


def test_a_queued_job_that_is_stopped_never_runs():
    with client(workers=1, work=stand_still) as (http, service):
        first = http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"]
        second = http.post(f"{API}/jobs", json={"target": r12_target(), "methods": {"strands": True}}).json()["id"]
        wait_until(http, first, "standing")
        assert http.get(f"{API}/jobs/{second}").json()["state"] == "queued"  # one worker, and it is taken

        assert http.post(f"{API}/jobs/{second}/stop").json()["state"] == "stopped"
        http.post(f"{API}/jobs/{first}/stop")

        assert service.started == 1


def test_a_job_cut_off_by_a_restart_is_planned_again(tmp_path):
    db = tmp_path / "site.sqlite3"
    request = parse_request({"target": r12_target()}, "poe1", fixture_world(), DAY)
    store = SqliteStore(db)
    store.add_job(JobRecord("cutoff", request.key, request.document, RUNNING, "2026-10-31T11:00:00Z", "2026-10-31T11:00:00Z"))
    store.close()

    with client(db) as (http, service):
        job = wait_until_done(http, "cutoff")

    assert job["state"] == "done" and service.started == 1


@pytest.mark.parametrize(
    ("body", "words"),
    [
        ({}, "the target as a JSON object"),
        ({"target": r12_target(), "economy": "hardcore"}, "unknown keys ['economy']"),
        ({"target": r12_target(), "methods": {"fossils": True}}, "unknown keys ['fossils']"),
        ({"target": r12_target(), "methods": {"strands": "yes"}}, "methods.strands must be true or false"),
        ({"target": r12_target(), "settings": {"start_price": -1}}, "settings.start_price"),
        ({"target": r12_target(), "settings": {"price_source": "guess"}}, "settings.price_source"),
        ({"target": r12_target(price_file="prices.json")}, "target.price_file"),
        ({"target": r12_target(base="No Such Amulet")}, "No Such Amulet"),
    ],
)
def test_a_request_that_cannot_be_planned_as_written_is_refused_at_once(body, words):
    with client() as (http, service):
        answer = http.post(f"{API}/jobs", json=body)

    assert answer.status_code == 400 and words in answer.json()["error"]
    assert service.started == 0


def test_a_body_nested_too_deep_is_refused_in_words():
    deep = "[" * 100_000 + "]" * 100_000
    with client() as (http, service):
        answer = http.post(f"{API}/jobs", content=deep, headers={"content-type": "application/json"})

    assert answer.status_code in (400, 413)


def test_unknown_jobs_routes_and_games_are_not_found():
    with client() as (http, service):
        assert http.get(f"{API}/jobs/nothing").status_code == 404
        assert http.post(f"{API}/jobs/nothing/stop").status_code == 404
        assert http.get(f"{API}/routes/nothing").status_code == 404
        assert http.get(f"{API}/routes/nothing/page").status_code == 404
        assert http.post("/api/v1/poe2/jobs", json={"target": r12_target()}).status_code == 404
        info = http.get(API).json()
        assert info["game"] == "poe1" and info["data_version"] == DATA.version and info["workers"] == 2


def test_the_key_is_the_request_not_its_spelling():
    world = fixture_world()
    plain = parse_request({"target": r12_target()}, "poe1", world, DAY)
    spelled = parse_request({"target": r12_target(), "methods": {"recipe_starts": True, "strands": False}, "settings": {"start_price": None}}, "poe1", world, DAY)
    priced = parse_request({"target": r12_target(), "settings": {"start_price": 6}}, "poe1", world, DAY)

    assert plain.key == spelled.key
    assert priced.key != plain.key
    assert parse_request({"target": r12_target()}, "poe2", world, DAY).key != plain.key
    assert parse_request({"target": r12_target()}, "poe1", world, DAY.replace(day=1)).key != plain.key  # the day judges a price's age
    with pytest.raises(RequestError):
        parse_request([], "poe1", world, DAY)


def test_the_store_lists_routes_newest_first_and_keeps_jobs_in_order(tmp_path):
    from crafting_system.web import RouteRecord

    store = SqliteStore(tmp_path / "s.sqlite3")
    for number in range(3):
        store.add_route(RouteRecord(f"r{number}", f"k{number}", {}, "2026-10-31T12:00:00Z", {}, {}, None))
        store.add_job(JobRecord(f"j{number}", "same", {}, QUEUED, "t", "t"))

    assert [route.id for route in store.routes(2)] == ["r2", "r1"]
    assert [route.id for route in store.routes(2, 2)] == ["r0"]
    assert store.route_by_key("k1").id == "r1"
    assert store.active_job("same").id == "j0"
    assert [job.id for job in store.jobs_in((QUEUED,))] == ["j0", "j1", "j2"]
    with pytest.raises(ValueError):
        store.update_job("j0", colour="red")


def test_a_plan_that_starts_the_planners_own_pool_runs_in_a_worker():
    """A worker is not a daemon process: the planner's pool (`parallel.WorkerPool`) starts processes of its own inside it."""
    with client(work=with_a_pool) as (http, service):
        job = wait_until_done(http, http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"])

        assert job["state"] == "done", job["error"]
        assert http.get(job["route"]["url"]).json()["summary"] == {"doubled": [2, 4, 6]}


def test_a_stopped_job_frees_its_worker_even_while_its_pool_runs():
    with client(workers=1, work=stuck_in_a_pool) as (http, service):
        first = http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"]
        wait_until(http, first, "standing")
        second = http.post(f"{API}/jobs", json={"target": r12_target(), "methods": {"strands": True}}).json()["id"]

        http.post(f"{API}/jobs/{first}/stop")

        assert wait_until(http, second, "standing")["state"] == "standing"  # the one worker's place was freed
        http.post(f"{API}/jobs/{second}/stop")
        assert service.started == 2


def test_a_route_is_stored_under_the_prices_it_was_planned_with():
    """A price file refreshed between the request and its run: the route is stored under the key of what the worker read, never under
    the older snapshot's key, so a request keyed on the older prices is not answered with it."""
    service = Service(SqliteStore(":memory:"), world_with_newer_prices_in_workers, workers=1, clock=lambda: MOMENT)
    from starlette.testclient import TestClient

    from crafting_system.web import create_app

    with TestClient(create_app({"poe1": service})) as http:
        posted = http.post(f"{API}/jobs", json={"target": r12_target()}).json()
        job = wait_until_done(http, posted["id"])
        route = http.get(job["route"]["url"]).json()

        assert job["state"] == "done" and route["key"] != posted["key"]
        assert http.post(f"{API}/jobs", json={"target": r12_target()}).status_code == 202  # not answered from the newer route
