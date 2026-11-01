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
    """A claim marked `approximate` that an action of the policy reads, with the reason it is marked.

    `interval` is the claim's own spread where the answer carries one (ADR-0028, ticket #221): the low, the point the plan uses
    and the high of a cost, the grid of an exponent, the difference between two tables; `words` says it in plain words. Both
    are empty for a claim with no interval, and then the text and the JSON are what they were without them.
    """

    claim: str
    reason: str
    interval: Mapping[str, object] | None = None
    words: str = ""


# the claims whose spread the answer shows: value keys of (point, low, high) and the unit in plain words
RANGE_CLAIMS = {
    "recombinator_cost.dust_per_combine_reports_3_26": (("point", "low", "high"), "Thaumaturgic Dust per combine"),
    "recombinator_cost.gold_per_combine_reports_3_26": (("point", "low", "high"), "Gold per combine"),
    "recombinator_cost.junk_craft_halves_dust_3_26": (
        ("factor_point", "factor_low", "factor_high"),
        "factor on the Dust when each input carries a junk craft",
    ),
}
GRID_CLAIMS = {"recombinator.selection_weighted_formula_unknown": "the selection exponent alpha"}
TABLE_CLAIMS = {
    "recombinator.count_table": "recombinator.count_table_wiki",
    "recombinator.count_table_wiki": "recombinator.count_table",
}


def number_text(value: float) -> str:
    """A claim's number in words: whole numbers with thousands separators, others with their digits (`0.11`, `1.3`)."""
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:g}"


def claim_interval(rule) -> tuple[Mapping[str, object], str] | None:
    """The spread of an approximate claim and its words, or None when the answer shows none for this claim (a fixed list of claims)."""
    if rule.id in RANGE_CLAIMS:
        keys, unit = RANGE_CLAIMS[rule.id]
        point, low, high = (float(rule.value[key]) for key in keys)
        words = f"the planner uses {number_text(point)}; reports range from {number_text(low)} to {number_text(high)} ({unit})"
        return {"kind": "range", "point": point, "low": low, "high": high, "unit": unit}, words
    if rule.id in GRID_CLAIMS:
        plan, grid = float(rule.value["plan"]), [float(x) for x in rule.value["grid"]]
        shown = ", ".join(number_text(x) for x in grid)
        words = f"the planner is run at {number_text(plan)}; its cost is read at {shown}"
        return {"kind": "grid", "plan": plan, "grid": grid}, words
    if rule.id in TABLE_CLAIMS:
        other = TABLE_CLAIMS[rule.id]
        a, b = rule.value, rule_by_id(other).value
        gap = max(abs(float(a[row][n]) - float(b[row][n])) for row in a for n in a[row])
        words = f"the guide's table is used; the wiki's rounding of the same table differs by up to {number_text(round(gap, 1))} points in a row"
        return {"kind": "alternative_table", "other": other, "largest_difference_points": round(gap, 1)}, words
    return None


def approximate_inputs(
    plan: Plan, policy: Mapping[CompressedState, Action[CompressedState]], data: GameData
) -> tuple[ApproximateInput, ...]:
    """The approximate claims read by the actions `policy` takes in the states it reaches from the start, by claim id.

    An action the plan offers but the policy never takes is not listed (ADR-0028). The limit of crafted mods with the enchantment
    of the extra crafted slot is the exception: that claim is not a constant of any action (it would be listed on every bench
    craft), so it is named here when the start item holds the enchantment and an action of the policy checks the limit; it leans
    to naming too many (the unsourced case is only the enchantment together with the multimod, ADR-0053).
    """
    actions = []
    for state in policy_states(plan.start, policy, plan.is_goal):
        action = policy.get(state)
        if plan.is_goal(state) or action is None:
            continue
        actions.append(action)
    return approximate_inputs_of(plan, actions, data)


def approximate_inputs_of(plan: Plan, actions, data: GameData) -> tuple[ApproximateInput, ...]:
    """The approximate claims read by `actions` (solver actions of the plan's offers), by claim id; see `approximate_inputs`.

    This is the list for a policy that is not a plain walk of outcomes, such as the policy of a product with inputs, whose
    caller walks it and hands over the actions it takes.
    """
    ids: set[str] = set()
    for action in actions:
        ids |= plan.offer_of(action).offer.action.claims(data)  # type: ignore[attr-defined]
    starts = getattr(plan, "starts", None)  # a stand-in plan of a test has none
    if starts is not None:
        ids |= set(starts.claims)  # a recipe-made start item rests on claims no action of the policy cites (ADR-0059)
    if CRAFTED_LIMIT_CLAIM in ids and grants_extra_crafted_slot(data, plan.abstraction.enchantment):
        ids.add(STACKING_CLAIM)
    if not is_jewel(data, plan.target.base_id):
        ids = {claim for claim in ids if not claim.startswith(JEWEL_CLAIMS)}  # an action cites them for every item it takes
    found = []
    for rule in (rule_by_id(claim) for claim in sorted(ids)):
        if not rule.approximate:
            continue
        spread = claim_interval(rule)
        found.append(ApproximateInput(rule.id, rule.approximate_reason, *(spread or (None, ""))))
    return tuple(found)


def approximate_lines(inputs: tuple[ApproximateInput, ...]) -> list[str]:
    """The text lines that name the approximate inputs of an answer (none when there are none)."""
    if not inputs:
        return []
    lines = [APPROXIMATE_HEADING]
    for item in inputs:
        lines.append(f"  {item.claim}: {item.reason}")
        if item.words:
            lines.append(f"      spread: {item.words}")
    return lines


def approximate_inputs_document(inputs: tuple[ApproximateInput, ...]) -> list[dict]:
    """The JSON `approximate_inputs`: one `{claim, reason}` per input (and its `interval` when it has one), an empty list when there are none."""
    return [
        {"claim": item.claim, "reason": item.reason, **({"interval": {**item.interval, "words": item.words}} if item.interval else {})}
        for item in inputs
    ]


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
