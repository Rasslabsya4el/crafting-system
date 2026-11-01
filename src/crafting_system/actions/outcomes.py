"""The result of an action on a concrete item: the whole distribution of what it can leave behind.

`Outcomes` is what `ChaosOrb.outcomes`, `HarvestReforge.outcomes` and `ApplyEssence.outcomes` return. It is one object with
three ways in: `chance_all` (the chance that the finished item holds given mods), `distribution`
(the exact distribution of the new mods seen through a caller's label, which is what the compressed
state of the solver uses) and `sample` (one finished item, drawn at random, with rolled values).

What an `Outcomes` gives, on the item before any mod is drawn (`retained`: a rare item with only the
fractured mods of the original, which stay and count inside the total of 4, 5 or 6 mods, and, for an
essence, its forced mod, which is on the item above the item level and counts inside the total too;
a low essence (levels 1 to 4) also caps the required level of the drawn mods):

* `chance_all(mod_ids)`: the exact `Fraction` chance that the finished item holds all of these mods,
  kept or newly drawn, jointly; 0 when two of them share a family; `ValueError` for an unknown id.
* `distribution(label)`: the exact distribution of the new mods seen through `label`, a pure
  function from a `Mod` to a hashable. An `Outcome` is a frozenset of `(label, how many new mods got
  it)` pairs; labels with a count of zero are left out and the kept mods (fractured, forced) are not in it. The
  probabilities are `Fraction`s that sum to exactly 1. This is the input of the compressed state.
* `sample(rng)`: one finished item from a seeded `random.Random`: the same process, with a value
  rolled for every stat and the tier of every drawn mod. Values exist only here; no exact result
  depends on them.

Exactness and cost: nothing is rounded. Families the label cannot tell apart (same side, same
weight per label) are counted, not identified, so the work grows with the number of distinct
(side, weight, label) classes in the pool, not with the number of families. A real amulet pool
(about 40 families) with a coarse label takes about 0.3 to 3 s; a pool of 40 families that all
have different weights took about 70 s, and a label that gives every mod its own value is worse.
The fractions are exact and can be thousands of bits long: `str()` of one can hit Python's
4300-digit limit, so convert with `float()` or `Fraction.limit_denominator` to display it.
"""

import random
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cached_property

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.items import ExplicitMod, Item, Rarity, Side, tier_table

from crafting_system.rules import get_rule

from .contract import ActionOutcomes
from .draw import (
    Outcome,
    exact_distribution,
    guaranteed_candidates,
    sample_new_mods,
    total_distribution,
)
from .errors import NotApplicableError
from .metamods import blocked_tags, kept_by_reroll
from .pool import ModFactor, PoolFamily, build_pool, mark_pool, tiers_of
from .rolls import roll_values

__all__ = [
    "Outcomes",
]

CHAOS_FRACTURED_MODS_KEPT = get_rule("chaos_orb.fractured_mods_kept")
HARVEST_FRACTURED_MODS_KEPT = get_rule("harvest_reforge.fractured_mods_kept")
REFUSED_WITHOUT_TAGGED_MOD = get_rule("harvest_reforge.refused_without_tagged_mod")
VALUES_UNIFORM_INTEGERS = get_rule("affix_pool.values_uniform_integers")
ONE = Fraction(1)


def retained_item(data: GameData, item: Item, forced: Mod | None = None) -> Item:
    """`item` as a reroll leaves it before any draw: rare, with the mods a reroll keeps and the `forced` mod only.

    A reroll keeps the fractured mods and every mod on a side that `Prefixes` or `Suffixes Cannot Be
    Changed` locks (`metamods.kept_by_reroll`). The forced mod is rolled at its lowest values, whatever
    its level (`sample` rolls it).
    """
    kept = kept_by_reroll(data, item)
    if forced is not None:
        tier = tier_table(data, item.base_id).get(forced.id, 1)  # an essence-only mod has no tier: 1
        low = tuple(min(stat.min, stat.max) for stat in forced.stats)
        kept = (*kept, ExplicitMod(forced.id, tier, low))
    return item.changed(data, rarity=Rarity.RARE, mods=kept)


@dataclass(frozen=True, eq=False)
class Outcomes:
    """What a reroll of `retained` can leave behind.

    `retained` is the item before any mod is drawn: for a reroll a rare item (magic for an Alteration)
    with only the fractured mods of the original and, for an essence, the forced mod (rolled at its lowest values: `sample` rolls it).
    `pool` is the candidate pool for the draws on it, `totals` the probability of each total number
    of mods of the finished item (kept mods included), `tag` the tag of the guaranteed mod of a
    Harvest reforge, None for a Chaos Orb or an essence, and `forced` the id of the forced mod of an
    essence, None otherwise. The forced mod is a kept mod: it is in `retained`, not in the
    distribution. `guaranteed_blocked` are the tags that an Attack or Caster metamod kept on the
    item keeps out of the guaranteed draw of a reforge: the pool of a reforge is not filtered, since
    the metamod filters its first added mod only (D8 of issue #28). With `rolls_lucky` (a Sanctified Fossil in the
    resonator, `fossils.sanctified_values_lucky`) `sample` rolls each value of the drawn mods and of the forced mod
    twice and keeps the better, the one nearer the stat's `max`; the kept mods keep the values they had, except those in `rerolled`, whose values `sample` rolls afresh and whose tiers stay
    (the influenced mods an Awakener's Orb keeps). Build one with `Outcomes.reroll`.
    """

    data: GameData
    retained: Item
    pool: tuple[PoolFamily, ...]
    totals: Mapping[int, Fraction]
    tag: str | None
    forced: str | None = None
    guaranteed_blocked: frozenset[str] = frozenset()
    rolls_lucky: bool = False  # every value of the mods this reroll puts on the item is rolled twice and the better kept (a Sanctified Fossil)
    rerolled: frozenset[str] = frozenset()  # ids of kept mods in `retained` whose values `sample` rolls afresh (an Awakener's Orb keeps the tier and rerolls the value)

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
        guaranteed: Callable[[Mod], bool] | None = None,
    ) -> "Outcomes":
        """The outcomes of rerolling `item` (already checked to be rerollable), guaranteeing `tag` if given.

        With `forced`, the mod is put on the retained rare item whatever its level, as a kept mod
        (the caller has checked that its family is free and its side has a slot), and `max_level`
        caps the required level of the drawn mods. `factor` multiplies the weight of every mod of the
        pool (the fossils of a resonator; 0 drops the mod) and `extra` are mods that join the pool.
        With `guaranteed`, exactly the mods it accepts are the ones the guaranteed draw picks from,
        whatever their tags in the data (the pool then carries `tag` on those: the influence reforge).
        Raises `NotApplicableError` when `tag` is given and the pool holds no mod with it that the
        retained item has a free family and a free slot for.
        """
        retained = retained_item(data, item, forced)
        blocked = blocked_tags(data, retained) if tag is not None else frozenset()
        pool = build_pool(data, retained, max_level, factor, extra, tag_filter=tag is None)
        if guaranteed is not None and tag is not None:
            pool = mark_pool(pool, tag, guaranteed)
        result = cls.over(data, retained, pool, tag, forced, blocked)
        if tag is not None and not guaranteed_candidates(result.pool, result.free, tag, blocked):
            raise NotApplicableError(
                f"the {tag} reforge cannot be used: the pool holds no {tag} mod "
                "that the item has a free slot and a free family for"
            )
        return result

    @classmethod
    def over(
        cls,
        data: GameData,
        retained: Item,
        pool: tuple[PoolFamily, ...],
        tag: str | None,
        forced: Mod | None,
        guaranteed_blocked: frozenset[str] = frozenset(),
        rolls_lucky: bool = False,
        rerolled: frozenset[str] = frozenset(),
    ) -> "Outcomes":
        """The outcomes of drawing from a `pool` already built onto `retained` (see `retained_item`).

        With `rolls_lucky` the values of the mods the draw puts on the item are rolled twice, the better kept. The kept
        mods named in `rerolled` get new values in `sample`.
        """
        return cls(
            data, retained, pool, total_distribution(data, retained), tag, None if forced is None else forced.id, guaranteed_blocked,
            rolls_lucky, rerolled,
        )

    @classmethod
    def fill(cls, data: GameData, retained: Item, totals: Mapping[int, Fraction]) -> "Outcomes":
        """The outcomes of drawing onto `retained`, which keeps every mod it holds, up to a total.

        `totals` is the probability of each total number of mods of the finished item (the mods of
        `retained` included), so one add is `{len(retained.mods) + 1: 1}` and a draw never takes a
        mod away. The pool is built on `retained`, whose rarity decides the capacity. Use `add_one_mod`
        and `draw_onto` of `add.py`; `add_one_mod` refuses an add that has no legal mod.
        """
        return cls(data, retained, build_pool(data, retained), totals, None, None)

    @property
    def components(self) -> tuple[tuple[Fraction, "Outcomes"], ...]:
        """A pool draw is a mixture of one part, itself (see `ActionOutcomes`)."""
        return ((ONE, self),)

    @property
    def fractures(self) -> bool:
        """Whether one finished mod is fractured: never for a plain draw (see `fracturing`)."""
        return False

    def fracturing(self) -> "ActionOutcomes":
        """The same draw followed by a fracture of one finished mod, uniformly (a Fractured Fossil's)."""
        from .mixture import Mixture

        return Mixture(self.data, ((ONE, self),), True)

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
            self.pool, self.free, self.tag, self.totals, len(self.retained.mods), label, self.guaranteed_blocked
        )

    @cached_property
    def _tiers(self) -> Mapping[str, int]:
        return tiers_of(self.data, self.retained)

    @cached_property
    def _float_weights(self) -> Mapping[str, float]:
        return {entry.mod.id: float(entry.weight) for family in self.pool for entry in family.mods}

    def sample(self, rng: random.Random) -> Item:
        """One finished item: the same process, drawn with `rng`, with values rolled and tiers set."""
        totals = list(self.totals)
        total = rng.choices(totals, weights=[float(self.totals[t]) for t in totals])[0]
        drawn = sample_new_mods(
            self.pool, self.free, self.tag, total, len(self.retained.mods), rng, self._float_weights,
            self.guaranteed_blocked,
        )
        rolled = [entry.mod for entry in drawn]
        kept = tuple(entry for entry in self.retained.mods if entry.mod_id != self.forced)
        if self.rerolled:
            kept = tuple(
                replace(entry, values=roll_values(rng, self.data.mods[entry.mod_id])) if entry.mod_id in self.rerolled else entry
                for entry in kept
            )
        if self.forced is not None:
            rolled.insert(0, self.data.mods[self.forced])
        new = tuple(
            ExplicitMod(
                mod.id,
                self._tiers[mod.id] if mod.id != self.forced else self._tiers.get(mod.id, 1),
                roll_values(rng, mod, self.rolls_lucky),
            )
            for mod in rolled
        )
        return self.retained.changed(self.data, mods=(*kept, *new))
