"""The goal as the abstraction sees it: requirement leaves with a status each, and the check over them."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import IntEnum
from functools import cached_property

from crafting_system.data import GameData
from crafting_system.items import accepted_by_tier


class Status(IntEnum):
    """How a requirement leaf stands on an item; ordered, so the best of several mods is the maximum."""

    ABSENT = 0
    BELOW = 1
    PASSING = 2


@dataclass(frozen=True)
class Wanted:
    """One requirement leaf: a mod from `mod_ids` that passes every limit.

    The limits are those of a target requirement: `min_tier` is the worst natural tier accepted (1 is the
    best), `min_roll` has one entry per stat (None where any value will do), `not_crafted` refuses a
    crafted mod.

    `tier_ok` is what the tier limit means in the game data (ticket #457): the mods of `mod_ids` whose natural tier on
    the base the leaf accepts (a mod with no natural tier is never in it), or None when the leaf asks no tier (a `mod:`
    leaf, a leaf that limits a roll and no tier). A target's leaf arrives with it resolved; a leaf built by hand with a
    `min_tier` is resolved by the `Abstraction` that gets it (`Goal.resolved`). `status_of` reads `tier_ok` and nothing else
    of the tier.
    """

    mod_ids: frozenset[str]
    min_tier: int | None = None
    min_roll: tuple[int | None, ...] | None = None
    not_crafted: bool = False
    tier_ok: frozenset[str] | None = None

    @property
    def has_roll_limit(self) -> bool:
        """Whether `min_roll` asks for any value at all."""
        return self.min_roll is not None and any(wanted is not None for wanted in self.min_roll)


@dataclass(frozen=True)
class ImplicitWanted:
    """One Eldritch implicit wanted: a mod from `mod_ids` of at least grade `min_grade` (1 Lesser to 6 Perfect).

    `min_roll` is the limit on its rolled values, as for `Wanted`. The mod may be an Eldritch implicit or an implicit of the
    base (grade 0, `min_grade` None): the compressed state holds what each implicit gives the leaf, the roll included
    (ticket #158, ADR-0027).
    """

    mod_ids: frozenset[str]
    min_grade: int | None = None
    min_roll: tuple[int | None, ...] | None = None

    @property
    def has_roll_limit(self) -> bool:
        """Whether `min_roll` asks for any value at all."""
        return self.min_roll is not None and any(wanted is not None for wanted in self.min_roll)


@dataclass(frozen=True)
class QualityWanted:
    """The quality wanted (ADR-0029, ADR-0049): at least `min_percent` of the catalyst `type`, or of the plain quality of a weapon or armour (`type` None).

    It is the final requirement of a goal (ticket #158): catalysts change no odds, so a planner offers the actions that only set
    the quality when every other requirement already passes (`Abstraction.quality_offer_pruned`).
    """

    type: object | None
    min_percent: int

    def is_met_by(self, quality) -> bool:
        """Whether `quality` (as an item stores it: a catalyst `Quality`, a `PlainQuality` or None) meets the requirement."""
        return quality is not None and getattr(quality, "type", None) == self.type and quality.percent >= self.min_percent


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

    `implicits` are the implicits wanted besides (Eldritch ones and the base's own), each of which must be passed by one implicit
    of the item (ADR-0027); `CompressedState.implicits` holds what each implicit gives each of them, the roll included.
    `quality` is the quality wanted, met last (ADR-0029). A goal built from a target reads both (ticket #158); a corrupted implicit
    of the target is not one of them (below).

    `asks_corrupted` and `allow_corrupted` carry what the target says about corruption (ADR-0036): it asks for a corrupted implicit
    (the goal is a corrupted item), or it allows a corrupted item without asking for an implicit. A target with neither is never
    met by a corrupted item. The corrupted implicit itself is not a requirement leaf: a corrupting action decides whether its outcome
    holds it, and the state keeps no corrupted-implicit status.
    """

    requirements: tuple[Node, ...]
    implicits: tuple[ImplicitWanted, ...] = ()
    asks_corrupted: bool = False
    allow_corrupted: bool = False
    quality: QualityWanted | None = None

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
        the same way, False for a target that has neither. The target's `implicits` (`mod_ids`, `min_grade`, `min_roll`; not a corrupted one,
        which a corrupting action decides, ADR-0036) and `quality` (`type`, `min_percent`) are read the same way, none for a target
        that has neither (ticket #158).
        """
        wanted = tuple(
            ImplicitWanted(
                frozenset(wish.mod_ids), wish.min_grade, None if wish.min_roll is None else tuple(wish.min_roll)
            )
            for wish in getattr(target, "implicits", ())
            if not getattr(wish, "corrupted", False)
        )
        asked = getattr(target, "quality", None)
        return cls(
            tuple(_node(node) for node in target.requirements),
            wanted,
            asks_corrupted=bool(getattr(target, "asks_corrupted", False)),
            allow_corrupted=bool(getattr(target, "allow_corrupted", False)),
            quality=None if asked is None else QualityWanted(asked.type, asked.min_percent),
        )


    def resolved(self, data: GameData, base_id: str, item_level: int) -> "Goal":
        """This goal with the tier limit of every hand-built leaf read from the game data of `base_id`.

        A leaf from a target already holds its `tier_ok`. A leaf with a `min_tier` and no `tier_ok` gets the mods whose natural
        tier on the base (`items.accepted_by_tier`, no influences) is that tier or better. A leaf with neither asks no tier.
        """

        def resolve(node: Node) -> Node:
            if isinstance(node, AtLeast):
                return AtLeast(node.k, tuple(resolve(member) for member in node.members))
            if node.min_tier is None or node.tier_ok is not None:
                return node
            return replace(node, tier_ok=accepted_by_tier(data, base_id, item_level, node.mod_ids, node.min_tier))

        return replace(self, requirements=tuple(resolve(node) for node in self.requirements))


def _node(node) -> Node:
    if hasattr(node, "at_least") and hasattr(node, "of"):
        return AtLeast(node.at_least, tuple(_node(member) for member in node.of))
    min_roll = None if node.min_roll is None else tuple(node.min_roll)
    tier_ok = getattr(node, "tier_ok", None)
    return Wanted(frozenset(node.mod_ids), node.min_tier, min_roll, node.not_crafted, None if tier_ok is None else frozenset(tier_ok))
