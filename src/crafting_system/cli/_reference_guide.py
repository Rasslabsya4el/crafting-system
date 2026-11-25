"""The guide's recorded figure of a target that is a reference craft, for a page built with no guide's route given (#1596, OR-59).

A reference craft (`_benchmark.REFERENCES`) names its target file and its guide's route file. When the route's rules do not finish on the
target (they have gaps), the route file records the guide's cost (`recorded_cost`), and the proof sentence compares the plan's cost with it,
said as recorded. A page built from a plan alone (the plain command with no `--route`, the `page` command with no `--route`, the website)
looks the target up among the reference crafts and says that figure too, so a plan dearer than its guide is never shown without saying so
(the owner's condition for showing R17 at all, 2026-11-24). The target matches when it states the same item as the reference's file: the
price file it names and the run's methods setting are not the item, so they are left out of the comparison.

`reference_beside` goes further for the page (#1584): it prices the reference's guide's route on the plan's model, as the benchmark does,
so the page can say the plan's cost against it and the steps where the two part. The guide's words are priced as written when they finish;
else as the reference's completed route (R04), else with a restart where its rules stop, which is how a recorded figure is measured (R17),
used only when it gives that figure to within 1%; else the recorded figure alone. A target that is no reference craft has no guide.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from crafting_system.config import find_project_root
from crafting_system.data import DataError, GameData
from crafting_system.planner import Plan, PlanError
from crafting_system.targets import Target, TargetError, load_target

from ._route import RESTART, Route, RouteError, Rule, When, evaluate_route, load_route, recorded_cost_of, route_actions
from ._route_view import COMPLETED_READING, RESTART_READING, GuideBeside, given_cost, judged_on


def _item(target: Target) -> Target:
    return replace(target, price_file=None, actions=None)


def _reference(data: GameData, target: Target, root: Path):
    """The reference craft (`_benchmark.BenchmarkRoute`) whose target states the same item as `target` and that has a guide's route, or None."""
    from ._benchmark import REFERENCES  # the list of the reference crafts lives with the benchmark, which imports the page code

    wanted = _item(target)
    for bench in REFERENCES:
        if bench.route is None:
            continue
        try:
            reference = load_target(root / bench.target, data)
        except (TargetError, DataError):  # a reference file this install cannot read: not this target
            continue
        if _item(reference) == wanted:
            return bench
    return None


def _priced(plan: Plan, path: Path, data: GameData, target: Target) -> tuple[Plan, Route, object]:
    """The route file at `path` evaluated on the plan it is judged on (`judged_on`): that plan, the route and its result."""
    judged = judged_on(plan, route_actions(path), data, target)
    route = load_route(path, judged, data)
    return judged, route, evaluate_route(judged, route, data)


def reference_beside(data: GameData, plan: Plan, target: Target, root: Path | None = None) -> GuideBeside | None:
    """The guide's route of the reference craft `target` states, priced on `plan`'s model for the page's block against the guide (#1584), or
    None: no such reference, or a route that cannot be read or priced here (the page then says only what `reference_guide` gives). `target`
    is the target as its file states it (`judged_on`)."""
    root = find_project_root() if root is None else root
    bench = _reference(data, target, root)
    if bench is None:
        return None
    try:
        judged, route, given = _priced(plan, root / bench.route, data, target)
        if given_cost(judged, given) is not None:
            return GuideBeside(judged, route, given)
        if bench.completed is not None:
            judged_c, completed, again = _priced(plan, root / bench.completed, data, target)
            if given_cost(judged_c, again) is not None:
                return GuideBeside(judged_c, completed, again, COMPLETED_READING)
        recorded = route.recorded_cost
        if recorded is None:
            return None
        # the rules with a last restart: how the file's figure was measured (its comment says so); its steps are used when they give that figure
        restarting = replace(route, rules=(*route.rules, Rule(0, When(), RESTART)), recorded_cost=None)
        again = evaluate_route(judged, restarting, data)
        cost = given_cost(judged, again)
        if cost is not None and math.isclose(cost, recorded, rel_tol=0.01):
            return GuideBeside(judged, route, again, RESTART_READING, recorded=True)
        return GuideBeside(judged, route, None, recorded=True)
    except (RouteError, PlanError):
        return None


def reference_guide(data: GameData, target: Target, root: Path | None = None) -> float | None:
    """The recorded guide's cost of the reference craft whose target states the same item as `target`, or None (no such reference, or its
    route records no figure because its rules finish: its cost is then the route's own, given with `--route`). `root` is the project root
    (default: the one this package is in); a reference whose files cannot be read there is passed over."""
    root = find_project_root() if root is None else root
    bench = _reference(data, target, root)
    return None if bench is None else recorded_cost_of(root / bench.route)
