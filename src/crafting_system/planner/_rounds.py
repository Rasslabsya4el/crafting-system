"""Widening the offers in rounds, never losing the plan in hand (#1069, OR-12, OR-13, OR-33, OR-39, OR-40).

An offer can make the model of the item finer on every state: a metamod craft makes it keep the junk by family type and tags, an Exalted Orb
by pool weight, a fracturing orb the fractured marks (`Abstraction.features`). One search over every offer then pays that fineness for every
offer on every state, and on a route whose plan takes seconds it can meet the net with no plan. So the planner searches in rounds:

* **Groups.** An offer adds to the model the features beyond the target's own that a model of that offer alone has (`Abstraction.features`).
  When no offer adds more than the junk count (`FIRST_ROUND`), the offers are one group and one search, as before the rounds (every benchmark
  route on main's default methods). Otherwise each offer is in the group of its kind and the features it adds, and the target's named offers
  join the first group; the groups go by the features they add, then by their number of offers, then by their kinds' names. So the rounds grow
  from the offers that refine the model least and are fewest, and a kind of thousands of offers (the fossil sets) comes after the small kinds
  that refine the model as little: the plan of the cheap rounds is in hand in seconds. The order decides only when a group is tried and with
  what share of the time; it drops no offer and no group, and changes nothing the answer proves: a group a run did not reach is listed as not
  tried, with what the plan is proved against without it (OR-13). No kind is named and no count is a cut.
* **Rounds.** Round 1 is the first group. Each later round is the offers of every round that closed before it, plus its own group. It is cut
  against the best plan so far: the exact price cut (`_price_cut`) with that plan's certified upper figure, and the search ends at once when its
  lower figure reaches that figure (`_envelope.Beaten`). A round that closes (exact, within the gap, beaten, or shown to reach no plan) joins
  the base of the next rounds; one that its share of the time, the memory net or a refusal stopped is set aside, and its plan is kept if it is
  cheaper. The share of a round is the run's time left over the rounds left (`_plan.search_net`), so time a round does not use goes to the
  rounds after it.
* **The answer** is the cheapest plan of every round. It is proved the cheapest over every offer only when every round closed (the last round
  then held every offer); otherwise it says over which methods it is proved, and each round set aside or not tried with its reason and the
  figure no plan of its offers costs less than (OR-13). A main tree whose every benchmark route has one group never enters the rounds.
"""

from __future__ import annotations

import gc
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from crafting_system.budget import BudgetExceeded

from . import _limits
from ._envelope import Beaten
from ._limits import Limit, WITHIN_GAP

FIRST_ROUND = frozenset({"junk"})  # the features an offer of the first round may add: counting the junk per side is what every reroll needs

CLOSED, WITHIN, BEATEN, NONE, STOPPED, REFUSED, UNTRIED = "closed", "within", "beaten", "no plan", "stopped", "refused", "not tried"


@dataclass(frozen=True)
class Group:
    """Offers searched in one round: their positions among the offers, their catalog kinds and the features they add."""

    positions: tuple[int, ...]
    kinds: tuple[str, ...]
    features: frozenset[str]


@dataclass(frozen=True)
class RoundCall:
    """What a round's plan is made with (`_plan._make_plan(round_call=...)`): the share of the run's time (`searches` rounds left, this one
    included), the certified upper figure of the plan in hand, and whether the run's watcher sees it. The upper figure, never the plan's mean,
    is what the round is cut against (`_price_cut`) and what its search ends at (`_envelope.Beaten`): the plan in hand costs at most that, so a
    round whose lower figure reaches it can save nothing, to the solver's certified precision (OR-32)."""

    searches: int
    upper: float | None
    watched: bool


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
        return self.status in (CLOSED, WITHIN, BEATEN, NONE)

    def document(self) -> dict:
        """The record as the JSON says it."""
        return {
            "kinds": list(self.kinds), "offers": self.offers, "status": self.status, "reason": self.reason, "lower_without_start": self.lower,
            "plan_cost_without_start": self.upper, "seconds": round(self.seconds, 3), "within": self.within, "features": list(self.features),
        }  # fmt: skip


def kind_of(offer) -> str:
    return offer.kind or offer.label


def round_groups(offers: Sequence, named: Sequence[str], added: Callable[[object], frozenset[str]]) -> tuple[Group, ...]:
    """The groups of `offers` in the order the rounds add them (see the module text). `named` are the target's `actions:`; `added(offer)` the
    features the offer adds to the target's own model. An offer is named by its label, or by its kind when no rule offered it unasked
    (`Offer.blocks`).

    One group, every offer, when the offers refine the model in one way only (each adds no feature beyond `FIRST_ROUND`): the search is one
    search, as before the rounds. Otherwise the target's named offers lead the first group, and every other offer is in the group of its kind
    and the features it adds; the groups go by the features they add, then by their number of offers, then by their kinds' names, so the rounds
    grow from the offers that refine the model least and are fewest. No kind is named and no count is a cut: every group gets its round."""
    names = set(named or ())
    features = [added(offer) for offer in offers]
    if all(found <= FIRST_ROUND for found in features):
        return (Group(tuple(range(len(offers))), tuple(sorted({kind_of(offer) for offer in offers})), frozenset().union(*features)),) if offers else ()
    asked = [offer.label in names or (offer.kind in names and offer.blocks is None) for offer in offers]
    by_key: dict[tuple, list[int]] = {}
    for i, offer in enumerate(offers):
        if not asked[i]:
            by_key.setdefault((kind_of(offer), features[i]), []).append(i)
    groups = [Group(tuple(positions), (kind,), found) for (kind, found), positions in by_key.items()]
    groups.sort(key=lambda group: (len(group.features), sorted(group.features), len(group.positions), group.kinds))
    first = [i for i in range(len(offers)) if asked[i]]
    if first:  # the named offers are searched from the first round
        head = groups.pop(0) if groups else Group((), (), frozenset())
        positions = tuple(sorted({*first, *head.positions}))
        groups.insert(0, Group(positions, tuple(sorted({kind_of(offers[i]) for i in positions})), frozenset().union(*(features[i] for i in positions))))
    return tuple(groups)


class NoPlan(Exception):
    """A round's search that showed no plan of its offers reaches the target (`run` raises it from the search's `NoPolicy`): the round closed,
    with no plan, and the next round widens its offers."""


class Stopped(Exception):
    """A round's search that a net stopped before any plan of its offers closed (`run` raises it from the search's `NoPolicy`): `reason` is the
    net's words, `lower` the figure no plan of its offers costs less than (None when unknown). The round is stopped, not refused: its offers
    were not shown to reach no plan."""

    def __init__(self, reason: str, lower: float | None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.lower = lower if lower is not None and math.isfinite(lower) else None


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
            plan = run(chosen, RoundCall(rest, best_upper, k == 0))
        except Beaten as beaten:
            status, lower, within = BEATEN, beaten.lower, beaten.within
            reason = (
                "no plan with these methods costs less than the plan in hand"
                + (f" (to within the gap of {beaten.within:.2%} this run allows)" if beaten.within is not None else "")
            )
        except BudgetExceeded as stop:
            status, reason = STOPPED, stop.binding.words()
            error = error or stop
        except NoPlan as none:  # proved: no plan of these offers alone reaches the target; the next round widens them
            status, reason, lower = NONE, str(none), math.inf
            error = error or none.__cause__ or none  # what the run says when no round made a plan
        except Stopped as stop:  # the round's share of the net ended its search before a plan closed: stopped, not refused
            status, reason, lower = STOPPED, stop.reason, stop.lower
            error = error or stop.__cause__ or stop
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
        if k == 0 or status in (CLOSED, WITHIN, BEATEN, NONE):
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
    if record.status == NONE:
        return f"{head}: finished, no plan with them alone reaches the target"
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
    "BEATEN", "CLOSED", "FIRST_ROUND", "Group", "NONE", "NoPlan", "REFUSED", "RoundCall", "RoundRecord", "STOPPED", "Stopped", "UNTRIED", "WITHIN", "Widened", "all_closed",
    "round_groups", "round_line", "rounds_limits", "widen",
]  # fmt: skip
