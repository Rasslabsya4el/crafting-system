"""Finite parameter search for the reviewed crafting-policy templates.

The choices and renewal laws in this module are the lead-authored policy
mathematics in ``docs/design/parameter-search.md`` (2026-09-21).  They do not
introduce any new game mechanics.  ``evaluate_fixed_policies`` remains the
explicit benchmark; this module enumerates only the finite grids documented
there and records the evaluated parameter rows on every selected policy.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import replace
import math
import time
from typing import Any

import numpy as np

from craftoracle.actions import ActionData, prepare_roll
from craftoracle.distributions import DrawEntry, OutcomeClass, probability
from craftoracle.item_model import ItemState, ModRef, resolve_pool
from craftoracle.policy_attempts import (
    correlated_attempt_metrics,
    estimate_correlated_attempt_p90,
    estimate_protected_cycle_p90,
    evaluate_grouped_schedule,
    protected_cycle_metrics,
    terminal_cost_atoms,
)
import craftoracle.policies as _fixed


_ENVY = "Metadata/Items/Currency/CurrencyEssenceEnvy3"
_SEED = 20260921
_SAMPLES = 50_000
_CONFIDENCE = 0.99
_MAGIC_WORK_SECONDS = 45.0
_LEVEL_SEARCH_WORK_SECONDS = 45.0


def optimize_policies(
    spec: object,
    loadout: object,
    data: ActionData,
    *,
    finish_bench_index: int | None = None,
    distribution_cache: MutableMapping[object, object] | None = None,
    item_level_range: str | Sequence[int] | None = None,
) -> dict[str, object]:
    """Evaluate the documented finite grids and select one row per template.

    Raw draw distributions belong to the caller-provided cache.  Price and
    target threshold are intentionally absent from the raw keys in the fixed
    action helpers; gate/stopping choices are part of the schedule keys here.
    """
    cache: MutableMapping[object, object] = {} if distribution_cache is None else distribution_cache
    levels, requested_interval, distinct_pool_count = _search_levels(spec, data, item_level_range)
    results: list[dict[str, object]] = []
    evaluated_levels: list[int] = []
    started = time.monotonic()
    incomplete_levels: list[int] = []
    for index, level in enumerate(levels):
        if item_level_range is not None and time.monotonic() - started > _LEVEL_SEARCH_WORK_SECONDS:
            incomplete_levels = levels[index:]
            break
        results.append(_optimize_one_level(
            _with_item_level(spec, level), loadout, data, cache, finish_bench_index
        ))
        evaluated_levels.append(level)
    merged = _merge_level_results(results)
    merged["item_level_search"] = {
        "requested_interval": list(requested_interval),
        "evaluated_item_levels": evaluated_levels,
        "evaluated_level_results": [
            {
                "item_level": level,
                "unavailable": [
                    {"id": row["id"], "reasons": list(row.get("reasons", ())) }
                    for row in result["unavailable"]
                ],
            }
            for level, result in zip(evaluated_levels, results)
        ],
        "distinct_pool_count": distinct_pool_count,
        "base_price_assumption": "The supplied base price is held constant at every allowed item level.",
        "complete": not incomplete_levels,
        "uncomputed_item_levels": incomplete_levels,
    }
    if incomplete_levels:
        for policy in merged["ranked"]:
            policy["item_level_search_status"] = "incomplete"
        merged["assumptions"] = [
            *merged["assumptions"],
            f"Item-level search stopped after {len(evaluated_levels)}/{len(levels)} distinct pools; displayed rows are not interval optima.",
        ]
    merged["assumptions"] = [
        *merged["assumptions"],
        "Optimizer searches only the documented finite parameter grids; it does not claim global optimality.",
        "The supplied base price is held constant across an opted-in item-level range.",
    ]
    return merged


def parse_item_level_range(value: str | Sequence[int]) -> tuple[int, int]:
    """Validate the opt-in inclusive ``MIN:MAX`` item-level interval."""
    if isinstance(value, str):
        pieces = value.split(":")
        if len(pieces) != 2 or any(not piece.strip() for piece in pieces):
            raise ValueError("item level range must be MIN:MAX")
        try:
            lower, upper = (int(piece) for piece in pieces)
        except ValueError as error:
            raise ValueError("item level range must be MIN:MAX integers") from error
    else:
        if isinstance(value, (bytes, bytearray)):
            raise ValueError("item level range must be MIN:MAX")
        try:
            lower, upper = tuple(value)
        except (TypeError, ValueError) as error:
            raise ValueError("item level range must contain exactly two integers") from error
    if any(isinstance(entry, bool) or not isinstance(entry, int) for entry in (lower, upper)):
        raise ValueError("item level range endpoints must be integers")
    if lower <= 0 or upper <= 0 or lower > upper:
        raise ValueError("item level range requires positive MIN <= MAX")
    return lower, upper


def _optimize_one_level(
    spec: object,
    loadout: object,
    data: ActionData,
    cache: MutableMapping[object, object],
    finish_bench_index: int | None,
) -> dict[str, object]:
    # Production keeps only ordinary fixed templates.  The legacy fixed
    # magic/protected p90 calculations are benchmarks and would otherwise be
    # computed only to be discarded by the grid rows below.
    fixed = _ordinary_fixed_rows(spec, loadout, data, cache)
    available = [
        _baseline_parameters(dict(row), spec, loadout, data)
        for row in fixed["ranked"]
    ]
    unavailable = [dict(row) for row in fixed["unavailable"]]

    for candidate in (
        _optimized_chaos(spec, loadout, data, cache),
        _optimized_magic(spec, loadout, data, cache),
        _optimized_protected(spec, loadout, data, cache),
        _optimized_harvest(spec, loadout, data, cache),
    ):
        _fixed._collect(candidate, available, unavailable)

    bench = _optimized_bench_finish(spec, loadout, data, cache, finish_bench_index)
    _fixed._collect(bench, available, unavailable)
    return _fixed._result(available, unavailable, data, getattr(loadout, "unit"))


def _ordinary_fixed_rows(spec, loadout, data, cache):
    """Keep only the fixed non-grid policy families for production ranking."""
    _fixed._validate_contract(spec, loadout, data)
    if _fixed._enabled_q9_flags(spec):
        raise NotImplementedError("out of tonight's slice: Q9")
    labels = _fixed._labels(spec)
    normal = _fixed._item(spec, "normal")
    available: list[dict[str, object]] = []
    unavailable: list[dict[str, object]] = []
    _fixed._collect(
        _fixed._alchemy_scour_policy(spec, loadout, data, normal, labels, cache),
        available,
        unavailable,
    )
    for essence_id in sorted(getattr(loadout, "allowed_essences")):
        _fixed._collect(
            _fixed._essence_policy(spec, loadout, data, normal, labels, essence_id, cache),
            available,
            unavailable,
        )
    return _fixed._result(available, unavailable, data, getattr(loadout, "unit"))


def _baseline_parameters(record: dict[str, object], spec: object, loadout: object, data: ActionData) -> dict[str, object]:
    identifier = str(record["id"])
    forced = None
    if identifier.startswith("essence-"):
        suffix = identifier.removeprefix("essence-")
        forced = next(
            (essence_id for essence_id in data.essences if essence_id.rsplit("/", 1)[-1] == suffix),
            None,
        )
    record["parameters"] = {
        "item_level": getattr(spec, "item_level"),
        "forced_essence_id": forced,
        "forced_essence_tier": data.essences[forced]["tier"] if forced is not None else None,
        "template": identifier,
        **_bench_target_parameters(spec, loadout, data),
    }
    record["candidate_count"] = 1
    record["parameter_audit"] = [{"parameters": record["parameters"], "expected_cost": record["expected_cost"]}]
    return record


def _optimized_chaos(spec: object, loadout: object, data: ActionData, cache: MutableMapping[object, object]) -> dict[str, object]:
    policy_id = "chaos-spam"
    name = "Chaos spam with Alchemy early-stop choice"
    prices, reasons = _fixed._requirements(loadout, ("alchemy", "chaos"), ("alchemy", "chaos"))
    if reasons:
        return _fixed._unavailable(policy_id, name, reasons)
    labels = _fixed._labels(spec)
    normal, rare = _fixed._item(spec, "normal"), _fixed._item(spec, "rare")
    alchemy = _fixed._action_distribution(cache, data, "alchemy", normal, labels)
    chaos = _fixed._action_distribution(cache, data, "chaos", rare, labels)
    a, p = _fixed._success_probability(spec, alchemy), _fixed._success_probability(spec, chaos)
    if p == 0:
        return _fixed._unavailable(policy_id, name, ["target is unreachable from the Chaos trial distribution"])

    candidates: list[dict[str, object]] = []
    for early_stop in (False, True):
        mean = _fixed._base_cost(loadout) + prices["alchemy"] + (1 - a if early_stop else 1) * prices["chaos"] / p
        p90 = _chaos_p90(
            a if early_stop else 0.0,
            p,
            _fixed._base_cost(loadout) + prices["alchemy"],
            prices["chaos"],
        )
        candidates.append({"parameters": {"item_level": getattr(spec, "item_level"), "alchemy_early_stop": early_stop, **_bench_target_parameters(spec, loadout, data)}, "mean": mean, "p90": p90})
    selected = min(candidates, key=lambda row: (float(row["mean"]), float(row["p90"]), str(row["parameters"])))
    early_stop = bool(selected["parameters"]["alchemy_early_stop"])
    final = _mix_completion_distributions(spec,
        (alchemy, a if early_stop else 0.0),
        (chaos, 1 - a if early_stop else 1.0),
    )
    policy = _fixed._policy(
        spec,
        loadout,
        policy_id,
        name,
        [
            _fixed._stage("Alchemy setup", a, 1, ("alchemy",), ("Stop on a completed Alchemy outcome." if early_stop else "This fixed choice discards every Alchemy outcome.",), alchemy),
            _fixed._stage("Chaos trial", p, (1 - a if early_stop else 1) / p, ("chaos",), ("Repeat Chaos only after an Alchemy non-completion." if early_stop else "Repeat Chaos until completion.",), chaos),
        ],
        float(selected["mean"]),
        float(selected["p90"]),
        "exact Alchemy/conditional-geometric Chaos mixture",
        final,
        ("alchemy", "chaos"),
        ("Apply Alchemy once.", "Use its selected early-stop rule, then repeat Chaos only on the remaining branch."),
        ("The p90 is from the actual early Alchemy atom plus the conditional geometric Chaos tail.",),
    )
    return _attach_search(policy, selected, candidates)


def _chaos_p90(alchemy_success: float, chaos_success: float, setup: float, chaos_price: float) -> float:
    if alchemy_success >= 0.9:
        return setup
    if chaos_success == 1:
        return setup + chaos_price
    tail = (1 - 0.9) / (1 - alchemy_success)
    draws = max(1, math.ceil(math.log(tail) / math.log1p(-chaos_success)))
    return setup + draws * chaos_price


def _optimized_magic(spec: object, loadout: object, data: ActionData, cache: MutableMapping[object, object]) -> dict[str, object]:
    policy_id = "magic-regal-exalt"
    name = "Magic, Regal, and bounded Exalt schedule"
    currencies = ("transmute", "alteration", "augmentation", "regal", "exalted", "scour")
    prices, reasons = _fixed._requirements(loadout, currencies, currencies)
    if reasons:
        return _fixed._unavailable(policy_id, name, reasons)
    if tuple(data.rules["magic_caps"]) != (1, 1) or tuple(data.rules["rare_caps"]) != (3, 3):
        return _fixed._unavailable(policy_id, name, ["magic grid requires ordinary 1/1 magic and 3/3 rare caps"])
    weights = _fixed._count_weights(data.rules["magic_count_weights"])
    if set(weights) != {1, 2}:
        return _fixed._unavailable(policy_id, name, ["magic grid requires one- and two-mod Alteration count outcomes only"])
    augmentation_probability = weights[1] / sum(weights.values())
    labels = _fixed._labels(spec)
    desired = _desired_labels(spec, labels)
    scenario = prepare_roll("alteration", _fixed._item(spec, "magic"), data, labels)
    candidates: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    started = time.monotonic()
    total = 2 * 3 * 4 * 4
    for early_stop in (False, True):
        for magic_gate in range(3):
            for regal_gate in range(4):
                for exalts in range(4):
                    if time.monotonic() - started > _MAGIC_WORK_SECONDS:
                        blocked = _fixed._unavailable(
                            policy_id,
                            name,
                            [f"optimization work limit reached after {len(audit)}/{total} evaluated magic grid rows; no partial optimum is reported"],
                        )
                        blocked["candidate_count"] = len(audit)
                        blocked["parameter_audit"] = audit
                        blocked["optimization_status"] = {"complete": False, "evaluated_rows": len(audit), "total_rows": total}
                        return blocked
                    stages = ((2, 1, 1), (1, 3, 3), *((1, 3, 3),) * exalts)
                    gates = (
                        lambda outcome, minimum=magic_gate: _desired_count(outcome, desired) >= minimum,
                        lambda outcome, minimum=regal_gate: _desired_count(outcome, desired) >= minimum,
                        *(None,) * exalts,
                    )
                    schedule = _magic_schedule(cache, scenario.entries, labels, desired, stages, gates, spec, early_stop)
                    atoms = terminal_cost_atoms(
                        schedule,
                        (prices["alteration"], prices["regal"], *(prices["exalted"],) * exalts),
                    )
                    success_atoms = _with_augmentation(atoms.success_atoms, augmentation_probability, prices["augmentation"])
                    failure_atoms = _with_augmentation(atoms.failure_atoms, augmentation_probability, prices["augmentation"])
                    parameters = {
                        "item_level": getattr(spec, "item_level"),
                        "magic_min_desired": magic_gate,
                        "regal_min_desired": regal_gate,
                        "max_exalts": exalts,
                        "early_stop": early_stop,
                        **_bench_target_parameters(spec, loadout, data),
                    }
                    if atoms.success_probability == 0:
                        audit.append({"parameters": parameters, "unavailable_reason": "target probability is zero"})
                        continue
                    metrics = correlated_attempt_metrics(
                        atoms.success_probability,
                        success_atoms,
                        failure_atoms,
                        reset_cost=prices["scour"] + prices["transmute"],
                        setup_cost=_fixed._base_cost(loadout) + prices["transmute"],
                    )
                    candidate = {
                        "parameters": parameters,
                        "mean": metrics.mean_cost,
                        "schedule": schedule,
                        "atoms": atoms,
                        "success_atoms": success_atoms,
                        "failure_atoms": failure_atoms,
                    }
                    candidates.append(candidate)
                    audit.append({"parameters": parameters, "expected_cost": metrics.mean_cost})
    if not candidates:
        blocked = _fixed._unavailable(policy_id, name, ["target is unreachable in every documented magic-grid row"])
        blocked["candidate_count"] = len(audit)
        blocked["parameter_audit"] = audit
        return blocked
    selected = min(candidates, key=lambda row: (float(row["mean"]), str(row["parameters"])))
    tied = [row for row in candidates if math.isclose(float(row["mean"]), float(selected["mean"]), rel_tol=0, abs_tol=1e-12)]
    _attach_magic_p90(selected, prices, loadout)
    for row in tied:
        if row is not selected:
            _attach_magic_p90(row, prices, loadout)
    selected = min(tied, key=lambda row: (float(row["mean"]), float(row["p90"]), str(row["parameters"])))
    schedule = selected["schedule"]
    assert hasattr(schedule, "success_by_stage")
    terminal = _normalized_distribution(_merge_distributions(schedule.success_by_stage))
    stages = _magic_policy_stages(schedule, selected, prices, spec, labels, cache, loadout, data, scenario.entries, desired)
    policy = _fixed._policy(
        spec,
        loadout,
        policy_id,
        name,
        stages,
        float(selected["mean"]),
        float(selected["p90"]),
        "sampled correlated finite attempt p90; exact mean",
        terminal,
        ("regal", "exalted", "scour"),
        ("Transmute once, then reroll the magic item with Alteration and optional Augmentation.", "Apply Regal and only the selected bounded number of Exalts while gate and stopping rules permit."),
        ("Every paid stage comes from the selected joint schedule; failures restart with Scour plus Transmute.",),
    )
    estimate = selected["estimate"]
    policy.update({
        "cost_p90_interval": [estimate.interval_lower, estimate.interval_upper],
        "cost_sample_count": estimate.samples,
        "cost_seed": _SEED,
        "cost_confidence": estimate.confidence,
        "cost_error_bound": estimate.dkw_epsilon,
        "schedule_peak_live_states": schedule.peak_live_states,
    })
    return _attach_search(policy, selected, candidates, audit)


def _attach_magic_p90(row: dict[str, object], prices: Mapping[str, float], loadout: object) -> None:
    atoms = row["atoms"]
    estimate = estimate_correlated_attempt_p90(
        atoms.success_probability,
        row["success_atoms"],
        row["failure_atoms"],
        reset_cost=prices["scour"] + prices["transmute"],
        setup_cost=_fixed._base_cost(loadout) + prices["transmute"],
        rng=np.random.default_rng(_SEED),
        samples=_SAMPLES,
        confidence=_CONFIDENCE,
    )
    row["p90"] = estimate.p90
    row["estimate"] = estimate


def _magic_schedule(cache, entries, labels, desired, stages, gates, spec, early_stop):
    key = (
        "optimizer-magic-schedule",
        tuple((entry.mod_id, entry.type, entry.group, entry.weight) for entry in entries),
        tuple(stages),
        tuple(_gate_key(gate) for gate in gates),
        tuple(sorted(labels.items())),
        tuple(sorted(desired)),
        bool(early_stop),
        _target_signature(spec),
    )
    if key not in cache:
        cache[key] = evaluate_grouped_schedule(
            entries,
            labels,
            stages,
            gates,
            lambda outcome: _fixed._completes(spec, outcome),
            early_stop=early_stop,
        )
    return cache[key]


def _gate_key(gate: object) -> object:
    if gate is None:
        return None
    defaults = getattr(gate, "__defaults__", None)
    return defaults if defaults is not None else repr(gate)


def _magic_policy_stages(schedule, selected, prices, spec, labels, cache, loadout, data, entries, desired):
    parameters = selected["parameters"]
    exalts = parameters["max_exalts"]
    attempts = 1 / schedule.success_probability
    gates = (
        lambda outcome, minimum=parameters["magic_min_desired"]: _desired_count(outcome, desired) >= minimum,
        lambda outcome, minimum=parameters["regal_min_desired"]: _desired_count(outcome, desired) >= minimum,
        *(None,) * exalts,
    )
    stage_specs = ((2, 1, 1), (1, 3, 3), *((1, 3, 3),) * exalts)
    stage_distributions = [
        _magic_prefix_distribution(
            cache, entries, labels, desired, stage_specs, gates, spec,
            bool(parameters["early_stop"]), index,
        )
        for index in range(len(stage_specs))
    ]
    transmute = _fixed._action_distribution(cache, data, "transmute", _fixed._item(spec, "normal"), labels)
    stages = [
        _fixed._stage("transmute setup/reset", 1, attempts, ("transmute",), ("First Transmute is setup; every failed attempt pays Scour then Transmute.",), transmute),
        _fixed._stage("magic two-mod gate", schedule.stage_reach_probabilities[0], attempts * schedule.stage_reach_probabilities[0], ("alteration", "augmentation?"), (f"Keep only states with at least {parameters['magic_min_desired']} desired labels unless the selected early stop completes the target.",), stage_distributions[0]),
        _fixed._stage("Regal gate", schedule.stage_reach_probabilities[1], attempts * schedule.stage_reach_probabilities[1], ("regal",), (f"Keep only states with at least {parameters['regal_min_desired']} desired labels unless the selected early stop completes the target.",), stage_distributions[1]),
    ]
    for index in range(exalts):
        reaches = schedule.stage_reach_probabilities[index + 2]
        stages.append(_fixed._stage(f"Exalt {index + 1}", reaches, attempts * reaches, ("exalted",), ("Stop when the selected rule permits; otherwise continue only while an Exalt remains.",), stage_distributions[index + 2]))
    return stages


def _magic_prefix_distribution(cache, entries, labels, desired, stages, gates, spec, early_stop, index):
    prefix_schedule = _magic_schedule(
        cache,
        entries,
        labels,
        desired,
        stages[: index + 1],
        (*gates[:index], None),
        spec,
        early_stop,
    )
    return _normalized_distribution(_merge_distributions((
        prefix_schedule.success_by_stage[-1], prefix_schedule.failure_by_stage[-1],
    )))


def _optimized_protected(spec: object, loadout: object, data: ActionData, cache: MutableMapping[object, object]) -> dict[str, object]:
    context = _protected_context(spec, loadout, data, cache)
    policy_id, name = "suffix-protected-life", "Envy suffix preparation and protected life"
    if "reasons" in context:
        return _fixed._unavailable(policy_id, name, context["reasons"])
    candidates: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    for max_prefixes in (1, 2):
        for min_elemental in (1, 2):
            for early_stop in (False, True):
                early, prepared = _preparation_classes(context["stage_one"], spec, context["labels"], max_prefixes, min_elemental, early_stop)
                u, v = _mass(early), _mass(prepared)
                for exalts in (1, 2, 3):
                    cycle = _protected_exalt_cycle(context, exalts, cache)
                    parameters = {
                        "item_level": getattr(spec, "item_level"),
                        "max_prefixes": max_prefixes,
                        "minimum_desired_elemental_suffixes": min_elemental,
                        "preparation_early_stop": early_stop,
                        "cycle_kind": "protected_exalt",
                        "max_exalts": exalts,
                        "bench_finish_id": None,
                        **_bench_target_parameters(spec, loadout, data),
                    }
                    if u == 0 and v == 0:
                        audit.append({"parameters": parameters, "unavailable_reason": "preparation gate has zero probability"})
                        continue
                    if cycle["p"] == 0:
                        audit.append({"parameters": parameters, "unavailable_reason": "protected cycle target probability is zero"})
                        continue
                    metrics = protected_cycle_metrics(
                        u, v, context["envy_price"], cycle["p"], cycle["b"], cycle["failed_cost"], cycle["success_atoms"], base_cost=context["base_cost"]
                    )
                    candidate = {
                        "parameters": parameters,
                        "mean": metrics.mean_cost,
                        "u": u,
                        "v": v,
                        "early": early,
                        "prepared": prepared,
                        "cycle": cycle,
                        "metrics": metrics,
                    }
                    candidates.append(candidate)
                    audit.append({"parameters": parameters, "expected_cost": metrics.mean_cost})
    if not candidates:
        blocked = _fixed._unavailable(policy_id, name, ["no reachable protected Exalt grid row"])
        blocked["candidate_count"] = len(audit)
        blocked["parameter_audit"] = audit
        return blocked
    return _finalize_protected_candidate(spec, loadout, context, candidates, audit, policy_id, name, "Exalt")


def _optimized_harvest(spec: object, loadout: object, data: ActionData, cache: MutableMapping[object, object]) -> dict[str, object]:
    context = _protected_context(spec, loadout, data, cache, harvest=True)
    policy_id, name = "suffix-protected-harvest-life", "Envy suffix preparation and protected Harvest life"
    if "reasons" in context:
        return _fixed._unavailable(policy_id, name, context["reasons"])
    candidates: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    for max_prefixes in (1, 2):
        for min_elemental in (1, 2):
            for early_stop in (False, True):
                early, prepared = _preparation_classes(context["stage_one"], spec, context["labels"], max_prefixes, min_elemental, early_stop)
                u, v = _mass(early), _mass(prepared)
                cycle = context["cycle"]
                parameters = {
                    "item_level": getattr(spec, "item_level"),
                    "max_prefixes": max_prefixes,
                    "minimum_desired_elemental_suffixes": min_elemental,
                    "preparation_early_stop": early_stop,
                    "cycle_kind": "protected_harvest_life",
                    "harvest_type_filter": "first_only",
                    "bench_finish_id": None,
                    **_bench_target_parameters(spec, loadout, data),
                }
                if u == 0 and v == 0:
                    audit.append({"parameters": parameters, "unavailable_reason": "preparation gate has zero probability"})
                    continue
                if cycle["p"] == 0:
                    audit.append({"parameters": parameters, "unavailable_reason": "protected cycle target probability is zero"})
                    continue
                metrics = protected_cycle_metrics(
                    u, v, context["envy_price"], cycle["p"], cycle["b"], cycle["failed_cost"], cycle["success_atoms"], base_cost=context["base_cost"]
                )
                candidate = {
                    "parameters": parameters,
                    "mean": metrics.mean_cost,
                    "u": u,
                    "v": v,
                    "early": early,
                    "prepared": prepared,
                    "cycle": cycle,
                    "metrics": metrics,
                }
                candidates.append(candidate)
                audit.append({"parameters": parameters, "expected_cost": metrics.mean_cost})
    if not candidates:
        blocked = _fixed._unavailable(policy_id, name, ["no reachable protected Harvest grid row"])
        blocked["candidate_count"] = len(audit)
        blocked["parameter_audit"] = audit
        return blocked
    return _finalize_protected_candidate(spec, loadout, context, candidates, audit, policy_id, name, "Harvest")


def _protected_context(spec, loadout, data, cache, *, harvest: bool = False):
    target_reason = _fixed._protected_target_reason(spec, data)
    if target_reason is not None:
        return {"reasons": [target_reason]}
    currencies = (_ENVY, "harvest_reforge:life") if harvest else (_ENVY, "scour", "exalted")
    actions = ("essence", "bench", "harvest_reforge:life") if harvest else ("essence", "bench", "scour", "exalted")
    prices, reasons = _fixed._requirements(loadout, actions, currencies, essence_id=_ENVY, bench_index=729)
    if reasons:
        return {"reasons": reasons}
    lock_reason = _fixed._suffix_lock_reason(spec, data)
    if lock_reason is not None:
        return {"reasons": [lock_reason]}
    labels = _fixed._labels(spec)
    stage_one = _fixed._action_distribution(cache, data, "essence", _fixed._item(spec, "normal"), labels, essence_id=_ENVY)
    bench_price, price_reason = _fixed._bench_price(loadout, 729)
    if price_reason is not None:
        return {"reasons": [price_reason]}
    prefix_entries = tuple(
        DrawEntry(entry.mod_id, entry.type, entry.group, entry.weight)
        for entry in resolve_pool(_fixed._item(spec, "rare"), data.bases, data.mods, "Prefix")
    )
    suffix_groups = {
        entry.group
        for entry in resolve_pool(_fixed._item(spec, "rare"), data.bases, data.mods, "Suffix")
    }
    overlap = {entry.group for entry in prefix_entries} & suffix_groups
    if overlap:
        return {"reasons": ["prefix/suffix group intersection prevents the required independent protected-prefix calculation"]}
    if not prefix_entries or not any(entry.mod_id == "IncreasedLife9" for entry in prefix_entries):
        return {"reasons": ["required IncreasedLife9 prefix is absent from the ordinary prefix pool"]}
    context: dict[str, object] = {
        "labels": labels,
        "stage_one": stage_one,
        "envy_price": prices[_ENVY],
        "base_cost": _fixed._base_cost(loadout),
        "prefix_entries": prefix_entries,
        "lock_cost": bench_price + (0 if harvest else prices["scour"]),
        "exalt_price": None if harvest else prices["exalted"],
    }
    if harvest:
        representatives, representative_reason = _fixed._harvest_suffix_representatives(spec, data)
        if representative_reason is not None:
            return {"reasons": [representative_reason]}
        item = ItemState(getattr(spec, "base"), getattr(spec, "item_level"), "rare", (*representatives, _fixed._bench_ref(data, 729)))
        prefixes = _fixed._harvest_distribution(cache, data, item, {"IncreasedLife9": labels["IncreasedLife9"]})
        life_label = labels["IncreasedLife9"]
        p = probability(prefixes, lambda outcome: life_label in outcome.labels)
        b = probability(prefixes, lambda outcome: outcome.prefixes == 3 and life_label not in outcome.labels)
        cycle_cost = bench_price + prices["harvest_reforge:life"]
        context["cycle"] = {
            "p": p,
            "b": b,
            "failed_cost": cycle_cost,
            "success_atoms": ((cycle_cost, 1.0),),
            "success_by_stage": ( {outcome: mass for outcome, mass in prefixes.items() if life_label in outcome.labels}, ),
            "all_distribution": prefixes,
            "kind": "harvest",
        }
    return context


def _protected_exalt_cycle(context: Mapping[str, object], exalts: int, cache: MutableMapping[object, object]) -> dict[str, object]:
    labels = context["labels"]
    entries = context["prefix_entries"]
    life_label = labels["IncreasedLife9"]
    key = ("optimizer-protected-exalt", entries, life_label, exalts)
    if key not in cache:
        cache[key] = evaluate_grouped_schedule(
            entries,
            {"IncreasedLife9": life_label},
            ((1, 3, 3),) * exalts,
            target_predicate=lambda outcome: life_label in outcome.labels,
            early_stop=True,
        )
    schedule = cache[key]
    first_hits = tuple(_mass(row) for row in schedule.success_by_stage)
    p = math.fsum(first_hits)
    price = context["exalt_price"]
    assert price is not None
    lock_cost = float(context["lock_cost"])
    success_atoms = tuple((lock_cost + (index + 1) * price, mass / p) for index, mass in enumerate(first_hits) if mass)
    return {
        "p": p,
        "b": 1 - p if exalts == 3 else 0.0,
        "failed_cost": lock_cost + exalts * price,
        "success_atoms": success_atoms,
        "success_by_stage": schedule.success_by_stage,
        "all_distribution": _merge_distributions((*schedule.success_by_stage, *schedule.failure_by_stage)),
        "first_hits": first_hits,
        "kind": "exalt",
    }


def _finalize_protected_candidate(spec, loadout, context, candidates, audit, policy_id, name, action_name):
    selected = min(candidates, key=lambda row: (float(row["mean"]), str(row["parameters"])))
    ties = [row for row in candidates if math.isclose(float(row["mean"]), float(selected["mean"]), rel_tol=0, abs_tol=1e-12)]
    _attach_protected_p90(selected, context)
    for row in ties:
        if row is not selected:
            _attach_protected_p90(row, context)
    selected = min(ties, key=lambda row: (float(row["mean"]), float(row["p90"]), str(row["parameters"])))
    metrics = selected["metrics"]
    cycle = selected["cycle"]
    terminal = _protected_terminal(selected["early"], selected["prepared"], cycle, context["labels"], metrics)
    attempt = _protected_attempt_distribution(selected["prepared"], cycle, context["labels"])
    params = selected["parameters"]
    stages = [
        _fixed._stage(
            "Envy preparation",
            selected["u"] + selected["v"],
            metrics.expected_preparations,
            (f"essence:{_ENVY}",),
            (f"Keep full three-suffix states with <= {params['max_prefixes']} prefixes and >= {params['minimum_desired_elemental_suffixes']} desired elemental suffixes.",),
            context["stage_one"],
        ),
        _fixed._stage(
            f"protected {action_name} life cycle",
            cycle["p"],
            metrics.expected_cycles,
            (("bench:729", "harvest_reforge:life") if action_name == "Harvest" else ("bench:729", "scour", "exalted")),
            ("Full-prefix failure returns to Envy preparation; other failures repeat the legal protected cycle.",),
            attempt,
        ),
    ]
    policy = _fixed._policy(
        spec,
        loadout,
        policy_id,
        name,
        stages,
        metrics.mean_cost,
        selected["p90"],
        "sampled protected-cycle renewal p90; exact mean",
        terminal,
        ((_ENVY, "bench:729", "harvest_reforge:life") if action_name == "Harvest" else (_ENVY, "bench:729", "scour", "exalted")),
        ("Repeat Envy according to the selected preparation gate.", f"Use the selected legal protected {action_name} cycle and restart preparation only after a full-prefix failure."),
        ("The renewal law retains the paid reset required after a three-Exalt full-prefix failure.",),
    )
    estimate = selected["estimate"]
    policy.update({
        "cost_p90_interval": [estimate.interval_lower, estimate.interval_upper],
        "cost_sample_count": estimate.samples,
        "cost_seed": _SEED,
        "cost_confidence": estimate.confidence,
        "cost_error_bound": estimate.dkw_epsilon,
        "recovery": {
            "preparation_early_probability": selected["u"],
            "preparation_cycle_probability": selected["v"],
            "cycle_success_probability": cycle["p"],
            "full_prefix_failure_probability": cycle["b"],
            "expected_envy_applications": metrics.expected_preparations,
            "expected_prefix_cycles": metrics.expected_cycles,
            "early_completion_probability": metrics.early_completion_probability,
            "via_cycle_probability": metrics.via_cycle_probability,
            "first_hit_probabilities": list(cycle.get("first_hits", ())),
        },
        "full_prefix_failure_probability": cycle["b"],
    })
    return _attach_search(policy, selected, candidates, audit)


def _attach_protected_p90(row: dict[str, object], context: Mapping[str, object]) -> None:
    cycle = row["cycle"]
    estimate = estimate_protected_cycle_p90(
        row["u"], row["v"], context["envy_price"], cycle["p"], cycle["b"], cycle["failed_cost"], cycle["success_atoms"],
        base_cost=context["base_cost"],
        rng=np.random.default_rng(_SEED),
        samples=_SAMPLES,
        confidence=_CONFIDENCE,
    )
    row["p90"] = estimate.p90
    row["estimate"] = estimate


def _preparation_classes(stage_one, spec, labels, max_prefixes, min_elemental, early_stop):
    life = labels["IncreasedLife9"]
    chaos = labels["ChaosResist6"]
    elemental = {labels[mod_id] for mod_id in ("FireResist8", "ColdResist8", "LightningResist8")}
    early: dict[OutcomeClass, float] = {}
    prepared: dict[OutcomeClass, float] = {}
    for outcome, mass in stage_one.items():
        completed = _fixed._completes(spec, outcome)
        if early_stop and completed:
            early[outcome] = early.get(outcome, 0.0) + mass
            continue
        if (
            chaos in outcome.labels
            and sum(label in elemental for label in outcome.labels) >= min_elemental
            and outcome.suffixes == 3
            and outcome.prefixes <= max_prefixes
        ):
            prepared[outcome] = prepared.get(outcome, 0.0) + mass
    return early, prepared


def _protected_terminal(early, prepared, cycle, labels, metrics):
    result: dict[OutcomeClass, float] = defaultdict(float)
    u, v = _mass(early), _mass(prepared)
    if u:
        for outcome, mass in early.items():
            result[outcome] += metrics.early_completion_probability * mass / u
    if v and cycle["p"]:
        for suffix, suffix_mass in prepared.items():
            suffix_labels = tuple(label for label in suffix.labels if label != labels["IncreasedLife9"])
            for stage in cycle["success_by_stage"]:
                for prefix, prefix_mass in stage.items():
                    if labels["IncreasedLife9"] not in prefix.labels:
                        continue
                    outcome = OutcomeClass(tuple(sorted((*suffix_labels, *prefix.labels))), prefix.prefixes, 3)
                    result[outcome] += metrics.via_cycle_probability * suffix_mass / v * prefix_mass / cycle["p"]
    return dict(result)


def _protected_attempt_distribution(prepared, cycle, labels):
    result: dict[OutcomeClass, float] = defaultdict(float)
    total = _mass(prepared)
    if not total:
        return {OutcomeClass((), 0, 0): 1.0}
    for suffix, suffix_mass in prepared.items():
        suffix_labels = tuple(label for label in suffix.labels if label != labels["IncreasedLife9"])
        for prefix, prefix_mass in cycle["all_distribution"].items():
            outcome = OutcomeClass(tuple(sorted((*suffix_labels, *prefix.labels))), prefix.prefixes, 3)
            result[outcome] += suffix_mass / total * prefix_mass
    return dict(result)


def _optimized_bench_finish(spec, loadout, data, cache, requested_index):
    index = 131 if requested_index is None else requested_index
    policy_id = _fixed._bench_id(index)
    name = f"Protected life with bench finish {index}"
    context = _protected_context(spec, loadout, data, cache)
    if "reasons" in context:
        return _fixed._unavailable(policy_id, name, context["reasons"])
    candidates: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    # A bench prefix can only follow the documented one-Exalt branch with no
    # early Envy terminal.  The surviving prefix is then provably Life9.
    for max_prefixes in (1, 2):
        for min_elemental in (1, 2):
            early, prepared = _preparation_classes(
                context["stage_one"], spec, context["labels"], max_prefixes, min_elemental, False
            )
            cycle = _protected_exalt_cycle(context, 1, cache)
            parameters = {
                "item_level": getattr(spec, "item_level"),
                "max_prefixes": max_prefixes,
                "minimum_desired_elemental_suffixes": min_elemental,
                "preparation_early_stop": False,
                "cycle_kind": "protected_exalt",
                "max_exalts": 1,
                "bench_finish_id": index,
                **_bench_target_parameters(spec, loadout, data),
            }
            u, v = _mass(early), _mass(prepared)
            if u or not v or not cycle["p"]:
                audit.append({"parameters": parameters, "unavailable_reason": "bench finish requires a non-early known one-prefix Life9 branch"})
                continue
            metrics = protected_cycle_metrics(
                u, v, context["envy_price"], cycle["p"], cycle["b"], cycle["failed_cost"], cycle["success_atoms"], base_cost=context["base_cost"]
            )
            candidate = {"parameters": parameters, "mean": metrics.mean_cost, "u": u, "v": v, "early": early, "prepared": prepared, "cycle": cycle, "metrics": metrics}
            candidates.append(candidate)
            audit.append({"parameters": parameters, "expected_cost": metrics.mean_cost})
    if not candidates:
        blocked = _fixed._unavailable(policy_id, name, ["no legal known-one-prefix protected branch is reachable"])
        blocked["candidate_count"] = len(audit)
        blocked["parameter_audit"] = audit
        return blocked
    protected = _finalize_protected_candidate(
        spec, loadout, context, candidates, audit, "suffix-protected-life", name, "Exalt"
    )
    rows = protected["terminal_distribution"]
    if not all(row["prefixes"] == 1 for row in rows):
        raise AssertionError("bench candidate retained a non-one-prefix terminal state")
    result = _fixed._protected_bench_policy(spec, loadout, data, protected, index)
    if "reasons" not in result:
        result["parameters"] = dict(protected["parameters"])
        result["candidate_count"] = len(audit)
        result["parameter_audit"] = audit
        result["steps"] = [f"Selected parameters: {_parameter_text(result['parameters'])}.", *result["steps"]]
    return result


def _attach_search(
    policy: dict[str, object],
    selected: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
    audit: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    parameters = dict(selected["parameters"])
    policy["parameters"] = parameters
    policy["candidate_count"] = len(candidates) if audit is None else len(audit)
    policy["parameter_audit"] = list(audit) if audit is not None else [
        {"parameters": dict(row["parameters"]), "expected_cost": float(row["mean"]), **({"cost_p90": float(row["p90"])} if "p90" in row else {})}
        for row in candidates
    ]
    policy["steps"] = [f"Selected parameters: {_parameter_text(parameters)}.", *policy["steps"]]
    return policy


def _parameter_text(parameters: Mapping[str, object]) -> str:
    return ", ".join(f"{key}={value}" for key, value in parameters.items())


def _bench_target_parameters(spec: object, loadout: object, data: ActionData) -> dict[str, object]:
    requested = {
        mod_id
        for tiers in getattr(spec, "tier_ids", {}).values()
        for tier in tiers
        for mod_id in tier
    }
    eligible = [
        index for index in sorted(getattr(loadout, "allowed_bench", ()))
        if f"bench:{index}" in requested
    ]
    if eligible:
        return {"target_left_to_bench": eligible[0], "target_left_to_bench_reason": None}
    return {
        "target_left_to_bench": None,
        "target_left_to_bench_reason": "no permitted bench ID is in the requested tier mapping; lower bench life is not counted as Life9",
    }


def _normalized_distribution(distribution: Mapping[OutcomeClass, float]) -> dict[OutcomeClass, float]:
    total = _mass(distribution)
    if total <= 0:
        raise ValueError("cannot normalize an empty terminal distribution")
    return {outcome: mass / total for outcome, mass in distribution.items()}


def _with_augmentation(atoms, chance, augmentation_price):
    if not atoms:
        return ()
    result: dict[float, float] = defaultdict(float)
    for cost, mass in atoms:
        result[cost] += mass * (1 - chance)
        result[cost + augmentation_price] += mass * chance
    return tuple(sorted(result.items()))


def _mix_completion_distributions(spec, *pieces):
    result: dict[OutcomeClass, float] = defaultdict(float)
    for distribution, weight in pieces:
        if not weight:
            continue
        selected_mass = _fixed._selected_mass(spec, distribution)
        if selected_mass == 0:
            continue
        for outcome, mass in distribution.items():
            if _fixed._completes(spec, outcome):
                result[outcome] += weight * mass / selected_mass
    return dict(result)


def _merge_distributions(distributions):
    result: dict[OutcomeClass, float] = defaultdict(float)
    for distribution in distributions:
        for outcome, mass in distribution.items():
            result[outcome] += mass
    return dict(result)


def _mass(distribution: Mapping[object, float]) -> float:
    return math.fsum(distribution.values())


def _desired_labels(spec, labels):
    if getattr(spec, "value_table", None) is not None:
        desired = set()
        for mod_id, label in labels.items():
            group, _, raw_tier = label.rpartition(":")
            if raw_tier.isdigit() and getattr(spec, "value_table").get(group, {}).get(int(raw_tier), 0) > 0:
                desired.add(label)
        return frozenset(desired)
    desired = set()
    for criterion in (*getattr(spec, "required_mods"), *(choice for choices in getattr(spec, "any_of") for choice in choices)):
        for tier in getattr(spec, "tier_ids")[criterion.group][:criterion.max_tier]:
            desired.update(labels[mod_id] for mod_id in tier)
    return frozenset(desired)


def _desired_count(outcome: OutcomeClass, desired: frozenset[str]) -> int:
    return sum(label in desired for label in outcome.labels)


def _target_signature(spec: object) -> object:
    return (
        getattr(spec, "threshold", None),
        tuple(sorted(getattr(spec, "labels", {}).items())),
        repr(getattr(spec, "required_mods", ())),
        repr(getattr(spec, "any_of", ())),
        repr(getattr(spec, "value_table", None)),
    )


def _search_levels(spec: object, data: ActionData, item_level_range):
    current = getattr(spec, "item_level")
    if item_level_range is None:
        return [current], (current, current), 1
    lower, upper = parse_item_level_range(item_level_range)
    candidates = [lower, *sorted({row.get("level") for row in data.mods.values() if isinstance(row, Mapping) and isinstance(row.get("level"), int) and lower < row["level"] <= upper})]
    signatures: set[object] = set()
    levels: list[int] = []
    for level in candidates:
        signature = _pool_signature(spec, data, level)
        if signature in signatures:
            continue
        signatures.add(signature)
        levels.append(level)
    return levels, (lower, upper), len(levels)


def _pool_signature(spec: object, data: ActionData, level: int) -> tuple[tuple[object, ...], ...]:
    flags = getattr(spec, "flags")
    rows = []
    for rarity in ("normal", "magic", "rare"):
        item = ItemState(getattr(spec, "base"), level, rarity, **{name: bool(flags.get(name, False)) for name in ("corrupted", "influenced", "fractured", "synthesised", "mirrored", "split")})
        rows.append(tuple((entry.mod_id, entry.type, entry.group, entry.weight) for entry in resolve_pool(item, data.bases, data.mods)))
    return tuple(rows)


def _with_item_level(spec: object, level: int) -> object:
    if getattr(spec, "item_level") == level:
        return spec
    try:
        return replace(spec, item_level=level)
    except TypeError as error:
        raise ValueError("item-level search requires an immutable dataclass item specification") from error


def _merge_level_results(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if not results:
        raise ValueError("item-level search produced no pools")
    available: dict[str, list[dict[str, object]]] = defaultdict(list)
    unavailable: dict[str, list[dict[str, object]]] = defaultdict(list)
    for result in results:
        for row in result["ranked"]:
            available[row["id"]].append(dict(row))
        for row in result["unavailable"]:
            unavailable[row["id"]].append(dict(row))
    selected: list[dict[str, object]] = []
    for identifier, rows in available.items():
        incomplete = [
            row for row in unavailable.get(identifier, [])
            if isinstance(row.get("optimization_status"), Mapping)
            and row["optimization_status"].get("complete") is False
        ]
        if incomplete:
            blocked = dict(incomplete[0])
            blocked["reasons"] = [
                *blocked.get("reasons", []),
                "item-level search is incomplete for this template; no cross-level optimum is reported",
            ]
            unavailable[identifier] = [blocked]
            continue
        winner = min(rows, key=lambda row: (row["expected_cost"], row["cost_p90"], repr(row.get("parameters", {}))))
        audits = [entry for row in rows for entry in row.get("parameter_audit", [])]
        winner["candidate_count"] = sum(int(row.get("candidate_count", 1)) for row in rows)
        winner["parameter_audit"] = audits
        skipped = unavailable.get(identifier, [])
        if skipped:
            winner["unavailable_level_rows"] = skipped
        selected.append(winner)
    blocked = [rows[0] for identifier, rows in unavailable.items() if identifier not in available]
    selected.sort(key=lambda row: (row["expected_cost"], row["cost_p90"], row["id"]))
    blocked.sort(key=lambda row: row["id"])
    first = results[0]
    return {"ranked": selected, "unavailable": blocked, "assumptions": list(first["assumptions"]), "unit": first.get("unit")}
