"""The resolved target and the goal check (ADR-0008).

Parsing turns every selector into mod ids and every stat count into a tuple, so a `Target` holds no
reference to the game data and `Target.is_met_by` needs none. A requirement is checked against each
explicit mod of the item on its own: a minimum tier and a minimum roll must hold on the same mod.
The tier is the one stored on the `ExplicitMod` (tier 1 is the best), never derived here, and how a
mod got onto the item (natural, fractured, crafted) matters only when `not_crafted` is set.

Implicits and quality are checked on their own (ADR-0027): an `ImplicitRequirement` is met by one
implicit of the item whose mod, Eldritch grade and rolled values all pass; a `QualityRequirement` by
the item's catalyst quality of the same type and at least the percent. Both compare the base roll
and the percent the item stores, never a value scaled by the quality (ADR-0029). An
`EnchantmentRequirement` is met when the item's one enchantment is among the acceptable ones
(ADR-0050).
"""

from dataclasses import dataclass
from pathlib import Path

from crafting_system.items import CatalystType, ExplicitMod, ImplicitMod, Influence, Item


@dataclass(frozen=True, slots=True)
class Requirement:
    """One mod wanted on the item.

    Exactly one of `family` (a family id) and `stat` (English stat text) is the selector as the owner
    wrote it; `mod_ids` is every mod that selector counts, or the one mod a `mod:` key names. `min_tier` is the worst tier accepted, so
    2 accepts tiers 1 and 2. `min_roll` has one entry per stat of the mod, None where any value will
    do. Rolls are the raw numbers of the game data.
    """

    family: str | None
    stat: str | None
    mod_ids: frozenset[str]
    min_tier: int | None = None
    min_roll: tuple[int | None, ...] | None = None
    not_crafted: bool = False

    def __post_init__(self) -> None:
        if (self.family is None) == (self.stat is None):
            raise ValueError("a requirement names exactly one of a family and a stat text")
        if not self.mod_ids:
            raise ValueError("a requirement needs at least one mod id")

    def is_met_by(self, item: Item) -> bool:
        """Whether one explicit mod of `item` is among `mod_ids` and passes every limit."""
        return any(self._counts(mod) for mod in item.mods)

    def _counts(self, mod: ExplicitMod) -> bool:
        if mod.mod_id not in self.mod_ids:
            return False
        if self.min_tier is not None and mod.tier > self.min_tier:
            return False
        if self.not_crafted and mod.crafted:
            return False
        if self.min_roll is None:
            return True
        if len(mod.values) != len(self.min_roll):
            return False
        return all(wanted is None or got >= wanted for wanted, got in zip(self.min_roll, mod.values))


@dataclass(frozen=True, slots=True)
class KOfN:
    """A k-of-n requirement: met when at least `at_least` of the members in `of` are met.

    Members are requirements or further k-of-n entries.
    """

    at_least: int
    of: tuple["Node", ...]

    def __post_init__(self) -> None:
        if not self.of:
            raise ValueError("a k-of-n entry needs at least one member")
        if not 1 <= self.at_least <= len(self.of):
            raise ValueError(f"at_least must be from 1 to {len(self.of)}, got {self.at_least}")

    def is_met_by(self, item: Item) -> bool:
        """Whether at least `at_least` members are met by `item`."""
        met = 0
        for member in self.of:
            if member.is_met_by(item):
                met += 1
                if met >= self.at_least:
                    return True
        return False


Node = Requirement | KOfN


@dataclass(frozen=True, slots=True)
class ImplicitRequirement:
    """One implicit mod wanted on the item.

    Exactly one of `family` and `stat` is the selector as the owner wrote it; `mod_ids` is every implicit
    mod that selector counts (the "in your Presence" variants only when a `mod:` key names one).
    `min_grade` is the lowest Eldritch grade accepted (1 Lesser to 6 Perfect), None when any grade does;
    it is set only for Eldritch implicits. `min_roll` has one entry per stat of the mod, None where any
    value will do. Rolls are the raw numbers of the game data, as stored on the item.

    `corrupted` marks a corrupted implicit (ADR-0036): `mod_ids` are then mods of the corrupted pool of the base at the
    target's item level, and only a corrupted item can hold one. A target with such an entry asks for a corrupted item.
    """

    family: str | None
    stat: str | None
    mod_ids: frozenset[str]
    min_grade: int | None = None
    min_roll: tuple[int | None, ...] | None = None
    corrupted: bool = False

    def __post_init__(self) -> None:
        if (self.family is None) == (self.stat is None):
            raise ValueError("an implicit requirement names exactly one of a family and a stat text")
        if not self.mod_ids:
            raise ValueError("an implicit requirement needs at least one mod id")

    def is_met_by(self, item: Item) -> bool:
        """Whether one implicit of `item` is among `mod_ids` and passes the grade and every roll."""
        if self.corrupted and not item.corrupted:
            return False
        return any(self._counts(entry) for entry in item.implicits)

    def _counts(self, entry: ImplicitMod) -> bool:
        if entry.mod_id not in self.mod_ids:
            return False
        if self.min_grade is not None and entry.grade < self.min_grade:
            return False
        if self.min_roll is None:
            return True
        if len(entry.values) != len(self.min_roll):
            return False
        return all(wanted is None or got >= wanted for wanted, got in zip(self.min_roll, entry.values))


@dataclass(frozen=True, slots=True)
class QualityRequirement:
    """The catalyst quality wanted: this `type` at `min_percent` (1 to 20) or more."""

    type: CatalystType
    min_percent: int

    def __post_init__(self) -> None:
        if not isinstance(self.type, CatalystType):
            raise ValueError("a quality requirement needs a CatalystType")
        if type(self.min_percent) is not int or self.min_percent < 1:
            raise ValueError("a quality requirement needs a whole minimum percent of 1 or more")

    def is_met_by(self, item: Item) -> bool:
        """Whether `item` has quality of this type and at least the percent."""
        quality = item.quality
        return quality is not None and quality.type is self.type and quality.percent >= self.min_percent


@dataclass(frozen=True, slots=True)
class EnchantmentRequirement:
    """The enchantment wanted: any one of `mod_ids`, the acceptable set the owner's entries stand for.

    `entries` are the entries as written (a mod id, a stat text or a bare tag), in file order. An item holds
    one enchantment, so there is only "any of"; the planner adds none the target does not name (ADR-0050).
    """

    entries: tuple[str, ...]
    mod_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not self.entries or not self.mod_ids:
            raise ValueError("an enchantment requirement needs at least one entry and one mod id")

    def is_met_by(self, item: Item) -> bool:
        """Whether the enchantment of `item` is one of `mod_ids`."""
        return item.enchantment in self.mod_ids


Condition = Node | ImplicitRequirement | QualityRequirement | EnchantmentRequirement


@dataclass(frozen=True, slots=True)
class Target:
    """The item the owner wants, and where a query starts from.

    `requirements` are all required at once, then `implicits` and `quality` when given. `start_item` is a fresh normal item of the base, item
    level and influences unless the file gave one. `price_file` is the path as resolved against the
    target file's folder; it is not read or checked here. `start_price` is the name the start item
    has in the price file (for example the buy spec's name), or None; it is not looked up here. `actions` names the
    kinds of actions the planner may use, or the labels of single actions (ADR-0024, ticket #70), or None for every kind it
    offers by default; the names are not checked here.
    `enchantment` is the acceptable set for the item's enchantment, or None when the target asks for none.
    `allow_corrupted` lets the goal be a corrupted item that has no corrupted implicit (ADR-0036); a target that asks for a
    corrupted implicit (`asks_corrupted`) takes a corrupted item too, and any other target is never met by one.
    `item_level_floor` and `tiers_top_at_item_level` are the author's word on how far the planner may plan below `item_level`
    (ADR-0061, `floor.py`): a stated lowest level, and the statement that the tiers written are the top tiers of `item_level`.
    """

    base_id: str
    item_level: int
    influences: frozenset[Influence]
    requirements: tuple[Node, ...]
    start_item: Item
    price_file: Path | None = None
    start_price: str | None = None
    implicits: tuple[ImplicitRequirement, ...] = ()
    quality: QualityRequirement | None = None
    actions: tuple[str, ...] | None = None
    enchantment: EnchantmentRequirement | None = None
    allow_corrupted: bool = False
    item_level_floor: int | None = None
    tiers_top_at_item_level: bool = False

    @property
    def asks_corrupted(self) -> bool:
        """Whether an implicit requirement is for a corrupted implicit: the goal is then a corrupted item."""
        return any(wish.corrupted for wish in self.implicits)

    @property
    def takes_corrupted(self) -> bool:
        """Whether a corrupted item can be the goal: the target asks for a corrupted implicit or allows a corrupted item."""
        return self.allow_corrupted or self.asks_corrupted

    def is_met_by(self, item: Item) -> bool:
        """Whether `item` meets every top-level requirement, every implicit requirement, the quality and the enchantment.

        A corrupted item is never a goal unless the target asks for a corrupted implicit or allows a corrupted item
        (`takes_corrupted`), whatever mods it holds (ADR-0036).
        """
        if item.corrupted and not self.takes_corrupted:
            return False
        return not self.unmet(item)

    def unmet(self, item: Item) -> tuple[Condition, ...]:
        """What `item` does not meet, in file order: requirements, then implicit requirements, then quality, then enchantment."""
        wanted: tuple[Condition, ...] = (*self.requirements, *self.implicits)
        if self.quality is not None:
            wanted = (*wanted, self.quality)
        if self.enchantment is not None:
            wanted = (*wanted, self.enchantment)
        return tuple(condition for condition in wanted if not condition.is_met_by(item))
