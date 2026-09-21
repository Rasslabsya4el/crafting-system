"""Exact cost distributions for independent geometric crafting loops.

The formulas and synthetic examples are specified in
``docs/design/build_contract.md`` and ``docs/specs/2026-09-21-loop-costs.md``.
They do not encode game mechanics or currency prices.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import math
from numbers import Real
from typing import Iterable


# The limits make the exact claim meaningful: callers can elect an estimator for
# larger distributions instead of accidentally allocating an unbounded array.
_MAX_GRID_POINTS = 200_000
_MAX_OPERATIONS = 2_000_000


@dataclass(frozen=True)
class LoopCost:
    success_probability: float
    expected_attempts: float
    expected_cost: float
    attempts_p90: float
    cost_p90: float
    method: str


@dataclass(frozen=True)
class ChainCost:
    expected_cost: float
    cost_p90: float
    method: str
    quantile_error: float | None = None


def geometric_cdf(n: int, p: float) -> float:
    """Return ``P(N <= n)`` for attempts ``N ~ Geom(p)`` including success."""
    probability = _probability(p)
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError("n must be an integer")
    if n < 1 or probability == 0:
        return 0.0
    if probability == 1:
        return 1.0
    return -math.expm1(n * math.log1p(-probability))


def geometric_quantile(p: float, q: float = 0.9) -> float:
    """Return the smallest positive attempt count whose geometric CDF reaches q."""
    probability = _probability(p)
    quantile = _open_probability(q, "q")
    if probability == 0:
        return math.inf
    if probability == 1:
        return 1

    estimate = math.log1p(-quantile) / math.log1p(-probability)
    n = max(1, math.ceil(estimate))
    # Correct floating-point rounding at a CDF boundary using the stable CDF.
    while n > 1 and geometric_cdf(n - 1, probability) >= quantile:
        n -= 1
    while geometric_cdf(n, probability) < quantile:
        n += 1
    return n


def geometric_cost(
    p: float,
    attempt_cost: float,
    *,
    reset_cost: float = 0,
    setup_cost: float = 0,
) -> LoopCost:
    """Calculate exact expectation and p90 for a fixed-cost geometric loop."""
    probability = _probability(p)
    attempt = _nonnegative_cost(attempt_cost, "attempt_cost")
    reset = _nonnegative_cost(reset_cost, "reset_cost")
    setup = _nonnegative_cost(setup_cost, "setup_cost")
    if probability == 0:
        return LoopCost(probability, math.inf, math.inf, math.inf, math.inf, "unreachable")

    attempts = 1.0 / probability
    attempts_p90 = geometric_quantile(probability)
    expected = setup + attempt * attempts + reset * (1 - probability) * attempts
    cost_p90 = setup + attempt * attempts_p90 + reset * (attempts_p90 - 1)
    return LoopCost(probability, attempts, expected, attempts_p90, cost_p90, "exact-geometric")


def chain_cost(stages: Iterable[tuple[float, float, float, float]]) -> ChainCost:
    """Convolve independent fixed-cost geometric stages on their exact cost lattice."""
    parsed = [_stage(stage) for stage in stages]
    if not parsed:
        return ChainCost(0.0, 0.0, "exact-lattice-convolution")
    if any(probability == 0 for probability, _, _, _ in parsed):
        return ChainCost(math.inf, math.inf, "unreachable")

    expected = sum(
        setup + attempt / probability + reset * (1 - probability) / probability
        for probability, attempt, reset, setup in parsed
    )
    stage_fractions = _stage_fractions(parsed)
    unit, _ = _lattice([cost for stage in stage_fractions for cost in stage])

    variable_stages: list[tuple[float, int, int]] = []
    fixed_shift = 0
    for (probability, _, _, _), (attempt, reset, setup) in zip(parsed, stage_fractions):
        base = _to_grid(setup + attempt, unit)
        step = _to_grid(attempt + reset, unit)
        if probability == 1 or step == 0:
            fixed_shift += base
        else:
            variable_stages.append((probability, base, step))

    if not variable_stages:
        cost = _from_grid(fixed_shift, unit)
        return ChainCost(expected, cost, "exact-lattice-convolution")

    crossing = _chain_crossing(variable_stages)
    return ChainCost(expected, _from_grid(fixed_shift + crossing, unit), "exact-lattice-convolution")


def compound_geometric_cost(
    p: float,
    costs: Iterable[tuple[float, float]],
    *,
    reset_cost: float = 0,
    setup_cost: float = 0,
) -> LoopCost:
    """Exact p90 when each independent attempt has a weighted cost distribution."""
    probability = _probability(p)
    reset = _nonnegative_cost(reset_cost, "reset_cost")
    setup = _nonnegative_cost(setup_cost, "setup_cost")
    parsed = _weighted_costs(costs)
    mean_attempt = sum(cost * weight for cost, weight, _ in parsed)
    if probability == 0:
        return LoopCost(probability, math.inf, math.inf, math.inf, math.inf, "unreachable")

    attempts = 1.0 / probability
    expected = setup + mean_attempt * attempts + reset * (1 - probability) * attempts
    fractions = [fraction for _, _, fraction in parsed] + [_cost_fraction(reset), _cost_fraction(setup)]
    unit, _ = _lattice(fractions)
    weighted_grid: dict[int, float] = {}
    for _, weight, fraction in parsed:
        grid_cost = _to_grid(fraction, unit)
        weighted_grid[grid_cost] = weighted_grid.get(grid_cost, 0.0) + weight
    reset_grid = _to_grid(_cost_fraction(reset), unit)
    setup_grid = _to_grid(_cost_fraction(setup), unit)
    crossing = _compound_crossing(probability, weighted_grid, reset_grid)
    return LoopCost(
        probability,
        attempts,
        expected,
        geometric_quantile(probability),
        _from_grid(setup_grid + crossing, unit),
        "exact-compound-geometric",
    )


def _stage(stage: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    try:
        probability, attempt, reset, setup = stage
    except (TypeError, ValueError) as exc:
        raise ValueError("each stage must contain p, attempt_cost, reset_cost, setup_cost") from exc
    return (
        _probability(probability),
        _nonnegative_cost(attempt, "attempt_cost"),
        _nonnegative_cost(reset, "reset_cost"),
        _nonnegative_cost(setup, "setup_cost"),
    )


def _stage_fractions(
    stages: list[tuple[float, float, float, float]],
) -> list[tuple[Fraction, Fraction, Fraction]]:
    return [(_cost_fraction(attempt), _cost_fraction(reset), _cost_fraction(setup)) for _, attempt, reset, setup in stages]


def _chain_crossing(stages: list[tuple[float, int, int]]) -> int:
    bound = 16
    while bound <= _MAX_GRID_POINTS:
        _check_work(bound, len(stages))
        distribution = [1.0] + [0.0] * bound
        for probability, base, step in stages:
            next_distribution = [0.0] * (bound + 1)
            failure = 1 - probability
            for cost in range(bound + 1):
                mass = probability * (distribution[cost - base] if cost >= base else 0.0)
                if cost >= step:
                    mass += failure * next_distribution[cost - step]
                next_distribution[cost] = mass
            distribution = next_distribution
        if math.fsum(distribution) >= 0.9:
            return _first_crossing(distribution, 0.9)
        bound *= 2
    raise NotImplementedError("cost convolution work limit")


def _compound_crossing(probability: float, costs: dict[int, float], reset: int) -> int:
    positive = [(cost + reset, weight) for cost, weight in costs.items() if cost + reset > 0]
    zero_weight = sum(weight for cost, weight in costs.items() if cost + reset == 0)
    denominator = 1 - (1 - probability) * zero_weight
    bound = 16
    while bound <= _MAX_GRID_POINTS:
        _check_work(bound, len(positive) + 1)
        distribution = [0.0] * (bound + 1)
        for total in range(bound + 1):
            attempt_mass = probability * costs.get(total, 0.0)
            continuation = math.fsum(
                weight * distribution[total - step] for step, weight in positive if total >= step
            )
            distribution[total] = (attempt_mass + (1 - probability) * continuation) / denominator
        if math.fsum(distribution) >= 0.9:
            return _first_crossing(distribution, 0.9)
        bound *= 2
    raise NotImplementedError("cost convolution work limit")


def _weighted_costs(costs: Iterable[tuple[float, float]]) -> list[tuple[float, float, Fraction]]:
    parsed: list[tuple[float, float, Fraction]] = []
    for entry in costs:
        try:
            cost, weight = entry
        except (TypeError, ValueError) as exc:
            raise ValueError("each cost must contain cost and weight") from exc
        parsed.append((_nonnegative_cost(cost, "cost"), _positive_weight(weight), _cost_fraction(cost)))
    if not parsed:
        raise ValueError("costs must not be empty")
    total_weight = math.fsum(weight for _, weight, _ in parsed)
    return [(cost, weight / total_weight, fraction) for cost, weight, fraction in parsed]


def _lattice(costs: list[Fraction]) -> tuple[Fraction, list[int]]:
    denominator = 1
    for cost in costs:
        denominator = math.lcm(denominator, cost.denominator)
    numerators = [cost.numerator * (denominator // cost.denominator) for cost in costs]
    divisor = 0
    for numerator in numerators:
        divisor = math.gcd(divisor, numerator)
    if divisor == 0:
        return Fraction(1), [0 for _ in costs]
    return Fraction(divisor, denominator), [numerator // divisor for numerator in numerators]


def _to_grid(cost: Fraction, unit: Fraction) -> int:
    value = cost / unit
    if value.denominator != 1:
        raise AssertionError("cost does not fit its own lattice")
    return value.numerator


def _from_grid(cost: int, unit: Fraction) -> float:
    return float(cost * unit)


def _first_crossing(distribution: list[float], threshold: float) -> int:
    cumulative = 0.0
    for cost, mass in enumerate(distribution):
        cumulative += mass
        if cumulative >= threshold:
            return cost
    raise AssertionError("crossing requested before CDF threshold")


def _check_work(bound: int, stages: int) -> None:
    if bound > _MAX_GRID_POINTS or (bound + 1) * stages > _MAX_OPERATIONS:
        raise NotImplementedError("cost convolution work limit")


def _probability(value: float) -> float:
    probability = _finite_number(value, "p")
    if probability < 0 or probability > 1:
        raise ValueError("p must be in [0, 1]")
    return probability


def _open_probability(value: float, name: str) -> float:
    probability = _finite_number(value, name)
    if probability <= 0 or probability >= 1:
        raise ValueError(f"{name} must be in (0, 1)")
    return probability


def _nonnegative_cost(value: float, name: str) -> float:
    cost = _finite_number(value, name)
    if cost < 0:
        raise ValueError(f"{name} must be nonnegative")
    return cost


def _positive_weight(value: float) -> float:
    weight = _finite_number(value, "weight")
    if weight <= 0:
        raise ValueError("weight must be positive")
    return weight


def _finite_number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _cost_fraction(value: float) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, Decimal):
        return Fraction(value)
    return Fraction(Decimal(str(value)))
