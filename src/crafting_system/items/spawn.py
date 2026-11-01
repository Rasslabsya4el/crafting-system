"""The spawn weight and the generation weight of a mod on the tags of an item, and the weight a draw uses.

Both weight lists are ordered in the raw data and read first-match: the first entry whose tag the
item has decides, and the later ones are ignored (the mod's own order, not the order of the tags).
The result is an exact fraction; nothing here is rounded.

A Battle Royale copy of a mod (its id carries the marker of `affix_pool.royale_duplicates_do_not_spawn`) has
spawn weights in the export but is not rolled by the game, so its spawn weight is 0 on every item. Every pool,
tier table and weight sum of the planner reads spawn weights through `spawn_weight`, so this one place keeps
such a mod out of all of them.
"""

from collections.abc import Iterable
from fractions import Fraction

from crafting_system.data import Mod, Weight
from crafting_system.rules import get_rule

SPAWN_WEIGHT_FIRST_MATCH = get_rule("affix_pool.spawn_weight_first_match")
GENERATION_WEIGHT_MULTIPLIER = get_rule("affix_pool.generation_weight_multiplier")
ROYALE_DUPLICATES = get_rule("affix_pool.royale_duplicates_do_not_spawn")
ROYALE_MARKER: str = ROYALE_DUPLICATES.value["id_marker"]
PERCENT = 100


def _first_match(entries: tuple[Weight, ...], tags: frozenset[str]) -> Weight | None:
    """The first entry, in the order of `entries`, whose tag is in `tags`; None when none is."""
    return next((entry for entry in entries if entry.tag in tags), None)


def is_battle_royale(mod: Mod) -> bool:
    """Whether `mod` is a Battle Royale copy: its id holds the marker of `affix_pool.royale_duplicates_do_not_spawn`."""
    return ROYALE_MARKER in mod.id


def spawn_weight(mod: Mod, tags: Iterable[str]) -> int:
    """The spawn weight of `mod` on an item with `tags`; 0 when no entry matches or the mod is a Battle Royale copy."""
    if ROYALE_MARKER in mod.id:
        return 0
    entry = _first_match(mod.spawn_weights, frozenset(tags))
    return 0 if entry is None else entry.weight


def generation_factor(mod: Mod, tags: Iterable[str]) -> Fraction:
    """The multiplier of `mod` on an item with `tags`: its first matching generation weight over 100, else 1."""
    entry = _first_match(mod.generation_weights, frozenset(tags))
    return Fraction(1) if entry is None else Fraction(entry.weight, PERCENT)


def effective_weight(mod: Mod, tags: Iterable[str]) -> Fraction:
    """The weight a draw uses for `mod` on an item with `tags`: the spawn weight times the generation factor."""
    tags = frozenset(tags)
    return spawn_weight(mod, tags) * generation_factor(mod, tags)
