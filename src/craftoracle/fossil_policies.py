"""Bounded ordinary Chaotic-resonator spam policy.

The policy mathematics are from ``docs/design/family-policies.md`` (2026-09-21).
Fossil outcome laws are supplied by the accepted adapter in :mod:`craftoracle.fossils`;
prices and the at-most-four caller availability domain are loadout inputs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, MutableMapping, Sequence
from itertools import combinations
import math
import time

from craftoracle.actions import ActionData
from craftoracle.distributions import OutcomeClass
from craftoracle.fossils import fossil_distribution, prepare_fossils
from craftoracle.item_model import ItemState
import craftoracle.policies as _fixed


_POLICY_ID = "fossil-spam"
_NAME = "Bounded Chaotic fossil spam with Alchemy early-stop"
_WORK_SECONDS = 45.0


def fossil_spam_policy(
    spec: object,
    loadout: object,
    data: ActionData,
    cache: MutableMapping[object, object],
    *,
    deadline: float | None = None,
) -> dict[str, object]:
    """Evaluate every permitted nonempty fossil subset and select its cheapest mean."""
    fossils = tuple(sorted(getattr(loadout, "allowed_fossils", ())))
    if not fossils:
        return _fixed._unavailable(_POLICY_ID, _NAME, ["loadout has no allowed fossils"])
    if len(fossils) > 4:
        return _fixed._unavailable(_POLICY_ID, _NAME, ["loadout fossil availability exceeds the four-fossil policy limit"])
    if deadline is None:
        deadline = time.monotonic() + _WORK_SECONDS

    labels = _fixed._labels(spec)
    normal, rare = _fixed._item(spec, "normal"), _fixed._item(spec, "rare")
    action_reasons = _action_reasons(loadout)
    if action_reasons:
        return _fixed._unavailable(_POLICY_ID, _NAME, action_reasons)
    try:
        alchemy_price = float(loadout.price("alchemy"))
    except ValueError as error:
        return _fixed._unavailable(_POLICY_ID, _NAME, [str(error)])
    try:
        alchemy = _fixed._action_distribution(cache, data, "alchemy", normal, labels)
    except (ValueError, NotImplementedError) as error:
        return _fixed._unavailable(_POLICY_ID, _NAME, [str(error)])
    alchemy_success = _fixed._success_probability(spec, alchemy)
    rows: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    all_subsets = tuple(_subsets(fossils))

    for index, selected in enumerate(all_subsets):
        parameters = _parameters(spec, selected)
        if time.monotonic() >= deadline:
            rows.extend({"parameters": _parameters(spec, skipped), "unavailable_reason": "work limit"} for skipped in all_subsets[index:])
            break
        reasons: list[str] = []
        recipe_price = 0.0
        for currency in (*(_fossil_currency(fossil) for fossil in selected), _resonator_currency(len(selected))):
            try:
                recipe_price += float(loadout.price(currency))
            except ValueError as error:
                reasons.append(str(error))
        if reasons:
            rows.append({"parameters": parameters, "unavailable_reason": "; ".join(sorted(set(reasons)))})
            continue
        distribution = None
        success = 0.0
        if alchemy_success < 1:
            try:
                distribution = _fossil_distribution(cache, rare, data, selected, labels)
            except (ValueError, NotImplementedError) as error:
                rows.append({"parameters": parameters, "unavailable_reason": str(error)})
                continue
            success = _fixed._success_probability(spec, distribution)
            if success == 0:
                rows.append({"parameters": parameters, "unavailable_reason": "target probability is zero"})
                continue
        setup = _fixed._base_cost(loadout) + alchemy_price
        mean = setup if alchemy_success == 1 else setup + (1 - alchemy_success) * recipe_price / success
        p90 = fossil_spam_p90(alchemy_success, success, setup, recipe_price)
        row = {
            "parameters": parameters,
            "probability": success,
            "recipe_price": recipe_price,
            "expected_cost": mean,
            "cost_p90": p90,
            "expected_resonators": 0.0 if alchemy_success == 1 else (1 - alchemy_success) / success,
            "distribution": distribution,
        }
        rows.append({key: value for key, value in row.items() if key != "distribution"})
        candidates.append(row)

    if len(rows) < len(all_subsets):
        raise AssertionError("every fossil subset must have an explicit audit row")
    if any(row.get("unavailable_reason") == "work limit" for row in rows):
        blocked = _fixed._unavailable(_POLICY_ID, _NAME, ["work limit"])
        blocked["candidate_count"] = len(all_subsets)
        blocked["parameter_audit"] = rows
        blocked["optimization_status"] = {"complete": False, "reason": "work limit"}
        return blocked
    if not candidates:
        blocked = _fixed._unavailable(_POLICY_ID, _NAME, ["no permitted fossil recipe can complete the target"])
        blocked["candidate_count"] = len(all_subsets)
        blocked["parameter_audit"] = rows
        return blocked

    selected = min(candidates, key=lambda row: (float(row["expected_cost"]), float(row["cost_p90"]), tuple(row["parameters"]["fossil_ids"])))
    selected_ids = tuple(selected["parameters"]["fossil_ids"])
    final = _completion_mixture(spec, alchemy, alchemy_success, selected["distribution"])
    stages = [
        _fixed._stage("Alchemy setup", alchemy_success, 1, ("alchemy",), ("Stop immediately on a completed Alchemy result.",), alchemy),
    ]
    if alchemy_success < 1:
        stages.append(
            _fixed._stage("full Chaotic fossil reroll", float(selected["probability"]), float(selected["expected_resonators"]), tuple([*(_fossil_currency(fossil) for fossil in selected_ids), _resonator_currency(len(selected_ids))]), ("Repeat this complete fossil/resonator recipe after every non-completion.",), selected["distribution"])
        )
    policy = _fixed._policy(
        spec, loadout, _POLICY_ID, _NAME,
        stages,
        float(selected["expected_cost"]), float(selected["cost_p90"]),
        "exact Alchemy/conditional-geometric full Chaotic fossil mixture", final,
        tuple(["alchemy", *(_fossil_currency(fossil) for fossil in selected_ids), _resonator_currency(len(selected_ids))]),
        ("Apply Alchemy once to the normal base.", "Stop on its target outcome; otherwise repeatedly use the selected full Chaotic resonator on the rare item."),
        ("D21 additive fossil mode is selected.", "Fossil and resonator prices are invented caller inputs.", "The search domain is every nonempty subset of the caller's at-most-four fossil allowlist.", "Chaotic rerolls have zero item-destruction risk in this model."),
    )
    policy.update({
        "parameters": selected["parameters"],
        "candidate_count": len(all_subsets),
        "parameter_audit": rows,
        "selected_recipe_price": selected["recipe_price"],
        "expected_resonators": selected["expected_resonators"],
        "fossil_mode": "additive",
        "source": "data/rules/fossils.json ordinary IDs; docs/mechanics/fossils_resonators.md D21",
        "confidence": "reimplemented-from-CoE",
    })
    policy["steps"] = [f"Selected parameters: {_parameter_text(selected['parameters'])}.", *policy["steps"]]
    return policy


def fossil_spam_p90(alchemy_success: float, fossil_success: float, setup: float, recipe_price: float) -> float:
    """Exact 90th percentile for the documented early-Alchemy geometric mixture."""
    if alchemy_success >= 0.9 or recipe_price == 0:
        return setup
    if fossil_success == 1:
        return setup + recipe_price
    tail = (1 - 0.9) / (1 - alchemy_success)
    draws = max(1, math.ceil(math.log(tail) / math.log1p(-fossil_success)))
    return setup + recipe_price * draws


def _subsets(fossils: Sequence[int]) -> tuple[tuple[int, ...], ...]:
    return tuple(part for count in range(1, len(fossils) + 1) for part in combinations(fossils, count))


def _parameters(spec: object, fossils: Sequence[int]) -> dict[str, object]:
    return {
        "item_level": getattr(spec, "item_level"), "fossil_ids": list(fossils), "socket_count": len(fossils),
        "fossil_mode": "additive", "alchemy_early_stop": True, "search_domain": "all nonempty subsets of allowed_fossils (maximum 4)",
    }


def _action_reasons(loadout: object) -> list[str]:
    if loadout.permits(("alchemy", "fossil")):
        return []
    return ["loadout does not permit required actions"]


def _fossil_currency(fossil: int) -> str:
    return f"fossil:{fossil}"


def _resonator_currency(socket_count: int) -> str:
    return f"resonator:{socket_count}"


def _fossil_distribution(cache, item: ItemState, data: ActionData, fossils: tuple[int, ...], labels: Mapping[str, str]):
    plan = prepare_fossils(item, data, fossils, labels, mode="additive", socket_count=len(fossils))
    key = (
        "fossil-spam-distribution", plan.item, plan.fossils, plan.mode, plan.draw_counts, plan.prefix_cap, plan.suffix_cap,
        tuple(sorted(plan.labels.items())), tuple((entry.mod_id, entry.type, entry.group, entry.weight) for entry in plan.entries),
        tuple(sorted(plan.effective_weights.items())),
    )
    if key not in cache:
        cache[key] = fossil_distribution(item, data, fossils, labels, mode="additive", socket_count=len(fossils))
    return cache[key]


def _completion_mixture(spec: object, alchemy, alchemy_success: float, fossils):
    result: dict[OutcomeClass, float] = defaultdict(float)
    for distribution, weight in ((alchemy, alchemy_success), (fossils, 1 - alchemy_success)):
        if weight == 0:
            continue
        success = _fixed._selected_mass(spec, distribution)
        for outcome, mass in distribution.items():
            if _fixed._completes(spec, outcome):
                result[outcome] += weight * mass / success
    return dict(result)


def _parameter_text(parameters: Mapping[str, object]) -> str:
    return ", ".join(f"{key}={value}" for key, value in parameters.items())
