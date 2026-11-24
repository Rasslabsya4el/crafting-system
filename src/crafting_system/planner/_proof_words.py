"""The one sentence that says how sure a plan is, in a player's words (#1576, OR-58): the route page's "Proof" field, the text report's
"Proof:" line and the JSON's `proof` say it from here, and nothing else words the answer's proof.

Three cases, no more:

* **Proved** (`PROVED`): the search held every action open to the craft together and finished, and its plan is proved within 1% of the
  cheapest (`budget.PROOF_GAP`; exact when the gap is 0). Only then does the sentence say "proved" without a qualifier.
* **Best found, not proved** (`BEST_FOUND`): any other plan. The sentence says how many of the actions open to the craft were searched to the
  end together with the plan (`tried_together`): the most actions of a group of methods that finished with the plan in hand, from the group
  whose plan the run ended with on; a group that finished early because it could not beat the plan counts, a group that showed only that its
  methods alone do not reach the target does not (it did not hold the plan's actions). With a guide's route, its cost beside the plan's.
* **No plan** (`NO_PLAN`): the search stopped before any plan reached the target; that is not a proof that none does (OR-33).

The rule (OR-58, owner 2026-11-24): a craft is shown as proved only when the plan is proved within 1% over every method; otherwise "best plan
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


def _guide_words(cost: float, guide: float | None) -> str:
    if guide is None or not math.isfinite(guide) or not math.isfinite(cost):
        return ""
    return f" It costs {_chaos(cost)} in all, against {_chaos(guide)} for the guide's route."


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
    """The actions open to the craft: every action offered over the groups of methods, or the plan's offers for one search. A plan saved
    before the count was kept reads the most actions any group held (the last group holds every action)."""
    info = plan.search
    if info is not None and info.widening:
        return getattr(info, "offered", 0) or max(record.offers for record in info.widening)
    return len(plan.offers)


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
    finished = [
        record.offers for record in records[first:] if record.status in (CLOSED, WITHIN, BEATEN) or getattr(record, "held_again", False)
    ]
    return min(max(finished, default=0), total)


def proof_words(plan, guide: float | None = None) -> ProofWords:
    """The proof sentence of `plan` (a `Plan`); `guide` is the cost of the guide's route with the start item, when one was given."""
    total = _open(plan)
    cost = plan.start_price.chaos + (plan.risk.mean.value if plan.risk is not None else plan.mean_remaining)
    against = _guide_words(cost, guide)
    gap = _proved_gap(plan)
    if gap is not None and gap <= PROOF_GAP + 1e-12:
        within = "" if gap == 0.0 else f", to within {PROOF_GAP * 100:g}%"
        return ProofWords(
            PROVED,
            f"Proved: no cheaper way exists{within}. The search held all {total:,} actions open to this craft together and finished." + against,
            total,
            total,
            guide,
        )
    if gap is not None:  # every action held and finished, but only within a gap wider than 1%
        said = (
            f"Best plan found, not proved the cheapest: the search held all {total:,} actions open to this craft together and finished, but it "
            f"proved this plan only to within {gap * 100:.2f}% of the cheapest, not 1%."
        )
        return ProofWords(BEST_FOUND, said + against, total, total, guide)
    if plan.approximation is not None:
        said = "Best plan found, not proved the cheapest: the search worked on a simplified model of the craft, so a cheaper plan may exist."
        return ProofWords(BEST_FOUND, said + against, total, 0, guide)
    tried = _tried_together(plan, total)
    if tried:
        said = (
            f"Best plan found, not proved the cheapest: {tried:,} of the {total:,} actions open to this craft were searched to the end together "
            "with this plan before the search ran out of time or memory, so a cheaper plan that uses the others may exist."
        )
    elif info_rounds(plan):
        said = (
            "Best plan found, not proved the cheapest: no group of methods that held this plan was searched to the end before the search ran out "
            f"of time or memory, so a cheaper plan may exist among the {total:,} actions open to this craft."
        )
    else:
        said = (
            f"Best plan found, not proved the cheapest: the search held the {total:,} actions open to this craft together but ran out of time or "
            "memory before it finished, so a cheaper plan may exist."
        )
    return ProofWords(BEST_FOUND, said + against, total, tried, guide)


def info_rounds(plan) -> bool:
    """Whether the methods were searched in groups (the rounds of `_rounds`)."""
    return plan.search is not None and bool(plan.search.widening)


def no_plan_words() -> ProofWords:
    """The proof sentence of a run that stopped with no plan."""
    return ProofWords(NO_PLAN, NO_PLAN_SENTENCE)


__all__ = ["BEST_FOUND", "NO_PLAN", "NO_PLAN_SENTENCE", "PROVED", "ProofWords", "no_plan_words", "proof_words"]
