"""Exact ordinary-catalyst quality transitions and finite finishing policies.

Sources: docs/mechanics/quality_catalysts.md S46/S47, read 2026-09-21.
S47 supplies the documented increment formula and adjacent-integer law. S46
supplies the ordinary catalyst names and the 3.15 metadata-preservation rule.
"""

from __future__ import annotations

from dataclasses import replace
import math
from numbers import Real
import random

from craftoracle.actions import ActionData, _validate_item
from craftoracle.item_model import ItemState


CATALYST_SOURCES = {
    "confidence": "documented",
    "increment": "S47 https://www.poewiki.net/index.php?title=Quality&oldid=1673652, Amount",
    "eligibility": "S46 https://www.poewiki.net/index.php?title=Catalyst&oldid=1675910",
}
"""Source pointers retained with the first ordinary-catalyst implementation."""

REGULAR_CATALYSTS = frozenset((
    "Abrasive", "Accelerating", "Fertile", "Imbued", "Intrinsic",
    "Noxious", "Prismatic", "Tempering", "Turbulent", "Unstable",
))
_JEWELLERY_TYPES = frozenset(("Ring", "Amulet", "Belt"))
_Q9_FLAGS = ("corrupted", "influenced", "fractured", "synthesised", "mirrored", "split")
_CATALYST_NAMES = {name.casefold(): name for name in REGULAR_CATALYSTS}


def catalyst_distribution(
    item: ItemState,
    data: ActionData,
    catalyst_type: str,
) -> dict[ItemState, float]:
    """Return one ordinary catalyst's exact quality/type state distribution.

    It deliberately preserves all affixes and item identity. The result is
    keyed by ``ItemState`` rather than a modifier-only outcome projection.
    """
    catalyst_type = _normalise_catalyst_type(catalyst_type)
    _validate_catalyst_input(item, data, catalyst_type)
    current_quality = item.quality if item.catalyst_type == catalyst_type else 0
    result: dict[ItemState, float] = {}
    for gain, probability in _increment_distribution(item.item_level).items():
        outcome = replace(
            item,
            quality=min(20, current_quality + gain),
            catalyst_type=catalyst_type,
        )
        result[outcome] = result.get(outcome, 0.0) + probability
    return result


def apply_catalyst(
    item: ItemState,
    data: ActionData,
    catalyst_type: str,
    *,
    rng: random.Random,
) -> ItemState:
    """Sample one ordinary catalyst application from its exact distribution."""
    if not isinstance(rng, random.Random):
        raise ValueError("rng must be random.Random")
    catalyst_type = _normalise_catalyst_type(catalyst_type)
    _validate_catalyst_input(item, data, catalyst_type)
    current_quality = item.quality if item.catalyst_type == catalyst_type else 0
    gain = _sample_increment(item.item_level, rng)
    return replace(item, quality=min(20, current_quality + gain), catalyst_type=catalyst_type)


def plan_catalyst(
    item: ItemState,
    data: ActionData,
    catalyst_type: str,
    target_quality: int,
    unit_price: Real,
) -> dict[str, object]:
    """Return an exact finite repeat-until-target ordinary-catalyst policy."""
    catalyst_type = _normalise_catalyst_type(catalyst_type)
    _validate_catalyst_input(item, data, catalyst_type)
    if isinstance(target_quality, bool) or not isinstance(target_quality, int) or not 1 <= target_quality <= 20:
        raise ValueError("target_quality must be an integer from 1 through 20")
    if isinstance(unit_price, bool) or not isinstance(unit_price, Real) or not math.isfinite(unit_price) or unit_price < 0:
        raise ValueError("unit_price must be a finite non-negative number")

    price = float(unit_price)
    start = item if item.catalyst_type == catalyst_type else replace(item, quality=0, catalyst_type=None)
    expected = _backward_expected_applications(start.quality, item.item_level, target_quality)
    count_distribution, final_distribution = _forward_finish_distributions(start, data, catalyst_type, target_quality)
    p90 = _quantile_count(count_distribution, 0.9)
    if price == 0.0:
        cost_distribution = {0.0: 1.0}
    else:
        cost_distribution: dict[float, float] = {}
        for count, probability in count_distribution.items():
            cost = count * price
            cost_distribution[cost] = cost_distribution.get(cost, 0.0) + probability
    return {
        "count_distribution": count_distribution,
        "final_quality_distribution": final_distribution,
        "cost_distribution": cost_distribution,
        "expected_applications": expected,
        "applications_p90": p90,
        "expected_cost": expected * price,
        "cost_p90": p90 * price,
        "steps": (f"Apply {catalyst_type} Catalyst until quality is at least {target_quality}%.",),
        "source_confidence": CATALYST_SOURCES["confidence"],
        "sources": CATALYST_SOURCES,
        "price_disclaimer": "Unit price is supplied by the caller; no market-price claim is made.",
    }


def _increment_distribution(item_level: int) -> dict[int, float]:
    f_value = max(1.0, min(30.0 * math.exp(-item_level / 30.0) - 0.3, 20.0))
    lower = math.floor(f_value)
    upper = math.ceil(f_value)
    if lower == upper:
        return {lower: 1.0}
    return {lower: upper - f_value, upper: f_value - lower}


def _sample_increment(item_level: int, rng: random.Random) -> int:
    increments = _increment_distribution(item_level)
    if len(increments) == 1:
        return next(iter(increments))
    lower, upper = sorted(increments)
    return upper if rng.random() < increments[upper] else lower


def _backward_expected_applications(start_quality: int, item_level: int, target_quality: int) -> float:
    expected = [0.0] * 21
    gains = _increment_distribution(item_level)
    for quality in range(target_quality - 1, -1, -1):
        expected[quality] = 1.0 + sum(
            probability * expected[min(20, quality + gain)]
            for gain, probability in gains.items()
        )
    return expected[start_quality]


def _forward_finish_distributions(
    start: ItemState,
    data: ActionData,
    catalyst_type: str,
    target_quality: int,
) -> tuple[dict[int, float], dict[ItemState, float]]:
    if start.quality >= target_quality:
        return {0: 1.0}, {start: 1.0}

    active = {start: 1.0}
    count_distribution: dict[int, float] = {}
    final_distribution: dict[ItemState, float] = {}
    # Every ordinary gain is at least one, so no path needs more than 20 applications.
    for applications in range(1, 21):
        next_active: dict[ItemState, float] = {}
        for state, state_probability in active.items():
            for outcome, probability in catalyst_distribution(state, data, catalyst_type).items():
                mass = state_probability * probability
                if outcome.quality >= target_quality:
                    count_distribution[applications] = count_distribution.get(applications, 0.0) + mass
                    final_distribution[outcome] = final_distribution.get(outcome, 0.0) + mass
                else:
                    next_active[outcome] = next_active.get(outcome, 0.0) + mass
        if not next_active:
            return _normalise_distribution(count_distribution), _normalise_distribution(final_distribution)
        active = next_active
    raise AssertionError("ordinary catalyst path exceeded its 20-application bound")


def _quantile_count(distribution: dict[int, float], percentile: float) -> int:
    cumulative = 0.0
    for count in sorted(distribution):
        cumulative += distribution[count]
        if cumulative >= percentile:
            return count
    raise AssertionError("finite catalyst count distribution has insufficient mass")


def _normalise_distribution(distribution: dict) -> dict:
    total = sum(distribution.values())
    if total <= 0.0:
        raise AssertionError("finite catalyst distribution has no probability mass")
    return {outcome: probability / total for outcome, probability in distribution.items()}


def _validate_catalyst_input(item: ItemState, data: ActionData, catalyst_type: str) -> None:
    if not isinstance(item, ItemState):
        raise ValueError("item must be an ItemState")
    if not isinstance(data, ActionData):
        raise ValueError("data must be ActionData")
    _validate_item(item, data)
    if any(getattr(item, flag) for flag in _Q9_FLAGS):
        raise NotImplementedError("out of tonight's slice: Q9")
    if isinstance(item.item_level, bool) or not isinstance(item.item_level, int) or item.item_level <= 0:
        raise ValueError("item level must be a positive integer")
    if isinstance(item.quality, bool) or not isinstance(item.quality, int) or not 0 <= item.quality <= 20:
        raise ValueError("quality must be an integer from 0 through 20")
    if item.catalyst_type is not None and item.catalyst_type not in REGULAR_CATALYSTS:
        raise ValueError("catalyst_type must be a supported regular catalyst or None")
    if item.quality > 0 and item.catalyst_type is None:
        raise ValueError("catalyst_type is required when quality is positive")
    base = data.bases.get(item.base_name)
    if not isinstance(base, dict):
        raise ValueError("base must be present in ActionData")
    if base.get("type") not in _JEWELLERY_TYPES:
        raise ValueError("catalyst requires a Ring, Amulet, or Belt jewellery base")


def _normalise_catalyst_type(catalyst_type: str) -> str:
    if isinstance(catalyst_type, str):
        canonical = _CATALYST_NAMES.get(catalyst_type.casefold())
        if canonical is not None:
            return canonical
    raise ValueError("supported regular catalyst is required; Tainted, Dextral, and Sinistral are unsupported")
