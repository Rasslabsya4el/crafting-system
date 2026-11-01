"""The corrupted implicit pool: every implicit a corrupting action could draw on a base, at an item level (ADR-0037).

A Vaal Orb, a Bloodstained resonator and the Locus of Corruption draw their implicit from the mods whose
`generation_type` is `corrupted`. A mod is a candidate when the first of its spawn weights that the base's tags
match is above 0, and its `required_level` is at most the item level (the gate Craft of Exile applies to its corrupted
mods too). Every mod is its own draw, so a family with three tiers counts three times. The pool depends on the base's
tags only, hence on its item class (Warstaves are the one class with two pools: the three experimental rods carry the
Staff tags). Nothing here reads what an item holds: the explicit mods do not enter the draw.

The mods are those of the base's own domain (`item` for equipment, `misc` for jewels, `abyss_jewel` for abyss jewels). The domain
matters: an abyss jewel mod lists only the `default` tag, which every base has, so a pool built on tags alone would
give a ring the abyss jewel implicits.

Cluster and Timeless jewels are refused (`OutOfScopeError`): their pools are not checked against the data (ADR-0004,
ADR-0037); a base whose class has no pool at all is refused with `NotApplicableError`.
"""

from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import BaseItem, GameData, Mod
from crafting_system.items import UnknownBaseError, spawn_weight

from .errors import NotApplicableError, OutOfScopeError

CORRUPTED = "corrupted"
ABYSS_JEWEL_TAG = "abyss_jewel"
ABYSS_JEWEL_DOMAIN = "abyss_jewel"
CLUSTER_JEWEL_DOMAIN = "affliction_jewel"
TIMELESS_JEWEL_NAME = "Timeless Jewel"


@dataclass(frozen=True, slots=True)
class CorruptedImplicit:
    """A mod the corrupted pool can give, and its weight (the spawn weight of the first matching tag)."""

    mod: Mod
    weight: int


@dataclass(frozen=True, slots=True)
class CorruptedImplicitPool:
    """The corrupted implicits a base can get at an item level, in the order of the game data.

    `item_class` is the base's class. A pool can be empty only when the item level is below every mod's required
    level; `chance` then raises, as there is no draw.
    """

    base_id: str
    item_class: str
    item_level: int
    mods: tuple[CorruptedImplicit, ...]

    @property
    def total_weight(self) -> int:
        """W: the sum of the weights of the mods."""
        return sum(entry.weight for entry in self.mods)

    def mod_ids(self) -> frozenset[str]:
        """The ids of the mods in the pool."""
        return frozenset(entry.mod.id for entry in self.mods)

    def weight_of(self, mod_id: str) -> int:
        """The weight of the mod `mod_id`; 0 when it is not in the pool."""
        return next((entry.weight for entry in self.mods if entry.mod.id == mod_id), 0)

    def chance(self, mod_id: str) -> Fraction:
        """The exact chance that one draw gives `mod_id` (its weight over W); 0 when it is not in the pool.

        Raises `ValueError` for an empty pool.
        """
        total = self.total_weight
        if total == 0:
            raise ValueError(f"the corrupted implicit pool of {self.base_id} at item level {self.item_level} is empty")
        return Fraction(self.weight_of(mod_id), total)


_CORRUPTED_MODS: dict[int, tuple[GameData, tuple[Mod, ...]]] = {}
_POOL_LIMIT = 256
_POOLS: dict[tuple[int, str, int], tuple[GameData, CorruptedImplicitPool]] = {}


def _corrupted_mods(data: GameData) -> tuple[Mod, ...]:
    """Every mod of generation type corrupted, in data order (the entry keeps `data` alive, so its `id` is not reused)."""
    found = _CORRUPTED_MODS.get(id(data))
    if found is not None and found[0] is data:
        return found[1]
    mods = tuple(mod for mod in data.mods.values() if mod.generation_type == CORRUPTED)
    _CORRUPTED_MODS[id(data)] = (data, mods)
    return mods


def _refuse_unchecked(base: BaseItem) -> None:
    """Raise `OutOfScopeError` for a Cluster or a Timeless jewel: their corrupted pools are not checked."""
    if base.domain == CLUSTER_JEWEL_DOMAIN:
        kind = "Cluster Jewel"
    elif base.name == TIMELESS_JEWEL_NAME:
        kind = "Timeless Jewel"
    else:
        return
    raise OutOfScopeError(
        f"{base.name} is a {kind}: its corrupted implicit pool is not checked against the game data, "
        "so no pool is given (ADR-0037)"
    )


def corrupted_implicit_pool(data: GameData, base_id: str, item_level: int) -> CorruptedImplicitPool:
    """The corrupted implicit pool of the base `base_id` at `item_level`.

    Raises `UnknownBaseError` for a base not in the game data, `OutOfScopeError` for a Cluster or Timeless jewel
    and `NotApplicableError` for a base whose item class has no corrupted implicit at all (a flask, a map, a gem).
    A result is cached per game data object, base and item level.
    """
    key = (id(data), base_id, item_level)
    hit = _POOLS.get(key)
    if hit is not None and hit[0] is data:
        return hit[1]
    pool = _compute(data, base_id, item_level)
    if len(_POOLS) >= _POOL_LIMIT:
        del _POOLS[next(iter(_POOLS))]
    _POOLS[key] = (data, pool)
    return pool


def _compute(data: GameData, base_id: str, item_level: int) -> CorruptedImplicitPool:
    base = data.base_items.get(base_id)
    if base is None:
        raise UnknownBaseError(f"no base {base_id} in the game data")
    _refuse_unchecked(base)
    domain = ABYSS_JEWEL_DOMAIN if ABYSS_JEWEL_TAG in base.tags else base.domain
    candidates = []
    any_level = False
    for mod in _corrupted_mods(data):
        if mod.domain != domain:
            continue
        weight = spawn_weight(mod, base.tags)
        if weight <= 0:
            continue
        any_level = True
        if mod.required_level <= item_level:
            candidates.append(CorruptedImplicit(mod, weight))
    if not any_level:
        raise NotApplicableError(
            f"{base.name} ({base.item_class}) has no corrupted implicit pool: no corrupting action gives it an implicit"
        )
    return CorruptedImplicitPool(base_id, base.item_class, item_level, tuple(candidates))
