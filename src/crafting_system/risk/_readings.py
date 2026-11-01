"""The interval driver over rule axes (ADR-0012 amended, ADR-0022 reworded; ticket #220).

Some rules the sources leave open are rule axes (ADR-0033): the exponent `alpha` of the recombinator's selection, the
Awakener's group conflict. Each combination of one value per axis is a **reading**, and each reading is one ordinary
model that `solve` handles; the solver never learns what an axis is. The driver takes one model per reading (5, 2 or
10 of them) and, in `risk`:

* solves every model (`k` solves); the solution of the plan reading is the **plan**, the route at `alpha = 1` and the
  receiver's mod surviving, and the best cost `V_r` of each reading is a lower bound of what any route can promise;
* evaluates every candidate policy, the optimum of each reading, under every reading (`k^2` fixed-policy evaluations,
  exact linear systems, `_mean`): `J(pi_r, r')`, the table of the report;
* reads from the plan's row its cost interval `[min over r'; max over r']` over the **whole** grid, not its two ends: the
  extreme of a route's cost is often interior (132 of 1,200 random cases, research #90, ADR-0012), so a route whose
  minimum lies at an inner grid point is found;
* names the **route with the smallest worst case**, the candidate with the least `max over r' of J`; it is the plan itself
  unless another candidate is strictly better, and the report says whether it differs;
* certifies the bracket of the robust optimum `W* = min over policies of max over readings of J`:

      max_r V_r  <=  W*  <=  min over candidates of max_r' J(pi_c, r')

  A gap of zero proves the route optimal; otherwise the report shows the gap (`W*` can lie anywhere inside it, and the
  true optimum over a continuous `alpha` can lie outside the grid's by whatever happens between grid points, so the
  interval is an inner bound until a finer grid says otherwise, ADR-0022);
* solves the best route **without** the actions the caller leaves out (`without`, e.g. every action with inputs): the only
  comparison route anywhere (ADR-0012). The Awakener's conflict has its interval but no comparison route; its caller
  passes no `without`.

A rule is one global fact of the game, not a choice nature makes at each visit, which is why this is a family of solves and
not a game with a maximising nature (ADR-0022).

Completeness. A candidate is a policy of the states its own reading reaches. Under another reading a recombination can
land on a state the candidate never saw (the outcomes' support differs). Those states are added to the starts and every
model is solved again from the enlarged set, until each candidate is total on what it reaches under every reading; the
values do not change, only the policies get longer. A state that stays uncovered (its value is infinite, or the action the
candidate chose is not offered under the other reading) leaves the candidate stuck there: its cost under that reading is
infinite. Actions are matched across readings by their `label`, so labels must be unique within a state and must name the
same action under every reading.

Without any axis there is one model: the driver solves it once, the plan is that solution, and the interval is a point.
"""

import math
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass

from ..solver import Action, Model, solve
from ._mean import INFINITE, policy_mean
from ._moments import interval
from ._report import Estimate

GAP_TOLERANCE = 1e-9  # relative: a bracket this narrow counts as closed (`IntervalReport.proven_optimal`)
SAME = 1e-12  # relative: a candidate must be better than the incumbent by more than this to replace it


@dataclass(frozen=True, slots=True)
class Route[S, R]:
    """The optimal policy of one reading, and what it costs under every reading.

    `policy` is the solver's, state to the action of `reading`'s own model. `costs[r']` is its mean cost from the start under
    reading `r'` (an `Estimate`; infinite when the policy cannot finish there). `best` and `worst` are the least and the
    greatest of the points over the readings, as intervals: `value` is the point, `low` and `high` hold for the true number
    whatever the float rounding. `best_reading` and `worst_reading` name where they sit.
    """

    reading: R
    policy: Mapping[S, Action[S]]
    costs: Mapping[R, Estimate]
    best_reading: R
    worst_reading: R
    best: Estimate
    worst: Estimate

    @property
    def interval(self) -> tuple[float, float]:
        """`(best, worst)`: the cost interval of the route over all readings."""
        return (self.best.value, self.worst.value)


@dataclass(frozen=True, slots=True)
class Baseline[S]:
    """The best route when the actions left out are not offered: the comparison route of ADR-0012."""

    value: Estimate
    policy: Mapping[S, Action[S]]


@dataclass(frozen=True, slots=True)
class IntervalReport[S, R]:
    """What `solve_readings` returns.

    * `readings`: the readings in order, the plan first.
    * `plan`: the route optimal at the plan reading; its `interval` is the plan's cost interval over the grid.
    * `robust`: the route with the smallest worst case (the plan itself unless another candidate is strictly better; see
      `robust_differs`).
    * `routes`: the candidate of every reading, `values[r]` the best cost under reading `r` (the diagonal), `table[c][r']`
      the cost of the candidate of reading `c` under reading `r'`.
    * `lower`, `upper`: the certified bracket `lower <= W* <= upper` of the robust optimum; `upper` is the worst case of
      `robust`. `gap` is `upper - lower` and `proven_optimal` says it is closed.
    * `baseline`: the best route without the actions left out, or None when none were.
    """

    readings: tuple[R, ...]
    plan: Route[S, R]
    robust: Route[S, R]
    routes: Mapping[R, Route[S, R]]
    values: Mapping[R, Estimate]
    table: Mapping[R, Mapping[R, Estimate]]
    lower: Estimate
    upper: Estimate
    baseline: Baseline[S] | None

    @property
    def robust_differs(self) -> bool:
        """True when the route with the smallest worst case is not the plan (the report then names both)."""
        return self.robust.reading != self.plan.reading

    @property
    def gap(self) -> float:
        return 0.0 if self.upper.value == self.lower.value else self.upper.value - self.lower.value

    @property
    def proven_optimal(self) -> bool:
        """The bracket of `W*` is closed (to `GAP_TOLERANCE`): the robust route is optimal over every policy."""
        return self.gap <= GAP_TOLERANCE * abs(self.upper.value)


def has_inputs(action: Action) -> bool:
    """A ready `without` predicate: the actions that consume other items (recombinators, imprints, the Awakener's Orb)."""
    return bool(action.extra_inputs)


class _Memo[S]:
    """Asks a model once per state and keeps the answers; also finds an offered action by its label."""

    def __init__(self, model: Model[S]) -> None:
        self.model = model
        self._goals: dict[S, bool] = {}
        self._offers: dict[S, tuple] = {}
        self._labels: dict[S, dict] = {}

    def is_goal(self, state: S) -> bool:
        found = self._goals.get(state)
        if found is None:
            found = self._goals[state] = bool(self.model.is_goal(state))
        return found

    def actions(self, state: S) -> tuple:
        found = self._offers.get(state)
        if found is None:
            found = self._offers[state] = tuple(self.model.actions(state))
        return found

    def by_label(self, state: S, label: Hashable) -> Action[S] | None:
        table = self._labels.get(state)
        if table is None:
            table = self._labels[state] = {}
            for action in self.actions(state):
                table.setdefault(action.label, []).append(action)
        found = table.get(label)
        if not found:
            return None
        if len(found) > 1 and any(other != found[0] for other in found[1:]):
            raise ValueError(f"two different actions at {state!r} share the label {label!r}: readings are matched by label")
        return found[0]


class _Without[S]:
    """A model with some actions left out."""

    def __init__(self, memo: _Memo[S], drop: Callable[[Action], bool]) -> None:
        self.memo = memo
        self.drop = drop

    def is_goal(self, state: S) -> bool:
        return self.memo.is_goal(state)

    def actions(self, state: S) -> tuple:
        return tuple(a for a in self.memo.actions(state) if not self.drop(a))


def _estimate(value: float, error: float) -> Estimate:
    if math.isinf(value):
        return INFINITE
    return Estimate(value, *interval(value, error))


def _walk[S](
    candidate: Mapping[S, Action[S]], start: S, memo: _Memo[S], own: bool
) -> tuple[dict[S, Action[S]], list[S]]:
    """The candidate as a policy of the model `memo`, over the states it reaches there, and the reached states it does not cover.

    `own` says the candidate was made for this very model: its actions are used as they are. Otherwise each action is
    looked up by label; one the model does not offer leaves its state stuck (no entry, and not reported as uncovered).
    """
    actions: dict[S, Action[S]] = {}
    uncovered: list[S] = []
    seen = {start}
    stack = [start]
    while stack:
        state = stack.pop()
        if memo.is_goal(state):
            continue
        chosen = candidate.get(state)
        if chosen is None:
            uncovered.append(state)
            continue
        action = chosen if own else memo.by_label(state, chosen.label)
        if action is None:
            continue
        actions[state] = action
        targets = [t for t, weight in action.outcomes if weight]
        for target in (*targets, *action.extra_inputs):
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return actions, uncovered


def _key(policy: Mapping) -> frozenset:
    return frozenset((state, action.label) for state, action in policy.items())


def _best_and_worst[R](costs: Mapping[R, Estimate]) -> tuple[R, R, Estimate, Estimate]:
    best_reading = min(costs, key=lambda r: costs[r].value)
    worst_reading = max(costs, key=lambda r: costs[r].value)
    best = Estimate(
        costs[best_reading].value, min(c.low for c in costs.values()), min(c.high for c in costs.values())
    )
    worst = Estimate(
        costs[worst_reading].value, max(c.low for c in costs.values()), max(c.high for c in costs.values())
    )
    return best_reading, worst_reading, best, worst


def solve_readings[S, R: Hashable](
    models: Mapping[R, Model[S]],
    start: S,
    *,
    plan: R | None = None,
    without: Callable[[Action], bool] | None = None,
    tolerance: float = 1e-10,
    direct_solve_limit: int = 64,
    max_sweeps: int = 100_000,
    value_ceiling: float = 1e12,
) -> IntervalReport[S, R]:
    """Solve one model per reading, cross-evaluate the optimal policies and report the plan, its interval and the bracket.

    `models` maps each reading to its ordinary model (an `Action` model whose inputs are states, as `solve` takes it,
    e.g. an `Acquisition` product); `start` is the state to plan from (for an `Acquisition`, `acquisition.start(item)`).
    `plan` is the reading the plan is made at (default the first); the others follow in the order of `models`.
    `without`, when given, is a predicate on an `Action`: the actions it accepts are not offered in the comparison route,
    solved on the plan reading's model (`has_inputs` for "no recombinators"). The remaining options are those of `solve`.
    """
    order = list(models)
    if not order:
        raise ValueError("at least one reading (one model) is needed")
    if plan is None:
        plan = order[0]
    if plan not in models:
        raise ValueError(f"the plan reading {plan!r} is not one of the readings {order!r}")
    order = [plan, *(r for r in order if r != plan)]
    options = {
        "tolerance": tolerance,
        "direct_solve_limit": direct_solve_limit,
        "max_sweeps": max_sweeps,
        "value_ceiling": value_ceiling,
    }
    memos = {r: _Memo(models[r]) for r in order}

    # the optimum of every reading, from starts enlarged until each optimum is total under every other reading
    starts: dict[S, None] = {start: None}
    walks: dict[tuple[frozenset, R], tuple[dict[S, Action[S]], list[S]]] = {}
    while True:
        solutions = {r: solve(memos[r], list(starts), **options) for r in order}
        keys = {r: _key(solutions[r].policy) for r in order}
        walks.clear()
        grown = False
        for r in order:
            for r2 in order:
                if (keys[r], r2) in walks:
                    continue
                walk = walks[(keys[r], r2)] = _walk(solutions[r].policy, start, memos[r2], own=r == r2)
                for state in walk[1]:
                    if state not in starts:
                        starts[state] = None
                        grown = True
        if not grown:
            break

    means: dict[tuple[frozenset, R], Estimate] = {}

    def cost(c: R, r2: R) -> Estimate:
        slot = (keys[c], r2)
        if slot not in means:
            means[slot] = policy_mean(walks[slot][0], start, memos[r2].is_goal)
        return means[slot]

    table = {c: {r2: cost(c, r2) for r2 in order} for c in order}
    values = {r: _estimate(solutions[r].values[start], solutions[r].error_bound) for r in order}
    routes = {}
    for c in order:
        best_reading, worst_reading, best, worst = _best_and_worst(table[c])
        routes[c] = Route(c, solutions[c].policy, table[c], best_reading, worst_reading, best, worst)

    chosen = plan
    for c in order:
        new, old = routes[c].worst.value, routes[chosen].worst.value
        if new < old and not math.isclose(new, old, rel_tol=SAME):
            chosen = c

    lower = Estimate(
        max(v.value for v in values.values()), max(v.low for v in values.values()), max(v.high for v in values.values())
    )
    baseline = None
    if without is not None:
        kept = _Without(memos[plan], without)
        found = solve(kept, [start], **options)
        baseline = Baseline(_estimate(found.values[start], found.error_bound), found.policy)
    return IntervalReport(
        readings=tuple(order),
        plan=routes[plan],
        robust=routes[chosen],
        routes=routes,
        values=values,
        table=table,
        lower=lower,
        upper=routes[chosen].worst,
        baseline=baseline,
    )

