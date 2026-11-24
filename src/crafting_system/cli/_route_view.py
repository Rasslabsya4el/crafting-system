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
a wanted mod, one line per place they lead to: the target, the same step again ("not yet, this step again"), another step, each
named by the item that goes there and the action it goes on with (", then Orb of Annulment", #1442), and by its step ("→ step 7"): only a
step whose one place is the row right below leaves it to the arrow between the rows, so that a loop back to an earlier step reads as one (a
sure step's one outcome included, under "Next step"). On failure lists the outcomes that
lose a wanted mod the item came to the step with (a leaf of the target that was met and no longer is; a mod only an earlier use of the same
step gave is a miss, not a loss, #889), or land in a step that restarts or has no action (PRES-6: never decided by what the item still costs
to finish). A restart's own row says where it goes under "Next step": buying the item again is that step, not its failure (#892). Uses on
average, when an item comes to a step more than once in a run (restarts, returns), says the uses each time, the times and the sum (#892).
A use that consumes nothing (an unveil, a pick, the draw of a bought listing) costs "free", never the planner's epsilon (#1442). A branch whose
landing items differ from the card after the step has its own item card under it. Tier chances (OR-31): when the step
can add a mod of a family the target wants, one line per family with the chance of each tier and of none (`_route_tiers`),
mixed the same way. Accepts, on a craft with several outcomes, says how many mods the accepted results may have (when
every mod is tracked) and that the rest is any. A step that cannot reach the target says "never finishes from here" in
place of its uses. An essence of level 5 or more has a last field, Note: it reforges a rare, keeping a fractured mod
only where the item holds one, so no Scouring.

Every mod line has one format, the game's text with its ranges and the tier (`+(100-114) to maximum Life · T1`,
see `_route_card`). The bought start item shows its known mods that way and the rest of a rare as `any mod or
empty`. A given route that does what the planner's policy does is not drawn again (`merge_sections`): the goal
card says so in a line; one that differs is drawn with its differing steps only, linking the shared ones.

Words about the item come from the compressed states of the step's outcomes: a requirement leaf that
becomes met or is lost, a mod fractured, crafted mods added or removed, else the wanted mods or open slots its items have and the
other branches' lack (`item_words`). When nothing tells two outcomes apart the line names the action the item goes on with.

Numbers: money is `≈ 12 c` (3 significant digits, thousands commas, `≈` only when rounded), chances
`37%`, `≈4.3%`, `0.093%`, uses `≈ 1.1`. A route that never finishes has no cost numbers at all.

The step cost of a row is uses x cost per use, so the buy plus the step costs add up to the risk run's
mean plus the start price (`StepRow.cost` holds the number for a test). Reaches into
`_route_card._StateReader` for the text of a goal leaf, and into the plan's abstraction only through
what `_route_card` already reads.
"""

import dataclasses
import json
import math
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from crafting_system.actions import DRAW_LABEL
from crafting_system.solver._packed import expand_ranges
from crafting_system.abstraction import CompressedState, Status
from crafting_system.abstraction._kinds import kind_tags
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity, Side
from crafting_system.prices.query_compare import searched_spec
from crafting_system.prices import BuySpec
from crafting_system.prices.trade_stats import TradeStats, parse_trade_stats
from crafting_system.risk import RiskReport
from crafting_system.solver import Action
from crafting_system.prices.price_names import canonical_influences
from crafting_system.targets import Target, plain_base_names
from crafting_system.planner import PROOF_PROVED, proof_words
from crafting_system.planner import GIVEN_SOURCE, REACHED, SHOWN_LABELS, STRANDS, Plan, grouped, limit_text, more_labels, not_shown, spent_kinds_named

from ._interval import IntervalAnswer
from ._marking import approximate_inputs, approximate_page_lines, price_inputs
from ._price_marks import price_uses, use_line
from ._report import Report
from ._report_net import ask
from ._route import RESTART, Route, RouteResult
from ._route_card import ANY_OR_EMPTY, EMPTY, FAMILY_TYPE_TEXT, ItemCard, _capacity, _StateReader, card_of_item, card_of_states, card_of_target, essence_notes, mod_text
from ._route_chain import chain_of_packed_policy
from ._route_flow import _blocks as _route_flow_blocks
from ._route_flow import Chain, Edge, Flow, LossReader, Step, arrived, chain_of_policy, flow_limits, flow_of
from ._route_html import render_page
from ._limit_words import display_text, fossil_name, group_words, page_limits, player_words, state_line_text
from ._route_proof import PROOF, Proof, group_title, page_line, page_words, proof_of
from ._route_tiers import TierLine, tier_lines
from ._route_trade import BuyStep, buy_step
from ._start_step import ROLE_GEMS, FirstStep, first_step

# the planner's route, by what it is; how far it is proved the cheapest is the "Proof" field beside it (`_route_proof`, #1161): a plan whose
# search a net stopped is never called the cheapest
PLANNER_LABEL = "The planner's plan"
# beside the mean when the plan began as a walk toward the target and a net stopped its search (#1142, OR-33, OR-40): the reader sees at the top
# that this is a plan that works, not one shown near the best, before he reads the label above or the limit at the end of the card
NOT_NEAR_BEST = (
    "This route reaches the target, but the search was stopped before it found one close to the cheapest: its first plan was found by heading "
    "for the target, not by cost. Treat it as a fallback, not a recommendation; a crafter's own route may cost far less (the reason is under "
    "\"What this answer leaves out\")."
)


class PageError(ValueError):
    """A page that cannot be drawn honestly from the plan it was given."""


NEVER_FINISHES = "never finishes from here"
SURE_NEXT = "Next step, by the item it is used on"  # the field of a sure action's branches, in place of "Chance per use" (#984)
GAPS = "never finishes: the route has gaps"
MADE_DRAW_TITLE = "Check the mods the Awakener's Orb gave"  # the same step when row 1 made the item by its recipe (#1523)
DRAW_TITLE = "Check the mods the bought item came with"  # the step of the draw of a bought listing (`DRAW_LABEL` is the planner's name for it, #1442)
AGAIN = "not yet, this step again"  # an outcome that leaves the item in the same step: the player uses the action again (#889)
NEXT = "Next step"  # the field of a restart, in place of "On failure": buying the item again is the step, not a failure of it (#892)
FREE = "free"  # the cost of a use that consumes nothing (an unveil, a pick): the planner's epsilon is no price a player pays (#1442)
NEVER = "never finishes"
REACHED_FROM = "Reached from"  # the rows that lead to a row the row above does not lead to (#1442)

# --- the model of the page -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """One entry of a field. With `href` the line is a link: all of `text`, or, when `anchor` is set, that
    trailing part (`text` then a space and `anchor` as the link)."""

    text: str
    href: str | None = None
    anchor: str = ""
    more: tuple[str, ...] = ()  # entries the text does not name: the page holds them in a "details" element, closed by default
    more_title: str = ""  # the summary of that element; "" for "the other N"
    more_apart: bool = False  # the entries are sentences, each on a line of its own (the batches of the search, `_route_proof`), not a list joined by commas


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
    guide: float | None = None  # the guide's route's cost with the start item, when one was given: the proof sentence says the plan's against it (OR-59)


def route_input(plan: Plan, interval: IntervalAnswer | None = None, guide: float | None = None) -> RouteInput:
    """The planner's own policy, with the interval of the plan when the answer read a rule axis.

    A packed plan shown by its lumped chain (`Plan.lumped`) gets the chain of its item states too: the page is made from that.
    """
    chain = chain_of_packed_policy(plan.policy) if plan.lumped else None
    return RouteInput(PLANNER_LABEL, plan, plan.view_policy, plan.risk, interval=interval, chain=chain, guide=guide)


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


def _open(count_: int, side: str) -> str:
    """"no open prefix", "1 open suffix", "2 open prefixes"."""
    if count_ == 0:
        return f"no open {side}"
    return f"{count_} open {side}{'es' if count_ > 1 else ''}"


def _plain(label: str, *texts: str, tone: str = "") -> Field | None:
    return Field(label, tuple(Line(text) for text in texts), tone) if texts else None


def _fields(*candidates: Field | None) -> tuple[Field, ...]:
    return tuple(candidate for candidate in candidates if candidate is not None)


def _lost_leaves(chain: Chain, src: np.ndarray, dst: np.ndarray) -> tuple[range, np.ndarray]:
    """For each edge `src -> dst` of the chain (item states), which leaves of the target the use stops meeting: the wanted mods it loses.

    A leaf is lost on an edge when the item before has it met (PASSING) and the item after has not. Read on item states, so an Augmentation
    never loses one and a Remove Crafted Mods loses only what a crafted mod gave. The flow counts the loss only on the uses where the item
    has just come to the step holding the mod (`_route_flow.arrived`): a mod that an earlier use of the same step gave and the next use rerolls
    away is a miss of that step, not a loss; an essence used again on boots never "loses" the Life only its last roll gave (#889).
    """
    width = len(chain.states[0].status)
    status = np.array([state.status for state in (*chain.states, *chain.goals)], dtype=np.int8).reshape(chain.m + len(chain.goals), width)
    met = int(Status.PASSING)
    return range(status.shape[1]), (status[src] == met) & (status[dst] != met)


def _leaves_met(chain: Chain) -> np.ndarray:
    """A number per state for the leaves of the target it meets: what a use loses depends on the state it starts from only through these (#689)."""
    width = len(chain.states[0].status)
    met = np.array([state.status for state in chain.states], dtype=np.int8).reshape(chain.m, width) == int(Status.PASSING)
    return np.unique(met, axis=0, return_inverse=True)[1].reshape(-1)


def _met(chain: Chain) -> np.ndarray:
    """The leaves of the target each state and each goal of `chain` meets (rows: states, then goals), kept on the chain."""
    cached = chain.__dict__.get("_met")
    if cached is None:
        width = len(chain.states[0].status)
        status = np.array([state.status for state in (*chain.states, *chain.goals)], dtype=np.int8).reshape(chain.m + len(chain.goals), width)
        cached = status == int(Status.PASSING)
        object.__setattr__(chain, "_met", cached)
    return cached


def _given(chain: Chain) -> np.ndarray:
    """Per key of `chain` (a step), the leaves a use of that step can make met on an item that stays in the step: what its own rolls give.

    Read once per (kernel, step, leaves met) triple, kept on the chain. An Annulment or a removal gives none; an essence, a Chaos Orb, a fossil
    give the leaves of the mods they can roll.
    """
    cached = chain.__dict__.get("_given")
    if cached is None:
        met = _met(chain)
        m = chain.m
        cached = np.zeros((len(chain.keys), met.shape[1]), dtype=bool)
        acting = np.flatnonzero(chain.kernel >= 0)
        if acting.size:
            classes = _leaves_met(chain)
            _, first = np.unique(np.stack([chain.kernel[acting], chain.key[acting], classes[acting]], axis=1), axis=0, return_index=True)
            reps = acting[first]
            table = chain.kernels
            sizes = table.kernel_sizes()[chain.kernel[reps]]
            for a, b in _route_flow_blocks(np.concatenate(([0], np.cumsum(sizes)))):
                ask()  # the report's memory net (#1381)
                src = np.repeat(reps[a:b], sizes[a:b])
                dst = table.k_succ[expand_ranges(table.k_ptr[chain.kernel[reps[a:b]]], sizes[a:b])].astype(np.int64)
                stays = (dst < m) & (chain.key[np.minimum(dst, m - 1)] == chain.key[src])
                gained = ~met[src] & met[dst] & stays[:, None]
                np.logical_or.at(cached, chain.key[src], gained)
        object.__setattr__(chain, "_given", cached)
    return cached


def _own_losses(chain: Chain, src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Per edge `src -> dst`: whether every leaf it loses is one its step's own uses can give (`_given`), so that it may be the step's own roll (#889)."""
    met = _met(chain)
    lost = met[src] & ~met[dst]
    return ~(lost & ~_given(chain)[chain.key[src]]).any(axis=1)


LOST_LEAVES = LossReader(_lost_leaves, _leaves_met, arrived, _own_losses)


def steps_of_chain(chain: Chain) -> Flow:
    """The steps of a chain, as the page and the text report both draw them (`_route_flow.flow_of`): made once for a chain, then read from it.

    The chain of a lumped plan is made once per policy, so the page, the text report and the plan's limits all read the same solve.
    """
    cached = getattr(chain, "_steps", None)
    if cached is None:
        cached = flow_of(chain, is_restart=lambda action: action.label == RESTART, loss=LOST_LEAVES)
        object.__setattr__(chain, "_steps", cached)
    return cached


def _require_limits(plan: Plan) -> None:
    """A page is drawn only from a plan that carries the limits a planner's plan has; the steps of the text report are not a page and ask nothing."""
    if not any(limit.kind == STRANDS for limit in plan.limits):
        # Every plan the planner makes carries the limit "Memory Strands are not considered" (`strands_limit`, the first one `plan_for` writes), so a plan
        # without it is not one the planner made, and a page drawn from it would say "Cheapest policy of the planner" with no part "What this answer
        # leaves out", or a part that lacks what every real plan has (OR-13).
        raise PageError(
            "the plan has no limits of a planner's plan (not even the Memory Strands one), so the page would claim a guarantee it does not state (OR-13): "
            "a plan made by the planner always carries what it leaves out (`Plan.limits`); build this one with them"
        )


# --- telling the branches of a step apart by the item (#1442) ---------------------------------------------------

# the order of the conditions on an item: wanted mods first, a wanted family at too low a tier last
_ORDER = {"leaf": 0, "crafted": 1, "fractured": 1, "rarity": 2, "junk": 3, "tag": 3, "open": 4, "below": 5}
_BINARY = ("leaf", "below", "fractured", "crafted", "rarity")
KINDS = 4  # the most kinds of item one line names, and the most conditions that name one: past them a line no longer reads as a condition
KIND_WORDS = 4


@dataclass(frozen=True)
class _Column:
    """A condition a player checks on an item: "with" or "without" `noun`, or `noun` alone ("a magic item"); `order` ranks the words."""

    sign: str
    noun: str
    order: tuple[int, int]


@dataclass(frozen=True)
class _Table:
    """The conditions on the items one step's uses leave: `tests[c, i]` whether condition `c` holds on item `i`."""

    index: dict
    columns: tuple[_Column, ...]
    tests: np.ndarray

    def rows(self, states) -> np.ndarray:
        return np.unique(np.fromiter((self.index[state] for state in states), dtype=np.int64))

    @staticmethod
    def of(states: list, traits: list[dict[tuple, int]], noun) -> "_Table":
        keys = list(dict.fromkeys(key for each in traits for key in each))
        columns: list[_Column] = []
        tests: list[np.ndarray] = []
        seen: set[tuple[str, str]] = set()
        for key in sorted(keys, key=lambda key: _ORDER[key[0]]):
            if key[0] == "open" and any(key not in each for each in traits):  # an item whose open slots are not known
                continue
            values = np.fromiter((each.get(key, 0) for each in traits), dtype=np.int64, count=len(traits))
            for sign, words, test in _conditions(key, values, noun):
                if (sign, words) in seen or test.all() or not test.any():  # a crafted mod the target wants is its leaf too: one condition
                    continue
                seen.add((sign, words))
                columns.append(_Column(sign, words, (_ORDER[key[0]], len(columns))))
                tests.append(test)
        matrix = np.array(tests, dtype=bool).reshape(len(tests), len(states))
        return _Table({state: i for i, state in enumerate(states)}, tuple(columns), matrix)


def _conditions(key: tuple, values: np.ndarray, noun):
    """The conditions of one trait of the items (`_View._traits`), in words, each with where it holds."""
    kind = key[0]
    if kind in _BINARY:
        if kind == "rarity":
            yield "", f"a {key[1]} item", values == 1
            return
        words = noun(key)
        yield "with", words, values == 1
        yield "without", words, values == 0
        return
    side = key[1]
    what = f"open {side}" if kind == "open" else f"unwanted {side}" if kind == "junk" else f"unwanted {side} mod"

    def counted(count_: int) -> str:
        return f"{count_} {what}" if count_ == 1 else f"{count_} {what}{'es' if what.endswith('fix') else 's'}"

    found = sorted(set(values.tolist()))
    for count_ in found:  # a count first, then the ranges
        if kind == "open":
            yield "with", _open(count_, side), values == count_
        elif count_ == 0:
            yield "without", f"an {what}", values == 0
        else:
            yield "with", f"an {what}" if count_ == 1 else counted(count_), values == count_
    for count_ in found[1:]:
        yield "with", f"at least {counted(count_)}", values >= count_
    for count_ in found[:-1]:
        if count_:
            yield "with", f"at most {counted(count_)}", values <= count_


def _parted(on_others: np.ndarray, rest: np.ndarray, columns) -> int:
    """How many of the other items left (`rest`) the conditions `columns` together rule out."""
    held = rest.copy()
    for c in columns:
        held &= on_others[c]
    return int(rest.sum() - held.sum())


def _fewest(whole: list[int], on_others: np.ndarray, rest: np.ndarray) -> list[int] | None:
    """The fewest of the conditions `whole` (each holds on every item of the branch) that rule out every other item: one, else two, the
    earliest words first; None when two do not."""
    need = int(rest.sum())
    for c in whole:  # in the order of their words
        if _parted(on_others, rest, [c]) == need:
            return [c]
    best = sorted(whole, key=lambda c: -_parted(on_others, rest, [c]))[:24]
    pairs = [(a + b, a, [a, b]) for k, a in enumerate(best) for b in best[k + 1 :] if _parted(on_others, rest, [a, b]) == need]
    return min(pairs)[2] if pairs else None


def _kinds(table: _Table, on_mine: np.ndarray, on_others: np.ndarray, rest: np.ndarray) -> list[list[int]] | None:
    """The items of a branch as at most `KINDS` kinds, each told by at most `KIND_WORDS` conditions that hold on all its items and on no
    other item: a kind is grown one condition at a time, each the one that rules out the most other items for the items it keeps (the
    information gain of rule learning, FOIL), and the next kind is grown on the items no kind names yet. None when they do not cover them all."""
    left = np.ones(on_mine.shape[1], dtype=bool)
    kinds: list[list[int]] = []
    for _ in range(KINDS):
        kind: list[int] = []
        mine, theirs = left.copy(), rest.copy()
        while theirs.any() and len(kind) < KIND_WORDS:
            p, n = int(mine.sum()), int(theirs.sum())
            best, score = None, -math.inf
            for c in range(len(on_mine)):
                p1, n1 = int((mine & on_mine[c]).sum()), int((theirs & on_others[c]).sum())
                if p1 == 0 or n1 == n:
                    continue
                gain = p1 * (math.log(p1 / (p1 + n1)) - math.log(p / (p + n)))
                if gain > score + 1e-12:
                    best, score = c, gain
            if best is None:  # no condition rules out one more other item
                break
            kind.append(best)
            mine &= on_mine[best]
            theirs &= on_others[best]
        if theirs.any() or not kind:
            return None
        kinds.append(kind)
        left &= ~mine
        if not left.any():
            return kinds
    return None


def _words(columns: list[_Column]) -> str:
    """Conditions in words: those alone first, then "with ...", then "without ..." ("a rare item, with Life T1, without an unwanted prefix")."""
    ordered = sorted(columns, key=lambda column: column.order)
    parts = [column.noun for column in ordered if column.sign == ""]
    for sign in ("with", "without"):
        if nouns := [column.noun for column in ordered if column.sign == sign]:
            parts.append(f"{sign} {'; '.join(nouns)}")
    return ", ".join(parts)


class _View:
    """What the rows of one section share: the plan, the data, the flow and the anchors."""

    def __init__(self, inp: RouteInput, data: GameData, buy: BuyStep | None, prefix: str, route_field: bool) -> None:
        self.inp, self.plan, self.data, self.buy, self.prefix = inp, inp.plan, data, buy, prefix
        self.route_field = route_field
        self.ab = self.plan.abstraction
        self.chain = inp.chain if inp.chain is not None else chain_of_policy(self.plan.start, inp.policy, self.ab.is_goal, inp.reasons)
        self.flow = steps_of_chain(self.chain)
        # a start item made at a vendor (ADR-0059): row 1 is the recipe, not a buy
        starts = getattr(self.plan, "starts", None)  # a stand-in plan of a test has none
        self.first: FirstStep | None = None if starts is None else first_step(starts.chosen, data, self.plan.target)
        # the item the route starts from: its fractured mods are marked on the target card and on every card after a step (#895)
        self.start_item: Item = self.plan.target.start_item if starts is None else starts.chosen.item
        # the mods the essences of this route force, each with its essence's tier: a line that stands for one says where it comes from (#895)
        used = [step.action.label for step in self.flow.steps if step.action is not None]
        self.forced = essence_notes(data, self.ab.base_id, used)
        self.reader = _StateReader(self.ab, self.start_item, self.forced, self.plan.target.influences)

    # -- anchors and links ---------------------------------------------------------------------------------

    def anchor(self, number: int) -> str:
        return f"{self.prefix}s{number}"

    def link(self, text: str, number: int) -> Line:
        """`text` with a link to row `number` and its arrow ("→ step 7"). Every line that names a place a step leads to has one, but the one
        place of a step that is the row right below, which `chance_lines` leaves to the arrow between the rows (#1442)."""
        return Line(text, f"#{self.anchor(number)}", f"→ step {number}")

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

    def _fractured(self, state: CompressedState) -> set:
        """The fractured entries of a state: a mod held as its family type ("~3") is told by what it gives the goal, so a fractured Life T1
        and a fractured junk mod of one family type are two entries (#1442)."""
        return set(state.fractured)

    def _fractured_text(self, entry) -> str:
        """A fractured mod in words: the wanted mod it is when it gives the goal a leaf, even when the state holds it as a family type (#1442)."""
        if entry.mod_id in self.data.mods:
            return f"{self._mod(entry.mod_id)} · fractured"
        slot = self.reader.fractured(entry.mod_id, entry.contribution)[1]
        return f"{slot.text} · {slot.note} · fractured" if slot.note else f"{slot.text} · fractured"

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
                if entry not in before_fractured:
                    mods.append(self._fractured_text(entry))
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

    def lost(self, edge: Edge, removed: bool = False) -> list[str]:
        """What a failure edge costs the item, in words: the wanted mod its uses lose, or the list of those they may lose. A sure use
        (`removed`: Remove Crafted Mods, a Scouring) does not miss: it removes them, which is what it is used for (R13 step 13, #1442)."""
        texts = list(dict.fromkeys(self.leaf_text(i) for i in edge.lost))  # two leaves that read alike are one mod to a player (#984)
        if removed:
            return [f"{texts[0]} removed" if len(texts) == 1 else f"removed: {'; '.join(texts)}"] if texts else []
        if len(texts) <= 1:
            return [f"{text} lost" for text in texts]
        return [f"one of these lost: {'; '.join(texts)}"]

    def appeared(self, step: Step, edge: Edge) -> list[str]:
        """What every state of a forward edge has that no state of the step has (a leaf met, a mod fractured or crafted).

        A leaf that a new fractured or crafted mod meets is named once, as the mod (as `gains` does), and no text twice (#984)."""
        before = self._passing(step.states)
        before_fractured = set().union(*(self._fractured(state) for state in step.states))
        before_crafted = set().union(*(self._crafted(state) for state in step.states))
        new_fractured = sorted(set.intersection(*(self._fractured(state) for state in edge.states)) - before_fractured, key=lambda entry: (entry.mod_id, entry.contribution))
        new_crafted = sorted(set.intersection(*(self._crafted(state) for state in edge.states)) - before_crafted)
        each = [self._fractured(state) - before_fractured for state in edge.states]  # what each item had fractured by this use
        mixed = not new_fractured and bool(edge.states) and all(each)  # every item had a mod fractured, not the same one (R13 step 10, #1442)
        explained = {
            i
            for state, new in zip(edge.states, each)
            for contribution in (
                *(entry.contribution for entry in new if mixed or entry in new_fractured),  # a fractured mod named below, alone or in a list
                *(slot.contribution for slot in state.slots if slot.crafted and slot.kind in new_crafted),
            )
            for i, status in enumerate(contribution)
            if status is Status.PASSING
        }
        found = [
            self.leaf_text(i)
            for i in range(len(self.plan.leaf_labels))
            if i not in before and i not in explained and all(state.status[i] is Status.PASSING for state in edge.states)
        ]
        found += [self._fractured_text(entry) for entry in new_fractured]
        if mixed:  # say which they may be
            texts = sorted({self._fractured_text(entry).removesuffix(" · fractured") for new in each for entry in new})
            found.append(f"{texts[0]} · fractured" if len(texts) == 1 else f"one of these fractured: {'; '.join(texts)}")
        found += [f"{self._mod(mod_id)} · crafted" for mod_id in new_crafted]
        return list(dict.fromkeys(found))

    # -- the fields of a step ----------------------------------------------------------------------------------

    def edge_phrase(self, step: Step, edge: Edge) -> tuple[str, bool]:
        """What happens on the item at an edge, in words and without its chance; `True` when the words only name the row it leads to.

        A goal edge is "the target", an edge to the same step is "not yet, this step again", a failure is the wanted mods a use loses (of
        those the item came to the step with, `_lost_leaves`), or the restart / the dead end it lands in; any other edge says what every
        landing item has that the step's items lack, else what its items have, or lack, that the items of the step's other branches do not
        (`item_words`): the item by which a player tells where it goes (#1442). Only when nothing tells them apart do the words name the row.
        """
        if edge.kind == "goal" or edge.to is None:
            return "the target", False
        if edge.kind == "failure" and step.action is not None and step.action.label == RESTART:
            again = "made again at the vendor" if self.first is not None else "made again" if self.plan.start_price.made is not None else "bought again"
            return f"the start item {again}", False
        if edge.kind == "again":  # the item a use leaves in the step, told from those it sends on to another step (R14 step 9's Exalted Orb)
            onward = any(other.kind != "goal" and other.to != edge.to for other in step.edges)  # beside the target alone, "not yet" says it
            tell = self.item_words(step, edge) if onward else ""
            return (f"{tell}, {AGAIN}" if tell else AGAIN), False
        if edge.kind == "failure" and (lost := self.lost(edge, removed=step.action is not None and self.sure(step.action))):
            tell = self.item_words(step, edge, given=tuple(("without", self.leaf_text(i)) for i in edge.lost))
            return " and ".join(lost) + (f", {tell}" if tell else ""), False
        # what the use gave, and what parts the item from those of the step's other branches (the use may give the same on several)
        appeared = self.appeared(step, edge) if edge.states else []
        said = tuple(("with", text) for text in appeared)
        words = ", ".join(part for part in (" and ".join(appeared), self.item_words(step, edge, given=said)) if part)
        if edge.kind == "failure":
            there = self.flow.steps[edge.to - 1].action  # `edge.to` is a step number (from 1)
            lead = f"{words}, " if words else ""
            if there is None:
                return f"{lead}the route has no step for this item", True
            if there.label == RESTART:  # with what the restart costs: its row may be far from this one (#1442), and the item that sends there
                return f"{lead}the item is restarted: a new start item for {self.cost_lines(there)[0]}", True
        if words:
            return words, False
        return f"the item of step {edge.to + 1}", True

    def _free_slots(self, state: CompressedState) -> tuple[int, int] | None:
        """The open prefixes and suffixes of an item state; None when the abstraction does not keep every mod (then they are not known)."""
        if not self.reader.tracked:
            return None
        rarity = state.flags.rarity
        if rarity is Rarity.NORMAL:
            return None
        held = Counter(slot.side for slot in state.slots)
        for entry in state.fractured:
            held[self.reader.fractured(entry.mod_id, entry.contribution)[0]] += 1
        sides = (Side.PREFIX, Side.SUFFIX)
        return tuple(max(0, _capacity(self.data, self.ab.base_id, side, rarity) - held[side]) for side in sides)  # type: ignore[return-value]

    def item_words(self, step: Step, edge: Edge, among: list[Edge] | None = None, given: tuple[tuple[str, str], ...] = ()) -> str:
        """The item of a branch, by what a player checks on it that tells it from every item of the step's other branches (or of `among`)
        (#1442): a wanted mod held or not, a crafted or a fractured mod, the rarity, the mods the target does not need on each side (and
        those of them with an attack or caster tag, which a metamod reads), the open prefixes and suffixes, a wanted family at too low a tier.

        The plan picks the next action by the item a use leaves, so the items of two branches are never the same: a few of these conditions
        that hold on every item of the branch and on none of the others' are what a player reads off his item ("with an unwanted attack mod,
        then Orb of Annulment"). The fewest that do, wanted mods first; when the branch holds items of several kinds, one set per kind joined
        by "or" (at most `KINDS`). `given` are the conditions the line says already, as ("with" or "without", words): what the use gave or
        lost, which part it from some others already.
        "" when nothing parts every item within those bounds (words that hold on some other branch's items too would send a player
        wrong), or when `given` says enough.
        """
        key = (step.number, id(edge), None if among is None else tuple(id(other) for other in among), given)
        cache = self.__dict__.setdefault("_words", {})
        if key not in cache or cache[key][0] is not edge:  # the edge kept with its words: its id is not taken by another while it lives
            cache[key] = (edge, among, self._item_words(step, edge, among, given))
        return cache[key][2]

    def _item_words(self, step: Step, edge: Edge, among: list[Edge] | None, given: tuple[tuple[str, str], ...]) -> str:
        if not edge.states:
            return ""
        pool = [other for other in (step.edges if among is None else among) if other is not edge and other.to != edge.to]
        # the items of the branches that go on with another action (the target's too): a lost-and-back branch to the same step reads apart already
        table = self._table(step)
        if any(state not in table.index for each in (edge, *pool) for state in each.states):  # items the step's own branches do not hold
            states = list(dict.fromkeys(state for each in (edge, *pool) for state in each.states))
            table = _Table.of(states, [self._traits(state) for state in states], self._noun)
        mine = table.rows(edge.states)
        theirs = [table.rows(other.states) for other in pool]
        others = np.setdiff1d(np.concatenate(theirs) if theirs else np.zeros(0, dtype=np.int64), mine)
        if not others.size:
            return ""
        on_mine, on_others = table.tests[:, mine], table.tests[:, others]
        rest = np.ones(others.size, dtype=bool)
        for c, column in enumerate(table.columns):  # what the line says already
            if (column.sign, column.noun) in given and on_mine[c].all():
                rest &= on_others[c]
        if not rest.any():
            return ""
        whole = [c for c in range(len(table.columns)) if on_mine[c].all() and not on_others[c][rest].all()]
        chosen = _fewest(whole, on_others, rest)
        if chosen is not None:
            return _words([table.columns[c] for c in chosen])
        kinds = _kinds(table, on_mine, on_others, rest)  # several kinds of item, each told apart by its own conditions
        if kinds is not None:
            return ", or ".join(_words([table.columns[c] for c in kind]) for kind in kinds)
        return ""  # no words that hold on this branch's items alone: a condition some other branch's items share would send a player wrong

    def _table(self, step: Step) -> "_Table":
        """The conditions of `_traits` on every item a use of `step` leaves, kept per step."""
        tables = self.__dict__.setdefault("_tables", {})
        if step.number not in tables:
            states = list(dict.fromkeys(state for edge in step.edges for state in edge.states))
            tables[step.number] = _Table.of(states, [self._traits(state) for state in states], self._noun)
        return tables[step.number]

    def _noun(self, key: tuple) -> str:
        kind = key[0]
        if kind == "leaf":
            return self.leaf_text(key[1])
        if kind == "below":
            below = self.reader.wanted([key[1]], Status.BELOW)
            return f"{below.text} · {below.note}"  # "tier too low", or "below roll 12" for a leaf that asks a roll (#1433)
        if kind == "crafted":
            return f"{self._mod(key[1])} · crafted"
        return key[1]  # a fractured mod's words, a rarity

    def _traits(self, state: CompressedState) -> dict[tuple, int]:
        """What a player sees on an item, as numbers: the wanted mods it holds, at the tier or too low, its crafted and fractured mods, its
        rarity, the mods the target does not need on each side (with the attack or caster tag a metamod reads), its open prefixes and suffixes."""
        traits: dict[tuple, int] = {}
        for i, status in enumerate(state.status):
            traits[("leaf", i)] = int(status is Status.PASSING)
            traits[("below", i)] = int(status is Status.BELOW)
        for entry in state.fractured:
            traits[("fractured", self._fractured_text(entry))] = 1
        traits[("rarity", state.flags.rarity.value)] = 1
        junk = {Side.PREFIX: 0, Side.SUFFIX: 0}
        tags: Counter = Counter()
        for slot in state.slots:
            if slot.crafted:
                traits[("crafted", slot.kind)] = 1
            elif not any(status is not Status.ABSENT for status in slot.contribution):
                junk[slot.side] += 1
                tags.update(kind_tags(slot.kind))
        if self.reader.tracked:  # else the state keeps no mod the target does not need
            traits[("junk", "prefix")], traits[("junk", "suffix")] = junk[Side.PREFIX], junk[Side.SUFFIX]
            for tag in ("attack", "caster"):
                traits[("tag", tag)] = tags[tag]
            free = self._free_slots(state)
            if free is not None:
                traits[("open", "prefix")], traits[("open", "suffix")] = free
        return traits

    @staticmethod
    def sure(action: Action) -> bool:
        """Whether one use of the action always gives the same item (a bench craft, Remove Crafted Mods): it never misses, and where its
        items go on to differs only by the item it was used on, not by chance (#984)."""
        return sum(1 for outcome in action.outcomes if outcome.weight > 0) <= 1

    def chance_lines(self, step: Step, action: Action, shown: list[Edge], below: int, sure: bool) -> list[Line]:
        """One line per place the outcomes that lose no wanted mod lead to, with the exact mixture of their chances.

        For a sure action (`sure`) the lines are the shares of its uses that go on to each step, by the item it was used on (`step_row`
        titles them so): a chance of a sure use would read as a miss (#984). A restart is never sure here: what it buys is a new random item."""
        if len(shown) == 1:
            edge = shown[0]
            onward = edge.kind not in ("goal", "again") and edge.to is not None and edge.to + 1 != below
            if self.sure(action):  # one place and one outcome: said only when that place is not the row below (a loop back, a jump)
                return [self.link(f"then {self.next_title(edge)}", edge.to + 1)] if onward else []
            if action.label == DRAW_LABEL and edge.kind not in ("goal", "again") and edge.to is not None and all(other is edge or other.kind != "failure" for other in step.edges):
                # every listing goes on the same way, whatever it came with (R20: the essence of the next step rerolls it, #1442)
                text = f"whatever mods it came with, go on with {self.next_title(edge)}"
                return [self.link(text, edge.to + 1)] if onward else [Line(text)]
            text = chance_text(edge.chance)
            return [self.link(f"{text}, then {self.next_title(edge)}", edge.to + 1)] if onward else [Line(text)]
        lines = []
        for edge, (what, _) in zip(shown, self.phrases(step, shown)):
            text = f"{what}: {chance_text(edge.chance)}" + (" of uses" if sure else "")
            lines.append(Line(text) if edge.kind in ("goal", "again") else self.link(text, edge.to + 1))
        return lines

    def failure_lines(self, step: Step, failing: list[Edge]) -> list[Line]:
        """One line per place a use that loses a wanted mod, or restarts the item, leads to."""
        lines = []
        for edge, (what, _) in zip(failing, self.phrases(step, failing)):
            lines.append(self.link(f"{what} ({chance_text(edge.chance)})", edge.to + 1))
        return lines

    def restart_lines(self, step: Step, edges: list[Edge]) -> list[Line]:
        """Where a restart goes: the start item again, a line per step it leads to, with the chance only when there are several (#892)."""
        many = len(edges) > 1
        return [
            self.link(f"{what}{f' ({chance_text(edge.chance)})' if many else ''}", edge.to + 1)
            for edge, (what, _) in zip(edges, self.phrases(step, edges))
        ]

    def phrases(self, step: Step, edges: list[Edge]) -> list[tuple[str, bool]]:
        """`edge_phrase` of each edge, with the action each goes on with when it leads to another step: ", then Fracturing Orb" (#1442).

        A player who holds the item of a branch must be told what to do with it next, not only which row to read; a branch that leads back to
        the same step with a mod lost says so (", this step again"). A phrase that only names the row ("the item of step 4") becomes the action.
        """
        found = []
        for edge, (what, names_row) in zip(edges, (self.edge_phrase(step, edge) for edge in edges)):
            if edge.to is None or edge.kind in ("goal", "again") or (step.action is not None and step.action.label == RESTART):
                found.append((what, names_row))
            elif edge.to == step.number:
                found.append((f"{what}, this step again", names_row))
            elif names_row and what.startswith("the item of step"):
                found.append((f"then {self.next_title(edge)}", True))
            elif names_row:
                found.append((what, names_row))
            else:
                found.append((f"{what}, then {self.next_title(edge)}", names_row))
        return found

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
        A mod of a base with no tiers (a base jewel) has no tier: `(5-7)% increased maximum Life: 3.3% · none 97%` (#963).
        """
        every = all(share.wanted for share in line.tiers)

        def percent(chance: float) -> str:
            return "0%" if chance == 0.0 else chance_text(chance)

        if not line.tiered:
            return f"{line.text}: {percent(math.fsum(share.chance for share in line.tiers))} · none {percent(line.none)}"

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
            mark = self.plan.start_price.mark
            return [money(self.plan.start_price.chaos), *([mark] if mark else [])]  # OR-8: a thin market's price carries its mark
        if action.label == DRAW_LABEL:  # the first draw of a bought item (ADR-0064): the listing's price was paid in row 1 and is paid again by every restart
            again = " and again by each restart" if any(step.action is not None and step.action.label == RESTART for step in self.flow.steps) else ""
            if self.plan.start_price.made is not None:  # the item was made in row 1, not bought (#1523)
                return [f"{FREE}: the item was paid in step 1{again}"]
            return [f"{FREE}: the listing's price is paid in step 1{again}"]
        priced = self.plan.offer_of(action)
        if not priced.parts:  # an unveil, a pick: it consumes nothing (the planner's epsilon is for its solver, not a price, #1442)
            return [FREE]
        stand_ins = priced.offer.action.stand_ins(self.data)  # a resource paid in place of goods no price list holds says what it is (#1518)
        lines = [f"{count_} × {name} {money(chaos)}" + (f": {stand_ins[name]}" if name in stand_ins else "") for name, count_, chaos, _ in priced.parts]
        if len(priced.parts) > 1:
            lines.append(f"total {money(priced.cost)}")
        lines.extend(f"{name}: {mark}" for name, mark in priced.marks)  # OR-8: a part priced from a thin market carries its mark
        return lines

    def plan_name(self, price_name: str | None) -> str | None:
        """A price name as the page shows it: the base by its game name, never its id (#553, #481); words tell it from a base of its name."""
        return None if price_name is None else plain_base_names(self.data, price_name)

    def title(self, action: Action) -> str:
        if action.label == RESTART:
            if self.first is not None:
                return "Restart: make the start item at the vendor again"
            if self.plan.start_price.made is not None:
                return f"Restart: make the start item again with an {self.plan.start_price.made.orb}"
            name = self.start_name()
            return f"Restart: buy {name} again" if name else "Restart: buy the start item again"
        if action.label == DRAW_LABEL:  # the first draw of a bought item (ADR-0064): the player reads what the listing came with, he uses nothing
            return MADE_DRAW_TITLE if self.plan.start_price.made is not None else DRAW_TITLE
        offer = self.plan.offer_of(action).offer
        action = offer.action
        adds = action.adds(self.data, self.plan.target.start_item)
        if adds.crafted and adds.named and len(adds.named) == 1:  # a bench craft: named by the mod it adds
            return f"Benchcraft: {self._mod(next(iter(adds.named)))}"
        if action.reads(self.data).needs_crafted:  # Remove Crafted Mods
            return f"Benchcraft: {offer.label}"
        return fossil_name(offer.label)  # a fossil set by its fossils' game names (#1514)

    def trade_field(self) -> Field | None:
        if self.buy is None or self.first is not None or self.plan.start_price.made is not None:  # the buy spec describes the bought start item, not a recipe-made one
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
        filler = ANY_OR_EMPTY if item.rarity is Rarity.RARE or self.plan.start.flags.unopened else EMPTY  # a bought item holds mods the target does not name (OR-17, ADR-0064)
        return card_of_item(self.data, item, tiers=True, rolled=False, filler=filler)

    def essence_note(self, action: Action, step: Step) -> str | None:
        """For an essence of level 5 or more used on a rare: it reforges it, keeping a fractured mod only where the item holds one (R09, R20
        hold none: #1442, #1514)."""
        rare = [state for state in step.states if state.flags.rarity is Rarity.RARE]
        if not rare:
            return None
        label = self.plan.offer_of(action).label
        if not any(essence.name == label and essence.level >= 5 for essence in self.data.essences.values()):
            return None
        held = [bool(state.fractured) for state in rare]
        if all(held):
            said = "reforges a rare item and keeps only the fractured mod: no Scouring first, the item stays rare"
        elif any(held):
            said = "reforges a rare item and keeps only a fractured mod, where the item has one: no Scouring first, the item stays rare"
        else:
            said = "reforges a rare item with new mods, the essence's mod among them: no Scouring first, the item stays rare"
        if len(rare) < len(step.states):  # the step also takes the bought normal item (R04, R06): the essence makes it rare (crafter, #1442)
            said += "; on a normal item it makes it rare, with the essence's mod among its new mods"
        return said

    def craft_again_note(self, action: Action, step: Step) -> str | None:
        """For a bench craft an item comes to more than once in a run: it is paid again each time (R24's suffix lock of 2 Divine, ≈3.1
        times, #1442). A bench craft is refused on an item that already holds its mod, so an item that comes back has lost it."""
        offer = self.plan.offer_of(action).offer
        adds = offer.action.adds(self.data, self.plan.target.start_item)
        if not (adds.crafted and adds.named) or step.uses is None or not step.reached or not math.isfinite(step.uses):
            return None
        times = step.uses / step.reached
        if times < 1.05:
            return None
        return (
            "each time an item comes back here the craft is gone (the steps under \"Reached from\" that send it back take it off), so it is "
            "paid again: the step cost counts every one"
        )

    def sure_draw_note(self, action: Action, step: Step) -> str | None:
        """For a craft that draws its result at random but is sure on every item of the step (the Wild Bristle Matron on a suffix-full item,
        whose one metamod with room is Suffixes Cannot Be Changed): why a random craft is drawn with no chance (#1518, crafter on R04, R14, R20,
        R24). A sure step's repeats come from the steps that send the item back, which "Reached from" names."""
        if not self.sure(action):
            return None
        offer = self.plan.offer_of(action).offer
        if not offer.action.adds(self.data, self.plan.target.start_item).draws:
            return None
        said = (
            "this craft picks its result at random among those the item allows, but on every item this step is used on only one is "
            "allowed, so each use gives the item below: it cannot miss here"
        )
        if step.uses is not None and step.reached and math.isfinite(step.uses) and step.uses / step.reached >= 1.05:
            said += "; it is used again each time a later miss sends the item back here"
        return said

    def notes(self, action: Action, step: Step, restart: bool) -> list[str]:
        """The Note lines of a row: the essence's, a random craft that is sure here, a bench craft's paid again on each return, and, when the
        visits could not be solved, that this row's chances are a plain mean."""
        found = []
        if not restart and (draw := self.sure_draw_note(action, step)):
            found.append(draw)
        if not restart and (essence := self.essence_note(action, step)):
            found.append(essence)
        if not restart and (again := self.craft_again_note(action, step)):
            found.append(again)
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

    def made_row(self, final: bool) -> StepRow:
        """Row 1 of a plan whose start item has no market line and is made by its recipe (#1523): an Awakener's Orb on two single-influence
        Rare helmets holding an influenced mod, each good with its own price; the item card is the Rare the orb gives, whose mods the next row draws."""
        price = self.plan.start_price
        made = price.made
        assert made is not None
        buy = tuple(Line(f"{count} × {self.plan_name(name)} {money(chaos)}") for name, count, chaos, _ in made.goods)
        use = Line(
            f"{made.orb} on the first helmet with the second as the item it destroys: the first keeps its base and item level and becomes a Rare "
            "item with both influences; it keeps one influenced mod of each helmet (one at random where a helmet holds several) and every other "
            "mod is rolled anew"
        )
        note = _plain(
            "Note",
            "the plan reads the new item's mods as those of a bought Rare (an Orb of Alchemy's roll), without the two kept influenced mods",
        )
        fields = _fields(Field("Buy", buy), Field("Use", (use,)), _plain("Cost per use", money(price.chaos)), note)
        target = self.plan.target
        influences = "/".join(canonical_influences(each.value for each in target.influences))
        title = f"Make a {influences} {self.data.base_items[target.base_id].name}, item level {target.item_level}, with an {made.orb}"
        return StepRow(1, title, fields, self.start_card(), self.anchor(1), final, price.chaos)

    def buy_row(self, final: bool) -> StepRow:
        if self.first is not None:
            return self.vendor_row(self.first, final)
        if self.plan.start_price.made is not None:
            return self.made_row(final)
        price = self.plan.start_price
        if price.given:  # OR-6: the player already holds it; nothing is bought, so there is no trade field and no price
            fields = _fields(_plain("Start item", *self.start_accepts()), _plain("Cost per use", GIVEN_SOURCE))
            return StepRow(1, "Start item (given)", fields, self.start_card(), self.anchor(1), final, price.chaos)
        cost = [money(price.chaos)]
        if price.mark:  # OR-8: a thin market's price never stands unmarked
            cost.append(price.mark)
        if price.taken_for:
            cost.append(price.taken_for)
            cost.append(self.wider_advice())
        fields = _fields(
            _plain("Accepts", *self.start_accepts()),
            self.trade_field(),
            _plain("Cost per use", *cost),
        )
        title = f"Buy {self.start_name()}" if price.name else "Start item"
        return StepRow(1, title, fields, self.start_card(), self.anchor(1), final, price.chaos)

    def start_name(self) -> str | None:
        """The bought start item in words: its price name, or, when the price is of a wider item, that item as searched (#937)."""
        price = self.plan.start_price
        if price.searched is not None and self.buy is not None and self.buy.item:
            return self.buy.item
        return self.plan_name(price.name)

    def any_base(self) -> tuple[str, str] | None:
        """(the planned base's name, "any <kind> base") when the start price's search takes any base of the kind, else None (#937)."""
        if self.plan.start_price.searched is None or self.buy is None or self.first is not None:
            return None
        spec = self.buy_spec_words()
        return None if spec is None else (self.data.base_items[self.plan.target.base_id].name, spec)

    def buy_spec_words(self) -> str | None:
        """"Ring, any base" when the buy step's first line names no base type ("Rare, any ring base"), else None."""
        return any_base_words(self.buy)

    def wider_advice(self) -> str:
        """One line a player acts on when the start is priced as a wider item: what to buy, and what the exact item costs (#483, #937)."""
        entry = self.plan.prices.prices.get(self.plan.start_price.name or "")
        p = None if entry is None else entry.provenance
        if p is None or p.exact_listings is None:
            exact = "the exact item's own listings were not read"
        elif p.exact_listings == 0 or p.exact_price is None:
            exact = f"the exact item had {'no' if p.exact_listings == 0 else p.exact_listings} listing{'' if p.exact_listings == 1 else 's'} on {p.date}"
        else:
            listings = f"{p.exact_listings} listing{'' if p.exact_listings == 1 else 's'}"
            exact = f"the exact item had {listings} on {p.date}, at {money(p.exact_price)}{'' if p.exact_listings == 1 else ' on average'}"
        planned = self.plan_name(self.plan.start_price.name) or "the item of the target file"
        return f"what to do: buy the cheapest item the trade link shows; the plan is worked out on {planned}, and {exact}, so a player buys the wider item"

    def step_row(self, step: Step) -> StepRow:
        ask()  # the report's memory net (#1381)
        number = step.number + 1
        action = step.action
        if action is None:
            fields = _fields(_plain("Why", step.reason or "no action is available here"))
            return StepRow(number, "No action", fields, card_of_states(self.ab, step.states, self.reader), self.anchor(number))
        restart = action.label == RESTART
        sure = self.sure(action) and not restart
        removing = [edge for edge in step.edges if sure and self.removes(edge)]  # a sure use's removal is no failure: it is what it is used for
        moving = [edge for edge in step.edges if edge.kind in ("forward", "goal") or edge in removing]
        shown = [edge for edge in step.edges if edge.kind != "failure" or edge in removing]
        failing = [edge for edge in step.edges if edge.kind == "failure" and edge not in removing]
        goal = self.gains(step, moving)
        if not goal and any(edge.kind == "goal" for edge in moving):
            goal = ["the target"]
        one_way = action.label == DRAW_LABEL and len(shown) == 1 and not failing and shown[0].kind not in ("goal", "again")
        if one_way:
            goal = []  # a listing that goes on the same way whatever it came with aims at no mod: the Goal would read as what to look for (#1442)
        never = step.never_finishes
        step_cost = step.step_cost
        leave = math.fsum(edge.chance for edge in step.edges if edge.to != step.number)  # the chance a use takes the item out of the step
        uses = [NEVER_FINISHES] if never else [] if step.uses is None else [self.uses_text(step.uses, step.reached, sure or restart, leave)]
        if uses and not never and step.reached is not None and step.reached < 0.9995:
            uses[0] += f" (reached in {chance_text(step.reached)} of runs)"
        chances = [] if restart else self.chance_lines(step, action, shown, number + 1, sure)
        if restart:
            after = self.start_card()
        else:
            landing = [state for edge in (moving or step.edges) for state in edge.states]
            after = card_of_states(self.ab, list(dict.fromkeys(landing)), self.reader)
        fields = _fields(
            self.reached_from(number),
            _plain("Goal", *goal),
            _plain("Accepts", *self.accepts(action, moving, after)),
            self.trade_field() if restart else None,
            Field((NEXT if len(chances) == 1 else SURE_NEXT) if sure else NEXT if one_way else "Chance per use", tuple(chances)) if chances else None,
            None if one_way else self.tier_field(step, action),  # a listing that goes on the same way: its odds change no choice (crafter, #1442)
            _plain("Cost per use", *self.cost_lines(action)),
            _plain("Uses on average", *uses),
            _plain("Step cost", FREE if self.free(action) else money(step_cost)) if step_cost is not None else None,
            Field(NEXT, tuple(self.restart_lines(step, failing))) if failing and restart else None,
            Field("On failure", tuple(self.failure_lines(step, failing)), "warn") if failing and not restart else None,
            _plain("Note", *self.notes(action, step, restart)),
        )
        final = any(edge.kind == "goal" for edge in step.edges)
        return StepRow(number, self.title(action), fields, after, self.anchor(number), final, step_cost, self.branches(step, after))

    def removes(self, edge: Edge) -> bool:
        """Whether a failure edge is a use that took wanted mods off the item and goes on to a step that acts (not a restart, not a dead end)."""
        if edge.kind != "failure" or not edge.lost or edge.to is None:
            return False
        there = self.flow.steps[edge.to - 1].action
        return there is not None and there.label != RESTART

    def reached_from(self, number: int) -> Field | None:
        """The rows that lead to row `number`, when the row above it is not one of them: a row reached only from a loop or a jump is printed
        between the rows of the straight path, and a player reading down would take it next (R14: steps 11, 12, 13, #1442). Row 2 always
        follows the start of row 1."""
        into = self.__dict__.get("_into")
        if into is None:
            into = {}
            for step in self.flow.steps:
                for edge in step.edges:
                    if edge.to is not None and edge.to != step.number:
                        into.setdefault(edge.to + 1, set()).add(step.number + 1)
            self._into = into
        rows = sorted(into.get(number, ()))
        if number <= 2 or not rows or number - 1 in rows:
            return None
        return Field(REACHED_FROM, tuple(Line(f"step {row}: {self.title_of(row)}", f"#{self.anchor(row)}") for row in rows))

    def title_of(self, row: int) -> str:
        there = self.flow.steps[row - 2].action
        return "no action" if there is None else self.title(there)

    def free(self, action: Action) -> bool:
        """Whether a use of the action consumes nothing a player pays for: the draw of a bought listing, an unveil, a pick (#1442)."""
        if action.label == RESTART:
            return False
        return action.label == DRAW_LABEL or not self.plan.offer_of(action).parts

    @staticmethod
    def uses_text(uses: float, reached: float | None, sure: bool, leave: float | None = None) -> str:
        """The expected uses of a step in a run. A sure action is used once each time the run reaches it, so it reads as one use, and as the
        times a run that reaches the step is there when that is more than once: never as a use that may miss (#984).

        Any other action, when an item comes to the step more than once in a run (a restart buys a new one, a later miss sends it back): the
        uses each time an item comes, the times, and the sum. `leave` is the chance one use takes the item out of the step, so an item that
        comes uses it `1 / leave` times and the step is come to `uses x leave` times in a run (#892: 107 Augmentations are one on each of 107
        helmets, never 107 on one). Without `leave` the sum alone."""
        if not sure:
            if not leave or not math.isfinite(uses):
                return count(uses)
            arrivals = uses * leave
            times = arrivals / reached if reached else arrivals
            if times < 1.05:  # an item comes once: the uses are those on one item
                return count(uses)
            each = count(1.0 / leave).replace("≈ ", "≈")
            run = "in a run that reaches it" if reached else "in a run"
            return f"{count(uses)} in all: an item comes to this step {count(times).replace('≈ ', '≈')} times {run}, {each} {'use' if each in ('1', '≈1') else 'uses'} each time"
        if not reached:  # no reach solved: the times a run is at the step are not known, each of them is still one sure use
            return "1 each time"
        times = count(uses / reached)
        return "1" if times in ("1", "≈ 1") else f"an item comes to this step {times.replace('≈ ', '≈')} times in a run that reaches it, 1 use each time"

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
            proved = f"; {row.note}" if row.note else ""  # a plan the search did not prove the cheapest from this start (#826): what it proved
            lines.append(f"{head}: {candidate.label}: {money(row.total)} in all (start {start} + crafting {money(row.mean_remaining or 0.0)}{proved})")
        return _plain("Start", *lines)

    def proof_field(self) -> Field | None:
        """The goal card's "Proof" field: the planner's one proof sentence (`planner.proof_words`, OR-59), the same as the text report's and the
        JSON's; None for a given route."""
        if self.inp.label != PLANNER_LABEL:
            return None
        words = proof_words(self.plan, self.inp.guide)
        return _plain(PROOF, words.sentence, tone="" if words.case == PROOF_PROVED else "warn")

    @property
    def proof(self) -> Proof | None:
        """How far the planner proved its own plan (`_route_proof`, #1161); None for a given route, which says its own limits."""
        return proof_of(self.plan) if self.inp.label == PLANNER_LABEL else None

    def limit_line(self, limit) -> Line:
        """A limit of the goal card: the planner's in the page's words of its proof (`_route_proof`), a given route's as it is; either with the
        planner's own words said as a player reads them (`_limit_words`, #893, #1514)."""
        return said_line(limit, limit_line) if self.proof is None else planner_limit_line(self.plan, limit)

    def walked(self) -> bool:
        """Whether the planner's own plan is one its search walked to and was stopped on (a `REACHED` limit, #1142); a given route never is."""
        return self.inp.label == PLANNER_LABEL and any(limit.kind == REACHED for limit in self.plan.limits)

    def goal_card(self) -> GoalCard:
        plan, risk = self.plan, self.inp.risk
        shift, divine = plan.start_price.chaos, plan.prices.chaos_per_divine

        def total(value: float) -> str:
            return f"{money(value + shift)} ({_divine(value + shift, divine)})"

        mean = total(risk.mean.value) if math.isfinite(risk.mean.value) else (GAPS if self.inp.reasons else NEVER)
        said = not_shown(risk, risk.p90)  # the sentence of the text report, its own cause first (M7, #512)
        p90 = said if said is not None else f"{total(risk.p90.value)} or less" if math.isfinite(risk.p90.value) else "no finish in 9 runs of 10"
        success = risk.success_probability.value
        interval = self.inp.interval
        uses = price_uses(plan, self.inp.policy, risk.mean.value, chain=self.chain)  # each price the policy buys with, its source and marks (#616, OR-7, OR-23)
        if interval is None:
            approximate = approximate_page_lines(approximate_inputs(plan, self.inp.policy, self.data, uses))
            rule = ()
        else:  # the claims of every route the interval shows, each with its spread; the plan and its interval come first
            approximate = approximate_page_lines((*interval.approximate_inputs, *price_inputs(uses)))
            rule = tuple(_plain(label, *lines) for label, lines in interval.facts(divine))
        approximate = [plain_base_names(self.data, line) for line in approximate]  # a start item priced under a key with a base id is said by its game name (#553)
        fields = _fields(
            _plain("Route", self.inp.label) if self.route_field else None,
            self.proof_field(),
            self.start_field(),
            _plain("Mean", mean),
            _plain("Not shown near the best", NOT_NEAR_BEST, tone="warn") if self.walked() else None,
            _plain("9 runs in 10", p90),
            _plain("Success chance", chance_text(success)) if success < 1 - 1e-9 else None,
            *rule,
            _plain("Approximate inputs", *approximate, tone="warn"),
            _plain("Prices", f"league {plan.prices.league}, fetched {plan.prices.fetched_at:%Y-%m-%d}", *(plain_base_names(self.data, use_line(use)) for use in uses)),
        )
        # the plan's limits are said in the planner's section (they already hold what its own steps cannot show); a given route says its own
        limits = plan.limits if self.inp.label == PLANNER_LABEL else flow_limits(self.chain)
        limits = spent_kinds_named(limits, (use.name for use in uses))  # a kind named by a currency a step pays with is named by its use (#983)
        limits = page_limits(limits, plan.target)  # fossil sets by their game names; socket methods apart on a target with no sockets (#1514)
        leaves_out = tuple(
            Field(group_words(group_title(group[0].kind, title) if self.proof is not None else title), tuple(self.limit_line(limit) for limit in group))
            for title, group in grouped(limits)
        )
        return GoalCard(fields, card_of_target(self.data, plan.target, self.start_item, self.forced), leaves_out)


BENCH_LABEL = "Bench craft "  # how an action label names a bench craft (`actions.bench`)


def limit_line(limit, why: str | None = None, guarantee: str | None = None) -> Line:
    """A limit as one line of the page: its first `SHOWN_LABELS` labels named, the rest in a closed "details" element (OR-13).

    A limit that leaves out more bench crafts than that is said as one short statement, `Not offered: 146 bench crafts, each because its mod
    counts toward no requirement, ...`, and every craft is in the closed element, by its mod (#991): the first three of 146 crafts tell a player nothing
    the count and the cause do not. `why` and `guarantee` replace the limit's cause and guarantee as the page says them (`_route_proof.page_words`).
    """
    labels = limit.labels
    reason = limit.reason() if why is None else why
    guarantee = limit.guarantee if guarantee is None else guarantee
    if len(labels) > SHOWN_LABELS and all(label.startswith(BENCH_LABEL) for label in labels):
        text = f"{limit.what}: {len(labels):,} bench crafts" + (f", each because {reason}" if reason else "") + f". {guarantee}"
        return Line(text, more=tuple(label.removeprefix(BENCH_LABEL) for label in labels), more_title="which crafts")
    # the planner's one sentence of a limit (`limit_text`), with the page's cause and guarantee: a stand-in guarantee is cut off and replaced
    text = limit_text(dataclasses.replace(limit, why=reason, names=(), guarantee=".", approximate=""), SHOWN_LABELS)
    return Line(text[: -len(".")] + guarantee, more=more_labels(limit))


def planner_limit_line(plan: Plan, limit, proof: Proof | None = None) -> Line:
    """One of the planner's limits as its route's goal card says it (#1161): the rounds and the methods they did not finish in the page's own
    words, every other limit in the planner's sentence with its claim of cheapness said as the plan is proved (`_route_proof`)."""
    proof = proof_of(plan) if proof is None else proof
    own = page_line(limit, proof, plan)
    if own is not None:
        return own
    why, guarantee = page_words(limit, proof, plan)
    return said_line(limit, lambda limit: limit_line(limit, why, guarantee))


def said_line(limit, drawn) -> Line:
    """A limit's line (`drawn(limit)`) with the planner's own words said as a player reads them (`_limit_words`, #893, #1514): the two notes on
    what the route draws in the page's sentences, every other sentence and its labels with the planner's words replaced."""
    said = display_text(limit) or state_line_text(limit)
    if said is not None:
        return Line(said)
    line = drawn(limit)
    return dataclasses.replace(line, text=player_words(line.text), more=tuple(player_words(entry) for entry in line.more))


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
    _require_limits(inp.plan)
    view = _View(inp, data, buy, prefix, route_field)
    rows = [view.buy_row(final=not view.flow.steps)]
    rows += [view.step_row(step) for step in view.flow.steps]
    goal = view.goal_card()
    base = view.any_base()
    if base is not None:  # the start is priced as any base of its kind: no card promises the planned base's name or implicit (#937)
        rows = [
            dataclasses.replace(row, after=_any_base(row.after, base), branches=tuple(dataclasses.replace(b, card=_any_base(b.card, base)) for b in row.branches))
            for row in rows
        ]
        goal = dataclasses.replace(goal, target=_any_base(goal.target, base))
    return RouteSection(inp.label, goal, tuple(rows), anchor)


def _any_base(card: ItemCard, base: tuple[str, str]) -> ItemCard:
    """`card` with the planned base (`base[0]`) named as any base of its kind (`base[1]`) and no implicit: the bought base may be another."""
    if card.name != base[0]:
        return card
    return dataclasses.replace(card, name=base[1], implicits=())


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

    Two rows are the same step with the same continuation when they say the same and every link of the given row goes
    to a row that is itself the planner's row the planner's link goes to (found by dropping, until nothing changes, the
    pairs whose links part ways). `merge_sections` asks this to tell a route that is the planner's, one for one, and
    to pair a row with the planner's row that continues alike when several say the same words.
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


def _same_words(policy: RouteSection, given: RouteSection, alike: dict[int, StepRow], prefix: str) -> dict[int, StepRow]:
    """Given row number -> the planner's row that says the same words, whatever follows it (OR-19: only the steps that differ).

    A row of `alike` (same continuation too) keeps its pair; any other given row is paired with the first planner's
    row of the same words. Where such a row goes on differently is said by `_parting`, not by drawing the row again.
    The pair must link from the same lines (`linked`): `_parting` says where a link of the given row lands, and has no
    words for a line that links in one row only.
    """

    def linked(row: StepRow, prefix: str) -> list[bool]:
        return [target is not None for target in _targets(row, prefix)]

    shared: dict[int, StepRow] = {}
    for row in given.rows:
        if row.number in alike:
            shared[row.number] = alike[row.number]
            continue
        for other in policy.rows:
            if _row_key(row) == _row_key(other) and linked(row, prefix) == linked(other, ""):
                shared[row.number] = other
                break
    return shared


def _parting(given: RouteSection, shared: dict[int, StepRow], prefix: str) -> dict[int, list[Line]]:
    """Given row number -> a line per place the shared row goes on to that the planner's row does not go on to.

    The planner's row is drawn with the planner's links. A link of the given row that lands elsewhere (on a row of the
    given route's own, or on another of the planner's rows) is kept here, so the follow-up that differs stays linked.
    """
    by_number = {row.number: row for row in given.rows}
    found: dict[int, list[Line]] = {}
    for number, there in shared.items():
        seen: set[str] = set()
        pairs = zip(_targets(by_number[number], prefix), _targets(there, ""), strict=True)
        for here, theirs in pairs:
            if here is None:
                continue
            landing = shared.get(here)
            if landing is not None and landing.number == theirs:
                continue
            if landing is None:
                line = Line(f"after step {number} this route goes on to its own", f"#{by_number[here].anchor}", f"step {here}")
            else:
                line = Line(f"after step {number} this route goes on to the planner's", f"#{landing.anchor}", f"step {landing.number}")
            if line.href not in seen:
                seen.add(line.href)
                found.setdefault(number, []).append(line)
    return found


def merge_sections(policy: RouteSection, given: RouteSection, name: str) -> tuple[RouteSection, ...]:
    """The planner's section and the given route's: one when they are the same, else the given route's differing steps.

    When every row of the given route is one of the planner's, one for one and with the same continuation
    (`_same_steps`), the planner's section says so in a line and the given route has no section. Otherwise a row that
    says the same words as a planner's row (`_same_words`) is drawn once, in the planner's section: the given route's
    section keeps its differing rows only, lists the steps it shares with the planner (as links, with the planner's
    number; under a shared step that goes on differently, where this route goes on: `_parting`) and sends the links
    that pointed at a shared row to the planner's row. What the answer leaves out is the plan's, said once in the
    planner's section; the given section holds only what its own steps cannot show (`flow_limits`).
    """
    prefix = given.rows[0].anchor.removesuffix("s1") if given.rows else ""
    alike = _same_steps(policy, given, prefix)
    if len(alike) == len(given.rows) == len(policy.rows) == len({row.number for row in alike.values()}):
        head = (Field("Route", (Line(policy.title),)), Field("Given route", (Line(f"Same as the given route ({name})"),)))
        goal = replace(policy.goal, fields=(*head, *policy.goal.fields))
        return (replace(policy, goal=goal),)
    shared = _same_words(policy, given, alike, prefix)
    parting = _parting(given, shared, prefix)

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
        tuple(
            line
            for n, there in shared.items()
            for line in (Line(f"step {n}: the planner's step {there.number}", f"#{there.anchor}"), *parting.get(n, ()))
        ),
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
    guide: float | None = None,
) -> Path:
    """Write the route view of `report`'s plan to `path` (and of the given route, stacked below) and return `path` (`route_page`)."""
    page = route_page(report, data, route=route, given=given, buy_spec=buy_spec, cache_dir=cache_dir, guide=guide)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8", newline="\n")
    return path


def route_page(
    report: Report,
    data: GameData,
    *,
    route: Route | None = None,
    given: RouteResult | None = None,
    buy_spec: BuySpec | None = None,
    cache_dir: Path | None = None,
    guide: float | None = None,
) -> str:
    """The route view of `report`'s plan (and of the given route, stacked below) as one self-contained HTML page: the page
    `write_route_page` writes and the website serves (#961).

    The page makes no request: the trade link is built from `buy_spec` and the stat list in
    `<cache_dir>/trade/stats.json` when that exists. `guide` is the guide's route's cost with the start item when no given route is drawn (the
    benchmark's figure of it): the proof sentence says the plan's cost against it; a given route's own cost takes its place.
    """
    ask(fresh=True)  # the report's memory net, read at the page's start (#1381)
    plan = report.plan
    buy = None
    if buy_spec is not None:
        searchable = [mod for mod in data.mods.values() if mod.text]  # a mod with no text (a veiled one) cannot be searched by
        searched = plan.start_price.searched  # a start priced as a wider item: the step names and links what was priced (#937, OR-7)
        spec = buy_spec if searched is None else searched_spec(buy_spec, searched)
        buy = buy_step(spec, plan.prices.league, searchable, _trade_stats(cache_dir), searched)
    stacked = route is not None and given is not None  # then each section has a heading with its route's name
    guide = given_cost(plan, given) if given is not None else guide
    policy = build_section(route_input(plan, report.interval, guide), data, buy, anchor="policy", route_field=not stacked)
    sections = (policy,)
    if route is not None and given is not None:
        drawn = build_section(
            given_route_input(plan, route, given), data, buy, prefix="g-", anchor="given", route_field=False
        )
        sections = merge_sections(policy, drawn, route.name or Path(route.source).name)
    wider = any_base_words(buy) if plan.start_price.searched is not None else None
    return render_page(Page(page_title(data, plan.target, wider), sections))


def given_cost(plan: Plan, given: RouteResult | None) -> float | None:
    """The given route's mean cost with the start item, as the proof sentence compares the plan's with it; None with no route or no finite cost."""
    if given is None or given.risk is None or not math.isfinite(given.risk.mean.value):
        return None  # a route with a gap never finishes: it has no cost to compare with
    return plan.start_price.chaos + given.risk.mean.value


def any_base_words(buy: BuyStep | None) -> str | None:
    """"Ring, any base" when the buy step's first line names no base type ("Rare, any ring base"), else None."""
    first = buy.accepts[0] if buy is not None and buy.accepts else ""
    marker = ", any "
    if marker not in first or not first.endswith(" base"):
        return None
    kind = first.split(marker, 1)[1][: -len(" base")]
    return f"{kind[:1].upper()}{kind[1:]}, any base"


def page_title(data: GameData, target: Target, wider: str | None = None) -> str:
    """The page's title: the item the route makes, as a player names it ("Elder Shaper Eternal Burgonet, item level 86"), never the target's
    file name (#893, #1442), with its wanted mods in short (`wanted_words`). A start bought as any base of its kind is named as the cards
    name it ("Ring, any base", #937)."""
    influences = " ".join(influence.value.title() for influence in sorted(target.influences))
    base = wider or data.base_items[target.base_id].name
    wanted = wanted_words(data, target)
    return f"Route to craft: {influences + ' ' if influences else ''}{base}, item level {target.item_level}" + (f", with {wanted}" if wanted else "")


_LEAD = re.compile(r"^\+?(?:#|\([\d.]+-[\d.]+\)|[\d.]+)%?\s+(?:(?:to|increased|chance to)\s+)?")  # "reduced" and a minus sign stay: they turn the mod


def short_mod(text: str) -> str:
    """A wanted mod as a title names it: its first line without the figures in front ("+(13-14)% chance to Suppress Spell Damage" is
    "Suppress Spell Damage", "+# to maximum Life" is "maximum Life"); a text with no figure in front stays as it is."""
    first = text.split(" / ")[0]
    return _LEAD.sub("", first, count=1) or first


def _titled(slot) -> str:
    """A wanted slot in the title: its short name, its tier ("T1", "T2 or better") and whether it is fractured or crafted (crafter, #1442)."""
    marks = [mark for mark in ("fractured", "crafted") if mark in slot.marks]
    tier = f" {slot.note}" if re.match(r"^T\d", slot.note or "") else ""
    return f"{' '.join(marks) + ' ' if marks else ''}{short_mod(slot.text)}{tier}"


def wanted_words(data: GameData, target: Target) -> str:
    """The target's wanted mods in short, in the order of its card: each wanted slot, then each group as "1 of A / B / C" (#893)."""
    card = card_of_target(data, target)
    names = [_titled(slot) for slot in (*card.implicits, *card.prefixes, *card.suffixes) if slot.tone == "wanted"]
    for group in card.groups:
        need = re.match(r"at least (\d+) of", group.heading)
        names.append(f"{need.group(1) if need else 'some'} of {' / '.join(dict.fromkeys(short_mod(member.text) for member in group.members))}")
    return ", ".join(dict.fromkeys(names))
