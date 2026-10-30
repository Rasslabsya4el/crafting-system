"""The compressed state: flags, the fractured mods with what they give each leaf, and the status of each leaf."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from crafting_system.items import Influence, Rarity

from ._goal import Status, Wanted


@dataclass(frozen=True)
class Flags:
    """What the rerolls look at besides the mods; `crafted` says the item holds a crafted mod or metamod."""

    rarity: Rarity
    corrupted: bool
    influences: frozenset[Influence]
    crafted: bool


@dataclass(frozen=True)
class FracturedMod:
    """A fractured mod: the canonical id of its kind and what it gives each leaf of the goal."""

    mod_id: str
    contribution: tuple[Status, ...]


@dataclass(frozen=True)
class CompressedState:
    """The part of an item that decides what a rerolling action can do next.

    `fractured` is sorted by `(mod_id, contribution)`; `status` is per leaf, of the whole item.
    """

    flags: Flags
    fractured: tuple[FracturedMod, ...]
    status: tuple[Status, ...]


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
