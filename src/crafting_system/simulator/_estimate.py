"""The statistics of a sample of runs: mean, quantile and success rate, each with a confidence interval.

Everything is a normal approximation (Wilson for a proportion), good for thousands of runs and
not for a handful. Plain `math` and `statistics`; no third-party library.
"""

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

EXACT_TOLERANCE = 1e-12  # relative: how close two numbers must be to count as equal when nothing is random


@dataclass(frozen=True, slots=True)
class SampledEstimate:
    """A number estimated from a sample: `value`, its `standard_error` and a confidence interval `[low, high]`.

    `low` and `high` hold at the confidence the report was made with. `standard_error` is 0.0 when
    the sample shows no spread.
    """

    value: float
    standard_error: float
    low: float
    high: float

    def contains(self, x: float) -> bool:
        """Whether `x` lies inside the confidence interval."""
        return self.low <= x <= self.high

    def agrees_with(self, x: float, *, sigmas: float = 5.0) -> bool:
        """Whether `x` is within `sigmas` standard errors of `value`.

        With a standard error of 0 the sample showed no spread, and only equality within 1e-12
        relative agrees.
        """
        if self.standard_error == 0.0:
            return math.isclose(self.value, x, rel_tol=EXACT_TOLERANCE, abs_tol=0.0)
        return abs(self.value - x) <= sigmas * self.standard_error


def critical_value(confidence: float) -> float:
    """z such that a standard normal variable lies in [-z, z] with probability `confidence`."""
    return statistics.NormalDist().inv_cdf(0.5 + confidence / 2.0)


def proportion(successes: int, runs: int, confidence: float) -> SampledEstimate:
    """The share `successes / runs` with its Wilson score interval.

    The standard error is that of the Wilson-centred share (successes + z^2/2) / (runs + z^2), so it
    stays above 0 even when every run succeeded; the interval itself is the Wilson interval.
    """
    z = critical_value(confidence)
    share = successes / runs
    scale = 1.0 + z * z / runs
    centre = (share + z * z / (2.0 * runs)) / scale
    half = z / scale * math.sqrt(share * (1.0 - share) / runs + z * z / (4.0 * runs * runs))
    low = 0.0 if successes == 0 else max(0.0, centre - half)
    high = 1.0 if successes == runs else min(1.0, centre + half)
    shifted = (successes + z * z / 2.0) / (runs + z * z)
    return SampledEstimate(share, math.sqrt(shifted * (1.0 - shifted) / (runs + z * z)), low, high)


def mean(values: Sequence[float], confidence: float) -> SampledEstimate:
    """The sample mean, its standard error (sample sd over sqrt(n)) and mean -+ z standard errors.

    Needs at least two values.
    """
    n = len(values)
    centre = values[0] if len(set(values)) == 1 else math.fsum(values) / n  # fsum/n can miss a repeated value
    spread = math.sqrt(math.fsum((v - centre) ** 2 for v in values) / (n - 1))
    error = spread / math.sqrt(n)
    z = critical_value(confidence)
    return SampledEstimate(centre, error, centre - z * error, centre + z * error)


def quantile(values: Sequence[float], level: float, confidence: float) -> SampledEstimate:
    """The empirical quantile: the smallest sample value x with at least `level` of the sample at or below x.

    The interval is the order-statistic bracket: the number of values at or below the true quantile
    is binomial(n, level), so ranks n*level -+ z sqrt(n*level*(1-level)) (rounded outwards, held
    inside 1..n) bound it. The standard error is the bracket's half width over z, an approximation
    that is 0 when the bracket is one atom.
    """
    n = len(values)
    ordered = sorted(values)
    z = critical_value(confidence)
    spread = z * math.sqrt(n * level * (1.0 - level))
    target = n * Fraction(repr(level))  # the level as written (0.9 is 9/10), so n * level has no float noise
    rank = min(n, max(1, math.ceil(target)))
    lower = min(n, max(1, math.floor(float(target) - spread)))
    upper = min(n, max(1, math.ceil(float(target) + spread)))
    low, high = ordered[lower - 1], ordered[upper - 1]
    return SampledEstimate(ordered[rank - 1], (high - low) / (2.0 * z), low, high)
