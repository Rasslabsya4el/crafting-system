# Adapted from PoEQuery `official_api_query.py` (https://github.com/NickRyder/PoEQuery), MIT,
# (c) 2021 Nick Ryder; the licence is in `third_party/PoEQuery-LICENSE.txt`.
"""The trade-site search query for buy actions (#39): the query model, its JSON body and the buy spec.

`TradeQuery` is the body of `POST /api/trade/search/{league}`. Equal queries give equal
`json.dumps(body, sort_keys=True)`, so the body (with the league) is a usable cache key
(`query_hash`). A `BuySpec` says what the owner wants to buy (the same shape as the start item of a
target file); `build_query` turns it, with the mods already resolved to trade stat ids by
`trade_stats`, into a `TradeQuery`. Nothing here talks to the network.

Differences from PoEQuery: frozen, typed dataclasses; `ilvl_max` writes `max` (PoEQuery wrote
`min`); no `sale_type`, so listings without a price are dropped later, on our side.

Filter coverage, against Awakened PoE Trade's `TradeRequest` (renderer `pathofexile-trade.ts`).
"Set" means this query can write it; "not covered" filters are not needed to price a rare
equipment piece bought for its mods, and each one would also widen the query hash space for no gain.

    Trade filter                                  This query    Note
    --------------------------------------------  ------------  -----------------------------------
    status                                        set           online / securable / available / any
    type (base type)                              set           `query.type`
    name (uniques)                                not covered   rare items have no name to buy by
    stats, group type "and"                       set           one group; filters sorted
    stats, groups "if" / "count" / "not" /        not covered   a buy spec is a plain AND of mods
      "mercenary"
    type_filters.rarity, .category                set
    misc_filters.ilvl (min and max)               set
    misc_filters.corrupted, .mirrored             set           both written explicitly
    misc_filters.fractured_item                   set           iff a spec mod is fractured
    misc_filters.quality, .gem_level, .gem_imbued,
      .stack_size, .memory_level, .foulborn_item,
      .vestigial, .identified, .split               not covered   not relevant to rare equipment
    socket_filters (links, white sockets)         not covered   the buy actions do not ask for sockets
    armour_filters, weapon_filters, map_filters   not covered   defence / damage rolls come from mods
    trade_filters (price, collapse, indexed)      not covered   price is read from the listings; the
                                                                query sorts by price ascending
    influence (APT: pseudo stats)                 set           `INFLUENCE_STAT_IDS`, minimum 1

PoEQuery's extra filters (`synthesised_item`, `identified`, `enchanted`, `crafted`, `quality`,
sockets and links by colour, `sale_type`, `indexed`, `alternate_art`, `talisman_tier`, ultimatum)
are left out for the same reason.
"""

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RARITIES = ("normal", "magic", "rare", "unique", "nonunique", "uniquefoil")
STATUSES = ("online", "securable", "available", "any")

INFLUENCE_STAT_IDS: Mapping[str, str] = {
    name: f"pseudo.pseudo_has_{name}_influence"
    for name in ("shaper", "elder", "crusader", "hunter", "redeemer", "warlord")
}


class TradeSpecError(ValueError):
    """A buy spec or a query that cannot be built."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _check_number(what: str, value: Any) -> None:
    """`value` is a finite number (not a bool), or this raises."""
    if not _is_number(value) or not math.isfinite(value):
        raise TradeSpecError(f"{what} must be a finite number, got {value!r}")


def _json_number(value: float) -> int | float:
    """An integral number as an int, so 30 and 30.0 give one body and one hash."""
    return int(value) if float(value).is_integer() else float(value)


def _check_level(what: str, value: Any) -> None:
    if value is not None and not _is_int(value):
        raise TradeSpecError(f"{what} must be a whole number, got {value!r}")


def _check_range(what: str, low: Any, high: Any) -> None:
    if low is not None and high is not None and low > high:
        raise TradeSpecError(f"{what}: minimum {low} is above maximum {high}")


def _check_rarity(rarity: Any) -> None:
    if rarity not in RARITIES:
        raise TradeSpecError(f"rarity must be one of {', '.join(RARITIES)}, got {rarity!r}")


def _bool_option(value: bool) -> dict[str, str]:
    return {"option": "true" if value else "false"}


@dataclass(frozen=True)
class StatFilter:
    """One stat filter: a trade stat id with an optional minimum and maximum."""

    id: str
    min: float | None = None
    max: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise TradeSpecError(f"a stat filter needs a stat id, got {self.id!r}")
        for what, value in (("minimum", self.min), ("maximum", self.max)):
            if value is not None:
                _check_number(f"stat filter {self.id}: {what}", value)
        _check_range(f"stat filter {self.id}", self.min, self.max)

    def to_json(self) -> dict[str, Any]:
        found: dict[str, Any] = {"id": self.id, "disabled": False}
        value = {}
        if self.min is not None:
            value["min"] = _json_number(self.min)
        if self.max is not None:
            value["max"] = _json_number(self.max)
        if value:
            found["value"] = value
        return found


@dataclass(frozen=True)
class TradeQuery:
    """The body of a trade search. `type` is the base type name, `category` e.g. "accessory.amulet"."""

    type: str | None = None
    category: str | None = None
    rarity: str | None = None
    ilvl_min: int | None = None
    ilvl_max: int | None = None
    corrupted: bool | None = None
    mirrored: bool | None = None
    fractured: bool | None = None
    stats: tuple[StatFilter, ...] = field(default_factory=tuple)
    status: str = "available"

    def __post_init__(self) -> None:
        if self.rarity is not None:
            _check_rarity(self.rarity)
        if self.status not in STATUSES:
            raise TradeSpecError(f"status must be one of {', '.join(STATUSES)}, got {self.status!r}")
        _check_level("item level minimum", self.ilvl_min)
        _check_level("item level maximum", self.ilvl_max)
        _check_range("item level", self.ilvl_min, self.ilvl_max)

    def _type_filters(self) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if self.rarity is not None:
            filters["rarity"] = {"option": self.rarity}
        if self.category is not None:
            filters["category"] = {"option": self.category}
        return filters

    def _misc_filters(self) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        level = {}
        if self.ilvl_min is not None:
            level["min"] = self.ilvl_min
        if self.ilvl_max is not None:
            level["max"] = self.ilvl_max
        if level:
            filters["ilvl"] = level
        for key, value in (
            ("corrupted", self.corrupted),
            ("mirrored", self.mirrored),
            ("fractured_item", self.fractured),
        ):
            if value is not None:
                filters[key] = _bool_option(value)
        return filters

    def body(self) -> dict[str, Any]:
        """The JSON body of `POST /api/trade/search/{league}`; deterministic."""
        stat_filters = sorted(
            (stat.to_json() for stat in self.stats), key=lambda found: json.dumps(found, sort_keys=True)
        )
        query: dict[str, Any] = {
            "status": {"option": self.status},
            "stats": [{"type": "and", "filters": stat_filters}],
        }
        filters = {}
        for group, content in (
            ("type_filters", self._type_filters()),
            ("misc_filters", self._misc_filters()),
        ):
            if content:
                filters[group] = {"filters": content}
        if filters:
            query["filters"] = filters
        if self.type is not None:
            query["type"] = self.type
        return {"query": query, "sort": {"price": "asc"}}


def query_hash(league: str, body: Mapping[str, Any]) -> str:
    """The cache key of a search: sha256 of the canonical JSON of the league and the body."""
    canonical = json.dumps(
        {"league": league, "body": body}, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BuyMod:
    """A mod the bought item must have. `stat` is a repoe family id or the English stat text."""

    stat: str
    minimum: float | None = None
    fractured: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.stat, str) or not self.stat.strip():
            raise TradeSpecError(f"a buy mod needs a stat, got {self.stat!r}")
        if self.minimum is not None:
            _check_number(f"buy mod {self.stat}: minimum", self.minimum)


@dataclass(frozen=True)
class BuySpec:
    """What to buy: an item with given mods that no aggregator prices."""

    name: str
    base_type: str | None = None
    category: str | None = None
    rarity: str = "rare"
    item_level_min: int | None = None
    item_level_max: int | None = None
    influences: tuple[str, ...] = ()
    corrupted: bool = False
    mods: tuple[BuyMod, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise TradeSpecError(f"a buy spec needs a name, got {self.name!r}")
        if self.base_type is None and self.category is None:
            raise TradeSpecError(f"buy spec {self.name!r} needs a base_type or a category")
        _check_rarity(self.rarity)
        unknown = [name for name in self.influences if name not in INFLUENCE_STAT_IDS]
        if unknown:
            raise TradeSpecError(
                f"buy spec {self.name!r}: unknown influence {', '.join(map(repr, unknown))}; "
                f"known: {', '.join(INFLUENCE_STAT_IDS)}"
            )
        if len(set(self.influences)) != len(self.influences):
            raise TradeSpecError(f"buy spec {self.name!r}: an influence is listed twice")
        _check_level("item_level_min", self.item_level_min)
        _check_level("item_level_max", self.item_level_max)
        _check_range("item level", self.item_level_min, self.item_level_max)


def build_query(spec: BuySpec, mod_filters: Sequence[StatFilter]) -> TradeQuery:
    """The query for a spec. `mod_filters` are the spec's mods already resolved to trade stat ids."""
    influence_filters = tuple(StatFilter(INFLUENCE_STAT_IDS[name], min=1) for name in spec.influences)
    return TradeQuery(
        type=spec.base_type,
        category=spec.category,
        rarity=spec.rarity,
        ilvl_min=spec.item_level_min,
        ilvl_max=spec.item_level_max,
        corrupted=spec.corrupted,
        mirrored=False,
        fractured=True if any(mod.fractured for mod in spec.mods) else None,
        stats=tuple(mod_filters) + influence_filters,
    )


_SPEC_KEYS = frozenset(
    {
        "name",
        "base_type",
        "category",
        "rarity",
        "item_level_min",
        "item_level_max",
        "influence",
        "corrupted",
        "mods",
    }
)
_MOD_KEYS = frozenset({"stat", "minimum", "fractured"})


def _field(
    record: Mapping[str, Any], key: str, where: str, kind: str, check, *, default: Any = None
) -> Any:
    if key not in record or record[key] is None:
        return default
    value = record[key]
    if not check(value):
        raise TradeSpecError(f"{where}: {key} must be {kind}, got {value!r}")
    return value


def _no_unknown_keys(record: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    for key in record:
        if key not in allowed:
            raise TradeSpecError(
                f"{where}: unknown key {key!r}; known keys: {', '.join(sorted(allowed))}"
            )


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _parse_mod(record: Any, where: str) -> BuyMod:
    if not isinstance(record, Mapping):
        raise TradeSpecError(f"{where}: each mod must be a mapping with a stat, got {record!r}")
    _no_unknown_keys(record, _MOD_KEYS, where)
    if "stat" not in record:
        raise TradeSpecError(f"{where}: a mod needs a stat")
    return BuyMod(
        stat=_field(record, "stat", where, "text", _is_str),
        minimum=_field(record, "minimum", where, "a number", _is_number),
        fractured=_field(record, "fractured", where, "true or false", _is_bool, default=False),
    )


def _parse_spec(record: Any, where: str) -> BuySpec:
    if not isinstance(record, Mapping):
        raise TradeSpecError(f"{where}: the file must be a mapping of keys, got {type(record).__name__}")
    _no_unknown_keys(record, _SPEC_KEYS, where)
    if "name" not in record:
        raise TradeSpecError(f"{where}: a buy spec needs a name")
    influence = _field(
        record,
        "influence",
        where,
        "a list of influence names",
        lambda v: isinstance(v, list) and all(isinstance(item, str) for item in v),
        default=[],
    )
    raw_mods = _field(record, "mods", where, "a list of mods", lambda v: isinstance(v, list), default=[])
    return BuySpec(
        name=_field(record, "name", where, "text", _is_str),
        base_type=_field(record, "base_type", where, "text", _is_str),
        category=_field(record, "category", where, "text", _is_str),
        rarity=_field(record, "rarity", where, "text", _is_str, default="rare"),
        item_level_min=_field(record, "item_level_min", where, "a whole number", _is_int),
        item_level_max=_field(record, "item_level_max", where, "a whole number", _is_int),
        influences=tuple(influence),
        corrupted=_field(record, "corrupted", where, "true or false", _is_bool, default=False),
        mods=tuple(_parse_mod(item, where) for item in raw_mods),
    )


def load_buy_spec(path: Path) -> BuySpec:
    """Read a buy spec from a YAML file. A missing file raises FileNotFoundError."""
    text = Path(path).read_text(encoding="utf-8")
    where = str(path)
    try:
        record = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise TradeSpecError(f"{where}: not valid YAML ({error})") from error
    try:
        return _parse_spec(record, where)
    except TradeSpecError as error:
        if where in str(error):
            raise
        raise TradeSpecError(f"{where}: {error}") from error
