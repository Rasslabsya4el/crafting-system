"""Cost law for the legal suffix-protected tagged-Harvest policy.

The rule is recorded in ``docs/mechanics/harvest.md`` under "Legal
protected-half policy boundary".  This module only evaluates the stated
renewal law; it does not decide which crafting states are legal.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class RenewalMetrics:
    """Exact moments for a preparation/reforge renewal process."""

    preparation_cost: float
    mean_cost: float
    reforge_attempts: float
    preparations: float
    essence_attempts: float


@dataclass(frozen=True)
class RenewalCostEstimate:
    """Seeded empirical p90 and its DKW probability-space interval."""

    p90: float
    interval_lower: float
    interval_upper: float
    samples: int
    seed: int
    confidence: float
    dkw_epsilon: float
    sample_mean: float
    sample_standard_error: float
    method: str = "estimated-dkw-renewal-monte-carlo"


def renewal_metrics(
    preparation_p: float,
    essence_price: float,
    p: float,
    b: float,
    reforge_cost: float,
    *,
    base_cost: float = 0,
) -> RenewalMetrics:
    """Return exact costs and attempt counts for the stated renewal law.

    ``p`` is final success per tagged reforge and ``b`` is a failed result
    with three prefixes.  Such a result restarts the same base's Envy
    preparation; other failures retain the protected suffixes and reforge.
    """
    preparation = _probability(preparation_p, "preparation_p", allow_zero=False)
    success = _probability(p, "p", allow_zero=False)
    full_failure = _probability(b, "b")
    if full_failure > 1 - success + 1e-12:
        raise ValueError("b must not exceed 1-p")
    full_failure = min(full_failure, 1 - success)
    essence = _nonnegative(essence_price, "essence_price")
    reforge = _nonnegative(reforge_cost, "reforge_cost")
    base = _nonnegative(base_cost, "base_cost")

    preparation_cost = essence / preparation
    reforge_attempts = 1 / success
    preparations = 1 + full_failure / success
    essence_attempts = preparations / preparation
    mean = base + preparation_cost + (reforge + full_failure * preparation_cost) / success
    if not all(math.isfinite(value) for value in (mean, reforge_attempts, preparations, essence_attempts)):
        raise ValueError("renewal result is not finite")
    return RenewalMetrics(preparation_cost, mean, reforge_attempts, preparations, essence_attempts)


def estimate_renewal_cost_p90(
    preparation_p: float,
    essence_price: float,
    p: float,
    b: float,
    reforge_cost: float,
    *,
    base_cost: float = 0,
    samples: int = 50_000,
    seed: int = 20260921,
    confidence: float = 0.99,
) -> RenewalCostEstimate:
    """Sample the exact renewal cost law with bounded independent NumPy draws.

    ``K`` is geometric final-reforge count, ``R`` counts full-prefix failures
    among its failed reforges, and ``J`` is the total number of Envy attempts
    for ``R + 1`` preparations.  DKW bounds quantify uncertainty in the
    percentile estimate, not variation in a completed item's cost.
    """
    metrics = renewal_metrics(
        preparation_p, essence_price, p, b, reforge_cost, base_cost=base_cost
    )
    preparation = _probability(preparation_p, "preparation_p", allow_zero=False)
    success = _probability(p, "p", allow_zero=False)
    full_failure = _probability(b, "b")
    full_failure = min(full_failure, 1 - success)
    essence = _nonnegative(essence_price, "essence_price")
    reforge = _nonnegative(reforge_cost, "reforge_cost")
    base = _nonnegative(base_cost, "base_cost")
    trial_count = _positive_integer(samples, "samples")
    parsed_seed = _integer(seed, "seed")
    coverage = _probability(confidence, "confidence")
    if coverage >= 1:
        raise ValueError("confidence must be in [0, 1)")
    epsilon = math.sqrt(math.log(2 / (1 - coverage)) / (2 * trial_count))
    if epsilon >= 0.1:
        raise ValueError("samples are insufficient to bracket the 0.9 quantile")

    rng = np.random.default_rng(parsed_seed)
    attempts = rng.geometric(success, size=trial_count)
    if success == 1:
        resets = np.zeros(trial_count, dtype=np.int64)
    else:
        resets = rng.binomial(attempts - 1, full_failure / (1 - success))
    preparation_count = resets + 1
    essence_attempts = rng.negative_binomial(preparation_count, preparation) + preparation_count
    costs = base + attempts * reforge + essence_attempts * essence
    if not np.isfinite(costs).all() or not math.isfinite(metrics.mean_cost):
        raise ValueError("renewal result is not finite")
    ordered = np.sort(costs)
    sample_mean = float(np.mean(costs))
    sample_standard_error = float(np.std(costs, ddof=1) / math.sqrt(trial_count))
    return RenewalCostEstimate(
        _higher_quantile(ordered, 0.9),
        _higher_quantile(ordered, max(0.0, 0.9 - epsilon)),
        _higher_quantile(ordered, min(1.0, 0.9 + epsilon)),
        trial_count,
        parsed_seed,
        coverage,
        epsilon,
        sample_mean,
        sample_standard_error,
    )


def _higher_quantile(ordered: np.ndarray, probability: float) -> float:
    rank = max(0, min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1))
    return float(ordered[rank])


def _probability(value: object, name: str, *, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    result = float(value)
    if result < 0 or result > 1 or (not allow_zero and result == 0):
        lower = "(0" if not allow_zero else "[0"
        raise ValueError(f"{name} must be in {lower}, 1]")
    return result


def _nonnegative(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return float(value)


def _positive_integer(value: object, name: str) -> int:
    result = _integer(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value
