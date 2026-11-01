"""`Finite`: the outcomes of an action whose result is a short list of exact items, each with its probability.

A new method that does not draw from a pool (a removal of one random mod, a swap, a coin flip) lists
what it can leave behind and gets `chance_all`, `distribution`, `sample` and the mixture the
abstraction builds its kernel from, with nothing else to write. `given` is the item the action was
used on: the mods of a result that `given` does not hold are the new ones, which is what
`distribution` shows. A result is exact: a new mod stays at its lowest values (`sample` rolls none).
"""

import random
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.items import Item

from .contract import Fixed
from .draw import Outcome

__all__ = [
    "Finite",
]

ONE = Fraction(1)


@dataclass(frozen=True, eq=False)
class Finite:
    """What an action can leave behind as `(probability, item)` pairs that sum to exactly 1.

    Raises `ValueError` at construction when the probabilities do not sum to 1 or one is not positive.
    """

    data: GameData
    given: Item
    results: tuple[tuple[Fraction, Item], ...]

    def __post_init__(self) -> None:
        if not self.results or any(chance <= 0 for chance, _ in self.results) or sum(c for c, _ in self.results) != 1:
            raise ValueError("the results of a finite action are items with positive probabilities that sum to 1")

    @cached_property
    def components(self) -> tuple[tuple[Fraction, Fixed], ...]:
        return tuple((chance, Fixed(self.data, item)) for chance, item in self.results)

    @property
    def fractures(self) -> bool:
        return False

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        """The exact chance that the finished item holds all of `mod_ids` (0 when two share a family)."""
        wanted = set(mod_ids)
        unknown = sorted(wanted - self.data.mods.keys())
        if unknown:
            raise ValueError(f"mod {unknown[0]} is not in the game data")
        mods = [self.data.mods[mod_id] for mod_id in sorted(wanted)]
        if any(conflicts(a, b) for index, a in enumerate(mods) for b in mods[index + 1 :]):
            return Fraction(0)
        return sum(
            (chance for chance, item in self.results if wanted <= {entry.mod_id for entry in item.mods}),
            Fraction(0),
        )

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """The new mods of each result (those `given` does not hold) seen through `label`, with the result's probability."""
        held = {(entry.mod_id, entry.fractured, entry.crafted) for entry in self.given.mods}
        shown: dict[Outcome, Fraction] = {}
        for chance, item in self.results:
            counts: dict[Hashable, int] = {}
            for entry in item.mods:
                if (entry.mod_id, entry.fractured, entry.crafted) not in held:
                    key = label(self.data.mods[entry.mod_id])
                    counts[key] = counts.get(key, 0) + 1
            outcome = frozenset(counts.items())
            shown[outcome] = shown.get(outcome, Fraction(0)) + chance
        return shown

    def sample(self, rng: random.Random) -> Item:
        """One of the results, chosen with its probability."""
        return rng.choices([item for _, item in self.results], weights=[float(chance) for chance, _ in self.results])[0]
