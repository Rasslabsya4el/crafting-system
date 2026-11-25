"""The one sentence that says how sure a plan is, in a player's words (#1576, OR-59): the route page's "Proof" field, the text report's
"Proof:" line and the JSON's `proof` say it from here, and nothing else words the answer's proof.

Four cases, no more:

* **Proved** (`PROVED`): the search held every action open to the craft together and finished, and its plan is proved within 1% of the
  cheapest (`budget.PROOF_GAP`; exact when the gap is 0). Only then does the sentence say "proved" without a qualifier.
* **Best found, not proved** (`BEST_FOUND`): any other plan. The sentence says how many of the actions open to the craft were searched to the
  end together with the plan (`tried_together`): the most actions of a group of methods that finished with the plan in hand, from the group
  whose plan the run ended with on; a group that finished early because it could not beat the plan counts, a group that showed only that its
  methods alone do not reach the target does not (it did not hold the plan's actions). With a guide's route, its cost beside the plan's.
* **No plan** (`NO_PLAN`): the search stopped before any plan reached the target; that is not a proof that none does (OR-33).
* **No usable plan** (`NO_USABLE`, #1628): the search ended with a plan one of whose steps expects more uses than the run's setting
  (`_usable`, OR-12's stop-and-say-so net): the answer is no plan, and the sentence gives that plan's cost, the step, its uses and what was
  considered (`unusable_words`).

The rule (OR-59, owner 2026-11-24): a craft is shown as proved only when the plan is proved within 1% over every method; otherwise "best plan
found, not proved", what was considered, and the cost against the guide. The words carry no search term (round, bound, key, envelope); "a group
of methods" is the most technical phrase they use.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from crafting_system.budget import PROOF_GAP

from . import _limits
from ._envelope_plan import certificate_gap
from ._rounds import BEATEN, CLOSED, WITHIN

PROVED, BEST_FOUND, NO_PLAN = "proved", "best found, not proved", "no plan"
NO_USABLE = "no usable plan"  # the search ended with a plan no player would follow (`_usable`, #1628)
NO_PLAN_SENTENCE = (
    "No plan found: the search stopped before it found any way to reach the target. That does not mean there is none; a longer run may find one."
)
_SAME = 1e-9  # two costs of a round's plan and the plan shown read the same within this share
_SOLVE_WITHIN = "The search stopped once the plan was proved close to the cheapest"  # `_envelope_plan.envelope_limits`
_ALLOWS = re.compile(r"the gap this run allows is ([0-9.]+)%")
_AT_MOST = re.compile(r"at most ([0-9.]+)% above it")


@dataclass(frozen=True)
class ProofWords:
    """How sure the plan is: `case` one of `PROVED`, `BEST_FOUND`, `NO_PLAN`; `sentence` the one sentence every output prints; `open` the
    actions open to the craft; `tried_together` how many of them were searched to the end together with the plan (all of them when proved);
    `guide` the guide's route's cost with the start item, when one was given."""

    case: str
    sentence: str
    open: int = 0
    tried_together: int = 0
    guide: float | None = None

    def document(self) -> dict:
        """The JSON's `proof`."""
        return {"case": self.case, "sentence": self.sentence, "actions_open": self.open, "actions_tried_together": self.tried_together, "guide_cost": self.guide}


def _chaos(value: float) -> str:
    return f"{value:,.2f} Chaos"


RECORDED = " (the figure recorded for it: its steps as written do not finish on this item)"


def _guide_words(cost: float, guide: float | None, recorded: bool = False) -> str:
    """The plan's cost against the guide's, said in plain words: dearer or cheaper, and how many times when dearer (#1596, OR-59).
    `recorded`: the guide's figure is the one its route file records, since its rules do not finish here."""
    if guide is None or not math.isfinite(guide) or not math.isfinite(cost):
        return ""
    where = f"the guide's route at {_chaos(guide)}{RECORDED if recorded else ''}"
    if _chaos(cost) == _chaos(guide):
        return f" It costs {_chaos(cost)} in all, the same as the guide's route{RECORDED if recorded else ''}."
    if cost > guide:
        if guide <= 0 or f"{cost / guide:,.2f}" == "1.00":  # no ratio of a free guide; a hair dearer reads by its difference (#1597)
            more = f"{_chaos(cost - guide)} more than {where}" + (f" ({(cost - guide) / guide:.2%} more)" if guide > 0 else "")
            return f" It costs {_chaos(cost)} in all, {more}: this plan is dearer than the guide's."
        return f" It costs {_chaos(cost)} in all, {cost / guide:,.2f} times {where}: this plan is dearer than the guide's."
    return f" It costs {_chaos(cost)} in all, less than {where}: this plan is cheaper than the guide's."


def _proved_gap(plan) -> float | None:
    """The share above the cheapest the plan is proved within over every action open to it, or None when it is not proved over them all."""
    info = plan.search
    if plan.approximation is not None:
        return None
    if info is None:  # a plan with no search record: its limits say whether every group of methods finished (`_plan.py`, the Lock's rewrite)
        stopped = any(limit.kind == _limits.UNTRIED for limit in plan.limits) or any(
            limit.kind == _limits.ROUNDS and "not every round finished" in limit.what for limit in plan.limits
        )
        solve_stopped = any(
            (limit.kind == _limits.SOLVE and limit.what == "The search was stopped") or limit.kind == _limits.REACHED for limit in plan.limits
        )
        if stopped or solve_stopped:
            return None
        for limit in plan.limits:  # stopped by itself at the run's gap: one search's own limit, or the rounds' limit when every round closed
            if limit.kind == _limits.SOLVE and limit.what == _SOLVE_WITHIN and (found := _ALLOWS.search(limit.why)) is not None:
                return float(found.group(1)) / 100
            if limit.kind == _limits.ROUNDS and (found := _AT_MOST.search(limit.guarantee)) is not None:
                return float(found.group(1)) / 100
        return None if any(_limits.WITHIN_GAP in limit.guarantee for limit in plan.limits) else 0.0
    if info.exact:
        return 0.0
    if info.within is None:
        return None
    gap = certificate_gap(info)
    return info.within if gap is None else gap


def _open(plan) -> int:
    """The actions open to the craft: every action offered over the groups of methods, or the plan's offers for one search; 0 when unknown (a
    plan saved before the planner kept the count: no group need hold every action, so none of their counts is the total)."""
    info = plan.search
    if info is None:  # the Lock's rewrite dropped the search record (`_plan.py`): its plan's offers are one round's, not the total
        return 0
    if info.widening:
        return getattr(info, "offered", 0)
    return len(plan.offers)


def _all(total: int) -> str:
    """ "all 10,873 crafts this planner can use on this item", or "every craft ..." when the count is unknown."""
    return f"all {total:,} crafts this planner can use on this item" if total else "every craft this planner can use on this item"


_LEFT_OUT = " Methods it cannot use yet are listed below the prices, and one of them could be cheaper."


def _tried_together(plan, total: int) -> int:
    """The most actions searched to the end together with the plan (see the module's text)."""
    info = plan.search
    records = tuple(info.widening) if info is not None else ()
    if not records:
        return 0
    costs = [record.upper for record in records if record.upper is not None and math.isfinite(record.upper)]
    if not costs:
        return 0
    best = min(costs)
    first = next(n for n, record in enumerate(records) if record.upper is not None and record.upper <= best * (1 + _SAME) + _SAME)
    made = records[first]
    # the rounds after the plan's own hold its actions only when its round closed and so joined the base of the later ones (`_rounds.widen`), or
    # when they are grown from the plan in hand (`RoundRecord.growth`); a round that stopped with the plan did not join it (checker, #1576)
    kept = made.status in (CLOSED, WITHIN) or getattr(made, "held_again", False)
    finished = [
        record.offers
        for n, record in enumerate(records[first:])
        if (record.status in (CLOSED, WITHIN, BEATEN) or getattr(record, "held_again", False)) and (n == 0 or kept or record.growth is not None)
    ]
    most = max(finished, default=0)
    return min(most, total) if total else most


def proof_words(plan, guide: float | None = None, *, recorded: bool = False) -> ProofWords:
    """The proof sentence of `plan` (a `Plan`); `guide` is the cost of the guide's route with the start item, when one was given, and
    `recorded` says it is the figure its route file records, since the route's rules do not finish (#1596)."""
    total = _open(plan)
    cost = plan.start_price.chaos + (plan.risk.mean.value if plan.risk is not None else plan.craft_mean)  # the mods and the finish steps (#1234)
    against = _guide_words(cost, guide, recorded)
    gap = _proved_gap(plan)
    if gap is not None and any(limit.kind == _limits.IMPRINTS for limit in plan.limits):  # the search left imprints out by its rule (#1567, #1580)
        said = (
            f"Best plan found, not proved to be the cheapest: the search checked {_all(total)} together to the end, but it made an imprint "
            "only of an item worth coming back to, so a plan that imprints the item elsewhere may be cheaper."
        )
        return ProofWords(BEST_FOUND, said + against, total, total, guide)
    if gap is not None and gap <= PROOF_GAP + 1e-12:
        within = "" if gap == 0.0 else f", to within {PROOF_GAP * 100:g}% of the crafting cost,"
        return ProofWords(
            PROVED,
            f"Proved: no cheaper plan exists{within} among {_all(total)}, every one checked to the end." + _LEFT_OUT + against,
            total,
            total,
            guide,
        )
    if gap is not None:  # every action held and finished, but only within a gap wider than 1%
        said = (
            f"Best plan found, not proved to be the cheapest: the search checked {_all(total)} together to the end, but it "
            f"proved this plan only to within {gap * 100:.2f}% of the cheapest, not 1%."
        )
        return ProofWords(BEST_FOUND, said + against, total, total, guide)
    if plan.approximation is not None:
        said = "Best plan found, not proved to be the cheapest: the search worked on a simplified model of the craft, so a cheaper plan may exist."
        return ProofWords(BEST_FOUND, said + against, total, 0, guide)
    tried = _tried_together(plan, total)
    if tried:
        said = (
            "Best plan found, not proved to be the cheapest: the search ran out of time or memory after checking only "
            f"{tried:,} {f'of the {total:,} ' if total else ''}crafts this planner can use on this item fully checked in combination with this plan (the "
            "groups are under \"How the methods were searched\"), so a cheaper plan that uses the other crafts may exist."
        )
    elif info_rounds(plan):
        said = (
            "Best plan found, not proved to be the cheapest: the search ran out of time or memory before it finished checking any group of crafts "
            f"that held this plan, so a cheaper plan may exist among the {f'{total:,} ' if total else ''}crafts this planner can use on this item."
        )
    else:
        said = (
            "Best plan found, not proved to be the cheapest: the search ran out of time or memory before it finished checking the "
            f"{f'{total:,} ' if total else ''}crafts this planner can use on this item together, so a cheaper plan may exist."
        )
    return ProofWords(BEST_FOUND, said + against, total, tried, guide)


def info_rounds(plan) -> bool:
    """Whether the methods were searched in groups (the rounds of `_rounds`)."""
    return plan.search is not None and bool(plan.search.widening)


def unusable_words(plan, label: str, uses: float, line: float) -> ProofWords:
    """The proof sentence of a run whose best plan expects more than `line` uses of its step `label` (`_usable.check_usable`, #1628, OR-12):
    no usable plan, the figure and the step, and what the search considered, in the words of the plan it replaces (OR-59)."""
    best = proof_words(plan)
    cost = plan.start_price.chaos + (plan.risk.mean.value if plan.risk is not None else plan.craft_mean)
    said = (
        f"No usable plan found within the limit: the best plan found costs {_chaos(cost)} and expects about {uses:,.0f} uses of {label}, "
        f"more than the {line:,.0f} uses of one step a player can follow, so it is not shown as a plan."
    )
    if best.case == PROVED:
        considered = f" No cheaper plan exists among {_all(best.open)}; a plan that uses one step fewer times, if there is one, costs more."
    elif best.tried_together:
        considered = (
            f" The search checked only {best.tried_together:,} {f'of the {best.open:,} ' if best.open else ''}crafts this planner can use on "
            "this item fully in combination with that plan before it ran out of time or memory; a longer run may find a usable plan."
        )
    else:
        considered = (
            f" The search ran out of time or memory before it finished checking the {f'{best.open:,} ' if best.open else ''}crafts this planner "
            "can use on this item together; a longer run may find a usable plan."
        )
    return ProofWords(NO_USABLE, said + considered, best.open, best.tried_together)


def no_plan_words() -> ProofWords:
    """The proof sentence of a run that stopped with no plan."""
    return ProofWords(NO_PLAN, NO_PLAN_SENTENCE)


__all__ = ["BEST_FOUND", "NO_PLAN", "NO_PLAN_SENTENCE", "NO_USABLE", "PROVED", "ProofWords", "no_plan_words", "proof_words", "unusable_words"]
