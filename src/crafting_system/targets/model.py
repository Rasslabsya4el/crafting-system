"""The resolved target and the goal check (ADR-0008).

Parsing turns every selector into mod ids and every stat count into a tuple, so a `Target` holds no
reference to the game data and `Target.is_met_by` needs none. A requirement is checked against each
explicit mod of the item on its own: a minimum tier and a minimum roll must hold on the same mod.
The tier is the one stored on the `ExplicitMod` (tier 1 is the best), never derived here, and how a
mod got onto the item (natural, fractured, crafted) matters only when `not_crafted` is set.
"""

from dataclasses import dataclass
from pathlib import Path

from crafting_system.items import ExplicitMod, Influence, Item


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
class Target:
    """The item the owner wants, and where a query starts from.

    `requirements` are all required at once. `start_item` is a fresh normal item of the base, item
    level and influences unless the file gave one. `price_file` is the path as resolved against the
    target file's folder; it is not read or checked here. `start_price` is the name the start item
    has in the price file (for example the buy spec's name), or None; it is not looked up here.
    """

    base_id: str
    item_level: int
    influences: frozenset[Influence]
    requirements: tuple[Node, ...]
    start_item: Item
    price_file: Path | None = None
    start_price: str | None = None

    def is_met_by(self, item: Item) -> bool:
        """Whether `item` meets every top-level requirement."""
        return not self.unmet(item)

    def unmet(self, item: Item) -> tuple[Node, ...]:
        """The top-level requirements `item` does not meet, in file order."""
        return tuple(node for node in self.requirements if not node.is_met_by(item))
