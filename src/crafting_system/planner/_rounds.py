"""Widening the offers in rounds, never losing the plan in hand (#1069, OR-12, OR-13, OR-33, OR-39, OR-40).

An offer can make the model of the item finer on every state: a metamod craft makes it keep the junk by family type and tags, an Exalted Orb
by pool weight, a fracturing orb the fractured marks (`Abstraction.features`). One search over every offer then pays that fineness for every
offer on every state, and on a route whose plan takes seconds it can meet the net with no plan. So the planner searches in rounds:

* **Groups.** An offer adds to the model the features beyond the target's own that a model of that offer alone has (`Abstraction.features`).
  When no offer adds more than the junk count (`FIRST_ROUND`), the offers are one group and one search, as before the rounds (every benchmark
  route on main's default methods). Otherwise each offer is in the group of its kind and the features it adds, and the target's named offers
  join the first group (so do the actions of a route judged against the plan, #1110: `judged_route_limit`); the groups go by the features they add beyond `FIRST_ROUND` (the junk count every reroll needs is no refinement here,
  as in the test for one group), then by their number of offers, then by their kinds' names. So the rounds grow from the offers that refine the
  model least and are fewest, and a kind of thousands of offers (the fossil sets) comes after the small kinds that refine the model as little:
  the plan of the cheap rounds is in hand in seconds. Once the first plan is in hand, the rounds left go by the cheapest a plan of their
  offers with the base can be, from the offers' floors alone, lowest first (`by_floor`, #1135). The order decides only when a group is tried and with
  what share of the time; it drops no offer and no group, and changes nothing the answer proves: a group a run did not reach is listed as not
  tried, with what the plan is proved against without it (OR-13). No kind is named and no count is a cut.
* **Rounds.** Round 1 is the first group. Each later round is the offers of every round that closed before it, plus its own group. It is cut
  against the best plan so far: the exact price cut (`_price_cut`) with that plan's certified upper figure, and the search ends at once when its
  lower figure reaches that figure (`_envelope.Beaten`). A round that closes (exact, within the gap, or shown to reach no plan) with a plan
  cheaper than the plan in hand (beyond the error of either figure), or with no plan in hand when it began, or as the last round, joins
  the base of the next rounds (one that closes with no cheaper plan is set aside: below), and so does one a refusal ended (a solve that failed proves nothing against its offers and took no time from the
  others: a wider round may solve them); one that its share of the time or the memory net stopped is set aside, and its plan is kept if it is
  cheaper. The round that made the first plan joins the base whatever its end (#1135): the plan in hand is made of its offers, and a round
  that cannot hold them cannot widen it (R11's essence round gave way on 2 of 9 runners, and its Exalted round then reached no plan). Until a plan is in hand, a round may take all the time left: the answer must hold a plan (OR-33), and a later round cannot
  give one sooner than the rounds before it. Once a plan is in hand, the share of a round is the run's time left over the rounds left
  (`_plan.search_net`), so time a round does not use goes to the rounds after it; and a round that began with no plan in hand is held to that
  share too once its own search holds a plan: it gives way there, with its plan, unless its last search round still lowered that plan by more
  than the run's gap (`Share`, #1080, #1094), so every group is tried once a plan exists. The rounds left are the groups not yet tried and,
  once a group is set aside and every round so far closed, the last round that holds the set-aside groups again (#1095): that round, owed for the whole proof, keeps its share, where counting only the groups left it no time when the others used theirs.
  Two refusals in a row set the first refused group aside (it would refuse every round after it). A round that begins with a plan in hand
  needs no room kept in its share for its search to make one, so its bound's build may take the whole share, not the quarter a search
  with no plan keeps it to (`RoundCall.held`, `_plan.search_net`, #1099): a short share otherwise cut the build before it was complete,
  and the round stopped on a weak lower figure (R11's Exalted round: a share of about 20 s, a build of about 6 s, cut at 5 s, where the
  complete bound's first plan costs 188.03 c against the 617.28 c in hand). A plan a stopped search walked to (#1142) is not held so: it is
  proved near nothing, and a build that took the whole share left the round's search no time to find a better one (R13). The share itself
  is unchanged. A build that the share ends nearly done (by the offers its model holds) finishes, to at most twice the share, and its
  search makes its first plan (#1135, `abstraction._pattern.Growth`): R11's Exalted round builds in 24 to 28 s on a runner against a share
  of 26 to 27 s, and cut there it kept 617.28 c on 3 of 4 runners. The time past the share comes off the rounds after it; a build far from
  done stops at the share as before.
* **A run counted in states** (`Budget.in_states`: a states net and no time net, the setting of the goldens, fixtures and benchmark records,
  #886). The rounds then count their work in the states their searches knew, never in seconds (`StatesMeter`): the states left are the net
  less the states the rounds before knew, a round with a plan in hand searches with a states net of its share of them, and `Share` reads the
  states its search knew where it would read the clock. Nothing in the rounds reads the clock, so the same target under the same net gives the
  same plan and the same answer on every machine (a round's line names its states, not its seconds).
* **A group that cannot beat the plan in hand is not carried** (#1080, #1091). A round before the last that began with a plan in hand and
  ended beaten, closed (exactly or within the gap) with no cheaper plan, or closed with no plan at all (#1097), proved only that no plan of its offers with the base costs less
  than the plan in hand ("beaten" below covers both); no exact rule lets a later round leave it out and keep the optimum. A plan in hand of 10 that adds mods A
  and B together; group G adds A for 1, group H adds B for 1, the base has no other way to either: G with the base costs 11 and H with the
  base costs 11, both beaten, while G and H together cost 2. "Beaten" says nothing of the plans that join a later group, and no test of
  whether a later group's offers change what its offers do is exact on an item whose every action reads and changes the same affixes. Carrying
  it keeps the proof, at the cost of every later round holding it and of the plan's offers holding it: R05's 1,192 fossil sets, whose round
  closed at the cost of the plan in hand in 2 s, then grew the solve after the net by about 1 GB a minute until the runner died (#1091). So a group beaten before the last round is
  set aside like a stopped one: the rounds after it do not hold it, and the answer names it, with its lower figure over the base it was
  searched with, among the rounds that do not make the plan the cheapest of every method (`RoundRecord.closed`). A beaten last round has no
  round after it and still closes. The proof comes back in one place: when every round closed and groups were set aside so, one last round
  holds them with the base, that is every offer; if it closes the set-aside groups count as closed again and the plan is the cheapest of
  every method, as when they were carried. That round runs only when the whole proof is in reach; its offers become the plan's only when it
  makes a cheaper plan, which then needs them.
* **The answer** is the cheapest plan of every round. It is proved the cheapest over every offer only when every round closed (the last round
  then held every offer); otherwise it says over which methods it is proved, and each round set aside or not tried with its reason and the
  figure no plan of its offers costs less than (OR-13). When no round made a plan, the answer says that no plan of the offered methods
  reaches the target only when every round finished with none (the last then held every offer); when a net stopped a round or left one
  untried, it says no plan was found yet, what the finished rounds showed and what stopped the others (`no_plan_words`, #1168: R13's round 1
  showed no plan of its own methods, the rest were stopped, and the run said no plan of any method reaches the goal).
  A main tree whose every benchmark route has one group never enters the rounds.
"""

from __future__ import annotations

import gc
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from crafting_system.budget import BudgetExceeded

from . import _limits
from ._envelope import Beaten
from ._limits import Limit, WITHIN_GAP

FIRST_ROUND = frozenset({"junk"})  # the features an offer of the first round may add: counting the junk per side is what every reroll needs

CLOSED, WITHIN, BEATEN, NONE, STOPPED, REFUSED, UNTRIED = "closed", "within", "beaten", "no plan", "stopped", "refused", "not tried"
GAVE_WAY = "gave way"  # a round that began with no plan in hand, made one, and had used its share: it gives the rest of the time back (#1080)


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
    give_way: Callable[[object], str | None] | None = None  # asked after each step of the round's search (`Progress`): its reason to yield, or None
    states: int | None = None  # the round's states net when the run counts in states (`StatesMeter`): it replaces the budget's whole figure
    # a plan in hand when the round began, other than one a stopped search walked to (`walked`, #1142): its bound's build may take the
    # round's whole share (`_plan.search_net`, #1099)
    held: bool = False
    floors: bool = False  # only the figure of the group's offers' floors is asked (`Floor`, raised by `_make_plan`): the order of the rounds (#1135)


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
    carried: bool = True  # False: a round before the last that could not beat the plan in hand, whose group later rounds did not hold (`widen`)
    states: int | None = None  # the states its search knew, when the run counts in states (`StatesMeter`): the answer names them, not the seconds

    @property
    def closed(self) -> bool:
        """It closed, and every round after it held its group: only then does the last round's proof cover its offers too."""
        return self.status in (CLOSED, WITHIN, BEATEN, NONE) and self.carried

    def document(self) -> dict:
        """The record as the JSON says it."""
        return {
            "kinds": list(self.kinds), "offers": self.offers, "status": self.status, "reason": self.reason, "lower_without_start": self.lower,
            "plan_cost_without_start": self.upper, "seconds": round(self.seconds, 3), "within": self.within, "features": list(self.features),
            "carried": self.carried, **({} if self.states is None else {"states": self.states}),
        }  # fmt: skip


def kind_of(offer) -> str:
    return offer.kind or offer.label


def round_groups(offers: Sequence, named: Sequence[str], added: Callable[[object], frozenset[str]]) -> tuple[Group, ...]:
    """The groups of `offers` in the order the rounds add them (see the module text). `named` are the run's methods (`PlanSettings.methods`, #405); `added(offer)` the
    features the offer adds to the target's own model. An offer is named by its label, or by its kind when no rule offered it unasked
    (`Offer.blocks`).

    One group, every offer, when the offers refine the model in one way only (each adds no feature beyond `FIRST_ROUND`): the search is one
    search, as before the rounds. Otherwise the target's named offers lead the first group, and every other offer is in the group of its kind
    and the features it adds; the groups go by the features they add beyond `FIRST_ROUND`, then by their number of offers, then by their kinds'
    names, so the rounds grow from the offers that refine the model least and are fewest. No kind is named and no count is a cut: every group gets its round."""
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
    groups.sort(key=lambda group: (len(group.features - FIRST_ROUND), sorted(group.features - FIRST_ROUND), len(group.positions), sorted(group.features), group.kinds))
    first = [i for i in range(len(offers)) if asked[i]]
    if first:  # the named offers are searched from the first round
        head = groups.pop(0) if groups else Group((), (), frozenset())
        positions = tuple(sorted({*first, *head.positions}))
        groups.insert(0, Group(positions, tuple(sorted({kind_of(offers[i]) for i in positions})), frozenset().union(*(features[i] for i in positions))))
    return tuple(groups)


class Floor(Exception):
    """Raised by `_make_plan` for a `RoundCall.floors` call: the figure no plan of the round's offers costs less than, from their floors alone
    (`_pattern_bound.offers_floor`), None when a net ended it."""

    def __init__(self, figure: float | None) -> None:
        super().__init__(figure)
        self.figure = figure


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


class Share:
    """The time rule of a round that begins with no plan in hand (#1080, OR-33, OR-40): it may take all the time left until its search holds a
    plan (the answer must hold one), and from then on it is a round like the others, whose share is the time left at its start over the rounds
    left, this one included (`_plan.search_net`). Its search asks this after each of its own rounds (`_envelope.Net.give_way`): once it holds a
    plan, the round has used that share, and the search's last round did not lower its plan by more than the run's gap (`gap`, OR-39: a fall
    the run would not tell from a plan proved within its gap; with no gap, by nothing), the search stops there with its plan, and what is left
    goes to the rounds after it. Counted in its rounds, not in seconds: a plan that keeps falling by a cent a search round (a trickle, #1094)
    gives way, where under "no cheaper plan" it took every second left. Without it one slow round took every
    second left after its first plan and the rounds after it were never tried (R10: a first plan at 147 s, then 440 s with no cheaper plan, and
    19 rounds not tried; R13 and R09 the same with 2 rounds). A plan still falling is not cut: R11's essences made a first plan of 7,817 c and
    the next search round one of 597 c (a fall of 92%, far above a gap of 1%), and a rule that gave way at the first plan answered 7,837 c on a
    slower runner. No figure here is a count or a cut, and the gap is the run's own (`Budget.gap`): the share is the one every round with a plan in hand gets, and the clock is the run's (`left`, `clock_now`); what stays
    time-dependent is only when the share is used, as for every round."""

    def __init__(self, left: float, rounds: int, began: float, clock_now: Callable[[], float], unit: str = "seconds", gap: float = 0.0) -> None:
        self.share, self.began, self.clock_now, self.gap = left / max(rounds, 1), began, clock_now, max(gap, 0.0)
        self.upper: float | None = None  # the cheapest plan its search held when it last asked
        whole = "the time" if unit == "seconds" else f"the {unit}"  # `StatesMeter`: the run's net is in states, and so is the share
        fell = "made no cheaper plan" if self.gap == 0.0 else f"lowered its plan by no more than the run's gap of {self.gap:.2%}"
        self.said = (
            f"its search made a plan, it had used its share of {whole} ({self.share:,.0f} {unit}, {whole} left over the rounds left), and its "
            f"last search round {fell}: the rest went to the rounds after it"
        )

    def __call__(self, standing) -> str | None:
        """The reason to stop at this standing of the search (`_envelope.Standing`), or None to go on."""
        upper = standing.upper if standing.upper is not None and math.isfinite(standing.upper) else None
        fell = upper is not None and (self.upper is None or upper < self.upper * (1.0 - self.gap))  # by more than the gap: still falling
        if upper is not None and (self.upper is None or upper < self.upper):
            self.upper = upper
        return self.said if upper is not None and not fell and self.clock_now() - self.began >= self.share else None


class StatesMeter:
    """The rounds' clock when the run counts its work in states (`Budget.in_states`: a states net and no time net, #886): the states the rounds'
    searches knew, never the seconds, so the rounds' shares and `Share`'s rule give the same rounds on every machine. `given` is the run's states
    net; the states a round knows are read from its search's standing after each of its search rounds (`saw`) and, once it ends, from its plan's
    count when it has one (`ended`). A round's net is its share of the states left (`net`); nothing here reads the clock."""

    unit = "states"

    def __init__(self, given: int, clock=None) -> None:
        self.given, self.spent, self.running = given, 0, 0
        # the run's account (`budget.Clock.spend`, #1101): each round's states go on it as the round ends, and what other searches spend on it
        # while the rounds run (an Awakener's Orb's donors, searched inside a round) comes off the states left
        self.clock, self.base = clock, (0 if clock is None else clock.spent)

    def left(self) -> float:
        outside = 0 if self.clock is None else self.clock.spent - self.base - self.spent
        return float(max(self.given - self.spent - self.running - outside, 0))

    def now(self) -> float:
        return float(self.spent + self.running)

    def net(self, searches: int) -> int:
        """The states net of a round that shares the states left with `searches` rounds (itself included); at least one state."""
        return max(int(self.left()) // max(searches, 1), 1)

    def saw(self, standing) -> None:
        self.running = max(self.running, int(getattr(standing, "states", 0) or 0))

    def ended(self, touched: int | None) -> int:
        """Close the round: the states it knew (its plan's count, or what its search last stood at), added to the spent ones."""
        known = max(self.running, int(touched or 0))
        self.spent, self.running = self.spent + known, 0
        if self.clock is not None:
            self.clock.spend(known)
        return known


@dataclass(frozen=True)
class Widened:
    """The rounds' outcome: the cheapest plan (None when no round made one), the record of every round, and the error the caller raises when
    no round made a plan and none was stopped (`no_plan_words` says a stop from the records): the first refusal or stop a round raised, else
    the first round's proof that no plan of its offers reaches the target (#1168: a proof of round 1's offers is no proof of a later round's)."""

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
    meter: StatesMeter | None = None,
    gap: float = 0.0,
    floor: Callable[[tuple, RoundCall], float | None] | None = None,
) -> Widened:
    """Run the rounds of `groups` over `offers` (see the module text). `run(round_offers, call)` makes a round's plan (raising what `_make_plan`
    raises, or `Beaten`); `upper_of(plan)` is its certified upper figure, `mean_of(plan)` its mean, `ended(plan)` its status and reason;
    `left()` the run's seconds left (None: no net), `clock_now()` the time. With `meter` the run counts in states (`StatesMeter`): the rounds'
    shares, `Share` and the rounds not tried read it, never `left` or the clock (the clock only times each round for the JSON). `gap` is the
    run's proof gap (`Budget.gap`, OR-39), the fall of a plan `Share` still counts as falling. `floor(round_offers, call)`, when given, is the
    figure no plan of those offers costs less than from their floors alone (`Floor`), or None: once the first plan is in hand, the rounds left go
    by it (`by_floor`)."""
    if meter is not None:
        left, measure = meter.left, meter.now
    else:
        measure = clock_now
    best, best_upper, best_mean, error, proof = None, None, None, None, None
    base: list[int] = []
    records: list[RoundRecord] = []
    refused_last: tuple[int, tuple[int, ...]] | None = None  # the last round, when a refusal ended it: its record's place and its group's offers
    queue = list(groups)
    set_aside: list[tuple[int, Group]] = []  # the groups not carried (could not beat the plan in hand): their record's place and the group
    closing: int | None = None  # the place in the queue of the last round that holds the set-aside groups again, once it is added
    for k, group in _growing(queue):
        ahead = len(queue) - k  # the rounds of the queue from this one on
        # the last round that holds the set-aside groups again is owed while every round so far closed: it is counted among the rounds left,
        # so the rounds before it keep it its share (#1095)
        owed = closing is None and bool(set_aside) and _all_ended(records)
        rest = ahead + (1 if owed else 0)
        out_of_time = (time_left := left()) is not None and time_left <= 0.0
        if out_of_time:
            used = "the run's time was used up" if meter is None else "the run's states net was used up"
            records.extend(RoundRecord(g.kinds, len(g.positions), UNTRIED, f"{used} before this round", None, None, 0.0, states=None if meter is None else 0) for g in queue[k:])
            break
        positions = sorted({*base, *group.positions})
        chosen = tuple(offers[i] for i in positions)
        began = clock_now()
        counted = began if meter is None else measure()
        plan, status, reason, lower, upper, within, touched = None, REFUSED, "", None, None, None, None
        # a plan in hand when the round began; the round's own plan became it. A plan a stopped search walked to (#1142) is executable but proved
        # near nothing: it does not count as held, so the round's build keeps the room for its search a round with no plan keeps (#1099), as
        # before the walk (R13: a walked plan in hand gave the metamod round's build its whole share and its search 0 seconds, 32,813 c for 11,246)
        held, improved = best is not None and not walked(best), False
        first = best is None  # no plan at all in hand: a plan this round makes is the run's first (#1135), a walked one included
        unit = "seconds" if meter is None else meter.unit
        give_way = None if best is not None or time_left is None or rest == 1 else Share(time_left, rest, counted, measure, unit, gap)  # the last round has all the time left
        searches = rest if best is not None else 1
        asked = give_way if meter is None else _seen_by(meter, give_way)  # counted in states: every round's search reports the states it knows
        try:  # no plan in hand: all the time left until its search holds a plan, then its share (`Share`)
            plan = run(chosen, RoundCall(searches, best_upper, k == 0, asked, None if meter is None else meter.net(searches), held))
        except Beaten as beaten:
            status, lower, within = BEATEN, beaten.lower, beaten.within
            touched = getattr(beaten, "states", None)
            reason = (
                "no plan with these methods costs less than the plan in hand"
                + (f" (to within the gap of {beaten.within:.2%} this run allows)" if beaten.within is not None else "")
            )
        except BudgetExceeded as stop:
            status, reason = STOPPED, stop.binding.words()
            error = error or stop
        except NoPlan as none:  # proved: no plan of these offers alone reaches the target; the next round widens them
            status, reason, lower, touched = NONE, str(none), math.inf, states_of(none)
            proof = proof or none.__cause__ or none  # what the run says when every round showed no plan (the last held every offer)
        except Stopped as stop:  # the round's share of the net ended its search before a plan closed: stopped, not refused
            status, reason, lower, touched = STOPPED, stop.reason, stop.lower, states_of(stop)
            error = error or stop.__cause__ or stop
        except ValueError as refusal:  # a `PlanError`: the round's offers reach no plan, or the search refused them
            status, reason, touched = REFUSED, str(refusal), states_of(refusal)
            error = error or refusal
        if plan is not None:
            status, reason = ended(plan)
            if give_way is not None and status == STOPPED and reason.startswith(give_way.said):  # (a counted run may add its build's stop after it)
                status = GAVE_WAY
            search = getattr(plan, "search", None)
            lower, upper = getattr(search, "lower", None), mean_of(plan)
            within = getattr(search, "within", None) if status == WITHIN else None
            if best is None or _cheaper(upper, upper_of(plan), best_mean, best_upper):
                best, best_upper, best_mean, improved = plan, upper_of(plan), upper, True
        if lower is not None and best_upper is not None and k > 0:
            lower = min(lower, best_upper)  # a round cut against the plan in hand proves no more than that plan's figure (`_price_cut`)
        if lower is not None and not math.isfinite(lower):
            lower = None  # a round with no plan states no figure (the JSON holds no infinity)
        touched = getattr(getattr(plan, "search", None), "touched", None) if plan is not None else touched
        known = None if meter is None else meter.ended(touched)  # a round that raised is counted at the states its search knew when it ended
        records.append(RoundRecord(group.kinds, len(chosen), status, reason, lower, upper, clock_now() - began, within, tuple(sorted(group.features)), states=known))
        place = len(records) - 1
        if status == REFUSED and k > 0 and refused_last is not None:
            # two refusals in a row: the group of the round before, which joined the base on its refusal, is set aside and the round after
            # this one widens what the base held before it (#1080): a group whose offers make every solve refuse would refuse every round after
            earlier_place, earlier = refused_last
            base = sorted(set(base) - set(earlier))
            positions = sorted({*base, *group.positions})
            records[earlier_place] = replace(records[earlier_place], reason=records[earlier_place].reason + "; set aside, since the round after it was refused too")
        refused_last = (place, group.positions) if status == REFUSED and k > 0 else None
        if held and not improved and status in (CLOSED, WITHIN, BEATEN, NONE) and ahead > 1:
            # proved unable to beat the plan in hand (beaten, closed with no cheaper plan, or closed with no plan at all): its group is not carried
            # into the rounds after it (#1080, #1091, #1097). Its proof covers its offers with the base only, not with a later group's, so the
            # answer no longer counts it as closed (`RoundRecord.closed`) and names it with its lower figure. Carrying it kept R05's 1,192 fossil
            # sets (their round closed at the plan in hand's cost) in every later round and in the plan's offers, and the solve after the net
            # built each until the runner died
            records[place] = replace(records[place], carried=False)
            set_aside.append((place, group))
        elif k == 0 or status in (CLOSED, WITHIN, BEATEN, NONE, REFUSED) or (first and improved):
            # the first round is the base whatever its end, a refused one too: every later round widens it. So is the round that made the
            # first plan, whatever its end (#1135): the plan in hand is made of its offers, and a later round that cannot hold them cannot
            # widen that plan (R11: the essence round gave way at 52 s, its plan 597.28 c, on 2 of 9 runners, and the Exalted round, without
            # the essences, reached no plan: the answer kept 617.28 c where essences then an Exalted Orb cost 188.03 c)
            base = positions
        if floor is not None and improved and first and len(queue) - k - 1 >= 2 and not ((still := left()) is not None and still <= 0.0):
            # the first plan is in hand: the rounds left (two or more) go by the cheapest a plan of their offers with the base can be, lowest first (#1135)
            searches = len(queue) - k - 1
            call = RoundCall(searches, best_upper, False, None, None if meter is None else meter.net(searches), True, floors=True)
            queue[k + 1 :] = by_floor(queue[k + 1 :], lambda g: figure_of(floor, tuple(offers[i] for i in sorted({*base, *g.positions})), call, left))
        if k == len(queue) - 1 and closing is None and set_aside and _all_ended(records):
            # every round closed, some groups were set aside: one last round holds them with the base, which is then every offer, so
            # the last round again holds every offer and its proof is the whole one (a plan joining a set-aside group with a later one is in it)
            queue.append(Group(tuple(sorted({i for _, g in set_aside for i in g.positions})), tuple(sorted({kind for _, g in set_aside for kind in g.kinds})),
                               frozenset().union(*(g.features for _, g in set_aside))))  # fmt: skip
            closing = len(queue) - 1
        if k == closing and records[place].closed:
            for aside, _ in set_aside:
                records[aside] = replace(records[aside], carried=True, reason=records[aside].reason + "; the last round held them again, with every method")
        plan = None
        gc.collect()  # the round's model goes before the next one is built (memory)
    return Widened(best, tuple(records), error or proof)


def figure_of(floor: Callable[[tuple, RoundCall], float | None], chosen: tuple, call: RoundCall, left: Callable[[], float | None]) -> float | None:
    """The floor figure of `chosen` (`widen`'s `floor`), or None: when the run's time or states are used up (nothing is asked), or when the
    floors pass was refused (a `PlanError` or any model refusal, a `ValueError`: the abstraction of these offers cannot be built, as a round
    records) or a net ended it first (`BudgetExceeded`, `NoPlan`, `Stopped`). The round itself says why when it runs; the order only puts the
    group after those with a figure (#1135)."""
    if (still := left()) is not None and still <= 0.0:
        return None
    try:
        return floor(chosen, call)
    except (ValueError, BudgetExceeded, NoPlan, Stopped):
        return None


def by_floor(groups: Sequence[Group], figure: Callable[[Group], float | None]) -> list[Group]:
    """`groups` ordered by `figure` (the cheapest a plan of the group's offers with the base can be, from their floors alone), lowest first; a
    group with no figure (a net ended its floors) after those with one, and ties in their order (#1135).

    Once a plan is in hand, a round can only matter by a cheaper plan, and the group whose floors allow the cheapest one is the likeliest to hold
    it; a round run after the rounds that cannot beat the plan in hand keeps a share they did not take. R11 without the guide: the Exalted Orb's
    round (its floor 9.64 c over the essences) was the tenth after the essences', behind rounds whose floors were the essences' own (75.2 c):
    those took their whole share and more, and the Exalted round's share fell from 40 s to 20 s, too short for its bound (probe 44104520931,
    runner 5: 617.28 c where its first plan costs 188.03 c). The order changes when a group is tried, never what the answer proves (OR-13)."""
    figures = [figure(group) for group in groups]
    order = sorted(range(len(groups)), key=lambda n: (figures[n] is None, figures[n] if figures[n] is not None else 0.0, n))
    return [groups[n] for n in order]


def _all_ended(records: Sequence[RoundRecord]) -> bool:
    """Every round so far closed (exactly, within the gap, beaten, or with no plan): only then is the last round that holds the set-aside
    groups again due."""
    return all(record.status in (CLOSED, WITHIN, BEATEN, NONE) for record in records)


def states_of(error: BaseException) -> int | None:
    """The states the search knew when it ended, read off the first error of `error`'s chain that carries them (`_envelope.NoPolicy.states`,
    #1101), so a round that raised is counted as exactly as one that made a plan; None when none does."""
    seen: BaseException | None = error
    while seen is not None:
        states = getattr(seen, "states", None)
        if isinstance(states, int) and states > 0:
            return states
        seen = seen.__cause__
    return None


def _seen_by(meter: StatesMeter, give_way: Share | None) -> Callable[[object], str | None]:
    """The rule a round's search asks after each of its rounds when the run counts in states: the meter first reads the states it knows, then
    `Share` (when the round has one) decides on that count."""

    def asked(standing) -> str | None:
        meter.saw(standing)
        return give_way(standing) if give_way is not None else None

    return asked


def _cheaper(mean: float, upper: float | None, best_mean: float, best_upper: float | None) -> bool:
    """Whether a round's plan (its mean, and its certified upper figure) costs less than the plan in hand beyond the error of either figure.
    Two solves of plans of the same cost differ by their solvers' error (OR-32's 1e-6 of an exact mean), so a plain `mean < best_mean` takes a
    round that closed at the plan in hand's cost for a cheaper one, and carries its group (#1080: R05's fossil round, which closed at the
    plan in hand's cost in 2 s). The plan in hand's figure with its error taken off is its mean less the error its upper figure adds; with no
    certified figure of either plan, the means decide."""
    if upper is None or best_upper is None:
        return mean < best_mean
    return upper < best_mean - max(best_upper - best_mean, 0.0)


def _growing(queue: list[Group]):
    """The rounds of `queue` with their place, reading it as it grows (`widen` adds the last round once it knows it is due)."""
    k = 0
    while k < len(queue):
        yield k, queue[k]
        k += 1


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
    line = _round_line(n, record)
    return line if record.carried else line + " (with the methods of the rounds before it; the rounds after it did not hold them)"


def _round_line(n: int, record: RoundRecord) -> str:
    spent = f"{record.seconds:,.0f} s" if record.states is None else f"{record.states:,} states"  # a run counted in states names no seconds
    head = f"round {n} ({group_name(record)}; {record.offers:,} actions offered, {spent})"
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
    if record.status == GAVE_WAY:
        low = f"; no plan with them costs less than {_figure(record.lower)}" if record.lower is not None else ""
        return f"{head}: gave way ({record.reason}), its plan costs {_figure(record.upper)}{low}"
    if record.status == REFUSED:
        return f"{head}: no plan ({record.reason})"
    return f"{head}: not tried, {record.reason}"


def walked(plan) -> bool:
    """Whether a round's plan is one its stopped search walked to toward the goal (a `REACHED` limit, `_envelope_plan.reached_limits`, #1142)."""
    return any(getattr(limit, "kind", None) == _limits.REACHED for limit in getattr(plan, "limits", ()))


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
    net = "the states or the memory" if any(record.states is not None for record in records) else "the time or memory"  # `StatesMeter`
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
            f"these rounds did not finish before their share of {net}, ended at once but were not held by the rounds after them, or were not reached: {{names}}",
            "The plan shown is the best the finished rounds found; these methods may still give a cheaper one, at no less than the figure stated for each.",
            labels=tuple(sorted({kind for _, record in open_rounds for kind in record.kinds})),
            names=tuple(round_line(n, record) for n, record in open_rounds),
        ),
    )


def no_plan_words(records: Sequence[RoundRecord]) -> str | None:
    """What a run whose rounds made no plan says when a net stopped a round or left one untried (#1168, OR-13, OR-33, OR-40): it found no plan
    yet, which does not show that none exists; what the rounds that finished did show (no plan of their methods alone reaches the target);
    every round that did not finish, with the net that stopped it; and what the user can do. None when no round was stopped or left untried:
    every round then showed no plan (the last held every offer: a proof over every method offered) or was refused (the refusal says itself),
    and none either when the last round showed no plan, which is the same proof."""
    if not any(record.status in (STOPPED, UNTRIED) for record in records) or (records and records[-1].status == NONE):
        return None  # (a last round that showed no plan held every offer: the proof, whatever stopped a round before it)
    proved = [group_name(record) for record in records if record.status == NONE]
    shown = (
        f"The rounds that finished showed only that no plan made only of {'; '.join(proved)} reaches the target"
        if proved
        else "No round finished, so nothing is shown about any method"
    )
    unit = "states" if any(record.states is not None for record in records) else "time"  # a run counted in states (`StatesMeter`)
    lines = "; ".join(round_line(n, record) for n, record in enumerate(records, start=1) if record.status != NONE)
    return (
        "no round of the methods made a plan before the search stopped, so this does not show that no plan exists. "
        f"{shown}. Not finished: {lines}. To get a plan, run again with more {unit} or memory, or with fewer methods: "
        "a search over fewer methods is smaller and may finish where this one stopped"
    )


def judged_route_limit(labels: Sequence[str], first: RoundRecord) -> Limit:
    """What the rounds prove against a route judged against their plan (#1110, OR-13). The route's actions (`labels`) lead the first round and
    every round holds them, so the route is a plan of the first round's methods (with the restart and the listing's draw, which every round
    has). When that round finished, no plan of its methods costs less than its own plan, and the plan shown costs no more than that one: the
    route costs no less than the plan shown (to within the gap the round closed within). When it did not finish, nothing is proved between
    the two: the route may cost less than the plan."""
    why = "the given route's actions were offered from the first round on, and every round held them"
    if first.status == CLOSED:
        guarantee = "The first round finished: no plan made only of its methods, the route's among them, costs less than the plan shown, so the route costs no less than it."
    elif first.status == WITHIN:
        guarantee = (
            f"The first round finished within {first.within or 0.0:.2%}: no plan made only of its methods, the route's among them, costs less "
            f"than the plan shown by more than that, so the route costs no less than it, to within {first.within or 0.0:.2%}."
        )
    elif first.status == NONE:
        guarantee = "The first round finished with no plan of its methods alone reaching the target: the route, made of them, does not finish from every item it reaches."
    else:
        guarantee = (
            "The first round did not finish, so the plan shown is not proved to cost no more than the route: the route may cost less, and its "
            "cost is its own, read on its own actions."
        )
    return Limit(_limits.ROUNDS, "The given route's methods were searched from the first round", why, guarantee, labels=tuple(labels))


__all__ = [
    "BEATEN", "CLOSED", "FIRST_ROUND", "GAVE_WAY", "Group", "NONE", "NoPlan", "REFUSED", "RoundCall", "RoundRecord", "STOPPED", "Share", "StatesMeter", "Stopped", "UNTRIED", "WITHIN", "Widened", "all_closed",
    "judged_route_limit", "no_plan_words", "round_groups", "round_line", "rounds_limits", "widen",
]  # fmt: skip
