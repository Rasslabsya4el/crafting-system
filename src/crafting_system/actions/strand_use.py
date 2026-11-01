"""What an action does with Memory Strands: whether its draws cut tiers, and what it spends (ADR-0041; ticket #276).

Every action answers `Action.strand_use(data)` with a `StrandUse`, or with None when it has declared nothing. The declaration has two
parts, one per question of ADR-0041:

* `cuts`: the random draws of explicit mods the action makes see the tier cut of the item (`cut.py`, ADR-0040). The action builds its
  pool with `self.cut_of(data, item)`, which is the `Cut` of the item's count before the craft for an action that cuts and None for one
  that does not. A fixed result (an essence's guaranteed mod, a bench mod) is never cut; a fossil, a Harvest craft or a beast never cuts.
* `spend`: the law of the strands the craft uses up, a `SpendLaw`. The craft draws `x` from the law and the count becomes
  `max(0, s - x)` *after* the cut, which used the count before (claim `memory_strands.cut_uses_strands_before_spend`). A spend larger
  than the count empties it; the count never goes below 0. Every law is a uniform whole number on 0 to a ceiling (claim
  `memory_strands.spend_law_uniform`, `approximate`); the ceiling may depend on the number of mods on the item before the craft
  (the Exalted Orb: `SpendLaw.by_mods`).

**An undeclared action is refused on an item with one strand or more** (`OutOfScopeError`, the default of ADR-0004), so no later action
can silently ignore strands; at 0 strands it behaves as it always did. The refusal and the spend are made by `Action` itself, around
the `outcomes` of every subclass, so an action writes neither: it declares `strand_use`, passes its `cut_of` to the pool, and the
result of a spending action on a stranded item is a `Spent`, the same `ActionOutcomes` with one more answer, `strands_after`.

`Spent` leaves `components`, `chance_all` and `distribution` as the draw gives them: the spend is independent of the mods drawn, so the
distribution of the new mods does not change and the distribution of the count after the craft is `strands_after`, the second factor of
the joint chance. `sample` rolls the spend and sets the count of the finished item. An action that spends nothing, or an item with no
strands, returns the draw itself, so no answer at 0 strands changes by a bit; `strands_after(outcomes, count)` is `{count: 1}` then.

Every declaration cites the claims it rests on (`StrandUse.claims`). They are **not** among `Action.claims`, which would list the
(approximate) strand claims on every answer of B1 to B4, strands off or on; they are `Action.strand_claims`, which a plan that
considers strands adds to its approximate inputs (ADR-0028). This module and `cut` are shared by all actions for that reason
(`contract.SHARED_BY_ALL`): importing a name from them does not make an action name their claims.

The table of ADR-0041 is declared in each action's own module: the actions of B1 (#276) and the veiled, Eldritch (Chaos, Embers, Ichors,
Conflict), influenced Exalted, Dominance, beast influence, Blessed, catalyst and Awakener's actions (B5-11a to d and f). The rest declare their own
rows (B5-11e, g and h: Harvest add/remove and swaps, the recombinator, imprints): until they do, they are refused on a stranded item, as are the
Eldritch Exalted and Annulment Orbs, which no ticket or row of the table names.
"""

import random
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property
from typing import TYPE_CHECKING

from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.rules import Rule, get_rule

from .cut import (
    CULL_COUNTS_ELIGIBLE_TIERS,
    CUT_USES_STRANDS_BEFORE_SPEND,
    NO_STRANDS_NO_CUT,
    ROLLABLE_TIERS,
    WEIGHTS_OF_KEPT_TIERS,
    ZERO_IS_NO_CULL,
)

if TYPE_CHECKING:
    from .contract import ActionOutcomes

__all__ = [
    "ANNULMENT_KEEPS_STRANDS",
    "CUT_CLAIMS",
    "CUT_FOLLOWS_SPEND_TABLE",
    "DIVINE_KEEPS_STRANDS",
    "FOSSIL_HARVEST_NOT_CUT",
    "NOT_SPENT_BY",
    "SCOURING_KEEPS_STRANDS",
    "TAILORING_LEAVES_STRANDS",
    "SPEND_BASIC",
    "SPEND_CHAOS_FAMILY",
    "SPEND_ESSENCE",
    "SPEND_EXALTED",
    "SPEND_LAW_UNIFORM",
    "SPEND_SPECIAL_ORBS",
    "Spent",
    "SpendLaw",
    "StrandUse",
    "strands_after",
]

SPEND_BASIC = get_rule("memory_strands.spend_ranges_basic")  # Transmutation, Augmentation, Alteration 8; Regal 16
SPEND_CHAOS_FAMILY = get_rule("memory_strands.spend_ranges_chaos_family")  # Alchemy, Chaos 50
SPEND_ESSENCE = get_rule("memory_strands.spend_ranges_essence")  # any essence 80
SPEND_EXALTED = get_rule("memory_strands.spend_exalted_by_mod_count")  # 16, 22, 26, 32, 34, 38 by the mods before the craft
SPEND_SPECIAL_ORBS = get_rule("memory_strands.spend_ranges_special_orbs")  # value: eldritch_chaos 60, veiled_chaos 80, awakeners 100 (B5-11a, b, f)
SPEND_LAW_UNIFORM = get_rule("memory_strands.spend_law_uniform")
# The claims behind the actions that neither cut nor spend (`StrandUse.untouched`).
NOT_SPENT_BY = get_rule("memory_strands.not_spent_by")  # resonators, Harvest, beasts, benches; the wiki lists Fracturing, Annulment, Scouring, Divine neither way
CUT_FOLLOWS_SPEND_TABLE = get_rule("memory_strands.cut_follows_spend_table")  # the emulator cuts exactly the methods that have a spend row
FOSSIL_HARVEST_NOT_CUT = get_rule("memory_strands.fossil_harvest_not_cut")
ANNULMENT_KEEPS_STRANDS = get_rule("memory_strands.annulment_keeps_strands")
SCOURING_KEEPS_STRANDS = get_rule("memory_strands.scouring_keeps_strands")
DIVINE_KEEPS_STRANDS = get_rule("memory_strands.divine_keeps_strands")
TAILORING_LEAVES_STRANDS = get_rule("enchantment.tailoring_orb_leaves_memory_strands")  # Tempering and Tailoring: the base changes, the mods and the count do not

# The claims every cutting action rests on: the formula, the eligible tiers, 0 strands, the count before the spend, the kept weights.
CUT_CLAIMS: tuple[Rule, ...] = (
    NO_STRANDS_NO_CUT,
    ROLLABLE_TIERS,
    CULL_COUNTS_ELIGIBLE_TIERS,
    ZERO_IS_NO_CULL,
    CUT_USES_STRANDS_BEFORE_SPEND,
    WEIGHTS_OF_KEPT_TIERS,
)


@dataclass(frozen=True)
class SpendLaw:
    """The strands a craft uses up: a whole number drawn uniformly on 0 to a ceiling (claim `memory_strands.spend_law_uniform`).

    `ceilings` has one entry for a ceiling that does not depend on the item, or one per number of explicit mods the item holds before
    the craft (index 0, 1, 2, ...; a larger number takes the last): the Exalted Orb's. The count after the craft is
    `max(0, s - x)`, so a spend larger than the count empties it and a count of 0 stays 0.
    """

    ceilings: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.ceilings or any(type(ceiling) is not int or ceiling < 1 for ceiling in self.ceilings):
            raise ValueError(f"a spend law has at least one ceiling, each a whole number from 1: {self.ceilings!r}")

    @classmethod
    def uniform(cls, ceiling: int) -> "SpendLaw":
        """A uniform whole number on 0 to `ceiling`, whatever is on the item."""
        return cls((ceiling,))

    @classmethod
    def by_mods(cls, *ceilings: int) -> "SpendLaw":
        """A uniform whole number whose ceiling is `ceilings[n]` for an item that holds `n` explicit mods before the craft."""
        return cls(tuple(ceilings))

    def ceiling(self, mods_before: int = 0) -> int:
        """The largest spend of a craft on an item with `mods_before` explicit mods."""
        return self.ceilings[min(max(mods_before, 0), len(self.ceilings) - 1)]

    def after(self, strands: int, mods_before: int = 0) -> Mapping[int, Fraction]:
        """The exact distribution of the count after the craft, from `strands` before it: `max(0, strands - x)` for `x` uniform on 0 to the ceiling.

        The chances sum to exactly 1; a count of 0 stays 0, and a spend larger than the count lands on 0.
        """
        if type(strands) is not int or strands < 0:
            raise ValueError(f"a strand count is a whole number from 0, got {strands!r}")
        ceiling = self.ceiling(mods_before)
        share = Fraction(1, ceiling + 1)
        counts: dict[int, Fraction] = {}
        for spent in range(ceiling + 1):
            left = max(0, strands - spent)
            counts[left] = counts.get(left, Fraction(0)) + share
        return dict(sorted(counts.items()))

    def sample_after(self, rng: random.Random, strands: int, mods_before: int = 0) -> int:
        """One count after the craft, drawn with `rng`."""
        return max(0, strands - rng.randrange(self.ceiling(mods_before) + 1))


@dataclass(frozen=True)
class StrandUse:
    """An action's declaration of what it does with Memory Strands (ADR-0041): whether its draws cut, what it spends, and the claims behind it.

    `spend` is None for an action that leaves the count alone (a fossil, a Harvest craft, a Scouring Orb). `claims` are the ids of the
    registry claims the declaration rests on, listed on an answer that considers strands. Build one with `cutting` (an action that
    cuts and spends) or `untouched` (one that does neither).
    """

    cuts: bool = False
    spend: SpendLaw | None = None
    claims: frozenset[str] = frozenset()

    @classmethod
    def cutting(cls, spend: SpendLaw, *rules: Rule) -> "StrandUse":
        """An action whose draws cut and that spends by `spend`; `rules` are the claims of its ceiling, besides the cut's and the law's."""
        return cls(True, spend, frozenset(rule.id for rule in (*CUT_CLAIMS, SPEND_LAW_UNIFORM, *rules)))

    @classmethod
    def untouched(cls, *rules: Rule) -> "StrandUse":
        """An action that neither cuts nor spends: the strands of the item stay as they are. `rules` are the claims that say so."""
        return cls(False, None, frozenset(rule.id for rule in rules))

    @property
    def reads_count(self) -> bool:
        """Whether the result depends on the count the item has: a cut reads it, and so does a spend (the count after is a function of it)."""
        return self.cuts or self.spend is not None

    @property
    def changes_count(self) -> bool:
        """Whether the count of the finished item can differ from the count before."""
        return self.spend is not None

    def after(self, item: Item) -> Mapping[int, Fraction]:
        """The distribution of the count after one use on `item`, from its count before (the mods it holds fix the ceiling of a law that depends on them)."""
        if self.spend is None:
            return {item.memory_strands: Fraction(1)}
        return self.spend.after(item.memory_strands, len(item.mods))


@dataclass(frozen=True, eq=False)
class Spent:
    """The result of a spending action on an item with strands: `given`, whose finished item then loses a random part of its count.

    It is an `ActionOutcomes` that answers `components`, `fractures`, `chance_all` and `distribution` as `given` does (the spend does
    not depend on the mods drawn), and any other attribute of `given` (a pool, a retained item) too. `strands_after` is the exact
    distribution of the count after the craft, `before` the count the item had; `sample` sets the count of the finished item.

    **The items of `components` and the items a caller builds from `distribution` keep the count before the craft** (the retained item
    holds it, and the cut was made from it); only `strands_after` and `sample` say what is left. A consumer that stores the count in the
    state (B5-4) pairs each outcome of `distribution` with each entry of `strands_after`: they are independent.
    """

    given: "ActionOutcomes"
    data: GameData
    law: SpendLaw
    before: int
    mods_before: int

    def __post_init__(self) -> None:
        if self.before < 1:
            raise ValueError("a result is `Spent` only for an item with strands: with none the draw itself is the result")

    @cached_property
    def strands_after(self) -> Mapping[int, Fraction]:
        """The exact distribution of the count of the finished item: `max(0, before - x)`, `x` uniform on 0 to the ceiling of the law."""
        return self.law.after(self.before, self.mods_before)

    @property
    def components(self):
        return self.given.components

    @property
    def fractures(self) -> bool:
        return self.given.fractures

    def chance_all(self, mod_ids):
        return self.given.chance_all(mod_ids)

    def distribution(self, label):
        return self.given.distribution(label)

    def sample(self, rng: random.Random) -> Item:
        """One finished item from `given`, its count set to what the spend leaves."""
        finished = self.given.sample(rng)
        return finished.changed(self.data, memory_strands=self.law.sample_after(rng, self.before, self.mods_before))

    def __getattr__(self, name: str):
        if name == "given" or name.startswith("__"):  # not yet built (a copy) or a protocol lookup: no recursion
            raise AttributeError(name)
        return getattr(self.given, name)


def strands_after(outcomes: "ActionOutcomes", count: int) -> Mapping[int, Fraction]:
    """The exact distribution of the strand count after the action that gave `outcomes`, on an item that had `count`.

    `{count: 1}` for a result that spends nothing (every result at 0 strands, and an action that declares no spend).
    """
    if isinstance(outcomes, Spent):
        return outcomes.strands_after
    return {count: Fraction(1)}
