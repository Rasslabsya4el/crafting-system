"""The heavy benchmark's record of the site's plans of the reference routes (every beta method on, no guide's actions), and the check of a new run against it (#1109).

`benchmark --net` plans every benchmark route the way the site does (`SITE_PLAN`, #1156): the target alone with the default offers (every beta
method on, OR-41) and the planner settings' vendor-recipe starts, no guide's actions leading the first round of offers (those lead only the guided plan of a plain `benchmark`, #1110, which
no user gets), under the run's budget from the planner settings of the machine (OR-40; with the default settings `Budget.default()`, the
10-minute net). A record and a check take only runs of the site's plan, so a record of the guided plan cannot guard the site's. Each route's entry then carries
a `record` (`record_of_plan`): the plan's cost (its mean, the start item included), the figure no plan can cost less than (`lower`, the start
item included), the seconds of the plan, the peak memory the search read, and how the search ended (`stop`). A route the run could not plan
carries no cost and its error is its stop.

A run under a time net depends on the machine and on the run, so a record is made of **two** runs (`make_record`): per route both runs, the
spread between their costs, and the ceiling a new run may reach. The check (`check_run`) is "no worse than", not equality: a route fails when
its new cost is above the ceiling, or when it gives no plan (or no entry: its runner died) where both recorded runs gave one.

The ceiling is the higher recorded cost plus the larger of the spread of the two runs and `TOLERANCE_FLOOR` of that cost. The floor is the
proof the search owes (`budget.PROOF_GAP`, OR-39): a plan the search stopped at a proved 1% may cost up to 1% more than another run's, and two
runs that happened to agree must not make the check fail on that. A route that planned in one recorded run and not in the other has no
spread to measure (`UNSTABLE`): every new result passes until the record is renewed. A route that planned in neither passes too, and a new plan
there is told as such. The tolerance is checked on the cost alone: the lower bound, the seconds, the memory and the stop are recorded so that
a reader sees what changed, and they are machine readings, not verdicts.

A plan no player would follow is no plan (#1628): the planner's entry answers it as "no usable plan found within the limit"
(`planner.UnusablePlan`), so its run's record has no cost, and a record never holds it as a plan. And a route that passes with a plan dearer
than `GUIDE_FLAG_TIMES` its guide's route (the guide's figure the same run evaluated, `given_route`) is flagged (`FLAGGED`): it fails
nothing, and a person reads that plan (R24's 51,581 c at the ten-minute runner net, 10.7 times its guide's 4,838.92 c). The figure is the
check's, not the planner's: a plan dearer than the guide is still shown, with the honest label (OR-59, the owner on R17 at 1.8 times).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from crafting_system.budget import PROOF_GAP

FORMAT = "crafting-system-heavy-benchmark-record/2"  # /2: the site's plan, with no guide's actions (#1156); /1 recorded the guided plan
SITE_PLAN = "site"  # the plan a `benchmark.json` of `--net` holds: the target alone, as the site plans it (#1156)
GUIDED_PLAN = "guided"  # the plan of a `benchmark` with no net: a guide's actions lead its first round (#1110)
TOLERANCE_FLOOR = PROOF_GAP  # the least tolerance of a route, as a share of its higher recorded cost (see the module text)
GUIDE_FLAG_TIMES = 10.0  # a passing plan dearer than this many times its guide's route is flagged for a person (see the module text)

PLANNED = "planned"  # both recorded runs gave a plan: the route is checked against its ceiling
UNSTABLE = "unstable"  # one recorded run gave a plan and the other did not: no spread to check against
NO_PLAN = "no plan"  # neither recorded run gave a plan

PASS = "pass"
FLAGGED = "needs a human"  # passes, but a person must read the plan: dearer than `GUIDE_FLAG_TIMES` its guide's route
FAIL = "fail"
NOT_RUN = "not run"  # a route of the record the new run left out: a failure, unless the check was asked for some routes only
NOT_RECORDED = "not recorded"  # a route of the new run the record does not hold


def record_of_plan(mean: float | None, lower: float | None, seconds: float | None, peak_mb: float | None, stop: str) -> dict:
    """The record of one route in one run: its cost (None without a plan) and the readings beside it."""
    return {"mean": mean, "lower": lower, "seconds": seconds, "peak_mb": peak_mb, "stop": stop}


def merge_documents(documents: Iterable[Mapping]) -> dict:
    """One run made of the `benchmark.json` parts a split run wrote (one per runner, and the `start` and `own` folders of
    `benchmark_routes.py`): every part's routes, the distinct machines they ran on, and the first part's prices and budget; the parts
    must hold one plan (`SITE_PLAN` or `GUIDED_PLAN`)."""
    parts = list(documents)
    if not parts:
        raise ValueError("no benchmark.json to read")
    machines: list = []
    for part in parts:
        if part.get("machine") not in machines:
            machines.append(part.get("machine"))
    routes = [entry for part in parts for entry in part.get("routes", ())]
    names = [entry["id"] for entry in routes]
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        raise ValueError(f"route {', '.join(twice)} is in more than one part of the run")
    plans = sorted({str(part.get("plan")) for part in parts})
    if len(plans) > 1:
        raise ValueError(f"the parts of the run hold different plans ({', '.join(plans)})")
    return {
        "machine": machines,
        "ran_at": min((part.get("ran_at") or "" for part in parts), default=None),
        "prices": parts[0].get("prices"),
        "budget": parts[0].get("budget"),
        "plan": parts[0].get("plan"),
        "routes": routes,
    }


def runs_of(document: Mapping) -> dict[str, dict]:
    """The record of each route of one `benchmark.json` (a run with `--net`), by route id; a route with an error and no record gets one
    with no cost whose stop is the error."""
    found: dict[str, dict] = {}
    for entry in document.get("routes", ()):
        record = entry.get("record")
        if record is None:
            if not entry.get("error"):
                raise ValueError(f"route {entry['id']} has no record: the run was not made with --net")
            record = record_of_plan(None, None, None, None, entry["error"])
        found[entry["id"]] = record
    return found


@dataclass(frozen=True)
class RouteRecord:
    """One route of a record: its two runs, how they agree, and the most a new run may cost."""

    first: dict
    second: dict

    @property
    def state(self) -> str:
        planned = (self.first["mean"] is not None, self.second["mean"] is not None)
        return PLANNED if all(planned) else NO_PLAN if not any(planned) else UNSTABLE

    @property
    def spread(self) -> float | None:
        """The higher cost less the lower, in Chaos; None unless both runs planned."""
        if self.state != PLANNED:
            return None
        return abs(self.first["mean"] - self.second["mean"])

    @property
    def ceiling(self) -> float | None:
        """The most a new run's plan may cost and pass; None when no ceiling applies (see the module text)."""
        if self.state != PLANNED:
            return None
        high = max(self.first["mean"], self.second["mean"])
        return high + max(self.spread, TOLERANCE_FLOOR * high)

    def document(self) -> dict:
        spread = self.spread
        low = None if spread is None else min(self.first["mean"], self.second["mean"])
        return {
            "runs": [self.first, self.second],
            "state": self.state,
            "spread": spread,
            "spread_share": None if spread is None or not low else spread / low,
            "ceiling": self.ceiling,
        }


KILLED = "no entry in the run: its runner was killed (its timeout or its memory) before the plan stopped"


def make_record(first: Mapping, second: Mapping, routes: Iterable[str] | None = None, killed: Iterable[str] = ()) -> dict:
    """The record made of two `benchmark.json` documents of `--net` runs: every route of both (or of `routes`), with both runs' figures,
    the spread and the ceiling; and the machine, commit, time and budget of each run.

    A route of `killed` (named by the caller, who saw its runner die: a plan that does not stop at its net, #1156) that a run holds no entry
    for is recorded there with no plan, its stop `KILLED`; any other route missing from a run is refused, so that no route drops out unsaid."""
    one, two = dict(runs_of(_site(first))), dict(runs_of(_site(second)))
    for name in killed:
        for found in (one, two):
            found.setdefault(name, record_of_plan(None, None, None, None, KILLED))
    wanted = list(routes) if routes is not None else [name for name in one if name in two]
    stray = [name for name in killed if name not in wanted]
    if stray:
        raise ValueError(f"{', '.join(stray)} is named as killed but is not a route of the record")
    missing = [name for name in wanted if name not in one or name not in two]
    if missing:
        raise ValueError(f"a record needs two runs of every route; {', '.join(missing)} is not in both runs")
    return {
        "format": FORMAT,
        "plan": SITE_PLAN,
        "runs": [_run_heading(first), _run_heading(second)],
        "routes": {name: RouteRecord(one[name], two[name]).document() for name in wanted},
    }


def _site(document: Mapping) -> Mapping:
    """`document`, when it holds the site's plans (`SITE_PLAN`); a run of the guided plan or of no stated plan is refused (#1156)."""
    plan = document.get("plan")
    if plan != SITE_PLAN:
        raise ValueError(f"the run holds the {plan or 'unstated'} plan, not the site's: the heavy benchmark records and checks `benchmark --net` runs only")
    return document


def _run_heading(document: Mapping) -> dict:
    return {key: document.get(key) for key in ("machine", "ran_at", "prices", "budget")}


@dataclass(frozen=True)
class Verdict:
    """The check of one route: `PASS`, `FAIL`, `NOT_RUN` or `NOT_RECORDED`, and why, in words."""

    route: str
    outcome: str
    why: str


def check_run(record: Mapping, document: Mapping, routes: Iterable[str] | None = None) -> list[Verdict]:
    """The verdict of every route of the record (or of `routes`, a run of some routes only), and of every route of the new run the record
    does not hold (see the module text). A route asked for that the run does not hold fails (`NOT_RUN`): a runner killed for its memory or
    its timeout writes no `benchmark.json`, and its routes must not pass by being absent."""
    if record.get("format") != FORMAT:
        raise ValueError(f"not a record of the heavy benchmark (format {record.get('format')!r}, not {FORMAT!r})")
    new = runs_of(_site(document))
    guides = guides_of(document)
    wanted = list(record["routes"]) if routes is None else list(routes)
    unknown = [name for name in wanted if name not in record["routes"]]
    if unknown:
        raise ValueError(f"the record does not hold {', '.join(unknown)}")
    verdicts = []
    for name in wanted:
        held = record["routes"][name]
        first, second = held["runs"]
        if name not in new:
            if RouteRecord(first, second).state == NO_PLAN:  # no plan to lose: a runner that dies there gives what the record holds
                verdicts.append(Verdict(name, PASS, "no plan in either recorded run, and no entry now (a runner that died writes none)"))
            else:
                verdicts.append(Verdict(name, NOT_RUN, "the run holds no entry for this route (a runner that died writes none)"))
            continue
        verdicts.append(_flagged(_verdict(name, RouteRecord(first, second), new[name]), new[name]["mean"], guides.get(name)))
    verdicts.extend(Verdict(name, NOT_RECORDED, "the record does not hold this route") for name in new if name not in record["routes"])
    return verdicts


def _verdict(name: str, held: RouteRecord, run: Mapping) -> Verdict:
    cost = run["mean"]
    if held.state == NO_PLAN:
        said = "no plan in either recorded run"
        return Verdict(name, PASS, f"{said}; now a plan of {cost:,.2f} c" if cost is not None else f"{said}, none now ({run['stop']})")
    if held.state == UNSTABLE:
        return Verdict(name, PASS, "the record is unstable (a plan in one recorded run of two): no check until it is renewed")
    ceiling = held.ceiling
    assert ceiling is not None  # a planned record has one
    if cost is None:
        return Verdict(name, FAIL, f"no plan ({run['stop']}), where both recorded runs gave one (up to {ceiling:,.2f} c passes)")
    if cost > ceiling:
        return Verdict(name, FAIL, f"{cost:,.2f} c, above the ceiling of {ceiling:,.2f} c")
    return Verdict(name, PASS, f"{cost:,.2f} c, within the ceiling of {ceiling:,.2f} c")


def guides_of(document: Mapping) -> dict[str, float]:
    """The cost of each route's guide's route that a run evaluated (`given_route.mean`, the start item included), by route id."""
    found = {}
    for entry in document.get("routes", ()):
        mean = (entry.get("given_route") or {}).get("mean")
        if isinstance(mean, (int, float)) and mean > 0:
            found[entry["id"]] = float(mean)
    return found


def _flagged(verdict: Verdict, cost: float | None, guide: float | None) -> Verdict:
    """`verdict`, flagged for a person when it passes a plan dearer than `GUIDE_FLAG_TIMES` its guide's route (see the module text)."""
    if verdict.outcome != PASS or cost is None or guide is None or cost <= GUIDE_FLAG_TIMES * guide:
        return verdict
    return Verdict(verdict.route, FLAGGED, f"{verdict.why}; {cost / guide:,.1f} times its guide's route ({guide:,.2f} c): a person reads this plan")


def render_check(verdicts: Iterable[Verdict]) -> str:
    """One line per route: its id, its verdict and why."""
    return "\n".join(f"{verdict.route}: {verdict.outcome.upper()}: {verdict.why}" for verdict in verdicts)


def failed(verdicts: Iterable[Verdict]) -> bool:
    """Whether any route failed the check."""
    return any(verdict.outcome in (FAIL, NOT_RUN) for verdict in verdicts)
