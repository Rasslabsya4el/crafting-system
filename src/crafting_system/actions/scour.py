"""The Orb of Scouring: removes every mod that is not fractured, and the rarity follows what is left."""

import random
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .draw import Outcome, refuse_metamods
from .errors import NotApplicableError

ACCEPTS_MAGIC_OR_RARE = get_rule("scouring.accepts_magic_or_rare")
REMOVES_ALL_UNPROTECTED_MODS = get_rule("scouring.removes_all_unprotected_mods")
FRACTURED_MODS_STAY = get_rule("scouring.fractured_mods_stay")
RARITY_FOLLOWS_MODS_LEFT = get_rule("scouring.rarity_follows_mods_left")
KEEPS_INFLUENCE = get_rule("scouring.keeps_influence")
REFUSED_ON_CORRUPTED = get_rule("magic_orbs.refused_on_corrupted")

ONE = Fraction(1)


@dataclass(frozen=True, eq=False)
class ScourOutcomes:
    """What an Orb of Scouring leaves behind: one result, with probability 1.

    `retained` is the finished item: the fractured mods only, in the rarity they allow. It has the
    same three methods as the random actions, `chance_all`, `distribution` and `sample`.
    """

    data: GameData
    retained: Item

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
class ScouringOrb:
    """One Orb of Scouring."""

    def outcomes(self, data: GameData, item: Item) -> ScourOutcomes:
        """The outcome of using the orb on `item`.

        The item keeps its fractured mods and influences and loses every other mod, an ordinary
        crafted one included; it is normal with none left, magic with one and rare with two or more.
        Raises `NotApplicableError` for a normal or a corrupted item and `OutOfScopeError` for one
        with a crafted metamod.
        """
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("an Orb of Scouring works on a magic or rare item only, and this item is normal")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Orb of Scouring")
        refuse_metamods(data, item)
        kept = item.fractured_mods
        if not kept:
            rarity = Rarity.NORMAL
        elif len(kept) < RARITY_FOLLOWS_MODS_LEFT.value:
            rarity = Rarity.MAGIC
        else:
            rarity = Rarity.RARE
        return ScourOutcomes(data, item.changed(data, rarity=rarity, mods=kept))
