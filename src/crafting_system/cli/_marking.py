"""How an answer says what it is: exact, or approximate within a certified gap (ADR-0023, ticket #127).

This is the one place that words and serialises the marking, in text and in JSON. It is also the home of the
approximate inputs (ADR-0028, ticket #143): the claims marked `approximate` that the actions of a policy read.
Those are an uncertainty in the model; the certified gap below is the solver's error given the model. They are
independent (an exact answer can read an approximate claim, an approximate one can read none) and never joined
into one percentage: the lines and the JSON key of one have nothing to do with those of the other.

An exact answer prints nothing extra in the text and
`{"approximate": false}` in the JSON; an approximate one prints its words, the two bounds, the level and the block
count, and puts `approximate: true`, `lower`, `upper`, `gap`, `level` (and `blocks`, `tolerance`,
`within_tolerance`, `message`) in the JSON. Bounds are totals, the price of the start item included, like the mean
of an exact answer; the gap is the solver's own, of the cost still to pay, which is the larger and so the safe one.

`--verify` of an approximate answer (ticket #128) is worded here too: the policy of blocks is run on concrete items,
and its mean, p90 and CVaR are simulated numbers, each shown with the words `SIMULATED`, never next to a certified
figure that looks like them. The certified interval of the mean is the only certified number of the block.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.abstraction import CompressedState
from crafting_system.actions import grants_extra_crafted_slot
from crafting_system.data import GameData
from crafting_system.rules import get_rule, rule_by_id
from crafting_system.simulator import SampledEstimate
from crafting_system.solver import Action

from ._approx import Approximation
from ._plan import Plan
from ._reach import policy_states
from ._verify import CVAR_LEVEL, SIGMAS, Verification

SIMULATED = "simulated, not certified"
CVAR_PERCENT = f"{CVAR_LEVEL:.0%}"
CERTIFIED = "approximate (certified within {gap} of the exact mean)"
UNCERTIFIED = "approximate (the certified gap is {gap}, above the {tolerance} tolerance)"
NO_RISK = "not given for an approximate answer: the chain on blocks is not Markov and no exact chain of the policy is built"


def percent(value: float) -> str:
    """A gap as a percentage: never rounded down to look smaller than it is."""
    if math.isinf(value):
        return "unbounded"
    places = 2 if value >= 1e-4 else 4
    return f"{math.ceil(Fraction(value) * 100 * 10**places) / 10**places:.{places}f}%"


def headline(approximation: Approximation) -> str:
    """The words that mark the answer."""
    if approximation.within_tolerance:
        return CERTIFIED.format(gap=percent(approximation.gap))
    return UNCERTIFIED.format(gap=percent(approximation.gap), tolerance=f"{approximation.tolerance:.0%}")


def marking_lines(approximation: Approximation | None, shift: float, divine: float) -> list[str]:
    """The text lines that mark an answer (none for an exact one). `shift` is the start item's price, `divine` Chaos per Divine."""
    if approximation is None:
        return []

    def chaos(value: float) -> str:
        return "never" if math.isinf(value) else f"{value + shift:,.2f}"

    lines = [
        f"Answer: {headline(approximation)}",
        f"  The exact mean cost, the start item included, is between {chaos(approximation.lower)} and {chaos(approximation.upper)} Chaos",
        f"  ({(approximation.lower + shift) / divine:.3g} to {(approximation.upper + shift) / divine:.3g} Divine); the policy below costs no more than the upper figure.",
        f"  Level: {approximation.level}; {approximation.blocks:,} blocks solved"
        + (f", {approximation.expanded:,} of them exact states expanded by the tail cut." if approximation.expanded else "."),
    ]
    if approximation.message:
        lines.append(f"  {approximation.message}")
    return lines


def risk_lines() -> list[str]:
    """What the result block says in place of the odds and the percentiles."""
    return [f"  success, p50, p90, CVaR  {NO_RISK}"]


def marking_document(approximation: Approximation | None, shift: float) -> dict:
    """The JSON marking: `approximate`, and for an approximate answer its interval, gap and level."""
    if approximation is None:
        return {"approximate": False}

    def number(value: float) -> float | None:
        return None if math.isinf(value) or math.isnan(value) else value + shift

    return {
        "approximate": True,
        "lower": number(approximation.lower),
        "upper": number(approximation.upper),
        "gap": None if math.isinf(approximation.gap) else approximation.gap,
        "level": approximation.level,
        "blocks": approximation.blocks,
        "expanded": approximation.expanded,
        "tolerance": approximation.tolerance,
        "within_tolerance": approximation.within_tolerance,
        "message": approximation.message,
    }


# --- the approximate inputs (ADR-0028) -------------------------------------------------------------------------

APPROXIMATE_HEADING = "Approximate inputs (claims that no other source settles):"
CRAFTED_LIMIT_CLAIM = "bench_craft.one_crafted_mod_by_default"  # read by every action that checks the limit of crafted mods
STACKING_CLAIM = "enchantment.crafted_slot_with_multimod_takes_the_larger"


JEWEL_ITEM_CLASSES = get_rule("affix_count.rare_jewel_max_per_side").value["item_classes"]
JEWEL_CLAIMS = "jewel."  # the ids of the claims about jewels: they count for an answer on a jewel base only


def is_jewel(data: GameData, base_id: str) -> bool:
    """Whether `base_id` is a jewel base (the item classes of `affix_count.rare_jewel_max_per_side`)."""
    base = data.base_items.get(base_id)
    return base is not None and base.item_class in JEWEL_ITEM_CLASSES


@dataclass(frozen=True)
class ApproximateInput:
    """A claim marked `approximate` that an action of the policy reads, with the reason it is marked."""

    claim: str
    reason: str


def approximate_inputs(
    plan: Plan, policy: Mapping[CompressedState, Action[CompressedState]], data: GameData
) -> tuple[ApproximateInput, ...]:
    """The approximate claims read by the actions `policy` takes in the states it reaches from the start, by claim id.

    An action the plan offers but the policy never takes is not listed (ADR-0028). The limit of crafted mods with the enchantment
    of the extra crafted slot is the exception: that claim is not a constant of any action (it would be listed on every bench
    craft), so it is named here when the start item holds the enchantment and an action of the policy checks the limit; it leans
    to naming too many (the unsourced case is only the enchantment together with the multimod, ADR-0053).
    """
    ids: set[str] = set()
    for state in policy_states(plan.start, policy, plan.is_goal):
        action = policy.get(state)
        if plan.is_goal(state) or action is None:
            continue
        ids |= plan.offer_of(action).offer.action.claims(data)  # type: ignore[attr-defined]
    starts = getattr(plan, "starts", None)  # a stand-in plan of a test has none
    if starts is not None:
        ids |= set(starts.claims)  # a recipe-made start item rests on claims no action of the policy cites (ADR-0059)
    if CRAFTED_LIMIT_CLAIM in ids and grants_extra_crafted_slot(data, plan.abstraction.enchantment):
        ids.add(STACKING_CLAIM)
    if not is_jewel(data, plan.target.base_id):
        ids = {claim for claim in ids if not claim.startswith(JEWEL_CLAIMS)}  # an action cites them for every item it takes
    rules = (rule_by_id(claim) for claim in sorted(ids))
    return tuple(ApproximateInput(rule.id, rule.approximate_reason) for rule in rules if rule.approximate)


def approximate_lines(inputs: tuple[ApproximateInput, ...]) -> list[str]:
    """The text lines that name the approximate inputs of an answer (none when there are none)."""
    if not inputs:
        return []
    return [APPROXIMATE_HEADING, *(f"  {item.claim}: {item.reason}" for item in inputs)]


def approximate_inputs_document(inputs: tuple[ApproximateInput, ...]) -> list[dict]:
    """The JSON `approximate_inputs`: one `{claim, reason}` per input, an empty list when there are none."""
    return [{"claim": item.claim, "reason": item.reason} for item in inputs]


# --- --verify of an approximate answer -------------------------------------------------------------------------


def _chaos(value: float) -> str:
    return "never" if math.isinf(value) else f"{value:,.2f}"


def _shown(estimate: SampledEstimate) -> str:
    return f"{_chaos(estimate.value)} Chaos, interval {_chaos(estimate.low)} to {_chaos(estimate.high)}"


def verification_lines(check: Verification) -> list[str]:
    """The text of `--verify` for an approximate answer: every p90 and CVaR number carries the words `SIMULATED`."""
    report = check.report
    cost = report.cost
    lower, upper = check.bounds
    verdict = (
        "AGREES: the simulated mean is consistent with the certified interval"
        if check.agrees
        else f"DOES NOT AGREE: {check.reason}"
    )
    return [
        f"Verification by simulation, not certified ({check.runs:,} runs, seed {check.seed}, at most {check.max_steps:,} uses per run)",
        "  The policy of blocks was run on concrete items: each item is compressed, mapped to its block and given that block's action.",
        f"  simulated mean cost {_chaos(cost.value)} Chaos, {report.confidence:.0%} interval {_chaos(cost.low)} to {_chaos(cost.high)} "
        f"(normal approximation), {SIMULATED}",
        f"  certified interval for the exact mean {_chaos(lower)} to {_chaos(upper)} Chaos",
        f"  simulated p90 {_shown(check.p90)} ({SIMULATED})",
        f"  simulated CVaR {CVAR_PERCENT} {_shown(check.cvar)} ({SIMULATED})",
        f"  detectable error    a mean off by more than {check.detectable_error:.1%} is rejected "
        f"({SIGMAS:g} standard errors); a smaller error passes; more --runs see smaller ones",
        f"  successes {report.successes:,} of {report.runs:,}, mean uses per run {report.mean_steps:.1f}",
        "  " + verdict,
    ]


def _sampled(estimate: SampledEstimate) -> dict:
    return {
        "value": _number(estimate.value),
        "standard_error": _number(estimate.standard_error),
        "low": _number(estimate.low),
        "high": _number(estimate.high),
    }


def _number(value: float) -> float | None:
    return None if math.isinf(value) or math.isnan(value) else value


def verification_document(check: Verification) -> dict:
    """The JSON `verification` block of an approximate answer: simulated numbers labelled as such, no computed p90."""
    report = check.report
    lower, upper = check.bounds
    return {
        "label": SIMULATED,
        "runs": check.runs,
        "seed": check.seed,
        "max_steps": check.max_steps,
        "interval": f"{report.confidence:.0%}, normal approximation",
        "simulated_mean_cost": _sampled(report.cost),
        "certified_interval": {"lower": _number(lower), "upper": _number(upper)},
        "simulated_p90": _sampled(check.p90),
        "simulated_cvar": {"level": CVAR_LEVEL, **_sampled(check.cvar)},
        "successes": report.successes,
        "unfinished": report.unfinished,
        "stopped": report.stopped,
        "detectable_relative_error": _number(check.detectable_error),
        "agrees": check.agrees,
        "reason": check.reason,
    }
