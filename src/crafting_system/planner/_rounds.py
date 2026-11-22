"""Widening the offers in steps, never losing the plan in hand: scheme S (#1276; #1069, OR-12, OR-13, OR-33, OR-38, OR-39, OR-40).

An offer can make the model of the item finer on every state: a metamod craft makes it keep the junk by family type and tags, an Exalted Orb
by pool weight, a fracturing orb the fractured marks (`Abstraction.features`). One search over every offer then pays that fineness for every
offer on every state, and its bound's build does not complete (research note 2026-11-18-rounds-design, probes e2 and e4: killed at 16 GB). So
the planner searches in steps. What decides a step is whether its bound's build completes: on a complete bound the search's first plan is
the cheapest of its offers within the gap in seconds, on a stopped one it is blind and its first plan can be absurd (the note's probes e6
and e10: the same R04 methods give 32,192.94 c on 7 offers, 898,973,434,471 c on 19).

* **The steps** (`round_groups`). When no offer adds more to the model than the junk count (`FIRST_ROUND`), the offers are one step and one
  search, as before the rounds. Otherwise step 1 is the *seed*: the target's named actions (and a judged route's, #1110), and for every wanted
  mod not on the start item the offers of least cost over their chance of giving it (`_offer_kinds.leaf_providers`). Every other offer is in
  one *family*, fixed by what its action declares to the model (`Abstraction.features`) and by its kind, never by a route: the single orbs
  that refine nothing or add by pool weight (rerolls, moves, additions); the single offers that read only the junk (removals); then one
  family for each rung of `LADDER` (fractures, metamods, a second item, imprints, veiled mods, the swaps and draws by tag or level, and
  every other refinement); then each kind of many offers that refines nothing, the fewest first (the essences, the bench crafts, the fossil
  sets last). Seed and families are the steps, in that order, the same for every target: a step's place can be said before a run. The order
  decides only when a family is tried and with what share; no offer is dropped and no count is a cut.
* **A step** is the offers accepted so far plus one family. Its share of the run's time is the time left over the steps left, this one
  included, never all the time left (`_plan.search_net`), and its bound's build may take the whole share (`Net.step`): a step is accepted only
  when its build completes, so a build cut at a quarter to leave room for a search is the build it would then undo. A step whose build
  completes searches and its family is **accepted**: it stays in every later step, whether its plan was cheaper or not. A step that began
  with a plan in hand and whose build did not complete is **undone** with no search (`_envelope.Incomplete`): the offers accepted before it
  stand, and its family is named in the answer as not finished. A step with no plan in hand searches on the bound it has, its first
  plan's chain past its share if it must (the answer must hold a plan, OR-33): a plan its search makes on a stopped bound is kept when it is the cheapest, said to be unproved, and the step is undone
  all the same. The seed is the base of every later step whatever its end. A step stopped by its share, or refused, is undone too. Time a step
  does not use goes to the steps after it.
* **A family that cannot beat the plan in hand is set aside** (#1080, #1091, #1097): a step that began with a plan in hand and ended beaten,
  closed with no cheaper plan, or closed with no plan at all proved only that no plan of its offers with the base costs less than the plan in
  hand. Carrying it would grow every later step by it (R05's 1,192 fossil sets grew the solve after the net by 1 GB a minute, #1091). A plan in
  hand of 10 that adds mods A and B together; family G adds A for 1, family H adds B for 1, the base has no other way to either: G with the
  base costs 11 and H with the base costs 11, both beaten, while G and H together cost 2 (#1389). So:
* **The second pass.** When the steps are done and time is left, the families set aside or undone are tried once more, in their order, each
  over the offers accepted by then; in this pass a step whose build completes joins whatever its end (nothing is set aside again), so G's step
  holds the base and H's holds G too, and the plan of 2 is found. A refused family is tried there again (#1088). A family of several kinds
  whose step was not finished is tried there one kind a step, smaller steps whose builds may complete. One pass, no loop. The retries owed
  count among the steps left in the first pass, so its last step (the fossil sets) leaves the pass its shares.
* **A run counted in states** (`Budget.in_states`: a states net and no time net, the setting of the goldens, fixtures and benchmark records,
  #886). The steps count their work in the states their searches knew, never in seconds (`StatesMeter`): a step searches with a states net of
  its share of the states left, and its build has the pieces of that whole share. Nothing here reads the clock, so the same target under the
  same net gives the same plan on every machine (a step's line names its states, not its seconds).
* **The answer** is the cheapest plan of every step. It is proved the cheapest over every offer only when the last step held every offer and
  closed (`RoundRecord.covered`); otherwise it is proved only against the methods of the steps that closed, and each family set aside, undone,
  stopped or not tried is named with its reason and the figure no plan of its offers costs less than (OR-13, OR-38). A plan of a step whose
  bound did not complete is said to be unproved even among its own offers (OR-39). When no step made a plan, the answer says that no plan of
  the offered methods reaches the target only when the last step held every offer and showed none; otherwise it says no plan was found yet,
  and what stopped the steps (`no_plan_words`, #1168).
  A main tree whose every benchmark route has one step never enters the steps.

Dropped with the rounds of one kind (#1276, the note's section 5): the groups ordered by features, a round with no plan in hand taking all the
time left (#1268), `Share`'s give-way, the floors' order pass (#1135, #1241), the late room of a nearly done build (#1135, #1175, #1176, #1180),
the quarter of a round's build (#1099), the two-refusals rule (#1088) and the closing round's share (#1095, #1149): each is replaced by the step
accepted or undone by its build, its share of the time left, and the one second pass.
"""

from __future__ import annotations

import gc
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from crafting_system.budget import BudgetExceeded

from . import _limits
from ._envelope import Beaten, Incomplete
from ._limits import Limit, WITHIN_GAP

FIRST_ROUND = frozenset({"junk"})  # the features an offer of the first round may add: counting the junk per side is what every reroll needs
SECOND_ITEM = "second item"  # what an offer that reads a second item adds (an Awakener's Orb: its donor is planned in its step, `_awakener`)
# the rungs of the families of offers that refine the model, least first (`round_groups`): a family is the highest rung of what its offers add
# beyond the junk, and a feature on no rung is of the rung after the last. Fixed by the model's features, the same for every target (#1276)
LADDER: tuple[frozenset[str], ...] = (
    frozenset({"pool weights"}),
    frozenset({"fractures"}),
    frozenset({"metamods"}),
    frozenset({SECOND_ITEM}),
    frozenset({"imprints"}),
    frozenset({"veiled mods", "unveil offer"}),
    frozenset({"families by mod", "draw levels", "draw tags"}),
)

CLOSED, WITHIN, BEATEN, NONE, STOPPED, REFUSED, UNTRIED = "closed", "within", "beaten", "no plan", "stopped", "refused", "not tried"
UNDONE = "undone"  # a step whose bound's build did not complete: its family is not accepted (#1276)
ENDED = (CLOSED, WITHIN, BEATEN, NONE)  # a step that closed: exactly, within the gap, beaten, or with no plan of its offers


@dataclass(frozen=True)
class Group:
    """Offers searched in one step: their positions among the offers, their catalog kinds and the features they add."""

    positions: tuple[int, ...]
    kinds: tuple[str, ...]
    features: frozenset[str]


@dataclass(frozen=True)
class RoundCall:
    """What a step's plan is made with (`_plan._make_plan(round_call=...)`): the share of the run's time (`searches` steps left, this one
    included), the certified upper figure of the plan in hand, and whether the run's watcher sees it. The upper figure, never the plan's mean,
    is what the step is cut against (`_price_cut`) and what its search ends at (`_envelope.Beaten`): the plan in hand costs at most that, so a
    step whose lower figure reaches it can save nothing, to the solver's certified precision (OR-32). `held`: a plan in hand when the step
    began, so a build that does not complete undoes the step with no search (`Net.step`, `_envelope.Incomplete`)."""

    searches: int
    upper: float | None
    watched: bool
    give_way: Callable[[object], str | None] | None = None  # asked after each round of the step's search (`StatesMeter` reads its states there)
    states: int | None = None  # the step's states net when the run counts in states (`StatesMeter`): it replaces the budget's whole figure
    held: bool = False
    first_any: bool = False  # no plan in hand: the step's first plan's chain may run on a bound not built whole (OR-33)
    first_states: int | None = None  # counted in states: the states the steps have left, what a step's first plan's chain may know (`Net.first_states`)


@dataclass(frozen=True)
class RoundRecord:
    """One step as the answer states it (OR-13): its family's kinds, its offers, how it ended, the figure no plan of its offers costs less than,
    the cost of its own plan (after the start item), and its seconds."""

    kinds: tuple[str, ...]
    offers: int
    status: str
    reason: str
    lower: float | None
    upper: float | None
    seconds: float
    within: float | None = None  # the gap it closed within, when it closed only within one (the run's gap, OR-32)
    features: tuple[str, ...] = ()  # what its family's offers add to the model (`Abstraction.features`): with the kinds, what names the family
    carried: bool = True  # False: its family was not in the steps after it (set aside, undone, or a plan of a stopped bound, `widen`)
    states: int | None = None  # the states its search knew, when the run counts in states (`StatesMeter`): the answer names them, not the seconds
    covered: bool = False  # a later step held every offer and closed: its proof covers this step's offers too (`widen`)
    unproved: bool = False  # its plan came from a search on a bound whose build did not complete (OR-39: not proved even among its offers)

    @property
    def closed(self) -> bool:
        """It closed and every step after it held its family, or a later step that held every offer closed: only then does the last step's proof
        cover its offers too."""
        return self.covered or (self.status in ENDED and self.carried)

    def document(self) -> dict:
        """The record as the JSON says it."""
        return {
            "kinds": list(self.kinds), "offers": self.offers, "status": self.status, "reason": self.reason, "lower_without_start": self.lower,
            "plan_cost_without_start": self.upper, "seconds": round(self.seconds, 3), "within": self.within, "features": list(self.features),
            "carried": self.carried, **({} if self.states is None else {"states": self.states}),
            **({"covered": True} if self.covered else {}), **({"unproved": True} if self.unproved else {}),
        }  # fmt: skip


def kind_of(offer) -> str:
    return offer.kind or offer.label


def rung(features: frozenset[str]) -> int:
    """The rung of `LADDER` of an offer that adds `features` beyond the junk (none: -1): the highest of its features' rungs, a feature on no rung
    counting as the rung after the last."""
    found = -1
    for feature in features:
        at = next((n for n, step in enumerate(LADDER) if feature in step), len(LADDER))
        found = max(found, at)
    return found


def round_groups(
    offers: Sequence, named: Sequence[str], added: Callable[[object], frozenset[str]], seed: Sequence[int] | Callable[[], Sequence[int]] = ()
) -> tuple[Group, ...]:
    """The steps of `offers` (see the module text): one step of every offer when no offer adds a feature beyond `FIRST_ROUND`; otherwise the seed
    (the offers the run names, `named`: `PlanSettings.methods`, #405, by label, or by kind when no rule offered it unasked, `Offer.blocks`; and the
    positions `seed`, `_offer_kinds.leaf_providers`, or a function that gives them, asked only when there are steps), then the families.
    `added(offer)` is what the offer adds to the target's own model."""
    names = set(named or ())
    features = [added(offer) for offer in offers]
    if all(found <= FIRST_ROUND for found in features):
        return (Group(tuple(range(len(offers))), tuple(sorted({kind_of(offer) for offer in offers})), frozenset().union(*features)),) if offers else ()
    first = {i for i, offer in enumerate(offers) if offer.label in names or (offer.kind in names and offer.blocks is None)}
    first |= set(seed() if callable(seed) else seed)
    sizes: dict[str, int] = {}
    for offer in offers:
        sizes[kind_of(offer)] = sizes.get(kind_of(offer), 0) + 1
    families: dict[tuple, list[int]] = {}
    for i, offer in enumerate(offers):
        if i in first:
            continue
        beyond = features[i] - FIRST_ROUND
        kind = kind_of(offer)
        if beyond and beyond <= LADDER[0] or (not beyond and sizes[kind] == 1 and "junk" not in features[i]):
            key = (0, 0, "")  # the single orbs that reroll, move or add by pool weight
        elif not beyond and sizes[kind] == 1:
            key = (1, 0, "")  # the single offers that read the junk and add nothing: removals
        elif beyond:
            key = (2 + rung(beyond), 0, "")
        else:
            key = (3 + len(LADDER), sizes[kind], kind)  # a kind of many offers that refines nothing: its own family, the fewest first
        families.setdefault(key, []).append(i)
    steps = [_group(offers, features, sorted(first))] if first else []
    steps += [_group(offers, features, positions) for _key, positions in sorted(families.items(), key=lambda item: item[0])]
    return tuple(steps)


def _group(offers: Sequence, features: Sequence[frozenset[str]], positions: Sequence[int]) -> Group:
    return Group(tuple(positions), tuple(sorted({kind_of(offers[i]) for i in positions})), frozenset().union(*(features[i] for i in positions)))


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


class StatesMeter:
    """The rounds' clock when the run counts its work in states (`Budget.in_states`: a states net and no time net, #886): the states the rounds'
    searches knew, never the seconds, so the steps' shares give the same steps on every machine. `given` is the run's states
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
    unproved: bool = False  # the plan came from a search on a bound not built whole (OR-39)


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
    complete: Callable[[object], bool] = lambda plan: True,
    release: Callable[[object], None] | None = None,
) -> Widened:
    """Run the steps of `groups` over `offers` (see the module text). `run(step_offers, call)` makes a step's plan (raising what `_make_plan`
    raises, `Beaten`, or `Incomplete`); `upper_of(plan)` is its certified upper figure, `mean_of(plan)` its mean, `ended(plan)` its status and
    reason, `complete(plan)` whether its search's bound was built whole; `left()` the run's seconds left (None: no net), `clock_now()` the time.
    With `meter` the run counts in states (`StatesMeter`): the steps' shares and the steps not tried read it, never `left` or the clock (the clock
    only times each step for the JSON). `release(plan)`, when given, is called on each finished step's plan before the next step: it lets go of
    what the plan holds and no later step, nor the answer, needs (#1076: `_plan`'s drops the memos of the plan's abstraction)."""
    if meter is not None:
        left = meter.left
    best, best_upper, best_mean, error, proof, best_unproved = None, None, None, None, None, False
    base: list[int] = []
    records: list[RoundRecord] = []
    queue = list(groups)
    first_pass = len(queue)  # the steps of the first pass; those after it are the second pass (`again`)
    again: list[tuple[int, Group, list[int], str]] = []  # the families set aside or undone in the first pass: their record's place, the family, the offers its step held, how it ended
    retry: dict[int, tuple[int, list[int], str]] = {}  # the place in the queue of a family tried again -> its first record's place, offers and end
    for k, group in _growing(queue):
        second = k >= first_pass
        # the steps of the queue from this one on, and in the first pass the retries the second pass owes so far: the share is the time left
        # over them, so the last step of the first pass (the fossil sets) does not take what the second pass needs
        rest = len(queue) - k + (0 if second else len(again))
        if (time_left := left()) is not None and time_left <= 0.0:
            used = "the run's time was used up" if meter is None else "the run's states net was used up"
            records.extend(RoundRecord(g.kinds, len(g.positions), UNTRIED, f"{used} before this step", None, None, 0.0, features=tuple(sorted(g.features)), carried=False, states=None if meter is None else 0) for g in queue[k:])
            break
        positions = sorted({*base, *group.positions})
        earlier = retry.get(k)
        if earlier is not None and earlier[1] == positions and earlier[2] in ENDED:
            # the second pass, over the very offers its first step held, which closed: it joins with no search (its proof is the same)
            records[earlier[0]] = replace(records[earlier[0]], reason=records[earlier[0]].reason + "; it joined the second pass with no new search (the same methods)")
            base = positions
            if k == len(queue) - 1 and len(positions) == len(offers):  # that closed step held every offer and is the last: the whole proof
                records = [replace(record, covered=True) for record in records]
            continue
        chosen = tuple(offers[i] for i in positions)
        began = clock_now()
        plan, status, reason, lower, upper, within, touched, unproved = None, REFUSED, "", None, None, None, None, False
        held, improved = best is not None, False
        asked = None if meter is None else _seen_by(meter)  # counted in states: every step's search reports the states it knows
        try:
            plan = run(chosen, RoundCall(
                rest, best_upper, k == 0, asked, None if meter is None else meter.net(rest), held, first_any=not held,
                first_states=None if meter is None else max(int(meter.left()), 1),
            ))  # fmt: skip
        except Beaten as beaten:
            status, lower, within = BEATEN, beaten.lower, beaten.within
            touched = getattr(beaten, "states", None)
            reason = (
                "no plan with these methods costs less than the plan in hand"
                + (f" (to within the gap of {beaten.within:.2%} this run allows)" if beaten.within is not None else "")
            )
        except Incomplete as stop:  # a plan in hand and a bound not built whole: undone with no search (`Net.step`)
            status, lower = UNDONE, stop.lower
            reason = f"its count of the cheapest possible cost did not finish in its share ({stop.expanded:,} of {stop.keys:,} cases worked out: {stop.reason}), so it was not searched"
        except BudgetExceeded as stop:
            status, reason = STOPPED, stop.binding.words()
            error = error or _bare(stop)
        except NoPlan as none:  # proved: no plan of these offers alone reaches the target; the next step widens them
            status, reason, lower, touched = NONE, str(none), math.inf, states_of(none)
            proof = proof or _bare(none.__cause__ or none)  # what the run says when every step showed no plan (the last held every offer)
        except Stopped as stop:  # the step's share of the net ended its search before a plan closed: stopped, not refused
            status, reason, lower, touched = STOPPED, stop.reason, stop.lower, states_of(stop)
            error = error or _bare(stop.__cause__ or stop)
        except ValueError as refusal:  # a `PlanError`: the step's offers reach no plan, or the search refused them
            status, reason, touched = REFUSED, str(refusal), states_of(refusal)
            error = error or _bare(refusal)
        if plan is not None:
            status, reason = ended(plan)
            unproved = not complete(plan)
            search = getattr(plan, "search", None)
            lower, upper = getattr(search, "lower", None), mean_of(plan)
            within = getattr(search, "within", None) if status == WITHIN else None
            if best is None or _cheaper(upper, upper_of(plan), best_mean, best_upper):
                best, best_upper, best_mean, improved, best_unproved = plan, upper_of(plan), upper, True, unproved
            if release is not None:
                # a finished step holds its plan and its figures only (#1076), before the next step runs: what its search made on the way (its
                # abstraction's memos) would otherwise stay with the plan in hand through every later step and count against their memory net
                release(plan)
            if unproved:  # a plan of a search on a bound not built whole: kept when cheapest, the step undone (OR-39)
                status, reason = UNDONE, "its count of the cheapest possible cost did not finish in its share, so its plan is not proved even among its own methods" + (f" ({reason})" if reason else "")
        if lower is not None and best_upper is not None and held:
            lower = min(lower, best_upper)  # a step cut against the plan in hand proves no more than that plan's figure (`_price_cut`)
        if lower is not None and not math.isfinite(lower):
            lower = None  # a step with no plan states no figure (the JSON holds no infinity)
        touched = getattr(getattr(plan, "search", None), "touched", None) if plan is not None else touched
        known = None if meter is None else meter.ended(touched)  # a step that raised is counted at the states its search knew when it ended
        whole = len(positions) == len(offers) and status in ENDED  # it held every offer and closed: nothing is left to try again
        if k == 0 or whole:
            accepted = True  # the seed is the base of every later step, whatever its end
        elif plan is not None and not unproved and status in (CLOSED, WITHIN, STOPPED):
            # built whole: accepted, unless it closed with no cheaper plan than the one in hand (it proved its family cannot beat it)
            accepted = second or improved or not held or status == STOPPED
        else:
            accepted = second and status in (BEATEN, NONE) or status == NONE and not held  # the second pass sets nothing aside (G and H)
        if not accepted and not second:
            again.append((len(records), group, positions, status))  # set aside (it cannot beat the plan in hand) or undone: tried once more in the second pass
            if status in ENDED:
                reason = (reason + "; " if reason else "") + "it cannot beat the plan in hand with the methods before it, so it was set aside"
        records.append(RoundRecord(
            group.kinds, len(chosen), status, reason, lower, upper, clock_now() - began, within, tuple(sorted(group.features)),
            carried=accepted, states=known, unproved=unproved,
        ))  # fmt: skip
        if accepted:
            base = positions
        if k == first_pass - 1 and again:
            # the first pass is done: the families set aside or undone are tried once more, in their order, over the offers accepted by then
            for place, family, searched, ended_as in again:
                parts = [family] if ended_as in ENDED or len(family.kinds) < 2 else _by_kind(family, offers)
                for part in parts:
                    retry[len(queue)] = (place, searched if part is family else [], ended_as)
                    queue.append(part)
                said = "tried again in the second pass" + ("" if len(parts) == 1 else f", one kind a step ({len(parts)} steps)")
                records[place] = replace(records[place], reason=records[place].reason + "; " + said)
        if k == len(queue) - 1 and status in ENDED and len(positions) == len(offers):
            # the last step held every offer and closed: its proof is the whole one, and covers every step before it (OR-38)
            records = [replace(record, covered=True) for record in records]
        plan = None
        gc.collect()  # the step's model goes before the next one is built (memory)
    return Widened(best, tuple(records), error or proof, best_unproved)


def _bare(error: BaseException) -> BaseException:
    """`error` and every error of its chain without their tracebacks (#1325). A round's error is kept until the run ends (the first one is what
    the caller raises), and its traceback holds the frames the search raised it from, with their locals: the round's whole search and kernel
    stores (R11: the 11th round began with 4,084 MB held, the previous round's search of 64,672 states held by its `_kernel` frames). What the
    caller reads of it is its type, its words and the counts it carries (`states_of`), not its frames."""
    seen: set[int] = set()
    stack: list[BaseException | None] = [error]
    while stack:
        each = stack.pop()
        if each is None or id(each) in seen:
            continue
        seen.add(id(each))
        each.__traceback__ = None
        stack.extend((each.__cause__, each.__context__))
    return error


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


def _seen_by(meter: StatesMeter) -> Callable[[object], str | None]:
    """The rule a step's search asks after each of its rounds when the run counts in states: the meter reads the states it knows; it never
    stops the search (the step's states net does)."""

    def asked(standing) -> str | None:
        meter.saw(standing)
        return None

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


def _by_kind(family: Group, offers: Sequence) -> list[Group]:
    """A family whose step was not finished, split into one group per kind for the second pass (#1276): a smaller step whose build may
    complete where the whole family's did not (R09: the single orbs together, 15 offers, built 194,000 cases in their share and stopped)."""
    kinds: dict[str, list[int]] = {}
    for i in family.positions:
        kinds.setdefault(kind_of(offers[i]), []).append(i)
    return [Group(tuple(positions), (kind,), family.features) for kind, positions in sorted(kinds.items())]


def _growing(queue: list[Group]):
    """The steps of `queue` with their place, reading it as it grows (`widen` adds the second pass once the first is done)."""
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
    """One step as the answer says it."""
    line = _round_line(n, record)
    return line if record.carried or record.covered else line + " (with the methods of the rounds before it; the rounds after it did not hold them)"


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
    if record.status == UNDONE:
        plan = f", its plan costs {_figure(record.upper)} (not proved)" if record.upper is not None else ""
        low = f"; no plan with them costs less than {_figure(record.lower)}" if record.lower is not None else ""
        return f"{head}: not finished ({record.reason}){plan}{low}"
    if record.status == REFUSED:
        return f"{head}: no plan ({record.reason})"
    return f"{head}: not tried, {record.reason}"


def rounds_limits(records: Sequence[RoundRecord], exact: bool, within: float | None, unproved: bool = False) -> tuple[Limit, ...]:
    """What the answer says of its steps (OR-13, OR-38): one limit listing every step and what the plan is proved against, and, when a step did
    not close, one limit of the methods set aside, not finished or not tried, each with its reason and its lower figure. `unproved`: the plan
    came from a search whose bound was not built whole, so it is not proved even among its own methods (OR-39)."""
    if unproved:
        return _unproved_limits(records)
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


def _unproved_limits(records: Sequence[RoundRecord]) -> tuple[Limit, ...]:
    """The answer of steps whose cheapest plan came from a search on a bound not built whole (OR-39): its cost is exact, its optimality is not
    claimed even among its own methods, and every step that did not close is named."""
    lines = tuple(round_line(n, record) for n, record in enumerate(records, start=1))
    open_rounds = [(n, record) for n, record in enumerate(records, start=1) if not record.closed]
    return (
        Limit(
            _limits.ROUNDS,
            "The methods were searched in steps, and the plan shown is not proved",
            "the search widened its methods step by step: {names}",
            "The plan shown came from a search whose count of the least possible cost did not finish: its cost is what it says, but nothing "
            "is proved of it beyond that, not even against its own methods. A plan that uses any of the methods may cost less.",
            names=lines,
        ),
        Limit(
            _limits.UNTRIED,
            "Not finished",
            "these steps did not finish, were set aside or were not reached: {names}",
            "These methods may still give a cheaper plan, at no less than the figure stated for each.",
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
    if not any(record.status in (STOPPED, UNTRIED, UNDONE) for record in records) or (records and records[-1].status == NONE):
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
    "BEATEN", "CLOSED", "FIRST_ROUND", "Group", "LADDER", "NONE", "NoPlan", "REFUSED", "RoundCall", "RoundRecord", "SECOND_ITEM", "STOPPED", "StatesMeter",
    "Stopped", "UNDONE", "UNTRIED", "WITHIN", "Widened", "all_closed", "judged_route_limit", "no_plan_words", "round_groups", "round_line", "rounds_limits",
    "widen",
]  # fmt: skip
