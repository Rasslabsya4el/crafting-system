"""What a worker process does with one job: load the world, call the planner's entry, and send its words back to the service.

`run_job` is the body of a worker process. It talks to the service only through `send`: `("standing", {...})` each time the search says
where it stands, then one last message, `("done", {...}, key)` with the route (its `summary` names the price snapshot it was planned on, `snapshot`) and the key of the inputs it was planned with (the price
file read in this process, which may be newer than the one the job was keyed with), or `("failed", text)` with the planner's own words. A `Work`
function takes the world, the checked request and a `watch`, and returns the route: `plan_request` is the site's; tests name their own.
"""

import math
import traceback
from collections.abc import Callable
from datetime import UTC

from crafting_system.actions import NotApplicableError, OutOfScopeError, imprints_held_at_most
from crafting_system.data import DataError
from crafting_system.prices import PriceFileNotFound
from crafting_system.solver import ConvergenceError
from crafting_system.targets import StartKind, TargetError, buy_spec_of
from crafting_system.budget import BudgetExceeded
from crafting_system.cli import build_report, plan_record, policy_document, report_net, route_page
from crafting_system.planner import PlanError, PlanSettings, Standing, plan_target

from ._request import parse_request
from ._world import SNAPSHOT_TIME_FORMAT, World, WorldSource

# the refusals a plan run gives in its own words; the command line prints the same set as an `Error:` line (`cli._main`)
REFUSALS = (TargetError, DataError, PriceFileNotFound, PlanError, NotApplicableError, OutOfScopeError, ConvergenceError, ValueError, OSError)

Watch = Callable[[dict], None]
Work = Callable[[World, dict, str, Watch], dict]


def _number(value: float | None) -> float | None:
    return None if value is None or not math.isfinite(value) else value


def standing_document(standing: Standing) -> dict:
    """Where the search stands, as the job shows it: the best plan's mean cost so far and the figure no plan can cost less than (both
    after the start item, so without its price), the proved gap between them, and the search's rounds and seconds (OR-39, #906)."""
    return {
        "plan_cost_without_start": _number(standing.upper),
        "lower_bound_without_start": _number(standing.lower),
        "gap": _number(standing.gap),
        "rounds": standing.rounds,
        "seconds": standing.seconds,
    }


def _search_document(plan) -> dict | None:
    search = plan.search
    if search is None:
        return None
    gap = None if not search.lower > 0 or not math.isfinite(search.upper) else max(search.upper / search.lower - 1.0, 0.0)
    document = {"exact": search.exact, "within": search.within, "stopped": search.stopped, "gap": gap}
    if search.widening:  # the offers were searched in rounds (#1069): each round, how it ended and its figures (OR-13)
        document["rounds"] = [record.document() for record in search.widening]
    return document


def plan_request(world: World, request: dict, game: str, watch: Watch) -> dict:
    """The site's work: the plan of `request` in `world`, its figures as the planner states them, the JSON policy and the route page."""
    checked = parse_request(request, game, world)
    methods, settings = checked.document["methods"], checked.document["settings"]
    with imprints_held_at_most(world.config.max_imprints):
        plan = plan_target(
            world.data, checked.target, world.prices,
            PlanSettings(
                recipe_starts=methods["recipe_starts"], strands=methods["strands"], start_price=settings["start_price"],
                methods=None if methods.get("allowed") is None else tuple(methods["allowed"]),
                price_source=settings["price_source"], price_gap_percent=world.config.price_gap_percent, today=world.price_day, budget=world.budget,
                time_limit_seconds=settings.get("time_limit_seconds"),
                watch=lambda standing: watch(standing_document(standing)),
            ),
        )  # fmt: skip
        name = f"{world.data.base_items[checked.target.base_id].name}, item level {checked.target.item_level}"
        page = None
        try:
            with report_net(None if world.budget is None else world.budget.memory_mb):  # the outputs ask the run's memory net (#1381)
                report = build_report(plan, world.data)
                policy = policy_document(report, None, target_name=name)
                if plan.approximation is None:  # the page is not built for an approximate answer yet, as on the command line
                    spec = buy_spec_of(world.data, checked.target) if checked.target.start is StartKind.BOUGHT else None
                    page = route_page(report, world.data, buy_spec=spec, cache_dir=world.config.cache_dir)
        except BudgetExceeded as stop:  # past the net after the plan: the plan's record, its stop said, and no page (#1381, OR-13)
            policy, page = plan_record(plan, target_name=name, stopped=stop.binding.words()), None
    summary = {
        "answer": policy["answer"],
        "totals": policy["totals"],
        "start": policy["start"],
        "prices": policy["prices"],
        "limits": policy["limits"],
        "search": _search_document(plan),
        "time_limit_seconds": settings.get("time_limit_seconds"),  # the time limit the plan ran under (#1577; None: no time limit)
    }
    return {"summary": summary, "policy": policy, "page": page}


def run_job(world_source: WorldSource, work: Work, request: dict, game: str, send: Callable[[tuple], None]) -> None:
    """The body of a worker process: one job, start to end, every word of it through `send`."""
    try:
        world = world_source()
        key = parse_request(request, game, world).key
        route = work(world, request, game, lambda standing: send(("standing", standing)))
        prices = world.prices  # the snapshot the route was planned on, so the API can say its age on any later day (#976)
        snapshot = {"league": prices.league, "fetched_at": prices.fetched_at.astimezone(UTC).strftime(SNAPSHOT_TIME_FORMAT)}
        route = {**route, "summary": {**route["summary"], "snapshot": snapshot}}
    except REFUSALS as error:
        send(("failed", str(error)))
    except Exception as error:  # noqa: BLE001  (a fault of the service, not a refusal of the planner: said, never swallowed)
        send(("failed", f"internal error: {type(error).__name__}: {error}\n{traceback.format_exc(limit=8)}"))
    else:
        send(("done", route, key))
