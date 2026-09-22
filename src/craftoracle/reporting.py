"""Pure offline route-report construction and HTML rendering.

The planner remains the sole owner of probabilities. This module only labels
and accounts for fields it receives in an accepted plan document, then
renders two static, offline HTML pages from that data: `index.html` (the
player-facing report, read like in-game instructions) and `evidence.html`
(everything a player does not need at the workbench: pytest status, the
Craft of Exile cross-check, raw plan data, per-route audit detail).
"""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
import json
import math
import re
from numbers import Real
from pathlib import Path
from typing import Any


_CHAOS_LABEL = "Chaos Orb"


def build_report(plan: Mapping[str, Any], context: Mapping[str, Any], evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a JSON-safe report model without evaluating a crafting policy."""
    ranked = _list(plan, "ranked")
    unavailable = _list(plan, "unavailable")
    evidence_data = _evidence(evidence, context.get("generation", {}).get("commit"))
    routes = [_route(_mapping(route, "ranked route"), plan, context, index) for index, route in enumerate(ranked)]
    return {
        "schema_version": 1,
        "input": dict(_mapping(plan.get("input"), "input")),
        "prices": dict(_mapping(plan.get("prices"), "prices")),
        "assumptions": list(_list(plan, "assumptions")),
        "routes": routes,
        "unavailable": [dict(_mapping(row, "unavailable route")) for row in unavailable],
        "evidence": evidence_data,
        "context": _json_value(context),
    }


def material_accounting(route: Mapping[str, Any], plan: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    """Derive supported-route material rows from planner fields and caller prices."""
    prices = _mapping(plan.get("prices"), "prices")
    values = _mapping(prices.get("values", {}), "price values")
    base_cost = _number(prices.get("base_cost", 0), "base_cost")
    identifier = _string(route.get("id", ""), "route id")
    envy_name = _envy_display_name(context)
    rows: list[dict[str, Any]] = []
    complete = True
    reason: str | None = None

    def add(currency: str, count: float, price_key: str | None = None, action: str | None = None, uses: float | None = None) -> None:
        """Append one payment row. `action` is the crafting ACTION this payment is
        for (defaults to "Use <currency>", correct for every currency that is
        applied directly to the item); `uses` is how many times that action
        happens (defaults to `count`, correct unless one use of the action
        costs more than one unit of this currency, e.g. a bench recipe)."""
        nonlocal complete, reason
        if count == 0:
            return
        resolved_key = price_key or _price_key(currency, values)
        price = values.get(resolved_key) if resolved_key is not None else None
        resolved_action = action or f"Use {_currency_display_name(currency)}"
        resolved_uses = count if uses is None else uses
        if isinstance(price, bool) or not isinstance(price, Real) or not math.isfinite(price):
            complete = False
            reason = f"missing price for {currency}"
            rows.append({"currency": currency, "count": count, "unit_price": None, "spend": None, "action": resolved_action, "uses": resolved_uses})
            return
        rows.append({"currency": currency, "count": count, "unit_price": float(price), "spend": count * float(price), "action": resolved_action, "uses": resolved_uses})

    if identifier.startswith("essence"):
        stage = _find_stage(route, "essence") or _first_stage(route)
        parameters = _mapping(route.get("parameters", {}), "parameters")
        essence_id = parameters.get("forced_essence_id", parameters.get("essence_id"))
        if stage is None or not isinstance(essence_id, str):
            complete, reason = False, "missing essence stage or essence_id"
        else:
            names = _mapping(context.get("essence_names", {}), "essence_names")
            add(str(names.get(essence_id, essence_id)), _number(stage.get("expected_attempts"), "essence expected_attempts"), essence_id)
    elif identifier.startswith("alchemy-scour"):
        stage = _find_stage(route, "alchemy") or _first_stage(route)
        if stage is None:
            complete, reason = False, "missing Alchemy stage"
        else:
            attempts = _number(stage.get("expected_attempts"), "alchemy expected_attempts")
            add("Alchemy", attempts)
            add("Scour", max(0.0, attempts - 1))
    elif identifier.startswith("chaos"):
        stage = _find_stage(route, "chaos") or _first_stage(route)
        if stage is None:
            complete, reason = False, "missing Chaos stage"
        else:
            add("Alchemy", 1)
            add("Chaos", _number(stage.get("expected_attempts"), "chaos expected_attempts"))
    elif identifier.startswith("fossil"):
        expected = route.get("expected_resonators")
        params = _mapping(route.get("parameters", {}), "parameters")
        fossil_ids = params.get("fossil_ids")
        if expected is None or not isinstance(fossil_ids, list):
            complete, reason = False, "missing fossil recipe"
        else:
            count = _number(expected, "expected_resonators")
            add("Alchemy", 1)
            fossils = _mapping(context.get("fossil_names", {}), "fossil_names")
            resonator_action = "Use a Chaotic Resonator"
            # One resonator use consumes one of each selected fossil plus the resonator itself: that
            # is ONE batch of `count` uses billed in several currencies, so only the first row counts
            # towards the action's total uses (see _aggregate_actions).
            for position, fossil_id in enumerate(fossil_ids):
                add(str(fossils.get(str(fossil_id), fossils.get(fossil_id, f"fossil {fossil_id}"))), count, f"fossil:{fossil_id}", action=resonator_action, uses=(count if position == 0 else 0.0))
            add(f"{len(fossil_ids)}-socket Chaotic Resonator", count, f"resonator:{len(fossil_ids)}", action=resonator_action, uses=(count if not fossil_ids else 0.0))
    elif identifier.startswith("fracture"):
        counts = _mapping(route.get("expected_action_counts", {}), "expected_action_counts")
        if not counts:
            complete, reason = False, "missing expected_action_counts"
        else:
            envy_id = context.get("envy_id")
            for count_key, currency in (("bases", "Base"), ("alchemy", "Alchemy"), ("scour", "Scour"), ("fracturing", "Fracturing Orb"), ("envy", envy_name)):
                if count_key in counts:
                    count = _number(counts[count_key], count_key)
                    if count_key == "bases":
                        rows.append({"currency": "Base", "count": count, "unit_price": base_cost, "spend": count * base_cost, "action": "Buy a Base", "uses": count})
                    else:
                        add(currency, count, envy_id if count_key == "envy" and isinstance(envy_id, str) else None)
    elif identifier.startswith("suffix-protected"):
        recovery = _mapping(route.get("recovery", {}), "recovery")
        parameters = _mapping(route.get("parameters", {}), "parameters")
        envy, cycles = recovery.get("expected_envy_applications"), recovery.get("expected_prefix_cycles")
        if envy is None or cycles is None:
            complete, reason = False, "missing protected recovery accounting"
        else:
            envy_count, cycle_count = _number(envy, "expected_envy_applications"), _number(cycles, "expected_prefix_cycles")
            envy_id = context.get("envy_id")
            add(envy_name, envy_count, envy_id if isinstance(envy_id, str) else None)
            _add_bench_recipe(rows, values, context, 729, cycle_count, add)
            if "harvest" in identifier:
                add("Harvest reforge Life", cycle_count)
            else:
                add("Scour", cycle_count)
                probabilities = recovery.get("first_hit_probabilities", [])
                max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
                if not isinstance(probabilities, list):
                    complete, reason = False, "missing protected first_hit_probabilities"
                else:
                    survival = 0.0
                    expected_exalts = 0.0
                    for probability in probabilities[:max_exalts]:
                        expected_exalts += 1 - survival
                        survival += _number(probability, "first_hit probability")
                    add("Exalt", cycle_count * expected_exalts)
                if parameters.get("bench_finish_id") is not None:
                    _add_bench_recipe(rows, values, context, _integer(parameters["bench_finish_id"], "bench_finish_id"), 1, add)
    elif identifier.startswith("magic"):
        attempts = route.get("expected_attempts")
        if attempts is None:
            stage = _first_stage(route)
            attempts = stage.get("expected_attempts") if stage else None
        rules = _mapping(context.get("action_rules", {}), "action_rules")
        weights = _mapping(rules.get("magic_count_weights", {}), "magic_count_weights")
        if attempts is None or not weights:
            complete, reason = False, "missing Magic attempt count or magic_count_weights"
        else:
            total = sum(_number(value, "magic count weight") for value in weights.values())
            one = _number(weights.get("1", 0), "one-mod magic weight") / total
            count = _number(attempts, "magic expected_attempts")
            add("Transmute", count)
            add("Alteration", count)
            add("Augmentation", count * one)
            add("Scour", max(0.0, count - 1))
            for stage in _list(route, "stages"):
                name = str(_mapping(stage, "stage").get("name", "")).lower()
                if "regal" in name:
                    add("Regal", _number(_mapping(stage, "stage").get("expected_attempts"), "regal expected_attempts"))
                if "exalt" in name:
                    add("Exalt", _number(_mapping(stage, "stage").get("expected_attempts"), "exalt expected_attempts"))
    else:
        complete, reason = False, "missing accounting translation for this route"

    if base_cost and not identifier.startswith("fracture"):
        rows.insert(0, {"currency": "Base", "count": 1.0, "unit_price": base_cost, "spend": base_cost, "action": "Buy a Base", "uses": 1.0})
    if complete and any(row["spend"] is None for row in rows):
        complete, reason = False, reason or "missing price or recipe"
    total = math.fsum(float(row["spend"]) for row in rows if row["spend"] is not None)
    expected = route.get("expected_cost")
    matches = complete and expected is not None and math.isclose(total, _number(expected, "expected_cost"), rel_tol=1e-9, abs_tol=1e-7)
    if complete and not matches:
        reason = f"accounting total {total:g} differs from planner expected_cost {_number(expected, 'expected_cost'):g}"
    return {"rows": rows, "total": total, "complete": complete and matches, "reason": reason}


def render_report(report: Mapping[str, Any]) -> str:
    """Fill the standalone player report template with server-rendered HTML."""
    title = escape(str(_mapping(report.get("input"), "input").get("name", "Crafting route report")))
    body = _player_body_html(report)
    return _fill_template(title, body)


def render_evidence(report: Mapping[str, Any]) -> str:
    """Fill the standalone evidence template: everything the player page dropped."""
    name = str(_mapping(report.get("input"), "input").get("name", "Crafting route report"))
    title = escape(f"{name} — evidence")
    body = _evidence_body_html(report)
    return _fill_template(title, body)


def _fill_template(title: str, body: str) -> str:
    template = (Path(__file__).with_name("report_assets") / "template.html").read_text(encoding="utf-8")
    if "{{REPORT_TITLE}}" not in template or "{{REPORT_BODY}}" not in template:
        raise ValueError("report template is missing required placeholders")
    return template.replace("{{REPORT_TITLE}}", title).replace("{{REPORT_BODY}}", body)


def _route(route: Mapping[str, Any], plan: Mapping[str, Any], context: Mapping[str, Any], index: int) -> dict[str, Any]:
    stages = []
    identifier = _string(route.get("id", ""), "route id")
    for stage in _list(route, "stages"):
        row = _mapping(stage, "stage")
        name = str(row.get("name", "stage"))
        meaning = "Chance of reaching this step" if identifier.startswith("magic") else _stage_meaning(identifier, name)
        stages.append({"name": name, "probability": row.get("probability"), "expected_attempts": row.get("expected_attempts"), "meaning": meaning})
    threshold = route.get("stopping_threshold", _mapping(plan.get("input"), "input").get("utility_threshold"))
    recovery = dict(_mapping(route.get("recovery", {}), "recovery"))
    metadata = {key: route.get(key) for key in ("cost_p90_interval", "cost_sample_count", "cost_seed", "cost_error_bound", "cost_confidence", "irreversible_failure_risk", "wrong_fracture_risk_per_trial", "expected_discarded_bases", "irreversible_item_destruction_risk", "expected_attempts") if key in route}
    metadata.update(recovery)
    if identifier.startswith("magic"):
        attempts = _first_stage(route)
        if attempts is not None and _number(attempts.get("expected_attempts"), "magic expected_attempts") > 0:
            metadata["success_probability"] = 1 / _number(attempts.get("expected_attempts"), "magic expected_attempts")
    title = _route_title(identifier, route, context)
    accounting = material_accounting(route, plan, context)
    base_name = str(_mapping(plan.get("input"), "input").get("base", "") or "")
    return {"key": f"{identifier}-{threshold if threshold is not None else 'base'}-{index}", "id": identifier, "name": str(route.get("name", identifier)), "title": title, "search_text": f"{title} {identifier} {route.get('name', '')}", "expected_cost": route.get("expected_cost"), "cost_p90": route.get("cost_p90"), "cost_label": "approximate" if route.get("cost_p90_interval") else "exact", "expected_utility": route.get("expected_utility"), "frontier": bool(route.get("frontier", False)), "stopping_threshold": threshold, "stages": stages, "parameters": dict(_mapping(route.get("parameters", {}), "parameters")), "decisions": list(route.get("decision_points", [])), "metadata": metadata, "source": {"assumptions": list(route.get("assumptions", [])), "design": ["docs/design/route-report.md", "docs/design/parameter-search.md", "docs/design/family-policies.md"], "generation": context.get("generation", {})}, "audit": {"parameter_audit": list(route.get("parameter_audit", [])), "terminal_distribution": list(route.get("terminal_distribution", []))}, "instructions": _instructions(identifier, route, context, base_name), "accounting": accounting, "flow": _flow(identifier, route, context, accounting["rows"])}


def _route_title(identifier: str, route: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    parameters = _mapping(route.get("parameters", {}), "parameters")
    envy_name = _envy_display_name(context)
    if identifier == "suffix-protected-life-bench-131":
        return f"{envy_name} → Suffixes Cannot Be Changed → Exalted Orb → Bench"
    if identifier == "suffix-protected-life":
        return f"{envy_name} → Suffixes Cannot Be Changed → Exalted Orb"
    if identifier == "suffix-protected-harvest-life":
        return f"{envy_name} → Suffixes Cannot Be Changed → Harvest Reforge: Life"
    if identifier == "fracture-life-envy":
        return f"Fractured Life T1 → {envy_name}"
    if identifier.startswith("fossil"):
        names = _mapping(context.get("fossil_names", {}), "fossil_names")
        selected = ", ".join(str(names.get(str(value), names.get(value, f"fossil {value}"))) for value in parameters.get("fossil_ids", []))
        return "Fossil: " + selected
    if identifier.startswith("alchemy-scour"):
        return "Orb of Alchemy → Orb of Scouring"
    if identifier.startswith("chaos"):
        return "Orb of Alchemy → Chaos Orb"
    if identifier.startswith("magic"):
        return "Orb of Alteration → Regal Orb → Exalted Orb"
    if identifier.startswith("essence"):
        essence_id = parameters.get("forced_essence_id", parameters.get("essence_id"))
        return str(_mapping(context.get("essence_names", {}), "essence_names").get(essence_id, essence_id or route.get("name", identifier)))
    return str(route.get("name", identifier))


def _step(text: str, detail: str | None = None) -> dict[str, str | None]:
    """One "step by step" line: one action, imperative, in game verbs. `detail`
    is a short second line for a retry rule too long for the main sentence."""
    return {"text": text, "detail": detail}


def _instructions(identifier: str, route: Mapping[str, Any], context: Mapping[str, Any], base_name: str) -> list[dict[str, str | None]]:
    parameters = _mapping(route.get("parameters", {}), "parameters")
    life = _life_target_text(context)
    envy_name = _envy_display_name(context)
    base = f"a normal {base_name}" if base_name else "a normal base"
    if identifier.startswith("essence"):
        essence_id = parameters.get("forced_essence_id", parameters.get("essence_id"))
        essence = _mapping(context.get("essence_names", {}), "essence_names").get(essence_id, essence_id or "Essence")
        return [_step(f"Use {essence} on {base}; keep the item once it has the target modifiers, otherwise use {essence} again.")]
    if identifier.startswith("alchemy-scour"):
        return [_step("Use Orb of Alchemy on " + base + "; keep the item once the target is met, otherwise use Orb of Scouring and use Orb of Alchemy again.")]
    if identifier.startswith("chaos"):
        early = bool(parameters.get("alchemy_early_stop", True))
        return [
            _step(f"Use Orb of Alchemy on {base}" + (", checking the target now." if early else "; the result is not checked here.")),
            _step("Use Chaos Orb repeatedly (never Orb of Scouring in between) and keep the item once the target is met."),
        ]
    if identifier.startswith("fossil"):
        fossils = _mapping(context.get("fossil_names", {}), "fossil_names")
        selected = ", ".join(str(fossils.get(str(value), f"fossil {value}")) for value in parameters.get("fossil_ids", []))
        sockets = parameters.get("socket_count", "?")
        return [
            _step(f"Use Orb of Alchemy on {base} and check the target immediately."),
            _step(f"Fill a {sockets}-socket Chaotic Resonator with {selected} and use it on the item; repeat until the target is met."),
        ]
    if identifier.startswith("fracture"):
        early = bool(parameters.get("alchemy_early_stop", False))
        return [
            _step(
                f"Use Orb of Alchemy on {base}, then Orb of Scouring and Orb of Alchemy again, until it has exactly four explicit modifiers including {life}.",
                None if early else "The early-finish check on a complete Alchemy roll is off for this route; it always continues to four modifiers.",
            ),
            _step(f"Use Fracturing Orb once it has exactly four explicit modifiers including {life}."),
            _step("Set a wrongly fractured base aside (no refund in this cost model) and buy a new one; start over from Orb of Alchemy."),
            _step(f"Use {envy_name} repeatedly once {life} is fractured, and keep the item once the target is met."),
        ]
    if identifier.startswith("suffix-protected-harvest"):
        prep = _protected_preparation_step(parameters, envy_name, base)
        return [
            prep,
            _step(
                f"Use Suffixes Cannot Be Changed, then Harvest Reforge: Life; keep the item once it has {life}.",
                f"On a miss: repeat this step while a prefix is free, or go back to step 1 once three prefixes are used (no Orb of Scouring here).",
            ),
        ]
    if identifier.startswith("suffix-protected"):
        max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
        prep = _protected_preparation_step(parameters, envy_name, base)
        steps = [prep, _step("Use Suffixes Cannot Be Changed, then Orb of Scouring.")]
        if max_exalts:
            steps.append(_step(
                f"Use up to {max_exalts} Exalted Orbs and keep the item once it has {life}.",
                f"Only once all {max_exalts} have failed: repeat step 2 while a prefix is free, or go back to step 1 once three prefixes are used.",
            ))
        if parameters.get("bench_finish_id") is not None:
            bench = _mapping(context.get("bench_names", {}), "bench_names").get(str(parameters["bench_finish_id"]), f"bench {parameters['bench_finish_id']}")
            steps.append(_step(f"Finish with Crafting Bench: {bench}; this does not replace the required {life}."))
        return steps
    if identifier.startswith("magic"):
        max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
        early = bool(parameters.get("early_stop", False))
        magic_gate, regal_gate = parameters.get("magic_min_desired"), parameters.get("regal_min_desired")
        steps = [
            _step(f"Use Orb of Transmutation on {base}."),
            _step("Use Orb of Alteration; on a one-modifier result also use Orb of Augmentation."),
            _step(
                f"Keep going only with at least {magic_gate} desired modifiers"
                + (", checked now" if early else " (checked only at the last configured step)")
                + "; otherwise use Orb of Scouring and Orb of Transmutation and start over.",
            ),
        ]
        if max_exalts and early:
            steps.append(_step(
                "Use Regal Orb; keep the item now if the target is met.",
                f"Otherwise continue only with at least {regal_gate} desired modifiers; below that, use Orb of Scouring and Orb of Transmutation and start over.",
            ))
        elif max_exalts:
            steps.append(_step(
                f"Use Regal Orb and continue only with at least {regal_gate} desired modifiers.",
                "Below that, use Orb of Scouring and Orb of Transmutation and start over.",
            ))
        else:
            steps.append(_step(
                "Use Regal Orb; keep the item once the target is met.",
                f"Otherwise (fewer than {regal_gate} desired modifiers) use Orb of Scouring and Orb of Transmutation and start over.",
            ))
        if max_exalts:
            steps.append(_step(
                f"Use up to {max_exalts} Exalted Orbs and keep the item once the target is met.",
                ("On a miss after every use, use Orb of Scouring and Orb of Transmutation and start over." if early else "On a miss after the last use, use Orb of Scouring and Orb of Transmutation and start over."),
            ))
        return steps
    return [_step(str(step)) for step in route.get("steps", [])] or [_step("No instructions are available for this route.")]


def _protected_preparation_step(parameters: Mapping[str, Any], envy_name: str, base: str) -> dict[str, str | None]:
    early = bool(parameters.get("preparation_early_stop", False))
    suffixes = parameters.get("minimum_desired_elemental_suffixes", "?")
    prefixes = parameters.get("max_prefixes", "?")
    text = (
        f"Use {envy_name} on {base}; keep the item when it has exactly 3 suffixes, at least {suffixes} elemental "
        f"resistance suffixes, and at most {prefixes} prefixes, otherwise use {envy_name} again."
    )
    detail = "An item that is already complete finishes the route immediately, even during this step." if early else None
    return _step(text, detail)


def _life_target_text(context: Mapping[str, Any]) -> str:
    target = _mapping(context.get("target", {}), "target")
    labels = _mapping(target.get("labels", {}), "target labels")
    value = labels.get("IncreasedLife:1")
    return f"Life T1 ({value})" if isinstance(value, str) else "Life T1"


def _envy_display_name(context: Mapping[str, Any]) -> str:
    envy_id = context.get("envy_id")
    if not isinstance(envy_id, str):
        return "Envy"
    names = _mapping(context.get("essence_names", {}), "essence_names")
    return str(names.get(envy_id, "Envy"))


def _stage_meaning(identifier: str, name: str) -> str:
    lower = name.lower()
    if "preparation" in lower:
        return "Chance of meeting the preparation gate, or finishing early"
    if "protected" in lower:
        return "Chance of the target in one protected cycle"
    if identifier.startswith(("essence", "alchemy", "chaos", "fossil")):
        return "Chance of the target per use"
    return "Step chance from the plan"


def _evidence(evidence: Mapping[str, Any] | None, report_commit: Any) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        return {"status": "unavailable", "message": "Checks unavailable: proof.json was not provided."}
    pytest = _mapping(evidence.get("pytest", {}), "evidence pytest")
    coe = _mapping(evidence.get("coe", {}), "evidence coe")
    status = "passed" if pytest.get("status") == "passed" and coe.get("status") == "passed" else "unavailable" if "unavailable" in {pytest.get("status"), coe.get("status")} else "failed"
    mismatch = isinstance(report_commit, str) and evidence.get("git_commit") != report_commit
    def link(path: Any) -> Any:
        return f"evidence/{path}" if isinstance(path, str) else path
    commands = [{**dict(command), "stdout_file": link(command.get("stdout_file")), "stderr_file": link(command.get("stderr_file"))} if isinstance(command, Mapping) else command for command in evidence.get("commands", [])]
    return {"status": status, "message": evidence.get("message"), "pytest": dict(pytest), "coe": dict(coe), "commands": commands, "artifacts": {key: link(value) for key, value in _mapping(evidence.get("artifacts", {}), "artifacts").items()}, "proof_link": "evidence/proof.json", "git_commit": evidence.get("git_commit"), "generated_at": evidence.get("generated_at"), "working_tree_dirty": evidence.get("working_tree_dirty"), "revision_message": "Checks are from a different revision" if mismatch else None}


def _find_stage(route: Mapping[str, Any], needle: str) -> Mapping[str, Any] | None:
    return next((row for raw in _list(route, "stages") if needle in str((row := _mapping(raw, "stage")).get("name", "")).lower()), None)


def _first_stage(route: Mapping[str, Any]) -> Mapping[str, Any] | None:
    stages = _list(route, "stages")
    return _mapping(stages[0], "stage") if stages else None


# --------------------------------------------------------------------------
# Crafting-flow model: one box per currency actually spent (from the same
# accounting rows the cost table uses), plus the conditions already computed
# for `_instructions`. No new engine numbers; this only restructures them.
# --------------------------------------------------------------------------


def _aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order: list[str] = []
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        currency = str(row["currency"])
        if currency not in merged:
            merged[currency] = {"currency": currency, "count": 0.0, "unit_price": row.get("unit_price"), "spend": 0.0}
            order.append(currency)
        entry = merged[currency]
        entry["count"] += float(row.get("count") or 0.0)
        if entry["unit_price"] is None:
            entry["unit_price"] = row.get("unit_price")
        if row.get("spend") is None or entry["spend"] is None:
            entry["spend"] = None
        else:
            entry["spend"] = float(entry["spend"]) + float(row["spend"])
    return [merged[currency] for currency in order]


def _aggregate_actions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group payment rows by the crafting ACTION they pay for (in first-seen
    order), so a flow step is "Crafting Bench: Suffixes Cannot Be Changed"
    paid in Divine Orbs, never a step titled "Divine Orb". Every row already
    carries `action`/`uses` (see `material_accounting`'s `add`); this only
    regroups them, it adds no new engine numbers.

    `uses` is summed across rows of the same action: most actions have one
    row (sum is a no-op), but e.g. three per-attempt "exalt 1/2/3" stages are
    three genuinely separate batches of real Exalted Orb uses and must add up
    (`_add_bench_recipe` and the fossil+resonator bundle instead mark every
    row but the first `uses=0`, since those rows are one batch billed in more
    than one currency, not several batches). Payments are also merged by
    currency, so three same-currency rows show one payment line, not three.
    """
    order: list[str] = []
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        action = str(row.get("action") or f"Use {_currency_display_name(str(row['currency']))}")
        if action not in merged:
            merged[action] = {"action": action, "uses": 0.0, "cost": 0.0, "payment_order": [], "payments": {}}
            order.append(action)
        entry = merged[action]
        entry["uses"] += float(row.get("uses", row.get("count")) or 0.0)
        spend = row.get("spend")
        entry["cost"] = None if spend is None or entry["cost"] is None else entry["cost"] + float(spend)
        currency = str(row["currency"])
        if currency not in entry["payments"]:
            entry["payments"][currency] = {"currency": currency, "count": 0.0, "spend": 0.0}
            entry["payment_order"].append(currency)
        payment = entry["payments"][currency]
        payment["count"] += float(row.get("count") or 0.0)
        if row.get("spend") is None or payment["spend"] is None:
            payment["spend"] = None
        else:
            payment["spend"] = float(payment["spend"]) + float(row["spend"])
    return [
        {"action": merged[action]["action"], "uses": merged[action]["uses"], "cost": merged[action]["cost"],
         "payments": [merged[action]["payments"][currency] for currency in merged[action]["payment_order"]]}
        for action in order
    ]


def _flow(identifier: str, route: Mapping[str, Any], context: Mapping[str, Any], accounting_rows: list[dict[str, Any]]) -> dict[str, Any]:
    parameters = _mapping(route.get("parameters", {}), "parameters")
    stages = _list(route, "stages")
    life = _life_target_text(context)
    envy_name = _envy_display_name(context)
    actions = _aggregate_actions(accounting_rows)
    base_action = next((entry for entry in actions if entry["action"] == "Buy a Base"), None)
    action_rows = [entry for entry in actions if entry["action"] != "Buy a Base"]

    def mk(entry: dict[str, Any]) -> dict[str, Any]:
        return {"action": entry["action"], "uses": entry["uses"], "cost": entry["cost"], "payments": entry["payments"], "chance": None, "transitions": []}

    steps = [mk(entry) for entry in action_rows]

    if identifier.startswith("essence") and len(steps) >= 1:
        steps[0]["chance"] = stages[0]["probability"] if stages else None
        steps[0]["transitions"] = [
            {"kind": "repeat", "label": "Target not on the item"},
            {"kind": "success", "label": "Target complete"},
        ]
    elif identifier.startswith("alchemy-scour") and len(steps) >= 2:
        steps[0]["chance"] = stages[0]["probability"] if stages else None
        steps[0]["transitions"] = [
            {"kind": "success", "label": "Target complete"},
            {"kind": "forward", "to": 1, "label": "Target not complete"},
        ]
        steps[1]["transitions"] = [{"kind": "reset", "to": 0, "label": "Use Orb of Alchemy again"}]
    elif identifier.startswith("chaos") and len(steps) >= 2:
        early = bool(parameters.get("alchemy_early_stop", True))
        steps[0]["transitions"] = [{"kind": "forward", "to": 1, "label": "Check the target now" if early else "Result not checked here"}]
        steps[1]["chance"] = stages[-1]["probability"] if stages else None
        steps[1]["transitions"] = [
            {"kind": "repeat", "label": "Target not complete (no Scour in between)"},
            {"kind": "success", "label": "Target complete"},
        ]
    elif identifier.startswith("fossil") and len(steps) >= 2:
        steps[0]["transitions"] = [{"kind": "forward", "to": 1, "label": "Target not complete"}]
        steps[1]["chance"] = stages[-1]["probability"] if stages else None
        steps[1]["transitions"] = [
            {"kind": "repeat", "label": "Target not complete"},
            {"kind": "success", "label": "Target complete"},
        ]
    elif identifier.startswith("fracture") and len(steps) >= 4:
        early = bool(parameters.get("alchemy_early_stop", False))
        alchemy, scour, fracturing, envy = steps[0], steps[1], steps[2], steps[3]
        alchemy["transitions"] = [
            {"kind": "forward", "to": 2, "label": f"Exactly four explicit modifiers, including {life}"},
            {"kind": "forward", "to": 1, "label": f"Not yet {life} with exactly four explicit modifiers" + ("" if early else " (early check is off)")},
        ]
        scour["transitions"] = [{"kind": "reset", "to": 0, "label": "Use Orb of Alchemy again"}]
        fracturing["transitions"] = [
            {"kind": "forward", "to": 3, "label": f"Fractured {life}"},
            {"kind": "restart", "label": "Fractured a different modifier: set the base aside and buy a new one"},
        ]
        envy["transitions"] = [
            {"kind": "repeat", "label": "Target not complete"},
            {"kind": "success", "label": "Target complete"},
        ]
    elif identifier.startswith("suffix-protected") and len(steps) >= 3:
        prep_early = bool(parameters.get("preparation_early_stop", False))
        suffixes = parameters.get("minimum_desired_elemental_suffixes", "?")
        prefixes = parameters.get("max_prefixes", "?")
        gate_label = f"Exactly 3 suffixes, at least {suffixes} elemental resistance suffixes, at most {prefixes} prefixes"
        envy_transitions = [
            {"kind": "repeat", "label": "Fewer suffixes, too few elemental resistances, or too many prefixes"},
            {"kind": "forward", "to": 1, "label": gate_label},
        ]
        if prep_early:
            envy_transitions.append({"kind": "success", "label": "Already complete during preparation"})
        steps[0]["transitions"] = envy_transitions
        steps[1]["transitions"] = [{"kind": "forward", "to": 2, "label": None}]
        finisher = steps[2]
        if identifier.startswith("suffix-protected-harvest"):
            finisher["transitions"] = [
                {"kind": "success", "label": life},
                {"kind": "reset", "to": 1, "label": "No hit, free prefix available"},
                {"kind": "reset", "to": 0, "label": "No hit, three prefixes used"},
            ]
        elif len(steps) >= 4:
            max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
            exalt = steps[3]
            finisher["transitions"] = [{"kind": "forward", "to": 3, "label": None}]
            exalt_transitions = [{"kind": "repeat", "label": f"No {life} yet, tries remain (up to {max_exalts})"}]
            if len(steps) >= 5:
                exalt_transitions.append({"kind": "forward", "to": 4, "label": f"{life} hit"})
                steps[4]["transitions"] = [{"kind": "success", "label": "Bench finish applied"}]
            else:
                exalt_transitions.append({"kind": "success", "label": f"{life} hit"})
            exalt_transitions.append({"kind": "reset", "to": 1, "label": f"All {max_exalts} Exalted Orbs failed, free prefix available"})
            exalt_transitions.append({"kind": "reset", "to": 0, "label": f"All {max_exalts} Exalted Orbs failed, three prefixes used"})
            exalt["transitions"] = exalt_transitions
    elif identifier.startswith("magic") and len(steps) >= 5:
        magic_gate = parameters.get("magic_min_desired")
        regal_gate = parameters.get("regal_min_desired")
        early = bool(parameters.get("early_stop", False))
        max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
        transmute, alteration, augmentation, scour, regal = steps[0], steps[1], steps[2], steps[3], steps[4]
        transmute["transitions"] = [{"kind": "forward", "to": 1, "label": None}]
        alteration["transitions"] = [{"kind": "forward", "to": 2, "label": "One modifier (also use Augmentation)"}]
        check_label = f"At least {magic_gate} desired modifiers" if magic_gate is not None else "Enough desired modifiers"
        miss_label = (f"Fewer than {magic_gate} desired modifiers" if magic_gate is not None else "Not enough desired modifiers") + (" (checked now)" if early else " (checked only at the last configured step)")
        augmentation["transitions"] = [
            {"kind": "forward", "to": 4, "label": check_label},
            {"kind": "forward", "to": 3, "label": miss_label},
        ]
        scour["transitions"] = [{"kind": "reset", "to": 0, "label": "Use Orb of Transmutation again"}]
        if max_exalts and len(steps) >= 6:
            exalted = steps[5]
            regal["transitions"] = [
                {"kind": "forward", "to": 5, "label": f"At least {regal_gate} desired modifiers"},
                {"kind": "forward", "to": 3, "label": f"Fewer than {regal_gate} desired modifiers"},
            ]
            exalted["transitions"] = [
                {"kind": "repeat", "label": f"Target not complete, tries remain (up to {max_exalts})"},
                {"kind": "success", "label": "Target complete"},
                {"kind": "reset", "to": 3, "label": f"All {max_exalts} Exalted Orbs failed"},
            ]
        else:
            regal["transitions"] = [
                {"kind": "success", "label": "Target complete"},
                {"kind": "forward", "to": 3, "label": f"Fewer than {regal_gate} desired modifiers"},
            ]
    return {"steps": steps, "restart": {"uses": base_action["uses"], "cost": base_action["cost"]} if base_action else None}


# --------------------------------------------------------------------------
# Display formatting (dot-decimal, English; separate from the strict
# validators above, which raise on bad input instead of degrading).
# --------------------------------------------------------------------------


def _display_number(value: Any) -> str:
    if value is None or isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        return "-"
    rounded = round(float(value), 1)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:,.1f}"


def _display_int(value: Any) -> str:
    if value is None or isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        return "-"
    return f"{round(float(value)):,}"


def _display_percent(value: Any) -> str:
    if value is None or isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        return "-"
    if 0 < value < 0.001:
        return f"&lt;0.1% (about 1 in {_display_int(round(1 / value))})"
    return f"{_display_number(value * 100)}%"


_CURRENCY_DISPLAY = {
    "Alchemy": "Orb of Alchemy",
    "Scour": "Orb of Scouring",
    "Chaos": "Chaos Orb",
    "chaos": "Chaos Orb",
    "Transmute": "Orb of Transmutation",
    "Alteration": "Orb of Alteration",
    "Augmentation": "Orb of Augmentation",
    "Regal": "Regal Orb",
    "Exalt": "Exalted Orb",
    "Divine": "Divine Orb",
    "divine": "Divine Orb",
    "Harvest reforge Life": "Harvest Reforge: Life",
}


def _currency_display_name(name: str) -> str:
    """Map an internal accounting currency label to the game's own wording.

    Accounting rows carry short internal labels (some inherited straight from
    price-file keys, e.g. lowercase "divine" from a bench recipe); this is a
    display-only lookup and never changes a row's price-resolution key.
    """
    return _CURRENCY_DISPLAY.get(name, name)


def _currency_family(name: str) -> str:
    """Classify a currency OR action label into a chip colour family."""
    lower = name.lower()
    if "crafting bench" in lower:
        return "bench"
    if "essence" in lower:
        return "essence"
    if "resonator" in lower:
        return "resonator"
    if "fossil" in lower:
        return "fossil"
    if "harvest" in lower:
        return "harvest"
    if "fracturing" in lower:
        return "fracturing"
    if "base" in lower:
        return "base"
    return "orb"


def _safe_local_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if re.match(r"^[a-z][a-z0-9+.-]*:", value, re.IGNORECASE):
        return None
    if value.startswith("/") or value.startswith("\\"):
        return None
    parts = re.split(r"[\\/]", value)
    if any(part in ("", ".", "..") for part in parts):
        return None
    return value


def _local_link(value: Any, label: str | None = None) -> str:
    path = _safe_local_path(value)
    if path is None:
        return '<span class="muted">no local file</span>'
    return f'<a href="{escape(path)}">{escape(label or path)}</a>'


# --------------------------------------------------------------------------
# Player page (index.html)
# --------------------------------------------------------------------------


def _player_body_html(report: Mapping[str, Any]) -> str:
    routes = report.get("routes", [])
    if not isinstance(routes, list) or not routes:
        return '<p class="bad">No routes are available for this target.</p>'
    return _target_card_html(report) + _routes_section_html(routes, report) + _footer_html(report)


def _mod_line_html(item: Mapping[str, Any]) -> str:
    kind = escape(str(item.get("type", "Modifier")))
    tier = _display_int(item.get("tier", item.get("max_tier")))
    family = escape(str(item.get("family", "")))
    text = escape(str(item.get("text", "")))
    return f'<div class="tt-mod"><div class="tt-mod-kind">{kind} modifier (Tier: {tier}) &mdash; {family}</div><div class="tt-mod-text">{text}</div></div>'


def _mod_inline_html(item: Mapping[str, Any]) -> str:
    kind = escape(str(item.get("type", "Modifier")))
    tier = _display_int(item.get("tier", item.get("max_tier")))
    family = escape(str(item.get("family", "")))
    text = escape(str(item.get("text", "")))
    return f'<span class="tt-mod-inline">{kind} (T{tier}) {family}: {text}</span>'


def _target_card_html(report: Mapping[str, Any]) -> str:
    input_data = _mapping(report.get("input"), "input")
    target = _mapping(_mapping(report.get("context", {}), "context").get("target", {}), "target")
    base = escape(str(input_data.get("base", "")))
    ilvl = input_data.get("item_level")
    quality = input_data.get("quality")
    flags = _mapping(input_data.get("flags", {}), "flags")
    badge_words = (("Corrupted", "corrupted"), ("Fractured Item", "fractured"), ("Synthesised Item", "synthesised"), ("Mirrored", "mirrored"), ("Influenced Item", "influenced"), ("Split Item", "split"))
    badges = "".join(f'<div class="tt-badge">{escape(word)}</div>' for word, key in badge_words if flags.get(key))
    lines = [_mod_line_html(item) for item in target.get("criteria", [])]
    for group in target.get("any_of", []):
        if not isinstance(group, list) or not group:
            continue
        options = " / ".join(_mod_inline_html(item) for item in group)
        lines.append(f'<div class="tt-mod tt-any"><span class="tt-any-label">One of:</span> {options}</div>')
    if not lines and target.get("value_rows"):
        seen: set[str] = set()
        for row in target["value_rows"]:
            group = str(row.get("group"))
            if group in seen:
                continue
            seen.add(group)
            lines.append(_mod_line_html(row))
    threshold = target.get("threshold")
    threshold_html = ""
    if threshold is not None and target.get("value_table"):
        threshold_html = f'<p class="tt-note">The route stops once the item scores at least {_display_number(threshold)} points on the input value table (see evidence for the full table).</p>'
    quality_html = f" &middot; Quality: {_display_int(quality)}%" if isinstance(quality, Real) and not isinstance(quality, bool) and quality else ""
    return f'''<section class="tooltip-card">
      <div class="tt-header tt-rare">{base}</div>
      <div class="tt-sub">Item Level: {_display_int(ilvl)}{quality_html}</div>
      {badges}
      <div class="tt-mods">{"".join(lines) or '<p class="muted">No target modifiers were provided.</p>'}</div>
      {threshold_html}
    </section>'''


def _route_action_chain_html(flow: Mapping[str, Any]) -> str:
    """The route row's compact chain: actions in policy order, with a short
    repeat/reset note on any step that loops (never bare payment currencies:
    D95 -- a chip is what you click, not what you pay with)."""
    steps = flow.get("steps", [])
    if not steps:
        return ""
    parts: list[str] = []
    for index, step in enumerate(steps):
        family = _currency_family(step["action"])
        parts.append(f'<span class="chip chip-{family}">{escape(step["action"])}</span>')
        repeat_labels = [t.get("label") for t in step.get("transitions", []) if t.get("kind") == "repeat" and t.get("label")]
        other_labels = [t.get("label") for t in step.get("transitions", []) if t.get("kind") in ("reset", "restart") and t.get("label")]
        if repeat_labels:
            parts.append(f'<span class="chip-note">(repeat while: {escape("; ".join(repeat_labels))})</span>')
        if other_labels:
            parts.append(f'<span class="chip-note">(otherwise: {escape("; ".join(other_labels))})</span>')
        if index < len(steps) - 1:
            parts.append('<span class="chip-arrow">&rarr;</span>')
    return "".join(parts)


def _route_try_chance(route: Mapping[str, Any]) -> str | None:
    stages = route.get("stages", [])
    probability = route.get("metadata", {}).get("success_probability")
    if probability is None:
        if len(stages) == 1:
            probability = stages[0].get("probability")
        elif len(stages) == 2 and stages[0].get("expected_attempts") == 1:
            probability = stages[1].get("probability")
    if isinstance(probability, bool) or not isinstance(probability, Real) or not math.isfinite(probability) or not (0 < probability <= 1):
        return None
    count = round(1 / probability)
    return f"1 out of {count:,} ({_display_percent(probability)})"


def _route_row_html(index: int, route: Mapping[str, Any]) -> str:
    chips = _route_action_chain_html(route.get("flow", {}))
    chance = _route_try_chance(route)
    chance_html = f'<div class="route-chance">Success chance per try: {chance}</div>' if chance else ""
    approx = "~" if route.get("cost_label") == "approximate" else ""
    title = escape(str(route.get("title") or route.get("name") or route.get("id")))
    return f'''<input type="radio" name="route" id="tab-{index}" class="route-tab"{" checked" if index == 0 else ""}>
    <label for="tab-{index}" class="route-row">
      <div class="route-title">{title}</div>
      <div class="route-chips">{chips}</div>
      {chance_html}
      <div class="route-costs">avg {_display_number(route.get("expected_cost"))} <span class="chip chip-orb">{_CHAOS_LABEL}</span> &middot; p90: {approx}{_display_number(route.get("cost_p90"))} <span class="chip chip-orb">{_CHAOS_LABEL}</span></div>
    </label>'''


def _flow_html(flow: Mapping[str, Any]) -> str:
    steps = flow.get("steps", [])
    if not steps:
        return '<p class="muted">No crafting flow is available for this route.</p>'
    parts: list[str] = []
    for index, step in enumerate(steps):
        chance_html = f'<div class="flow-meta">chance per use: {_display_percent(step["chance"])}</div>' if step.get("chance") is not None else ""
        meta_html = f'<div class="flow-meta">avg uses: {_display_number(step["uses"])} &middot; cost: {_display_number(step["cost"])} {_CHAOS_LABEL}</div>'
        meta_html += _flow_payment_html(step)
        forward_label = None
        badges: list[str] = []
        for transition in step.get("transitions", []):
            kind = transition.get("kind")
            label = transition.get("label")
            to = transition.get("to")
            if kind == "forward" and to == index + 1:
                forward_label = label
                continue
            if kind == "success":
                badges.append(f'<div class="flow-badge flow-success">&#127937; {escape(label or "Target complete")}</div>')
            elif kind == "repeat":
                badges.append(f'<div class="flow-badge flow-repeat">&#8635; repeat: {escape(label or "")}</div>')
            elif kind == "reset":
                target_no = to + 1 if isinstance(to, int) else "?"
                badges.append(f'<div class="flow-badge flow-reset">&#8634; back to Step {target_no}: {escape(label or "")}</div>')
            elif kind == "restart":
                badges.append(f'<div class="flow-badge flow-restart">&#8962; new base: {escape(label or "")}</div>')
            elif kind == "forward":
                target_no = to + 1 if isinstance(to, int) else "?"
                badges.append(f'<div class="flow-badge flow-forward">&rArr; Step {target_no}: {escape(label or "")}</div>' if label else f'<div class="flow-badge flow-forward">&rArr; Step {target_no}</div>')
        family = _currency_family(step["action"])
        parts.append(f'''<div class="flow-step">
      <div class="flow-title">Step {index + 1}</div>
      <div class="flow-chip flow-chip-{family}">{escape(step["action"])}</div>
      {chance_html}{meta_html}
      {"".join(badges)}
    </div>''')
        if index < len(steps) - 1:
            label_html = f'<span class="flow-cond">{escape(forward_label)}</span>' if forward_label else ""
            parts.append(f'<div class="flow-arrow">&rarr;{label_html}</div>')
    restart = flow.get("restart")
    restart_html = ""
    if restart:
        restart_html = f'<div class="flow-house">&#8962; A wrong fracture buys a new Base (avg {_display_number(restart["uses"])}, {_display_number(restart["cost"])} {_CHAOS_LABEL}) and restarts from Step 1.</div>'
    return f'<div class="flow-track">{"".join(parts)}</div>{restart_html}'


def _flow_payment_html(step: Mapping[str, Any]) -> str:
    """Show the payment under an action box ("N Divine Orb each") whenever
    one use of the action costs something other than exactly one unit of a
    single currency (a plain "Use Orb of X" action needs no extra line: its
    payment is already the same number as "avg uses")."""
    uses = step.get("uses")
    payments = [p for p in step.get("payments", []) if p.get("count")]
    if not payments or not isinstance(uses, Real) or isinstance(uses, bool) or not uses:
        return ""
    parts = []
    for payment in payments:
        per_use = payment["count"] / uses
        if len(payments) == 1 and math.isclose(per_use, 1.0, rel_tol=1e-9, abs_tol=1e-9):
            continue
        parts.append(f'{_display_number(per_use)} {escape(_currency_display_name(str(payment["currency"])))}')
    if not parts:
        return ""
    return f'<div class="flow-meta">{" + ".join(parts)} each</div>'


def _example_item_html(route: Mapping[str, Any], report: Mapping[str, Any]) -> str:
    terminal = route.get("audit", {}).get("terminal_distribution", [])
    if not isinstance(terminal, list) or not terminal:
        return ""
    best = max(terminal, key=lambda entry: entry.get("probability", 0) if isinstance(entry, Mapping) else 0)
    labels_map = _mapping(_mapping(_mapping(report.get("context", {}), "context").get("target", {}), "target").get("labels", {}), "labels")
    input_data = _mapping(report.get("input"), "input")
    rows = "".join(
        f'<div class="tt-mod tt-added"><span class="tt-tag tt-tag-added">Added</span> {escape(str(labels_map.get(label, label)))}</div>'
        for label in best.get("labels", [])
        if isinstance(label, str)
    )
    probability = best.get("probability")
    return f'''<div class="tooltip-card tooltip-example">
      <div class="tt-header tt-rare">{escape(str(input_data.get("base", "")))}</div>
      <div class="tt-mods">{rows}</div>
      <p class="tt-note">One successful outcome actually computed by the planner ({_display_percent(probability)} of successful runs land on exactly this modifier set). A failed attempt is simply missing one or more of the required modifiers shown at the top of the page.</p>
    </div>'''


def _costs_table_html(accounting: Mapping[str, Any], aggregated_rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f'<tr><td>{escape(_currency_display_name(str(row["currency"])))}</td><td>{_display_number(row["count"])}</td>'
        f'<td>{_display_number(row["unit_price"])}</td><td>{_display_number(row["spend"])}</td></tr>'
        for row in aggregated_rows
    )
    total = accounting.get("total")
    complete = accounting.get("complete")
    warn = "" if complete else f'<p class="bad">Incomplete cost accounting: {escape(str(accounting.get("reason") or "no reason given"))}</p>'
    return f'''<div class="table-wrap"><table><thead><tr><th>Currency</th><th>Used (average)</th><th>{_CHAOS_LABEL} each</th><th>{_CHAOS_LABEL} total</th></tr></thead>
      <tbody>{body}</tbody>
      <tfoot><tr><td colspan="3">Total</td><td>{_display_number(total)}</td></tr></tfoot>
    </table></div>{warn}'''


def _step_html(step: Mapping[str, Any]) -> str:
    if isinstance(step, Mapping):
        text, detail = step.get("text", ""), step.get("detail")
    else:
        text, detail = str(step), None
    detail_html = f'<div class="step-detail">{escape(str(detail))}</div>' if detail else ""
    return f"<li>{escape(str(text))}{detail_html}</li>"


def _route_panel_html(route: Mapping[str, Any], report: Mapping[str, Any]) -> str:
    flow_html = _flow_html(route.get("flow", {}))
    steps_html = "".join(_step_html(step) for step in route.get("instructions", []))
    example_html = _example_item_html(route, report)
    aggregated = _aggregate_rows(route.get("accounting", {}).get("rows", []))
    costs_html = _costs_table_html(route.get("accounting", {}), aggregated)
    title = escape(str(route.get("title") or route.get("name") or ""))
    return f'''<h2>Crafting flow &mdash; {title}</h2>
    <div class="flow-scroll">{flow_html}</div>
    <h2>Step by step</h2>
    <div class="steps-with-example">
      <ol class="steps">{steps_html or "<li>No instructions are available.</li>"}</ol>
      {example_html}
    </div>
    <h2>Costs per success</h2>
    {costs_html}'''


def _routes_section_html(routes: list[Any], report: Mapping[str, Any]) -> str:
    visible, hidden = routes[:6], routes[6:]
    radios_and_rows = "".join(_route_row_html(index, route) for index, route in enumerate(visible))
    hidden_rows = "".join(_route_row_html(index + len(visible), route) for index, route in enumerate(hidden))
    show_all = f'<details class="show-all"><summary>Show all {len(routes)} routes</summary>{hidden_rows}</details>' if hidden else ""
    panels = "".join(f'<div class="route-panel" id="panel-{index}">{_route_panel_html(route, report)}</div>' for index, route in enumerate(routes))
    style_rules = "".join(f'#tab-{index}:checked ~ .route-panels #panel-{index}{{display:block}}' for index in range(len(routes)))
    return f'''<section class="routes">
      <h2>Routes</h2>
      {radios_and_rows}
      {show_all}
      <div class="route-panels">{panels}</div>
      <style>.route-panel{{display:none}}{style_rules}</style>
    </section>'''


def _footer_html(report: Mapping[str, Any]) -> str:
    generation = _mapping(_mapping(report.get("context", {}), "context").get("generation", {}), "generation")
    generated_at = generation.get("generated_at")
    commit = generation.get("commit")
    commit_html = f" from commit {escape(str(commit)[:12])}" if isinstance(commit, str) and commit else ""
    return f'''<footer>
      <p class="muted">Prices are placeholders, not trade prices.</p>
      <p><a href="evidence.html">Evidence and proof</a></p>
      <p class="muted">Generated {escape(str(generated_at or "-"))}{commit_html}.</p>
    </footer>'''


# --------------------------------------------------------------------------
# Evidence page (evidence.html): everything the player page dropped.
# --------------------------------------------------------------------------


def _evidence_body_html(report: Mapping[str, Any]) -> str:
    return (
        '<p><a href="index.html">&larr; Back to the report</a></p>'
        + _evidence_summary_html(report)
        + _evidence_pytest_html(report)
        + _evidence_coe_html(report)
        + _evidence_commands_html(report)
        + _evidence_routes_html(report)
        + _evidence_unavailable_html(report)
        + _evidence_raw_html(report)
    )


def _evidence_summary_html(report: Mapping[str, Any]) -> str:
    evidence = report.get("evidence")
    if not isinstance(evidence, Mapping):
        return '<section><h2>Evidence</h2><p class="bad">No evidence was provided.</p></section>'
    pytest_data = _mapping(evidence.get("pytest", {}), "evidence pytest")
    coe = _mapping(evidence.get("coe", {}), "evidence coe")
    revision = evidence.get("revision_message")
    return f'''<section><h2>Evidence</h2>
      <p>{f'<span class="bad">{escape(str(revision))}</span> ' if revision else ""}pytest status: <strong>{escape(str(pytest_data.get("status", "unavailable")))}</strong>;
      Craft of Exile cross-check status: <strong>{escape(str(coe.get("status", "unavailable")))}</strong>;
      working tree dirty: {escape(str(evidence.get("working_tree_dirty")))}; revision {escape(str(evidence.get("git_commit") or "not provided"))};
      generated at {escape(str(evidence.get("generated_at") or "not provided"))}.</p>
      <p class="muted">Tests and Craft of Exile cases check components, not the whole route and not the live game.</p></section>'''


def _evidence_pytest_html(report: Mapping[str, Any]) -> str:
    evidence = report.get("evidence") if isinstance(report.get("evidence"), Mapping) else {}
    pytest_data = _mapping(evidence.get("pytest", {}), "evidence pytest")
    cases = pytest_data.get("cases", [])
    grouped: dict[str, list[Any]] = {}
    if isinstance(cases, list):
        for item in cases:
            if isinstance(item, Mapping):
                grouped.setdefault(str(item.get("file", "unknown file")), []).append(item)
    body = "".join(
        f'<h3>{escape(file)}</h3><div class="table-wrap"><table><thead><tr><th>Test</th><th>Status</th><th>Minutes</th><th>Message</th></tr></thead><tbody>'
        + "".join(f'<tr><td>{escape(str(item.get("name")))}</td><td>{escape(str(item.get("status")))}</td><td>{_display_number(item.get("duration_minutes"))}</td><td>{escape(str(item.get("message") or "-"))}</td></tr>' for item in items)
        + "</tbody></table></div>"
        for file, items in grouped.items()
    ) or "<p>No test case list is available.</p>"
    return f'''<section><h2>pytest summary</h2>
      <p>tests {_display_int(pytest_data.get("tests"))}, passed {_display_int(pytest_data.get("passed"))}, failures {_display_int(pytest_data.get("failures"))}, errors {_display_int(pytest_data.get("errors"))}, skipped {_display_int(pytest_data.get("skipped"))}.</p>
      <details><summary>Test cases by file</summary>{body}</details></section>'''


def _evidence_coe_html(report: Mapping[str, Any]) -> str:
    evidence = report.get("evidence") if isinstance(report.get("evidence"), Mapping) else {}
    coe = _mapping(evidence.get("coe", {}), "evidence coe")
    rows = coe.get("cases", [])
    body = "".join(
        f'<tr><td>{escape(str(row.get("id")))}</td><td>{escape(str(row.get("action")))}</td><td>{escape(str(row.get("base")))}</td>'
        f'<td>{escape(", ".join(str(t) for t in row.get("targets", [])))}</td><td>{_display_percent(row.get("ours"))}</td><td>{_display_percent(row.get("coe"))}</td>'
        f'<td>{"-" if row.get("relative_difference") is None else _display_number(row["relative_difference"] * 100) + "%"}</td></tr>'
        for row in rows if isinstance(row, Mapping)
    ) or '<tr><td colspan="7">No Craft of Exile cases.</td></tr>'
    return f'''<section><h2>Craft of Exile cross-check</h2><div class="table-wrap"><table>
      <thead><tr><th>ID</th><th>Action</th><th>Base</th><th>Targets</th><th>Ours</th><th>CoE</th><th>Difference</th></tr></thead>
      <tbody>{body}</tbody></table></div></section>'''


def _evidence_commands_html(report: Mapping[str, Any]) -> str:
    evidence = report.get("evidence") if isinstance(report.get("evidence"), Mapping) else {}
    commands = evidence.get("commands", [])
    items = "".join(
        f'<li><strong>{escape(str(command.get("name")))}</strong>: {escape(" ".join(str(a) for a in command.get("argv", [])))}; exit {_display_int(command.get("exit_code"))}; '
        f'{_display_number(command.get("duration_minutes"))} min; {_local_link(command.get("stdout_file"), "stdout")} / {_local_link(command.get("stderr_file"), "stderr")}</li>'
        for command in commands if isinstance(command, Mapping)
    ) or "<li>No commands were recorded.</li>"
    artifacts_map = _mapping(evidence.get("artifacts", {}), "artifacts")
    artifacts = "".join(f'<li>{escape(str(name))}: {_local_link(path)}</li>' for name, path in artifacts_map.items()) or "<li>No artifacts were recorded.</li>"
    return f'<section><h2>Commands and artifacts</h2><p>Full proof: {_local_link(evidence.get("proof_link"), "proof.json")}</p><ul>{items}</ul><ul>{artifacts}</ul><p>Raw plan: <a href="plan.json">plan.json</a></p></section>'


def _evidence_routes_html(report: Mapping[str, Any]) -> str:
    routes = report.get("routes", [])
    body = "".join(_evidence_route_detail_html(route) for route in routes if isinstance(route, Mapping))
    return f'<section><h2>Route detail</h2>{body}</section>'


def _evidence_route_detail_html(route: Mapping[str, Any]) -> str:
    parameter_rows = "".join(
        f'<tr><td>{escape(str(key))}</td><td>{escape(json.dumps(value) if isinstance(value, (dict, list)) else str(value))}</td></tr>'
        for key, value in route.get("parameters", {}).items()
    )
    dump = json.dumps({"decisions": route.get("decisions"), "source": route.get("source"), "metadata": route.get("metadata"), "audit": route.get("audit")}, indent=2, ensure_ascii=False)
    title = escape(str(route.get("title") or route.get("id")))
    return f'''<details><summary>{title} ({escape(str(route.get("id")))})</summary>
      <p>expected cost {_display_number(route.get("expected_cost"))}; p90 {_display_number(route.get("cost_p90"))} ({escape(str(route.get("cost_label")))}); expected utility {_display_number(route.get("expected_utility"))};
      stopping threshold {_display_number(route.get("stopping_threshold"))}; frontier {escape(str(route.get("frontier")))}.</p>
      <div class="table-wrap"><table><tbody>{parameter_rows}</tbody></table></div>
      <pre>{escape(dump)}</pre>
    </details>'''


def _evidence_unavailable_html(report: Mapping[str, Any]) -> str:
    unavailable = report.get("unavailable", [])
    items = "".join(
        f'<li>{escape(str(row.get("id") or row.get("name") or "route"))}: {escape("; ".join(str(r) for r in row.get("reasons", [row.get("reason", "no reason given")])))}</li>'
        for row in unavailable if isinstance(row, Mapping)
    ) or "<li>No unavailable routes.</li>"
    return f'<section><h2>Unavailable routes</h2><ul>{items}</ul></section>'


def _evidence_raw_html(report: Mapping[str, Any]) -> str:
    dump = json.dumps({"assumptions": report.get("assumptions"), "input": report.get("input"), "prices": report.get("prices")}, indent=2, ensure_ascii=False)
    return f'<section><h2>Assumptions and raw input</h2><pre>{escape(dump)}</pre></section>'


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _list(value: Mapping[str, Any], key: str) -> list[Any]:
    result = value.get(key, [])
    if not isinstance(result, list):
        raise ValueError(f"{key} must be a list")
    return result


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _integer(value: Any, name: str) -> int:
    number = _number(value, name)
    if not number.is_integer() or number < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return int(number)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("report contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(entry) for key, entry in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(entry) for entry in value]
    return str(value)


def _price_key(currency: str, values: Mapping[str, Any]) -> str | None:
    """Resolve display names to the existing loadout's production keys."""
    aliases = {
        "Alchemy": "alchemy", "Scour": "scour", "Chaos": "chaos", "Transmute": "transmute",
        "Alteration": "alteration", "Augmentation": "augmentation", "Regal": "regal", "Exalt": "exalted",
        "Fracturing Orb": "fracturing", "Harvest reforge Life": "harvest_reforge:life",
    }
    candidates = (currency, aliases.get(currency), "fossil:" + currency.removeprefix("fossil "),
                  "resonator:" + currency.split("-", 1)[0] if currency.endswith("Chaotic Resonator") else None)
    return next((candidate for candidate in candidates if isinstance(candidate, str) and candidate in values), None)


def _bench_action_name(context: Mapping[str, Any], index: int) -> str:
    names = _mapping(context.get("bench_names", {}), "bench_names")
    return f"Crafting Bench: {names.get(str(index), f'recipe {index}')}"


def _add_bench_recipe(rows: list[dict[str, Any]], values: Mapping[str, Any], context: Mapping[str, Any], index: int, multiplier: float, add: Any) -> None:
    """Add the payment row(s) for one bench-craft ACTION. The action itself
    (a crafting-bench recipe, e.g. "Suffixes Cannot Be Changed") happens
    `multiplier` times; the payment row(s) carry however many currency units
    that costs per use, which is not always the same number (a recipe can
    cost more than one unit of its currency per use)."""
    action = _bench_action_name(context, index)
    recipes = _mapping(context.get("bench_recipes", {}), "bench_recipes")
    recipe = recipes.get(str(index), recipes.get(index))
    if not isinstance(recipe, Mapping):
        rows.append({"currency": f"Bench {index}", "count": multiplier, "unit_price": None, "spend": None, "action": action, "uses": multiplier})
        return
    # One bench craft can cost more than one currency (a multimod recipe): that is ONE batch of
    # `multiplier` uses billed in several currencies, so only the first row counts towards the
    # action's total uses (see _aggregate_actions).
    for position, (currency, quantity) in enumerate(recipe.items()):
        add(str(currency), multiplier * _number(quantity, "bench recipe quantity"), str(currency), action=action, uses=(multiplier if position == 0 else 0.0))
