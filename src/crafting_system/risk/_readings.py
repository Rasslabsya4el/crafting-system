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

Hinekora's Lock (ADR-0054, ticket #297). A reading's model may offer a `Peek`; each reading is then solved by `solve_peek`, and its
candidate is its policy together with its **acceptance sets** (`Route.reactions`). Under another reading the candidate's acceptance
sets stay as they are and only the chances are recomputed from that reading's kernels (`solver.ExpandedModel`, lenient): the Lock
leads to the same "apply a" and "give up" pseudo-states with the chances of that reading, an option is matched across readings by its
label, a pair whose result that reading cannot throw drops out, a result the set does not hold is not accepted, and a state at which the
candidate did not take the Lock keeps its plain actions only. A pseudo-state the candidate never reached under its own reading (its
chance was 0 there) takes its only action, or at "give up" the fallback that is best by the candidate's own values. The baseline is
solved by `solve_peek` too, with the actions left out removed from the Peeks' options and fallbacks. A model without a Peek is solved
and walked exactly as before.

Known limits:
* A completion round solves every model again (the optima do not change, only the starts grow); a model set whose
  readings reach many states the others do not pays for the extra rounds. The first round is the only one when the
  readings share their supports, which holds for the exponent `alpha` of the recombinator (weights change, supports not).
* Ties go to the plan: another candidate replaces the incumbent only when its worst case is below the incumbent's by more
  than the certified error of both (`worst.high < worst.low`). A `ConvergenceError` of any reading's solve aborts the report.
* The comparison route is solved on the plan reading's model: the actions left out are the ones that read an axis, so the
  rest is the same under every reading.
"""

import math
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, field

from ..solver import GIVE_UP, Action, ExpandedModel, Model, Peek, PeekNode, Reaction, Solution, action_value, solve_peek
from ._mean import INFINITE, policy_mean
from ._moments import interval
from ._report import Estimate, Expected

GAP_TOLERANCE = 1e-9  # relative: a bracket this narrow counts as closed (`IntervalReport.proven_optimal`)
FIRST = object()  # `plan` default: the first reading of `models` (None can be a reading, e.g. the empty one)


@dataclass(frozen=True, slots=True)
class Route[S, R]:
    """The optimal policy of one reading, and what it costs under every reading.

    `policy` is the solver's, state to the action of `reading`'s own model (with the Lock's pseudo-states, `solver.PeekNode`, when
    it takes the Lock). `reactions` holds the acceptance set of every state at which its reading's model offers the Lock (empty
    without a Lock); under another reading those sets stay and only the chances change. `costs[r']` is its mean cost from the start under
    reading `r'` (an `Expected`: an `Estimate` and, when it is infinite, its cause, M7 #512). `best` and `worst` are the least and the
    greatest of the points over the readings, as intervals: `value` is the point, `low` and `high` hold for the true number
    whatever the float rounding. `best_reading` and `worst_reading` name where they sit.
    """

    reading: R
    policy: Mapping[S, Action[S]]
    costs: Mapping[R, Expected]
    best_reading: R
    worst_reading: R
    best: Estimate
    worst: Estimate
    reactions: Mapping[S, Reaction] = field(default_factory=dict)

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
    * `solution`: the whole solution of the plan reading (its values and policy at every state solved), the one `plan.policy`
      is taken from: the planner reports it as the plan (#589). None only for a report built by hand.
    """

    readings: tuple[R, ...]
    plan: Route[S, R]
    robust: Route[S, R]
    routes: Mapping[R, Route[S, R]]
    values: Mapping[R, Estimate]
    table: Mapping[R, Mapping[R, Expected]]
    lower: Estimate
    upper: Estimate
    baseline: Baseline[S] | None
    solution: Solution[S] | None = None

    @property
    def robust_differs(self) -> bool:
        """True when the route with the smallest worst case is not the plan (the report then names both)."""
        return self.robust.reading != self.plan.reading

    @property
    def gap(self) -> float:
        return 0.0 if self.upper.value == self.lower.value else self.upper.value - self.lower.value

    @property
    def proven_optimal(self) -> bool:
        """The bracket of `W*` is finite and closed (to `GAP_TOLERANCE`): the robust route is optimal over every policy."""
        return math.isfinite(self.upper.value) and self.gap <= GAP_TOLERANCE * abs(self.upper.value)


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
    """A model with some actions left out; a Peek keeps the options and fallback actions that are not, and goes when no option is left.

    `drop` is asked about ordinary actions only, never about the Peek itself: the Lock cannot be switched off here (a target's
    `actions:` does that before the model is built)."""

    def __init__(self, memo: _Memo[S], drop: Callable[[Action], bool]) -> None:
        self.memo = memo
        self.drop = drop

    def is_goal(self, state: S) -> bool:
        return self.memo.is_goal(state)

    def actions(self, state: S) -> tuple:
        found = []
        for action in self.memo.actions(state):
            if isinstance(action, Peek):
                options = tuple(a for a in action.options if not self.drop(a))
                if options:
                    found.append(Peek(action.label, action.cost, options, tuple(a for a in action.fallback if not self.drop(a))))
            elif not self.drop(action):
                found.append(action)
        return tuple(found)


def _peek_at(memo: _Memo, state: Hashable) -> Peek | None:
    return next((a for a in memo.actions(state) if isinstance(a, Peek)), None)


def _translated(reactions: Mapping, own: _Memo, other: _Memo) -> dict:
    """A candidate's acceptance sets as they read in another reading's model: each option matched by its label (a pair whose option that
    model does not offer at the state drops out, as does every pair of a state where it offers no Lock)."""
    found = {}
    for state, reaction in reactions.items():
        mine, theirs = _peek_at(own, state), _peek_at(other, state)
        if mine is None or theirs is None:
            continue
        index: dict = {}
        for b, option in enumerate(theirs.options):
            index.setdefault(option.label, b)
        found[state] = tuple((index[mine.options[a].label], r) for a, r in reaction if mine.options[a].label in index)
    return found


def _estimate(value: float, error: float) -> Estimate:
    if math.isinf(value):
        return INFINITE
    return Estimate(value, *interval(value, error))


def _walk[S](
    candidate: Mapping[S, Action[S]], start: S, memo: _Memo[S], own: bool, values: Mapping[S, float] | None = None
) -> tuple[dict[S, Action[S]], list[S]]:
    """The candidate as a policy of the model `memo`, over the states it reaches there, and the reached states it does not cover.

    `own` says the candidate was made for this very model: its actions are used as they are. Otherwise each action is
    looked up by label; one the model does not offer leaves its state stuck (no entry, and not reported as uncovered).
    A Lock's "apply" pseudo-state takes its one action from `memo` (an option's index may differ between readings, its node is
    never looked up in the candidate); a "give up" node the candidate does not hold takes the fallback best by the candidate's `values`.
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
        as_is = own
        if isinstance(state, PeekNode) and (chosen is None or state.kind != GIVE_UP):
            # an "apply" node holds the option's one action, whatever index the option has in this reading (#297)
            chosen, as_is = _node_action(state, memo, values or {}), True
        if chosen is None:
            if not isinstance(state, PeekNode):
                uncovered.append(state)
            continue
        action = chosen if as_is else memo.by_label(state, chosen.label)
        if action is None:
            continue
        actions[state] = action
        targets = [t for t, weight in action.outcomes if weight]
        for target in (*targets, *action.extra_inputs):
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return actions, uncovered


def _node_action(node: PeekNode, memo: _Memo, values: Mapping) -> Action | None:
    """The action of a Lock's pseudo-state that the candidate never reached: an "apply" node's one action, or the fallback best by `values`."""
    offered = memo.actions(node)
    if len(offered) <= 1 or node.kind != GIVE_UP:
        return offered[0] if offered else None
    return min(offered, key=lambda action: action_value(action, values))


def _key(policy: Mapping, reactions: Mapping) -> tuple[frozenset, frozenset]:
    return frozenset((state, action.label) for state, action in policy.items()), frozenset(reactions.items())


def _best_and_worst[R](costs: Mapping[R, Expected]) -> tuple[R, R, Estimate, Estimate]:
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
    plan: R = FIRST,  # type: ignore[assignment]
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
    if plan is FIRST:
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
    views: dict[tuple, _Memo] = {}  # (candidate key, reading) -> the reading's model under the candidate's acceptance sets

    def view(c: R, r2: R) -> _Memo:
        reactions = solutions[c].reactions
        if not reactions:
            return memos[r2]
        slot = (keys[c], r2)
        if slot not in views:
            fixed = reactions if c == r2 else _translated(reactions, memos[c], memos[r2])
            views[slot] = _Memo(ExpandedModel(memos[r2], fixed, lenient=True))
        return views[slot]

    # the optimum of every reading, from starts enlarged until each optimum is total under every other reading
    starts: dict[S, None] = {start: None}
    walks: dict[tuple, tuple[dict[S, Action[S]], list[S]]] = {}
    while True:
        solutions = {r: solve_peek(memos[r], list(starts), **options) for r in order}
        keys = {r: _key(solutions[r].policy, solutions[r].reactions) for r in order}
        walks.clear()
        views.clear()
        grown = False
        for r in order:
            for r2 in order:
                if (keys[r], r2) in walks:
                    continue
                walk = walks[(keys[r], r2)] = _walk(
                    solutions[r].policy, start, view(r, r2), own=r == r2, values=solutions[r].values
                )
                for state in walk[1]:
                    if state not in starts:
                        starts[state] = None
                        grown = True
        if not grown:
            break

    means: dict[tuple[frozenset, R], Expected] = {}

    def cost(c: R, r2: R) -> Expected:
        slot = (keys[c], r2)
        if slot not in means:
            means[slot] = policy_mean(walks[slot][0], start, view(c, r2).is_goal)
        return means[slot]

    table = {c: {r2: cost(c, r2) for r2 in order} for c in order}
    values = {r: _estimate(solutions[r].values[start], solutions[r].error_bound) for r in order}
    routes = {}
    for c in order:
        best_reading, worst_reading, best, worst = _best_and_worst(table[c])
        routes[c] = Route(c, solutions[c].policy, table[c], best_reading, worst_reading, best, worst, solutions[c].reactions)

    chosen = plan
    for c in order:
        if routes[c].worst.high < routes[chosen].worst.low:  # better beyond the certified error, else a tie
            chosen = c

    lower = Estimate(
        max(v.value for v in values.values()), max(v.low for v in values.values()), max(v.high for v in values.values())
    )
    baseline = None
    if without is not None:
        kept = _Without(memos[plan], without)
        found = solve_peek(kept, [start], **options)
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
        solution=solutions[plan],
    )

