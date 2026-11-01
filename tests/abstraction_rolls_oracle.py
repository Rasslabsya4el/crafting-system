"""Layer 1 for roll requirements (#71): every concrete item WITH its values, listed one by one, independent of `abstraction`.

`abstraction_oracle.finished_items` lists the finished items of a reroll with every value at the low end of
its range. Here each of them is expanded again: the mods the reroll drew roll every value, and a Divine Orb
rerolls the values of the mods it changes. Nothing is computed from a formula: a fair value is each integer
of the range in turn, a lucky value (a Sanctified Fossil: rolled twice, the better one kept) is every pair of
rolls, the better of each pair counted. The one thing taken from `abstraction_oracle` is the list of finished
items and the compare; the one thing taken from `actions` is the contract (`Action`, `Rerolled`) for the toys
that stand in for the Divine Orb and the Sanctified Fossil.

`TINY` is the small pool of `abstraction_pool` with every range cut to two or four integers, so that the
enumeration is a few thousand items: the Life tiers roll 1..4 and 5..8, the hybrid Lightning damage two
stats of 1..2 and 3..4 / 1..2, Lightning Resistance 1..2, 3..4 and 5..6, the crafted lock 1..2.
"""

import dataclasses
import itertools
import random
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping
from fractions import Fraction

from abstraction_fossil import fossil_finished
from abstraction_oracle import finished_items
from abstraction_pool import (
    CRAFTED,
    DAMAGE_1,
    DAMAGE_2,
    GEM,
    LEVEL,
    LIFE_1,
    LIFE_2,
    MANA_1,
    MANA_2,
    RESIST_1,
    RESIST_2,
    RESIST_3,
    SMALL,
)
from items_support import AMULET

from crafting_system.actions import (
    Action,
    Adds,
    ChaosOrb,
    NotApplicableError,
    Reads,
    Rerolled,
)
from crafting_system.actions.metamods import locked_sides, on_locked_side
from crafting_system.data import GameData, Mod
from crafting_system.data.model import StatRange
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table

RANGES = {
    LIFE_1: ((1, 4),),
    LIFE_2: ((5, 8),),
    DAMAGE_1: ((1, 2), (1, 2)),
    DAMAGE_2: ((3, 4), (1, 2)),
    RESIST_1: ((1, 2),),
    RESIST_2: ((3, 4),),
    RESIST_3: ((5, 6),),
    MANA_1: ((2, 2),),
    MANA_2: ((4, 4),),
    GEM: ((1, 1),),
    CRAFTED: ((1, 2),),
}


def _cut(mod: Mod) -> Mod:
    return dataclasses.replace(
        mod, stats=tuple(StatRange(stat.id, low, high) for stat, (low, high) in zip(mod.stats, RANGES[mod.id], strict=True))
    )


TINY: GameData = dataclasses.replace(SMALL, mods={mod_id: _cut(SMALL.mods[mod_id]) for mod_id in RANGES})
TIERS = tier_table(TINY, AMULET)


def rolled(mod_id: str, *values: int, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    """The mod of `TINY` at its table tier (1 for a mod that cannot spawn) with these values."""
    return ExplicitMod(mod_id, TIERS.get(mod_id, 1), values, fractured=fractured, crafted=crafted)


def tiny_item(*mods: ExplicitMod, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    return Item.build(TINY, base_id=AMULET, item_level=LEVEL, rarity=rarity, mods=mods, **fields)


def value_cases(data: GameData, mod_id: str, lucky: bool = False) -> list[tuple[tuple[int, ...], Fraction]]:
    """Every tuple of values a mod can roll, with its exact chance, found by listing the rolls.

    A stat rolls each integer of its range with the same chance and the stats are independent. With `lucky`
    each stat is rolled twice (every pair of rolls is one case) and the better value is kept, the better being
    the one nearer the stat's `max`.
    """
    per_stat = []
    for stat in data.mods[mod_id].stats:
        rolls = range(min(stat.min, stat.max), max(stat.min, stat.max) + 1)
        counts: Counter = Counter()
        if lucky:
            better = max if stat.max >= stat.min else min
            for first, second in itertools.product(rolls, rolls):
                counts[better(first, second)] += 1
        else:
            for value in rolls:
                counts[value] += 1
        total = sum(counts.values())
        per_stat.append([(value, Fraction(count, total)) for value, count in sorted(counts.items())])
    cases = []
    for combination in itertools.product(*per_stat):
        chance = Fraction(1)
        for _, each in combination:
            chance *= each
        cases.append((tuple(value for value, _ in combination), chance))
    return cases


def reroll_values(
    data: GameData, item: Item, rolling: Callable[[ExplicitMod], bool], lucky: bool = False
) -> list[tuple[Item, Fraction]]:
    """Every item that `item` can become when the values of the mods that satisfy `rolling` are rolled afresh."""
    options = [
        value_cases(data, entry.mod_id, lucky) if rolling(entry) else [(entry.values, Fraction(1))] for entry in item.mods
    ]
    result = []
    for combination in itertools.product(*options):
        chance = Fraction(1)
        mods = []
        for entry, (values, each) in zip(item.mods, combination, strict=True):
            chance *= each
            mods.append(dataclasses.replace(entry, values=values))
        result.append((item.changed(data, mods=tuple(mods)), chance))
    return result


def finished_with_values(
    data: GameData, start: Item, tag: str | None = None, *, forced: str | None = None, cap: int | None = None, lucky: bool = False
) -> list[tuple[Item, Fraction]]:
    """Every finished item of a reroll of `start` (kept: its fractured mods and the forced mod), the values of every drawn mod rolled."""
    kept = {entry.mod_id for entry in start.fractured_mods} | ({forced} if forced else set())
    result: dict[Item, Fraction] = defaultdict(Fraction)
    for item, chance in finished_items(data, start, tag, forced=forced, cap=cap):
        for rolled_item, each in reroll_values(data, item, lambda entry: entry.mod_id not in kept, lucky):
            result[rolled_item] += chance * each
    assert sum(result.values()) == 1
    return list(result.items())


def resonator_with_values(data: GameData, action, start: Item, lucky: bool = False) -> list[tuple[Item, Fraction]]:
    """Every finished item of the resonator `action` on `start` (`abstraction_fossil.fossil_finished`), the values of every drawn mod rolled."""
    kept = {entry.mod_id for entry in start.fractured_mods}
    result: dict[Item, Fraction] = defaultdict(Fraction)
    for item, chance in fossil_finished(data, action, start):
        for rolled_item, each in reroll_values(data, item, lambda entry: entry.mod_id not in kept, lucky):
            result[rolled_item] += chance * each
    assert sum(result.values()) == 1
    return list(result.items())


def divine_items(
    data: GameData, start: Item, changed: Iterable[tuple[str, bool, bool]], lucky: bool = False
) -> list[tuple[Item, Fraction]]:
    """Every item that `start` can become when the mods with these `(mod id, fractured, crafted)` keys are rerolled."""
    keys = set(changed)
    return reroll_values(data, start, lambda entry: (entry.mod_id, entry.fractured, entry.crafted) in keys, lucky)


# --- the toys that stand in for the Divine Orb and the Sanctified Fossil -----------------------------------


@dataclasses.dataclass(frozen=True, eq=False)
class RerolledOutcomes:
    """The outcomes of `ToyDivine`: one `Rerolled` part of probability 1 and nothing else."""

    data: GameData
    item: Item
    changed: frozenset[tuple[str, bool, bool]]
    lucky: bool = False

    @property
    def components(self):
        return ((Fraction(1), Rerolled(self.data, self.item, self.changed, self.lucky)),)

    @property
    def fractures(self) -> bool:
        return False

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        held = {entry.mod_id for entry in self.item.mods}
        return Fraction(1) if set(mod_ids) <= held else Fraction(0)

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping:
        return {frozenset(): Fraction(1)}

    def sample(self, rng: random.Random) -> Item:
        mods = tuple(
            dataclasses.replace(entry, values=tuple(rng.randint(s.min, s.max) for s in self.data.mods[entry.mod_id].stats))
            if (entry.mod_id, entry.fractured, entry.crafted) in self.changed
            else entry
            for entry in self.item.mods
        )
        return self.item.changed(self.data, mods=mods)


@dataclasses.dataclass(frozen=True)
class ToyDivine(Action):
    """Rerolls the values of every mod that is not fractured and not on a side a lock protects, in place."""

    lucky: bool = False

    def label(self, data: GameData | None = None) -> str:
        return "Toy Divine"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Divine Orb": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), rerolls_values=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.removal()

    def outcomes(self, data: GameData, item: Item) -> RerolledOutcomes:
        if item.corrupted or item.rarity not in (Rarity.RARE, Rarity.MAGIC):
            raise NotApplicableError("the toy rerolls a rare or magic item that is not corrupted")
        locked = locked_sides(data, item)
        changed = frozenset(
            (entry.mod_id, entry.fractured, entry.crafted)
            for entry in item.mods
            if not entry.fractured and not on_locked_side(data, entry, locked)
        )
        return RerolledOutcomes(data, item, changed, self.lucky)


@dataclasses.dataclass(frozen=True)
class ToyLuckyChaos(Action):
    """A Chaos Orb whose rolled values are rolled twice, the better one kept (what a Sanctified Fossil adds)."""

    def label(self, data: GameData | None = None) -> str:
        return "Toy Lucky Chaos"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Lucky Orb": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing()

    def outcomes(self, data: GameData, item: Item):
        return dataclasses.replace(ChaosOrb().outcomes(data, item), rolls_lucky=True)


def with_new_values(
    data: GameData, finished: Iterable[tuple[Item, Fraction]], start: Item, lucky: bool = False
) -> list[tuple[Item, Fraction]]:
    """Each finished item of an orb that adds mods (`abstraction_adds_oracle`), the values of the mods `start` did not hold rolled."""
    held = {entry.mod_id for entry in start.mods}
    result: dict[Item, Fraction] = defaultdict(Fraction)
    for item, chance in finished:
        for rolled_item, each in reroll_values(data, item, lambda entry: entry.mod_id not in held, lucky):
            result[rolled_item] += chance * each
    assert sum(result.values()) == 1
    return list(result.items())
