"""The beast crafts that add a mod: the Wild Bristle Matron and the two side swaps (ticket #147, rules of issues #88 and #93, ADR-0030).

* `WildBristleMatron` adds one of the five metamods, uniformly among those that are allowed on the item
  (an open slot on the metamod's side, no family conflict, room for one more crafted mod).
* `BeastSideSwap` (Farric Wolf Alpha: add a prefix, remove a suffix; Farric Lynx Alpha: the other way round)
  adds a mod on one side drawn in proportion to weight, capped by the level of the beast and not the level of
  the item, and then removes one mod of the other side, uniformly among those that are not fractured.

Both answer with `Finite`: a short list of exact items with exact probabilities. The beasts they consume come
from `beasts.recipe_resources`. Several rules rest on Craft of Exile alone and carry the approximate mark (ADR-0028).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Item, Rarity, Side
from crafting_system.items.model import MAX_ITEM_LEVEL, MIN_ITEM_LEVEL
from crafting_system.rules import get_rule

from .bench import CRAFTED_TIER
from .beasts import ANY_RARE_CREATURE_PRICE, DEFAULT_BEAST_LEVEL, recipe_resources
from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .metamods import crafted_limit, locked_sides
from .pool import build_pool, tiers_of

__all__ = [
    "BeastSideSwap",
    "WildBristleMatron",
]

METAMOD_ONE_OF_FIVE = get_rule("beastcraft.metamod_one_of_five_if_allowed")
METAMOD_ODDS_UNIFORM = get_rule("beastcraft.metamod_odds_uniform")
METAMOD_NEEDS_SLOT_AND_ROOM = get_rule("beastcraft.metamod_needs_slot_and_crafted_room")
METAMOD_IDS = get_rule("beastcraft.metamod_ids")
SIDE_SWAP_NEEDS_RARE_AND_OPEN_SLOT = get_rule("beastcraft.side_swap_needs_rare_and_open_slot")
SIDE_SWAP_USES_BEAST_LEVEL = get_rule("beastcraft.side_swap_uses_beast_level")
SIDE_SWAP_ADDED_MOD_IS_A_DRAW = get_rule("beastcraft.side_swap_added_mod_is_a_draw")
SIDE_SWAP_REMOVAL_UNIFORM = get_rule("beastcraft.side_swap_removal_uniform")
SIDE_SWAP_METAMOD_RULES = get_rule("beastcraft.side_swap_metamod_rules")
SIDE_SWAP_REFUSED_WITHOUT_REMOVABLE_MOD = get_rule("beastcraft.side_swap_refused_without_removable_mod")
REFUSED_ON_CORRUPTED = get_rule("bench_craft.refused_on_corrupted")


def _low(mod: Mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


def _refuse_if_corrupted(item: Item, what: str) -> None:
    if item.corrupted:
        raise NotApplicableError(f"the item is corrupted, and a corrupted item takes no {what}")


def _metamod_classes(data: GameData) -> frozenset[str]:
    """The item classes the bench offers a metamod for: the five share one list (`bench_craft.option_item_classes`)."""
    ids = {mod.id for mod in wild_bristle_metamods(data)}
    return frozenset(
        item_class
        for option in data.bench_options
        if option.actions.add_explicit_mod in ids
        for item_class in option.item_classes
    )


def _allowed_classes(data: GameData, item: Item) -> tuple[Mod, ...]:
    """The metamods of the Matron when the bench offers metamods for the item class of `item` (a crafted mod could be added there), else none."""
    base = data.base_items.get(item.base_id)
    if base is None or base.item_class not in _metamod_classes(data):
        return ()
    return wild_bristle_metamods(data)


def wild_bristle_metamods(data: GameData) -> tuple[Mod, ...]:
    """The metamods the Matron can add that `data` holds, one per family of `beastcraft.metamod_ids`, in data order.

    A family the data holds no mod of on the side the claim names is left out.
    """
    wanted = METAMOD_IDS.value
    found: dict[str, Mod] = {}
    for mod in data.mods.values():
        for family in mod.families:
            if family in wanted and mod.generation_type == wanted[family]:
                found.setdefault(family, mod)
    return tuple(found.values())


@dataclass(frozen=True)
class WildBristleMatron(Action):
    """The beast recipe that adds one of the five metamods, uniformly among those the item allows."""

    rare_creature_price: int = ANY_RARE_CREATURE_PRICE.value

    def label(self, data: GameData | None = None) -> str:
        return "Beastcraft Wild Bristle Matron (add a metamod)"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return recipe_resources("add_metamod", self.rare_creature_price)

    def reads(self, data: GameData) -> Reads:
        """Like a bench craft: the craft is refused when one of the five families is on the item, and a metamod is one more crafted mod."""
        return Reads(junk=True, families=frozenset(METAMOD_IDS.value), block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # it picks among five mods, but only those five and always as a crafted mod: a draw that names none
        return Adds(named=None, crafted=True, draws=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of the recipe on `item`: one result per allowed metamod, each with chance 1/n.

        A metamod is allowed when the item has an open slot on its side, holds no mod of its family and
        holds fewer crafted mods than the limit (one, or three with the multimod), and the bench offers it for
        the item class of the base (`beastcraft.metamod_needs_slot_and_crafted_room`). The metamod is added as
        a crafted mod at its lowest values. As for a bench craft, `NotApplicableError` for a corrupted item,
        a full crafted limit, or no allowed metamod; `OutOfScopeError` for a normal item or one with no mod
        (no admitted rule says what the recipe does there). An item that fails `Item.validate` raises its `ItemError`.
        """
        item.validate(data)
        _refuse_if_corrupted(item, "beast craft")
        if item.rarity is Rarity.NORMAL:
            raise OutOfScopeError("the item is normal; no admitted rule says what the Wild Bristle Matron does to a normal item")
        if not item.mods:
            raise OutOfScopeError(f"the item is {item.rarity} and holds no mod, which no admitted rule covers")
        limit, held = crafted_limit(data, item), len(item.crafted_mods)
        if held >= limit:
            raise NotApplicableError(
                f"the item holds {held} crafted mod{'' if held == 1 else 's'}, which is the limit ({limit}); remove it first"
            )
        allowed = [
            mod
            for mod in _allowed_classes(data, item)
            if item.free_slots(data, Side(mod.generation_type)) > 0 and not item.blocks(data, mod)
        ]
        if not allowed:
            raise NotApplicableError(
                "no metamod is allowed on the item: each needs an open slot on its side and a family that is not on the item yet"
            )
        share = Fraction(1, len(allowed))
        return Finite(
            data,
            item,
            tuple((share, item.add_mod(data, ExplicitMod(mod.id, CRAFTED_TIER, _low(mod), crafted=True))) for mod in allowed),
        )


@kind("wild-bristle-matron", order=86, opt_in=True)
def _wild_bristle_matron(data: GameData, item: Item):
    if item.rarity is Rarity.RARE and _allowed_classes(data, item):
        yield WildBristleMatron()


@dataclass(frozen=True)
class BeastSideSwap(Action):
    """The beast recipe that adds a mod on `add_side` and removes one from the other side (Farric Wolf / Lynx Alpha)."""

    add_side: Side
    beast_level: int = DEFAULT_BEAST_LEVEL.value
    rare_creature_price: int = ANY_RARE_CREATURE_PRICE.value

    def __post_init__(self) -> None:
        if not isinstance(self.add_side, Side):
            raise ValueError(f"the side that is added must be a Side, not {self.add_side!r}")
        if type(self.beast_level) is not int or not MIN_ITEM_LEVEL <= self.beast_level <= MAX_ITEM_LEVEL:
            raise ValueError(f"the beast level must be a whole number from {MIN_ITEM_LEVEL} to {MAX_ITEM_LEVEL}, not {self.beast_level!r}")

    @property
    def remove_side(self) -> Side:
        return Side.SUFFIX if self.add_side is Side.PREFIX else Side.PREFIX

    @property
    def _recipe(self) -> str:
        return f"add_{self.add_side.value}_remove_{self.remove_side.value}"

    @property
    def variant(self) -> str:
        return f"beast level {self.beast_level}"

    def label(self, data: GameData | None = None) -> str:
        return f"Beastcraft Add {self.add_side.value.capitalize()} Remove {self.remove_side.value.capitalize()}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return recipe_resources(self._recipe, self.rare_creature_price)

    def reads(self, data: GameData) -> Reads:
        """The result depends on the count and the families of the junk of both sides and on the lock and tag metamods.

        The added mod is drawn from the pool at the level of the beast, which is not the level of the item, so the family
        types of the state carry the weight of each mod at the beast level too (`draw_levels`, #149): two families alike at
        the item's level but not at the beast's are never one type. The removal is uniform, so only counts matter.
        """
        return Reads(junk=True, families=frozenset(), pool_weight=True, draw_levels=frozenset({self.beast_level}))

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # `keeps_crafted` stays True: a crafted mod is one of the mods the removal may take, but it is not erased
        return Adds(named=None, draws=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of the recipe on `item`: the added mod and the removed mod, one result per pair.

        The added mod is drawn from the pool of `add_side` at the beast level (the item level is ignored,
        a family on the item and the Attack and Caster metamods respected) in proportion to weight; then one
        mod of the other side, among those the item held before the add that are not fractured, is removed
        uniformly (crafted mods and metamods included). If the other side is locked by a metamod nothing is
        removed. The added mod is a new mod at its lowest values and table tier.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, has no open slot on `add_side`,
        has an unlocked other side without a removable mod, or for which no mod is legal to add.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"a beast side swap works on a rare item only, and this item is {item.rarity}")
        _refuse_if_corrupted(item, "beast side swap")
        if item.free_slots(data, self.add_side) <= 0:
            raise NotApplicableError(f"the item has no open {self.add_side.value} slot for the mod the craft adds")
        if self.remove_side in locked_sides(data, item):
            removable: tuple[ExplicitMod | None, ...] = (None,)  # the lock of the losing side: it adds without removing
        else:
            removable = tuple(entry for entry in item.mods_on(data, self.remove_side) if not entry.fractured)
            if not removable:
                raise NotApplicableError(
                    f"the item has no {self.remove_side.value} that is not fractured to remove, and the {self.remove_side.value}es are not locked"
                )
        drawn = [
            entry
            for family in build_pool(data, item.changed(data, item_level=self.beast_level))
            if family.side is self.add_side
            for entry in family.mods
        ]
        total = sum((entry.weight for entry in drawn), Fraction(0))
        if not drawn:
            raise NotApplicableError(
                f"the beast cannot add a {self.add_side.value}: no mod of its pool is legal on the item at beast level {self.beast_level}"
            )
        tiers = tiers_of(data, item)
        after_removal = [item if gone is None else item.remove_mod(data, gone.mod_id) for gone in removable]
        results = []
        for entry in drawn:
            added = ExplicitMod(entry.mod.id, tiers.get(entry.mod.id, 1), _low(entry.mod))
            for retained in after_removal:
                results.append((entry.weight / total / len(after_removal), retained.add_mod(data, added)))
        return Finite(data, item, tuple(results))


@kind("beast-side-swap", order=85, opt_in=True)
def _beast_side_swaps(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        yield BeastSideSwap(Side.PREFIX)
        yield BeastSideSwap(Side.SUFFIX)
