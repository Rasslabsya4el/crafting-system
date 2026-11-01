"""The Orb of Scouring: removes every mod that is not fractured or on a locked side, and the rarity follows what is left."""

import random
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Fixed, Reads
from .draw import Outcome
from .errors import NotApplicableError
from .metamods import kept_by_reroll
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, SCOURING_KEEPS_STRANDS, StrandUse

__all__ = [
    "ScourOutcomes",
    "ScouringOrb",
]

ACCEPTS_MAGIC_OR_RARE = get_rule("scouring.accepts_magic_or_rare")
REMOVES_ALL_UNPROTECTED_MODS = get_rule("scouring.removes_all_unprotected_mods")
FRACTURED_MODS_STAY = get_rule("scouring.fractured_mods_stay")
RARITY_FOLLOWS_MODS_LEFT = get_rule("scouring.rarity_follows_mods_left")
KEEPS_INFLUENCE = get_rule("scouring.keeps_influence")
KEEPS_LOCKED_SIDE = get_rule("metamods.scouring_keeps_locked_side")
REFUSED_ON_CORRUPTED = get_rule("magic_orbs.refused_on_corrupted")
COST = get_rule("scouring.cost")
JEWELS_TAKE_THE_ORBS = get_rule("jewel.ordinary_orbs_work_on_jewels")

ONE = Fraction(1)


@dataclass(frozen=True, eq=False)
class ScourOutcomes:
    """What an Orb of Scouring leaves behind: one result, with probability 1.

    `retained` is the finished item: the fractured mods only, in the rarity they allow. It has the
    same three methods as the random actions, `chance_all`, `distribution` and `sample`.
    """

    data: GameData
    retained: Item

    @cached_property
    def components(self) -> tuple[tuple[Fraction, Fixed], ...]:
        """One part with probability 1: the scoured item (see `ActionOutcomes`)."""
        return ((ONE, Fixed(self.data, self.retained)),)

    @property
    def fractures(self) -> bool:
        return False

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        """1 when the scoured item holds all of `mod_ids`, 0 when it does not (two of one family included).

        Raises `ValueError` for an id that is not in the game data.
        """
        wanted = set(mod_ids)
        unknown = sorted(wanted - self.data.mods.keys())
        if unknown:
            raise ValueError(f"mod {unknown[0]} is not in the game data")
        mods = [self.data.mods[mod_id] for mod_id in sorted(wanted)]
        if any(conflicts(a, b) for index, a in enumerate(mods) for b in mods[index + 1 :]):
            return Fraction(0)
        held = {entry.mod_id for entry in self.retained.mods}
        return ONE if wanted <= held else Fraction(0)

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """The one outcome, with no new mod, and probability 1."""
        return {frozenset(): ONE}

    def sample(self, rng: random.Random) -> Item:
        """The scoured item (nothing is random)."""
        return self.retained


@dataclass(frozen=True)
class ScouringOrb(Action):
    """One Orb of Scouring."""

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Scouring"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(SCOURING_KEEPS_STRANDS, CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: neither cuts nor spends: the count stays

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing(block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.removal(keeps_crafted=False)

    def outcomes(self, data: GameData, item: Item) -> ScourOutcomes:
        """The outcome of using the orb on `item`.

        The item keeps its fractured mods, the mods of a side that `Prefixes` or `Suffixes Cannot Be
        Changed` locks, and its influences, and loses every other mod, an ordinary crafted one and the
        lock itself included (the lock sits on the other side); it is normal with none left, magic with
        one and rare with two or more. `Cannot roll Attack` and `Caster Modifiers` do not protect a mod.
        Raises `NotApplicableError` for a normal or a corrupted item.
        """
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("an Orb of Scouring works on a magic or rare item only, and this item is normal")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Orb of Scouring")
        kept = kept_by_reroll(data, item)
        if not kept:
            rarity = Rarity.NORMAL
        elif len(kept) < RARITY_FOLLOWS_MODS_LEFT.value:
            rarity = Rarity.MAGIC
        else:
            rarity = Rarity.RARE
        return ScourOutcomes(data, item.changed(data, rarity=rarity, mods=kept))


@kind("scouring-orb", order=80, planner=False, why_not="not in the B1 offer set; which actions a target needs is pruning (#118)")
def _scouring_orb(data: GameData, item: Item):
    yield ScouringOrb()
