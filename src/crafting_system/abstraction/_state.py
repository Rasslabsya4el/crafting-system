"""The compressed state: flags, the fractured mods, the other mods as slots, and the status of each leaf."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from crafting_system.items import Influence, Rarity, Side

from ._goal import Status, Wanted


@dataclass(frozen=True)
class Flags:
    """What the actions look at besides the mods: the rarity, corruption and influences."""

    rarity: Rarity
    corrupted: bool
    influences: frozenset[Influence]


@dataclass(frozen=True)
class FracturedMod:
    """A fractured mod: the canonical id of its kind and what it gives each leaf of the goal.

    `mod_id` is a kind ("~3", with the tags of its mod: "~3@attack") instead of a mod id when an enabled
    action may fracture a mod the item holds (`Reads.fractures`) and the mod's family is told apart only by its family type.
    """

    mod_id: str
    contribution: tuple[Status, ...]


@dataclass(frozen=True)
class Slot:
    """One mod that is not fractured, counted with the others of its side and kind.

    `kind` says what the enabled actions can tell it apart by. An ordinary mod of a family that every
    enabled action treats alike has the kind "" (a family type: only its side and what it gives the
    goal count), or, when an enabled action adds mods and keeps the junk (`Reads.pool_weight`), a
    numbered family type "~n" (side, and the weights and goal contribution of the family's mods); any
    other ordinary mod has its family key, so it stays identified. With metamods modelled, an ordinary
    kind also carries the Attack/Caster tags of its mod ("~3@attack"). A crafted mod
    (a bench mod or a metamod) has its canonical mod id. `contribution` is what the mod gives each leaf.
    """

    side: Side
    kind: str
    contribution: tuple[Status, ...]
    crafted: bool = False

    @property
    def key(self) -> tuple[str, str, tuple[int, ...], bool]:
        """The order slots are kept in."""
        return (self.side.value, self.kind, tuple(int(value) for value in self.contribution), self.crafted)


@dataclass(frozen=True)
class CompressedState:
    """The part of an item that decides what an action can do next.

    `fractured` is sorted by `(mod_id, contribution)`; `status` is per leaf, of the whole item;
    `slots` are the mods that are not fractured, sorted by `Slot.key` and kept as a multiset (a
    repeat is a second mod of that side and kind). A reroll-only abstraction keeps only the crafted
    slots, because every action it knows erases the other mods.
    """

    flags: Flags
    fractured: tuple[FracturedMod, ...]
    status: tuple[Status, ...]
    slots: tuple[Slot, ...] = ()

    @property
    def crafted(self) -> bool:
        """Whether the item holds a crafted mod or metamod."""
        return any(slot.crafted for slot in self.slots)

    def count(self, side: Side) -> int:
        """How many mods of `side` the item holds besides the fractured ones."""
        return sum(slot.side is side for slot in self.slots)


def best_of(width: int, vectors: Iterable[Sequence[int]]) -> tuple[Status, ...]:
    """The per-leaf maximum of `vectors`, ABSENT where there are none."""
    result = [0] * width
    for vector in vectors:
        for index, value in enumerate(vector):
            if value > result[index]:
                result[index] = value
    return tuple(Status(value) for value in result)


def status_of(
    leaf: Wanted, mod_id: str, tier: int, values: tuple[int, ...], crafted: bool
) -> Status:
    """What a mod gives `leaf`, by the rule of a target requirement.

    ABSENT when the mod is not one of the leaf's; BELOW when its tier is worse than `min_tier`, it is
    crafted and `not_crafted` is set, or its roll fails (the number of values equals `len(min_roll)`
    and every wanted value is reached); otherwise PASSING.
    """
    if mod_id not in leaf.mod_ids:
        return Status.ABSENT
    if leaf.min_tier is not None and tier > leaf.min_tier:
        return Status.BELOW
    if leaf.not_crafted and crafted:
        return Status.BELOW
    if leaf.min_roll is None:
        return Status.PASSING
    if len(values) != len(leaf.min_roll):
        return Status.BELOW
    reached = all(wanted is None or got >= wanted for wanted, got in zip(leaf.min_roll, values))
    return Status.PASSING if reached else Status.BELOW
