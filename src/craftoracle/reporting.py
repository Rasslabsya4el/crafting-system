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
from typing import Any


def build_report(plan: Mapping[str, Any], context: Mapping[str, Any], evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a JSON-safe report model without evaluating a crafting policy."""
    ranked = _list(plan, "ranked")
    unavailable = _list(plan, "unavailable")
    routes = [_route(_mapping(route, "ranked route"), plan, context, index) for index, route in enumerate(ranked)]
    evidence_data = _evidence(evidence, context.get("generation", {}).get("commit"))
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
                    add(currency, _number(counts[action], action), envy_id if action == "envy" and isinstance(envy_id, str) else None)
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
    """Render a standalone, CSP-free report which operates entirely offline."""
    title = escape(str(_mapping(report.get("input"), "input").get("name", "Crafting route report")))
    payload = json.dumps(_json_value(report), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>
:root{{color-scheme:dark;--ink:#eef8f7;--muted:#aabdbc;--teal:#42c9bb;--line:#35504e;--bg:#101a1b;--panel:#182526}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1220px;margin:auto;padding:28px}}h1{{margin:0}}h2{{font-size:1.2rem;margin-top:0}}.notice{{background:#483710;border-left:4px solid #f2bb43;padding:10px 14px;margin:18px 0}}.layout{{display:grid;grid-template-columns:minmax(360px,1fr) minmax(0,1.35fr);gap:18px}}section{{background:var(--panel);border:1px solid var(--line);padding:18px;border-radius:6px}}table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}th,td{{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}}button{{font:inherit;color:inherit;background:none;border:0;cursor:pointer;text-align:left;padding:0}}button.route{{width:100%}}button.route:hover,button.route:focus{{color:var(--teal);outline:2px solid var(--teal);outline-offset:2px}}input{{width:100%;padding:8px;border:1px solid var(--line);border-radius:4px;background:#0f1718;color:var(--ink)}}.muted{{color:var(--muted)}}.bad{{color:#ff9d9d}}.good{{color:#65ddcf}}details{{margin-top:12px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#0f1718;padding:10px}}@media print{{body{{background:#fff;color:#111}}section{{background:#fff;border:0}}main{{max-width:none;padding:0}}.no-print{{display:none}}section{{break-inside:avoid}}.layout{{display:block}}}}@media(max-width:800px){{.layout{{grid-template-columns:1fr}}main{{padding:14px}}}}
</style></head><body><main><h1>{title}</h1><div id="app"></div></main><script id="report-data" type="application/json">{payload}</script><script>
const R=JSON.parse(document.getElementById('report-data').textContent),e=s=>String(s??'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const n=x=>typeof x==='number'?x.toLocaleString('ru-RU',{{minimumFractionDigits:1,maximumFractionDigits:1}}):e(x), p=x=>typeof x==='number'?(x>0&&x<.001?'<0,1% (примерно 1 из '+Math.round(1/x).toLocaleString('ru-RU')+')':(x*100).toLocaleString('ru-RU',{{minimumFractionDigits:1,maximumFractionDigits:1}})+'%'):e(x), route=()=>R.routes.find(x=>x.key===location.hash.slice(1))||R.routes[0];
function detail(x){{if(!x)return '<p>Нет доступных маршрутов.</p>';const a=x.accounting, rows=a.rows.map(r=>`<tr><td>${{e(r.currency)}}</td><td>${{n(r.count)}}</td><td>${{r.unit_price==null?'нет цены':n(r.unit_price)}}</td><td>${{r.spend==null?'—':n(r.spend)}}</td></tr>`).join('');return `<h2>${{e(x.name)}}</h2><p class="${{a.complete?'good':'bad'}}">${{a.complete?'Учёт сходится с ожидаемой стоимостью.':'Неполный учёт: '+e(a.reason||'нет данных')}}</p><h3>Инструкция</h3><ol>${{x.instructions.map(s=>'<li>'+e(s)+'</li>').join('')}}</ol><h3>Вероятности этапов</h3><table><tr><th>Этап</th><th>Значение</th><th>Смысл</th></tr>${{x.stages.map(s=>`<tr><td>${{e(s.name)}}</td><td>${{p(s.probability)}}</td><td>${{e(s.meaning)}}</td></tr>`).join('')}}</table><h3>Материалы (${{e(R.prices.unit)}})</h3><table><tr><th>Валюта</th><th>Количество</th><th>Цена</th><th>Расход</th></tr>${{rows}}</table><p>Итого: ${{n(a.total)}} ${{e(R.prices.unit)}}; план: ${{n(x.expected_cost)}} ${{e(R.prices.unit)}}.</p><details><summary>Параметры, решения и источники</summary><pre>${{e(JSON.stringify({{parameters:x.parameters,decisions:x.decisions,source:x.source}},null,2))}}</pre></details>`}}
function target(){{const t=R.context.target||{{}}, c=(t.criteria||[]).map(x=>`<li>${{e(x.text)}} (tier ${{n(x.max_tier)}})</li>`).join(''), a=(t.any_of||[]).map(g=>`<li>одно из: ${{g.map(x=>e(x.text)+' (tier '+n(x.max_tier)+')').join('; ')}}</li>`).join('');if(t.value_table){{const rows=Object.entries(t.value_table).map(([g,v])=>`<tr><td>${{e(g)}}</td><td>${{e(Object.entries(v).map(([tier,p])=>'tier '+tier+': '+p).join('; '))}}</td></tr>`).join('');return `<section><h2>Цель</h2><p>Вымышленная таблица utility, не DPS. Остановиться при ${{n(t.threshold)}} очках.</p><table><tr><th>Группа</th><th>Очки по tier</th></tr>${{rows}}</table></section>`}}return `<section><h2>Цель</h2><ul>${{c+a}}</ul></section>`}}
function evidence(){{const v=R.evidence, py=v.pytest||{{}}, co=v.coe||{{}}, cases=(py.cases||[]).map(x=>`<tr><td>${{e(x.name)}}</td><td>${{e(x.file)}}</td><td>${{e(x.status)}}</td></tr>`).join(''), rows=(co.cases||[]).map(x=>`<tr><td>${{e(x.name||x.id)}}</td><td>${{e(x.status||'')}}</td><td>${{n(x.max_abs_relative_difference??'')}}</td></tr>`).join('');return `<details><summary>Доказательства</summary><p>${{v.status==='unavailable'?'Проверки недоступны':v.status==='passed'?'Компонентные проверки и CoE-сравнение доступны.':'Проверки завершились с ошибкой.'}}</p><p>${{e(v.revision_message||'')}}</p><h3>Тесты: ${{e(py.status||'unavailable')}}</h3><table><tr><th>Case</th><th>Файл</th><th>Статус</th></tr>${{cases}}</table><h3>CoE: ${{e(co.status||'unavailable')}}</h3><table><tr><th>Case</th><th>Статус</th><th>Разница</th></tr>${{rows}}</table><pre>${{e(JSON.stringify(v.commands||[],null,2))}}</pre></details>`}}
function draw(forced){{const q=(forced??document.getElementById('q')?.value??'').toLowerCase(), rs=R.routes.filter(x=>(x.id+x.name).toLowerCase().includes(q));document.getElementById('app').innerHTML=`<p>${{e(R.input.base)}} · ilvl ${{n(R.input.item_level)}} · качество ${{n(R.input.quality)}}</p>${{target()}}<p class="notice"><strong>Цены вымышлены.</strong> ${{e(R.prices.note||'Цены предоставлены входным loadout.')}}</p><div class="layout"><section><label class="no-print">Поиск <input id="q" value="${{e(q)}}"></label><table><tr><th>Маршрут</th><th>Порог</th><th>Среднее</th><th>p90</th><th>Ценность</th><th title="Лучший обмен цены и ценности">На границе</th></tr>${{rs.map(x=>`<tr><td><button class="route" data-key="${{e(x.key)}}">${{e(x.name)}}</button></td><td>${{n(x.stopping_threshold??'—')}}</td><td>${{n(x.expected_cost)}} ${{e(R.prices.unit)}}</td><td>${{n(x.cost_p90)}} ${{e(x.cost_label)}}</td><td>${{n(x.expected_utility)}}</td><td>${{x.frontier?'да':'нет'}}</td></tr>`).join('')}}</table><p class="muted">«На границе» означает лучший доступный обмен ожидаемой цены и ценности.</p><h3>Недоступные</h3>${{R.unavailable.map(x=>`<p><b>${{e(x.name||x.id)}}</b>: ${{e((x.reasons||[]).join('; '))}}</p>`).join('')}}${{evidence()}}</section><section id="detail">${{detail(route())}}</section></div>`;document.getElementById('q').oninput=function(){{const value=this.value, caret=this.selectionStart;draw(value);const next=document.getElementById('q');next.focus();next.setSelectionRange(caret,caret)}};document.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>{{location.hash=b.dataset.key;document.getElementById('detail').innerHTML=detail(route())}})}}draw();window.onhashchange=draw;
</script></body></html>'''


def _route(route: Mapping[str, Any], plan: Mapping[str, Any], context: Mapping[str, Any], index: int) -> dict[str, Any]:
    stages = []
    identifier = _string(route.get("id", ""), "route id")
    for stage in _list(route, "stages"):
        row = _mapping(stage, "stage")
        name = str(row.get("name", "stage"))
        meaning = "Шанс дойти до этапа" if identifier.startswith("magic") else _stage_meaning(identifier, name)
        stages.append({"name": name, "probability": row.get("probability"), "expected_attempts": row.get("expected_attempts"), "meaning": meaning})
    threshold = route.get("stopping_threshold", _mapping(plan.get("input"), "input").get("utility_threshold"))
    return {"key": f"{identifier}-{threshold if threshold is not None else 'base'}-{index}", "id": identifier, "name": str(route.get("name", identifier)), "expected_cost": route.get("expected_cost"), "cost_p90": route.get("cost_p90"), "cost_label": "приблизительно" if route.get("cost_p90_interval") else "точно", "expected_utility": route.get("expected_utility"), "frontier": bool(route.get("frontier", False)), "stopping_threshold": threshold, "stages": stages, "parameters": dict(_mapping(route.get("parameters", {}), "parameters")), "decisions": list(route.get("decision_points", [])), "source": {"assumptions": list(route.get("assumptions", [])), "generation": context.get("generation", {})}, "instructions": _instructions(identifier, route, context), "accounting": material_accounting(route, plan, context)}


def _instructions(identifier: str, route: Mapping[str, Any], context: Mapping[str, Any]) -> list[str]:
    parameters = _mapping(route.get("parameters", {}), "parameters")
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
        return ["Примените Orb of Alchemy и немедленно проверьте цель.", "При неудаче заполните один Chaotic Resonator выбранными fossil и примените его к rare-предмету.", "Повторяйте полный рецепт и проверяйте после каждого применения."]
    if identifier.startswith("fracture"):
        return ["На новой normal-базе подготовьте ровно четыре ordinary explicit с Life9.", "Примените Fracturing Orb.", "Неверную фрактуру отложите с salvage 0 и купите новую базу; верную Life9 завершайте Deafening Envy."]
    if identifier.startswith("suffix-protected-harvest"):
        return ["Подготовьте выбранные суффиксы Deafening Envy.", "Создайте Suffixes Cannot Be Changed и примените Harvest reforge Life.", "При заполненных префиксах вернитесь к подготовке; иначе повторите lock + reforge."]
    if identifier.startswith("suffix-protected"):
        max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
        steps = ["Подготовьте выбранные суффиксы Deafening Envy.", "Создайте Suffixes Cannot Be Changed и примените Orb of Scouring."]
        if max_exalts:
            steps.append(f"Сделайте до {max_exalts} Exalt Orb; остановитесь после первого Life9.")
        if parameters.get("bench_finish_id") is not None:
            steps.append("Завершите выбранным armour bench craft.")
        return steps
    if identifier.startswith("magic"):
        max_exalts = _integer(parameters.get("max_exalts", 0), "max_exalts")
        steps = ["Примените Orb of Transmutation; этот setup не проверяется.", "Используйте Orb of Alteration; при одном модификаторе добавьте Orb of Augmentation.", "При неудаче сбросьте Orb of Scouring + Transmutation, затем примените Regal Orb."]
        if max_exalts:
            steps.append(f"После Regal сделайте до {max_exalts} Exalt Orb.")
        return steps
    return [str(step) for step in route.get("steps", [])] or ["Для этого маршрута нет перевода инструкций."]


def _stage_meaning(identifier: str, name: str) -> str:
    lower = name.lower()
    if "preparation" in lower:
        return "Вход в gate подготовки или раннюю остановку"
    if "protected" in lower:
        return "Условный шанс цели в одном защищённом цикле"
    if identifier.startswith(("essence", "alchemy", "chaos", "fossil")):
        return "Шанс цели за одно применение"
    return "Вероятность этапа по плану"


def _evidence(evidence: Mapping[str, Any] | None, report_commit: Any) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        return {"status": "unavailable", "message": "Проверки недоступны: proof.json не предоставлен."}
    pytest = _mapping(evidence.get("pytest", {}), "evidence pytest")
    coe = _mapping(evidence.get("coe", {}), "evidence coe")
    status = "passed" if pytest.get("status") == "passed" and coe.get("status") == "passed" else "unavailable" if "unavailable" in {pytest.get("status"), coe.get("status")} else "failed"
    mismatch = isinstance(report_commit, str) and evidence.get("git_commit") != report_commit
    return {"status": status, "pytest": dict(pytest), "coe": dict(coe), "commands": list(evidence.get("commands", [])), "git_commit": evidence.get("git_commit"), "generated_at": evidence.get("generated_at"), "revision_message": "Проверки другой ревизии" if mismatch else None}


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
