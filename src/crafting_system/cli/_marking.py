"""How an answer says what it is: exact, or approximate within a certified gap (ADR-0023, ticket #127).

This is the one place that words and serialises the marking, in text and in JSON, so that what a later ticket adds
to it (the approximate inputs of #143) is added here. An exact answer prints nothing extra in the text and
`{"approximate": false}` in the JSON; an approximate one prints its words, the two bounds, the level and the block
count, and puts `approximate: true`, `lower`, `upper`, `gap`, `level` (and `blocks`, `tolerance`,
`within_tolerance`, `message`) in the JSON. Bounds are totals, the price of the start item included, like the mean
of an exact answer; the gap is the solver's own, of the cost still to pay, which is the larger and so the safe one.

`--verify` of an approximate answer (ticket #128) is worded here too: the policy of blocks is run on concrete items,
and its mean, p90 and CVaR are simulated numbers, each shown with the words `SIMULATED`, never next to a certified
figure that looks like them. The certified interval of the mean is the only certified number of the block.
"""

import math
from fractions import Fraction

from crafting_system.simulator import SampledEstimate

from ._approx import Approximation
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
        f"  Level: {approximation.level}; {approximation.blocks:,} blocks solved.",
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
        "tolerance": approximation.tolerance,
        "within_tolerance": approximation.within_tolerance,
        "message": approximation.message,
    }


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
