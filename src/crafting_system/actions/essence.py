"""An essence: one forced mod on a normal item (Alchemy-style fill) or on a rare item (Chaos-style reforge)."""

from collections.abc import Mapping
from dataclasses import dataclass

from crafting_system.data import Essence, GameData, conflicts
from crafting_system.items import Item, Rarity, Side, UnknownBaseError, capacity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import refuse_unmodelled
from .errors import NotApplicableError, OutOfScopeError
from .outcomes import Outcomes

FORCED_MOD_BY_ITEM_CLASS = get_rule("essence.forced_mod_by_item_class")
DAGGER_STAFF_TAKE_CLASS_MODS = get_rule("essence.dagger_staff_take_class_mods")
NORMAL_ITEM_BECOMES_RARE_LIKE_ALCHEMY = get_rule("essence.normal_item_becomes_rare_like_alchemy")
RARE_ITEM_REFORGED_LIKE_CHAOS = get_rule("essence.rare_item_reforged_like_chaos")
NORMAL_ONLY_UP_TO_LEVEL = get_rule("essence.normal_only_up_to_level")
HIGHER_LEVELS_ALSO_REFORGE_RARES = get_rule("essence.higher_levels_also_reforge_rares")
LOW_LEVELS_CAP_RANDOM_MODS = get_rule("essence.low_levels_cap_random_mods")
FORCED_MOD_COUNTS_IN_TOTAL = get_rule("essence.forced_mod_counts_in_total")
FORCED_MOD_IGNORES_ITEM_LEVEL = get_rule("essence.forced_mod_ignores_item_level")
FRACTURED_MODS_KEPT = get_rule("essence.fractured_mods_kept")
REFUSED_ON_FAMILY_CLASH_WITH_FRACTURED = get_rule("essence.refused_on_family_clash_with_fractured")
REFORGE_REMOVES_CRAFTED_MODS = get_rule("essence.reforge_removes_crafted_mods")
REFUSED_ON_CORRUPTED = get_rule("essence.refused_on_corrupted")
DESOLATION_IS_NOT_A_B1_ACTION = get_rule("essence.desolation_is_not_a_b1_action")
COST = get_rule("essence.cost")


@dataclass(frozen=True)
class ApplyEssence(Action):
    """One essence, named as in the game data ("Shrieking Essence of Spite") or by its record id."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("an essence is named by its name or record id in the game data")

    def label(self, data: GameData | None = None) -> str:
        if data is None:
            raise ValueError("an essence is named as the game data names it, so it needs the data")
        return self._record(data).name

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        if data is None:
            raise ValueError("an essence is priced under the name the game data gives it, so it needs the data")
        return {self._record(data).name: 1}

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing(block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        if data is None or item is None:
            return Adds.erasing()
        base = data.base_items.get(item.base_id)
        mod_id = None if base is None else _forced_mod_id(self._record(data), base.item_class)
        return Adds.erasing() if mod_id is None else Adds.erasing(named=frozenset({mod_id}))

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The outcomes of using the essence on `item`.

        Raises `ValueError` for a name that is no essence in `data`, `NotApplicableError` for a
        magic item, a rare item and an essence that works on normal items only, a corrupted item,
        an item class that takes no essence, and a forced mod that shares a family with a fractured
        mod, and `OutOfScopeError` (no admitted rule covers it) for Essence of Desolation, an
        influenced item, one with a metamod, one whose fractured mods fill the side of the forced
        mod, and a level 1 to 4 essence that has no cap in the data.
        """
        essence = self._record(data)
        if item.rarity is Rarity.MAGIC:
            raise NotApplicableError("an essence works on a normal or rare item only, and this item is magic")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no essence")
        if essence.name == DESOLATION_IS_NOT_A_B1_ACTION.value:
            raise OutOfScopeError(
                f"{essence.name} is not a B1 action: it has no ordinary source in 3.29, so it is not modelled"
            )
        normal_only = essence.level <= NORMAL_ONLY_UP_TO_LEVEL.value
        if item.rarity is Rarity.RARE and normal_only:
            raise NotApplicableError(
                f"{essence.name} works on a normal item only, and this item is rare; "
                "an essence reforges a rare item from level "
                f"{NORMAL_ONLY_UP_TO_LEVEL.value + 1} (Screaming) on"
            )
        forced = self._forced_mod(data, essence, item)
        refuse_unmodelled(data, item)
        side = Side(forced.generation_type)
        for entry in item.fractured_mods:
            if conflicts(forced, data.mods[entry.mod_id]):
                raise NotApplicableError(
                    f"the item already has a mod of this type: the forced mod {forced.id} of "
                    f"{essence.name} shares a family with the fractured mod {entry.mod_id}"
                )
        used = sum(1 for entry in item.fractured_mods if data.mods[entry.mod_id].generation_type == side.value)
        if used >= capacity(data, item.base_id, Rarity.RARE).of(side):
            raise OutOfScopeError(
                f"the fractured mods fill every {side.value} slot, so the forced mod {forced.id} "
                "has no slot; no admitted rule says what the game does then"
            )
        max_level = None
        if normal_only:
            max_level = essence.item_level_restriction
            if max_level is None:
                raise OutOfScopeError(f"{essence.name} has no level cap in the game data")
        return Outcomes.reroll(data, item, tag=None, forced=forced, max_level=max_level)

    def _record(self, data: GameData) -> Essence:
        """The essence record named `self.name`, an essence craft (some record of the file is not one)."""
        for essence in data.essences.values():
            if self.name in (essence.name, essence.id):
                if all(entry.mod_id is None for entry in essence.mods):
                    raise ValueError(f"{self.name!r} is no essence craft: the data has no mod for it on any item class")
                return essence
        raise ValueError(f"there is no essence {self.name!r} in the game data")

    def _forced_mod(self, data: GameData, essence: Essence, item: Item):
        base = data.base_items.get(item.base_id)
        if base is None:
            raise UnknownBaseError(f"item on {item.base_id}: the base is not in the game data")
        mod_id = _forced_mod_id(essence, base.item_class)
        if mod_id is None:
            raise NotApplicableError(f"{essence.name} gives no mod on {base.item_class}, so it takes no essence")
        return data.mods[mod_id]


def _forced_mod_id(essence: Essence, item_class: str) -> str | None:
    """The id of the mod `essence` forces on an item of `item_class`, None when the class takes no essence."""
    mod_id = essence.mod_for(item_class)
    if mod_id is None:
        mod_id = essence.mod_for(DAGGER_STAFF_TAKE_CLASS_MODS.value.get(item_class, item_class))
    return mod_id


@kind("essence", order=30)
def _essences(data: GameData, item: Item):
    """Every essence the item class takes; those of level 1 to 4 work on a normal item only, so only a normal item lists them."""
    for record in data.essences.values():
        if record.is_corruption_only or record.name == DESOLATION_IS_NOT_A_B1_ACTION.value:
            continue
        if record.level <= NORMAL_ONLY_UP_TO_LEVEL.value and item.rarity is not Rarity.NORMAL:
            continue
        base = data.base_items.get(item.base_id)
        if base is not None and _forced_mod_id(record, base.item_class) is not None:
            yield ApplyEssence(record.name)
