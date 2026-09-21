"""Pure offline route-report construction and HTML rendering.

The planner remains the sole owner of probabilities.  This module only labels
and accounts for fields it receives in an accepted plan document.
"""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any


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
    rows: list[dict[str, Any]] = []
    complete = True
    reason: str | None = None

    def add(currency: str, count: float, price_key: str | None = None) -> None:
        nonlocal complete, reason
        if count == 0:
            return
        resolved_key = price_key or _price_key(currency, values)
        price = values.get(resolved_key) if resolved_key is not None else None
        if isinstance(price, bool) or not isinstance(price, Real) or not math.isfinite(price):
            complete = False
            reason = f"missing price for {currency}"
            rows.append({"currency": currency, "count": count, "unit_price": None, "spend": None})
            return
        rows.append({"currency": currency, "count": count, "unit_price": float(price), "spend": count * float(price)})

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
            for fossil_id in fossil_ids:
                add(str(fossils.get(str(fossil_id), fossils.get(fossil_id, f"fossil {fossil_id}"))), count, f"fossil:{fossil_id}")
            add(f"{len(fossil_ids)}-socket Chaotic Resonator", count, f"resonator:{len(fossil_ids)}")
    elif identifier.startswith("fracture"):
        counts = _mapping(route.get("expected_action_counts", {}), "expected_action_counts")
        if not counts:
            complete, reason = False, "missing expected_action_counts"
        else:
            envy_id = context.get("envy_id")
            for action, currency in (("bases", "Base"), ("alchemy", "Alchemy"), ("scour", "Scour"), ("fracturing", "Fracturing Orb"), ("envy", "Envy")):
                if action in counts:
                    count = _number(counts[action], action)
                    if action == "bases":
                        rows.append({"currency": "Base", "count": count, "unit_price": base_cost, "spend": count * base_cost})
                    else:
                        add(currency, count, envy_id if action == "envy" and isinstance(envy_id, str) else None)
    elif identifier.startswith("suffix-protected"):
        recovery = _mapping(route.get("recovery", {}), "recovery")
        parameters = _mapping(route.get("parameters", {}), "parameters")
        envy, cycles = recovery.get("expected_envy_applications"), recovery.get("expected_prefix_cycles")
        if envy is None or cycles is None:
            complete, reason = False, "missing protected recovery accounting"
        else:
            envy_count, cycle_count = _number(envy, "expected_envy_applications"), _number(cycles, "expected_prefix_cycles")
            envy_id = context.get("envy_id")
            add("Envy", envy_count, envy_id if isinstance(envy_id, str) else None)
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
        rows.insert(0, {"currency": "Base", "count": 1.0, "unit_price": base_cost, "spend": base_cost})
    if complete and any(row["spend"] is None for row in rows):
        complete, reason = False, reason or "missing price or recipe"
    total = math.fsum(float(row["spend"]) for row in rows if row["spend"] is not None)
    expected = route.get("expected_cost")
    matches = complete and expected is not None and math.isclose(total, _number(expected, "expected_cost"), rel_tol=1e-9, abs_tol=1e-7)
    if complete and not matches:
        reason = f"accounting total {total:g} differs from planner expected_cost {_number(expected, 'expected_cost'):g}"
    return {"rows": rows, "total": total, "complete": complete and matches, "reason": reason}


def render_report(report: Mapping[str, Any]) -> str:
    """Fill the standalone report template with safely embedded JSON data."""
    title = escape(str(_mapping(report.get("input"), "input").get("name", "Crafting route report")))
    payload = json.dumps(_json_value(report), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = (Path(__file__).with_name("report_assets") / "template.html").read_text(encoding="utf-8")
    if "{{REPORT_TITLE}}" not in template or "{{REPORT_DATA}}" not in template:
        raise ValueError("report template is missing required placeholders")
    return template.replace("{{REPORT_TITLE}}", title).replace("{{REPORT_DATA}}", payload)
def _route(route: Mapping[str, Any], plan: Mapping[str, Any], context: Mapping[str, Any], index: int) -> dict[str, Any]:
    stages = []
    identifier = _string(route.get("id", ""), "route id")
    for stage in _list(route, "stages"):
        row = _mapping(stage, "stage")
        name = str(row.get("name", "stage"))
        meaning = "Шанс дойти до этапа" if identifier.startswith("magic") else _stage_meaning(identifier, name)
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
    return {"key": f"{identifier}-{threshold if threshold is not None else 'base'}-{index}", "id": identifier, "name": str(route.get("name", identifier)), "title": title, "search_text": f"{title} {identifier} {route.get('name', '')}", "expected_cost": route.get("expected_cost"), "cost_p90": route.get("cost_p90"), "cost_label": "приблизительно" if route.get("cost_p90_interval") else "точно", "expected_utility": route.get("expected_utility"), "frontier": bool(route.get("frontier", False)), "stopping_threshold": threshold, "stages": stages, "parameters": dict(_mapping(route.get("parameters", {}), "parameters")), "decisions": list(route.get("decision_points", [])), "metadata": metadata, "source": {"assumptions": list(route.get("assumptions", [])), "design": ["docs/design/route-report.md", "docs/design/parameter-search.md", "docs/design/family-policies.md"], "generation": context.get("generation", {})}, "audit": {"parameter_audit": list(route.get("parameter_audit", [])), "terminal_distribution": list(route.get("terminal_distribution", []))}, "instructions": _instructions(identifier, route, context), "accounting": material_accounting(route, plan, context)}


def _route_title(identifier: str, route: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    parameters = _mapping(route.get("parameters", {}), "parameters")
    if identifier == "suffix-protected-life-bench-131":
        return "Envy → защита суффиксов → Exalted Orb → верстак"
    if identifier == "suffix-protected-life":
        return "Envy → защита суффиксов → Exalted Orb"
    if identifier == "suffix-protected-harvest-life":
        return "Envy → защита суффиксов → Harvest Life"
    if identifier == "fracture-life-envy":
        return "Фрактура здоровья T1 → Envy"
    if identifier.startswith("fossil"):
        names = _mapping(context.get("fossil_names", {}), "fossil_names")
        selected = ", ".join(str(names.get(str(value), names.get(value, f"fossil {value}"))) for value in parameters.get("fossil_ids", []))
        return "Fossil: " + selected
    if identifier.startswith("alchemy-scour"):
        return "Alchemy → Scouring"
    if identifier.startswith("chaos"):
        return "Alchemy → Chaos Orb"
    if identifier.startswith("magic"):
        return "Alteration → Regal → Exalted Orb"
    if identifier.startswith("essence"):
        essence_id = parameters.get("forced_essence_id", parameters.get("essence_id"))
        return str(_mapping(context.get("essence_names", {}), "essence_names").get(essence_id, essence_id or route.get("name", identifier)))
    return str(route.get("name", identifier))


def _instructions(identifier: str, route: Mapping[str, Any], context: Mapping[str, Any]) -> list[str]:
    parameters = _mapping(route.get("parameters", {}), "parameters")
    life = _life_target_text(context)
    if identifier.startswith("essence"):
        essence_id = parameters.get("forced_essence_id", parameters.get("essence_id"))
        essence = _mapping(context.get("essence_names", {}), "essence_names").get(essence_id, essence_id or "Essence")
        return ["Возьмите обычную базу.", f"Применяйте {essence} и проверяйте цель после каждого применения.", f"Готово — остановитесь; иначе повторите ту же {essence}."]
    if identifier.startswith("alchemy-scour"):
        return ["Примените Orb of Alchemy.", "Если цель выполнена — остановитесь.", "Иначе примените Orb of Scouring и вернитесь к Alchemy."]
    if identifier.startswith("chaos"):
        early = bool(parameters.get("alchemy_early_stop", True))
        return ["Сначала примените Orb of Alchemy." + (" Проверьте раннюю остановку." if early else " Результат намеренно не используется."), "Затем повторяйте Chaos Orb до цели без Scour между применениями."]
    if identifier.startswith("fossil"):
        fossils = _mapping(context.get("fossil_names", {}), "fossil_names")
        selected = ", ".join(str(fossils.get(str(value), f"fossil {value}")) for value in parameters.get("fossil_ids", []))
        sockets = parameters.get("socket_count", "?")
        return ["Примените Orb of Alchemy и немедленно проверьте цель.", f"При неудаче заполните один {sockets}-socket Chaotic Resonator: {selected}; примените его к rare-предмету.", "Повторяйте полный рецепт и проверяйте после каждого применения."]
    if identifier.startswith("fracture"):
        early = bool(parameters.get("alchemy_early_stop", False))
        return ["На каждой новой обычной базе примените Orb of Alchemy." + (" После каждого Alchemy проверьте раннее завершение." if early else " Ранняя проверка намеренно отключена."), f"Если цель не готова, но ровно четыре обычных явных модификатора уже включают {life}, немедленно примените Fracturing Orb. Иначе применяйте Orb of Scouring + Orb of Alchemy до этого условия.", "Неверную фрактуру отложите без выручки от продажи в этом расчёте и купите новую базу; отмены нет.", f"При фрактуре {life} повторяйте Deafening Essence of Envy до цели."]
    if identifier.startswith("suffix-protected-harvest"):
        return _protected_preparation(parameters) + ["Примените Harvest reforge Life с Suffixes Cannot Be Changed; attack/caster blocker не используется.", f"{life} завершает маршрут. При свободном префиксе повторите оплаченные защиту суффиксов и reforge; при трёх префиксах вернитесь к Envy-подготовке. Scour здесь нет."]
    if identifier.startswith("suffix-protected"):
        max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
        steps = _protected_preparation(parameters) + ["Примените Suffixes Cannot Be Changed и Orb of Scouring."]
        if max_exalts:
            steps.append(f"Сделайте до {max_exalts} Exalted Orb; остановитесь после первого {life}. Только после неудачи всех {max_exalts} применений: при свободном префиксе повторите оплаченные защиту суффиксов и Scour, при трёх префиксах вернитесь к Envy.")
        if parameters.get("bench_finish_id") is not None:
            bench = _mapping(context.get("bench_names", {}), "bench_names").get(str(parameters["bench_finish_id"]), f"bench {parameters['bench_finish_id']}")
            steps.append(f"Завершите {bench}; это не заменяет требуемый {life}.")
        return steps
    if identifier.startswith("magic"):
        max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
        early = bool(parameters.get("early_stop", False))
        magic_gate, regal_gate = parameters.get("magic_min_desired"), parameters.get("regal_min_desired")
        steps = ["Примените Orb of Transmutation; это оплачиваемая подготовка без проверки.", "Примените Orb of Alteration; только при одном модификаторе добавьте Orb of Augmentation.", f"{'Сначала проверяйте цель на каждом этапе.' if early else 'Проверяйте цель только на последнем настроенном этапе.'} Затем требуется не менее {magic_gate} желаемых модификаторов: моды из цели или тиры с положительной ценностью из входной таблицы; неудача сбрасывается Orb of Scouring + Transmutation."]
        if max_exalts:
            steps.append(f"Затем примените Regal Orb; продолжайте без промежуточной проверки цели, иначе сброс Orb of Scouring + Transmutation.")
        else:
            steps.append(f"Затем примените Regal Orb; после проверки цели требуется не менее {regal_gate} желаемых модификаторов, иначе сброс Orb of Scouring + Transmutation.")
        if max_exalts:
            steps.append(f"После Regal сделайте до {max_exalts} Exalted Orb; {'после каждого применения сначала проверяйте цель и готовое останавливайте.' if early else 'проверьте цель после последнего применения.'} При неудаче сбросьте Orb of Scouring + Transmutation.")
        else:
            steps.append("После Regal проверьте цель: готово — остановитесь; иначе Orb of Scouring + Orb of Transmutation и вернитесь к Alteration.")
        return steps
    return [str(step) for step in route.get("steps", [])] or ["Для этого маршрута нет перевода инструкций."]


def _protected_preparation(parameters: Mapping[str, Any]) -> list[str]:
    early = bool(parameters.get("preparation_early_stop", False))
    suffixes = parameters.get("minimum_desired_elemental_suffixes", "?")
    prefixes = parameters.get("max_prefixes", "?")
    first = "Повторяйте Deafening Essence of Envy." + (" Цель, готовая во время подготовки, сразу завершает маршрут." if early else " Ранняя готовая цель здесь намеренно не останавливает маршрут.")
    return [first, f"Примите только ровно 3 суффикса, минимум {suffixes} суффиксов сопротивления стихиям из цели и не более {prefixes} префиксов; остальные Envy-результаты повторите."]


def _life_target_text(context: Mapping[str, Any]) -> str:
    target = _mapping(context.get("target", {}), "target")
    labels = _mapping(target.get("labels", {}), "target labels")
    value = labels.get("IncreasedLife:1")
    return f"здоровье T1 ({value})" if isinstance(value, str) else "здоровье T1"


def _stage_meaning(identifier: str, name: str) -> str:
    lower = name.lower()
    if "preparation" in lower:
        return "Вход в условие отбора подготовки или раннюю остановку"
    if "protected" in lower:
        return "Условный шанс цели в одном защищённом цикле"
    if identifier.startswith(("essence", "alchemy", "chaos", "fossil")):
        return "Шанс цели за одно применение"
    return "Вероятность этапа по плану"


def _evidence(evidence: Mapping[str, Any] | None, report_commit: Any) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        return {"status": "unavailable", "message": "Проверки недоступны: proof.json не предоставлен.", "proof_link": "evidence/proof.json"}
    pytest = _mapping(evidence.get("pytest", {}), "evidence pytest")
    coe = _mapping(evidence.get("coe", {}), "evidence coe")
    status = "passed" if pytest.get("status") == "passed" and coe.get("status") == "passed" else "unavailable" if "unavailable" in {pytest.get("status"), coe.get("status")} else "failed"
    mismatch = isinstance(report_commit, str) and evidence.get("git_commit") != report_commit
    def link(path: Any) -> Any:
        return f"evidence/{path}" if isinstance(path, str) else path
    commands = [{**dict(command), "stdout_file": link(command.get("stdout_file")), "stderr_file": link(command.get("stderr_file"))} if isinstance(command, Mapping) else command for command in evidence.get("commands", [])]
    return {"status": status, "message": evidence.get("message"), "pytest": dict(pytest), "coe": dict(coe), "commands": commands, "artifacts": {key: link(value) for key, value in _mapping(evidence.get("artifacts", {}), "artifacts").items()}, "proof_link": "evidence/proof.json", "git_commit": evidence.get("git_commit"), "generated_at": evidence.get("generated_at"), "working_tree_dirty": evidence.get("working_tree_dirty"), "revision_message": "Проверки другой ревизии" if mismatch else None}


def _find_stage(route: Mapping[str, Any], needle: str) -> Mapping[str, Any] | None:
    return next((row for raw in _list(route, "stages") if needle in str((row := _mapping(raw, "stage")).get("name", "")).lower()), None)


def _first_stage(route: Mapping[str, Any]) -> Mapping[str, Any] | None:
    stages = _list(route, "stages")
    return _mapping(stages[0], "stage") if stages else None


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


def _add_bench_recipe(rows: list[dict[str, Any]], values: Mapping[str, Any], context: Mapping[str, Any], index: int, multiplier: float, add: Any) -> None:
    recipes = _mapping(context.get("bench_recipes", {}), "bench_recipes")
    recipe = recipes.get(str(index), recipes.get(index))
    if not isinstance(recipe, Mapping):
        rows.append({"currency": f"Bench {index}", "count": multiplier, "unit_price": None, "spend": None})
        return
    for currency, quantity in recipe.items():
        add(str(currency), multiplier * _number(quantity, "bench recipe quantity"), str(currency))
