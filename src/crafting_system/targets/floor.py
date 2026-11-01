"""The item level floor of a target and the groups of levels with one pool (ADR-0061, ticket #352).

The item level a target file names is where the owner's guide put it, not the lowest level at which the item can be made. A belt
that asks for tier-1 Fire and Cold Resistance needs item level 84, and a belt of 84 has a smaller pool than one of 86, so it can be
cheaper to craft and to buy (research #337, R13: 5,492 Chaos at level 84 against 6,311 at 86). `item_level_options` says how far
down the planner may go and which levels are one plan; it builds no start option and prices nothing (that is `plan_with_starts`, #359).

* **The floor is the lowest level at which every requirement can be met.** A tier is absolute on a base (`items.tier_table`), so
  what a requirement asks for fixes the lowest level of the mods that give it: for each requirement the lowest `required_level` among
  the mods that pass its tier, its roll limit and `not_crafted`, from the sources the planner has: the pool of a random draw, the bench
  (the mod's own required level, the crafted mod counting as tier 1 at its lowest roll) and a fixed mod an action forces (an essence, a fossil; it ignores the item
  level, `essence.forced_mod_ignores_item_level`). They are those of the actions the target offers: the planner's catalog
  that its `actions:` names (a kind, or the label of one action; none is every default kind, corrupted essences left out). `at_least` groups take
  the k-th lowest of their members. A requirement the start item already meets asks nothing, but a mod the start item holds needs its
  own level. A requirement no source can give has no level; the target is then met at no level and the floor stays at the file's.
* **The author can say more.** `item_level_floor: N` raises the floor to N, never lowers it below the derived one. `tiers_top_at_item_level:
  true` says the tiers written are "the top tier at that level" (R05's resistances are tier 2 because the guide's ring is level 75),
  so the level is not lowered at all. A target that asks for a corrupted implicit is not lowered either: its mod ids are the corrupted
  pool of the file's level.
* **Levels are grouped by pool.** Two levels are one plan when no random draw sees a difference: the mods that can spawn are those whose
  `required_level` is at most the level, so the pool changes only at the required levels of the candidate mods. Quality makes every level
  its own group, because a catalyst's gain depends on the item level (`catalyst.gain_depends_on_item_level`). The top group runs up to
  the highest item level, past the file's level; a bought base of any level in it is that plan.
* **Below the floor is refused**, with the requirement that needs more (`target_at_level`).
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace

from crafting_system.actions import (
    Action,
    ActionError,
    catalog,
    drawable_mod_ids,
    kinds,
    tiers_of,
)
from crafting_system.data import GameData, Mod
from crafting_system.items import ItemError, Side
from crafting_system.items.model import MAX_ITEM_LEVEL, MIN_ITEM_LEVEL

from .errors import TargetError
from .model import KOfN, Node, Requirement, Target

__all__ = [
    "ItemLevelFloor",
    "ItemLevelOptions",
    "LevelGroup",
    "NodeLevel",
    "floor_of",
    "item_level_options",
    "level_groups",
    "refusal_at",
    "target_at_level",
]

BENCH_TIER = 1  # `actions.bench.CRAFTED_TIER`: a crafted mod counts as tier 1 of what it crafts, whatever its range

DERIVED = "derived"
STATED = "stated"
PINNED = "pinned"
CORRUPTED = "corrupted"
AT_TARGET = "at target"


@dataclass(frozen=True)
class NodeLevel:
    """The lowest item level at which one top-level requirement can be met, and what sets it.

    `level` is None when no source gives it at any level. `source` is `pool`, `bench`, `forced mod`, `start item` or `none`; `mod_id` is
    the mod that sets the level (None for `start item` and `none`).
    """

    label: str
    level: int | None
    source: str
    mod_id: str | None = None


@dataclass(frozen=True)
class ItemLevelFloor:
    """The lowest item level the planner may plan a target at, and why.

    `level` is at most the file's `item_level`. `kind` is `derived` (the tiers the requirements ask for), `stated` (the target's
    `item_level_floor` is the higher), `pinned` (`tiers_top_at_item_level`), `corrupted` (a corrupted implicit is asked for) or
    `at target` (the leaves ask for more than the file's level, so no level below the file's can do). `reason` is that in a sentence.
    `nodes` are the levels of the top-level requirements, in file order; `start_level` is the level the mods of the start item need.
    """

    level: int
    kind: str
    reason: str
    nodes: tuple[NodeLevel, ...]
    start_level: int = MIN_ITEM_LEVEL

    @property
    def binding(self) -> NodeLevel | None:
        """The requirement with the highest level (the first of them), or None when no requirement has a level."""
        return _binding(self.nodes)


def _binding(nodes: tuple[NodeLevel, ...]) -> NodeLevel | None:
    known = [node for node in nodes if node.level is not None]
    return max(known, key=lambda node: node.level or 0) if known else None


@dataclass(frozen=True)
class LevelGroup:
    """Item levels `lowest` to `highest` that have one pool, so one plan.

    `lowest` is not below the floor. `highest` is where the pool next changes, or the highest item level: it can lie above the
    target's own level (a bought base of any level in the group is this plan).
    """

    lowest: int
    highest: int

    def contains(self, level: int) -> bool:
        return self.lowest <= level <= self.highest


@dataclass(frozen=True)
class ItemLevelOptions:
    """The floor of a target and the groups of levels from it up to the target's level, lowest first."""

    floor: ItemLevelFloor
    groups: tuple[LevelGroup, ...]


# -- the lowest level of a requirement ------------------------------------------------------------


def _label(node: Node) -> str:
    if isinstance(node, KOfN):
        return f"at least {node.at_least} of ({'; '.join(_label(member) for member in node.of)})"
    name = (node.family if node.family is not None else node.stat or "").replace("\n", ", ")
    tier = f" tier {node.min_tier}" if node.min_tier is not None else ""
    return f"{name}{tier}"


def _offered(data: GameData, target: Target) -> list[Action]:
    """The actions the planner could use on the target's start item, as `actions:` names them (the catalog the planner reads).

    No `actions:` is every kind offered by default (corrupted essences are opt-in, so they are not among them). A name is a kind of
    the catalog, else the label of one action (an essence by its name, a bench craft by its text). A name that is neither is not
    checked here: the planner refuses the file.
    """
    start = target.start_item
    names = target.actions
    if names is None:
        return list(catalog(data, start, planner_only=True))
    usable = {entry.name for entry in kinds(planner_only=True)}
    exist = {entry.name for entry in kinds()}
    found = list(catalog(data, start, planner_only=True, names={name for name in names if name in usable}))
    labels = {name for name in names if name not in exist}
    if labels:
        found.extend(
            action for action in catalog(data, start, planner_only=True, names=usable) if action not in found and action.label(data) in labels
        )
    return found


def _within(wish: Requirement, tier: int) -> bool:
    """Whether `tier` (1 is the best) is accepted by the requirement's `min_tier`."""
    return wish.min_tier is None or tier <= wish.min_tier


def _roll_passes(mod: Mod, wanted: tuple[int | None, ...] | None, *, high: bool) -> bool:
    if wanted is None:
        return True
    if len(mod.stats) != len(wanted):
        return False
    return all(
        limit is None or (max(stat.min, stat.max) if high else min(stat.min, stat.max)) >= limit
        for stat, limit in zip(mod.stats, wanted, strict=True)
    )


class _Sources:
    """Where a mod can come from for this target, and the item level that source asks for."""

    def __init__(self, data: GameData, target: Target) -> None:
        self.data = data
        self.target = target
        base = data.base_items[target.base_id]
        # The mods a random draw can give this item: tiers_of lists every domain (veiled, jewel, monster ones among them), a draw takes
        # the base's own domain and the two sides.
        self.tiers = {
            mod_id: tier
            for mod_id, tier in tiers_of(data, target.start_item).items()
            if data.mods[mod_id].domain == base.domain and data.mods[mod_id].generation_type in Side
        }
        # What an offered action puts on the item by name (`Action.adds`): a crafted mod (the bench) is given at the mod's own required
        # level; any other fixed mod (an essence's forced mod, a fossil's, an aspect's) ignores the item level.
        self.bench: frozenset[str] = frozenset()
        self.forced: frozenset[str] = frozenset()
        for action in _offered(data, target):
            adds = action.adds(data, target.start_item)
            if not adds.named:
                continue
            if adds.crafted:
                self.bench |= adds.named
            else:
                self.forced |= adds.named

    def lowest(self, wish: Requirement) -> NodeLevel:
        """The lowest level at which `wish` is met, with the mod and the source that give it."""
        label = _label(wish)
        if wish.is_met_by(self.target.start_item):
            return NodeLevel(label, MIN_ITEM_LEVEL, "start item")
        best: tuple[int, str, str] | None = None  # (level, source, mod id)
        for mod_id in sorted(wish.mod_ids):
            mod = self.data.mods.get(mod_id)
            if mod is None:
                continue
            for level, source in self._gates(wish, mod):
                if best is None or level < best[0]:
                    best = (level, source, mod_id)
        if best is None:
            return NodeLevel(label, None, "none")
        return NodeLevel(label, best[0], best[1], best[2])

    def _gates(self, wish: Requirement, mod: Mod) -> Iterable[tuple[int, str]]:
        tier = self.tiers.get(mod.id)
        if tier is not None and _within(wish, tier) and _roll_passes(mod, wish.min_roll, high=True):
            yield max(mod.required_level, MIN_ITEM_LEVEL), "pool"
        if mod.id in self.bench and not wish.not_crafted and _within(wish, BENCH_TIER) and _roll_passes(mod, wish.min_roll, high=False):
            yield max(mod.required_level, MIN_ITEM_LEVEL), "bench"
        if mod.id in self.forced and _within(wish, tier if tier is not None else 1) and _roll_passes(mod, wish.min_roll, high=True):
            yield MIN_ITEM_LEVEL, "forced mod"


def _node_levels(sources: _Sources, node: Node) -> tuple[int | None, NodeLevel]:
    """The level of a requirement or a group, and its `NodeLevel` (a group's source is that of the member that binds it)."""
    if isinstance(node, Requirement):
        found = sources.lowest(node)
        return found.level, found
    members = [_node_levels(sources, member) for member in node.of]
    ranked = sorted((level for level, _ in members if level is not None))
    if len(ranked) < node.at_least:
        return None, NodeLevel(_label(node), None, "none")
    level = ranked[node.at_least - 1]
    binder = next(found for member_level, found in members if member_level == level)
    return level, NodeLevel(_label(node), level, binder.source, binder.mod_id)


def floor_of(data: GameData, target: Target) -> ItemLevelFloor:
    """The lowest item level the planner may plan `target` at (see the module docstring)."""
    sources = _Sources(data, target)
    nodes = tuple(_node_levels(sources, node)[1] for node in target.requirements)
    start_level = max(
        (data.mods[entry.mod_id].required_level for entry in target.start_item.mods if not entry.crafted and entry.mod_id in data.mods),
        default=MIN_ITEM_LEVEL,
    )
    asked = max([start_level, *(node.level for node in nodes if node.level is not None)])
    at = target.item_level
    if target.tiers_top_at_item_level:
        return ItemLevelFloor(at, PINNED, f"the target says its tiers are the top tiers of item level {at}, so the level is not lowered", nodes, start_level)
    if target.asks_corrupted:
        return ItemLevelFloor(at, CORRUPTED, f"the target asks for a corrupted implicit, drawn from the pool of item level {at}", nodes, start_level)
    if any(node.level is None for node in nodes):
        missing = next(node for node in nodes if node.level is None)
        return ItemLevelFloor(at, AT_TARGET, f"no source the floor knows (a random draw, the bench, an essence, the start item) gives {missing.label}, so the level is not lowered", nodes, start_level)
    if asked > at:
        return ItemLevelFloor(at, AT_TARGET, f"the requirements ask for item level {asked}, above the target's {at}", nodes, start_level)
    stated = target.item_level_floor
    if stated is not None and stated > asked:
        return ItemLevelFloor(stated, STATED, f"the target states the floor {stated}; its requirements alone would allow {asked}", nodes, start_level)
    binding = _binding(nodes)
    if binding is None or (binding.level or 0) < start_level:
        why = f"the mods of the start item need item level {start_level}"
    else:
        which = f"{binding.mod_id} ({binding.source})" if binding.mod_id else binding.source
        why = f"{binding.label} needs item level {binding.level}, from {which}"
    return ItemLevelFloor(asked, DERIVED, why, nodes, start_level)


# -- the groups of levels ------------------------------------------------------------------------


def _change_points(data: GameData, target: Target) -> list[int] | None:
    """The item levels at which the pool of a random draw gains a mod, or None when the pool cannot be built (then every level counts)."""
    try:
        ids = drawable_mod_ids(data, target.start_item.changed(data, item_level=MAX_ITEM_LEVEL))
    except ActionError:
        return None
    return sorted({data.mods[mod_id].required_level for mod_id in ids})


def level_groups(data: GameData, target: Target, floor: int) -> tuple[LevelGroup, ...]:
    """The groups of item levels from `floor` up to the target's level, lowest first; the last group runs on to the highest item level."""
    at = target.item_level
    if not MIN_ITEM_LEVEL <= floor <= at:
        raise ValueError(f"the floor {floor} is not from {MIN_ITEM_LEVEL} to the target's item level {at}")
    points = _change_points(data, target)
    if points is None or target.quality is not None:
        points = list(range(MIN_ITEM_LEVEL, MAX_ITEM_LEVEL + 1))  # every level its own plan
    starts = sorted({floor, *(point for point in points if floor < point <= at)})
    groups = []
    for lowest in starts:
        later = [point for point in points if point > lowest]
        highest = later[0] - 1 if later else MAX_ITEM_LEVEL
        groups.append(LevelGroup(lowest, highest))
    return tuple(groups)


def item_level_options(data: GameData, target: Target) -> ItemLevelOptions:
    """The floor of `target` and its groups of levels from the floor to the target's level."""
    floor = floor_of(data, target)
    return ItemLevelOptions(floor, level_groups(data, target, floor.level))


# -- planning at a level --------------------------------------------------------------------------


def refusal_at(data: GameData, target: Target, level: int) -> str | None:
    """Why `target` is not planned at item level `level`, or None when it may be (a level above the target's is not asked here)."""
    if type(level) is not int or not MIN_ITEM_LEVEL <= level <= MAX_ITEM_LEVEL:
        return f"item level {level!r} is outside {MIN_ITEM_LEVEL} to {MAX_ITEM_LEVEL}"
    floor = floor_of(data, target)
    if level >= floor.level:
        return None
    return f"item level {level} is below {floor.level}, the lowest at which this target can be planned: {floor.reason}"


def target_at_level(data: GameData, target: Target, level: int) -> Target:
    """`target` with its item level, and that of its start item, set to `level`.

    Raises `TargetError` for a level below the floor (`refusal_at`) and when the start item cannot have that level.
    """
    problem = refusal_at(data, target, level)
    if problem is not None:
        raise TargetError(problem)
    if level == target.item_level:
        return target
    try:
        start = target.start_item.changed(data, item_level=level)
    except ItemError as error:
        raise TargetError(f"the start item cannot have item level {level}: {error}") from None
    return replace(target, item_level=level, start_item=start)

