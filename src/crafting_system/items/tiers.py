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


def tier_table(data: GameData, base_id: str) -> Mapping[str, int]:
    """The tier of every mod that can spawn on the base `base_id`, by mod id; read-only.

    Mods that cannot spawn there (spawn weight 0 for the base's tags) are absent. Raises
    `UnknownBaseError` when the base is not in the game data.
    """
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
