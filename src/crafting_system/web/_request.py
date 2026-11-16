"""A request of the website: what a user asks (a target, the method switches, his settings), checked, and its canonical key.

The body of `POST /api/v1/<game>/jobs` is a JSON object:

    {"target": {...},                                   # the target as a JSON object, with the keys of a target file (`targets`)
     "methods": {"recipe_starts": true, "strands": false},   # optional: the method switches the planner has today
     "settings": {"start_price": null, "price_source": "both"}}  # optional: the user's settings

A missing switch or setting is the machine's planner setting (`crafting.toml`, `Config`). Unknown keys are refused, so a key added later
(the economy modes of #323, more method switches) never changes what an older request meant. The prices are the site's snapshot, so a
target may not name a `price_file`.

The **key** of a request is the SHA-256 of one canonical JSON text: the game, the target's canonical form (`target_form`: the parsed
target, so two spellings of one item are one key, #966), the method switches and settings with their defaults filled in, the planner settings of the machine that change an answer (the proof gap, the time and memory nets, the imprint
cap, the recombinator variant), the price snapshot, the game data version and the planner version. Two requests with the same key get the
same plan, so the second is answered from the store (OR-36). The calendar day is not in it: the site judges a price's age on the day its
snapshot was fetched (`World.price_day`), which the snapshot's identity already holds, so a route is reused for as long as its snapshot
stands, on any day.
"""

import dataclasses
import enum
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from crafting_system.config import PRICE_SOURCES
from crafting_system.targets import EnchantmentRequirement, ImplicitRequirement, KOfN, Requirement, Target, TargetError, parse_target

from ._world import World

_TOP_KEYS = ("target", "methods", "settings")
_METHOD_KEYS = ("recipe_starts", "strands")
_SETTING_KEYS = ("start_price", "price_source")


class RequestError(ValueError):
    """The request cannot be planned as written; the text says what is wrong in the user's words."""


@dataclass(frozen=True)
class Request:
    """A checked request: the target parsed, every switch and setting filled in, and its key. `document` is what the store keeps."""

    game: str
    target: Target
    document: dict
    key: str


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


# the fields that only say how the owner wrote a selector: what it counts is in `mod_ids`, which the planner reads (`targets.model`)
_SPELLING_FIELDS = {Requirement: ("family", "stat"), ImplicitRequirement: ("family", "stat"), EnchantmentRequirement: ("entries",)}
# the lists whose order says nothing: every entry is required at once (`Target`), or `at_least` of the members (`KOfN`)
_UNORDERED_FIELDS = {Target: ("requirements", "implicits"), KOfN: ("of",)}


def _form(value: object) -> object:
    """The JSON form of a parsed value: a dataclass as its type and fields (less the spelling ones), a set sorted, an enum by its value."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        kind = type(value)
        dropped = _SPELLING_FIELDS.get(kind, ())
        unordered = _UNORDERED_FIELDS.get(kind, ())
        form: dict[str, object] = {"type": kind.__name__}
        for field in dataclasses.fields(value):
            if field.name in dropped:
                continue
            entry = _form(getattr(value, field.name))
            form[field.name] = sorted(entry, key=_canonical) if field.name in unordered and isinstance(entry, list) else entry
        return form
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (frozenset, set)):
        return sorted((_form(entry) for entry in value), key=_canonical)
    if isinstance(value, (tuple, list)):
        return [_form(entry) for entry in value]
    if isinstance(value, dict):
        return {str(name): _form(entry) for name, entry in value.items()}
    if isinstance(value, Path):
        return value.as_posix()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"a target holds a {type(value).__name__}, which its canonical form does not know")  # a new field type is said, never keyed by repr


def target_form(target: Target) -> dict:
    """The canonical form of a parsed target, as it goes into a request's key (#966): what the planner reads, not how it was written. A stat
    text and the family id it stands for, a key spelled out at its default or left out, and the order of the required entries give one
    form; the item asked and the start item are all in it."""
    return _form(target)  # type: ignore[return-value]


def _object(value: object, where: str, allowed: tuple[str, ...]) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RequestError(f"{where} must be a JSON object")
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise RequestError(f"{where} has unknown keys {unknown}; the known ones are {list(allowed)}")
    return value


def _switch(value: object, where: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise RequestError(f"{where} must be true or false")
    return value


def _chaos_or_none(value: object, where: str) -> float | None:
    """A price the user gives: a finite number of Chaos above zero (a price of 0 is never "free", #505), or None to read the snapshot."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not value > 0:
        raise RequestError(f"{where} must be a number of Chaos above zero, or null to read the price snapshot")
    return float(value)


def parse_request(body: object, game: str, world: World) -> Request:
    """Check `body` against `world` and give the request with its key; raises `RequestError` with what is wrong."""
    top = _object(body, "the request", _TOP_KEYS)
    if not isinstance(top.get("target"), dict):
        raise RequestError("the request must hold the target as a JSON object under \"target\"")
    target_object = top["target"]
    if "price_file" in target_object:
        raise RequestError("target.price_file: the site prices every request with its own price snapshot; leave the key out")
    methods = _object(top.get("methods"), "methods", _METHOD_KEYS)
    settings = _object(top.get("settings"), "settings", _SETTING_KEYS)
    config = world.config

    start_price = _chaos_or_none(settings.get("start_price"), "settings.start_price")
    price_source = settings.get("price_source", config.price_source)
    if price_source not in PRICE_SOURCES:
        raise RequestError(f"settings.price_source must be one of {list(PRICE_SOURCES)}")

    try:
        target = parse_target(json.dumps(target_object, indent=2, ensure_ascii=False), world.data, source="target")
    except TargetError as problem:
        raise RequestError(str(problem)) from None

    document = {
        "target": target_object,
        "methods": {
            "recipe_starts": _switch(methods.get("recipe_starts"), "methods.recipe_starts", config.recipe_starts),
            "strands": _switch(methods.get("strands"), "methods.strands", config.memory_strands),
        },
        "settings": {"start_price": start_price, "price_source": price_source},
    }
    keyed = {"game": game, "target": target_form(target), "methods": document["methods"], "settings": document["settings"], "machine": world.machine, "prices": world.price_snapshot, "data": world.data.version, "planner": world.planner_version}
    return Request(game, target, document, hashlib.sha256(_canonical(keyed).encode("utf-8")).hexdigest())
