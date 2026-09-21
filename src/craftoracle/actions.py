"""Ordinary-currency action adapter over the accepted item pool and exact DP.

Mechanics: docs/mechanics/basic_currency.md, affix_generation.md,
bench_metamods.md and essences.md.  The Q9 boundary and count parameters are
the lead-provisional rules recorded in docs/GOAL.md and data/rules/ordinary.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from craftoracle.distributions import DrawEntry, OutcomeClass, draw_distribution, mixture_distribution
from craftoracle.item_model import ItemState, ModRef, load_item_data, resolve_pool


_Q9_ERROR = "out of tonight's slice: Q9"
_NORMAL, _MAGIC, _RARE = "normal", "magic", "rare"
_LOCK_PREFIXES = "ItemGenerationCannotChangePrefixes"
_LOCK_SUFFIXES = "ItemGenerationCannotChangeSuffixes"
_MULTIMOD = "ItemGenerationCanHaveMultipleCraftedMods"
_NO_ATTACK = "ItemGenerationCannotRollAttackAffixes"
_NO_CASTER = "ItemGenerationCannotRollCasterAffixes"
_ESSENCE_LEVEL_CAPS = {1: 35, 2: 45, 3: 60, 4: 75}  # S21, docs/mechanics/essences.md
_BLOCKED_ACTIONS = {
    "harvest": "Q6", "fossils": "Q13", "eldritch": "Q11", "awakener": "Q20",
    "recombinator": "Q21", "fracture": "Q12", "veiled": "Q12", "corruption": "Q18",
    "beasts": "Q25", "catalysts": "Q23",
}
_DRAW_ACTIONS = frozenset(("transmute", "alteration", "augmentation", "regal", "alchemy", "chaos", "exalted", "essence"))


@dataclass(frozen=True)
class ActionData:
    bases: dict[str, dict]
    mods: dict[str, dict]
    bench: dict[int, dict]
    essences: dict[str, dict]
    rules: dict[str, Any]


@dataclass(frozen=True)
class RollScenario:
    """Inspectable input to one exact weighted draw or count-mixture draw."""

    entries: tuple[DrawEntry, ...]
    draw_counts: tuple[tuple[int, int], ...]
    prefix_cap: int
    suffix_cap: int
    initial_prefixes: int
    initial_suffixes: int
    initial_labels: tuple[str, ...]
    blocked_groups: tuple[str, ...]


def load_action_data(root: Path) -> ActionData:
    """Load the committed projections required by ordinary actions."""
    root = Path(root)
    bases, mods = load_item_data(root / "data/pob_bases.json", root / "data/pob_mod_families.json")
    bench_doc = _json_object(root / "data/pob_bench.json", "bench")
    essence_doc = _json_object(root / "data/pob_essences.json", "essence")
    rules = _json_object(root / "data/rules/ordinary.json", "ordinary rules")
    bench: dict[int, dict] = {}
    for row in _required_rows(bench_doc, "bench"):
        _validate_bench_row(row)
        index = row["source_index"]
        if index in bench:
            raise ValueError(f"duplicate bench source_index: {index}")
        bench[index] = row
    essences: dict[str, dict] = {}
    for row in _required_rows(essence_doc, "essences"):
        _validate_essence_row(row)
        essence_id = row["id"]
        if essence_id in essences:
            raise ValueError(f"duplicate essence id: {essence_id}")
        essences[essence_id] = row
    _validate_rules(rules)
    return ActionData(bases, mods, bench, essences, rules)


def prepare_roll(
    action: str,
    item: ItemState,
    data: ActionData,
    labels: Mapping[str, str] | None = None,
    *,
    essence_id: str | None = None,
) -> RollScenario:
    """Resolve the candidate pool and terminal draw setup for a draw action."""
    _validate_action_data(data)
    _validate_item(item, data)
    checked_labels = _validate_labels(labels)
    if action not in _DRAW_ACTIONS:
        _action_error(action)
    if action == "essence":
        return _prepare_essence(item, data, checked_labels, essence_id)
    if essence_id is not None:
        raise ValueError("essence_id is only valid for essence")
    if action == "transmute":
        _require_rarity(item, _NORMAL, action)
        return _reroll_scenario(item, data, checked_labels, _MAGIC, (), _count_weights(data, _MAGIC))
    if action == "alteration":
        _require_rarity(item, _MAGIC, action)
        return _reroll_scenario(item, data, checked_labels, _MAGIC, _retained_for_reroll(item), _count_weights(data, _MAGIC))
    if action == "alchemy":
        _require_rarity(item, _NORMAL, action)
        return _reroll_scenario(item, data, checked_labels, _RARE, (), _count_weights(data, _RARE))
    if action == "chaos":
        _require_rarity(item, _RARE, action)
        return _reroll_scenario(item, data, checked_labels, _RARE, _retained_for_reroll(item), _count_weights(data, _RARE))
    if action == "augmentation":
        _require_rarity(item, _MAGIC, action)
        return _addition_scenario(item, data, checked_labels, _MAGIC)
    if action == "regal":
        _require_rarity(item, _MAGIC, action)
        return _addition_scenario(item, data, checked_labels, _RARE)
    if action == "exalted":
        _require_rarity(item, _RARE, action)
        return _addition_scenario(item, data, checked_labels, _RARE)
    raise AssertionError("validated draw action was not dispatched")


def action_distribution(
    action: str,
    item: ItemState,
    data: ActionData,
    labels: Mapping[str, str] | None = None,
    *,
    essence_id: str | None = None,
    bench_index: int | None = None,
    harvest_tag: str | None = None,
    harvest_type_filter: str = "first_only",
    fossil_ids: tuple[int, ...] | list[int] | None = None,
    fossil_mode: str = "additive",
    socket_count: int | None = None,
) -> dict[OutcomeClass, float]:
    """Return terminal-only exact outcomes; do not use the projection for a later action."""
    checked_labels = _validate_labels(labels)
    if action in _DRAW_ACTIONS:
        if harvest_tag is not None or harvest_type_filter != "first_only":
            raise ValueError("harvest options are only valid for harvest_reforge")
        if bench_index is not None:
            raise ValueError("bench_index is only valid for bench")
        if fossil_ids is not None or fossil_mode != "additive" or socket_count is not None:
            raise ValueError("fossil options are only valid for fossil")
        scenario = prepare_roll(action, item, data, checked_labels, essence_id=essence_id)
        parts = []
        for draws, weight in scenario.draw_counts:
            parts.append((weight, draw_distribution(
                scenario.entries, draws, checked_labels,
                prefix_cap=scenario.prefix_cap, suffix_cap=scenario.suffix_cap,
                initial_prefixes=scenario.initial_prefixes, initial_suffixes=scenario.initial_suffixes,
                initial_labels=scenario.initial_labels, blocked_groups=scenario.blocked_groups,
            )))
        return mixture_distribution(parts)
    if action == "harvest_reforge":
        if essence_id is not None:
            raise ValueError("essence_id is only valid for essence")
        if bench_index is not None:
            raise ValueError("bench_index is only valid for bench")
        if fossil_ids is not None or fossil_mode != "additive" or socket_count is not None:
            raise ValueError("fossil options are only valid for fossil")
        if harvest_tag is None:
            raise ValueError("harvest_reforge requires harvest_tag")
        # Harvest imports ActionData from this module, so keep the adapter import local.
        from craftoracle.harvest import harvest_distribution
        return harvest_distribution(item, data, harvest_tag, checked_labels, type_filter=harvest_type_filter)
    if action == "fossil":
        if essence_id is not None:
            raise ValueError("essence_id is only valid for essence")
        if bench_index is not None:
            raise ValueError("bench_index is only valid for bench")
        if harvest_tag is not None or harvest_type_filter != "first_only":
            raise ValueError("harvest options are only valid for harvest_reforge")
        if fossil_ids is None:
            raise ValueError("fossil requires fossil_ids")
        from craftoracle.fossils import fossil_distribution
        return fossil_distribution(item, data, fossil_ids, checked_labels, mode=fossil_mode, socket_count=socket_count)
    if essence_id is not None:
        raise ValueError("essence_id is only valid for essence")
    if harvest_tag is not None or harvest_type_filter != "first_only":
        raise ValueError("harvest options are only valid for harvest_reforge")
    if fossil_ids is not None or fossil_mode != "additive" or socket_count is not None:
        raise ValueError("fossil options are only valid for fossil")
    _validate_action_data(data)
    _validate_item(item, data)
    if action == "annul":
        if bench_index is not None:
            raise ValueError("bench_index is only valid for bench")
        return _annul_distribution(item, data, checked_labels)
    if action == "scour":
        if bench_index is not None:
            raise ValueError("bench_index is only valid for bench")
        return _item_outcome(scour_item(item, data), checked_labels)
    if action == "bench":
        if bench_index is None:
            raise ValueError("bench requires bench_index")
        return _item_outcome(bench_item(item, data, bench_index), checked_labels)
    _action_error(action)
    raise AssertionError("unreachable")


def scour_item(item: ItemState, data: ActionData) -> ItemState:
    """Apply the deterministic Scouring transition without mutating ``item``."""
    _validate_action_data(data)
    _validate_item(item, data)
    if item.rarity == _NORMAL:
        raise ValueError("scour requires non-normal item")
    retained = _retained_for_reroll(item)
    prefixes, suffixes = _counts(retained)
    rarity = _NORMAL if not retained else _MAGIC if prefixes <= 1 and suffixes <= 1 else _RARE
    return _replace_item(item, rarity, retained)


def bench_item(item: ItemState, data: ActionData, bench_index: int) -> ItemState:
    """Apply one deterministic bench craft with its exact ``bench:<index>`` identity."""
    _validate_action_data(data)
    _validate_item(item, data)
    if isinstance(bench_index, bool) or not isinstance(bench_index, int) or bench_index not in data.bench:
        raise ValueError(f"unknown bench source_index: {bench_index}")
    row = data.bench[bench_index]
    base = _base_for(item, data)
    if base["type"] not in row["types"] or row["types"][base["type"]] is not True:
        raise ValueError(f"bench {bench_index} does not support base type {base['type']}")
    if any(mod.group == row["group"] for mod in item.mods):
        raise ValueError("bench group conflicts with an existing modifier")
    rarity = _MAGIC if item.rarity == _NORMAL else item.rarity
    cap = _caps(data, rarity)
    prefixes, suffixes = _counts(item.mods)
    current = prefixes if row["type"] == "Prefix" else suffixes
    side_cap = cap[0] if row["type"] == "Prefix" else cap[1]
    if current >= side_cap:
        raise ValueError("bench side is full")
    crafted = [mod for mod in item.mods if _is_bench(mod)]
    allowance = 3 if any(mod.group == _MULTIMOD for mod in crafted) else 1
    if len(crafted) >= allowance:
        raise ValueError("crafted modifier allowance is full")
    new_mod = ModRef(f"bench:{bench_index}", row["type"], row["group"])
    return _replace_item(item, rarity, (*item.mods, new_mod))


def _reroll_scenario(item, data, labels, rarity, retained, count_weights) -> RollScenario:
    cap = _caps(data, rarity)
    prefix_count, suffix_count = _counts(retained)
    entries = _candidate_entries(item, data, retained, _meta_flags(retained), None)
    blocked = tuple(mod.group for mod in retained)
    draw_counts = tuple((max(0, target - len(retained)), weight) for target, weight in count_weights)
    return RollScenario(entries, draw_counts, cap[0], cap[1], prefix_count, suffix_count, _labels_for(retained, labels), blocked)


def _addition_scenario(item, data, labels, resulting_rarity) -> RollScenario:
    cap = _caps(data, resulting_rarity)
    prefixes, suffixes = _counts(item.mods)
    if prefixes >= cap[0] and suffixes >= cap[1]:
        raise ValueError("item is full")
    entries = _candidate_entries(item, data, item.mods, _meta_flags(item.mods), None)
    entries = tuple(
        entry for entry in entries
        if (entry.type == "Prefix" and prefixes < cap[0])
        or (entry.type == "Suffix" and suffixes < cap[1])
    )
    if not entries:
        raise ValueError("no eligible modifier can be added")
    return RollScenario(entries, ((1, 1),), cap[0], cap[1], prefixes, suffixes, _labels_for(item.mods, labels), tuple(mod.group for mod in item.mods))


def _prepare_essence(item, data, labels, essence_id) -> RollScenario:
    essence = _essence_for(essence_id, data)
    tier = essence["tier"]
    if tier == 8:
        raise NotImplementedError("unsourced: Q12")
    if item.rarity == _MAGIC or item.rarity not in {_NORMAL, _RARE}:
        raise ValueError("essence requires normal, or rare at tier 5+")
    if item.rarity == _RARE and tier < 5:
        raise ValueError("essence tier 1-4 cannot reforge a rare item")
    if any(mod.group in {_LOCK_PREFIXES, _LOCK_SUFFIXES, _NO_ATTACK, _NO_CASTER} for mod in item.mods):
        raise ValueError("outcome-affecting metamod prevents essence use")
    base = _base_for(item, data)
    try:
        forced_id = essence["mods"][base["type"]]
        forced_row = data.mods[forced_id]
    except KeyError as error:
        raise ValueError("essence has no mapped ordinary modifier for this base") from error
    forced = _mod_ref_from_row(forced_id, forced_row)
    cap = _caps(data, _RARE)
    level_cap = _ESSENCE_LEVEL_CAPS.get(tier)
    entries = _candidate_entries(item, data, (forced,), (False, False), level_cap)
    labels_forced = _labels_for((forced,), labels)
    prefixes, suffixes = _counts((forced,))
    return RollScenario(
        entries, tuple((max(0, target - 1), weight) for target, weight in _count_weights(data, _RARE)),
        cap[0], cap[1], prefixes, suffixes, labels_forced, (forced.group,),
    )


def _annul_distribution(item, data, labels):
    if item.rarity == _NORMAL:
        raise ValueError("annul requires non-normal item")
    attack_block, caster_block = _meta_flags(item.mods)
    protected_prefixes = any(mod.group == _LOCK_PREFIXES for mod in item.mods)
    protected_suffixes = any(mod.group == _LOCK_SUFFIXES for mod in item.mods)
    candidates = []
    for mod in item.mods:
        if (mod.type == "Prefix" and protected_prefixes) or (mod.type == "Suffix" and protected_suffixes):
            continue
        row = _row_for(mod, data)
        tags = row.get("modTags") or []
        if attack_block and "attack" in tags or caster_block and "caster" in tags:
            continue
        candidates.append(mod)
    if not candidates:
        raise ValueError("annul has no eligible modifier")
    result: dict[OutcomeClass, float] = {}
    for removed in candidates:
        remaining = tuple(mod for mod in item.mods if mod != removed)
        outcome = next(iter(_item_outcome(_replace_item(item, item.rarity, remaining), labels)))
        result[outcome] = result.get(outcome, 0.0) + 1.0 / len(candidates)
    return result


def _item_outcome(item, labels):
    prefixes, suffixes = _counts(item.mods)
    return {OutcomeClass(_labels_for(item.mods, labels), prefixes, suffixes): 1.0}


def _candidate_entries(item, data, existing, flags, level_cap):
    # Start from an empty rare item so bench refs do not enter item_model validation.
    empty = ItemState(item.base_name, item.item_level, _RARE, corrupted=item.corrupted, influenced=item.influenced,
                      fractured=item.fractured, synthesised=item.synthesised, mirrored=item.mirrored, split=item.split)
    entries = []
    attack_block, caster_block = flags
    blocked = {mod.group for mod in existing}
    for candidate in resolve_pool(empty, data.bases, data.mods):
        row = data.mods[candidate.mod_id]
        tags = row.get("modTags") or []
        if candidate.group in blocked or (level_cap is not None and candidate.level > level_cap):
            continue
        if attack_block and "attack" in tags or caster_block and "caster" in tags:
            continue
        entries.append(DrawEntry(candidate.mod_id, candidate.type, candidate.group, candidate.weight))
    return tuple(entries)


def _retained_for_reroll(item):
    lock_prefixes = any(mod.group == _LOCK_PREFIXES for mod in item.mods)
    lock_suffixes = any(mod.group == _LOCK_SUFFIXES for mod in item.mods)
    return tuple(mod for mod in item.mods if (lock_prefixes and mod.type == "Prefix") or (lock_suffixes and mod.type == "Suffix"))


def _meta_flags(mods):
    groups = {mod.group for mod in mods}
    return _NO_ATTACK in groups, _NO_CASTER in groups


def _validate_item(item, data):
    if not isinstance(item, ItemState):
        raise ValueError("item must be an ItemState")
    if any((item.corrupted, item.influenced, item.fractured, item.synthesised, item.mirrored, item.split)):
        raise NotImplementedError(_Q9_ERROR)
    if item.rarity not in {_NORMAL, _MAGIC, _RARE}:
        raise ValueError(f"invalid rarity: {item.rarity}")
    base = _base_for(item, data)
    if isinstance(item.item_level, bool) or not isinstance(item.item_level, int) or item.item_level <= 0:
        raise ValueError("item level must be a positive integer")
    seen_groups = set()
    seen_ids = set()
    for mod in item.mods:
        if not isinstance(mod, ModRef):
            raise ValueError("existing modifiers must be ModRef values")
        if mod.id in seen_ids or mod.group in seen_groups:
            raise ValueError("duplicate existing modifier id or group")
        row = _row_for(mod, data)
        if mod.type != row["type"] or mod.group != row["group"]:
            raise ValueError(f"existing mod ref differs from source row: {mod.id}")
        if _is_bench(mod) and row["types"].get(base["type"]) is not True:
            raise ValueError(f"existing bench modifier does not support base type {base['type']}")
        seen_ids.add(mod.id)
        seen_groups.add(mod.group)
    prefixes, suffixes = _counts(item.mods)
    cap = _caps(data, item.rarity)
    if prefixes > cap[0] or suffixes > cap[1]:
        raise ValueError(f"existing mods exceed {item.rarity} side cap")
    crafted = [mod for mod in item.mods if _is_bench(mod)]
    allowance = 3 if any(mod.group == _MULTIMOD for mod in crafted) else 1
    if len(crafted) > allowance:
        raise ValueError("existing crafted modifiers exceed allowance")


def _row_for(mod, data):
    if _is_bench(mod):
        try:
            index = int(mod.id.removeprefix("bench:"))
        except ValueError as error:
            raise ValueError(f"invalid bench modifier identity: {mod.id}") from error
        if f"bench:{index}" != mod.id or index not in data.bench:
            raise ValueError(f"unknown bench modifier identity: {mod.id}")
        return data.bench[index]
    if mod.id not in data.mods:
        raise ValueError(f"unknown mod id: {mod.id}")
    return data.mods[mod.id]


def _essence_for(essence_id, data):
    if not isinstance(essence_id, str):
        raise ValueError(f"unknown essence id: {essence_id}")
    row = data.essences.get(essence_id)
    if row is not None:
        return row
    matches = [row for key, row in data.essences.items() if key.rsplit("/", 1)[-1] == essence_id]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"unknown essence id: {essence_id}")


def _is_bench(mod):
    return isinstance(mod.id, str) and mod.id.startswith("bench:")


def _base_for(item, data):
    base = data.bases.get(item.base_name)
    if not isinstance(base, dict):
        occurrences = {
            id(row)
            for key, row in data.bases.items()
            if isinstance(key, str) and "@" in key and isinstance(row, dict) and row.get("name") == item.base_name
        }
        if occurrences:
            raise ValueError(f"ambiguous base name: {item.base_name}")
        raise ValueError(f"unknown base: {item.base_name}")
    if not isinstance(base.get("type"), str):
        raise ValueError(f"malformed base row for {item.base_name}")
    return base


def _caps(data, rarity):
    key = "magic_caps" if rarity == _MAGIC else "rare_caps" if rarity == _RARE else None
    if key is None:
        return (0, 0)
    caps = data.rules[key]
    return caps[0], caps[1]


def _count_weights(data, rarity):
    source = data.rules["magic_count_weights" if rarity == _MAGIC else "rare_count_weights"]
    return tuple((int(count), weight) for count, weight in source.items())


def _counts(mods):
    return sum(mod.type == "Prefix" for mod in mods), sum(mod.type == "Suffix" for mod in mods)


def _labels_for(mods, labels):
    return tuple(sorted(labels[mod.id] for mod in mods if mod.id in labels))


def _replace_item(item, rarity, mods):
    return ItemState(item.base_name, item.item_level, rarity, tuple(mods), item.corrupted, item.influenced,
                     item.fractured, item.synthesised, item.mirrored, item.split)


def _mod_ref_from_row(mod_id, row):
    return ModRef(mod_id, row["type"], row["group"])


def _require_rarity(item, rarity, action):
    if item.rarity != rarity:
        raise ValueError(f"{action} requires {rarity} item")


def _action_error(action):
    if action in _BLOCKED_ACTIONS:
        raise NotImplementedError(f"unsourced: {_BLOCKED_ACTIONS[action]}")
    raise ValueError(f"unknown action: {action}")


def _validate_labels(labels):
    if labels is None:
        return {}
    if not isinstance(labels, Mapping) or not all(isinstance(key, str) and isinstance(value, str) for key, value in labels.items()):
        raise ValueError("labels must map string modifier ids to strings")
    return labels


def _json_object(path, name):
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"unable to load {name} JSON: {path}") from error
    if not isinstance(doc, dict):
        raise ValueError(f"malformed {name} JSON")
    return doc


def _required_rows(doc, key):
    rows = doc.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"malformed JSON: {key} must be a list")
    return rows


def _validate_bench_row(row):
    if not isinstance(row, dict) or isinstance(row.get("source_index"), bool) or not isinstance(row.get("source_index"), int):
        raise ValueError("malformed bench row")
    if row.get("type") not in {"Prefix", "Suffix"} or not isinstance(row.get("group"), str) or not isinstance(row.get("types"), dict):
        raise ValueError("malformed bench row")


def _validate_essence_row(row):
    if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("mods"), dict):
        raise ValueError("malformed essence row")
    if isinstance(row.get("tier"), bool) or not isinstance(row.get("tier"), int) or row["tier"] < 1:
        raise ValueError("malformed essence row")


def _validate_rules(rules):
    if not isinstance(rules, dict):
        raise ValueError("malformed ordinary rules")
    for cap_key in ("magic_caps", "rare_caps"):
        caps = rules.get(cap_key)
        if not isinstance(caps, list) or len(caps) != 2 or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in caps):
            raise ValueError(f"malformed ordinary rules: {cap_key}")
    for count_key in ("magic_count_weights", "rare_count_weights"):
        weights = rules.get(count_key)
        if not isinstance(weights, dict) or not weights:
            raise ValueError(f"malformed ordinary rules: {count_key}")
        for count, weight in weights.items():
            if not isinstance(count, str) or not count.isdecimal() or int(count) < 1 or isinstance(weight, bool) or not isinstance(weight, int) or weight <= 0:
                raise ValueError(f"malformed ordinary rules: {count_key}")


def _validate_action_data(data):
    if not isinstance(data, ActionData):
        raise ValueError("data must be ActionData")
    _validate_rules(data.rules)
