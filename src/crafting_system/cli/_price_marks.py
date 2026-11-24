"""The prices a plan buys with, their sources and their marks: plain facts and approximate inputs (#616, #598 point 2, OR-7, OR-8, OR-12, OR-23).

`price_uses(plan, policy)` lists, for the policy a report shows, every priced resource its actions consume (and the start item, when
it is bought): the price, where it came from (`prices.provenance`), how many units the plan expects to use of it, and the marks
`prices.price_marks` gives it. The text report and the page print that list under "Prices"; `price_inputs` turns the marked ones into
the "Approximate inputs" the answer already prints (OR-23), so every channel that lists approximate inputs lists these too.

The expected uses are solved only for a price that could be marked for depth: a resource whose depth in units is at least the most
the plan could buy (its whole expected cost over the price) needs no solve, and one with no depth recorded needs none either. They are the
expected visits of the policy's item states summed by the action each takes (`expected_uses`): the visits of the route page's own solve
(`_route_flow._solved`, sparse, a block of edges at a time, made once for a chain and kept on it), so the price list and the uses of the
page's steps are one number. Before #1381 they were solved by `risk.expected_totals`, dense on each cycle of the policy shown: on R20's
lumped view (28,773 blocks in one cycle) that is a matrix of 6.6 GB, copied twice, and the kernel killed the run after its plan was made.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.prices import CHAOS_ORB, DIVINE_ORB
from crafting_system.prices.price_marks import PriceMark, chaos_text, judged_depth, price_marks, provenance_of, units_text
from crafting_system.prices.provenance import WIDER
import numpy as np

from crafting_system.solver import Action
from crafting_system.planner import Plan

from ._reach import policy_states
from ._route_flow import Chain, _solved, chain_of_policy

UNIT_WORDS = "the unit every price is in"
RATE_WORDS = "the price file's Divine rate"


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


def price_uses(
    plan: Plan, policy: Mapping | None, mean: float | None = None, *, solve_uses: bool = True, all_uses: bool = False, chain: Chain | None = None
) -> tuple[PriceUse, ...]:
    """The priced resources the policy buys with, in the order its actions are first met (the start item first when it is bought).

    Every currency a step spends is listed, a bench craft's included (#983, OR-7): the Chaos Orb as the unit every price is in, the
    Divine Orb by its row of the file or, with none, as the file's rate, as `planner._offers.price_offers` prices them. Any other resource
    with no entry in the price file (a start price given on the command line) is not listed: it carries no source to show. With `policy` None, or `solve_uses` False, no expected use is solved and a depth is
    compared with one unit, the least a plan that takes the action buys. `mean` is the policy's expected cost without the start item
    (default: the plan's own, `Plan.mean_remaining`); a given route passes its own, which the plan's optimum does not bound. With `all_uses`
    the expected uses of every resource are solved, not only of those whose depth could matter (a report of what a plan buys). `chain` is
    `policy` on item states when the caller holds it (a lumped view's item chain, `_route_chain.chain_of_plan`); else it is made from `policy`.
    """
    prices = getattr(plan, "prices", None)
    if prices is None:  # a stand-in plan of a test has no price file
        return ()
    labels = _labels(plan, policy) if policy is not None else {}
    counts = _counts(plan, labels) if labels else {}
    names = [name for name in dict.fromkeys(counts) if name in prices.prices or name in (CHAOS_ORB, DIVINE_ORB)]
    start_name = plan.start_price.name if plan.start_price.bought else None
    made = getattr(plan.start_price, "made", None) if plan.start_price.bought else None
    # what the first start item is bought as: the item itself, or the goods of the recipe that makes it (an Awakener's Orb's, #1523)
    first: dict[str, int] = {name: count for name, count, _, _ in made.goods} if made is not None else {start_name: 1} if start_name else {}
    for name in reversed(list(first)):
        if name in prices.prices and name not in names:
            names.insert(0, name)
    # the most a plan can buy of a resource is its whole expected cost over the resource's price: a price deeper than that needs no solve
    try:
        spent = plan.mean_remaining if mean is None else mean
    except KeyError:  # a plan that was not solved (a stand-in for a route's own policy)
        spent = math.inf
    ceiling = spent + (plan.start_price.chaos if plan.start_price.bought else 0.0)
    need: list[str] = []
    for name in names:
        if name not in prices.prices:
            continue  # a Chaos or Divine Orb the file has no row for: a unit, with no depth to judge
        entry = prices.prices[name]
        depth = judged_depth(entry, prices)  # a recipe price is as deep as the market price it rests on (#885)
        if depth is not None and depth < ceiling / entry.chaos:
            need.append(name)
    if all_uses:
        need = list(names)
    solved: dict[str, float | None] = {}
    if need and solve_uses and policy is not None and labels:
        per_label = expected_uses(chain if chain is not None else chain_of_policy(plan.start, policy, plan.is_goal), labels)
        for name in need:
            total = math.fsum(per_label[label] * count for label, count in counts.get(name, {}).items())
            total += first.get(name, 0)  # the first purchase of the start item (or of its recipe's goods), before any restart
            solved[name] = total
    found = []
    for name in names:
        uses = solved.get(name)
        if name == CHAOS_ORB:  # the unit every price is in: it has no market of its own, and no mark (price_offers prices it at 1)
            found.append(PriceUse(name, 1.0, UNIT_WORDS, None, uses, ()))
            continue
        if name not in prices.prices:  # a Divine Orb the file lists no row for is priced at the file's rate (price_offers)
            found.append(PriceUse(name, prices.chaos_per_divine, f"{RATE_WORDS}, {prices.league}, {prices.fetched_at:%Y-%m-%d}", None, uses, ()))
            continue
        entry = prices.prices[name]
        provenance = provenance_of(entry, prices)
        marks = price_marks(entry, prices, uses if uses is not None or name in need else ceiling / entry.chaos)
        source = "no source recorded" if provenance is None else provenance.words
        depth = None if provenance is None else provenance.depth
        wider = None if provenance is None or provenance.item != WIDER else (provenance.for_item or "")
        found.append(PriceUse(name, entry.chaos, source, depth, uses, marks, wider))
    return tuple(found)


def expected_uses(chain: Chain, labels) -> dict[str, float]:
    """The expected number of uses of each of `labels` in one run of the policy `chain` is: the expected visits of its states summed by the
    label of the action each takes (`_route_flow._solved`). Infinite for every label when the policy has no finite mean (a reachable state that
    cannot finish, or visits that could not be solved), as `risk.expected_totals` said it; zero for a start that already is a goal."""
    if chain.m == 0:
        return {label: 0.0 for label in labels}
    done = _solved(chain)
    if not (done.solved and bool(done.finishing.all())):
        return {label: math.inf for label in labels}
    per_key = np.bincount(chain.key, weights=done.visits, minlength=len(chain.keys))
    index = {key: k for k, key in enumerate(chain.keys)}
    return {label: float(per_key[index[("action", label)]]) if ("action", label) in index else 0.0 for label in labels}


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
