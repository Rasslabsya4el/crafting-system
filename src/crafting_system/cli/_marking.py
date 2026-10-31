"""How an answer says what it is: exact, or approximate within a certified gap (ADR-0023, ticket #127).

This is the one place that words and serialises the marking, in text and in JSON, so that what a later ticket adds
to it (the approximate inputs of #143) is added here. An exact answer prints nothing extra in the text and
`{"approximate": false}` in the JSON; an approximate one prints its words, the two bounds, the level and the block
count, and puts `approximate: true`, `lower`, `upper`, `gap`, `level` (and `blocks`, `tolerance`,
`within_tolerance`, `message`) in the JSON. Bounds are totals, the price of the start item included, like the mean
of an exact answer; the gap is the solver's own, of the cost still to pay, which is the larger and so the safe one.
"""

import math
from fractions import Fraction

from ._approx import Approximation

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
