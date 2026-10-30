"""The result of an action on a concrete item: the whole distribution of what it can leave behind.

`Outcomes` is what `ChaosOrb.outcomes` and `HarvestReforge.outcomes` return. It is one object with
three ways in: `chance_all` (the chance that the finished item holds given mods), `distribution`
(the exact distribution of the new mods seen through a caller's label, which is what the compressed
state of the solver uses) and `sample` (one finished item, drawn at random, with rolled values).
"""

import random
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.items import ExplicitMod, Item, Side, tier_table

from .draw import Outcome, exact_distribution, sample_new_mods, total_distribution
from .pool import PoolFamily, build_pool


@dataclass(frozen=True, eq=False)
class Outcomes:
    """What a reroll of `retained` can leave behind.

    `retained` is the item before any mod is drawn: the original item with only its fractured mods.
    `pool` is the candidate pool for the draws on it, `totals` the probability of each total number
    of mods of the finished item (kept mods included) and `tag` the tag of the guaranteed mod of a
    Harvest reforge, None for a Chaos Orb. Build one with `Outcomes.reroll`.
    """

    data: GameData
    retained: Item
    pool: tuple[PoolFamily, ...]
    totals: Mapping[int, Fraction]
    tag: str | None

    @classmethod
    def reroll(cls, data: GameData, item: Item, tag: str | None) -> "Outcomes":
        """The outcomes of rerolling `item` (already checked to be rerollable), guaranteeing `tag` if given."""
        retained = item.changed(data, mods=item.fractured_mods)
        return cls(data, retained, build_pool(data, retained), total_distribution(), tag)

    @property
    def free(self) -> Mapping[Side, int]:
        """The free slots per side on the retained item."""
        return {side: self.retained.free_slots(self.data, side) for side in Side}

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        """The exact chance that the finished item holds all of `mod_ids`, kept or newly drawn (joint).

        Raises `ValueError` for an id that is not in the game data. Two mods of one family can never
        be on one item, so that chance is 0.
        """
        wanted = set(mod_ids)
        unknown = sorted(wanted - self.data.mods.keys())
        if unknown:
            raise ValueError(f"mod {unknown[0]} is not in the game data")
        mods = [self.data.mods[mod_id] for mod_id in sorted(wanted)]
        if any(conflicts(a, b) for index, a in enumerate(mods) for b in mods[index + 1 :]):
            return Fraction(0)
        needed = wanted - {entry.mod_id for entry in self.retained.mods}
        shown = self.distribution(lambda mod: mod.id if mod.id in needed else None)
        return sum(
            (
                chance
                for outcome, chance in shown.items()
                if needed <= {label for label, _ in outcome}
            ),
            Fraction(0),
        )

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """The exact distribution of the new mods seen through `label`.

        An outcome is the set of `(label, how many new mods got that label)` pairs; the kept mods are
        not in it. Probabilities are exact and sum to 1. Exact for any pure `label`; the cost grows
        with the number of distinct (side, weight, label) classes in the pool.
        """
        return exact_distribution(
            self.pool, self.free, self.tag, self.totals, len(self.retained.mods), label
        )

    @cached_property
    def _tiers(self) -> Mapping[str, int]:
        return tier_table(self.data, self.retained.base_id)

    @cached_property
    def _float_weights(self) -> Mapping[str, float]:
        return {entry.mod.id: float(entry.weight) for family in self.pool for entry in family.mods}

    def sample(self, rng: random.Random) -> Item:
        """One finished item: the same process, drawn with `rng`, with values rolled and tiers set."""
        totals = list(self.totals)
        total = rng.choices(totals, weights=[float(self.totals[t]) for t in totals])[0]
        drawn = sample_new_mods(
            self.pool, self.free, self.tag, total, len(self.retained.mods), rng, self._float_weights
        )
        new = tuple(
            ExplicitMod(
                entry.mod.id,
                self._tiers[entry.mod.id],
                tuple(
                    rng.randint(min(stat.min, stat.max), max(stat.min, stat.max))
                    for stat in entry.mod.stats
                ),
            )
            for entry in drawn
        )
        return self.retained.changed(self.data, mods=(*self.retained.mods, *new))
