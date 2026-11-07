"""The route view (ticket #78): a plan or a given route as the model of one HTML page.

`route_input(plan)` and `given_route_input(plan, route, result)` say what is drawn: the planner's own
policy, or a given route evaluated as a fixed policy. `build_section(inp, data, buy)` turns one of them
into a `RouteSection` (a goal card on top, then one row per step: the step card and the item card of the
state after it); `write_route_page(...)` builds the sections, renders them with `_route_html.render_page`
and writes the file. The model is plain frozen dataclasses so tests read it directly.

Rows. Row 1 is always the start: a buy of the start item (its trade search link when a buy spec is
given). The other rows are the steps of `_route_flow.build_flow` over the policy: one row per player action
(OR-18), the states on which the policy takes the same action, whatever their chances. Row number = flow
step number + 1. A step's card has these fields in this order, one that does not apply left out: Goal,
Accepts, Trade, Chance per use, Tier chances, Cost per use, Uses on average, Step cost, On failure. Chances
only, never how a mechanic works. A step with no action (the dead end of a policy, the gap of a given route)
is a row titled "No action" that says why.

The states of a row are item states. A plan shown by its lumped chain (R04, R14) still has its rows made from the item states of
its policy (`RouteInput.chain`, `_route_chain`), never from the shown member of a block: what a row says of an item (a mod lost, the
tiers a draw can add) is a fact about items, and a block's members can differ in it.

The chances of a row are the exact mixture of those of its states (OR-20): the sum over the states of (expected
visits x chance) over the expected visits of the row (`_route_flow`). Chance per use lists the outcomes that do not lose
a wanted mod, one line per place they lead to: the target, the same step again ("nothing gained"), another step.
On failure lists the outcomes that lose a wanted mod (a leaf of the target that was met and no longer is), restart the item, or land
in a step that restarts or has no action (PRES-6: never decided by what the item still costs to finish). A branch whose
landing items differ from the card after the step has its own item card under it. Tier chances (OR-31): when the step
can add a mod of a family the target wants, one line per family with the chance of each tier and of none (`_route_tiers`),
mixed the same way. Accepts, on a craft with several outcomes, says how many mods the accepted results may have (when
every mod is tracked) and that the rest is any. A step that cannot reach the target says "never finishes from here" in
place of its uses. An essence of level 5 or more has a last field, Note: it reforges a rare and keeps only the fractured
mod, so no Scouring.

Every mod line has one format, the game's text with its ranges and the tier (`+(100-114) to maximum Life · T1`,
see `_route_card`). The bought start item shows its known mods that way and the rest of a rare as `any mod or
empty`. A given route that does what the planner's policy does is not drawn again (`merge_sections`): the goal
card says so in a line; one that differs is drawn with its differing steps only, linking the shared ones.

Words about the item come from the compressed states of the step's outcomes: a requirement leaf that
becomes met or is lost, a mod fractured, crafted mods added or removed. When no such difference tells two outcomes
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
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from crafting_system.abstraction import CompressedState, Status
from crafting_system.data import GameData
from crafting_system.items import Rarity
from crafting_system.prices import BuySpec
from crafting_system.prices.trade_stats import TradeStats, parse_trade_stats
from crafting_system.risk import RiskReport
from crafting_system.solver import Action
from crafting_system.targets import plain_base_names

from ._interval import IntervalAnswer
from ._limits import SHOWN_LABELS, grouped, limit_text, more_labels
from ._marking import approximate_inputs, approximate_page_line
from ._plan import GIVEN_SOURCE, Plan
from ._report import UNRESOLVED, Report
from ._route import RESTART, Route, RouteResult
from ._route_card import ANY_OR_EMPTY, EMPTY, FAMILY_TYPE_TEXT, ItemCard, _StateReader, card_of_item, card_of_states, card_of_target, mod_text
from ._route_chain import chain_of_packed_policy
from ._route_flow import Chain, Edge, Step, chain_of_policy, flow_limits, flow_of
from ._route_html import render_page
from ._route_tiers import TierLine, tier_lines
from ._route_trade import BuyStep, buy_step
from ._start_step import ROLE_GEMS, FirstStep, first_step

PLANNER_LABEL = "Cheapest policy of the planner"
NEVER_FINISHES = "never finishes from here"
GAPS = "never finishes: the route has gaps"
NEVER = "never finishes"

# --- the model of the page -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """One entry of a field. With `href` the line is a link: all of `text`, or, when `anchor` is set, that
    trailing part (`text` then a space and `anchor` as the link)."""

    text: str
    href: str | None = None
    anchor: str = ""
    more: tuple[str, ...] = ()  # entries the text does not name: the page holds them in a "details" element, closed by default


@dataclass(frozen=True)
class Field:
    """A labelled field of a card; `tone` "warn" draws it in the warning colour."""

    label: str
    lines: tuple[Line, ...]
    tone: str = ""


@dataclass(frozen=True)
class Branch:
    """The item card of one branch of a step, under the card after the step: `caption` says which (its line and chance)."""

    caption: str
    card: ItemCard


@dataclass(frozen=True)
class StepRow:
    """One row: the step card (title, fields) and the item card after the step.

    `final` marks a row whose step can end in the target; `cost` is the step cost in Chaos (None when
    the step has none: no action, or it never finishes). `branches` are the cards of the branches whose landing items differ
    from `after` (only on a step with several branches).
    """

    number: int
    title: str
    fields: tuple[Field, ...]
    after: ItemCard
    anchor: str
    final: bool = False
    cost: float | None = None
    branches: tuple[Branch, ...] = ()


@dataclass(frozen=True)
class GoalCard:
    """The goal card: its fields, the target item, and the section "What this answer leaves out" (one field to a group of limits, OR-13)."""

    fields: tuple[Field, ...]
    target: ItemCard
    leaves_out: tuple[Field, ...] = ()


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
    interval: IntervalAnswer | None = None  # the plan's interval over a rule axis (ticket #221); only the planner's own policy has one
    chain: Chain | None = None  # the policy on item states as arrays, when `policy` is a lumped view (then the rows are made from this, not from the shown members of blocks)


def route_input(plan: Plan, interval: IntervalAnswer | None = None) -> RouteInput:
    """The planner's own policy, with the interval of the plan when the answer read a rule axis.

    A packed plan shown by its lumped chain (`Plan.lumped`) gets the chain of its item states too: the page is made from that.
    """
    chain = chain_of_packed_policy(plan.policy) if plan.lumped else None
    return RouteInput(PLANNER_LABEL, plan, plan.view_policy, plan.risk, interval=interval, chain=chain)


def given_route_input(plan: Plan, route: Route, result: RouteResult) -> RouteInput:
    """A given route as a fixed policy; its gaps are states with no action and a reason."""
    name = route.name or Path(route.source).name
    reasons = {gap.state: gap.reason for gap in result.gaps}
    return RouteInput(f"Given route: {name}", plan, result.policy, result.risk, reasons, chain=result.chain)


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


def _lost_leaves(chain: Chain, src: np.ndarray, dst: np.ndarray) -> tuple[range, np.ndarray]:
    """For each edge `src -> dst` of the chain (item states), which leaves of the target the use stops meeting: the wanted mods it loses.

    A leaf is lost on an edge when the item before has it met (PASSING) and the item after has not. Read on item states, so an Augmentation
    never loses one and a Remove Crafted Mods loses only what a crafted mod gave.
    """
    width = len(chain.states[0].status)
    status = np.array([state.status for state in (*chain.states, *chain.goals)], dtype=np.int8).reshape(chain.m + len(chain.goals), width)
    met = int(Status.PASSING)
    return range(status.shape[1]), (status[src] == met) & (status[dst] != met)


class _View:
    """What the rows of one section share: the plan, the data, the flow and the anchors."""

    def __init__(self, inp: RouteInput, data: GameData, buy: BuyStep | None, prefix: str, route_field: bool) -> None:
        self.inp, self.plan, self.data, self.buy, self.prefix = inp, inp.plan, data, buy, prefix
        self.route_field = route_field
        self.ab = self.plan.abstraction
        self.reader = _StateReader(self.ab)
        self.chain = inp.chain if inp.chain is not None else chain_of_policy(self.plan.start, inp.policy, self.ab.is_goal, inp.reasons)
        self.flow = flow_of(self.chain, is_restart=lambda action: action.label == RESTART, loss=_lost_leaves)
        # a start item made at a vendor (ADR-0059): row 1 is the recipe, not a buy
        starts = getattr(self.plan, "starts", None)  # a stand-in plan of a test has none
        self.first: FirstStep | None = None if starts is None else first_step(starts.chosen, data, self.plan.target)

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
        return f"{text} · {note}" if note else text

    def _passing(self, states) -> set[int]:
        return {i for state in states for i, status in enumerate(state.status) if status is Status.PASSING}

    def _passing_in_all(self, states) -> set[int]:
        return {i for i in range(len(self.plan.leaf_labels)) if all(state.status[i] is Status.PASSING for state in states)}

    def _fractured(self, state: CompressedState) -> set[str]:
        return {entry.mod_id for entry in state.fractured}

    def _crafted(self, state: CompressedState) -> set[str]:
        return {slot.kind for slot in state.slots if slot.crafted}

    def _mod(self, mod_id: str) -> str:
        if mod_id not in self.data.mods:  # a fractured mod held as its family type ("~n"), ticket #70
            return FAMILY_TYPE_TEXT
        return mod_text(self.data.mods[mod_id])

    def gains(self, step: Step, edges: list[Edge]) -> list[str]:
        """What a step makes true in the states its forward edges lead to (a leaf met, a mod fractured or crafted).

        A leaf that only some of the step's states already meet still counts: the step aims at it for the others.
        """
        landing = [state for edge in edges for state in edge.states]
        if not landing:
            return []
        before_passing = self._passing_in_all(step.states)
        before_fractured = set().union(*(self._fractured(state) for state in step.states))
        before_crafted = set().union(*(self._crafted(state) for state in step.states))
        mods, explained = [], set()  # a new fractured or crafted mod, and the leaves it meets (named once, as the mod)
        for state in landing:
            for entry in state.fractured:
                if entry.mod_id not in before_fractured:
                    mods.append(f"{self._mod(entry.mod_id)} · fractured")
                    explained |= {i for i, status in enumerate(entry.contribution) if status is Status.PASSING}
            for slot in state.slots:
                if slot.crafted and slot.kind not in before_crafted:
                    mods.append(f"{self._mod(slot.kind)} · crafted")
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

    def lost(self, edge: Edge) -> list[str]:
        """What a failure edge costs the item, in words: the wanted mod its uses lose, or the list of those they may lose."""
        texts = [self.leaf_text(i) for i in edge.lost]
        if len(texts) <= 1:
            return [f"{text} lost" for text in texts]
        return [f"one of these lost: {'; '.join(texts)}"]

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
        found += [f"{self._mod(mod_id)} · fractured" for mod_id in sorted(shared_fractured - before_fractured)]
        found += [f"{self._mod(mod_id)} · crafted" for mod_id in sorted(shared_crafted - before_crafted)]
        return found

    # -- the fields of a step ----------------------------------------------------------------------------------

    def edge_phrase(self, step: Step, edge: Edge) -> tuple[str, bool]:
        """What happens on the item at an edge, in words and without its chance; `True` when the words only name the row it leads to.

        A goal edge is "the target", an edge to the same step is "nothing gained", a failure is the wanted mods a use loses, or
        the restart / the dead end it lands in; any other edge says what every landing item has that the step's items lack.
        """
        if edge.kind == "goal" or edge.to is None:
            return "the target", False
        if edge.kind == "again":
            return "nothing gained, this step again", False
        if edge.kind == "failure":
            if step.action is not None and step.action.label == RESTART:
                return f"the start item {'made again at the vendor' if self.first is not None else 'bought again'}", False
            if lost := self.lost(edge):
                return " and ".join(lost), False
            there = self.flow.steps[edge.to - 1].action  # `edge.to` is a step number (from 1)
            if there is None:
                return "the route has no step for this item", True
            if there.label == RESTART:
                return "the item is restarted", True
        elif appeared := self.appeared(step, edge):
            return " and ".join(appeared), False
        return f"the item of step {edge.to + 1}", True

    def chance_lines(self, step: Step, action: Action, shown: list[Edge], below: int) -> list[Line]:
        """One line per place the outcomes that lose no wanted mod lead to, with the exact mixture of their chances."""
        random = sum(1 for outcome in action.outcomes if outcome.weight > 0) > 1
        if len(shown) == 1 and not random:
            return []
        if len(shown) == 1:
            return [Line(chance_text(shown[0].chance))]
        lines = []
        for edge, (what, names_row) in zip(shown, self.phrases(step, shown)):
            text = f"{what}: {chance_text(edge.chance)}"
            lines.append(Line(text) if edge.kind in ("goal", "again") else self.link(text, edge.to + 1, below, always=names_row))
        return lines

    def failure_lines(self, step: Step, failing: list[Edge], below: int) -> list[Line]:
        """One line per place a use that loses a wanted mod, or restarts the item, leads to."""
        lines = []
        for edge, (what, names_row) in zip(failing, self.phrases(step, failing)):
            lines.append(self.link(f"{what} ({chance_text(edge.chance)})", edge.to + 1, None, always=names_row))
        return lines

    def phrases(self, step: Step, edges: list[Edge]) -> list[tuple[str, bool]]:
        """`edge_phrase` of each edge, and where two read alike, the action each goes on with: ", then Fracturing Orb".

        Two branches that lead to different steps differ in what the player does next, and that is the one thing a player sees of
        them when the item reads the same; branches to the same step are one edge already.
        """
        found = [self.edge_phrase(step, edge) for edge in edges]
        counts = Counter(what for what, _ in found)
        return [
            (f"{what}, then {self.next_title(edge)}" if counts[what] > 1 and edge.to is not None else what, names_row)
            for edge, (what, names_row) in zip(edges, found)
        ]

    def next_title(self, edge: Edge) -> str:
        """The action of the step an edge leads to, as its row is titled."""
        there = self.flow.steps[edge.to - 1].action  # `edge.to` is a step number (from 1)
        return "no action" if there is None else self.title(there)

    def accepts(self, action: Action, forward: list[Edge], after: ItemCard) -> list[str]:
        """What a random craft accepts as a good result: how many mods the item may end up with, and that the rest is any.

        Only for a step with several outcomes; the count only when the abstraction tracks every mod.
        """
        if not forward or action.label == RESTART or sum(1 for outcome in action.outcomes if outcome.weight > 0) < 2:
            return []
        landing = list(dict.fromkeys(state for edge in forward for state in edge.states))
        lines = []
        if self.reader.tracked:
            mods = sorted({len(state.fractured) + len(state.slots) for state in landing})
            if len(mods) > 1:
                lines.append(f"{', '.join(map(str, mods[:-1]))} or {mods[-1]} mods")
        if any(slot.tone == "any" for slot in (*after.prefixes, *after.suffixes)):
            lines.append("other mods: any")
        return lines

    def tier_field(self, step: Step, action: Action) -> Field | None:
        """OR-31: one line per wanted family the step can add, with the chance of each tier, mixed over the step's states."""
        if action.label == RESTART:
            return None
        lines = tier_lines(self.ab, self.plan.offer_of(action).offer.action, step.states, step.weights)
        return Field("Tier chances", tuple(Line(self.tier_text(line)) for line in lines)) if lines else None

    @staticmethod
    def tier_text(line: TierLine) -> str:
        """`+# to maximum Life: T1 1.4% (target) · T2 to T10 1.4% each · none 86%` (OR-31, format by the owner on #491).

        Runs of tiers with the same chance are joined ("T2 to T10 1.4% each", two tiers "T2 and T3 1.4% each"); a tier the target accepts is
        never joined with one it does not, and is marked "(target)"; when every tier is the target's, none is marked and the line ends with that.
        """
        every = all(share.wanted for share in line.tiers)

        def percent(chance: float) -> str:
            return "0%" if chance == 0.0 else chance_text(chance)

        runs: list[list] = []  # [first tier, last tier, chance, wanted]
        for share in line.tiers:
            last = runs[-1] if runs else None
            if last and last[1] + 1 == share.tier and last[3] == share.wanted and math.isclose(last[2], share.chance, rel_tol=1e-9, abs_tol=1e-15):
                last[1] = share.tier
            else:
                runs.append([share.tier, share.tier, share.chance, share.wanted])
        parts = []
        for first, final, chance, wanted in runs:
            mark = " (target)" if wanted and not every else ""
            if final == first:
                parts.append(f"T{first} {percent(chance)}{mark}")
            else:
                joiner = "and" if final == first + 1 else "to"
                parts.append(f"T{first} {joiner} T{final} {percent(chance)} each{mark}")
        parts.append(f"none {percent(line.none)}")
        return f"{line.text}: {' · '.join(parts)}" + (" · every tier is the target" if every else "")

    def branches(self, step: Step, after: ItemCard) -> tuple[Branch, ...]:
        """The card of each branch whose landing items differ from `after`; only a step with several branches draws them."""
        edges = [edge for edge in step.edges if edge.kind != "again"]
        if len(edges) < 2 or step.action is None or step.action.label == RESTART:
            return ()
        found = []
        for edge, (what, _) in zip(edges, self.phrases(step, edges)):
            card = card_of_states(self.ab, list(edge.states), self.reader)
            if card != after:
                found.append(Branch(f"{what} ({chance_text(edge.chance)})", card))
        return tuple(found)

    def cost_lines(self, action: Action) -> list[str]:
        if action.label == RESTART:
            return [money(self.plan.start_price.chaos)]
        priced = self.plan.offer_of(action)
        lines = [f"{count_} × {name} {money(chaos)}" for name, count_, chaos, _ in priced.parts]
        if len(priced.parts) > 1:
            lines.append(f"total {money(priced.cost)}")
        return lines

    def plan_name(self, price_name: str | None) -> str | None:
        """A price name as the page shows it: the base by its game name, never its id (#553, #481); words tell it from a base of its name."""
        return None if price_name is None else plain_base_names(self.data, price_name)

    def title(self, action: Action) -> str:
        if action.label == RESTART:
            if self.first is not None:
                return "Restart: make the start item at the vendor again"
            name = self.plan_name(self.plan.start_price.name)
            return f"Restart: buy {name} again" if name else "Restart: buy the start item again"
        offer = self.plan.offer_of(action).offer
        action = offer.action
        adds = action.adds(self.data, self.plan.target.start_item)
        if adds.crafted and adds.named and len(adds.named) == 1:  # a bench craft: named by the mod it adds
            return f"Benchcraft: {self._mod(next(iter(adds.named)))}"
        if action.reads(self.data).needs_crafted:  # Remove Crafted Mods
            return f"Benchcraft: {offer.label}"
        return offer.label

    def trade_field(self) -> Field | None:
        if self.buy is None or self.first is not None:  # the buy spec describes the bought start item, not a recipe-made one
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

    def start_card(self) -> ItemCard:
        """The bought start item: its known mods by tier, the rest of a rare unknown ("any mod or empty")."""
        item = self.plan.target.start_item
        filler = ANY_OR_EMPTY if item.rarity is Rarity.RARE else EMPTY
        return card_of_item(self.data, item, tiers=True, rolled=False, filler=filler)

    def essence_note(self, action: Action, step: Step) -> str | None:
        """For an essence of level 5 or more used on a rare: it reforges it and keeps only the fractured mod."""
        if not any(state.flags.rarity is Rarity.RARE for state in step.states):
            return None
        label = self.plan.offer_of(action).label
        for essence in self.data.essences.values():
            if essence.name == label and essence.level >= 5:
                return "reforges a rare item and keeps only the fractured mod: no Scouring first, the item stays rare"
        return None

    def notes(self, action: Action, step: Step, restart: bool) -> list[str]:
        """The Note lines of a row: the essence's, and, when the visits could not be solved, that this row's chances are a plain mean."""
        found = []
        if not restart and (essence := self.essence_note(action, step)):
            found.append(essence)
        if not self.flow.measured and len(step.states) > 1:
            found.append(
                f"the chances of this step are the plain mean of its {len(step.states):,} states: how often a run visits each could not be solved"
            )
        return found

    def vendor_row(self, step: FirstStep, final: bool) -> StepRow:
        """Row 1 of a plan that starts from a vendor recipe: what is handed over, the recipes, the price; the item card is what comes back."""
        hand = tuple(
            Line(f"{good.what if good.role == ROLE_GEMS else f'{good.count} × {good.what}'} {money(good.chaos)}") for good in step.hand
        )
        many = len(step.rounds) > 1
        recipes = tuple(
            Line(f"{f'{each.number}. ' if many else ''}{each.hand} → {each.gives} · T{each.tier}") for each in step.rounds
        )
        fields = _fields(
            Field("Hand the vendor", hand),
            Field("Recipes, each takes the item the one before made" if many else "Recipe", recipes),
            _plain("Cost per use", money(step.price)),
            _plain("Note", step.roll_note) if step.roll_note else None,
        )
        return StepRow(1, step.title, fields, self.start_card(), self.anchor(1), final, step.price)

    def buy_row(self, final: bool) -> StepRow:
        if self.first is not None:
            return self.vendor_row(self.first, final)
        price = self.plan.start_price
        if price.given:  # OR-6: the player already holds it; nothing is bought, so there is no trade field and no price
            fields = _fields(_plain("Start item", *self.start_accepts()), _plain("Cost per use", GIVEN_SOURCE))
            return StepRow(1, "Start item (given)", fields, self.start_card(), self.anchor(1), final, price.chaos)
        cost = [money(price.chaos)]
        if price.taken_for:
            cost.append(price.taken_for)
        fields = _fields(
            _plain("Accepts", *self.start_accepts()),
            self.trade_field(),
            _plain("Cost per use", *cost),
        )
        title = f"Buy {self.plan_name(price.name)}" if price.name else "Start item"
        return StepRow(1, title, fields, self.start_card(), self.anchor(1), final, price.chaos)

    def step_row(self, step: Step) -> StepRow:
        number = step.number + 1
        action = step.action
        if action is None:
            fields = _fields(_plain("Why", step.reason or "no action is available here"))
            return StepRow(number, "No action", fields, card_of_states(self.ab, step.states, self.reader), self.anchor(number))
        moving = [edge for edge in step.edges if edge.kind in ("forward", "goal")]
        shown = [edge for edge in step.edges if edge.kind != "failure"]
        failing = [edge for edge in step.edges if edge.kind == "failure"]
        restart = action.label == RESTART
        goal = self.gains(step, moving)
        if not goal and any(edge.kind == "goal" for edge in moving):
            goal = ["the target"]
        never = step.uses is not None and math.isinf(step.uses)
        step_cost = None if step.uses is None or never else step.uses * step.cost
        uses = [NEVER_FINISHES] if never else [] if step.uses is None else [count(step.uses)]
        if uses and not never and step.reached is not None and step.reached < 0.9995:
            uses[0] += f" (reached in {chance_text(step.reached)} of runs)"
        chances = self.chance_lines(step, action, shown, number + 1)
        if restart:
            after = self.start_card()
        else:
            landing = [state for edge in (moving or step.edges) for state in edge.states]
            after = card_of_states(self.ab, list(dict.fromkeys(landing)), self.reader)
        fields = _fields(
            _plain("Goal", *goal),
            _plain("Accepts", *self.accepts(action, moving, after)),
            self.trade_field() if restart else None,
            Field("Chance per use", tuple(chances)) if chances else None,
            self.tier_field(step, action),
            _plain("Cost per use", *self.cost_lines(action)),
            _plain("Uses on average", *uses),
            _plain("Step cost", money(step_cost)) if step_cost is not None else None,
            Field("On failure", tuple(self.failure_lines(step, failing, number + 1)), "warn") if failing else None,
            _plain("Note", *self.notes(action, step, restart)),
        )
        final = any(edge.kind == "goal" for edge in step.edges)
        return StepRow(number, self.title(action), fields, after, self.anchor(number), final, step_cost, self.branches(step, after))

    def start_field(self) -> Field | None:
        """When the start item is made at a vendor: the start options with their totals, so the choice can be read off the page."""
        if self.first is None or self.plan.starts is None:
            return None
        lines = []
        for row in self.plan.starts.considered:
            if row.total is None:
                continue
            head = "chosen" if row.outcome == "chosen" else "planned"
            candidate = row.candidate
            start = "given, not counted" if candidate.given else "no price" if candidate.price is None else money(candidate.price)
            lines.append(f"{head}: {candidate.label}: {money(row.total)} in all (start {start} + crafting {money(row.mean_remaining or 0.0)})")
        return _plain("Start", *lines)

    def goal_card(self) -> GoalCard:
        plan, risk = self.plan, self.inp.risk
        shift, divine = plan.start_price.chaos, plan.prices.chaos_per_divine

        def total(value: float) -> str:
            return f"{money(value + shift)} ({_divine(value + shift, divine)})"

        mean = total(risk.mean.value) if math.isfinite(risk.mean.value) else (GAPS if self.inp.reasons else NEVER)
        p90 = f"{total(risk.p90.value)} or less" if math.isfinite(risk.p90.value) else (
            UNRESOLVED if risk.success_probability.value >= 1.0 else "no finish in 9 runs of 10"
        )
        success = risk.success_probability.value
        interval = self.inp.interval
        if interval is None:
            approximate = [approximate_page_line(item) for item in approximate_inputs(plan, self.inp.policy, self.data)]
            rule = ()
        else:  # the claims of every route the interval shows, each with its spread; the plan and its interval come first
            approximate = [approximate_page_line(item) for item in interval.approximate_inputs]
            rule = tuple(_plain(label, *lines) for label, lines in interval.facts(divine))
        fields = _fields(
            _plain("Route", self.inp.label) if self.route_field else None,
            self.start_field(),
            _plain("Mean", mean),
            _plain("9 runs in 10", p90),
            _plain("Success chance", chance_text(success)) if success < 1 - 1e-9 else None,
            *rule,
            _plain("Approximate inputs", *approximate, tone="warn"),
            _plain("Prices", f"league {plan.prices.league}, fetched {plan.prices.fetched_at:%Y-%m-%d}"),
        )
        # the plan's limits are said in the planner's section (they already hold what its own steps cannot show); a given route says its own
        limits = plan.limits if self.inp.label == PLANNER_LABEL else flow_limits(self.chain)
        leaves_out = tuple(Field(title, tuple(Line(limit_text(limit, SHOWN_LABELS), more=more_labels(limit)) for limit in group)) for title, group in grouped(limits))
        return GoalCard(fields, card_of_target(self.data, plan.target), leaves_out)


def build_section(
    inp: RouteInput,
    data: GameData,
    buy: BuyStep | None = None,
    *,
    prefix: str = "",
    anchor: str = "route",
    route_field: bool = True,
) -> RouteSection:
    """The goal card and the rows of one route; `prefix` goes before the row anchors (`s2` becomes `<prefix>s2`).

    The goal card names the route in a "Route" field unless `route_field` is False (the page has a heading with it).
    """
    view = _View(inp, data, buy, prefix, route_field)
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


def _row_key(row: StepRow) -> tuple:
    """What a row says, without where it links: two rows with the same key can be the same step."""
    return (row.title, tuple((f.label, tuple(line.text for line in f.lines)) for f in row.fields), row.after, row.branches)


def _targets(row: StepRow, prefix: str) -> list[int | None]:
    """The row number each line of the row links to (None for a line with no link to a row of its section)."""
    found: list[int | None] = []
    for f in row.fields:
        for line in f.lines:
            local = line.href is not None and line.href.startswith(f"#{prefix}s")
            found.append(int(line.href[len(prefix) + 2 :]) if local else None)
    return found


def _same_steps(policy: RouteSection, given: RouteSection, prefix: str) -> dict[int, StepRow]:
    """Given row number -> the planner's row it repeats: same words and the same continuation.

    Two rows are the same step when they say the same and every link of the given row goes to a row that is itself
    the planner's row the planner's link goes to (found by dropping, until nothing changes, the pairs whose links
    part ways), so a step with another follow-up is never taken for the planner's.
    """
    by_number = {row.number: row for row in policy.rows}
    candidates: dict[int, StepRow] = {}
    for row in given.rows:
        for other in policy.rows:
            if _row_key(row) == _row_key(other):
                candidates[row.number] = other
                break
    changed = True
    while changed:
        changed = False
        for number, other in list(candidates.items()):
            mine = _targets(next(r for r in given.rows if r.number == number), prefix)
            theirs = _targets(other, "")
            for here, there in zip(mine, theirs, strict=True):
                if here is None and there is None:
                    continue
                if here is None or there is None or candidates.get(here) is not by_number.get(there):
                    del candidates[number]
                    changed = True
                    break
    return candidates


def merge_sections(policy: RouteSection, given: RouteSection, name: str) -> tuple[RouteSection, ...]:
    """The planner's section and the given route's: one when they are the same, else the given route's differing steps.

    Rows that are the same step (`_same_steps`) are drawn once, in the planner's section. When every row of the given
    route is one of the planner's, one for one, the planner's section says so in a line and the given route has no
    section. Otherwise the given route's section keeps its differing rows only, lists the steps it shares with the
    planner (as links, with the planner's number) and sends the links that pointed at a shared row to the planner's row. What the answer
    leaves out is the plan's, said once in the planner's section; the given section holds only what its own steps cannot show (`flow_limits`).
    """
    prefix = given.rows[0].anchor.removesuffix("s1") if given.rows else ""
    shared = _same_steps(policy, given, prefix)
    if len(shared) == len(given.rows) == len(policy.rows) == len({row.number for row in shared.values()}):
        head = (Field("Route", (Line(policy.title),)), Field("Given route", (Line(f"Same as the given route ({name})"),)))
        goal = replace(policy.goal, fields=(*head, *policy.goal.fields))
        return (replace(policy, goal=goal),)

    def redirect(line: Line) -> Line:
        if line.href is None or not line.href.startswith(f"#{prefix}s"):
            return line
        number = int(line.href[len(prefix) + 2 :])
        if number not in shared:
            return line
        there = shared[number]
        arrow = f"→ step {there.number}" if line.anchor else ""
        return replace(line, href=f"#{there.anchor}", anchor=arrow)

    rows = tuple(
        replace(row, fields=tuple(replace(f, lines=tuple(redirect(line) for line in f.lines)) for f in row.fields))
        for row in given.rows
        if row.number not in shared
    )
    same = Field(
        "Same as the planner",
        tuple(Line(f"step {n}: the planner's step {there.number}", f"#{there.anchor}") for n, there in shared.items()),
    )
    goal = replace(given.goal, fields=(*given.goal.fields, same)) if shared else given.goal
    return policy, replace(given, goal=goal, rows=rows)


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
    stacked = route is not None and given is not None  # then each section has a heading with its route's name
    policy = build_section(route_input(plan, report.interval), data, buy, anchor="policy", route_field=not stacked)
    sections = (policy,)
    if route is not None and given is not None:
        drawn = build_section(
            given_route_input(plan, route, given), data, buy, prefix="g-", anchor="given", route_field=False
        )
        sections = merge_sections(policy, drawn, route.name or Path(route.source).name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_page(Page(target_name or "Route view", sections)), encoding="utf-8", newline="\n")
    return path
