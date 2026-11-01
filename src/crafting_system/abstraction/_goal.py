"""The goal as the abstraction sees it: requirement leaves with a status each, and the check over them."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from functools import cached_property


class Status(IntEnum):
    """How a requirement leaf stands on an item; ordered, so the best of several mods is the maximum."""

    ABSENT = 0
    BELOW = 1
    PASSING = 2


@dataclass(frozen=True)
class Wanted:
    """One requirement leaf: a mod from `mod_ids` that passes every limit.

    The limits are those of a target requirement: `min_tier` is the worst tier accepted (1 is the
    best), `min_roll` has one entry per stat (None where any value will do), `not_crafted` refuses a
    crafted mod.
    """

    mod_ids: frozenset[str]
    min_tier: int | None = None
    min_roll: tuple[int | None, ...] | None = None
    not_crafted: bool = False

    @property
    def has_roll_limit(self) -> bool:
        """Whether `min_roll` asks for any value at all."""
        return self.min_roll is not None and any(wanted is not None for wanted in self.min_roll)


@dataclass(frozen=True)
class ImplicitWanted:
    """One Eldritch implicit wanted: a mod from `mod_ids` of at least grade `min_grade` (1 Lesser to 6 Perfect).

    `min_roll` is the limit on its rolled values, as for `Wanted`; the compressed state does not model a roll of an
    implicit yet (ticket #158), so an `Abstraction` refuses a goal that asks for one. A requirement on a base
    implicit (grade 0) is not modelled either: the state holds the two Eldritch sides only.
    """

    mod_ids: frozenset[str]
    min_grade: int | None = None
    min_roll: tuple[int | None, ...] | None = None

    @property
    def has_roll_limit(self) -> bool:
        """Whether `min_roll` asks for any value at all."""
        return self.min_roll is not None and any(wanted is not None for wanted in self.min_roll)


@dataclass(frozen=True)
class AtLeast:
    """A k-of-n requirement: met when at least `k` of `members` are met."""

    k: int
    members: tuple["Wanted | AtLeast", ...]

    def __post_init__(self) -> None:
        if not 1 <= self.k <= len(self.members):
            raise ValueError(f"k must be from 1 to {len(self.members)}, got {self.k}")


Node = Wanted | AtLeast


def _leaves(node: Node) -> tuple[Wanted, ...]:
    if isinstance(node, Wanted):
        return (node,)
    return tuple(leaf for member in node.members for leaf in _leaves(member))


def _met(node: Node, statuses: Sequence[Status], start: int) -> tuple[bool, int]:
    """Whether `node` is met by `statuses[start:]`, and the index after the leaves of `node`."""
    if isinstance(node, Wanted):
        return statuses[start] is Status.PASSING, start + 1
    met = 0
    position = start
    for member in node.members:
        member_met, position = _met(member, statuses, position)
        met += member_met
    return met >= node.k, position


@dataclass(frozen=True)
class Goal:
    """Every requirement must hold; the leaves, depth-first in file order, are the positions of a status tuple.

    `implicits` are the Eldritch implicits wanted besides, each of which must be passed by one side of the item
    (ADR-0027); `CompressedState.implicits` holds what each side gives each of them. A goal built from a target
    does not read them yet: the planner refuses a target with implicits until tickets #152 and #158.

    `asks_corrupted` and `allow_corrupted` carry what the target says about corruption (ADR-0036): it asks for a corrupted implicit
    (the goal is a corrupted item), or it allows a corrupted item without asking for an implicit. A target with neither is never
    met by a corrupted item. The corrupted implicit itself is not a requirement leaf: a corrupting action decides whether its outcome
    holds it, and the state keeps no corrupted-implicit status.
    """

    requirements: tuple[Node, ...]
    implicits: tuple[ImplicitWanted, ...] = ()
    asks_corrupted: bool = False
    allow_corrupted: bool = False

    @property
    def takes_corrupted(self) -> bool:
        """Whether a corrupted item can be the goal: the target asks for a corrupted implicit or allows a corrupted item."""
        return self.asks_corrupted or self.allow_corrupted

    @cached_property
    def leaves(self) -> tuple[Wanted, ...]:
        """The requirement leaves, depth-first in file order: the order of `CompressedState.status`."""
        return tuple(leaf for node in self.requirements for leaf in _leaves(node))

    def is_met(self, statuses: Sequence[Status]) -> bool:
        """Whether `statuses` (one per leaf) meet every requirement: a leaf needs PASSING, an `AtLeast` needs k members met."""
        if len(statuses) != len(self.leaves):
            raise ValueError(f"expected {len(self.leaves)} statuses, got {len(statuses)}")
        position = 0
        for node in self.requirements:
            met, position = _met(node, statuses, position)
            if not met:
                return False
        return True

    @classmethod
    def from_target(cls, target) -> "Goal":
        """The goal of a target, read by duck typing from `target.requirements`.

        A node with the attributes `at_least` and `of` is a k-of-n; any other node has `mod_ids`,
        `min_tier`, `min_roll` and `not_crafted`. What the target says about corruption (`asks_corrupted`, `allow_corrupted`) is read
        the same way, False for a target that has neither.
        """
        return cls(
            tuple(_node(node) for node in target.requirements),
            asks_corrupted=bool(getattr(target, "asks_corrupted", False)),
            allow_corrupted=bool(getattr(target, "allow_corrupted", False)),
        )


def _node(node) -> Node:
    if hasattr(node, "at_least") and hasattr(node, "of"):
        return AtLeast(node.at_least, tuple(_node(member) for member in node.of))
    min_roll = None if node.min_roll is None else tuple(node.min_roll)
    return Wanted(frozenset(node.mod_ids), node.min_tier, min_roll, node.not_crafted)
