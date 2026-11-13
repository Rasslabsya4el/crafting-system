"""The prices a plan buys with, their sources and their marks: plain facts and approximate inputs (#616, #598 point 2, OR-7, OR-8, OR-12, OR-23).

`price_uses(plan, policy)` lists, for the policy a report shows, every priced resource its actions consume (and the start item, when
it is bought): the price, where it came from (`prices.provenance`), how many units the plan expects to use of it, and the marks
`prices.price_marks` gives it. The text report and the page print that list under "Prices"; `price_inputs` turns the marked ones into
the "Approximate inputs" the answer already prints (OR-23), so every channel that lists approximate inputs lists these too.

The expected uses are solved only for a price that could be marked for depth: a resource whose depth in units is at least the most
the plan could buy (its whole expected cost over the price) needs no solve, and one with no depth recorded needs none either.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.prices import CHAOS_ORB, DIVINE_ORB
from crafting_system.prices.price_marks import PriceMark, chaos_text, judged_depth, price_marks, provenance_of, units_text
from crafting_system.prices.provenance import WIDER
from crafting_system.risk import expected_totals
from crafting_system.solver import Action
from crafting_system.planner import Plan

from ._reach import policy_states

@dataclass(frozen=True)
class PriceUse:
    """One priced resource of the answer: what it costs, where the price is from, what the plan expects to use, and why it is marked (if it is)."""

    name: str
    chaos: float
    source: str  # in a player's words: "poe.ninja exchange, Allflame, 2026-11-07"
    depth: float | None  # the units behind the price; None when not recorded
    uses: float | None  # the units the plan expects to buy; None when not solved
    marks: tuple[PriceMark, ...]
    wider: str | None = None  # what a stand-in price was read for, in words; None for the exact item

    @property
    def approximate(self) -> bool:
        return bool(self.marks)


def _labels(plan: Plan, policy: Mapping) -> dict[str, Action]:
    """One action of the policy for each offer label it takes in a state it reaches from the start."""
    found: dict[str, Action] = {}
    for state in policy_states(plan.start, policy, plan.is_goal):
        action = policy.get(state)
        if action is not None and not plan.is_goal(state):
            found.setdefault(action.label, action)
    return found


def _counts(plan: Plan, labels: Mapping[str, Action]) -> dict[str, dict[str, int]]:
    """Resource -> {offer label -> units one use of the offer consumes}, for the resources of the labels."""
    counts: dict[str, dict[str, int]] = {}
    for label, action in labels.items():
        for name, count, _, _ in plan.offer_of(action).parts:
            if count:
                counts.setdefault(name, {})[label] = count
    return counts


def price_uses(plan: Plan, policy: Mapping | None, mean: float | None = None, *, solve_uses: bool = True, all_uses: bool = False) -> tuple[PriceUse, ...]:
    """The priced resources the policy buys with, in the order its actions are first met (the start item first when it is bought).

    A resource with no entry in the price file (a Chaos Orb, a Divine Orb at the file's rate, a start price given on the command line)
    is not listed: it carries no source to show. With `policy` None, or `solve_uses` False, no expected use is solved and a depth is
    compared with one unit, the least a plan that takes the action buys. `mean` is the policy's expected cost without the start item
    (default: the plan's own, `Plan.mean_remaining`); a given route passes its own, which the plan's optimum does not bound. With `all_uses`
    the expected uses of every resource are solved, not only of those whose depth could matter (a report of what a plan buys).
    """
    prices = getattr(plan, "prices", None)
    if prices is None:  # a stand-in plan of a test has no price file
        return ()
    labels = _labels(plan, policy) if policy is not None else {}
    counts = _counts(plan, labels) if labels else {}
    names = [name for name in dict.fromkeys(counts) if name not in (CHAOS_ORB, DIVINE_ORB) and name in prices.prices]
    start_name = plan.start_price.name if plan.start_price.bought else None
    if start_name is not None and start_name in prices.prices and start_name not in names:
        names.insert(0, start_name)
    # the most a plan can buy of a resource is its whole expected cost over the resource's price: a price deeper than that needs no solve
    try:
        spent = plan.mean_remaining if mean is None else mean
    except KeyError:  # a plan that was not solved (a stand-in for a route's own policy)
        spent = math.inf
    ceiling = spent + (plan.start_price.chaos if plan.start_price.bought else 0.0)
    need: list[str] = []
    for name in names:
        entry = prices.prices[name]
        depth = judged_depth(entry, prices)  # a recipe price is as deep as the market price it rests on (#885)
        if depth is not None and depth < ceiling / entry.chaos:
            need.append(name)
    if all_uses:
        need = list(names)
    solved: dict[str, float | None] = {}
    if need and solve_uses and policy is not None and labels:
        ordered = list(labels)
        estimates = expected_totals(
            policy, plan.start, plan.is_goal, [(lambda action, label=label: 1.0 if action.label == label else 0.0) for label in ordered]
        )
        per_label = dict(zip(ordered, (e.value for e in estimates), strict=True))
        for name in need:
            total = math.fsum(per_label[label] * count for label, count in counts.get(name, {}).items())
            if name == start_name:
                total += 1.0  # the first purchase of the start item, before any restart
            solved[name] = total
    found = []
    for name in names:
        entry = prices.prices[name]
        provenance = provenance_of(entry, prices)
        uses = solved.get(name)
        marks = price_marks(entry, prices, uses if uses is not None or name in need else ceiling / entry.chaos)
        source = "no source recorded" if provenance is None else provenance.words
        depth = None if provenance is None else provenance.depth
        wider = None if provenance is None or provenance.item != WIDER else (provenance.for_item or "")
        found.append(PriceUse(name, entry.chaos, source, depth, uses, marks, wider))
    return tuple(found)


def use_line(use: PriceUse) -> str:
    """One price as a person reads it: "Prismatic Fossil: 5.87 Chaos, poe.ninja exchange, Allflame, 2026-11-07; approximate: price on 3.3 units"."""
    line = f"{use.name}: {chaos_text(use.chaos)} Chaos, {use.source}"
    if use.wider is not None:
        line += ", taken for a wider item" + (f" ({use.wider})" if use.wider else "")
    if use.depth is not None:
        line += f", {units_text(use.depth)} units behind it"
        if use.uses is not None:
            line += f", the plan buys about {units_text(use.uses)}"
    if use.marks:
        line += "; approximate: " + "; ".join(mark.reason for mark in use.marks)
    return line


def price_lines(uses: tuple[PriceUse, ...]) -> list[str]:
    """The text lines of the prices an answer buys with, one to a price, in the report's indent."""
    return [f"  {use_line(use)}" for use in uses]
