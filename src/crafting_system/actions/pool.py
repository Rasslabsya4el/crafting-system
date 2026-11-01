"""The pool of one random add: every mod that could be drawn next on an item, grouped by family.

A draw picks a mod in proportion to its weight among the candidates, then its whole family leaves
the pool and its side takes a slot (ADR-0021: a "family" is the exclusion set of a mod). The pool
holds no capacity filter: which sides still have room changes during a reroll, so the draw applies
it. Weights are exact fractions and never rounded.

The item's tags for the spawn weights are the tags of its base plus one tag per influence
(`item_tags`), so the mods of an influence join the pool. Items carry no Memory Strands (`NO_MEMORY_STRANDS`), so a draw is never tier-gated.
A family can have mods on both sides (jewels): its `PoolFamily` come in a pair of one name (`partners`), and a draw takes the family out on both sides.
The Attack and Caster metamods on the item filter the pool by tag (`metamods.py`). Implicit mods of the base never block a candidate (`IMPLICITS_DO_NOT_BLOCK`); only the explicit
mods on the item do.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import chain

from crafting_system.data import BaseItem, GameData, Mod
from crafting_system.items import Item, Side, UnknownBaseError, effective_weight, spawn_weight, tier_table
from crafting_system.rules import get_rule

from .errors import OutOfScopeError
from .metamods import allowed_by_tags, blocked_tags

DOMAIN_MATCH = get_rule("affix_pool.domain_match")
SIDE_IS_GENERATION_TYPE = get_rule("affix_pool.side_is_generation_type")
LEVEL_GATE = get_rule("affix_pool.level_gate")
FAMILY_EXCLUSION = get_rule("affix_draw.family_exclusion")
IMPLICITS_DO_NOT_BLOCK = get_rule("affix_pool.implicits_do_not_block")
NO_MEMORY_STRANDS = get_rule("affix_pool.no_memory_strands")
INFLUENCE_TAGS = get_rule("affix_pool.influence_tags")


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


@dataclass(frozen=True, slots=True)
class Candidate:
    """A mod that could be drawn next, with the weight it has before any fossil factor, and its family and side."""

    mod: Mod
    weight: Fraction
    family: str
    side: Side


ModFactor = Callable[[Mod], Fraction]

_ADMITTED_LIMIT = 32
_ADMITTED: dict[tuple, tuple[GameData, tuple[tuple[Mod, Fraction], ...]]] = {}


_POOL_LIMIT = 256
# (id(data), base, item level, influences, max level, mod ids of the item, mod ids of extra, tag filter) -> (data, candidates).
_POOLS: dict[tuple, tuple[GameData, tuple[Candidate, ...]]] = {}


def item_tags(data: GameData, item: Item) -> tuple[str, ...]:
    """The tags the spawn weights see on `item`: its base's tags, then one `<class key>_<influence key>` per influence.

    Raises `UnknownBaseError` for a base not in the game data and `OutOfScopeError` when the item is
    influenced and its item class has no admitted class key (`affix_pool.influence_tags`).
    """
    base = data.base_items.get(item.base_id)
    if base is None:
        raise UnknownBaseError(f"item on {item.base_id}: the base is not in the game data")
    if not item.influences:
        return base.tags
    class_key = INFLUENCE_TAGS.value["classes"].get(base.item_class)
    if class_key is None:
        raise OutOfScopeError(
            f"the item is influenced and its class ({base.item_class}) has no admitted influence class key, "
            "so the influence mods of its pool are not modelled"
        )
    keys = INFLUENCE_TAGS.value["influences"]
    return (*base.tags, *(f"{class_key}_{keys[influence.value]}" for influence in sorted(item.influences)))


def drawable_mod_ids(data: GameData, item: Item) -> frozenset[str]:
    """The ids of the mods a draw could give an item of `item`'s base, level and influences once it holds none.

    A planner asks this to see whether a mod of the goal can occur at all (a roll requirement on a mod no
    draw gives and no action adds is out of reach). The Attack and Caster metamods are not applied, so the answer is
    the larger one. Raises what `pool_candidates` raises (`UnknownBaseError`, `OutOfScopeError`).
    """
    bare = item.changed(data, mods=(), veil_offer=())
    return frozenset(candidate.mod.id for candidate in pool_candidates(data, bare))


def tiers_of(data: GameData, item: Item) -> Mapping[str, int]:
    """The tier of every mod that can spawn on `item`, counted as `items.tier_table` does but with the influence tags too.

    An item without influence gets `tier_table`. Mods that cannot spawn on it are absent.
    """
    if not item.influences:
        return tier_table(data, item.base_id)
    tags = item_tags(data, item)
    groups: dict[tuple[str, str, str], list[Mod]] = defaultdict(list)
    for mod in data.mods.values():
        if spawn_weight(mod, tags) > 0:
            groups[(mod.type, mod.generation_type, mod.domain)].append(mod)
    table: dict[str, int] = {}
    for group in groups.values():
        for mod in group:
            table[mod.id] = 1 + sum(other.required_level > mod.required_level for other in group)
    return table


def _admitted(
    data: GameData, base: BaseItem, tags: tuple[str, ...], level_limit: int, extra: Iterable[Mod]
) -> tuple[tuple[Mod, Fraction], ...]:
    """The mods of the domain with a side, within the level limit and a positive weight on `tags`, with that weight, in data order.

    What the item holds (its blocks, its metamods) is not in it, so it is the same for every item of one base, level
    and influence: a state-space walk asks for thousands of pools and would otherwise weigh every mod of the game each time.
    The entry keeps `data` alive, so its `id` cannot be reused while it is cached.
    """
    joined = tuple(extra)
    key = (id(data), base.domain, tags, level_limit, tuple(mod.id for mod in joined))
    found = _ADMITTED.get(key)
    if found is not None and found[0] is data:
        return found[1]
    own = ((mod, mod.domain == base.domain) for mod in data.mods.values())
    kept = []
    for mod, in_domain in chain(own, ((mod, True) for mod in joined)):
        if not in_domain or mod.generation_type not in Side or mod.required_level > level_limit:
            continue
        weight = effective_weight(mod, tags)
        if weight > 0:
            kept.append((mod, weight))
    if len(_ADMITTED) >= _ADMITTED_LIMIT:
        _ADMITTED.clear()
    entry = _ADMITTED[key] = (data, tuple(kept))
    return entry[1]


def pool_candidates(
    data: GameData,
    item: Item,
    max_level: int | None = None,
    extra: Iterable[Mod] = (),
    *,
    tag_filter: bool = True,
) -> tuple[Candidate, ...]:
    """Every mod that could be drawn next on `item`, with its weight on the base, in data order.

    `max_level` is a further cap on the required level of a candidate (the cap of a low essence on
    its random mods); the item level gate applies as well, so the effective limit is the lower of
    the two. `extra` are mods of other domains that join the pool (the Delve mods that a Faceted
    Fossil adds); they pass every other test of an ordinary candidate.

    The Attack and Caster metamods on `item` keep the mods with that tag out of the pool
    (`blocked_tags`); `tag_filter=False` leaves them in (a Harvest reforge filters its first mod only).

    Raises `OutOfScopeError` for a candidate that does not have exactly one family (none is
    drawable in domain `item` in 3.29.3.3). A family may have candidates on both sides (five families
    of the base jewels do, `affix_pool.family_may_span_both_sides`); `group_pool` makes one `PoolFamily`
    per side of it, and the two keep the family name.
    A result is cached per game data object and key; a call that raises is not cached.
    """
    extra = tuple(extra)
    key = (
        id(data),
        item.base_id,
        item.item_level,
        tuple(sorted(influence.value for influence in item.influences)),
        max_level,
        tuple(sorted(entry.mod_id for entry in item.mods)),  # the metamods that filter by tag are mods of the item
        tuple(mod.id for mod in extra),
        tag_filter,
    )
    hit = _POOLS.get(key)
    if hit is not None and hit[0] is data:
        return hit[1]
    candidates = _compute_pool_candidates(data, item, max_level, extra, tag_filter)
    if key not in _POOLS and len(_POOLS) >= _POOL_LIMIT:
        del _POOLS[next(iter(_POOLS))]
    _POOLS[key] = (data, candidates)
    return candidates


def _compute_pool_candidates(
    data: GameData, item: Item, max_level: int | None, extra: tuple[Mod, ...], tag_filter: bool
) -> tuple[Candidate, ...]:
    """`pool_candidates` without the cache; `extra` is already a tuple."""
    base = data.base_items.get(item.base_id)
    if base is None:
        raise UnknownBaseError(f"item on {item.base_id}: the base is not in the game data")
    tags = item_tags(data, item)
    blocked = blocked_tags(data, item) if tag_filter else frozenset()
    level_limit = item.item_level if max_level is None else min(item.item_level, max_level)
    candidates: list[Candidate] = []
    for mod, weight in _admitted(data, base, tags, level_limit, extra):
        if item.blocks(data, mod) or not allowed_by_tags(mod, blocked):
            continue
        if len(mod.families) != 1:
            raise OutOfScopeError(
                f"mod {mod.id} is a candidate but has {len(mod.families)} families; "
                "only mods with exactly one family are modelled"
            )
        candidates.append(Candidate(mod, weight, mod.families[0], Side(mod.generation_type)))
    return tuple(candidates)


def group_pool(candidates: Iterable[Candidate], factor: ModFactor | None = None) -> tuple[PoolFamily, ...]:
    """The candidates grouped by family, each weight times `factor(mod)`; a mod whose factor is 0 is dropped.

    A family keeps the order of its first candidate. `factor` is the weight factor of the fossils
    in a resonator (`None`: every factor is 1). A family whose candidates sit on both sides is two
    `PoolFamily` of one name, one per side (`partners`): at most one mod of the family is ever drawn.
    """
    grouped: dict[tuple[str, Side], list[PoolMod]] = {}
    for candidate in candidates:
        weight = candidate.weight if factor is None else candidate.weight * factor(candidate.mod)
        if weight <= 0:
            continue
        grouped.setdefault((candidate.family, candidate.side), []).append(PoolMod(candidate.mod, weight))
    return tuple(PoolFamily(name, side, tuple(mods)) for (name, side), mods in grouped.items())


def partners(pool: Iterable[PoolFamily]) -> dict[str, tuple[PoolFamily, ...]]:
    """The families of `pool` that have mods on both sides, by name, each as its two sides' `PoolFamily`.

    Two `PoolFamily` of one name are one family: drawing a mod of either takes the family out of the pool
    on both sides (`affix_draw.family_exclusion`).
    """
    by_name: dict[str, list[PoolFamily]] = defaultdict(list)
    for family in pool:
        by_name[family.family].append(family)
    return {name: tuple(parts) for name, parts in by_name.items() if len(parts) > 1}


def mark_pool(pool: Iterable[PoolFamily], tag: str, chosen: Callable[[Mod], bool]) -> tuple[PoolFamily, ...]:
    """`pool` where exactly the mods for which `chosen` is true carry `tag` in `implicit_tags`.

    For a guaranteed draw whose set of mods is not a tag of the data (the influence reforge: the Hunter
    mods do not carry `influence_mod`). A mod is copied only when its tag changes, so the ids and weights stay.
    """

    def marked(mod: Mod) -> Mod:
        has, wants = tag in mod.implicit_tags, chosen(mod)
        if has == wants:
            return mod
        tags = (*mod.implicit_tags, tag) if wants else tuple(name for name in mod.implicit_tags if name != tag)
        return replace(mod, implicit_tags=tags)

    return tuple(
        PoolFamily(family.family, family.side, tuple(PoolMod(marked(entry.mod), entry.weight) for entry in family.mods))
        for family in pool
    )


def build_pool(
    data: GameData,
    item: Item,
    max_level: int | None = None,
    factor: ModFactor | None = None,
    extra: Iterable[Mod] = (),
    *,
    tag_filter: bool = True,
) -> tuple[PoolFamily, ...]:
    """The candidates for one more draw on `item`, grouped by family, in data order.

    See `pool_candidates` for `max_level`, `extra` and `tag_filter`, `group_pool` for `factor`.
    """
    return group_pool(pool_candidates(data, item, max_level, extra, tag_filter=tag_filter), factor)
