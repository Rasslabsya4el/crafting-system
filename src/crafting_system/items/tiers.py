"""The tier of a mod on a base, derived from the game data.

The data has no tier field, so the tier is counted here. Tiers are counted among the mods of one
mod type (not one family) and one generation type and domain, and only among the mods that can
spawn on the base (a positive spawn weight for its tags). The five "+1 to Level of all X Skill
Gems" amulet prefixes share one family but are five mod types, so each is tier 1. Inside a group
the tier of a mod is 1 plus the number of mods of the group with a strictly higher required level:
tier 1 is the highest required level, and mods that tie on the required level share a tier. No
such tie exists on a released base in 3.29.3.3. A tier does not depend on the item level.
"""

from collections import defaultdict
from collections.abc import Mapping
from types import MappingProxyType

from crafting_system.data import GameData, Mod
from crafting_system.rules import get_rule

from .errors import TierError, UnknownBaseError, UnknownModError
from .spawn import spawn_weight

NUMBERING = get_rule("mod_tier.numbering")
SCOPE = get_rule("mod_tier.scope_is_mod_type")


_TABLE_LIMIT = 32
# (id(data), base_id) -> (data, table). Holding `data` keeps its id from being reused while cached.
_TABLES: dict[tuple[int, str], tuple[GameData, Mapping[str, int]]] = {}


def tier_table(data: GameData, base_id: str) -> Mapping[str, int]:
    """The tier of every mod that can spawn on the base `base_id`, by mod id; read-only.

    Mods that cannot spawn there (spawn weight 0 for the base's tags) are absent. Raises
    `UnknownBaseError` when the base is not in the game data. The table is cached per game data
    object and base: a repeated call returns the same object.
    """
    key = (id(data), base_id)
    hit = _TABLES.get(key)
    if hit is not None and hit[0] is data:
        return hit[1]
    table = _compute_tier_table(data, base_id)
    if key not in _TABLES and len(_TABLES) >= _TABLE_LIMIT:
        del _TABLES[next(iter(_TABLES))]
    _TABLES[key] = (data, table)
    return table


def _compute_tier_table(data: GameData, base_id: str) -> Mapping[str, int]:
    """`tier_table` without the cache."""
    base = data.base_items.get(base_id)
    if base is None:
        raise UnknownBaseError(f"base {base_id} is not in the game data")
    groups: dict[tuple[str, str, str], list[Mod]] = defaultdict(list)
    for mod in data.mods.values():
        if spawn_weight(mod, base.tags) > 0:
            groups[(mod.type, mod.generation_type, mod.domain)].append(mod)
    table: dict[str, int] = {}
    for group in groups.values():
        levels = [mod.required_level for mod in group]
        for mod in group:
            table[mod.id] = 1 + sum(level > mod.required_level for level in levels)
    return MappingProxyType(table)


def mod_tier(data: GameData, base_id: str, mod_id: str) -> int:
    """The tier of the mod `mod_id` on the base `base_id`, from `tier_table`.

    Raises `UnknownBaseError`, `UnknownModError` when the mod is not in the game data, and
    `TierError` when the mod cannot spawn on the base.
    """
    table = tier_table(data, base_id)
    if mod_id not in data.mods:
        raise UnknownModError(f"mod {mod_id} is not in the game data")
    if mod_id not in table:
        raise TierError(f"mod {mod_id} has no tier on base {base_id}: it cannot spawn there")
    return table[mod_id]


# -- the natural tier: what a requirement may ask of a mod (ticket #457, OR-1, OR-2, OR-4) -------------------

ANY_TIER = "any"  # `min_tier: any`: every tier of the natural ladder counts
_NATURAL_SIDES = ("prefix", "suffix")


def natural_tiers(data: GameData, base_id: str, tiers: Mapping[str, int] | None = None) -> Mapping[str, int]:
    """The natural tier of every mod that a draw can roll on the base: `tier_table` cut down to the mods that have a natural ladder.

    A mod is natural when it is a prefix or a suffix of the base's own domain, it is not essence-only and it can spawn on the base
    (it is in the table). A bench craft (domain `crafted`), an essence-only mod, a veiled one, an Elevated one or an aspect has no
    natural tier and is absent. `tiers` is the table to cut: the default is `tier_table`; pass `actions.tiers_of` for an item with
    influences. The tier of a mod is the table's, the one number of the game data (`independent/ladder.py` computes the same).
    """
    table = tier_table(data, base_id) if tiers is None else tiers
    domain = data.base_items[base_id].domain
    found: dict[str, int] = {}
    for mod_id, tier in table.items():
        mod = data.mods[mod_id]
        if mod.domain == domain and mod.generation_type in _NATURAL_SIDES and not mod.is_essence_only:
            found[mod_id] = tier
    return MappingProxyType(found)


def top_tiers(data: GameData, natural: Mapping[str, int], item_level: int) -> Mapping[str, int]:
    """For each natural mod, the top tier of its ladder that `item_level` allows (OR-1); absent where no rung of the ladder is that low.

    A ladder is the natural mods of one mod type and one generation type. Its top tier at a level is the lowest tier number
    among its mods whose required level is at most the level.
    """
    best: dict[tuple[str, str], int] = {}
    for mod_id, tier in natural.items():
        mod = data.mods[mod_id]
        if mod.required_level <= item_level:
            key = (mod.type, mod.generation_type)
            if key not in best or tier < best[key]:
                best[key] = tier
    top: dict[str, int] = {}
    for mod_id in natural:
        mod = data.mods[mod_id]
        key = (mod.type, mod.generation_type)
        if key in best:
            top[mod_id] = best[key]
    return MappingProxyType(top)


def accepted_by_tier(
    data: GameData,
    base_id: str,
    item_level: int,
    mod_ids: frozenset[str],
    min_tier: int | str | None,
    tiers: Mapping[str, int] | None = None,
) -> frozenset[str]:
    """The mods of `mod_ids` that a tier leaf accepts, by their natural tier on the base; a mod with no natural tier is never in it.

    `min_tier` is a number k (natural tier k or better), `ANY_TIER` (every natural tier) or None (the OR-1 default: the top tier
    of the mod's ladder that `item_level` allows). `tiers` is as in `natural_tiers`.
    """
    natural = natural_tiers(data, base_id, tiers)
    if min_tier is None:
        top = top_tiers(data, natural, item_level)
        return frozenset(mod_id for mod_id in mod_ids if mod_id in top and natural[mod_id] <= top[mod_id])
    if min_tier == ANY_TIER:
        return frozenset(mod_id for mod_id in mod_ids if mod_id in natural)
    return frozenset(mod_id for mod_id in mod_ids if mod_id in natural and natural[mod_id] <= min_tier)
