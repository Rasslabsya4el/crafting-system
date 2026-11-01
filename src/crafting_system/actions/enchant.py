"""The Tempering Orb and the Tailoring Orb: one draw from the enchant pool of the item class; the new enchant replaces the old (ticket #239).

The family of the two heist orbs (ADR-0050, ADR-0051). `TemperingOrb()` works on a weapon (any base the item model gives the `weapon`
tag) and `TailoringOrb()` on a body armour; each puts one enchantment on the item, drawn **with replacement** from its pool, and a
second click replaces the first (`enchantment.one_slot_new_replaces_old`). They are the kinds `tempering` and `tailoring`.

**The pool** is the mods of the group `EnchantmentHeistWeapon` (136 in 3.29) or `EnchantmentHeistArmour` (54) that the 3.29.0 note did
not remove (`enchantment.weapon_pool_136`, `enchantment.armour_pool_54`, approximate, `items.enchant_info` decides which mod is in it).
It does not depend on the item level or the rarity. The extra crafted slot is a member of the pool at its Curio weight: a click that
rolls it leaves the item with that enchant, and the finish cost treats it as a click that misses (ADR-0051).

**The weights** are the players' counts of the Curio Displays, stored as data in the claims `enchantment.body_armour_weight_classes`
(one weight per *kind* of enchant: `kinds` holds, for each kind, how many enchants it has and the sample items it covers, and the
weight of an enchant is those items over those enchants) and `enchantment.weapon_weights_depend_on_tag` (one weight per enchant:
`count_of`). Both are marked `approximate`, with `enchantment.pool_is_weighted` (the assumption that the orbs draw from the Curio table,
ADR-0051); `Action.claims` names them so a report prints them under "Approximate inputs". A pool mod the claim gives no weight is an
`OutOfScopeError` that names it (the data and the claim must be moved together, ADR-0024).

**The result** is an `EnchantOutcomes`: one item per pool enchant, with its share of the total weight, the mods untouched. Because it is
a *finish step*, ADR-0050 keeps the enchantment out of the compressed state: the actions declare `Adds(enchantment=True)` and read
neither the enchantment they replace nor anything of the item but its mods' count. `chance_all` is the contract's (the chance that the
result holds mods as *explicit* mods), so it is 0 for an enchant; the weight share of an enchant is `chance_enchant`, and
`shares` lists them all. The planner does not search over the orbs as steps (ADR-0050: it prices them through the finish cost), so both
kinds are no planner kinds; they stay in the catalog, under the contract suite, and a route may name them.

**Refusals.** Nothing is consumed in either case, and the message names the reason:

* `NotApplicableError` for an item of the wrong class: a Tempering Orb on anything that is not a weapon (a shield, a quiver, an
  armour piece), a Tailoring Orb on anything that is not a body armour.
* `OutOfScopeError` for a corrupted item: no admitted rule says an orb works on one (ADR-0004; `enchantment.mirrored_and_corruption`
  only says that corrupting keeps the enchantment and that the bench needs an uncorrupted item).
* A mirrored item is refused by the game (`enchantment.mirrored_and_corruption`), but the item model holds no mirrored item, so there
  is nothing to refuse here; the same is true of the fixed sockets that stop a Tailoring Orb (`enchantment.tailoring_not_on_fixed_sockets`):
  they belong to unique items, which the model does not hold either.

**The price** is read from the price file by the name in the claims `tempering_orb.cost` and `tailoring_orb.cost` (the item's name in the
game data); an offer whose price the file lacks is dropped and reported with that name (`cli._offers.price_offers`, ADR-0007). The bench
removal of an enchantment (3 Orbs of Scouring, `enchantment.bench_removes_for_three_scouring`) is not an action: clicking again
replaces for free. The reforge of the sockets that a socket-stat enchant causes is not modelled (the planner models no sockets before B6;
`enchantment.socket_stat_enchant_reforges_sockets`), and neither is the Memory Strands count, which the Tailoring Orb leaves alone
(`enchantment.tailoring_orb_leaves_memory_strands`).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property
from typing import ClassVar

from crafting_system.data import GameData, Mod
from crafting_system.items import EnchantClass, EnchantKind, Item, enchant_class, enchant_info
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite

__all__ = [
    "EnchantOutcomes",
    "TailoringOrb",
    "TemperingOrb",
    "enchant_pool",
]

HEIST_ORBS_ADD_OR_REPLACE = get_rule("enchantment.heist_orbs_add_or_replace")
ONE_SLOT_NEW_REPLACES_OLD = get_rule("enchantment.one_slot_new_replaces_old")
MIRRORED_AND_CORRUPTION = get_rule("enchantment.mirrored_and_corruption")
TAILORING_NOT_ON_FIXED_SOCKETS = get_rule("enchantment.tailoring_not_on_fixed_sockets")
REMOVED_FROM_POOL_IN_3_29_0 = get_rule("enchantment.removed_from_pool_in_3_29_0")
WEAPON_POOL_136 = get_rule("enchantment.weapon_pool_136")
ARMOUR_POOL_54 = get_rule("enchantment.armour_pool_54")
POOL_IS_WEIGHTED = get_rule("enchantment.pool_is_weighted")
BODY_ARMOUR_WEIGHT_CLASSES = get_rule("enchantment.body_armour_weight_classes")
WEAPON_WEIGHTS_DEPEND_ON_TAG = get_rule("enchantment.weapon_weights_depend_on_tag")
EXTRA_CRAFTED_MODIFIER_CURIO_DISPLAY_RATE = get_rule("enchantment.extra_crafted_modifier_curio_display_rate")
TEMPERING_COST = get_rule("tempering_orb.cost")
TAILORING_COST = get_rule("tailoring_orb.cost")

ONE = Fraction(1)
_POOLS: dict[tuple[int, EnchantClass], tuple[GameData, tuple[tuple[Mod, Fraction], ...]]] = {}


def enchant_pool(data: GameData, item_class: EnchantClass) -> tuple[tuple[Mod, Fraction], ...]:
    """The pool of the orb of `item_class` with the weight of each enchant, in data order.

    A pool enchant is a mod `items.enchant_info` takes for one of the Tempering or Tailoring pool (the ones the 3.29.0 note removed
    are not). The weight is read from the claims (see the module docstring) and is a `Fraction`; it is not normalised, the draw divides by the sum.
    Raises `OutOfScopeError` when the data holds no enchant of the class or the claim gives a pool enchant no weight.
    A result is cached per game data object; the entry keeps `data` alive, so its `id` cannot be reused while it is cached.
    """
    key = (id(data), item_class)
    found = _POOLS.get(key)
    if found is not None and found[0] is data:
        return found[1]
    weigh = _armour_weight if item_class is EnchantClass.BODY_ARMOUR else _weapon_weight
    pool = []
    for mod in data.mods.values():
        info = enchant_info(mod)
        if info is not None and info.kind is EnchantKind.POOL and info.item_class is item_class:
            pool.append((mod, weigh(mod)))
    if not pool:
        raise OutOfScopeError(f"the game data holds no {item_class.value} enchantment of the Tempering or Tailoring pool")
    if len(_POOLS) >= 64:
        _POOLS.clear()
    _POOLS[key] = (data, tuple(pool))
    return _POOLS[key][1]


def _armour_weight(mod: Mod) -> Fraction:
    value = BODY_ARMOUR_WEIGHT_CLASSES.value
    kind_name = value["kind_of"].get(mod.id)
    if kind_name is None:
        raise OutOfScopeError(f"the claim {BODY_ARMOUR_WEIGHT_CLASSES.id} gives the body armour enchant {mod.id} no weight")
    entry = value["kinds"][kind_name]
    return Fraction(entry["items"], entry["enchants"])


def _weapon_weight(mod: Mod) -> Fraction:
    count = WEAPON_WEIGHTS_DEPEND_ON_TAG.value["count_of"].get(mod.id)
    if count is None:
        raise OutOfScopeError(f"the claim {WEAPON_WEIGHTS_DEPEND_ON_TAG.id} gives the weapon enchant {mod.id} no weight")
    return Fraction(count)


@dataclass(frozen=True, eq=False)
class EnchantOutcomes(Finite):
    """One result per pool enchant: the item with that enchantment and the same mods, each with its weight share.

    `chance_all` is the one of every action (the chance that the result holds mods as explicit mods), so for an enchant it is 0;
    `chance_enchant` is the chance of the enchantment and `shares` lists them. The new mods of a result are none, so `distribution` is the one empty outcome.
    """

    @cached_property
    def shares(self) -> Mapping[str, Fraction]:
        """The chance of each pool enchant on the result, by mod id; they sum to 1."""
        return {item.enchantment: chance for chance, item in self.results}

    def chance_enchant(self, mod_ids: Iterable[str]) -> Fraction:
        """The chance that the new enchantment is one of `mod_ids` (the sum of their shares: the draw is with replacement).

        A mod of the game data that is not in the pool (a Harvest quality enchant, an explicit mod) adds nothing; a mod that is not in the
        game data raises `ValueError`, as `chance_all` does.
        """
        wanted = set(mod_ids)
        unknown = sorted(wanted - self.data.mods.keys())
        if unknown:
            raise ValueError(f"mod {unknown[0]} is not in the game data")
        return sum((share for mod_id, share in self.shares.items() if mod_id in wanted), Fraction(0))


@dataclass(frozen=True)
class _EnchantOrb(Action):
    """What the two orbs share: the class they work on, the draw, and the declarations. Not a kind of its own."""

    LABEL: ClassVar[str]
    ITEM_CLASS: ClassVar[EnchantClass]
    COST: ClassVar
    CLAIMS: ClassVar[frozenset[str]]

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        # exactly the claims of this orb: the file holds two orbs that read different weight tables and prices
        return self.CLAIMS

    def label(self, data: GameData | None = None) -> str:
        return self.LABEL

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(self.COST.value)

    def reads(self, data: GameData) -> Reads:
        # It keeps the mods of the item and looks at their count only; it does not look at the enchantment it replaces.
        return Reads(junk=True, families=frozenset())

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # It draws no mod and names none; it sets the enchantment, which is no part of the compressed state (ADR-0050).
        return Adds(named=frozenset(), draws=False, enchantment=True)

    def outcomes(self, data: GameData, item: Item) -> EnchantOutcomes:
        """The outcomes of one click on `item`: one result per enchant of the pool, with its weight share, the old enchantment replaced.

        Raises `NotApplicableError` for an item of the wrong class and `OutOfScopeError` for a corrupted item or a pool the claims do not cover.
        """
        held = enchant_class(data.base_items[item.base_id])
        if held is not self.ITEM_CLASS:
            raise NotApplicableError(
                f"a {self.LABEL} works on a {self.ITEM_CLASS.value} only, and this item is a {data.base_items[item.base_id].item_class}"
            )
        if item.corrupted:
            raise OutOfScopeError(
                f"the item is corrupted, and no admitted rule says a {self.LABEL} works on a corrupted item ({MIRRORED_AND_CORRUPTION.id})"
            )
        pool = enchant_pool(data, self.ITEM_CLASS)
        total = sum((weight for _, weight in pool), Fraction(0))
        results = tuple((weight / total, item.changed(data, enchantment=mod.id)) for mod, weight in pool)
        return EnchantOutcomes(data, item, results)


@dataclass(frozen=True)
class TemperingOrb(_EnchantOrb):
    """One Tempering Orb: a weapon gets an enchantment of the weapon pool."""

    LABEL: ClassVar[str] = "Tempering Orb"
    ITEM_CLASS: ClassVar[EnchantClass] = EnchantClass.WEAPON
    COST: ClassVar = TEMPERING_COST
    CLAIMS: ClassVar[frozenset[str]] = frozenset(
        rule.id
        for rule in (
            HEIST_ORBS_ADD_OR_REPLACE, ONE_SLOT_NEW_REPLACES_OLD, MIRRORED_AND_CORRUPTION, REMOVED_FROM_POOL_IN_3_29_0, WEAPON_POOL_136,
            POOL_IS_WEIGHTED, WEAPON_WEIGHTS_DEPEND_ON_TAG, EXTRA_CRAFTED_MODIFIER_CURIO_DISPLAY_RATE, TEMPERING_COST,
        )
    )


@dataclass(frozen=True)
class TailoringOrb(_EnchantOrb):
    """One Tailoring Orb: a body armour gets an enchantment of the body armour pool."""

    LABEL: ClassVar[str] = "Tailoring Orb"
    ITEM_CLASS: ClassVar[EnchantClass] = EnchantClass.BODY_ARMOUR
    COST: ClassVar = TAILORING_COST
    CLAIMS: ClassVar[frozenset[str]] = frozenset(
        rule.id
        for rule in (
            HEIST_ORBS_ADD_OR_REPLACE, ONE_SLOT_NEW_REPLACES_OLD, MIRRORED_AND_CORRUPTION, TAILORING_NOT_ON_FIXED_SOCKETS,
            REMOVED_FROM_POOL_IN_3_29_0, ARMOUR_POOL_54, POOL_IS_WEIGHTED, BODY_ARMOUR_WEIGHT_CLASSES,
            EXTRA_CRAFTED_MODIFIER_CURIO_DISPLAY_RATE, TAILORING_COST,
        )
    )


@kind(
    "tempering",
    order=95,
    planner=False,
    why_not="the planner prices the orb through the finish cost of a target that names an enchantment (ADR-0050), it does not search over its clicks",
    applies_only_to="weapon",
)
def _tempering(data: GameData, item: Item):
    if enchant_class(data.base_items[item.base_id]) is EnchantClass.WEAPON:
        yield TemperingOrb()


@kind(
    "tailoring",
    order=96,
    planner=False,
    why_not="the planner prices the orb through the finish cost of a target that names an enchantment (ADR-0050), it does not search over its clicks",
    applies_only_to="body armour",
)
def _tailoring(data: GameData, item: Item):
    if enchant_class(data.base_items[item.base_id]) is EnchantClass.BODY_ARMOUR:
        yield TailoringOrb()
