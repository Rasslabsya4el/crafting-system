"""A mixture of pool draws, with an optional fractured mod: the result of a resonator (`FossilOutcomes`).

A Tangled Fossil draws one of 420 tag pairs and a Glyphic Fossil one forced mod, so what a resonator
leaves is `(probability, Outcomes)` pairs; a Fractured Fossil also fractures one finished mod, and
`distribution` then gives `Fractured` labels. Any action whose result is a mixture of pool draws can
return a `Mixture`; `Outcomes.fracturing()` is a one-pool mixture that fractures.
"""

import random
from collections import defaultdict
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction

from crafting_system.data import GameData, Mod
from crafting_system.items import Item

from .draw import Outcome
from .outcomes import Outcomes

__all__ = [
    "FossilOutcomes",
    "Fractured",
    "Mixture",
]


@dataclass(frozen=True, slots=True)
class Fractured:
    """The label of a mod that a Fractured Fossil fractured: `Fractured(label(mod))` in an outcome with count 1.

    The fractured mod is also counted under its own label like every new mod, so a caller that
    does not care about fracturing reads the same counts as for any reroll.
    """

    label: Hashable


@dataclass(frozen=True, eq=False)
class Mixture:
    """What an action with several pools can leave behind: a mixture of `Outcomes` (`components`), a resonator's for one.

    `components` holds `(probability, Outcomes)` pairs that sum to 1. `fractures` is True when a
    Fractured Fossil is socketed: one finished mod is then fractured, uniformly among all of them.
    """

    data: GameData
    components: tuple[tuple[Fraction, Outcomes], ...]
    fractures: bool

    def chance_all(self, mod_ids) -> Fraction:
        """The exact chance that the finished item holds all of `mod_ids`, kept, forced or newly drawn."""
        wanted = list(mod_ids)
        return sum((p * part.chance_all(wanted) for p, part in self.components), Fraction(0))

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """The exact distribution of the new mods seen through `label`, as for `Outcomes.distribution`.

        With a Fractured Fossil every outcome also holds one `(Fractured(l), 1)` pair, `l` being the
        label of the mod that was fractured; the mods that are kept or forced take part in the choice.
        """
        mixed: dict[Outcome, Fraction] = defaultdict(Fraction)
        for p, part in self.components:
            forced = None if part.forced is None else label(self.data.mods[part.forced])
            for outcome, chance in part.distribution(label).items():
                if not self.fractures:
                    mixed[outcome] += p * chance
                    continue
                counts = dict(outcome)
                if forced is not None:
                    counts[forced] = counts.get(forced, 0) + 1
                whole = sum(counts.values())
                if whole == 0:
                    mixed[outcome] += p * chance
                    continue
                for lab, count in counts.items():
                    mixed[outcome | {(Fractured(lab), 1)}] += p * chance * Fraction(count, whole)
        return dict(mixed)

    def sample(self, rng: random.Random) -> Item:
        """One finished item drawn with `rng`; a Fractured Fossil fractures one of its mods at random."""
        part = rng.choices([c for _, c in self.components], weights=[float(p) for p, _ in self.components])[0]
        finished = part.sample(rng)
        if not self.fractures or not finished.mods:
            return finished
        chosen = rng.randrange(len(finished.mods))
        mods = tuple(
            replace(entry, fractured=True) if index == chosen else entry
            for index, entry in enumerate(finished.mods)
        )
        return finished.changed(self.data, mods=mods)


FossilOutcomes = Mixture  # the name a resonator's result is known by
