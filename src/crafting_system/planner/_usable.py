"""Whether the plan in hand is one a player can follow: the expected uses of its dominant step against a stop-and-say-so net (#1628).

At a short net the search may end holding a plan that no player would follow: on a 4-core runner at ten minutes, R17's first group of
methods (essences only) gave a plan of 1,708,178,141,471 Chaos, about 1.0e12 Shrieking Essences of Loathing at 1.65 Chaos; R20's first
group, 35,058,189 Chaos, about 1.37 million Essences of Horror at 25.61 Chaos; R04's second group 3.78e13 Chaos. Those were answered as
plans. The step a plan spends most uses on (`dominant_step`) is what makes it followable or not: the owner's word (OR-12's source, the
memory note of 2026-11-01) is that "a route that needs 100k orbs on one step is useless to a player".

So the planner's entry (`plan_target`) reads the expected uses of each step of the plan it ends with, on the plan's own chain
(`_growth.step_shares`: each state's expected visits times the action it takes there, its repeats included), and when one step's uses pass
the run's setting (`PlanSettings.usable_step_uses`, default `USABLE_STEP_USES`) it does not answer with the plan: it raises `UnusablePlan`,
"no usable plan found within the limit", with the plan's cost, that step, its uses and what the search considered (`unusable_words`).

What this is and is not (OR-12, OR-13): a fixed figure, so only a stop-and-say-so net on the answer. It cuts nothing in the search, which
runs and prices exactly as before; it changes only what the answer calls a plan, and it says so. The figure is a setting (as OR-40 wants
of a limit), not one sized for a route or a runner: every reference craft's plan at the one-hour net uses one step at most 3,189 times
(R20's Essence of Horror, tmeas9), the others at most 1,350 (R04's Deafening Essence of Rage), so the line is 30 times above any plan a
player is shown today and about 10 times below the least absurd of the three answers above.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ._growth import step_shares
from ._plan import PlanError
from ._proof_words import unusable_words  # the proof sentences are made in one place (ADR-0063)

USABLE_STEP_USES = 100_000  # the most expected uses of one step a plan may need and still be shown as one (OR-12's source: "100k orbs on one step is useless to a player")


@dataclass(frozen=True)
class DominantStep:
    """The step of a plan with the most expected uses: its label, its expected uses (repeats included), and its share of the plan's cost in
    Chaos (expected uses times its price)."""

    label: str
    uses: float
    chaos: float


def dominant_step(plan) -> DominantStep | None:
    """The step of `plan` used most often on average (`_growth.step_shares`, read on the plan's chain), or None when its chain cannot be read
    (no packed policy, a plan of the approximate ladder, or a chain whose visits cannot be solved): such a plan is not judged, and is answered
    as a plan as before."""
    steps = [DominantStep(str(label), sum(visits for _state, _action, visits in where), share) for label, share, where in step_shares(plan)]
    steps = [step for step in steps if math.isfinite(step.uses)]
    return max(steps, key=lambda step: (step.uses, step.label), default=None)


class UnusablePlan(PlanError):
    """The search ended with a plan that no player would follow (`check_usable`): one step expects more uses than the run's setting allows.
    `plan` is that plan, kept for a caller that records what was found; `step` its dominant step; `line` the setting; `words` the answer's
    proof sentence (`_proof_words.unusable_words`). Its text says "no usable plan found within the limit", so a caller that reads a stop with
    no plan reads it as one (OR-33)."""

    def __init__(self, plan, step: DominantStep, line: float, words) -> None:
        self.plan, self.step, self.line, self.words = plan, step, line, words
        super().__init__(words.sentence)  # the whole answer: every caller that says a refusal by its text (the web's `run_job`) says all of it

    def document(self) -> dict:
        """What a record keeps of it (the benchmark's entry): the plan's cost with the start item, the step, its uses, the line and the proof
        sentence."""
        plan = self.plan
        cost = plan.start_price.chaos + (plan.risk.mean.value if plan.risk is not None else plan.craft_mean)
        return {"cost": float(cost), "step": self.step.label, "uses": self.step.uses, "step_chaos": float(self.step.chaos), "line": self.line, "sentence": self.words.sentence}


def check_usable(plan, line: float | None):
    """`plan` when no step of it expects more than `line` uses (or `line` is None: no net); otherwise raises `UnusablePlan`."""
    if line is None:
        return plan
    step = dominant_step(plan)
    if step is None or step.uses <= line:
        return plan
    raise UnusablePlan(plan, step, line, unusable_words(plan, step.label, step.uses, line))


__all__ = ["USABLE_STEP_USES", "DominantStep", "UnusablePlan", "check_usable", "dominant_step"]
