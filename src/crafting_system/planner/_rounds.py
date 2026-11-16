"""Widening the offers in rounds, never losing the plan in hand (#1069, OR-12, OR-13, OR-33, OR-39, OR-40).

An offer can make the model of the item finer on every state: a metamod craft makes it keep the junk by family type and tags, an Exalted Orb
by pool weight, a fracturing orb the fractured marks (`Abstraction.features`). One search over every offer then pays that fineness for every
offer on every state, and on a route whose plan takes seconds it can meet the net with no plan. So the planner searches in rounds:

* **Groups.** An offer belongs to the group of the features it adds to the model beyond the target's own (`Abstraction.features` of a model of
  that offer alone, less those of a model with none). The first round holds every offer the target names, and every offer that adds no feature
  or only the junk count (`FIRST_ROUND`), less any kind the target does not name whose offers number more than `SIZE_RATIO` times the rest of
  the first round (an action-side size: the search builds every offer at each state it expands, so such a kind alone would make the first round
  that many times slower; the fossil sets, about 9,000 offers against about 150 on R05, R10, R11 and R12 with every method on, where the 60
  essences against about 18 offers of main's defaults stay in it); such a kind is a group of its own. The other groups are ordered by the
  number of features they add, then by their number of offers, then by their kinds' names: the round that refines the model least, and then the
  smallest, comes first. No kind is named here.
* **Rounds.** Round 1 is the first round's offers, with the whole of the run's time. Each later round is the offers of every round that
  closed before it, plus its own group. It is cut against the best plan so far: the exact price cut (`_price_cut`) with that plan's certified
  upper figure, and the search ends at once when its lower figure reaches that plan's cost (`_envelope.Beaten`). A round that closes (exact,
  within the gap, or beaten) joins the base of the next rounds; one that its share of the time, the memory net or a refusal stopped is set
  aside, and its plan is kept if it is cheaper. The share of a round is the run's time left over the rounds left (`_plan.search_net`), so time a
  round does not use goes to the rounds after it.
* **The answer** is the cheapest plan of every round. It is proved the cheapest over every offer only when every round closed (the last round
  then held every offer); otherwise it says over which methods it is proved, and each round set aside or not tried with its reason and the
  figure no plan of its offers costs less than (OR-13). A main tree whose every benchmark route has one group never enters the rounds.
"""

from __future__ import annotations

import gc
import math
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from crafting_system.budget import BudgetExceeded

from . import _limits
from ._envelope import Beaten
from ._limits import Limit, WITHIN_GAP

FIRST_ROUND = frozenset({"junk"})  # the features an offer of the first round may add: counting the junk per side is what every reroll needs
SIZE_RATIO = 10  # a kind with more than this many times the offers of the rest of the first round is a round of its own (see the module text)

CLOSED, WITHIN, BEATEN, STOPPED, REFUSED, UNTRIED = "closed", "within", "beaten", "stopped", "refused", "not tried"


@dataclass(frozen=True)
class Group:
    """Offers searched in one round: their positions among the offers, their catalog kinds and the features they add."""

    positions: tuple[int, ...]
    kinds: tuple[str, ...]
    features: frozenset[str]


@dataclass(frozen=True)
class RoundCall:
    """What a round's plan is made with (`_plan._make_plan(round_call=...)`): the share of the run's time (`searches` rounds left, this one
    included), the certified upper figure of the plan in hand (for the price cut and the search's `beaten_at`), and whether the run's watcher sees it."""

    searches: int
    upper: float | None
    watched: bool
    mean: float | None = None  # the mean of the plan in hand: the search ends once no plan of the round's offers costs less (`_envelope.Beaten`)


@dataclass(frozen=True)
class RoundRecord:
    """One round as the answer states it (OR-13): its group's kinds, its offers, how it ended, the figure no plan of its offers costs less than,
    the cost of its own plan (after the start item), and its seconds."""

    kinds: tuple[str, ...]
    offers: int
    status: str
    reason: str
    lower: float | None
    upper: float | None
    seconds: float
    within: float | None = None  # the gap it closed within, when it closed only within one (the run's gap, OR-32)
    features: tuple[str, ...] = ()  # what its group's offers add to the model (`Abstraction.features`): with the kinds, what names the group

    @property
    def closed(self) -> bool:
        return self.status in (CLOSED, WITHIN, BEATEN)

    def document(self) -> dict:
        """The record as the JSON says it."""
        return {
            "kinds": list(self.kinds), "offers": self.offers, "status": self.status, "reason": self.reason, "lower_without_start": self.lower,
            "plan_cost_without_start": self.upper, "seconds": round(self.seconds, 3), "within": self.within, "features": list(self.features),
        }  # fmt: skip


def kind_of(offer) -> str:
    return offer.kind or offer.label


def round_groups(offers: Sequence, named: Sequence[str], added: Callable[[object], frozenset[str]]) -> tuple[Group, ...]:
    """The groups of `offers`, the first round's first (see the module text). `named` are the target's `actions:`; `added(offer)` the features
    the offer adds to the target's own model. An offer is named by its label, or by its kind when no rule offered it unasked (`Offer.blocks`)."""
    names = set(named or ())
    features = [added(offer) for offer in offers]
    asked = [offer.label in names or (offer.kind in names and offer.blocks is None) for offer in offers]
    first = [i for i, offer in enumerate(offers) if asked[i] or features[i] <= FIRST_ROUND]
    sizes = Counter(kind_of(offers[i]) for i in first if not asked[i])
    big = {kind for kind, count in sizes.items() if count > SIZE_RATIO * (len(first) - count)}
    first = [i for i in first if asked[i] or kind_of(offers[i]) not in big]
    taken = set(first)
    by_key: dict[tuple, list[int]] = {}
    for i, offer in enumerate(offers):
        if i not in taken:
            kind = kind_of(offer)
            by_key.setdefault(("size", kind) if kind in big and features[i] <= FIRST_ROUND else ("features", features[i]), []).append(i)
    later = [
        Group(tuple(positions), tuple(sorted({kind_of(offers[i]) for i in positions})), frozenset().union(*(features[i] for i in positions)))
        for positions in by_key.values()
    ]
    later.sort(key=lambda group: (len(group.features), len(group.positions), group.kinds))
    head = Group(tuple(first), tuple(sorted({kind_of(offers[i]) for i in first})), frozenset().union(*(features[i] for i in first)))
    return (head, *later) if first else tuple(later)


@dataclass(frozen=True)
class Widened:
    """The rounds' outcome: the cheapest plan (None when no round made one), the record of every round, and the first error a round raised
    (re-raised by the caller when no round made a plan)."""

    plan: object | None
    records: tuple[RoundRecord, ...]
    error: BaseException | None


def widen(
    groups: Sequence[Group],
    offers: Sequence,
    run: Callable[[tuple, RoundCall], object],
    *,
    upper_of: Callable[[object], float | None],
    mean_of: Callable[[object], float],
    ended: Callable[[object], tuple[str, str]],
    left: Callable[[], float | None],
    clock_now: Callable[[], float],
) -> Widened:
    """Run the rounds of `groups` over `offers` (see the module text). `run(round_offers, call)` makes a round's plan (raising what `_make_plan`
    raises, or `Beaten`); `upper_of(plan)` is its certified upper figure, `mean_of(plan)` its mean, `ended(plan)` its status and reason;
    `left()` the run's seconds left (None: no net), `clock_now()` the time."""
    best, best_upper, best_mean, error = None, None, None, None
    base: list[int] = []
    records: list[RoundRecord] = []
    for k, group in enumerate(groups):
        rest = len(groups) - k
        out_of_time = (time_left := left()) is not None and time_left <= 0.0
        if out_of_time:
            records.extend(RoundRecord(g.kinds, len(g.positions), UNTRIED, "the run's time was used up before this round", None, None, 0.0) for g in groups[k:])
            break
        positions = sorted({*base, *group.positions})
        chosen = tuple(offers[i] for i in positions)
        began = clock_now()
        plan, status, reason, lower, upper, within = None, REFUSED, "", None, None, None
        try:
            plan = run(chosen, RoundCall(1 if k == 0 else rest, best_upper, k == 0, best_mean))
        except Beaten as beaten:
            status, lower, within = BEATEN, beaten.lower, beaten.within
            reason = (
                "no plan with these methods costs less than the plan in hand"
                + (f" (to within the gap of {beaten.within:.2%} this run allows)" if beaten.within is not None else "")
            )
        except BudgetExceeded as stop:
            status, reason = STOPPED, stop.binding.words()
            error = error or stop
        except ValueError as refusal:  # a `PlanError`: the round's offers reach no plan, or the search refused them
            status, reason = REFUSED, str(refusal)
            error = error or refusal
        if plan is not None:
            status, reason = ended(plan)
            search = getattr(plan, "search", None)
            lower, upper = getattr(search, "lower", None), mean_of(plan)
            within = getattr(search, "within", None) if status == WITHIN else None
            if best is None or upper < best_mean:
                best, best_upper, best_mean = plan, upper_of(plan), upper
        if lower is not None and best_upper is not None and k > 0:
            lower = min(lower, best_upper)  # a round cut against the plan in hand proves no more than that plan's figure (`_price_cut`)
        records.append(RoundRecord(group.kinds, len(chosen), status, reason, lower, upper, clock_now() - began, within, tuple(sorted(group.features))))
        if k == 0 or status in (CLOSED, WITHIN, BEATEN):
            base = positions  # the first round is the base whatever its end: every later round widens it
        plan = None
        gc.collect()  # the round's model goes before the next one is built (memory)
    return Widened(best, tuple(records), error)


def all_closed(records: Sequence[RoundRecord]) -> bool:
    return all(record.closed for record in records)


def _figure(value: float | None) -> str:
    return "none" if value is None or not math.isfinite(value) else f"{value:,.2f} Chaos"


def group_name(record: RoundRecord) -> str:
    """A group as the answer names it: its kinds, and what its offers add to the model (one kind can be in two groups, e.g. the bench crafts
    that add a metamod and those that do not)."""
    kinds = ", ".join(record.kinds) if record.kinds else "no method"
    return f"{kinds} that add {', '.join(record.features)} to the model" if record.features else kinds


def round_line(n: int, record: RoundRecord) -> str:
    """One round as the answer says it."""
    head = f"round {n} ({group_name(record)}; {record.offers:,} actions offered, {record.seconds:,.0f} s)"
    if record.status == CLOSED:
        return f"{head}: finished, its best plan costs {_figure(record.upper)}"
    if record.status == WITHIN:
        return f"{head}: finished within the gap, its plan costs {_figure(record.upper)}"
    if record.status == BEATEN:
        return f"{head}: ended at once: {record.reason}; no plan with them costs less than {_figure(record.lower)}"
    if record.status == STOPPED:
        plan = f", its plan so far costs {_figure(record.upper)}" if record.upper is not None else ", with no plan"
        low = f"; no plan with them costs less than {_figure(record.lower)}" if record.lower is not None else ""
        return f"{head}: stopped ({record.reason}){plan}{low}"
    if record.status == REFUSED:
        return f"{head}: no plan ({record.reason})"
    return f"{head}: not tried, {record.reason}"


def rounds_limits(records: Sequence[RoundRecord], exact: bool, within: float | None) -> tuple[Limit, ...]:
    """What the answer says of its rounds (OR-13): one limit listing every round and what the plan is proved against, and, when a round did not
    close, one limit of the methods set aside or not tried, each with its reason and its lower figure."""
    lines = tuple(round_line(n, record) for n, record in enumerate(records, start=1))
    closed = [group_name(record) for record in records if record.closed]
    if all_closed(records):
        among = "every method offered, searched in rounds"
        guarantee = (
            _limits.claim(among, "Each round held the methods of the rounds before it, so the last one held every method.")
            if exact
            else {"guarantee": f"The plan is {WITHIN_GAP} among {among}, at most {within or 0.0:.2%} above it."}
        )
        return (Limit(_limits.ROUNDS, "The methods were searched in rounds", "the search widened its methods round by round: {names}", **guarantee, names=lines),)
    open_rounds = [(n, record) for n, record in enumerate(records, start=1) if not record.closed]
    proved = "; ".join(closed) if closed else "no method"
    return (
        Limit(
            _limits.ROUNDS,
            "The methods were searched in rounds, and not every round finished",
            "the search widened its methods round by round: {names}",
            f"No plan made only of the methods of the rounds that finished ({proved}) costs less than this plan"
            + (f", to within {within:.2%}" if within else "")
            + ". The rounds that did not finish are listed as not tried: a plan that uses their methods was not ruled out, and may cost less.",
            names=lines,
        ),
        Limit(
            _limits.UNTRIED,
            "Not finished",
            "these rounds did not finish before their share of the time or memory, or were not reached: {names}",
            "The plan shown is the best the finished rounds found; these methods may still give a cheaper one, at no less than the figure stated for each.",
            labels=tuple(sorted({kind for _, record in open_rounds for kind in record.kinds})),
            names=tuple(round_line(n, record) for n, record in open_rounds),
        ),
    )


__all__ = [
    "BEATEN", "CLOSED", "FIRST_ROUND", "Group", "REFUSED", "RoundCall", "RoundRecord", "STOPPED", "UNTRIED", "WITHIN", "Widened", "all_closed",
    "round_groups", "round_line", "rounds_limits", "widen",
]  # fmt: skip
