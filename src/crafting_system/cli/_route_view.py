"""The route view (ticket #78): a plan or a given route as the model of one HTML page.

`route_input(plan)` and `given_route_input(plan, route, result)` say what is drawn: the planner's own
policy, or a given route evaluated as a fixed policy. `build_section(inp, data, buy)` turns one of them
into a `RouteSection` (a goal card on top, then one row per step: the step card and the item card of the
state after it); `write_route_page(...)` builds the sections, renders them with `_route_html.render_page`
and writes the file. The model is plain frozen dataclasses so tests read it directly.

Rows. Row 1 is always the start: a buy of the start item (its trade search link when a buy spec is
given). The other rows are the steps of `_route_flow.build_flow` over the policy: a step stands for
compressed states only when the policy takes the same action in all of them and they lead on with the
same chances, so look-alike states that need different actions are different rows. Row number = flow
step number + 1. A step's card has these fields in this order, one that does not apply left out: Goal,
Accepts, Trade, Chance per use, Cost per use, Uses on average, Step cost, On failure. Chances only,
never how a mechanic works. A step with no action (the dead end of a policy, the gap of a given route)
is a row titled "No action" that says why.

Words about the item come from the compressed states of the step's outcomes: a requirement leaf that
becomes met, a mod fractured, crafted mods added or removed. When no such difference tells two outcomes
apart the line names the row the outcome leads to instead ("the item of step 4").

Numbers: money is `≈ 12 c` (3 significant digits, thousands commas, `≈` only when rounded), chances
`37%`, `≈4.3%`, `0.093%`, uses `≈ 1.1`. A route that never finishes has no cost numbers at all.

The step cost of a row is uses x cost per use, so the buy plus the step costs add up to the risk run's
mean plus the start price (`StepRow.cost` holds the number for a test). Reaches into
`_route_card._StateReader` for the text of a goal leaf, and into the plan's abstraction only through
what `_route_card` already reads.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from crafting_system.abstraction import CompressedState, Status
from crafting_system.actions import ApplyEssence, BenchCraft, ChaosOrb, RemoveCraftedMods
from crafting_system.data import GameData
from crafting_system.prices import BuySpec
from crafting_system.prices.trade_stats import TradeStats, parse_trade_stats
from crafting_system.risk import RiskReport
from crafting_system.solver import Action

from ._plan import Plan
from ._report import Report
from ._route import RESTART, Route, RouteResult
from ._route_card import ItemCard, _StateReader, card_of_item, card_of_states, card_of_target, mod_text
from ._route_flow import Edge, Step, build_flow
from ._route_html import render_page
from ._route_trade import BuyStep, buy_step

PLANNER_LABEL = "Cheapest policy of the planner"
NEVER_FINISHES = "never finishes from here"
GAPS = "never finishes: the route has gaps"

# --- the model of the page -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """One entry of a field. With `href` the line is a link: all of `text`, or, when `anchor` is set, that
    trailing part (`text` then a space and `anchor` as the link)."""

    text: str
    href: str | None = None
    anchor: str = ""


@dataclass(frozen=True)
class Field:
    """A labelled field of a card; `tone` "warn" draws it in the warning colour."""

    label: str
    lines: tuple[Line, ...]
    tone: str = ""


@dataclass(frozen=True)
class StepRow:
    """One row: the step card (title, fields) and the item card after the step.

    `final` marks a row whose step can end in the target; `cost` is the step cost in Chaos (None when
    the step has none: no action, or it never finishes).
    """

    number: int
    title: str
    fields: tuple[Field, ...]
    after: ItemCard
    anchor: str
    final: bool = False
    cost: float | None = None


@dataclass(frozen=True)
class GoalCard:
    fields: tuple[Field, ...]
    target: ItemCard


@dataclass(frozen=True)
class RouteSection:
    title: str
    goal: GoalCard
    rows: tuple[StepRow, ...]
    anchor: str = "route"


@dataclass(frozen=True)
class Page:
    title: str
    sections: tuple[RouteSection, ...]


# --- what is drawn -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteInput:
    """What one drawn route needs: its policy, the risk of that policy and why some states have no action."""

    label: str
    plan: Plan
    policy: Mapping[CompressedState, Action[CompressedState]]
    risk: RiskReport
    reasons: Mapping[CompressedState, str] = field(default_factory=dict)


def route_input(plan: Plan) -> RouteInput:
    """The planner's own policy."""
    return RouteInput(PLANNER_LABEL, plan, plan.policy, plan.risk)


def given_route_input(plan: Plan, route: Route, result: RouteResult) -> RouteInput:
    """A given route as a fixed policy; its gaps are states with no action and a reason."""
    name = route.name or Path(route.source).name
    reasons = {gap.state: gap.reason for gap in result.gaps}
    return RouteInput(f"Given route: {name}", plan, result.policy, result.risk, reasons)


# --- numbers -----------------------------------------------------------------------------------------------


def _significant(value: float, digits: int) -> tuple[str, bool]:
    """`value` to `digits` significant digits with thousands commas, and whether that is exact."""
    if value == 0:
        return "0", True
    rounded = float(f"{value:.{digits}g}")
    decimals = max(0, digits - 1 - math.floor(math.log10(abs(rounded))))
    text = f"{rounded:,.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text, math.isclose(rounded, value, rel_tol=1e-9)


def money(chaos: float) -> str:
    text, exact = _significant(chaos, 3)
    return f"{'' if exact else '≈ '}{text} c"


def count(value: float) -> str:
    text, exact = _significant(value, 3)
    return f"{'' if exact else '≈ '}{text}"


def chance_text(chance: float) -> str:
    if chance >= 1 - 1e-12:
        return "100%"
    percent = chance * 100
    if percent < 0.001:
        return "< 0.001%"
    if percent >= 99.95:
        return "> 99.9%"
    text, exact = _significant(percent, 3 if percent >= 99 else 2)
    return f"{'' if exact else '≈'}{text}%"


def _divine(chaos: float, chaos_per_divine: float) -> str:
    text, _ = _significant(chaos / chaos_per_divine, 2)
    return f"{text} Divine"


# --- the lines of a card -------------------------------------------------------------------------------------


def _plain(label: str, *texts: str, tone: str = "") -> Field | None:
    return Field(label, tuple(Line(text) for text in texts), tone) if texts else None


def _fields(*candidates: Field | None) -> tuple[Field, ...]:
    return tuple(candidate for candidate in candidates if candidate is not None)


class _View:
    """What the rows of one section share: the plan, the data, the flow and the anchors."""

    def __init__(self, inp: RouteInput, data: GameData, buy: BuyStep | None, prefix: str) -> None:
        self.inp, self.plan, self.data, self.buy, self.prefix = inp, inp.plan, data, buy, prefix
        self.ab = self.plan.abstraction
        self.reader = _StateReader(self.ab)
        self.flow = build_flow(self.plan.start, inp.policy, self.ab.is_goal, inp.reasons)

    # -- anchors and links ---------------------------------------------------------------------------------

    def anchor(self, number: int) -> str:
        return f"{self.prefix}s{number}"

    def link(self, text: str, number: int, below: int | None, *, always: bool = False) -> Line:
        """`text` with a link to row `number`; the arrow is left out when that row is right below row `below`."""
        href = f"#{self.anchor(number)}"
        if always:
            return Line(text, href)
        return Line(text) if number == below else Line(text, href, f"→ step {number}")

    # -- what changes ----------------------------------------------------------------------------------------

    def leaf_text(self, index: int) -> str:
        try:
            _, text, note = self.reader.leaf(index)
        except ValueError:
            return self.plan.leaf_labels[index]
        return f"{text} ({note})" if note else text

    def _passing(self, states) -> set[int]:
        return {i for state in states for i, status in enumerate(state.status) if status is Status.PASSING}

    def _fractured(self, state: CompressedState) -> set[str]:
        return {entry.mod_id for entry in state.fractured}

    def _crafted(self, state: CompressedState) -> set[str]:
        return {slot.kind for slot in state.slots if slot.crafted}

    def _mod(self, mod_id: str) -> str:
        return mod_text(self.data.mods[mod_id])

    def gains(self, step: Step, edges: list[Edge]) -> list[str]:
        """What a step makes true in the states its forward edges lead to (a leaf met, a mod fractured or crafted)."""
        landing = [state for edge in edges for state in edge.states]
        if not landing:
            return []
        before_passing = self._passing(step.states)
        before_fractured = set().union(*(self._fractured(state) for state in step.states))
        before_crafted = set().union(*(self._crafted(state) for state in step.states))
        mods, explained = [], set()  # a new fractured or crafted mod, and the leaves it meets (named once, as the mod)
        for state in landing:
            for entry in state.fractured:
                if entry.mod_id not in before_fractured:
                    mods.append(f"{self._mod(entry.mod_id)} (fractured)")
                    explained |= {i for i, status in enumerate(entry.contribution) if status is Status.PASSING}
            for slot in state.slots:
                if slot.crafted and slot.kind not in before_crafted:
                    mods.append(f"{self._mod(slot.kind)} (crafted)")
                    explained |= {i for i, status in enumerate(slot.contribution) if status is Status.PASSING}
        found = [
            self.leaf_text(i)
            for i in range(len(self.plan.leaf_labels))
            if i not in before_passing
            and i not in explained
            and any(state.status[i] is Status.PASSING for state in landing)
        ]
        found += mods
        if before_crafted and all(not self._crafted(state) for state in landing):
            found.append("crafted mods removed")
        if all(state.flags.rarity.value == "normal" for state in step.states) and any(
            state.flags.rarity.value != "normal" for state in landing
        ):
            found.append("a rare item")
        return list(dict.fromkeys(found))

    def lost(self, step: Step, edge: Edge) -> list[str]:
        """What the states of a failure edge no longer have: a leaf every state of the step met, crafted mods."""
        found = []
        for i in range(len(self.plan.leaf_labels)):
            if all(state.status[i] is Status.PASSING for state in step.states) and not any(
                state.status[i] is Status.PASSING for state in edge.states
            ):
                found.append(f"{self.leaf_text(i)} lost")
        if any(self._crafted(state) for state in step.states) and all(not self._crafted(state) for state in edge.states):
            found.append("crafted mods removed")
        return found

    def appeared(self, step: Step, edge: Edge) -> list[str]:
        """What every state of a forward edge has that no state of the step has (a leaf met, a mod fractured or crafted)."""
        before = self._passing(step.states)
        found = [
            self.leaf_text(i)
            for i in range(len(self.plan.leaf_labels))
            if i not in before and all(state.status[i] is Status.PASSING for state in edge.states)
        ]
        shared_fractured = set.intersection(*(self._fractured(state) for state in edge.states))
        shared_crafted = set.intersection(*(self._crafted(state) for state in edge.states))
        before_fractured = set().union(*(self._fractured(state) for state in step.states))
        before_crafted = set().union(*(self._crafted(state) for state in step.states))
        found += [f"{self._mod(mod_id)} fractured" for mod_id in sorted(shared_fractured - before_fractured)]
        found += [f"{self._mod(mod_id)} crafted" for mod_id in sorted(shared_crafted - before_crafted)]
        return found

    # -- the fields of a step ----------------------------------------------------------------------------------

    def chance_lines(self, step: Step, action: Action, forward: list[Edge], below: int) -> list[Line]:
        random = sum(1 for outcome in action.outcomes if outcome.weight > 0) > 1
        if len(forward) == 1 and not random:
            return []
        if len(forward) == 1:
            return [Line(chance_text(forward[0].chance))]
        lines = []
        for edge in forward:
            if edge.kind == "goal" or edge.to is None:
                lines.append(Line(f"the target: {chance_text(edge.chance)}"))
                continue
            number = edge.to + 1
            what = self.appeared(step, edge)
            if what:
                lines.append(self.link(f"{' and '.join(what)}: {chance_text(edge.chance)}", number, below))
            else:
                lines.append(self.link(f"the item of step {number}: {chance_text(edge.chance)}", number, below, always=True))
        return lines

    def failure_lines(self, step: Step, failing: list[Edge], below: int) -> list[Line]:
        lines = []
        for edge in failing:
            if edge.kind == "again" or edge.to is None:
                lines.append(Line(f"nothing gained ({chance_text(edge.chance)}): this step again"))
                continue
            number = edge.to + 1
            what = self.lost(step, edge)
            if step.action is not None and step.action.label == RESTART:
                lines.append(self.link(f"the start item bought again ({chance_text(edge.chance)})", number, None))
            elif what:
                lines.append(self.link(f"{' and '.join(what)} ({chance_text(edge.chance)})", number, None))
            else:
                lines.append(self.link(f"the item of step {number} ({chance_text(edge.chance)})", number, None, always=True))
        return lines

    def cost_lines(self, action: Action) -> list[str]:
        if action.label == RESTART:
            return [money(self.plan.start_price.chaos)]
        priced = self.plan.offer_of(action)
        lines = [f"{count_} × {name} {money(chaos)}" for name, count_, chaos, _ in priced.parts]
        if len(priced.parts) > 1:
            lines.append(f"total {money(priced.cost)}")
        return lines

    def title(self, action: Action) -> str:
        if action.label == RESTART:
            name = self.plan.start_price.name
            return f"Restart: buy {name} again" if name else "Restart: buy the start item again"
        offer = self.plan.offer_of(action).offer
        match offer.action:
            case ChaosOrb():
                return "Chaos Orb"
            case ApplyEssence(name=name):
                return name
            case BenchCraft(mod_id=mod_id):
                return f"Benchcraft: {self._mod(mod_id)}"
            case RemoveCraftedMods():
                return "Benchcraft: Remove Crafted Mods"
            case _:
                return offer.label

    def trade_field(self) -> Field | None:
        if self.buy is None:
            return None
        lines = [Line("Search on the trade site", self.buy.url)]
        lines += [Line(f"not in the link: {mod}") for mod in self.buy.unresolved]
        return Field("Trade", tuple(lines))

    # -- the rows ------------------------------------------------------------------------------------------------

    def start_accepts(self) -> list[str]:
        """What the buy takes: the buy spec's filter, else the start item as the target file gives it."""
        if self.buy is not None:
            return list(self.buy.accepts)
        card = card_of_item(self.data, self.plan.target.start_item)
        lines = list(card.properties)
        for slot in (*card.prefixes, *card.suffixes):
            if slot.tone in ("mod", "crafted", "wanted"):
                lines.append(f"fractured: {slot.text}" if "fractured" in slot.marks else slot.text)
        return lines

    def buy_row(self, final: bool) -> StepRow:
        price = self.plan.start_price
        cost = [money(price.chaos)] if price.chaos > 0 else ["free"]
        fields = _fields(
            _plain("Accepts", *self.start_accepts()),
            self.trade_field(),
            _plain("Cost per use", *cost),
            _plain("Step cost", money(price.chaos)) if price.chaos > 0 else None,
        )
        title = f"Buy {price.name}" if price.name else "Start item"
        after = card_of_item(self.data, self.plan.target.start_item)
        return StepRow(1, title, fields, after, self.anchor(1), final, price.chaos)

    def step_row(self, step: Step) -> StepRow:
        number = step.number + 1
        action = step.action
        if action is None:
            fields = _fields(_plain("Why", step.reason or "no action is available here"))
            return StepRow(number, "No action", fields, card_of_states(self.ab, step.states), self.anchor(number))
        forward = [edge for edge in step.edges if edge.kind in ("next", "goal")]
        failing = [edge for edge in step.edges if edge.kind in ("again", "back")]
        restart = action.label == RESTART
        goal = self.gains(step, forward)
        if not goal and any(edge.kind == "goal" for edge in forward):
            goal = ["the target"]
        never = step.uses is not None and math.isinf(step.uses)
        step_cost = None if step.uses is None or never else step.uses * action.cost
        uses = [NEVER_FINISHES] if never else [] if step.uses is None else [count(step.uses)]
        if uses and not never and step.reached is not None and step.reached < 0.9995:
            uses[0] += f" (reached in {chance_text(step.reached)} of runs)"
        chances = self.chance_lines(step, action, forward, number + 1)
        fields = _fields(
            _plain("Goal", *goal),
            self.trade_field() if restart else None,
            Field("Chance per use", tuple(chances)) if chances else None,
            _plain("Cost per use", *self.cost_lines(action)),
            _plain("Uses on average", *uses),
            _plain("Step cost", money(step_cost)) if step_cost is not None else None,
            Field("On failure", tuple(self.failure_lines(step, failing, number + 1)), "warn") if failing else None,
        )
        if restart:
            after = card_of_item(self.data, self.plan.target.start_item)
        else:
            landing = [state for edge in (forward or step.edges) for state in edge.states]
            after = card_of_states(self.ab, list(dict.fromkeys(landing)))
        final = any(edge.kind == "goal" for edge in step.edges)
        return StepRow(number, self.title(action), fields, after, self.anchor(number), final, step_cost)

    def goal_card(self) -> GoalCard:
        plan, risk = self.plan, self.inp.risk
        shift, divine = plan.start_price.chaos, plan.prices.chaos_per_divine

        def total(value: float) -> str:
            return f"{money(value + shift)} ({_divine(value + shift, divine)})"

        mean = total(risk.mean.value) if math.isfinite(risk.mean.value) else GAPS
        p90 = f"≤ {total(risk.p90.value)}" if math.isfinite(risk.p90.value) else "no finish in 9 runs of 10"
        success = risk.success_probability.value
        fields = _fields(
            _plain("Route", self.inp.label),
            _plain("Mean", mean),
            _plain("9 runs in 10", p90),
            _plain("Success chance", chance_text(success)) if success < 1 - 1e-9 else None,
            _plain("Prices", f"league {plan.prices.league}, fetched {plan.prices.fetched_at:%Y-%m-%d}"),
        )
        return GoalCard(fields, card_of_target(self.data, plan.target))


def build_section(
    inp: RouteInput, data: GameData, buy: BuyStep | None = None, *, prefix: str = "", anchor: str = "route"
) -> RouteSection:
    """The goal card and the rows of one route; `prefix` goes before the row anchors (`s2` becomes `<prefix>s2`)."""
    view = _View(inp, data, buy, prefix)
    rows = [view.buy_row(final=not view.flow.steps)]
    rows += [view.step_row(step) for step in view.flow.steps]
    return RouteSection(inp.label, view.goal_card(), tuple(rows), anchor)


# --- the page ------------------------------------------------------------------------------------------------


def _trade_stats(cache_dir: Path | None) -> TradeStats | None:
    """The trade site's stat list from the cache the prices code keeps, None when it is not there or unreadable."""
    if cache_dir is None:
        return None
    try:
        document = json.loads((cache_dir / "trade" / "stats.json").read_text(encoding="utf-8"))
        return parse_trade_stats(document.get("stats"))
    except (OSError, ValueError, AttributeError):
        return None


def write_route_page(
    path: Path,
    report: Report,
    data: GameData,
    *,
    route: Route | None = None,
    given: RouteResult | None = None,
    buy_spec: BuySpec | None = None,
    cache_dir: Path | None = None,
    target_name: str = "",
) -> Path:
    """Write the route view of `report`'s plan to `path` (and of the given route, stacked below) and return `path`.

    The page makes no request: the trade link is built from `buy_spec` and the stat list in
    `<cache_dir>/trade/stats.json` when that exists.
    """
    plan = report.plan
    buy = None
    if buy_spec is not None:
        searchable = [mod for mod in data.mods.values() if mod.text]  # a mod with no text (a veiled one) cannot be searched by
        buy = buy_step(buy_spec, plan.prices.league, searchable, _trade_stats(cache_dir))
    sections = [build_section(route_input(plan), data, buy, anchor="policy")]
    if route is not None and given is not None:
        sections.append(build_section(given_route_input(plan, route, given), data, buy, prefix="g-", anchor="given"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_page(Page(target_name or "Route view", tuple(sections))), encoding="utf-8")
    return path
