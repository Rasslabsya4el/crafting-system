"""Pareto marking and bounded utility-threshold policy comparisons.

The comparison rules are the lead-authored contract in
``docs/design/build_contract.md`` and ``docs/DECISIONS.md`` decision D18.
They rank evaluated policies; they do not define crafting mechanics or costs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
import math
from numbers import Real
from typing import Any

from craftoracle.optimizer import optimize_policies as evaluate_policies


_METRICS = (
    "expected_cost",
    "cost_p90",
    "irreversible_failure_risk",
    "expected_utility",
)


def pareto_frontier(records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return all nondominated records in their original stable order.

    Cost, p90 cost, and irreversible risk are minimized. Expected terminal
    utility is maximized. Equal points remain because neither is strictly
    better than the other.
    """
    candidates = list(records)
    metrics = [_metrics(record) for record in candidates]
    return [
        candidate
        for index, candidate in enumerate(candidates)
        if not any(
            other_index != index and _dominates(other_metrics, metrics[index])
            for other_index, other_metrics in enumerate(metrics)
        )
    ]


def evaluate_frontier(
    spec: object,
    loadout: object,
    data: object,
    *,
    thresholds: Sequence[float] | None = None,
    item_level_range: str | Sequence[int] | None = None,
) -> dict[str, object]:
    """Evaluate policies and mark their Pareto frontier.

    A comparison evaluates each requested utility stopping rule against one
    local raw-distribution cache. The caller's immutable item spec is replaced
    per threshold rather than modified in place.
    """
    if thresholds is None:
        return _mark_frontier(_evaluate(spec, loadout, data, {}, item_level_range))

    parsed_thresholds = _comparison_thresholds(spec, thresholds)
    distribution_cache: dict[object, object] = {}
    combined_ranked: list[Mapping[str, Any]] = []
    combined_unavailable: list[Mapping[str, Any]] = []
    assumptions: list[Any] | None = None
    extras: dict[str, object] | None = None
    level_search_by_threshold: list[dict[str, object]] = []

    for threshold in parsed_thresholds:
        variant_spec = replace(spec, threshold=threshold)
        result = _evaluate(variant_spec, loadout, data, distribution_cache, item_level_range)
        ranked, unavailable, result_assumptions = _result_records(result)
        if assumptions is None:
            assumptions = list(result_assumptions)
            extras = {key: value for key, value in result.items() if key not in {"ranked", "unavailable", "assumptions", "item_level_search"}}
        if "item_level_search" in result:
            level_search_by_threshold.append({"threshold": threshold, "search": result["item_level_search"]})
        combined_ranked.extend(_tag_threshold(record, threshold) for record in ranked)
        combined_unavailable.extend(_tag_threshold(record, threshold) for record in unavailable)

    combined_ranked.sort(key=lambda record: (*_sort_metrics(record), _record_id(record)))
    combined: dict[str, object] = {
        **({} if extras is None else extras),
        **({} if not level_search_by_threshold else {"item_level_search_by_threshold": level_search_by_threshold}),
        "ranked": combined_ranked,
        "unavailable": combined_unavailable,
        "assumptions": [] if assumptions is None else assumptions,
    }
    return _mark_frontier(combined)


def _evaluate(spec, loadout, data, distribution_cache, item_level_range):
    arguments = {"distribution_cache": distribution_cache}
    if item_level_range is not None:
        arguments["item_level_range"] = item_level_range
    return evaluate_policies(spec, loadout, data, **arguments)


def _mark_frontier(result: Mapping[str, object]) -> dict[str, object]:
    ranked, unavailable, assumptions = _result_records(result)
    for record in ranked:
        _metrics(record)
    frontier_records = pareto_frontier(ranked)
    frontier_ids = {id(record) for record in frontier_records}
    return {
        **dict(result),
        "ranked": [{**record, "frontier": id(record) in frontier_ids} for record in ranked],
        "unavailable": [dict(record) for record in unavailable],
        "assumptions": list(assumptions),
    }


def _comparison_thresholds(spec: object, thresholds: Sequence[float]) -> tuple[float, ...]:
    if getattr(spec, "value_table", None) is None:
        raise ValueError("threshold comparison is only valid for a utility item specification")
    if isinstance(thresholds, (str, bytes)):
        raise ValueError("comparison thresholds must be a non-empty sequence")
    try:
        raw_thresholds = tuple(thresholds)
    except TypeError as error:
        raise ValueError("comparison thresholds must be a non-empty sequence") from error
    if not raw_thresholds:
        raise ValueError("comparison thresholds must be non-empty")

    minimum = _finite_number(getattr(spec, "threshold", None), "item specification threshold")
    parsed = tuple(_finite_number(value, "comparison threshold") for value in raw_thresholds)
    if len(set(parsed)) != len(parsed):
        raise ValueError("comparison thresholds must be distinct")
    if any(value < minimum for value in parsed):
        raise ValueError("comparison thresholds must be at least the item specification threshold")
    return parsed


def _result_records(result: Mapping[str, object]) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Any]]:
    if not isinstance(result, Mapping):
        raise ValueError("policy evaluator must return an object")
    ranked = result.get("ranked")
    unavailable = result.get("unavailable")
    assumptions = result.get("assumptions")
    if not isinstance(ranked, list) or not isinstance(unavailable, list) or not isinstance(assumptions, list):
        raise ValueError("policy evaluator result requires ranked, unavailable, and assumptions lists")
    if not all(isinstance(record, Mapping) for record in [*ranked, *unavailable]):
        raise ValueError("policy evaluator records must be objects")
    return ranked, unavailable, assumptions


def _tag_threshold(record: Mapping[str, Any], threshold: float) -> dict[str, Any]:
    return {
        **dict(record),
        "id": f"{_record_id(record)}@{_threshold_id(threshold)}",
        "stopping_threshold": threshold,
    }


def _threshold_id(threshold: float) -> str:
    if threshold.is_integer():
        return str(int(threshold))
    return repr(threshold)


def _record_id(record: Mapping[str, Any]) -> str:
    identifier = record.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("policy record id must be a non-empty string")
    return identifier


def _metrics(record: Mapping[str, Any]) -> tuple[float, float, float, float]:
    if not isinstance(record, Mapping):
        raise ValueError("policy record must be an object")
    expected_cost, cost_p90, risk, utility = (
        _finite_number(record.get(metric), metric)
        for metric in _METRICS
    )
    return expected_cost, cost_p90, risk, utility


def _sort_metrics(record: Mapping[str, Any]) -> tuple[float, float]:
    expected_cost, cost_p90, _, _ = _metrics(record)
    return expected_cost, cost_p90


def _dominates(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> bool:
    left_cost, left_p90, left_risk, left_utility = left
    right_cost, right_p90, right_risk, right_utility = right
    no_worse = (
        left_cost <= right_cost
        and left_p90 <= right_p90
        and left_risk <= right_risk
        and left_utility >= right_utility
    )
    strictly_better = (
        left_cost < right_cost
        or left_p90 < right_p90
        or left_risk < right_risk
        or left_utility > right_utility
    )
    return no_worse and strictly_better


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)
