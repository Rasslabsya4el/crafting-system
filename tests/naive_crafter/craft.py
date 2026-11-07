"""Concrete items and the uses of the plain-spam orbs on them (ticket #555).

An item is a rarity and a list of held mods, each with its rolled values. A use takes an item and a random generator and gives the new
item, or raises `Refused` (the game would not take the orb, and nothing is spent). The rules each use reads are in `rules.py`, with
their sources; the mechanics read only the raw repoe-fork export (`mods.json`, `base_items.json`, `essences.json`,
`crafting_bench_options.json`) as plain dicts.

The draw (rules `DRAW`): the pool of an item is every mod of the base's domain that is a prefix or a suffix, not essence-only, not a
Battle Royale copy, with a first-match spawn weight above zero (times the generation weight / 100), and a required level at most the item
level (or the essence's cap). One add picks a mod with chance weight / sum of the weights of the mods that are still allowed: not of a
group the item holds, not of a side that is full. This is done by drawing from the whole pool and drawing again when the pick is not
allowed, which gives exactly that conditional chance; when twenty picks in a row are refused, the allowed mods are listed and drawn from.
"""

import bisect
from dataclasses import dataclass
from random import Random

from independent import ladder as shared

from .rules import CAPACITY, MAGIC_COUNTS, RARE_COUNTS

REJECTIONS = 20  # picks of the whole pool tried before the allowed mods are listed


class Refused(Exception):
    """The game does not take this orb on this item; nothing is spent."""


class Unsupported(Exception):
    """An action whose mechanic this player does not have (it names the mechanic)."""


@dataclass(frozen=True, slots=True)
class Held:
    """A mod on an item: its id, one rolled value per stat, fractured, crafted."""

    mod_id: str
    values: tuple[int, ...]
    fractured: bool = False
    crafted: bool = False


@dataclass(frozen=True, slots=True)
class Item:
    rarity: str  # normal, magic or rare
    mods: tuple[Held, ...] = ()


@dataclass(frozen=True)
class Laws:
    """How many mods a reroll leaves, by weight: the rules `magic_mod_count` and `rare_mod_count`. A test may change them to see a wrong law fail."""

    magic: tuple[tuple[int, int], ...] = tuple(MAGIC_COUNTS.items())
    rare: tuple[tuple[int, int], ...] = tuple(RARE_COUNTS.items())

    def total(self, rarity: str, rng: Random) -> int:
        weights = self.magic if rarity == "magic" else self.rare
        point = rng.random() * sum(weight for _, weight in weights)
        for count, weight in weights:
            point -= weight
            if point < 0:
                return count
        return weights[-1][0]


class Book:
    """The sides, groups and stat ranges of the mods of an export, read once."""

    def __init__(self, mods: dict):
        self.mods = mods
        self._side: dict[str, str] = {}
        self._groups: dict[str, frozenset[str]] = {}
        self._ranges: dict[str, tuple[tuple[int, int], ...]] = {}

    def side(self, mod_id: str) -> str:
        found = self._side.get(mod_id)
        if found is None:
            found = self._side[mod_id] = self.mods[mod_id]["generation_type"]
        return found

    def groups(self, mod_id: str) -> frozenset[str]:
        found = self._groups.get(mod_id)
        if found is None:
            found = self._groups[mod_id] = frozenset(self.mods[mod_id].get("groups") or ())
        return found

    def ranges(self, mod_id: str) -> tuple[tuple[int, int], ...]:
        found = self._ranges.get(mod_id)
        if found is None:
            found = self._ranges[mod_id] = tuple(
                (min(stat["min"], stat["max"]), max(stat["min"], stat["max"])) for stat in self.mods[mod_id]["stats"]
            )
        return found

    def roll(self, mod_id: str, rng: Random) -> tuple[int, ...]:
        """One uniform integer per stat, both ends included (rule `values_uniform_integers`)."""
        return tuple(low + int(rng.random() * (high - low + 1)) for low, high in self.ranges(mod_id))


def generation_multiplier(mod: dict, tags) -> float:
    """The first generation-weight entry whose tag the item has, as value / 100; 1 when there is none (rule `generation_weight_multiplier`)."""
    for entry in mod.get("generation_weights") or ():
        if entry["tag"] in tags:
            return entry["weight"] / 100
    return 1.0


class Pool:
    """The mods that can be drawn on an item of one base at one level, with cumulative weights."""

    def __init__(self, book: Book, tags, domain: str, level_cap: int):
        ids, weights = [], []
        for mod_id in sorted(book.mods):
            mod = book.mods[mod_id]
            if not shared.is_natural(mod_id, mod, tags, domain) or mod["required_level"] > level_cap:
                continue
            weight = shared.spawn_weight(mod, tags) * generation_multiplier(mod, tags)
            if weight > 0:
                ids.append(mod_id)
                weights.append(weight)
        self.book = book
        self.ids = ids
        self.weights = weights
        self.sides = [book.side(mod_id) for mod_id in ids]
        self.groups = [book.groups(mod_id) for mod_id in ids]
        self.cumulative = []
        total = 0.0
        for weight in weights:
            total += weight
            self.cumulative.append(total)
        self.total = total

    def draw(self, rng: Random, blocked: frozenset[str] | set[str], closed: tuple[str, ...]) -> str | None:
        """A mod chosen with chance weight / (sum of the allowed weights); None when no mod is allowed."""
        if not self.ids:
            return None
        cumulative, sides, groups = self.cumulative, self.sides, self.groups
        for _ in range(REJECTIONS):
            index = bisect.bisect_right(cumulative, rng.random() * self.total)
            if index >= len(sides):
                index = len(sides) - 1
            if sides[index] not in closed and blocked.isdisjoint(groups[index]):
                return self.ids[index]
        allowed = [i for i in range(len(self.ids)) if self.sides[i] not in closed and blocked.isdisjoint(self.groups[i])]
        if not allowed:
            return None
        point = rng.random() * sum(self.weights[i] for i in allowed)
        for i in allowed:
            point -= self.weights[i]
            if point < 0:
                return self.ids[i]
        return self.ids[allowed[-1]]


class Crafter:
    """The uses of the orbs, on the items of one base at one item level."""

    def __init__(self, export, base_id: str, item_level: int, influences=(), laws: Laws | None = None):
        """`export` is a `independent.export.RawExport`; `base_id` the metadata id of the base."""
        self.export = export
        self.base_id = base_id
        self.base = export.bases[base_id]
        self.item_class = self.base["item_class"]
        self.item_level = item_level
        self.tags = shared.item_tags(self.base["tags"], influences, self.item_class)
        self.domain = self.base["domain"]
        self.book = Book(export.mods)
        self.laws = laws or Laws()
        self._pools: dict[int, Pool] = {}

    def pool(self, level_cap: int | None = None) -> Pool:
        cap = self.item_level if level_cap is None else min(level_cap, self.item_level)
        if cap not in self._pools:
            self._pools[cap] = Pool(self.book, self.tags, self.domain, cap)
        return self._pools[cap]

    # -- the bookkeeping of an item -----------------------------------------------------------------------------

    def side_counts(self, mods) -> dict[str, int]:
        counts = {"prefix": 0, "suffix": 0}
        for held in mods:
            counts[self.book.side(held.mod_id)] += 1
        return counts

    def groups_of(self, mods) -> set[str]:
        found: set[str] = set()
        for held in mods:
            found |= self.book.groups(held.mod_id)
        return found

    def free_slots(self, item: Item, side: str) -> int:
        return CAPACITY[item.rarity] - self.side_counts(item.mods)[side]

    def _add(self, mods: list[Held], mod_id: str, rng: Random, **flags) -> None:
        mods.append(Held(mod_id, self.book.roll(mod_id, rng), **flags))

    def _fill(self, mods: list[Held], total: int, rarity: str, pool: Pool, rng: Random) -> None:
        """Add random mods until the item holds `total` (the kept ones included) or no mod is allowed any more."""
        room = CAPACITY[rarity]
        counts = self.side_counts(mods)
        blocked = self.groups_of(mods)
        while len(mods) < total:
            closed = tuple(side for side in ("prefix", "suffix") if counts[side] >= room)
            mod_id = pool.draw(rng, blocked, closed)
            if mod_id is None:
                return  # a dry pool leaves fewer mods
            self._add(mods, mod_id, rng)
            counts[self.book.side(mod_id)] += 1
            blocked |= self.book.groups(mod_id)

    # -- the uses ---------------------------------------------------------------------------------------------

    def transmute(self, item: Item, rng: Random) -> Item:
        if item.rarity != "normal":
            raise Refused("an Orb of Transmutation takes a normal item only")
        mods: list[Held] = []
        self._fill(mods, self.laws.total("magic", rng), "magic", self.pool(), rng)
        return Item("magic", tuple(mods))

    def alter(self, item: Item, rng: Random) -> Item:
        if item.rarity != "magic":
            raise Refused("an Orb of Alteration takes a magic item only")
        mods = [held for held in item.mods if held.fractured]
        self._fill(mods, self.laws.total("magic", rng), "magic", self.pool(), rng)
        return Item("magic", tuple(mods))

    def augment(self, item: Item, rng: Random) -> Item:
        if item.rarity != "magic":
            raise Refused("an Orb of Augmentation takes a magic item only")
        counts = self.side_counts(item.mods)
        if all(counts[side] >= CAPACITY["magic"] for side in counts):
            raise Refused("the magic item has no open prefix or suffix")
        mods = list(item.mods)
        self._fill(mods, len(mods) + 1, "magic", self.pool(), rng)
        if len(mods) == len(item.mods):
            raise Refused("no mod can be added to the open side")
        return Item("magic", tuple(mods))

    def regal(self, item: Item, rng: Random) -> Item:
        if item.rarity != "magic":
            raise Refused("a Regal Orb takes a magic item only")
        mods = list(item.mods)
        self._fill(mods, len(mods) + 1, "rare", self.pool(), rng)
        if len(mods) == len(item.mods):
            raise Refused("no mod can be added")
        return Item("rare", tuple(mods))

    def chaos(self, item: Item, rng: Random) -> Item:
        if item.rarity != "rare":
            raise Refused("a Chaos Orb takes a rare item only")
        mods = [held for held in item.mods if held.fractured]
        self._fill(mods, self.laws.total("rare", rng), "rare", self.pool(), rng)
        return Item("rare", tuple(mods))

    def essence(self, item: Item, rng: Random, record: dict) -> Item:
        """`record` is the essence's entry of `essences.json`."""
        if item.rarity == "magic" or (item.rarity == "rare" and record["level"] < 5):
            raise Refused("this essence does not take an item of this rarity")
        forced = (record.get("mods") or {}).get(self.item_class)
        if forced is None:
            raise Refused(f"this essence has no mod for the item class {self.item_class}")
        mods = [held for held in item.mods if held.fractured]
        if self.book.groups(forced) & self.groups_of(mods):
            raise Refused("the item already has a mod of the forced mod's group")
        self._add(mods, forced, rng)  # whatever the item level (rule `essence_forced_mod_ignores_item_level`)
        pool = self.pool(record.get("item_level_restriction"))
        self._fill(mods, self.laws.total("rare", rng), "rare", pool, rng)
        return Item("rare", tuple(mods))

    def bench(self, item: Item, rng: Random, mod_id: str) -> Item:
        if item.rarity == "normal":
            raise Refused("a normal item has no slot for a crafted mod")
        if any(held.crafted for held in item.mods):
            raise Refused("the item already holds a crafted mod")
        if self.book.groups(mod_id) & self.groups_of(item.mods):
            raise Refused("the item already has a mod of the crafted mod's group")
        if self.free_slots(item, self.book.side(mod_id)) <= 0:
            raise Refused("no open slot on the crafted mod's side")
        return Item(item.rarity, (*item.mods, Held(mod_id, self.book.roll(mod_id, rng), crafted=True)))
