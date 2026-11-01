"""An answer that reads a rule axis: the plan, its cost interval over the grid and the facts behind it (ADR-0012, 0022, 0028, 0035; ticket #221).

Some rules the sources leave open are rule axes (ADR-0033): the recombinator's selection exponent `alpha`, the Awakener's group
conflict. `risk.solve_readings` (ticket #220) solves one model per reading, evaluates every candidate route under every reading and
hands back an `IntervalReport`; this module words it for the owner and for the JSON, from the same facts, so the text, the JSON
and the route page cannot disagree:

* the plan (the route at the plan reading, alpha = 1) and what it costs there;
* the plan's cost interval over the whole grid, with the reading of its cheapest and its dearest point, and one line a reading;
* the best route without recombinators beside it (the only comparison route anywhere, ADR-0012; none for the Awakener's conflict);
* the route with the smallest worst case, named when it is not the plan, and the certified bracket of that worst case;
* the expected number of recombinations of the plan, what one costs in Dust and Gold, the interval of that cost rule and what it
  does to the plan's mean when the route stays the same;
* the Dust and the Gold price the cost was made with, and where each came from;
* the approximate inputs (ADR-0028) of every route the answer shows, each claim with its spread.

An answer whose plan reads no axis (no recombinator in the plan) has no `IntervalAnswer`: `build_interval_answer` returns None and
the report says nothing about alpha, not even that it was considered. Nothing here is a bound on the true cost: the interval is the
plan's cost at each reading of the grid, and the true exponent can lie between two grid points (ADR-0022).
"""

import math
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.prices import DUST, GOLD
from crafting_system.risk import Estimate, IntervalReport, Route, expected_total
from crafting_system.solver import Action

from ._marking import ApproximateInput, approximate_inputs_of, number_text
from ._plan import Plan

AXIS_NAMES = {
    "recombinator.alpha": "alpha",
    "awakener.group_conflict": "group_conflict",
}
AXIS_WORDS = {
    "recombinator.alpha": "the recombinator's mod selection exponent alpha (a mod is kept in proportion to its weight to the power alpha)",
    "awakener.group_conflict": "which mod survives when the Awakener's Orb meets a group conflict",
}
FORMAT_NOTE = "The interval is the plan's cost at each value of the grid, not a bound: the true value can lie between two grid points."


def money(chaos: float) -> str:
    return "never" if math.isinf(chaos) else f"{chaos:,.2f}"


def _number(value: float) -> float | None:
    """A float for JSON: infinity has no JSON form, so it becomes null."""
    return None if math.isinf(value) or math.isnan(value) else value


def reading_text(reading: Hashable, used: frozenset[str] | None = None) -> str:
    """A reading in words: `alpha = 1` (several axes joined with a comma); a reading that is not a `Reading` is shown as it is.

    `used` limits a `Reading` to the axes the plan reads, so an axis the plan never touches is not named.
    """
    values = getattr(reading, "values", None)
    if values is None:
        return str(reading)
    shown = [
        f"{AXIS_NAMES.get(name, name)} = {number_text(float(value)) if isinstance(value, int | float) or hasattr(value, 'numerator') else value}"
        for name, value in values
        if used is None or name in used
    ]
    return ", ".join(shown) or "no rule axis"


@dataclass(frozen=True)
class ReadingRow:
    """One reading of the grid: what the plan costs there, and what the best route for that reading costs (None when readings were merged)."""

    reading: str
    plan_cost: Estimate
    best_cost: Estimate | None


@dataclass(frozen=True)
class CombineRow:
    """One recombination of the plan: how often it is used, what one use takes and what that costs at the point and at the ends of the cost rule."""

    label: str
    uses: Estimate
    resources: tuple[tuple[str, int], ...]
    chaos: float
    chaos_low: float
    chaos_high: float


@dataclass(frozen=True)
class PriceLine:
    """The price of Dust or Gold used for the cost, in Chaos each, and the source it came from."""

    name: str
    chaos_each: float
    source: str


@dataclass(frozen=True)
class IntervalAnswer:
    """What an answer says of the rule axes it read; every cost is a total in Chaos with the start item's price included."""

    axes: tuple[str, ...]  # the ids of the axes the plan reads
    plan_reading: str
    rows: tuple[ReadingRow, ...]
    plan: Estimate
    best: Estimate  # the plan's cheapest point over the grid
    best_reading: str
    worst: Estimate  # and its dearest
    worst_reading: str
    robust_differs: bool
    robust_reading: str
    robust_worst: Estimate
    robust_costs: tuple[tuple[str, Estimate], ...]  # the route with the smallest worst case, its cost at each reading (only when it differs)
    lower: Estimate
    upper: Estimate
    proven_optimal: bool
    baseline: Estimate | None  # the best route without recombinators, None when the answer has no comparison route
    recombinations: Estimate | None  # the expected number of recombinations of the plan at the plan reading
    combines: tuple[CombineRow, ...]
    prices: tuple[PriceLine, ...]
    cost_rule_mean: tuple[Estimate, Estimate] | None  # the plan's mean with every combine at the low and at the high end of the cost rule
    approximate_inputs: tuple[ApproximateInput, ...]

    @property
    def gap(self) -> float:
        return 0.0 if self.upper.value == self.lower.value else self.upper.value - self.lower.value

    # --- text and page: the same facts as ordered (label, lines) ----------------------------------------------

    def facts(self, divine: float) -> list[tuple[str, list[str]]]:
        """The answer as ordered `(label, lines)`: the text report prints them, the route page draws them as fields."""
        names = ", ".join(AXIS_WORDS.get(axis, axis) for axis in self.axes)
        grid = ", ".join(row.reading for row in self.rows)
        out: list[tuple[str, list[str]]] = [
            ("Rule axis", [f"{names}; the plan is made at {self.plan_reading}; the grid is {grid}"]),
            ("Plan", [f"{money(self.plan.value)} Chaos ({self.plan.value / divine:.3g} Divine) at {self.plan_reading}"]),
        ]
        if self.best.value == self.worst.value:
            spread = [f"{money(self.best.value)} Chaos: the plan costs the same at every reading of the grid"]
        else:
            spread = [
                f"{money(self.best.value)} to {money(self.worst.value)} Chaos over the grid "
                f"(cheapest at {self.best_reading}, dearest at {self.worst_reading})"
            ]
        for row in self.rows:
            best = "" if row.best_cost is None else f"; the best route for it costs {money(row.best_cost.value)}"
            spread.append(f"{row.reading}: the plan costs {money(row.plan_cost.value)}{best}")
        spread.append(FORMAT_NOTE)
        out.append(("Interval", spread))
        if self.baseline is not None:
            out.append(("Without recombinators", self._baseline_lines()))
        out.append(("Smallest worst case", self._robust_lines()))
        out.append(("Bracket", self._bracket_lines()))
        if self.recombinations is not None:
            out.append(("Recombinations", self._combine_lines()))
            out.append(("Dust and Gold prices", self._price_lines()))
        return out

    def _baseline_lines(self) -> list[str]:
        assert self.baseline is not None
        if math.isinf(self.baseline.value):
            return ["no route without recombinators reaches the goal"]
        low = min(row.plan_cost.value for row in self.rows) - self.baseline.value
        high = max(row.plan_cost.value for row in self.rows) - self.baseline.value
        lines = [
            f"{money(self.baseline.value)} Chaos: the best route that uses none",
            f"plan minus this route: {low:+,.2f} to {high:+,.2f} Chaos over the grid (below 0 the plan is cheaper)",
        ]
        if self.cost_rule_mean is not None and self.cost_rule_mean[1].value > self.baseline.value >= self.plan.value:
            lines.append(
                f"the cost of a recombination is approximate too: at the high end of its reports the plan costs "
                f"{money(self.cost_rule_mean[1].value)} Chaos at {self.plan_reading}, more than this route"
            )
        return lines

    def _robust_lines(self) -> list[str]:
        if not self.robust_differs:
            return [f"the plan itself (worst case {money(self.robust_worst.value)} Chaos, at {self.worst_reading})"]
        lines = [
            f"the route made for {self.robust_reading}: worst case {money(self.robust_worst.value)} Chaos against the plan's {money(self.worst.value)}",
            "it is not the plan: the plan is the cheapest at " + self.plan_reading + "; this route is the safer one",
        ]
        lines += [f"{reading}: {money(cost.value)}" for reading, cost in self.robust_costs]
        return lines

    def _bracket_lines(self) -> list[str]:
        if self.proven_optimal:
            return [f"the smallest worst case any route can have is {money(self.upper.value)} Chaos: the route above reaches it (over the grid)"]
        return [
            f"the smallest worst case any route can have lies between {money(self.lower.value)} and {money(self.upper.value)} Chaos "
            f"(gap {money(self.gap)}, over the grid); the route above reaches the upper figure"
        ]

    def _combine_lines(self) -> list[str]:
        assert self.recombinations is not None
        uses = self.recombinations
        lines = [f"{uses.value:,.2f} expected for the plan at {self.plan_reading}" + self._certified(uses)]
        for row in self.combines:
            goods = " + ".join(f"{count:,} {name}" for name, count in row.resources)
            lines.append(
                f"{row.label}: {row.uses.value:,.2f} uses, {goods} = {money(row.chaos)} Chaos each "
                f"({money(row.chaos_low)} to {money(row.chaos_high)} on the intervals of the cost rule)"
            )
        if self.cost_rule_mean is not None:
            low, high = self.cost_rule_mean
            lines.append(
                f"same route, cost rule at its low end: mean {money(low.value)} Chaos; at its high end: {money(high.value)} Chaos"
            )
        return lines

    @staticmethod
    def _certified(estimate: Estimate) -> str:
        if estimate.high - estimate.low > 1e-6 * max(1.0, abs(estimate.value)):
            return f" (between {estimate.low:,.2f} and {estimate.high:,.2f})"
        return ""

    def _price_lines(self) -> list[str]:
        lines = []
        for price in self.prices:
            if price.name == DUST and price.chaos_each <= 1:
                words = f"{number_text(round(1 / price.chaos_each))} per Chaos Orb"
            elif price.name == GOLD and price.chaos_each * 1_000_000 >= 1:
                words = f"{number_text(price.chaos_each * 1_000_000)} Chaos Orbs per million"
            else:
                words = f"{price.chaos_each:g} Chaos Orbs each"
            lines.append(f"{price.name} at {words} [{price.source}]")
        if any(price.source == "default" for price in self.prices):
            lines.append("a default price is a guess, not a market price: set yours with a hand price in price_overrides.toml")
        return lines

    def text_lines(self, divine: float) -> list[str]:
        """The block of the text report (ASCII only): a heading, then each fact as `label: first line` and its further lines indented."""
        lines = ["Plan and its interval (start item included, costs in Chaos):"]
        for label, body in self.facts(divine):
            lines.append(f"  {label}: {body[0]}")
            lines.extend(f"      {line}" for line in body[1:])
        return lines

    # --- JSON ------------------------------------------------------------------------------------------------

    def document(self) -> dict:
        """The JSON `interval` block; costs in Chaos with the start item, `null` for infinity."""

        def est(e: Estimate) -> dict:
            return {"value": _number(e.value), "low": _number(e.low), "high": _number(e.high)}

        return {
            "rule_axes": [{"axis": axis, "words": AXIS_WORDS.get(axis, axis)} for axis in self.axes],
            "plan_reading": self.plan_reading,
            "readings": [
                {"reading": row.reading, "plan_cost": est(row.plan_cost), "best_route_cost": None if row.best_cost is None else est(row.best_cost)}
                for row in self.rows
            ],
            "plan_cost": est(self.plan),
            "plan_interval": {
                "best": est(self.best),
                "best_reading": self.best_reading,
                "worst": est(self.worst),
                "worst_reading": self.worst_reading,
                "note": FORMAT_NOTE,
            },
            "without_recombinators": None if self.baseline is None else est(self.baseline),
            "smallest_worst_case": {
                "differs_from_plan": self.robust_differs,
                "reading": self.robust_reading,
                "worst": est(self.robust_worst),
                "cost_by_reading": [{"reading": reading, "cost": est(cost)} for reading, cost in self.robust_costs],
            },
            "bracket": {
                "lower": est(self.lower),
                "upper": est(self.upper),
                "gap": _number(self.gap),
                "proven_optimal": self.proven_optimal,
            },
            "recombinations": None
            if self.recombinations is None
            else {
                "expected": est(self.recombinations),
                "at_reading": self.plan_reading,
                "by_action": [
                    {
                        "action": row.label,
                        "expected_uses": est(row.uses),
                        "resources": [{"name": name, "count": count} for name, count in row.resources],
                        "chaos_each": row.chaos,
                        "chaos_each_low": row.chaos_low,
                        "chaos_each_high": row.chaos_high,
                    }
                    for row in self.combines
                ],
                "mean_cost_at_cost_rule_low": None if self.cost_rule_mean is None else est(self.cost_rule_mean[0]),
                "mean_cost_at_cost_rule_high": None if self.cost_rule_mean is None else est(self.cost_rule_mean[1]),
                "prices": [{"name": p.name, "chaos_each": p.chaos_each, "source": p.source} for p in self.prices],
            },
        }


# --- building it from the interval driver's result ---------------------------------------------------------------------


def _walk[S](policy: Mapping[S, Action[S]], start: S, is_goal: Callable[[S], bool]) -> list[Action[S]]:
    """The actions `policy` takes in the states it reaches from `start`, following outcomes and the states of inputs alike."""
    actions: list[Action[S]] = []
    seen = {start}
    stack = [start]
    while stack:
        state = stack.pop()
        if is_goal(state):
            continue
        action = policy.get(state)
        if action is None:
            continue
        actions.append(action)
        targets = [t for t, weight in action.outcomes if weight > 0]
        for target in (*targets, *getattr(action, "extra_inputs", ())):
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return actions


def _unit_prices(parts: Iterable[tuple[str, int, float, str]]) -> dict[str, tuple[float, str]]:
    return {name: (chaos / count, source) for name, count, chaos, source in parts if count}


def build_interval_answer[S, R: Hashable](
    result: IntervalReport[S, R],
    plan: Plan,
    data: GameData,
    *,
    start: S,
    is_goal: Callable[[S], bool],
    shift: float | None = None,
    label: Callable[[R, frozenset[str] | None], str] = reading_text,
) -> IntervalAnswer | None:
    """Word the result of `risk.solve_readings` for `plan`'s prices and offers; None when the plan reads no rule axis.

    `result` is the driver's report on a model made of `plan`'s offers; `start` and `is_goal` are the model's (an `Acquisition`'s
    `start(item)` and `is_goal`). The plan's route is walked through its outcomes and its inputs; the answer is None, and so says nothing
    of any axis, when no action of it reads one (`Offer.axes`). `shift` is the start item's price (default the plan's), added to every total
    like the policy's own. `label` words a reading (`reading_text` by default); it gets the set of axis ids the plan reads.
    """
    shift = plan.start_price.chaos if shift is None else shift

    def is_combine(action: Action) -> bool:
        # a recombination is an action that prices itself on an interval (`resource_bounds`): the contract has no class to test for
        return hasattr(plan.offer_of(action).offer.action, "resource_bounds")

    plan_actions = _walk(result.plan.policy, start, is_goal)
    used = frozenset(axis.name for action in plan_actions for axis in plan.offer_of(action).offer.axes)
    if not used:
        return None
    robust_actions = _walk(result.robust.policy, start, is_goal) if result.robust_differs else []
    baseline_actions = _walk(result.baseline.policy, start, is_goal) if result.baseline is not None else []
    used |= frozenset(axis.name for action in robust_actions for axis in plan.offer_of(action).offer.axes)

    def shifted(e: Estimate) -> Estimate:
        return Estimate(e.value + shift, e.low + shift, e.high + shift)

    def named(reading: R) -> str:
        return label(reading, used)

    # readings that differ only in an axis the plan does not read are one row (the plan costs the same in each)
    groups: dict[str, list[R]] = {}
    for reading in _grid_order(result.readings):
        groups.setdefault(named(reading), []).append(reading)
    plan_row = result.plan.costs
    rows = tuple(
        ReadingRow(
            name,
            shifted(plan_row[members[0]]),
            shifted(result.values[members[0]]) if len(members) == 1 else None,
        )
        for name, members in groups.items()
    )
    plan_reading = named(result.plan.reading)

    combine_labels = {a.label for a in plan_actions if is_combine(a)}

    recombinations = None
    combines: list[CombineRow] = []
    prices: dict[str, PriceLine] = {}
    cost_rule_mean = None
    if combine_labels:
        recombinations = expected_total(result.plan.policy, start, is_goal, lambda a: 1.0 if is_combine(a) else 0.0)
        points: dict[str, tuple[float, float]] = {}  # label -> (chaos at the low end, chaos at the high end) of one use
        for name in sorted(combine_labels):
            priced = plan.offer_of(next(a for a in plan_actions if a.label == name))
            action = priced.offer.action
            units = _unit_prices(priced.parts)
            low_goods, high_goods = action.resource_bounds(data)  # type: ignore[attr-defined]
            low = sum(count * units[good][0] for good, count in low_goods.items() if good in units)
            high = sum(count * units[good][0] for good, count in high_goods.items() if good in units)
            points[name] = (min(low, priced.cost), max(high, priced.cost))
            uses = expected_total(result.plan.policy, start, is_goal, lambda a, n=name: 1.0 if a.label == n else 0.0)
            goods = tuple((good, count) for good, count, _, _ in priced.parts if count)
            combines.append(CombineRow(priced.label, uses, goods, priced.cost, *points[name]))
            for good in (DUST, GOLD):
                if good in units and good not in prices:
                    prices[good] = PriceLine(good, units[good][0], units[good][1])
        below = expected_total(
            result.plan.policy, start, is_goal,
            lambda a: plan.offer_of(a).cost - points[a.label][0] if a.label in points else 0.0,
        )  # fmt: skip
        above = expected_total(
            result.plan.policy, start, is_goal,
            lambda a: points[a.label][1] - plan.offer_of(a).cost if a.label in points else 0.0,
        )  # fmt: skip
        mean = shifted(result.plan.costs[result.plan.reading])
        cost_rule_mean = (
            Estimate(mean.value - below.value, mean.low - below.high, mean.high - below.low),
            Estimate(mean.value + above.value, mean.low + above.low, mean.high + above.high),
        )

    actions = [*plan_actions, *robust_actions, *baseline_actions]
    return IntervalAnswer(
        axes=tuple(sorted(used)),
        plan_reading=plan_reading,
        rows=rows,
        plan=shifted(result.plan.costs[result.plan.reading]),
        best=shifted(result.plan.best),
        best_reading=named(result.plan.best_reading),
        worst=shifted(result.plan.worst),
        worst_reading=named(result.plan.worst_reading),
        robust_differs=result.robust_differs,
        robust_reading=named(result.robust.reading),
        robust_worst=shifted(result.robust.worst),
        robust_costs=_robust_costs(result.robust, named, shifted) if result.robust_differs else (),
        lower=shifted(result.lower),
        upper=shifted(result.upper),
        proven_optimal=result.proven_optimal,
        baseline=None if result.baseline is None else shifted(result.baseline.value),
        recombinations=recombinations,
        combines=tuple(combines),
        prices=tuple(prices.values()),
        cost_rule_mean=cost_rule_mean,
        approximate_inputs=approximate_inputs_of(plan, actions, data),
    )


def _grid_order[R: Hashable](readings: Iterable[R]) -> list[R]:
    """The readings in the order of their values (the grid from the least exponent up), the plan reading not first; as given when they cannot be compared."""
    found = list(readings)
    try:
        return sorted(found, key=lambda r: getattr(r, "values", r))
    except TypeError:
        return found


def _robust_costs(route: Route, named: Callable, shifted: Callable) -> tuple[tuple[str, Estimate], ...]:
    seen: dict[str, Estimate] = {}
    for reading in _grid_order(route.costs):
        seen.setdefault(named(reading), shifted(route.costs[reading]))
    return tuple(seen.items())
