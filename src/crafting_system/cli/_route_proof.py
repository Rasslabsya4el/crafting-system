"""What the route page says the planner's plan is, in a player's words (#1161, #1508, #1512; OR-13, OR-33, OR-40).

The planner's records say how its search ended (`Plan.search`, `_envelope_plan.EnvelopeInfo`) and what each round of its methods did
(`_rounds.RoundRecord`). Its limits are written for every surface at once and in its own terms ("rounds", "gave way", "the time limit of
0 seconds", "within the stated gap of the cheapest", catalog ids such as `harvest-reforge-likelihood`). The page reads the same records and
says three things a player can act on:

* **How sure the plan is** (`Proof`, the goal card's "Proof" field). Searched to the end: the cheapest of the methods searched. Proved within
  the run's gap: within that share of the cheapest, with the figure no plan costs less than, in the same terms as the header's mean (the start
  item's price added, #1508). Stopped by time or memory with a plan in hand: the best plan found in the time given, never "cheapest", and how
  far the search got (the batches of methods it finished, or the figure its proof reached).
* **The sentences of the limits that claim cheapness** say the same: "within 1% of the cheapest" for a proved plan, "the best the search
  found before it stopped, not proved the cheapest" for a stopped one (`guarantee_words`); never "the stated gap".
* **The rounds** are told as batches of methods, each by its methods' game names and how it ended, with no search word (`rounds_line`,
  `untried_line`); an action ruled out by price is said against the plan shown, not against the plan in hand of an early round (#1512).

Only the page's words change: the planner's records, the text report and the JSON are as they were, and no figure is worked out here that the
records do not hold.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from crafting_system.planner import KINDS_NOT_TRIED, PROVED_UNNEEDED, ROUNDS, SHOWN_LABELS, WITHIN_GAP, Limit, Plan, kind_title, limit_text, more_labels
from crafting_system.planner import ROUND_BEATEN as BEATEN
from crafting_system.planner import ROUND_CLOSED as CLOSED
from crafting_system.planner import ROUND_GAVE_WAY as GAVE_WAY
from crafting_system.planner import ROUND_NONE as NONE
from crafting_system.planner import ROUND_REFUSED as REFUSED
from crafting_system.planner import ROUND_STOPPED as STOPPED
from crafting_system.planner import ROUND_WITHIN as WITHIN

EXACT, PROVED_WITHIN, STOPPED_SEARCH, APPROXIMATE = "exact", "within", "stopped", "approximate"
FINISHED = (CLOSED, WITHIN, BEATEN, NONE)  # a round that ended on its own: what it proves holds
PROOF = "Proof"  # the goal card's field
ROUNDS_TITLE = "How the methods were searched"  # the page's title of the group of the rounds' limit (`ROUNDS`)
_CATALOG_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$|^[a-z]+$")  # `fossil-set`, `essence`: a kind of the catalog, not a game name


def _money(chaos: float) -> str:
    from ._route_view import money  # the page's one format of a cost (a module import would be circular)

    return money(chaos)


def gap_text(gap: float) -> str:
    """A gap setting as a player reads it: 0.01 is "1%"."""
    return f"{gap * 100:g}%"


@dataclass(frozen=True)
class Proof:
    """How far the planner proved its plan: `how` is one of `EXACT`, `PROVED_WITHIN`, `STOPPED_SEARCH`, `APPROXIMATE`; `gap` the run's gap
    of a proof within it; `lower` the figure no plan of the methods searched costs less than, after the start item (None when the search
    proved none worth saying); `start` the start item's price; `rounds` the rounds of the methods (empty for one search)."""

    how: str
    gap: float | None = None
    lower: float | None = None
    start: float = 0.0
    rounds: tuple = ()
    mean: float | None = None  # the plan's mean cost after the start item: what the floor is compared with

    @property
    def stopped(self) -> bool:
        return self.how == STOPPED_SEARCH

    def field_text(self) -> str:
        """The goal card's "Proof" line."""
        if self.how == EXACT:
            return "Proved the cheapest of the methods searched; the methods left out are listed below the prices."
        if self.how == PROVED_WITHIN:
            return f"Proved within {gap_text(self.gap or 0.0)} of the cheapest of the methods searched: {self.floor_words()}."
        if self.how == APPROXIMATE:
            return "Proved only to within the gap stated below the prices of the cheapest of the methods searched."
        reach = self.reach_words()
        return (
            "Not proved the cheapest: this is the best plan the search found in the time and memory it was given, and a cheaper one may exist."
            + (f" {reach}" if reach else "")
        )

    def floor_words(self) -> str:
        """The figure no plan costs less than, in the header's terms (start item added) and the crafting part the gap is a share of (#1508)."""
        lower = self.lower or 0.0
        if self.start > 0:
            said = (
                f"no plan of them costs less than {_money(lower + self.start)} in all, that is {_money(lower)} of crafting on top of the "
                f"{_money(self.start)} start item (the {gap_text(self.gap or 0.0)} is of the crafting part)"
            )
        else:
            said = f"no plan of them costs less than {_money(lower)}"
        if self.mean is None:
            return said
        dearer = self.mean - lower
        # the proof may get closer than the gap it was allowed: the floor beside the mean says by how much this plan can be beaten (crafter, #1161)
        return said + (", so no plan of them is cheaper by even 0.01 c" if dearer < 0.005 else f", so this plan is at most {_money(dearer)} dearer than the cheapest")

    def reach_words(self) -> str:
        """How far a stopped search got: the batches of methods it finished, or the figure its proof reached."""
        if self.rounds:
            done = sum(1 for record in self.rounds if record.status in FINISHED)
            return f"It searched the methods in {len(self.rounds):,} batches and finished {done:,} of them (under \"{ROUNDS_TITLE}\")."
        if self.lower is not None and self.lower > 0:
            return f"Its proof got as far as this: no plan of the methods searched costs less than {_money(self.lower + self.start)} in all."
        return ""


def proof_of(plan: Plan) -> Proof:
    """How the planner proved `plan` (`Plan.search`; a plan of another path is exact unless it is approximate)."""
    start = plan.start_price.chaos
    info = plan.search
    if info is None:
        return _proof_of_limits(plan, start)
    rounds = tuple(info.widening)
    lower = info.lower if math.isfinite(info.lower) and info.lower > 0 else None
    mean = plan.risk.mean.value if plan.risk is not None and math.isfinite(plan.risk.mean.value) else None
    if info.exact:
        return Proof(EXACT, lower=lower, start=start, rounds=rounds, mean=mean)
    if info.within is not None:
        return Proof(PROVED_WITHIN, gap=info.within, lower=lower, start=start, rounds=rounds, mean=mean)
    return Proof(STOPPED_SEARCH, lower=lower, start=start, rounds=rounds, mean=mean)


_AT_MOST = re.compile(r"at most ([0-9.]+)% above it")


def _proof_of_limits(plan: Plan, start: float) -> Proof:
    """The proof of a plan with no search record (`Plan.search` is None: a plan of another path, or one whose solution Hinekora's Lock changed,
    `_plan.py`, which drops the packed result and keeps the limits): read off its limits. Rounds that did not all finish (an untried limit, or
    the rounds' head that says so) are a stopped search; rounds that all finished within a gap are that gap; a claim already said "within
    the stated gap" with no rounds is an approximate answer; otherwise the answer is exact (checker, #1161)."""
    limits = plan.limits
    rounds = [limit for limit in limits if limit.kind == ROUNDS and not limit.what.startswith("The given route's methods")]
    if any(limit.kind == KINDS_NOT_TRIED for limit in limits) or any("not every round finished" in limit.what for limit in rounds):
        return Proof(STOPPED_SEARCH, start=start)
    for limit in rounds:
        if (found := _AT_MOST.search(limit.guarantee)) is not None:
            return Proof(PROVED_WITHIN, gap=float(found.group(1)) / 100, start=start)
    if plan.approximation is not None or any(WITHIN_GAP in limit.guarantee for limit in limits):
        return Proof(APPROXIMATE, start=start)
    return Proof(EXACT, start=start)


_CLAIM = re.compile(rf"The plan is {re.escape(WITHIN_GAP)} among ([^.]+)\.")


def guarantee_words(text: str, proof: Proof) -> str:
    """A limit's sentence with its claim of cheapness said as the proof stands: "within 1% of the cheapest" for a proved plan, "the best the
    search found before it stopped, not proved the cheapest" for a stopped one; an exact or approximate answer's words as they are."""
    if proof.how == PROVED_WITHIN:
        return text.replace("the stated gap", gap_text(proof.gap or 0.0))
    if proof.how == STOPPED_SEARCH:
        text = _CLAIM.sub(lambda match: f"Among {match.group(1)}, the plan is the best the search found before it stopped, not proved the cheapest.", text)
        text = text.replace(WITHIN_GAP, "the best found before the search stopped, not proved the cheapest")
        return text.replace("within the stated gap", "only as close to the cheapest as the search got before it stopped")
    return text


_ORB_OF = frozenset({"alchemy", "alteration", "augmentation", "transmutation", "scouring", "annulment", "dominance", "chance", "regret", "binding", "horizons"})


def method_name(label: str) -> str:
    """A method as the game names it: a round's catalog kind (`harvest-reforge-likelihood`) by its title ("Orb of Alchemy" for
    `alchemy-orb`, as the game writes it), a label as it is."""
    if not _CATALOG_ID.match(label):
        return label
    if label.endswith("-orb") and label.removesuffix("-orb") in _ORB_OF:
        return f"Orb of {label.removesuffix('-orb').capitalize()}"
    return kind_title(label)


_ORDINALS = ("first", "second", "third", "fourth", "fifth")


def _methods(record, twin: int = 0) -> str:
    """The batch's methods by their game names; `twin` (1, 2, ...) when another batch holds the same kinds (one kind can be in two groups by
    what its actions change, `_rounds.group_name`, such as the bench crafts that are metamods and the rest): which group this is."""
    names = [method_name(kind) for kind in record.kinds]
    said = ", ".join(names) if names else "no method"
    if twin:
        which = _ORDINALS[twin - 1] if twin <= len(_ORDINALS) else f"{twin}th"
        said += f" ({which} group{', the metamods' if 'metamods' in record.features else ''})"
    return said


def _why(record) -> str:
    """Why the batch holds what it holds, for a batch grown from the plan in hand (`RoundRecord.growth`)."""
    if record.growth is None:
        return ""
    if record.growth.startswith("the seed"):
        return "a first set of methods, for each wanted mod the one of least cost for its chance: "
    return "methods the plan found so far uses or needs: "


def _net(record) -> str:
    """What ran out: the memory, the work of a run counted in states (`StatesMeter`), or the time."""
    return "memory" if "memory" in record.reason else "work" if record.states is not None or "states" in record.reason else "time"


def batch_line(n: int, record, grown: bool = False, twin: int = 0) -> str:
    """One batch of methods as a player reads it: its methods, how much it held, and how it ended (no search word, no seconds of a share)."""
    held = f"{record.offers:,} action{'' if record.offers == 1 else 's'}"
    # a widening round holds its base too (`_rounds`): after a growth, the plan's own methods; otherwise those of the earlier batches
    joined = "" if record.growth is not None or n == 1 else " with the methods of the plan found so far" if grown else " with the methods kept from the earlier batches"
    head = f"Batch {n} ({_why(record)}{_methods(record, twin)}{joined}; {held})"
    plan = f"its best plan costs {_money(record.upper)} of crafting" if record.upper is not None and math.isfinite(record.upper) else ""
    if record.status == CLOSED:
        end = "finished" + (f"; {plan}" if plan else "")
    elif record.status == WITHIN:
        end = f"finished, to within {gap_text(record.within or 0.0)}" + (f"; {plan}" if plan else "")
    elif record.status == BEATEN:
        then = f" (no plan of them costs less than {_money(record.lower)} of crafting)" if record.lower is not None else ""
        by = f" by more than {gap_text(record.within)}" if record.within else ""
        end = f"finished early: these methods cannot beat the plan the search already held{by}{then}"
    elif record.status == NONE:
        end = "finished: these methods alone do not reach the target"
    elif record.status in (STOPPED, GAVE_WAY):
        end = f"not finished: the {_net(record)} set aside for it ran out" + (f"; its best plan so far costs {_money(record.upper)} of crafting" if plan else ", with no plan")
    elif record.status == REFUSED:
        end = "could not be searched"
    else:  # UNTRIED
        end = f"not searched: the {_net(record)} ran out before it"
    if getattr(record, "held_again", False):
        end += "; the last batch searched these methods again with all the others"
    elif not record.carried:
        end += "; the batches after it did not hold these methods"
    return f"{head}: {end}."


def rounds_line(limit: Limit, proof: Proof) -> "Line":
    """The rounds' limit (`ROUNDS`) as the page says it: one sentence of what the batches prove, each batch in the closed element."""
    from ._route_view import Line

    if limit.what.startswith("The given route's methods"):  # `_rounds.judged_route_limit`: the route against the first round
        words = lambda text: text.replace("the first round", "the first batch of methods").replace("The first round", "The first batch of methods").replace("every round", "every later batch")
        return Line(f"{words(limit.what)} ({words(limit.why)}). {words(guarantee_words(limit.guarantee, proof))}")
    records = proof.rounds
    count = len(records)
    done = sum(1 for record in records if record.status in FINISHED)
    if not records:  # a rounds' limit with no records (`_proof_of_limits`): what the batches prove, with no batch named
        if proof.how == STOPPED_SEARCH:
            return Line(
                "The planner searched the methods in batches and did not finish all of them before the time or memory ran out. The plan shown "
                "is the best the search found, not proved the cheapest: a plan that uses the methods of the batches not finished may cost less."
            )
        if proof.how == PROVED_WITHIN:
            return Line(f"The planner searched the methods in batches, the last one with every method. The plan is within {gap_text(proof.gap or 0.0)} of the cheapest of the methods searched.")
        return Line("The planner searched the methods in batches, the last one with every method. No plan of the methods searched costs less than the plan shown.")
    head = f"The planner searched the methods in {count:,} batch{'' if count == 1 else 'es'}"
    # a batch grown from the plan in hand may stop and the proof still hold: it rests on the last batch, which held every method (`all_closed`)
    ended = (" and finished every one" if done == count else f" and finished {done:,} of them; the last one held every method") + _again(records)
    if proof.how == EXACT:
        tail = f"{ended}. No plan of the methods searched costs less than the plan shown."
    elif proof.how == PROVED_WITHIN:
        tail = f"{ended}. The plan is within {gap_text(proof.gap or 0.0)} of the cheapest of the methods searched: {proof.floor_words()}."
    else:
        grown = any(record.growth is not None for record in records)
        tail = (
            f" and finished {done:,} of them before the time or memory ran out. The plan shown is the best the search found, not proved the cheapest: "
            + (
                "each finished batch showed only that no plan made of its own methods costs less than its own best plan, "
                if grown
                else "no plan made only of the methods of the finished batches that the later batches kept costs less than it, "
            )
            + "and a plan that uses the methods of the batches not finished, or of a batch that finished early and was not kept, may cost less."
        )
    grown = any(record.growth is not None for record in records)
    seen = Counter(record.kinds for record in records if record.growth is None)
    order: Counter = Counter()
    lines = []
    for n, record in enumerate(records, start=1):
        twin = 0
        if record.growth is None and seen[record.kinds] > 1:
            order[record.kinds] += 1
            twin = order[record.kinds]
        lines.append(batch_line(n, record, grown, twin))
    lines = tuple(lines)
    return Line(head + tail, more=lines, more_title="each batch", more_apart=True)


def _again(records) -> str:
    """The batches cut short that the last batch searched again with every method (`RoundRecord.held_again`, #1500): what "finished every
    one" rests on for them."""
    again = [n for n, record in enumerate(records, start=1) if getattr(record, "held_again", False)]
    if not again:
        return ""
    names = ", ".join(str(n) for n in again)
    return f" (batch{'es' if len(again) > 1 else ''} {names} ran out of time, and the last batch searched {'their' if len(again) > 1 else 'its'} methods again with all the others)"


def untried_line(limit: Limit, proof: Proof) -> "Line":
    """The limit of the methods the rounds did not finish (`KINDS_NOT_TRIED`), by their game names, with no round's words."""
    from ._route_view import Line

    searched = {method_name(kind) for record in proof.rounds if record.growth is not None and record.status in FINISHED for kind in record.kinds}
    labels = tuple(name for name in dict.fromkeys(method_name(label) for label in limit.labels) if name not in searched)
    said = Limit(
        limit.kind,
        "Not searched to the end",
        f"the batches that held them ran out of the {'work or memory' if 'states' in limit.why else 'time or memory'} given before they finished, "
        "finished early without being kept by the batches after them, or were not reached",
        "The plan shown is the best the search found without them; a plan that uses them may cost less.",
        labels=labels,
    )
    return Line(limit_text(said, SHOWN_LABELS), more=more_labels(said))


_FOUND = re.compile(r"a plan already found \(([0-9,.]+) on average\)")


def price_cut_why(limit: Limit, plan: Plan) -> str | None:
    """The cause of the actions the price cut left out (`_price_cut.price_cut_limit`), against the plan shown (#1512): the figure the limit
    holds is that of the plan in hand when its round ran (235.04 c on R12 beside a plan of 40.93 c), and a use of each costs at least as much as
    buying a new start item and following that plan. The plan shown is said in its place only when it is no dearer than that one (on the
    rounds it always is: the plan shown is the cheapest of them; a cut made before the last search, `_plan.py`, need not be); otherwise the
    figure of the plan the cut was made against is said, as "a plan found during the search". None for any other limit."""
    if limit.kind != PROVED_UNNEEDED or limit.what != "Not searched" or not limit.why.startswith("each costs at least "):
        return None
    found = _FOUND.search(limit.why)
    start = plan.start_price.chaos
    mean = plan.risk.mean.value if plan.risk is not None else math.nan
    against = float(found.group(1).replace(",", "")) if found is not None else math.nan
    if math.isfinite(mean) and (not math.isfinite(against) or mean <= against * (1 + 1e-9) + 1e-9):
        said = f"buying a new start item and following this plan from there ({_money(start + mean)} in all)"
    elif math.isfinite(against):
        said = f"buying a new start item and following a plan found during the search from there ({_money(start + against)} in all)"
    else:
        return None
    return f"a use of each costs at least as much as {said}, whatever the item is at"


def page_line(limit: Limit, proof: Proof, plan: Plan) -> "Line | None":
    """The page's line of one of the planner's limits when the page says it in its own words; None to draw it as the planner wrote it, its
    claim of cheapness said as the proof stands (`guarantee_words`)."""
    if limit.kind == ROUNDS:
        return rounds_line(limit, proof)
    if limit.kind == KINDS_NOT_TRIED:
        return untried_line(limit, proof)
    return None


def page_words(limit: Limit, proof: Proof, plan: Plan) -> tuple[str, str]:
    """(cause, guarantee) of a limit drawn in the planner's own sentence: its claim of cheapness as the proof stands, and a price cut said
    against the plan shown."""
    why = price_cut_why(limit, plan)
    return (limit.reason() if why is None else why), guarantee_words(limit.guarantee, proof)


UNTRIED_TITLE = "Methods not searched to the end"


def group_title(kind: str, title: str) -> str:
    """The page's title of a group of limits: the rounds' group is about how the methods were searched, the untried one about the methods
    whose batches did not finish (some were tried and cut short, so not "not tried")."""
    return ROUNDS_TITLE if kind == ROUNDS else UNTRIED_TITLE if kind == KINDS_NOT_TRIED else title


__all__ = ["PROOF", "Proof", "ROUNDS_TITLE", "UNTRIED_TITLE", "batch_line", "group_title", "guarantee_words", "method_name", "page_line", "page_words", "proof_of"]
