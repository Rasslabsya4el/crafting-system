"""Raw repoe-fork JSON (already parsed) into the typed model, with strict validation.

The functions here take parsed JSON and touch no file or network, so tests feed them excerpts.
A missing key, a value of the wrong type (a `bool` is not an int, a string weight is wrong) or
a record that is not an object raises `RawFormatError` naming the record (its id, or its
position for the bench options) and the field. Extra raw keys are ignored: repoe-fork adds
some now and then, and the model keeps only what the project reads.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from .errors import RawFormatError
from .model import (
    BaseItem,
    BenchActions,
    BenchOption,
    CostEntry,
    Essence,
    EssenceMod,
    Fossil,
    GameData,
    Mod,
    StatRange,
    Weight,
)

MODS_FILE = "mods.json"
BASE_ITEMS_FILE = "base_items.json"
FOSSILS_FILE = "fossils.json"
ESSENCES_FILE = "essences.json"
BENCH_OPTIONS_FILE = "crafting_bench_options.json"


def _describe(value: Any) -> str:
    text = repr(value)
    if len(text) > 60:
        text = text[:57] + "..."
    return f"{type(value).__name__} {text}"


def _bad(where: str, field: str, expected: str, value: Any) -> RawFormatError:
    return RawFormatError(f"{where}: field {field!r} must be {expected}, got {_describe(value)}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _raw(record: Mapping, key: str, where: str, path: str) -> Any:
    if key not in record:
        raise RawFormatError(f"{where}: missing field {path + key!r}")
    return record[key]


def _str(record: Mapping, key: str, where: str, path: str = "") -> str:
    value = _raw(record, key, where, path)
    if not isinstance(value, str):
        raise _bad(where, path + key, "a string", value)
    return value


def _opt_str(record: Mapping, key: str, where: str, path: str = "") -> str | None:
    value = _raw(record, key, where, path)
    if value is not None and not isinstance(value, str):
        raise _bad(where, path + key, "a string or null", value)
    return value


def _int(record: Mapping, key: str, where: str, path: str = "") -> int:
    value = _raw(record, key, where, path)
    if not _is_int(value):
        raise _bad(where, path + key, "an integer", value)
    return value


def _opt_int(record: Mapping, key: str, where: str, path: str = "") -> int | None:
    value = _raw(record, key, where, path)
    if value is not None and not _is_int(value):
        raise _bad(where, path + key, "an integer or null", value)
    return value


def _bool(record: Mapping, key: str, where: str, path: str = "") -> bool:
    value = _raw(record, key, where, path)
    if not isinstance(value, bool):
        raise _bad(where, path + key, "true or false", value)
    return value


def _opt_bool(record: Mapping, key: str, where: str, path: str = "") -> bool | None:
    value = _raw(record, key, where, path)
    if value is not None and not isinstance(value, bool):
        raise _bad(where, path + key, "true, false or null", value)
    return value


def _object(record: Mapping, key: str, where: str, path: str = "") -> Mapping:
    value = _raw(record, key, where, path)
    if not isinstance(value, dict):
        raise _bad(where, path + key, "an object", value)
    return value


def _list(record: Mapping, key: str, where: str) -> list:
    value = _raw(record, key, where, "")
    if not isinstance(value, list):
        raise _bad(where, key, "a list", value)
    return value


def _str_tuple(record: Mapping, key: str, where: str) -> tuple[str, ...]:
    items = _list(record, key, where)
    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise _bad(where, f"{key}[{index}]", "a string", item)
    return tuple(items)


def _items(record: Mapping, key: str, where: str, expected: str) -> list[tuple[str, Mapping]]:
    """The elements of a list field, each checked to be an object, with the path used in messages."""
    items = _list(record, key, where)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise _bad(where, f"{key}[{index}]", expected, item)
    return [(f"{key}[{index}].", item) for index, item in enumerate(items)]


def _weights(record: Mapping, key: str, where: str) -> tuple[Weight, ...]:
    return tuple(
        Weight(_str(item, "tag", where, path), _int(item, "weight", where, path))
        for path, item in _items(record, key, where, "an object with tag and weight")
    )


def _records(raw: Any, file: str, kind: str) -> list[tuple[str, str, Mapping]]:
    """(id, `where` text for messages, record) of every record of a file that is an object keyed by id."""
    if not isinstance(raw, dict):
        raise RawFormatError(f"{file}: must be an object of {kind} records keyed by id, got {_describe(raw)}")
    found = []
    for record_id, record in raw.items():
        where = f"{file} {kind} {record_id!r}"
        if not isinstance(record, dict):
            raise RawFormatError(f"{where}: the record must be an object, got {_describe(record)}")
        found.append((record_id, where, record))
    return found


def normalize_mods(raw: Any) -> Mapping[str, Mod]:
    mods = {}
    for mod_id, where, record in _records(raw, MODS_FILE, "mod"):
        mods[mod_id] = Mod(
            id=mod_id,
            name=_str(record, "name", where),
            text=_opt_str(record, "text", where),
            type=_str(record, "type", where),
            families=_str_tuple(record, "groups", where),
            domain=_str(record, "domain", where),
            generation_type=_str(record, "generation_type", where),
            required_level=_int(record, "required_level", where),
            spawn_weights=_weights(record, "spawn_weights", where),
            generation_weights=_weights(record, "generation_weights", where),
            adds_tags=_str_tuple(record, "adds_tags", where),
            implicit_tags=_str_tuple(record, "implicit_tags", where),
            stats=tuple(
                StatRange(
                    _str(stat, "id", where, path),
                    _int(stat, "min", where, path),
                    _int(stat, "max", where, path),
                )
                for path, stat in _items(record, "stats", where, "an object with id, min and max")
            ),
            is_essence_only=_bool(record, "is_essence_only", where),
        )
    return MappingProxyType(mods)


def normalize_base_items(raw: Any) -> Mapping[str, BaseItem]:
    bases = {}
    for base_id, where, record in _records(raw, BASE_ITEMS_FILE, "base item"):
        bases[base_id] = BaseItem(
            id=base_id,
            name=_str(record, "name", where),
            item_class=_str(record, "item_class", where),
            domain=_str(record, "domain", where),
            drop_level=_int(record, "drop_level", where),
            tags=_str_tuple(record, "tags", where),
            implicits=_str_tuple(record, "implicits", where),
            release_state=_str(record, "release_state", where),
        )
    return MappingProxyType(bases)


def normalize_fossils(raw: Any) -> Mapping[str, Fossil]:
    fossils = {}
    for fossil_id, where, record in _records(raw, FOSSILS_FILE, "fossil"):
        fossils[fossil_id] = Fossil(
            id=fossil_id,
            name=_str(record, "name", where),
            added_mods=_str_tuple(record, "added_mods", where),
            forced_mods=_str_tuple(record, "forced_mods", where),
            allowed_tags=_str_tuple(record, "allowed_tags", where),
            forbidden_tags=_str_tuple(record, "forbidden_tags", where),
            positive_mod_weights=_weights(record, "positive_mod_weights", where),
            negative_mod_weights=_weights(record, "negative_mod_weights", where),
            changes_quality=_bool(record, "changes_quality", where),
            rolls_lucky=_bool(record, "rolls_lucky", where),
            rolls_white_sockets=_bool(record, "rolls_white_sockets", where),
            mirrors=_bool(record, "mirrors", where),
            corrupted_essence_chance=_int(record, "corrupted_essence_chance", where),
        )
    return MappingProxyType(fossils)


def normalize_essences(raw: Any) -> Mapping[str, Essence]:
    essences = {}
    for essence_id, where, record in _records(raw, ESSENCES_FILE, "essence"):
        kind = _object(record, "type", where)
        raw_mods = _object(record, "mods", where)
        for item_class, mod_id in raw_mods.items():
            if mod_id is not None and not isinstance(mod_id, str):
                raise _bad(where, f"mods[{item_class!r}]", "a mod id string or null", mod_id)
        essences[essence_id] = Essence(
            id=essence_id,
            name=_str(record, "name", where),
            tier=_int(kind, "tier", where, "type."),
            is_corruption_only=_bool(kind, "is_corruption_only", where, "type."),
            level=_int(record, "level", where),
            item_level_restriction=_opt_int(record, "item_level_restriction", where),
            spawn_level_min=_int(record, "spawn_level_min", where),
            mods=tuple(EssenceMod(item_class, mod_id) for item_class, mod_id in raw_mods.items()),
        )
    return MappingProxyType(essences)


def normalize_bench_options(raw: Any) -> tuple[BenchOption, ...]:
    if not isinstance(raw, list):
        raise RawFormatError(f"{BENCH_OPTIONS_FILE}: must be a list of bench options, got {_describe(raw)}")
    options = []
    for index, record in enumerate(raw):
        where = f"{BENCH_OPTIONS_FILE} bench option #{index}"
        if not isinstance(record, dict):
            raise RawFormatError(f"{where}: the record must be an object, got {_describe(record)}")
        actions = _object(record, "actions", where)
        raw_cost = _object(record, "cost", where)
        for item_id, count in raw_cost.items():
            if not _is_int(count):
                raise _bad(where, f"cost[{item_id!r}]", "an integer count", count)
        options.append(
            BenchOption(
                master=_str(record, "master", where),
                bench_tier=_int(record, "bench_tier", where),
                item_classes=_str_tuple(record, "item_classes", where),
                cost=tuple(CostEntry(item_id, count) for item_id, count in raw_cost.items()),
                actions=BenchActions(
                    add_explicit_mod=_opt_str(actions, "add_explicit_mod", where, "actions."),
                    add_enchant_mod=_opt_str(actions, "add_enchant_mod", where, "actions."),
                    change_socket_count=_opt_int(actions, "change_socket_count", where, "actions."),
                    link_sockets=_opt_int(actions, "link_sockets", where, "actions."),
                    color_sockets=_opt_str(actions, "color_sockets", where, "actions."),
                    remove_crafted_mods=_opt_bool(actions, "remove_crafted_mods", where, "actions."),
                    remove_enchantments=_opt_bool(actions, "remove_enchantments", where, "actions."),
                    reroll_rarity=_opt_bool(actions, "reroll_rarity", where, "actions."),
                    reroll_rare_mods=_opt_int(actions, "reroll_rare_mods", where, "actions."),
                ),
            )
        )
    return tuple(options)


def normalize_game_data(
    raw_mods: Any,
    raw_base_items: Any,
    raw_fossils: Any,
    raw_essences: Any,
    raw_bench_options: Any,
    *,
    version: str,
) -> GameData:
    """All five raw files (parsed JSON) into one `GameData` labelled with the pin's `version`."""
    return GameData(
        version=version,
        mods=normalize_mods(raw_mods),
        base_items=normalize_base_items(raw_base_items),
        fossils=normalize_fossils(raw_fossils),
        essences=normalize_essences(raw_essences),
        bench_options=normalize_bench_options(raw_bench_options),
    )
