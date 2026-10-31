"""The crafting bench: a craft that adds one fixed mod, and Remove Crafted Mods.

Both are deterministic: the new mod is named by the bench option, never drawn. They answer with the
same three methods as the random actions (`chance_all`, `distribution`, `sample`) on a
`BenchOutcomes`, whose one outcome has probability 1. `cost` gives the price of the option as
currency names and counts, for the price layer. Every craft counts as unlocked.
"""

import random
import re
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property

from crafting_system.data import BenchOption, GameData, Mod, conflicts
from crafting_system.items import ExplicitMod, Item, Metamod, Rarity, Side
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Fixed, Reads
from .draw import Outcome
from .errors import NotApplicableError, OutOfScopeError

ADDS_ONE_FIXED_MOD = get_rule("bench_craft.option_adds_one_fixed_mod")
OPTION_ITEM_CLASSES = get_rule("bench_craft.option_item_classes")
OPTION_COST = get_rule("bench_craft.option_cost")
FOLLOW_AFFIX_RULES = get_rule("bench_craft.crafts_follow_affix_rules")
ONE_CRAFTED_MOD = get_rule("bench_craft.one_crafted_mod_by_default")
METAMODS_ARE_CRAFTED_MODS = get_rule("bench_craft.metamods_are_crafted_mods")
REFUSED_ON_CORRUPTED = get_rule("bench_craft.refused_on_corrupted")
EVERY_CRAFT_UNLOCKED = get_rule("bench_craft.every_craft_unlocked")
REROLLS_NOT_B1 = get_rule("bench_craft.rerolls_not_b1_actions")
OTHER_OPTIONS_NOT_MOD_CRAFTS = get_rule("bench_craft.other_options_not_mod_crafts")
REMOVES_ALL_CRAFTED_MODS = get_rule("bench_craft.remove_crafted_mods_removes_all")
VALUES_UNIFORM_INTEGERS = get_rule("affix_pool.values_uniform_integers")

CRAFTED_TIER = 1  # crafted mods have no tier in the data (they never spawn); `Item` needs one, from 1
ONE = Fraction(1)


@dataclass(frozen=True, slots=True)
class CurrencyCost:
    """One currency of a bench price: its name in the game ("Orb of Scouring") and how many."""

    currency: str
    count: int


def without_ranges(text: str) -> str:
    """A mod text with its roll ranges as `#`: "+(6-11) to Strength" -> "+# to Strength"."""
    return re.sub(r"\(-?\d+(?:\.\d+)?--?\d+(?:\.\d+)?\)", "#", text)


def _one_line(text: str) -> str:
    """A mod text on one line: some mods read over two lines, such as a Life craft that also regenerates Mana."""
    return " / ".join(part.strip() for part in text.splitlines() if part.strip())


def _cost(data: GameData, option: BenchOption) -> tuple[CurrencyCost, ...]:
    entries = []
    for entry in option.cost:
        base = data.base_items.get(entry.item_id)
        if base is None:
            raise ValueError(f"the bench cost names {entry.item_id}, which is not a base item in the game data")
        entries.append(CurrencyCost(base.name, entry.count))
    return tuple(entries)


def _refuse_if_corrupted(item: Item, what: str) -> None:
    if item.corrupted:
        raise NotApplicableError(f"the item is corrupted, and a corrupted item takes no {what}")


def _refuse_if_class_not_offered(data: GameData, item: Item, option: BenchOption, what: str) -> None:
    base = data.base_items.get(item.base_id)
    item_class = base.item_class if base is not None else None
    if item_class not in option.item_classes:
        raise NotApplicableError(f"the bench does not offer {what} for the item class {item_class}")


@dataclass(frozen=True, eq=False)
class BenchOutcomes:
    """What a bench action leaves behind: one result, with probability 1.

    `retained` is the item once the action's removals are done and before its added mod, which is
    `added` (None for Remove Crafted Mods). Build one with `BenchCraft.outcomes` or
    `RemoveCraftedMods.outcomes`.
    """

    data: GameData
    retained: Item
    added: Mod | None

    @cached_property
    def components(self) -> tuple[tuple[Fraction, Fixed], ...]:
        """One part with probability 1: the finished item, the added mod at its lowest values (see `ActionOutcomes`)."""
        if self.added is None:
            return ((ONE, Fixed(self.data, self.retained)),)
        low = tuple(min(stat.min, stat.max) for stat in self.added.stats)
        crafted = ExplicitMod(self.added.id, CRAFTED_TIER, low, crafted=True)
        return ((ONE, Fixed(self.data, self.retained.changed(self.data, mods=(*self.retained.mods, crafted)))),)

    @property
    def fractures(self) -> bool:
        return False

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        """1 when the finished item holds all of `mod_ids`, 0 when it does not (two of one family included).

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
        if self.added is not None:
            held.add(self.added.id)
        return ONE if wanted <= held else Fraction(0)

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """The one outcome, the added mod seen through `label`, with probability 1 (empty for a removal)."""
        shown = frozenset({(label(self.added), 1)}) if self.added is not None else frozenset()
        return {shown: ONE}

    def sample(self, rng: random.Random) -> Item:
        """The finished item; the added mod gets a value rolled with `rng` for every stat."""
        if self.added is None:
            return self.retained
        values = tuple(
            rng.randint(min(stat.min, stat.max), max(stat.min, stat.max)) for stat in self.added.stats
        )
        crafted = ExplicitMod(self.added.id, CRAFTED_TIER, values, crafted=True)
        return self.retained.changed(self.data, mods=(*self.retained.mods, crafted))


@dataclass(frozen=True)
class BenchCraft(Action):
    """One bench craft, named by the crafted mod it adds ("JunMaster2AllDamage2_", a metamod's id, ...)."""

    mod_id: str

    @property
    def variant(self) -> str:
        return self.mod_id

    def label(self, data: GameData | None = None) -> str:
        if data is None:
            raise ValueError("a bench craft is named by the text of its mod, so it needs the data")
        mod = data.mods.get(self.mod_id)
        if mod is None:
            raise ValueError(f"the craft {self.mod_id} names a mod that is not in the game data")
        return f"Bench craft {_one_line(without_ranges(mod.text or mod.name))}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        if data is None:
            raise ValueError("a bench craft is priced from the bench data, so it needs the data")
        return {entry.currency: entry.count for entry in self.cost(data)}

    def reads(self, data: GameData) -> Reads:
        """A craft is refused when its mod shares a family with a mod on the item, so it tells those families apart."""
        mod = data.mods.get(self.mod_id)
        if mod is None:
            raise ValueError(f"the craft {self.mod_id} names a mod that is not in the game data")
        return Reads(junk=True, families=frozenset(mod.families), block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset({self.mod_id}), crafted=True, draws=False)

    def option(self, data: GameData) -> BenchOption:
        """The bench option that adds this mod; `ValueError` when the data has none."""
        for option in data.bench_options:
            if option.actions.add_explicit_mod == self.mod_id:
                return option
        raise ValueError(f"the bench has no option that adds the mod {self.mod_id}")

    def cost(self, data: GameData) -> tuple[CurrencyCost, ...]:
        """The price of one craft, as currency names and counts."""
        return _cost(data, self.option(data))

    def outcomes(self, data: GameData, item: Item) -> BenchOutcomes:
        """The outcome of crafting the mod onto `item`.

        A corrupted item and an item class the option is not offered for are checked first, then a
        normal item or an item with no mod, then the rest. Raises `NotApplicableError` for a
        corrupted item, a class not offered, a family already on the item, a full side, and an item
        that already holds a crafted mod; `OutOfScopeError` for a normal item or an item with no mod
        (no admitted rule says what a craft does there) and for an item that holds the multimod
        `Can have up to 3 Crafted Modifiers`, whose limit is not modelled yet. An item that fails
        `Item.validate` raises its `ItemError`.
        """
        option = self.option(data)
        mod = data.mods.get(self.mod_id)
        if mod is None:
            raise ValueError(f"the bench option for {self.mod_id} names a mod that is not in the game data")
        item.validate(data)
        _refuse_if_corrupted(item, "bench craft")
        _refuse_if_class_not_offered(data, item, option, f"the craft {self.mod_id}")
        if item.rarity is Rarity.NORMAL:
            raise OutOfScopeError(
                "the item is normal; no admitted rule says what a bench craft does to a normal item"
            )
        if not item.mods:
            raise OutOfScopeError(f"the item is {item.rarity} and holds no mod, which no admitted rule covers")
        for entry in item.mods:
            if conflicts(data.mods[entry.mod_id], mod) or entry.mod_id == mod.id:
                raise NotApplicableError(
                    f"the item holds {entry.mod_id}, which shares a family with the craft {self.mod_id}"
                )
        side = Side(mod.generation_type)
        if item.free_slots(data, side) <= 0:
            raise NotApplicableError(f"the item has no free {side.value} slot for the craft {self.mod_id}")
        if Metamod.MULTIPLE_CRAFTED_MODS in item.metamods(data):
            raise OutOfScopeError(
                "the item holds the multimod 'Can have up to 3 Crafted Modifiers'; "
                "the limit of three crafted mods is not modelled yet"
            )
        if len(item.crafted_mods) >= ONE_CRAFTED_MOD.value:
            raise NotApplicableError(
                f"the item holds {len(item.crafted_mods)} crafted mod, which is the limit "
                f"({ONE_CRAFTED_MOD.value}); remove it first"
            )
        return BenchOutcomes(data, item, mod)


@dataclass(frozen=True)
class RemoveCraftedMods(Action):
    """The bench's Remove Crafted Mods: removes every crafted mod, metamods included."""

    def label(self, data: GameData | None = None) -> str:
        return "Remove Crafted Mods"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        if data is None:
            raise ValueError("Remove Crafted Mods is priced from the bench data, so it needs the data")
        return {entry.currency: entry.count for entry in self.cost(data)}

    def reads(self, data: GameData) -> Reads:
        """It reads how many mods are left, not which: the count of the junk, no family."""
        return Reads(junk=True, families=frozenset(), needs_crafted=True, block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.removal(keeps_crafted=False)

    def option(self, data: GameData) -> BenchOption:
        """The bench option that removes crafted mods; `ValueError` when the data has none."""
        for option in data.bench_options:
            if option.actions.remove_crafted_mods:
                return option
        raise ValueError("the bench has no option that removes crafted mods")

    def cost(self, data: GameData) -> tuple[CurrencyCost, ...]:
        """The price of one use, as currency names and counts."""
        return _cost(data, self.option(data))

    def outcomes(self, data: GameData, item: Item) -> BenchOutcomes:
        """The outcome of removing every crafted mod of `item`.

        Raises `NotApplicableError` for a corrupted item, an item class the option is not offered
        for, or an item with no crafted mod, and `OutOfScopeError` for a magic or rare item that would be
        left with no mod (no admitted rule says what it becomes). An item that fails `Item.validate`
        raises its `ItemError`.
        """
        item.validate(data)
        _refuse_if_corrupted(item, "Remove Crafted Mods")
        _refuse_if_class_not_offered(data, item, self.option(data), "Remove Crafted Mods")
        if not item.crafted_mods:
            raise NotApplicableError("the item holds no crafted mod, so there is nothing to remove")
        kept = tuple(entry for entry in item.mods if not entry.crafted)
        if not kept:
            raise OutOfScopeError(
                f"the item is {item.rarity} and holds only crafted mods; "
                "no admitted rule says what it becomes without a mod"
            )
        return BenchOutcomes(data, item.changed(data, mods=kept), None)


def bench_crafts(data: GameData) -> tuple[BenchCraft, ...]:
    """Every bench craft that adds a crafted mod, in the order of the bench data (732 in 3.29.3.3)."""
    return tuple(
        BenchCraft(option.actions.add_explicit_mod)
        for option in data.bench_options
        if option.actions.add_explicit_mod is not None
    )


@kind("bench-craft", order=40)
def _bench_crafts(data: GameData, item: Item):
    """Every craft the bench offers for the item class."""
    base = data.base_items.get(item.base_id)
    item_class = base.item_class if base is not None else None
    for craft in bench_crafts(data):
        if item_class in craft.option(data).item_classes:
            yield craft


@kind("remove-crafted-mods", order=50)
def _remove_crafted_mods(data: GameData, item: Item):
    if any(option.actions.remove_crafted_mods for option in data.bench_options):
        yield RemoveCraftedMods()
