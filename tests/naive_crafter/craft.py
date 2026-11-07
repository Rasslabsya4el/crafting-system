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

The later uses (tickets #608 to #610): a fossil set changes the weight of each mod of the pool by its tags (`fossils.py`); the Harvest reforge draws
one mod of a tag first; the Exalted Orb adds a mod to a rare item; the Orb of Annulment removes one; the Fracturing Orb fractures one; the bench
adds the metamods (`Cannot roll Attack Modifiers`, `Cannot roll Caster Modifiers`, `Can have up to 3 Crafted Modifiers`) and Remove Crafted Mods
takes the crafted mods off. A metamod on the item is a crafted mod whose group says what it does (`METAMOD_FILTER`, `MULTIMOD`, `LOCKS`).
"""

import bisect
from dataclasses import dataclass
from random import Random

from independent import ladder as shared

from .rules import CAPACITY, MAGIC_COUNTS, RARE_COUNTS

REJECTIONS = 20  # picks of the whole pool tried before the allowed mods are listed
# the groups of the metamods in the export, and what each does (rules `metamod_tag_is_implicit_tag`, `multimod_raises_crafted_limit`, `metamod_essence_refused`)
METAMOD_FILTER = {"ItemGenerationCannotRollAttackAffixes": "attack", "ItemGenerationCannotRollCasterAffixes": "caster"}  # group -> the tag no add may have
MULTIMOD = "ItemGenerationCanHaveMultipleCraftedMods"  # the item may hold three crafted mods
LOCKS = frozenset({"ItemGenerationCannotChangePrefixes", "ItemGenerationCannotChangeSuffixes"})  # not played here: they protect a side from rerolls
CRAFTED_LIMIT = {False: 1, True: 3}  # crafted mods an item holds, without and with the multimod (rules `bench_one_crafted_mod`, `multimod_raises_crafted_limit`)
FRACTURE_MIN_MODS = 4  # rule `fracturing_needs_four_mods`


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
    """How many mods a reroll leaves, by weight: the rules `magic_mod_count` and `rare_mod_count`. A test may change them, or turn a rule off, to see a wrong law fail."""

    magic: tuple[tuple[int, int], ...] = tuple(MAGIC_COUNTS.items())
    rare: tuple[tuple[int, int], ...] = tuple(RARE_COUNTS.items())
    # three more rules a test can turn off, each to see a covered route disagree with the planner (rules `level_gate`, `family_exclusion`, `one_pool_for_both_sides`)
    level_gate: bool = True
    family_exclusion: bool = True
    one_pool: bool = True  # False: a side is chosen first, with equal chance among the open sides, and the mod is drawn from that side
    # the laws of tickets #608 to #610, each with a test that turns it off and sees a covered route leave the 4-standard-error line
    fossil_boost: bool = True  # False: a fossil's boost factors do not apply (rule `fossil_factors_stack_per_tag`)
    fossil_block: bool = True  # False: a blocked tag does not remove the mod (rule `fossil_block_wins`)
    harvest_guarantee: bool = True  # False: a Harvest reforge draws no mod of its tag first (rule `harvest_guaranteed_draw_first`)
    annul_spares_fractured: bool = True  # False: an Orb of Annulment may remove a fractured mod (rule `annulment_spares_fractured`)
    fracture_needs_four: bool = True  # False: a Fracturing Orb takes an item of fewer than four mods (rule `fracturing_needs_four_mods`)
    metamod_filter: bool = True  # False: `Cannot roll Attack Modifiers` filters nothing (rules `metamod_filters_adds`, `metamod_annulment_respects_tags`)
    metamod_refuses_rerolls: bool = True  # False: an essence or a resonator is taken by an item with a metamod (rule `metamod_essence_refused`)
    multimod: bool = True  # False: `Can have up to 3 Crafted Modifiers` lifts nothing (rule `multimod_raises_crafted_limit`)

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
        self._tags: dict[str, frozenset[str]] = {}

    def tags(self, mod_id: str) -> frozenset[str]:
        """The `implicit_tags` of a mod (rules `fossil_tags_are_implicit_tags`, `harvest_tag_is_implicit_tag`, `metamod_tag_is_implicit_tag`)."""
        found = self._tags.get(mod_id)
        if found is None:
            found = self._tags[mod_id] = frozenset(self.mods[mod_id].get("implicit_tags") or ())
        return found

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
    """The mods that can be drawn on an item of one base at one level, with cumulative weights.

    `factor` (a function of the mod's tags, for a fossil set) multiplies each weight and a zero removes the mod; `need_tag` keeps only the mods
    with that tag (the guaranteed draw of a Harvest reforge).
    """

    def __init__(self, book: Book, tags, domain: str, level_cap: int, factor=None, need_tag: str | None = None):
        ids, weights = [], []
        for mod_id in sorted(book.mods):
            mod = book.mods[mod_id]
            if not shared.is_natural(mod_id, mod, tags, domain) or mod["required_level"] > level_cap:
                continue
            if need_tag is not None and need_tag not in book.tags(mod_id):
                continue
            weight = shared.spawn_weight(mod, tags) * generation_multiplier(mod, tags)
            if factor is not None:
                weight *= factor(book.tags(mod_id))
            if weight > 0:
                ids.append(mod_id)
                weights.append(weight)
        self.book = book
        self.ids = ids
        self.weights = weights
        self.sides = [book.side(mod_id) for mod_id in ids]
        self.groups = [book.groups(mod_id) for mod_id in ids]
        self.mod_tags = [book.tags(mod_id) for mod_id in ids]
        self.cumulative = []
        total = 0.0
        for weight in weights:
            total += weight
            self.cumulative.append(total)
        self.total = total

    def draw(
        self, rng: Random, blocked: frozenset[str] | set[str], closed: tuple[str, ...], barred: frozenset[str] | set[str] = frozenset()
    ) -> str | None:
        """A mod chosen with chance weight / (sum of the allowed weights); None when no mod is allowed.

        Allowed: not of a group in `blocked`, not of a side in `closed`, and with none of the tags in `barred` (a metamod on the item).
        """
        if not self.ids:
            return None
        cumulative, sides, groups, mod_tags = self.cumulative, self.sides, self.groups, self.mod_tags
        for _ in range(REJECTIONS):
            index = bisect.bisect_right(cumulative, rng.random() * self.total)
            if index >= len(sides):
                index = len(sides) - 1
            if sides[index] not in closed and blocked.isdisjoint(groups[index]) and (not barred or barred.isdisjoint(mod_tags[index])):
                return self.ids[index]
        allowed = [
            i
            for i in range(len(self.ids))
            if self.sides[i] not in closed and blocked.isdisjoint(self.groups[i]) and (not barred or barred.isdisjoint(self.mod_tags[i]))
        ]
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
        self.influences = tuple(influences)
        self.tags = shared.item_tags(self.base["tags"], influences, self.item_class)
        self.domain = self.base["domain"]
        self.book = Book(export.mods)
        self.laws = laws or Laws()
        self._pools: dict[tuple, Pool] = {}

    def pool(self, level_cap: int | None = None, fossils=None, need_tag: str | None = None) -> Pool:
        """The pool at a level cap; `fossils` (a `fossils.FossilSet`) changes the weights, `need_tag` keeps one tag."""
        cap = self.item_level if level_cap is None else min(level_cap, self.item_level)
        if not self.laws.level_gate:
            cap = 10**6
        key = (cap, fossils.key if fossils is not None else None, need_tag)
        if key not in self._pools:
            factor = None
            if fossils is not None:
                factor = lambda tags: fossils.factor(tags, self.laws.fossil_boost, self.laws.fossil_block)  # noqa: E731
            self._pools[key] = Pool(self.book, self.tags, self.domain, cap, factor, need_tag)
        return self._pools[key]

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

    def barred_tags(self, mods) -> frozenset[str]:
        """The tags no add may carry because of the metamods among `mods` (rules `metamod_filters_adds`, `metamod_reroll_needs_retained_carrier`)."""
        if not self.laws.metamod_filter:
            return frozenset()
        return frozenset(METAMOD_FILTER[group] for held in mods for group in self.book.groups(held.mod_id) if group in METAMOD_FILTER)

    def has_metamod(self, mods) -> bool:
        """Whether a metamod other than the multimod is among `mods` (rule `metamod_essence_refused`)."""
        return any(group in METAMOD_FILTER or group in LOCKS for held in mods for group in self.book.groups(held.mod_id))

    def _add(self, mods: list[Held], mod_id: str, rng: Random, **flags) -> None:
        mods.append(Held(mod_id, self.book.roll(mod_id, rng), **flags))

    def _fill(self, mods: list[Held], total: int, rarity: str, pool: Pool, rng: Random) -> None:
        """Add random mods until the item holds `total` (the kept ones included) or no mod is allowed any more."""
        room = CAPACITY[rarity]
        counts = self.side_counts(mods)
        blocked = self.groups_of(mods) if self.laws.family_exclusion else set()
        barred = self.barred_tags(mods)
        while len(mods) < total:
            closed = tuple(side for side in ("prefix", "suffix") if counts[side] >= room)
            if not self.laws.one_pool and not closed:  # both sides open: choose the side first
                closed = ("prefix",) if rng.random() < 0.5 else ("suffix",)
            mod_id = pool.draw(rng, blocked, closed, barred)
            if mod_id is None:
                return  # a dry pool leaves fewer mods
            self._add(mods, mod_id, rng)
            counts[self.book.side(mod_id)] += 1
            if self.laws.family_exclusion:
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
        if self.laws.metamod_refuses_rerolls and self.has_metamod(item.mods):
            raise Refused("an essence is not taken by an item with a metamod")
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
        crafted = sum(held.crafted for held in item.mods)
        multimod = self.laws.multimod and any(MULTIMOD in self.book.groups(held.mod_id) for held in item.mods)
        if crafted >= CRAFTED_LIMIT[multimod]:
            raise Refused("the item already holds as many crafted mods as it may")
        if self.book.groups(mod_id) & self.groups_of(item.mods):
            raise Refused("the item already has a mod of the crafted mod's group")
        if self.free_slots(item, self.book.side(mod_id)) <= 0:
            raise Refused("no open slot on the crafted mod's side")
        return Item(item.rarity, (*item.mods, Held(mod_id, self.book.roll(mod_id, rng), crafted=True)))

    def remove_crafted(self, item: Item) -> Item:
        """Remove Crafted Mods: every crafted mod goes, metamods too, and their effects end; a fractured mod stays (rule `remove_crafted_mods_removes_all`)."""
        if item.rarity == "normal" or not any(held.crafted and not held.fractured for held in item.mods):
            raise Refused("the item holds no crafted mod to remove")
        return Item(item.rarity, tuple(held for held in item.mods if not held.crafted or held.fractured))

    # -- the uses of tickets #608 to #610 ---------------------------------------------------------------------------

    def fossil(self, item: Item, rng: Random, fossils) -> Item:
        """A Chaotic resonator with the fossils `fossils` (a `fossils.FossilSet`): a Chaos Orb whose pool weights the fossils change."""
        if item.rarity != "rare":
            raise Refused("a resonator takes a rare item only")
        if self.laws.metamod_refuses_rerolls and self.has_metamod(item.mods):
            raise Refused("a resonator is not taken by an item with a metamod")
        why = fossils.refuses(self.base["tags"])
        if why:
            raise Refused(why)
        mods = [held for held in item.mods if held.fractured]
        self._fill(mods, self.laws.total("rare", rng), "rare", self.pool(fossils=fossils), rng)
        return Item("rare", tuple(mods))

    def harvest(self, item: Item, rng: Random, tag: str) -> Item:
        """A tagged Harvest reforge: a Chaos Orb that first draws one mod with `tag` (it counts in the total)."""
        if item.rarity != "rare":
            raise Refused("a Harvest reforge takes a rare item only")
        if self.has_metamod(item.mods):
            raise Unsupported("a Harvest reforge on an item with a metamod: this player does not have the metamods' effect on a reforge (they filter the first mod only)")
        mods = [held for held in item.mods if held.fractured]
        if self.laws.harvest_guarantee:
            tagged = self.pool(need_tag=tag)
            if not tagged.ids:
                raise Refused(f"the pool of the item holds no mod with the tag {tag}")
            counts = self.side_counts(mods)
            closed = tuple(side for side in ("prefix", "suffix") if counts[side] >= CAPACITY["rare"])
            blocked = self.groups_of(mods) if self.laws.family_exclusion else set()
            mod_id = tagged.draw(rng, blocked, closed)
            if mod_id is None:
                raise Refused(f"no mod with the tag {tag} fits a free slot of the item")
            self._add(mods, mod_id, rng)
        self._fill(mods, self.laws.total("rare", rng), "rare", self.pool(), rng)
        return Item("rare", tuple(mods))

    def exalt(self, item: Item, rng: Random) -> Item:
        if item.rarity != "rare":
            raise Refused("an Exalted Orb takes a rare item only")
        mods = list(item.mods)
        self._fill(mods, len(mods) + 1, "rare", self.pool(), rng)
        if len(mods) == len(item.mods):
            raise Refused("no mod can be added")
        return Item("rare", tuple(mods))

    def annul(self, item: Item, rng: Random) -> Item:
        """Remove one mod, chosen with equal chance among the mods that can go: not a fractured one, not one a metamod protects."""
        if item.rarity == "normal":
            raise Refused("an Orb of Annulment takes a magic or a rare item only")
        barred = self.barred_tags(item.mods)
        candidates = [
            i
            for i, held in enumerate(item.mods)
            if (not held.fractured or not self.laws.annul_spares_fractured) and (not barred or barred.isdisjoint(self.book.tags(held.mod_id)))
        ]
        if not candidates:
            raise Refused("the item holds no mod an Orb of Annulment can remove")
        gone = candidates[int(rng.random() * len(candidates))]
        return Item(item.rarity, tuple(held for i, held in enumerate(item.mods) if i != gone))

    def fracture(self, item: Item, rng: Random) -> Item:
        """Fracture one mod of the item, chosen with equal chance among all its mods (crafted and metamods too)."""
        if item.rarity != "rare":
            raise Refused("a Fracturing Orb takes a rare item only")
        if self.influences or any(held.fractured for held in item.mods):
            raise Refused("a Fracturing Orb is not taken by an influenced item or one with a fractured mod")
        if self.laws.fracture_needs_four and len(item.mods) < FRACTURE_MIN_MODS:
            raise Refused("a Fracturing Orb needs at least four mods")
        if not item.mods:
            raise Refused("the item holds no mod to fracture")
        chosen = int(rng.random() * len(item.mods))
        return Item(
            item.rarity,
            tuple(Held(held.mod_id, held.values, True, held.crafted) if i == chosen else held for i, held in enumerate(item.mods)),
        )
