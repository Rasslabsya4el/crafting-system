"""The pool of one random add: every mod that could be drawn next on an item, grouped by family.

A draw picks a mod in proportion to its weight among the candidates, then its whole family leaves
the pool and its side takes a slot (ADR-0021: a "family" is the exclusion set of a mod). The pool
holds no capacity filter: which sides still have room changes during a reroll, so the draw applies
it. Weights are exact fractions and never rounded.

The item's tags for the spawn weights are the tags of its base: influences are refused before the
pool is built. Items carry no Memory Strands (`NO_MEMORY_STRANDS`), so a draw is never tier-gated.
Implicit mods of the base never block a candidate (`IMPLICITS_DO_NOT_BLOCK`); only the explicit
mods on the item do.
"""

from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Side, UnknownBaseError, effective_weight
from crafting_system.rules import get_rule

from .errors import OutOfScopeError

DOMAIN_MATCH = get_rule("affix_pool.domain_match")
SIDE_IS_GENERATION_TYPE = get_rule("affix_pool.side_is_generation_type")
LEVEL_GATE = get_rule("affix_pool.level_gate")
FAMILY_EXCLUSION = get_rule("affix_draw.family_exclusion")
IMPLICITS_DO_NOT_BLOCK = get_rule("affix_pool.implicits_do_not_block")
NO_MEMORY_STRANDS = get_rule("affix_pool.no_memory_strands")


@dataclass(frozen=True, slots=True)
class PoolMod:
    """A candidate mod and the weight a draw gives it (spawn weight times generation factor)."""

    mod: Mod
    weight: Fraction


@dataclass(frozen=True, slots=True)
class PoolFamily:
    """The candidates of one family; they share a side and at most one of them can be drawn."""

    family: str
    side: Side
    mods: tuple[PoolMod, ...]

    @property
    def weight(self) -> Fraction:
        """The sum of the weights of its mods: the chance the family is drawn, per unit of total weight."""
        return sum((entry.weight for entry in self.mods), Fraction(0))


def build_pool(data: GameData, item: Item, max_level: int | None = None) -> tuple[PoolFamily, ...]:
    """The candidates for one more draw on `item`, grouped by family, in data order.

    `max_level` is a further cap on the required level of a candidate (the cap of a low essence on
    its random mods); the item level gate applies as well, so the effective limit is the lower of
    the two.

    Raises `OutOfScopeError` for a candidate that does not have exactly one family (none is
    drawable in domain `item` in 3.29.3.3) and for a family whose candidates sit on both sides.
    """
    base = data.base_items.get(item.base_id)
    if base is None:
        raise UnknownBaseError(f"item on {item.base_id}: the base is not in the game data")
    level_limit = item.item_level if max_level is None else min(item.item_level, max_level)
    grouped: dict[str, list[PoolMod]] = {}
    sides: dict[str, Side] = {}
    for mod in data.mods.values():
        if (
            mod.domain != base.domain
            or mod.generation_type not in Side
            or mod.required_level > level_limit
        ):
            continue
        weight = effective_weight(mod, base.tags)
        if weight <= 0 or item.blocks(data, mod):
            continue
        if len(mod.families) != 1:
            raise OutOfScopeError(
                f"mod {mod.id} is a candidate but has {len(mod.families)} families; "
                "only mods with exactly one family are modelled"
            )
        family, side = mod.families[0], Side(mod.generation_type)
        if sides.setdefault(family, side) is not side:
            raise OutOfScopeError(
                f"family {family} has candidates on both sides; a family on one side only is modelled"
            )
        grouped.setdefault(family, []).append(PoolMod(mod, weight))
    return tuple(PoolFamily(name, sides[name], tuple(mods)) for name, mods in grouped.items())
