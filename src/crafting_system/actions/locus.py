"""The Locus of Corruption as an exact action: four outcomes, two corrupted implicits of different groups, and two dead ends (ticket #262, ADR-0038).

The Corruption Altar of a tier 3 Incursion room corrupts one uncorrupted item of any class the Vaal Orb takes and applies one of four
outcomes (`corruption.locus_four_outcomes`):

1. **Two corrupted implicits**, with the share `s` of `corruption.locus_two_implicit_share_decision` (the owner's 0.25, `approximate`, its
   interval 0.088 to 0.265 in the claim). The first is drawn by weight from the corrupted pool of the item's base at its item level
   (`corrupted_implicit_pool`, ADR-0037). The second is drawn by weight from the pool without the mods that share a mod group with the first
   (`corruption.locus_second_implicit_other_group`, `approximate`, Craft of Exile only; a mod group is a family, `data.conflicts`), so the
   chance of two named mods A and B of different groups is `wA/W * wB/(W - gA) + wB/W * wA/(W - gB)`, with `gX` the weight of X's group.
   They replace implicits of the item (`locus.replaces_two_implicits`): an item with three or more loses two chosen uniformly among its
   pairs, one with two loses both, one with one loses it and gains the second besides, one with none gains both. Each stat of each drawn
   mod rolls uniformly over its integer range (`affix_pool.values_uniform_integers`); a result shows both at their lowest values. The
   explicit mods are not touched.
2. **Every white socket turns non-white** (3.29.0): nothing a target can mind (ADR-0036, "Sockets"); the item is only corrupted.
3. **An influenced rare** of the same base with random affixes. For a target that asks for a corrupted implicit it is a dead end, as the
   Vaal Orb's brick (it adds no corrupted implicit). It is the same dead state as the brick (`corruption.dead_end`): the item corrupted, a
   rare, with its fractured mods and nothing else; the influence it gains is not in it, since nothing can act on a corrupted item. For a
   target that only allows a corrupted item it stays a dead end until the brick's fill (#260) is given a random influence; until then
   the plan never counts it as a goal, which errs high on the cost.
4. **The item is destroyed**: a dead end, the same dead state; the plan restarts and pays a new start item.

Outcomes 2 to 4 share what the two-implicit outcome leaves, `(1 - s) / 3` each (all four are 1/4 at the owner's 0.25; the claim of the four
equal outcomes and the share decision agree there).

**The price** of a use is the price-file entry "Locus of Corruption (use)" (`locus.cost`), whose default is 0 Chaos Orbs
(`prices.default_prices`, also standing in for a price file fetched before the entry existed). A target's `actions:` list that leaves out
`locus` leaves the Locus out of the plan (ADR-0024).

**Refusals.** `NotApplicableError` for a corrupted item ("The Corruption Altar device cannot be used on an item that is already corrupted")
and a base whose class has no corrupted pool; `OutOfScopeError` for a Cluster or a Timeless Jewel (ADR-0004), for an item level at which the
pool is empty, and for a pool in which some first draw leaves no mod of another group for the second (no admitted rule says what the altar
does then; no real pool is like that). The kind is not listed for any of these.

**What it declares** is the Vaal Orb's: `Reads` the implicits and the junk; `Adds.corrupting(keeps_mods=True)`, since the outcomes that can
still be a goal keep the explicit mods. It is never previewed (`corruption.locus_no_preview`), neither cuts nor spends Memory Strands.
"""

import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cached_property
from itertools import combinations

from crafting_system.data import GameData, conflicts
from crafting_system.items import ImplicitMod, Item, is_corrupted_implicit
from crafting_system.items.implicits import BASE_GRADE
from crafting_system.items.words import base_words
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .corrupted_pool import CorruptedImplicitPool, corrupted_implicit_pool
from .corruption import dead_end
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .rolls import roll_values
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, NOT_SPENT_BY, StrandUse

__all__ = [
    "LOCUS_USE",
    "LocusOfCorruption",
    "LocusOutcomes",
    "TwoImplicitDraw",
]

FOUR_OUTCOMES = get_rule("corruption.locus_four_outcomes")
SHARE = get_rule("corruption.locus_two_implicit_share_decision")
SHARE_OBSERVED = get_rule("corruption.locus_two_implicit_share_observed")
OTHER_GROUP = get_rule("corruption.locus_second_implicit_other_group")
NO_PREVIEW = get_rule("corruption.locus_no_preview")
REPLACES_TWO = get_rule("locus.replaces_two_implicits")
POOL_BY_ITEM_CLASS = get_rule("corruption.implicit_pool_by_item_class")
JEWEL_POOL = get_rule("corruption.jewel_implicit_pool")
VALUES_UNIFORM = get_rule("affix_pool.values_uniform_integers")
CORRUPTED_IS_FINAL = get_rule("corruption.corrupted_modifiable_exceptions")
COST = get_rule("locus.cost")

(LOCUS_USE,) = COST.value  # "Locus of Corruption (use)": the price-file name of one use
TWO_IMPLICIT_SHARE = Fraction(str(SHARE.value["share"]))
OTHER_SHARE = (1 - TWO_IMPLICIT_SHARE) / 3  # the sockets, the influenced rare and the destruction, each


@dataclass(frozen=True, slots=True)
class PairCase:
    """One way the double corruption can end: `kept` are the implicits that stay, `drawn` the two corrupted ones (at their lowest values)."""

    chance: Fraction
    kept: tuple[ImplicitMod, ...]
    drawn: tuple[ImplicitMod, ImplicitMod]

    @property
    def implicits(self) -> tuple[ImplicitMod, ...]:
        return (*self.kept, *self.drawn)


def _lowest(mod) -> ImplicitMod:
    return ImplicitMod(mod.id, BASE_GRADE, tuple(min(stat.min, stat.max) for stat in mod.stats))


@dataclass(frozen=True, eq=False)
class TwoImplicitDraw:
    """The two corrupted implicits of a double corruption on an item that holds `held` implicits (see the module text)."""

    data: GameData
    pool: CorruptedImplicitPool
    held: tuple[ImplicitMod, ...]

    @classmethod
    def for_item(cls, data: GameData, item: Item) -> "TwoImplicitDraw":
        """The draw on `item`; `OutOfScopeError` when the pool is empty or some first draw leaves nothing for the second."""
        pool = corrupted_implicit_pool(data, item.base_id, item.item_level)
        if not pool.mods:
            raise OutOfScopeError(
                f"the corrupted implicit pool of {base_words(data, item.base_id)} is empty at item level {item.item_level}, and the model has no rule for what the Locus of Corruption does when it has no implicit to add",
                detail=(
                    f"the corrupted implicit pool of {item.base_id} is empty at item level {item.item_level}, and no admitted rule says "
                    "what the Locus of Corruption does when it has no implicit to add"
                ),
            )
        draw = cls(data, pool, item.implicits)
        lonely = next((entry for entry in pool.mods if draw.rest_weight(entry.mod.id) == 0), None)
        if lonely is not None:
            raise OutOfScopeError(
                f"every corrupted implicit {base_words(data, item.base_id)} can get at item level {item.item_level} shares a mod group with {lonely.mod.id}, so the Locus of Corruption has no second implicit to draw after it, and the model has no rule for that",
                detail=(
                    f"the corrupted pool of {item.base_id} at item level {item.item_level} holds no mod of another group than {lonely.mod.id}: "
                    "no admitted rule says what the second draw of a double corruption does then"
                ),
            )
        return draw

    def group_weight(self, mod_id: str) -> int:
        """gX: the weight of the mods of the pool that share a mod group with `mod_id` (the mod itself included)."""
        mod = self.data.mods[mod_id]
        return sum(entry.weight for entry in self.pool.mods if entry.mod.id == mod_id or conflicts(mod, entry.mod))

    def rest_weight(self, mod_id: str) -> int:
        """W - gX: the weight left for the second draw after `mod_id` is drawn first."""
        return self.pool.total_weight - self.group_weight(mod_id)

    @cached_property
    def pairs(self) -> tuple[tuple[Fraction, tuple[str, str]], ...]:
        """Each unordered pair of corrupted implicits with its exact chance (both orders summed), the ids sorted."""
        total = self.pool.total_weight
        found: dict[tuple[str, str], Fraction] = {}
        for first in self.pool.mods:
            rest = self.rest_weight(first.mod.id)
            for second in self.pool.mods:
                if second.mod.id == first.mod.id or conflicts(first.mod, second.mod):
                    continue
                key = tuple(sorted((first.mod.id, second.mod.id)))
                found[key] = found.get(key, Fraction(0)) + Fraction(first.weight, total) * Fraction(second.weight, rest)
        return tuple((chance, key) for key, chance in found.items())

    @cached_property
    def kept(self) -> tuple[tuple[Fraction, tuple[ImplicitMod, ...]], ...]:
        """The implicits that stay with the chance of each: none up to two held, else every held one but a pair chosen uniformly."""
        if len(self.held) <= 2:
            return ((Fraction(1), ()),)
        gone = list(combinations(range(len(self.held)), 2))
        each = Fraction(1, len(gone))
        return tuple((each, tuple(entry for index, entry in enumerate(self.held) if index not in pair)) for pair in gone)

    @cached_property
    def cases(self) -> tuple[PairCase, ...]:
        """Every end of the double corruption, the chances summing to exactly 1."""
        mods = self.data.mods
        return tuple(
            PairCase(kept_chance * chance, kept, (_lowest(mods[a]), _lowest(mods[b])))
            for kept_chance, kept in self.kept
            for chance, (a, b) in self.pairs
        )


@dataclass(frozen=True, eq=False)
class LocusOutcomes(Finite):
    """The result of one use of the altar: `Finite` over the corrupted items it can leave, with a sampler that rolls the two drawn implicits."""

    def sample(self, rng: random.Random) -> Item:
        finished = super().sample(rng)
        mods = self.data.mods
        rolled = tuple(
            replace(entry, values=roll_values(rng, mods[entry.mod_id])) if is_corrupted_implicit(mods[entry.mod_id]) else entry
            for entry in finished.implicits
        )
        return finished.changed(self.data, implicits=rolled) if rolled != finished.implicits else finished

    def implicit_chances(self, mod_ids: Iterable[str]) -> Fraction:
        """The exact chance that the finished item holds all of these implicits, the drawn ones and the ones that stay alike."""
        wanted = set(mod_ids)
        unknown = sorted(wanted - self.data.mods.keys())
        if unknown:
            raise ValueError(f"mod {unknown[0]} is not in the game data")
        return sum((chance for chance, item in self.results if wanted <= {entry.mod_id for entry in item.implicits}), Fraction(0))


@dataclass(frozen=True)
class LocusOfCorruption(Action):
    """One use of the Locus of Corruption's altar."""

    def label(self, data: GameData | None = None) -> str:
        return "Locus of Corruption"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE, NOT_SPENT_BY)  # ADR-0041: neither cuts nor spends; the dead ends keep the count

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(
            rule.id
            for rule in (
                FOUR_OUTCOMES,
                SHARE,
                SHARE_OBSERVED,
                OTHER_GROUP,
                NO_PREVIEW,
                REPLACES_TWO,
                POOL_BY_ITEM_CLASS,
                JEWEL_POOL,
                VALUES_UNIFORM,
                CORRUPTED_IS_FINAL,
                COST,
            )
        )

    def reads(self, data: GameData) -> Reads:
        # how many implicits the item holds decides which go; the junk is kept by every outcome but the dead ends
        return Reads(junk=True, families=frozenset(), implicits=True, block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.corrupting(keeps_mods=True, draws=False)

    def outcomes(self, data: GameData, item: Item) -> LocusOutcomes:
        """The four outcomes on `item` as the corrupted items they leave, with their exact chances (see the module text for the refusals)."""
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and the Corruption Altar cannot be used on an item that is already corrupted")
        draw = TwoImplicitDraw.for_item(data, item)
        landed: dict[Item, Fraction] = {}

        def land(result: Item, chance: Fraction) -> None:
            landed[result] = landed.get(result, Fraction(0)) + chance

        for case in draw.cases:
            land(item.changed(data, corrupted=True, implicits=case.implicits), TWO_IMPLICIT_SHARE * case.chance)
        land(item.changed(data, corrupted=True), OTHER_SHARE)  # every white socket turns non-white: nothing a target minds
        land(dead_end(data, item), 2 * OTHER_SHARE)  # the influenced rare and the destruction
        return LocusOutcomes(data, item, tuple((chance, result) for result, chance in landed.items()))


@kind(
    "locus",
    order=108,
    corrupting=True,
    applies_only_to="an item whose class has a corrupted implicit pool",
)
def _locus(data: GameData, item: Item):
    if item.corrupted:
        return
    try:
        TwoImplicitDraw.for_item(data, item)
    except ValueError:
        return  # no pool (NotApplicableError), a Cluster or Timeless Jewel, an empty pool or one with no second draw (OutOfScopeError), an unknown base
    yield LocusOfCorruption()
