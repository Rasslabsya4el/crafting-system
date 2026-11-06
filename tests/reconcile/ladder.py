"""The natural tier ladder of a mod on a base, from the raw mods and bases (no planner code).

The rules live in `tests/independent/ladder.py`, the one module this package shares with `tests/oracle/` (ticket #419):
spawn weight on the item's tags (first matching entry), mods of the base's own domain, one mod `type` and one generation
type, ordered by required level, tier 1 the highest, Battle Royale copies left out (issue #248). What is here is what only
the reconciliation needs: the stat text readers and the mod pool of a base.

The ticket calls the ladder "of a family". Mods of one `groups` family can have several mod types (the five "+1 to Level
of all X Skill Gems" amulet prefixes), each its own ladder, so the type is used.
"""

import re

from independent.ladder import (
    TRADE_CATEGORY,
    base_ids_of,
    bases_named,
    bases_of_category,
    is_royale,
    item_tags,
    ladder_of,
    spawn_weight,
)

__all__ = [
    "TRADE_CATEGORY",
    "base_ids_of",
    "bases_named",
    "bases_of_category",
    "is_royale",
    "ladder",
    "normalise_stat_text",
    "pool_of",
    "spawn_weight",
    "stat_ranges",
]

_RANGE = re.compile(r"\(-?\d+(?:\.\d+)?--?\d+(?:\.\d+)?\)")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def ladder(mods: dict, base_tags, domain: str, mod_id: str, influences=(), item_class: str | None = None) -> dict[str, int]:
    """Tier by mod id of every mod in the ladder of `mod_id` on a base with `base_tags` and the base's `domain`.

    The ladder holds the natural mods of the same type and generation type. `mod_id` itself is in it only if it
    can spawn there. `influences` add the influence tags of the item; they need the base's `item_class`, and a class that
    takes no influence is refused (`independent.ladder.item_tags`).
    """
    return ladder_of(mods, item_tags(base_tags, influences, item_class), domain, mod_id)


def stat_ranges(mod: dict) -> list[tuple[float, float]]:
    """The (min, max) of each stat of the mod, in the order the data lists them."""
    return [(stat["min"], stat["max"]) for stat in mod["stats"]]


def normalise_stat_text(text: str) -> str:
    """A stat line with every number and every range replaced by `#`, as the buy specs write it."""
    text = _RANGE.sub("#", text)
    text = _NUMBER.sub("#", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def pool_of(mods: dict, base_tags, domain: str, cache: dict | None = None) -> frozenset:
    """The ids of the mods of the base's own `domain` (no Royale copy) that can spawn on a base with `base_tags`.

    The domain is the base's (`item` for gear, `misc` for jewels), as `ladder` takes it: the game rolls on a base only the
    mods of its domain, so the item-domain life mods that carry a `default` weight are not in a jewel's pool (ticket #433).
    """
    key = (id(mods), domain, tuple(sorted(base_tags)))
    if cache is not None and key in cache:
        return cache[key]
    found = frozenset(
        mod_id
        for mod_id, mod in mods.items()
        if mod["domain"] == domain and not is_royale(mod_id) and spawn_weight(mod, base_tags) > 0
    )
    if cache is not None:
        cache[key] = found
    return found
