"""The corrupted implicit that a Bloodstained Fossil adds, and the outcomes of a resonator that holds it (ticket #261, ADR-0038).

A resonator with a Bloodstained Fossil rerolls the item as its other fossils say and **also** corrupts it and adds one corrupted
implicit "similar to the outcome of using a Vaal Orb" (`corruption.bloodstained_fossil_implicit`). The two parts are independent:
the implicit is not affected by the other fossils, and the reroll does not look at the implicits.

* The implicit is drawn by weight from the corrupted pool of the item's base at its item level (`corrupted_implicit_pool`, ADR-0037)
  and never fails to be added (`corruption.bloodstained_never_fails`, owner). Each stat rolls uniformly over the integers of its
  range; no fossil, not even a Sanctified one, makes it lucky.
* It replaces one implicit of the item chosen uniformly (`corruption.implicit_replaces_existing`, the Vaal Orb's rule), or is just
  added when the item has none. The implicits of the item are the ones it stores and the ones of its base that it does not store
  (`Item` keeps an implicit only when given one, the game's item has the base's own). With a Gilded Fossil in the set it replaces
  every implicit (`fossils.bloodstained_gilded_replaces_all_implicits`).

`ImplicitDraw` is that second part alone: `cases` lists every way it can end with its exact chance (which implicits are kept, which
mod is drawn), `chance_all` and `sample` answer for the implicits of the finished item. `BloodstainedOutcomes` is the whole result
of the resonator and has the four ways in of an `ActionOutcomes`:

* `components`: one part per component of the reroll and case of the draw, the reroll's `Outcomes` with its `retained` item made
  corrupted and holding the implicits of the case, the corrupted one included. A part's share is the product of the two chances.
  The compressed state keeps no corrupted implicit (ADR-0036), so the parts of one reroll component that differ in the drawn mod all
  give the same states, and what the target wants of the implicit is decided where the target is known.
* `chance_all(mod_ids)`: the chance that the finished item holds all the mods, explicit ones and implicits alike. It is the
  product of the reroll's chance for the explicit mods and the draw's chance for the implicits (ADR-0038: two independent numbers).
* `distribution(label)`: the new explicit mods seen through `label`, the reroll's, since the draw adds none.
* `sample(rng)`: the reroll's sample, corrupted, with the implicits of a drawn case and its values rolled.
"""

import random
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cached_property

from crafting_system.data import GameData, Mod
from crafting_system.items import ImplicitMod, Item
from crafting_system.items.implicits import BASE_GRADE
from crafting_system.rules import get_rule

from .corrupted_pool import CorruptedImplicitPool, corrupted_implicit_pool
from .draw import Outcome
from .errors import OutOfScopeError
from .mixture import Mixture
from .outcomes import Outcomes
from .rolls import roll_values

BLOODSTAINED_ADDS_VAAL_IMPLICIT = get_rule("corruption.bloodstained_fossil_implicit")
BLOODSTAINED_NEVER_FAILS = get_rule("corruption.bloodstained_never_fails")
IMPLICIT_REPLACES_EXISTING = get_rule("corruption.implicit_replaces_existing")
IMPLICIT_POOL_BY_ITEM_CLASS = get_rule("corruption.implicit_pool_by_item_class")
GILDED_REPLACES_ALL_IMPLICITS = get_rule("fossils.bloodstained_gilded_replaces_all_implicits")

CLAIM_IDS = frozenset(
    rule.id
    for rule in (
        BLOODSTAINED_ADDS_VAAL_IMPLICIT,
        BLOODSTAINED_NEVER_FAILS,
        IMPLICIT_REPLACES_EXISTING,
        IMPLICIT_POOL_BY_ITEM_CLASS,
        GILDED_REPLACES_ALL_IMPLICITS,
    )
)
"""The claims a set with a Bloodstained Fossil reads and every other set does not (`ApplyFossils.claims`)."""

__all__ = ["BloodstainedOutcomes", "ImplicitCase", "ImplicitDraw"]


@dataclass(frozen=True, slots=True)
class ImplicitCase:
    """One way the draw can end: `kept` are the implicits of the item that stay, `drawn` the corrupted one (at its lowest values)."""

    chance: Fraction
    kept: tuple[ImplicitMod, ...]
    drawn: ImplicitMod

    @property
    def implicits(self) -> tuple[ImplicitMod, ...]:
        """All the implicits the finished item holds in this case."""
        return (*self.kept, self.drawn)


@dataclass(frozen=True, eq=False)
class ImplicitDraw:
    """The corrupted implicit a Bloodstained Fossil adds to an item that holds `held` implicits.

    With `replaces_all` (a Gilded Fossil in the set) no implicit of the item stays. Otherwise one of its implicits, chosen
    uniformly, is replaced and the others stay; an item with none just gains the drawn one. The drawn mod is chosen by weight
    from `pool`. An item stores an implicit only when it was given one (`Item`: the base's own implicits are not filled in), but the
    game's item has them: `unstored` is how many implicits of the base the item does not store, and each is as likely to be the
    replaced one as a stored one (ADR-0037: "chosen uniformly among the item's implicits, base and Eldritch ones alike"). When one
    of those goes, every stored implicit stays; the unstored ones are not on the finished item either way (so a base with two implicits
    of its own that the item does not store gives `chance_all` 0 for each of them).
    """

    data: GameData
    pool: CorruptedImplicitPool
    held: tuple[ImplicitMod, ...]
    replaces_all: bool
    unstored: int = 0

    @classmethod
    def for_item(cls, data: GameData, item: Item, replaces_all: bool) -> "ImplicitDraw":
        """The draw on `item`; `OutOfScopeError` when the pool is empty at its item level (no admitted rule says what the use does then)."""
        pool = corrupted_implicit_pool(data, item.base_id, item.item_level)
        if not pool.mods:
            raise OutOfScopeError(
                f"the corrupted implicit pool of {item.base_id} is empty at item level {item.item_level}, and no admitted rule says "
                "what a Bloodstained Fossil does when it has no implicit to add"
            )
        stored = {entry.mod_id for entry in item.implicits}
        unstored = sum(1 for mod_id in data.base_items[item.base_id].implicits if mod_id not in stored)
        return cls(data, pool, item.implicits, replaces_all, unstored)

    @cached_property
    def kept(self) -> tuple[tuple[Fraction, tuple[ImplicitMod, ...]], ...]:
        """The stored implicits that stay with the chance of each: all replaced, none to replace, or one replaced at random."""
        candidates = len(self.held) + self.unstored
        if self.replaces_all or not candidates:
            return ((Fraction(1), ()),)
        each = Fraction(1, candidates)
        patterns = [(each, self.held[:index] + self.held[index + 1 :]) for index in range(len(self.held))]
        if self.unstored:
            patterns.append((each * self.unstored, self.held))  # an implicit of the base that the item does not store goes
        return tuple(patterns)

    @cached_property
    def cases(self) -> tuple[ImplicitCase, ...]:
        """Every end of the draw: each kept pattern with each mod of the pool, the chances summing to exactly 1."""
        total = self.pool.total_weight
        cases = []
        for kept_chance, kept in self.kept:
            for entry in self.pool.mods:
                low = tuple(min(stat.min, stat.max) for stat in entry.mod.stats)
                cases.append(ImplicitCase(kept_chance * Fraction(entry.weight, total), kept, ImplicitMod(entry.mod.id, BASE_GRADE, low)))
        return tuple(cases)

    @cached_property
    def mod_ids(self) -> frozenset[str]:
        """The ids of every implicit a finished item can hold: the ones it has and the ones the pool can give."""
        return frozenset(entry.mod_id for entry in self.held) | self.pool.mod_ids()

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        """The exact chance that the finished item holds all of these implicits; 0 when two of them are drawn ones."""
        wanted = set(mod_ids)
        return sum(
            (case.chance for case in self.cases if wanted <= {entry.mod_id for entry in case.implicits}),
            Fraction(0),
        )

    def sample(self, rng: random.Random) -> tuple[ImplicitMod, ...]:
        """The implicits of one finished item: a case chosen with its chance, the drawn mod's values rolled."""
        case = rng.choices(self.cases, weights=[float(case.chance) for case in self.cases])[0]
        mod = self.data.mods[case.drawn.mod_id]
        return (*case.kept, ImplicitMod(mod.id, BASE_GRADE, roll_values(rng, mod)))


@dataclass(frozen=True, eq=False)
class BloodstainedOutcomes:
    """What a resonator with a Bloodstained Fossil leaves: the `reroll` of its other fossils, then the `draw` of the implicit.

    `reroll` is the `FossilOutcomes` of the same set without the Bloodstained Fossil, which is what the other fossils say; `given`
    is the item the resonator was used on. Every finished item is corrupted. See the module text for the four ways in.
    """

    data: GameData
    given: Item
    reroll: Mixture
    draw: ImplicitDraw

    @property
    def fractures(self) -> bool:
        return self.reroll.fractures

    @cached_property
    def components(self) -> tuple[tuple[Fraction, Outcomes], ...]:
        parts = []
        for share, part in self.reroll.components:
            for case in self.draw.cases:
                retained = part.retained.changed(self.data, corrupted=True, implicits=case.implicits)
                parts.append((share * case.chance, replace(part, retained=retained)))
        return tuple(parts)

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        """The exact chance that the finished item holds all of these mods, implicits included (the two draws are independent).

        Raises `ValueError` for an id that is not in the game data. Two corrupted implicits can never be on one item, so that chance is 0.
        """
        wanted = list(mod_ids)
        unknown = sorted(set(wanted) - self.data.mods.keys())
        if unknown:
            raise ValueError(f"mod {unknown[0]} is not in the game data")
        implicit = [mod_id for mod_id in wanted if mod_id in self.draw.mod_ids]
        explicit = [mod_id for mod_id in wanted if mod_id not in self.draw.mod_ids]
        return self.reroll.chance_all(explicit) * self.draw.chance_all(implicit)

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """The new explicit mods seen through `label`: the reroll's, since the draw adds none."""
        return self.reroll.distribution(label)

    def sample(self, rng: random.Random) -> Item:
        """One finished item: the reroll's sample, corrupted, holding the implicits of a drawn case."""
        finished = self.reroll.sample(rng)
        return finished.changed(self.data, corrupted=True, implicits=self.draw.sample(rng))
