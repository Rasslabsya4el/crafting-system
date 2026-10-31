"""The result of an action on a concrete item: the whole distribution of what it can leave behind.

`Outcomes` is what `ChaosOrb.outcomes`, `HarvestReforge.outcomes` and `ApplyEssence.outcomes` return. It is one object with
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
from crafting_system.items import ExplicitMod, Item, Rarity, Side, tier_table

from crafting_system.rules import get_rule

from .draw import (
    Outcome,
    exact_distribution,
    guaranteed_candidates,
    sample_new_mods,
    total_distribution,
)
from .errors import NotApplicableError
from .pool import ModFactor, PoolFamily, build_pool

CHAOS_FRACTURED_MODS_KEPT = get_rule("chaos_orb.fractured_mods_kept")
HARVEST_FRACTURED_MODS_KEPT = get_rule("harvest_reforge.fractured_mods_kept")
REFUSED_WITHOUT_TAGGED_MOD = get_rule("harvest_reforge.refused_without_tagged_mod")
VALUES_UNIFORM_INTEGERS = get_rule("affix_pool.values_uniform_integers")


def retained_item(data: GameData, item: Item, forced: Mod | None = None) -> Item:
    """`item` as a reroll leaves it before any draw: rare, with the fractured mods and the `forced` mod only.

    The forced mod is rolled at its lowest values, whatever its level (`sample` rolls it).
    """
    kept = item.fractured_mods
    if forced is not None:
        tier = tier_table(data, item.base_id).get(forced.id, 1)  # an essence-only mod has no tier: 1
        low = tuple(min(stat.min, stat.max) for stat in forced.stats)
        kept = (*kept, ExplicitMod(forced.id, tier, low))
    return item.changed(data, rarity=Rarity.RARE, mods=kept)


@dataclass(frozen=True, eq=False)
class Outcomes:
    """What a reroll of `retained` can leave behind.

    `retained` is the item before any mod is drawn: a rare item with only the fractured mods of the
    original and, for an essence, the forced mod (rolled at its lowest values: `sample` rolls it).
    `pool` is the candidate pool for the draws on it, `totals` the probability of each total number
    of mods of the finished item (kept mods included), `tag` the tag of the guaranteed mod of a
    Harvest reforge, None for a Chaos Orb or an essence, and `forced` the id of the forced mod of an
    essence, None otherwise. The forced mod is a kept mod: it is in `retained`, not in the
    distribution. Build one with `Outcomes.reroll`.
    """

    data: GameData
    retained: Item
    pool: tuple[PoolFamily, ...]
    totals: Mapping[int, Fraction]
    tag: str | None
    forced: str | None = None

    @classmethod
    def reroll(
        cls,
        data: GameData,
        item: Item,
        tag: str | None,
        *,
        forced: Mod | None = None,
        max_level: int | None = None,
        factor: ModFactor | None = None,
        extra: Iterable[Mod] = (),
    ) -> "Outcomes":
        """The outcomes of rerolling `item` (already checked to be rerollable), guaranteeing `tag` if given.

        With `forced`, the mod is put on the retained rare item whatever its level, as a kept mod
        (the caller has checked that its family is free and its side has a slot), and `max_level`
        caps the required level of the drawn mods. `factor` multiplies the weight of every mod of the
        pool (the fossils of a resonator; 0 drops the mod) and `extra` are mods that join the pool.
        Raises `NotApplicableError` when `tag` is given
        and the pool holds no mod with it that the retained item has a free family and a free slot
        for.
        """
        retained = retained_item(data, item, forced)
        pool = build_pool(data, retained, max_level, factor, extra)
        result = cls.over(data, retained, pool, tag, forced)
        if tag is not None and not guaranteed_candidates(result.pool, result.free, tag):
            raise NotApplicableError(
                f"the {tag} reforge cannot be used: the pool holds no {tag} mod "
                "that the item has a free slot and a free family for"
            )
        return result

    @classmethod
    def over(
        cls, data: GameData, retained: Item, pool: tuple[PoolFamily, ...], tag: str | None, forced: Mod | None
    ) -> "Outcomes":
        """The outcomes of drawing from a `pool` already built onto `retained` (see `retained_item`)."""
        return cls(data, retained, pool, total_distribution(), tag, None if forced is None else forced.id)

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
        not in it. Probabilities are exact and sum to 1. Exact for any pure `label`.

        The work grows with the number of distinct (side, weight, label) classes in the pool. A
        real amulet pool with a coarse label (a few values) takes about 0.3 to 3 s; a pool of 40
        families that all have different weights took about 70 s. The fractions are exact and can
        be thousands of bits long: `str()` of one can hit Python's 4300-digit limit, so convert
        with `float()` or `Fraction.limit_denominator` to display it.
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
        rolled = [entry.mod for entry in drawn]
        kept = tuple(entry for entry in self.retained.mods if entry.mod_id != self.forced)
        if self.forced is not None:
            rolled.insert(0, self.data.mods[self.forced])
        new = tuple(
            ExplicitMod(
                mod.id,
                self._tiers[mod.id] if mod.id != self.forced else self._tiers.get(mod.id, 1),
                tuple(
                    rng.randint(min(stat.min, stat.max), max(stat.min, stat.max))
                    for stat in mod.stats
                ),
            )
            for mod in rolled
        )
        return self.retained.changed(self.data, mods=(*kept, *new))
