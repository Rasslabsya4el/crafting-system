"""A brute-force oracle for the removals, the Exalted Orb, the Fracturing Orb and the metamods, independent of `crafting_system.abstraction` (ticket #69).

Like `abstraction_oracle.py` it lists every concrete finished item of an action with its exact
probability; a test compresses each one with `Abstraction.compress` and adds up the probability per
compressed state. Nothing here touches `Outcomes.distribution`, `exact_distribution`, the lumping of
`actions/draw.py` or `actions/metamods.py`; the one thing it takes from `actions` is `build_pool`: the
candidate (mod, weight) pairs of a draw, taken with the tag filter off so that the filter is played here.

The rules it plays are the claims of `metamods.yaml` and of the orbs, written again as plain code:

* `Prefixes` / `Suffixes Cannot Be Changed` lock a side: every mod of it is kept by a reroll and a Scouring
  and cannot be removed by an Annulment; the metamod sits on the other side, so it goes with a reroll
  (unless it is fractured, or the other lock keeps that side too). An open slot of a locked side still fills.
* `Cannot roll Attack` / `Caster Modifiers` keep the mods carrying that tag (the `implicit_tags` of the
  data) out of an Exalted Orb's pool, out of an Annulment's candidates and out of the draws of a reroll
  that leaves the metamod on the item (a reroll that removes it is not filtered); a tagged Harvest reforge
  filters its guaranteed mod only, the draws that follow still see every mod.
* An Orb of Annulment removes one of the mods that are not fractured, not on a locked side and without a
  blocked tag, uniformly; the metamod of the other side is one of them. The rarity stays.
* A Fracturing Orb fractures one of all the mods of the item (a crafted mod and a metamod included), uniformly.
* An Exalted Orb adds one mod, drawn in proportion to its weight from both sides together among the mods of
  the pool that have no blocked tag, whose family is not on the item and whose side has room (three mods a side).
* A Chaos Orb or a tagged reforge keeps the fractured mods and those of a locked side, which count inside
  a total of 4, 5 or 6 mods (8:3:1), then draws one mod at a time, as `abstraction_oracle.py` does.
* An Orb of Scouring leaves the kept mods and the rarity they allow (normal for none, magic for one, rare for more).

Every finished item is a validated `Item`: a drawn mod has the tier it has among the mods of its type that
can spawn with the item's tags (an influence tag included, `tier_table` here), every value at the low end of
its range, so a draw that broke a capacity or a family rule fails here, not silently.
"""

import dataclasses
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping
from fractions import Fraction

from crafting_system.actions import build_pool
from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

CAP = 3
SIDES = ("prefix", "suffix")
TOTALS = {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}
FRACTURE_MIN_MODS = 4

LOCK_PREFIXES = "ItemGenerationCannotChangePrefixes"
LOCK_SUFFIXES = "ItemGenerationCannotChangeSuffixes"
NO_ATTACK = "ItemGenerationCannotRollAttackAffixes"
NO_CASTER = "ItemGenerationCannotRollCasterAffixes"
MULTIMOD = "ItemGenerationCanHaveMultipleCraftedMods"
LOCKS = {LOCK_PREFIXES: "prefix", LOCK_SUFFIXES: "suffix"}
TAG_BLOCKS = {NO_ATTACK: "attack", NO_CASTER: "caster"}

CLASS_KEYS = {"Amulet": "amulet", "Bow": "bow", "Quiver": "quiver"}
INFLUENCE_KEYS = {Influence.HUNTER: "basilisk"}


# --- what the metamods on an item say ------------------------------------------------------------


def side_of(data: GameData, entry: ExplicitMod) -> str:
    return data.mods[entry.mod_id].generation_type


def held_families(data: GameData, item: Item) -> set[str]:
    return {family for entry in item.mods for family in data.mods[entry.mod_id].families}


def locked_sides(data: GameData, item: Item) -> set[str]:
    """The sides ("prefix", "suffix") whose mods a lock metamod on `item` protects."""
    return {LOCKS[family] for family in held_families(data, item) if family in LOCKS}


def blocked_tags(data: GameData, item: Item) -> set[str]:
    """The tags the Attack and Caster metamods on `item` keep out of a draw."""
    return {TAG_BLOCKS[family] for family in held_families(data, item) if family in TAG_BLOCKS}


def carries(data: GameData, mod_id: str, tags: set[str]) -> bool:
    """Whether the mod has one of `tags` among its implicit tags."""
    return bool(tags & set(data.mods[mod_id].implicit_tags))


def kept_by_reroll(data: GameData, item: Item) -> tuple[ExplicitMod, ...]:
    """What a reroll and a Scouring leave on the item: the fractured mods and every mod of a locked side."""
    locked = locked_sides(data, item)
    return tuple(entry for entry in item.mods if entry.fractured or side_of(data, entry) in locked)


# --- tiers and rolls --------------------------------------------------------------------------------


def spawn_tags(data: GameData, base_id: str, influences: Iterable[Influence] = ()) -> frozenset[str]:
    """The tags the spawn weights see: the base's tags and one `<class key>_<influence key>` per influence."""
    base = data.base_items[base_id]
    return frozenset(base.tags) | {f"{CLASS_KEYS[base.item_class]}_{INFLUENCE_KEYS[i]}" for i in influences}


def tier_table(data: GameData, base_id: str, influences: Iterable[Influence] = ()) -> dict[str, int]:
    """The tier of every mod that can spawn with these tags, among the mods of its (type, generation type, domain)."""
    tags = spawn_tags(data, base_id, influences)
    groups: dict[tuple[str, str, str], list[Mod]] = defaultdict(list)
    for mod in data.mods.values():
        first = next((entry.weight for entry in mod.spawn_weights if entry.tag in tags), 0)
        if first > 0:
            groups[(mod.type, mod.generation_type, mod.domain)].append(mod)
    return {
        mod.id: 1 + sum(other.required_level > mod.required_level for other in group)
        for group in groups.values()
        for mod in group
    }


def low_roll(data: GameData, mod_id: str, tier: int = 1, **flags: bool) -> ExplicitMod:
    """The mod at `tier` with every stat at the low end of its range."""
    values = tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)
    return ExplicitMod(mod_id, tier, values, **flags)


def _drawn(data: GameData, tiers: Mapping[str, int], mod_id: str) -> ExplicitMod:
    return low_roll(data, mod_id, tiers.get(mod_id, 1))


# --- the removals and the Fracturing Orb --------------------------------------------------------------


def annulled(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """An Orb of Annulment on `start`: one removable mod gone, each with chance 1/n."""
    locked, blocked = locked_sides(data, start), blocked_tags(data, start)
    removable = [
        entry
        for entry in start.mods
        if not entry.fractured and side_of(data, entry) not in locked and not carries(data, entry.mod_id, blocked)
    ]
    if not removable:
        raise ValueError("nothing to remove: the oracle is not asked about refusals")
    share = Fraction(1, len(removable))
    return [(start.remove_mod(data, entry.mod_id), share) for entry in removable]


def fracture_one(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """A Fracturing Orb on a rare, uninfluenced item of 4 or more mods with no fractured mod: one mod fractured, 1/n each."""
    if start.rarity is not Rarity.RARE or len(start.mods) < FRACTURE_MIN_MODS or start.influences or start.fractured_mods:
        raise ValueError("the orb refuses this item: the oracle is not asked about refusals")
    share = Fraction(1, len(start.mods))
    return [
        (start.changed(data, mods=tuple(dataclasses.replace(m, fractured=m is entry) for m in start.mods)), share)
        for entry in start.mods
    ]


def scoured(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """An Orb of Scouring: the kept mods (fractured, locked side) stay, the rarity follows their number."""
    kept = kept_by_reroll(data, start)
    rarity = Rarity.NORMAL if not kept else Rarity.MAGIC if len(kept) == 1 else Rarity.RARE
    return [(start.changed(data, rarity=rarity, mods=kept), Fraction(1))]


def crafted(data: GameData, start: Item, mod_id: str) -> list[tuple[Item, Fraction]]:
    """A bench craft that puts the crafted mod `mod_id` on `start`: one item, chance 1.

    The bench refuses (`ValueError`) a normal item or one with no mod, a family already on the item, a full side
    and an item that holds as many crafted mods as it may (one, three with the multimod).
    """
    mod = data.mods[mod_id]
    if start.rarity is Rarity.NORMAL or not start.mods:
        raise ValueError("no craft on a normal item or on one with no mod")
    if any(set(mod.families) & set(data.mods[entry.mod_id].families) or entry.mod_id == mod_id for entry in start.mods):
        raise ValueError("a family of the craft is on the item")
    if sum(side_of(data, entry) == mod.generation_type for entry in start.mods) >= CAP:
        raise ValueError("no free slot on the side of the craft")
    limit = 3 if MULTIMOD in held_families(data, start) else 1
    if sum(entry.crafted for entry in start.mods) >= limit:
        raise ValueError("the item holds as many crafted mods as it may")
    return [(start.add_mod(data, low_roll(data, mod_id, 1, crafted=True)), Fraction(1))]


def closure(
    start: Item, steps: Iterable[Callable[[Item], list[tuple[Item, Fraction]]]]
) -> set[Item]:
    """Every concrete item that `steps` can reach from `start`, `start` included; a step that refuses (`ValueError`) is skipped."""
    seen, queue = {start}, [start]
    while queue:
        item = queue.pop()
        for step in steps:
            try:
                results = step(item)
            except ValueError:
                continue
            for after, _ in results:
                if after not in seen:
                    seen.add(after)
                    queue.append(after)
    return seen


# --- the draws: the Exalted Orb and the rerolls ------------------------------------------------------------


def exalted(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """An Exalted Orb on a rare `start`: one mod drawn by weight among those the metamods and the slots allow."""
    blocked = blocked_tags(data, start)
    room = {side: CAP - sum(side_of(data, entry) == side for entry in start.mods) for side in SIDES}
    candidates = [
        (entry.mod, entry.weight)
        for family in build_pool(data, start, tag_filter=False)
        if room[family.side.value] > 0
        for entry in family.mods
        if not carries(data, entry.mod.id, blocked)
    ]
    if not candidates:
        raise ValueError("no mod can be added: the oracle is not asked about refusals")
    whole = sum((weight for _, weight in candidates), Fraction(0))
    tiers = tier_table(data, start.base_id, start.influences)
    return [(start.add_mod(data, _drawn(data, tiers, mod.id)), weight / whole) for mod, weight in candidates]


def rerolled(
    data: GameData, start: Item, tag: str | None = None, totals: Mapping[int, Fraction] | None = None
) -> list[tuple[Item, Fraction]]:
    """A Chaos Orb (no `tag`) or a tagged Harvest reforge on a rare `start`: every finished item with its chance.

    A Chaos Orb draws from the pool without the tags that a metamod it leaves on the item blocks; a reforge
    draws its first mod among the tagged mods that carry no such tag, the others from the whole pool.
    Raises `ValueError` when a reforge has no tagged mod to start with.
    """
    kept = kept_by_reroll(data, start)
    retained = start.changed(data, rarity=Rarity.RARE, mods=kept)
    blocked = blocked_tags(data, retained)
    room = {side: CAP - sum(side_of(data, entry) == side for entry in retained.mods) for side in SIDES}
    # (mod, family, side, weight) of every mod of the pool, the tag filter off
    every = [
        (entry.mod, family.family, family.side.value, entry.weight)
        for family in build_pool(data, retained, tag_filter=False)
        for entry in family.mods
    ]
    candidates = every if tag is not None else [c for c in every if not carries(data, c[0].id, blocked)]
    by_id = {mod.id: (family, side) for mod, family, side, _ in every}
    options: dict[frozenset[str], list[tuple[Mod, str, str, Fraction]]] = {}

    def open_now(drawn: frozenset[str]) -> list[tuple[Mod, str, str, Fraction]]:
        if drawn not in options:
            families = {by_id[mod_id][0] for mod_id in drawn}
            used = Counter(by_id[mod_id][1] for mod_id in drawn)
            options[drawn] = [c for c in candidates if c[1] not in families and used[c[2]] < room[c[2]]]
        return options[drawn]

    def advance(layer: Mapping[frozenset[str], Fraction]) -> dict[frozenset[str], Fraction]:
        following: dict[frozenset[str], Fraction] = defaultdict(Fraction)
        for drawn, chance in layer.items():
            choices = open_now(drawn)
            if not choices:
                following[drawn] += chance
                continue
            whole = sum((c[3] for c in choices), Fraction(0))
            for mod, _, _, weight in choices:
                following[drawn | {mod.id}] += chance * weight / whole
        return following

    layer: dict[frozenset[str], Fraction] = {frozenset(): Fraction(1)}
    if tag is not None:
        tagged = [
            c
            for c in every
            if tag in c[0].implicit_tags and not carries(data, c[0].id, blocked) and room[c[2]] > 0
        ]
        if not tagged:
            raise ValueError(f"no {tag} mod can be drawn first")
        whole = sum((c[3] for c in tagged), Fraction(0))
        layer = {frozenset({c[0].id}): c[3] / whole for c in tagged}
    totals = TOTALS if totals is None else totals
    picks_of = {total: max(0, total - len(kept) - (tag is not None)) for total in totals}
    layers = [layer]
    for _ in range(max(picks_of.values())):
        layers.append(advance(layers[-1]))
    outcome: dict[frozenset[str], Fraction] = defaultdict(Fraction)
    for total, chance in totals.items():
        for drawn, inner in layers[picks_of[total]].items():
            outcome[drawn] += chance * inner
    assert sum(outcome.values()) == 1
    tiers = tier_table(data, start.base_id, start.influences)
    return [
        (retained.changed(data, mods=(*retained.mods, *(_drawn(data, tiers, mod_id) for mod_id in drawn))), chance)
        for drawn, chance in outcome.items()
    ]


# --- composing and comparing -----------------------------------------------------------------------------


def then(
    finished: list[tuple[Item, Fraction]], step: Callable[[Item], list[tuple[Item, Fraction]]]
) -> list[tuple[Item, Fraction]]:
    """The finished items of doing `step` on each item of `finished`, the chances multiplied and added up per item."""
    merged: dict[Item, Fraction] = defaultdict(Fraction)
    for item, chance in finished:
        for after, inner in step(item):
            merged[after] += chance * inner
    return list(merged.items())


def hold_chance(finished: list[tuple[Item, Fraction]], mod_ids: set[str]) -> Fraction:
    """The chance that the finished item holds every mod of `mod_ids`."""
    return sum(
        (chance for item, chance in finished if mod_ids <= {entry.mod_id for entry in item.mods}),
        Fraction(0),
    )


def compose(
    first: Mapping[Hashable, Fraction], step: Callable[[Hashable], Mapping[Hashable, Fraction]]
) -> dict[Hashable, Fraction]:
    """The distribution of the state after `step` run on every state of `first` (the kernels one after the other)."""
    merged: dict[Hashable, Fraction] = defaultdict(Fraction)
    for state, chance in first.items():
        for after, inner in step(state).items():
            merged[after] += chance * inner
    return dict(merged)
