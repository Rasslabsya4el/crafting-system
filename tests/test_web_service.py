"""The website's service through HTTP on the fixture world (#961): submit, poll to done, the store answers the same request, a stopped job,
a failed job in the planner's own words, two identical requests at once plan once, and a restart that plans again what was cut off; two
spellings of one item share a key (#966), a refreshed price file keys new requests (#968), and the API says how old a snapshot is (#976)."""

import dataclasses
import datetime
import json
import multiprocessing
import os
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import price_file
from starlette.testclient import TestClient
from targets_support import DATA
from web_support import (
    API,
    FailingStore,
    MOMENT,
    PRICE_FILE_VARIABLE,
    at_once,
    client,
    fixed_clock,
    fixture_world,
    r12_target,
    stand_still,
    stuck_in_a_pool,
    wait_until,
    wait_until_done,
    with_a_pool,
    world_from_price_file,
    world_with_newer_prices_in_workers,
)

from crafting_system.prices import stale_warning, write_price_file
from crafting_system.targets import load_target
from crafting_system.prices.price_file import MAX_AGE_DAYS
from crafting_system.web import (
    ACTIVE,
    QUEUED,
    RUNNING,
    STOPPED_WORDS,
    JobRecord,
    RequestError,
    Service,
    SqliteStore,
    create_app,
    parse_request,
    snapshot_age,
    target_form,
)


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
    request = parse_request({"target": r12_target(start="given"), "settings": {"start_price": 5.0}}, "poe1", world)
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
    request = parse_request({"target": r12_target()}, "poe1", fixture_world())
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
    plain = parse_request({"target": r12_target()}, "poe1", world)
    spelled = parse_request({"target": r12_target(), "methods": {"recipe_starts": True, "strands": False}, "settings": {"start_price": None}}, "poe1", world)
    priced = parse_request({"target": r12_target(), "settings": {"start_price": 6}}, "poe1", world)

    assert plain.key == spelled.key
    assert priced.key != plain.key
    assert parse_request({"target": r12_target()}, "poe2", world).key != plain.key
    with pytest.raises(RequestError):
        parse_request([], "poe1", world)


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
        assert http.get(job["route"]["url"]).json()["summary"]["doubled"] == [2, 4, 6]


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


def test_a_route_is_reused_on_a_later_day_while_its_price_snapshot_stands(tmp_path):
    """The calendar day is not in the key: a plan judges prices on its snapshot's day (`World.price_day`), so the same request on the
    next day, with the same snapshot, is answered from the store (OR-36)."""
    db = tmp_path / "site.sqlite3"
    first = Service(SqliteStore(db), fixture_world, clock=lambda: MOMENT)
    first.start()
    try:
        job = first.submit({"target": r12_target()})
        assert first.wait(job.id, 60).state == "done"
    finally:
        first.close()
        first.store.close()

    later = Service(SqliteStore(db), fixture_world, clock=lambda: MOMENT + datetime.timedelta(days=3))
    later.start()
    try:
        again = later.submit({"target": r12_target()})
        assert again.state == "done" and again.from_store is True and later.started == 0
    finally:
        later.close()
        later.store.close()


def _service_on(store, work=at_once) -> Service:
    service = Service(store, fixture_world, workers=1, clock=lambda: MOMENT, work=work)
    service.start()
    return service


def _ends(service: Service, job_id: str) -> JobRecord:
    for _ in range(20):
        job = service.wait(job_id, 60)
        if job.state not in ACTIVE:
            return job
    raise AssertionError(f"job {job_id} owes an answer: {job}")


def _runs_after(service: Service) -> None:
    """The one worker's place is free and the dispatcher alive: another request runs to its end."""
    other = service.submit({"target": r12_target(), "methods": {"strands": True}})
    assert _ends(service, other.id).state == "done"


def test_a_job_whose_end_cannot_be_stored_fails_and_frees_its_place():
    store = FailingStore(SqliteStore(":memory:"), "add_route")
    service = _service_on(store)
    try:
        store.armed = True
        job = _ends(service, service.submit({"target": r12_target()}).id)

        assert job.state == "failed" and "could not be stored" in job.error and "the disk is gone (add_route)" in job.error
        _runs_after(service)
    finally:
        service.close()


def test_a_job_that_cannot_be_marked_running_fails_and_its_worker_is_ended():
    store = FailingStore(SqliteStore(":memory:"), "update_job", state=RUNNING)
    service = _service_on(store, work=stand_still)
    try:
        store.armed = True
        job = _ends(service, service.submit({"target": r12_target()}).id)

        assert job.state == "failed" and "did not start" in job.error
        assert not [child for child in multiprocessing.active_children() if child.name == f"poe1-job-{job.id}"]  # killed and reaped
        service._work = at_once  # noqa: SLF001  (the next worker answers at once)
        _runs_after(service)
    finally:
        service.close()


def test_the_dispatcher_outlives_a_store_that_fails_to_read_the_queue():
    store = FailingStore(SqliteStore(":memory:"), "jobs_in", times=2)
    service = _service_on(store)
    try:
        store.armed = True
        job = _ends(service, service.submit({"target": r12_target()}).id)

        assert job.state == "done" and store.times == 0
        assert service._dispatcher.is_alive()  # noqa: SLF001
    finally:
        service.close()


def test_a_job_the_store_can_neither_start_nor_fail_waits_queued_and_runs_later():
    store = FailingStore(SqliteStore(":memory:"), "update_job", times=2)  # marking it running fails, and so does failing it
    service = _service_on(store)
    try:
        store.armed = True
        job = _ends(service, service.submit({"target": r12_target()}).id)

        assert job.state == "done" and store.times == 0 and service.started == 1
    finally:
        service.close()


# --- the target's canonical form (#966) ------------------------------------------------------------------------------------------------


def test_two_spellings_of_one_item_share_a_key():
    """The key is built on the parsed target, not the JSON sent: an influence list left out, a stat text in place of its family id and
    the required entries in another order are one item, so one key; a looser tier is another item."""
    world = fixture_world()
    written = parse_request({"target": r12_target()}, "poe1", world)
    other = r12_target(requirements=[{"min_tier": "any", "stat": "+#% to Lightning Resistance"}, {"stat": "+1 to Level of all Lightning Skill Gems"}])
    del other["influence"]

    respelled = parse_request({"target": other}, "poe1", world)

    assert respelled.key == written.key
    assert respelled.document["target"] == other  # the store keeps what the user wrote; only the key is canonical
    assert target_form(respelled.target) == target_form(written.target)
    tier_two = r12_target(requirements=[{"stat": "+1 to Level of all Lightning Skill Gems"}, {"family": "LightningResistance", "min_tier": 2}])
    assert parse_request({"target": tier_two}, "poe1", world).key != written.key


def test_a_respelled_request_is_answered_from_the_store():
    with client(work=at_once) as (http, service):
        first = wait_until_done(http, http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"])
        other = r12_target(requirements=[{"stat": "+#% to Lightning Resistance", "min_tier": "any"}, {"stat": "+1 to Level of all Lightning Skill Gems"}])

        again = http.post(f"{API}/jobs", json={"target": other})

        assert again.status_code == 200 and again.json()["from_store"] is True
        assert again.json()["route"]["id"] == first["route"]["id"] and service.started == 1


# --- a refreshed price file (#968) -----------------------------------------------------------------------------------------------------


def _write_prices(path, prices, seconds: int) -> None:
    """Replace the price file in one step, as the refresh does, and give it its own write time (no clock is read)."""
    write_price_file(path, prices)
    os.utime(path, ns=(seconds * 10**9, seconds * 10**9))


def test_a_refreshed_price_file_keys_new_requests_without_a_restart(tmp_path, monkeypatch):
    path = tmp_path / "prices.json"
    _write_prices(path, price_file(), 1_000_000)
    monkeypatch.setenv(PRICE_FILE_VARIABLE, str(path))
    service = Service(SqliteStore(":memory:"), world_from_price_file, workers=1, clock=fixed_clock, work=at_once)
    with TestClient(create_app({"poe1": service})) as http:
        first = wait_until_done(http, http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"])
        old_snapshot = http.get(API).json()["price_snapshot"]

        newer = dataclasses.replace(price_file(start=4.5), fetched_at=datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC))
        _write_prices(path, newer, 2_000_000)
        refreshed = http.get(API).json()
        posted = http.post(f"{API}/jobs", json={"target": r12_target()})

        assert refreshed["price_snapshot"] != old_snapshot and refreshed["price_age"]["fetched_at"] == "2026-10-31T00:00:00Z"
        assert posted.status_code == 202 and posted.json()["key"] != first["key"]  # keyed on the new snapshot, so planned again
        second = wait_until_done(http, posted.json()["id"])
        assert http.get(second["route"]["url"]).json()["key"] == posted.json()["key"]  # the worker read the same new file

        path.write_text("{ half a file", encoding="utf-8")  # a broken refresh: the site keeps the snapshot it has
        os.utime(path, ns=(3_000_000 * 10**9, 3_000_000 * 10**9))
        assert http.get(API).json()["price_snapshot"] == refreshed["price_snapshot"]
        kept = http.post(f"{API}/jobs", json={"target": r12_target()})
        assert kept.status_code == 200 and kept.json()["from_store"] is True and service.started == 2


# --- the age of the price snapshot (#976) ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("days", "stale"), [(7, False), (8, True)])
def test_a_snapshot_is_stale_past_the_limit_the_command_warns_at(days, stale):
    fetched = datetime.datetime(2026, 10, 30, 23, 0, tzinfo=datetime.UTC)
    today = datetime.date(2026, 10, 30) + datetime.timedelta(days=days)

    age = snapshot_age("Test", fetched, today)

    assert age["age_days"] == days and age["max_age_days"] == MAX_AGE_DAYS and age["stale"] is stale
    assert (stale_warning(price_file(), today) is not None) is stale  # the command's own judgement on the same snapshot day
    assert (age["warning"] is not None) is stale
    if stale:
        assert f"{days} days old" in age["warning"] and "2026-10-30" in age["warning"]


def test_the_api_says_how_old_the_snapshot_behind_each_job_and_route_is(tmp_path):
    db = tmp_path / "site.sqlite3"
    with client(db, work=at_once) as (http, service):
        job = wait_until_done(http, http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"])
        route = http.get(job["route"]["url"]).json()
        assert http.get(API).json()["price_age"]["stale"] is False  # the fixture snapshot is of 2026-10-30, the clock says 10-31
        assert job["price_age"]["age_days"] == 1 and route["price_age"]["warning"] is None
        assert route["summary"]["snapshot"] == {"league": "Test", "fetched_at": "2026-10-30T00:00:00Z"}

    ten_days_later = Service(SqliteStore(db), fixture_world, clock=lambda: MOMENT + datetime.timedelta(days=10), work=at_once)
    with TestClient(create_app({"poe1": ten_days_later})) as http:
        info = http.get(API).json()
        again = http.post(f"{API}/jobs", json={"target": r12_target()}).json()  # the same snapshot: answered from the store
        listed = http.get(f"{API}/routes").json()["routes"][0]

        assert info["price_age"]["stale"] is True and info["price_age"]["age_days"] == 11
        assert again["from_store"] is True and again["price_age"]["stale"] is True and "11 days old" in again["price_age"]["warning"]
        assert listed["price_age"] == again["price_age"] == http.get(again["route"]["url"]).json()["price_age"]
        assert http.get(f"{API}/jobs/{job['id']}").json()["price_age"]["age_days"] == 11


# --- the league of the price snapshot against the game data's (#1026) -------------------------------------------------------------


def test_a_snapshot_of_another_league_than_the_game_data_is_said_in_the_sites_words():
    fetched = datetime.datetime(2026, 11, 16, 6, 0, tzinfo=datetime.UTC)
    today = datetime.date(2026, 11, 16)

    same = snapshot_age("Allflame", fetched, today, data_league="Allflame")
    other = snapshot_age("Covens", fetched, today, data_league="Allflame")
    unknown = snapshot_age("Covens", fetched, today)

    assert (same["data_league"], same["other_league"], same["league_warning"]) == ("Allflame", False, None)
    assert (unknown["data_league"], unknown["other_league"], unknown["league_warning"]) == (None, False, None)
    assert other["data_league"] == "Allflame" and other["other_league"] is True
    assert "Covens" in other["league_warning"] and "Allflame" in other["league_warning"]
    assert "python" not in other["league_warning"] and "crafting_system" not in other["league_warning"]  # OR-9: no command for a visitor
    assert other["warning"] is None  # a fresh snapshot: its age is not what is wrong


@pytest.mark.parametrize(("data_league", "other"), [("Allflame", True), ("Test", False)])
def test_the_info_document_every_job_and_every_route_say_when_the_prices_are_of_another_league(tmp_path, data_league, other):
    with client(tmp_path / "site.sqlite3", work=at_once, data_league=data_league) as (http, _service):
        info = http.get(API).json()
        job = wait_until_done(http, http.post(f"{API}/jobs", json={"target": r12_target()}).json()["id"])
        route = http.get(job["route"]["url"]).json()
        listed = http.get(f"{API}/routes").json()["routes"][0]

    for age in (info["price_age"], job["price_age"], route["price_age"], listed["price_age"]):
        assert age["league"] == "Test" and age["data_league"] == data_league and age["other_league"] is other
        assert (age["league_warning"] is not None) is other


def test_every_example_target_has_a_canonical_form_on_the_real_data():
    """Every field a target can hold (sockets, quality, an enchantment, implicits, k-of-n entries, actions) has a JSON form, so no
    request of the site fails on keying it; the form is JSON and the same for the same file read twice."""
    data = real_game_data()
    for path in sorted((Path(__file__).parents[1] / "examples" / "targets").glob("*.yaml")):
        form = target_form(load_target(path, data))
        assert json.loads(json.dumps(form)) == form, path.name
        assert target_form(load_target(path, data)) == form, path.name
