"""Which families the enabled actions can tell apart, and a concrete mod to stand for a slot.

A slot of a compressed state keeps no family unless an enabled action needs it. What an action needs
is its own declaration, `Action.reads(data)` (see `actions.Reads`): an action that reads nothing of
the junk erases it (a Chaos Orb, a Harvest reforge, an essence, a resonator) and needs no slot; one
that reads the junk needs its count, and the families it names (a bench craft: the families of its
mod, because it is refused when one is on the item), or every family when it names none. An action that
adds mods and keeps the junk (`Reads.adding`) needs the pool weight of the junk families, so they are
told apart by family type: side, and the weights and goal contribution of their mods. An action that
declares nothing reads everything, so with one of those every family is told apart.
"""

from collections.abc import Callable, Hashable, Iterable

from crafting_system.actions import Action, build_pool
from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Rarity, Side
from crafting_system.items.model import EXPLICIT_EXTRA_DOMAINS

ALIKE = ""  # the kind of a family that every enabled action treats like any other of its side
TYPE_PREFIX = "~"  # a kind that stands for a family type (pool weight), not for one family


def family_key(mod: Mod) -> str:
    """The families of a mod as one string; a mod without a family stands alone."""
    return "|".join(mod.families) or f"#{mod.id}"


def held_families(mod: Mod) -> set[str]:
    """The families a mod on an item occupies, one by one (a mod can have several)."""
    return set(mod.families) or {f"#{mod.id}"}


class Kinds:
    """The kind of every ordinary mod, and the representative mods that stand for slots.

    `actions` are the enabled actions. With none that reads the junk, nothing is kept for it. With one
    that adds mods and keeps the junk (`Reads.pool_weight`), a family that no action tells apart by
    name has the kind of its family type: its side and the sorted (`profile(mod)`, weight) of its mods
    in the pool of an empty rare item, `profile` being what a mod gives the goal.
    """

    def __init__(
        self,
        data: GameData,
        base_id: str,
        item_level: int,
        actions: Iterable[Action],
        profile: Callable[[Mod], Hashable] = lambda mod: (),
    ):
        self.data = data
        self.profile = profile
        self.base_id = base_id
        self.item_level = item_level
        self.actions = tuple(actions)
        self.tracked = any(self.reads_junk(action) for action in self.actions)
        self._distinct: set[str] = set()
        self._everything = False
        self.by_weight = False
        for action in self.actions:
            reads = action.reads(data)
            if not reads.junk:
                continue
            self.by_weight = self.by_weight or reads.pool_weight
            if reads.families is None:
                self._everything = True
            else:
                self._distinct.update(reads.families)
        self._listed: set[str] | None = None
        self._by_family: dict[str, list[Mod]] | None = None
        self._types: dict[str, str] | None = None
        self._members: dict[str, list[tuple[str, Mod]]] = {}

    def reads_junk(self, action: Action) -> bool:
        """Whether `action` can see the mods that a Chaos Orb would erase (their number or their families)."""
        return action.reads(self.data).junk

    def of(self, mod: Mod) -> str:
        """The kind of an ordinary (not crafted) mod: its family key, its family type's kind, or `ALIKE`."""
        key = family_key(mod)
        if self._everything or key in self._distinct or key not in self._listed_families():
            return key
        return self._type_kinds()[key] if self.by_weight else ALIKE

    def representative(self, side: Side, kind: str, taken: set[str]) -> Mod:
        """A mod to put on a concrete item for a slot of `side` and `kind`, of a family not in `taken`.

        The families of the chosen mod are added to `taken` (single families, as `held_families`).
        Raises `ValueError` when the item has no room for one more of that kind.
        """
        if kind != ALIKE and not kind.startswith(TYPE_PREFIX):
            mod = self._mod_of(kind, side)
            if held_families(mod) & taken:
                raise ValueError(f"two slots of the family {kind}: one item cannot hold both")
            taken |= held_families(mod)
            return mod
        for key, mod in self._members_of(side, kind):
            if key not in taken:
                taken.add(key)
                return mod
        raise ValueError(f"the state has more {side.value} slots of an ordinary family of that type than the pool has families")

    def _listed_families(self) -> set[str]:
        if self._listed is None:
            self._listed = {family.family for family in self._pool()}
        return self._listed

    def _pool(self):
        empty = Item.build(self.data, base_id=self.base_id, item_level=self.item_level, rarity=Rarity.RARE)
        return build_pool(self.data, empty)

    def _members_of(self, side: Side, kind: str) -> list[tuple[str, Mod]]:
        """The families (key and one mod) of the pool on `side` with this kind, in pool order."""
        if (side, kind) not in self._members:
            kinds = self._type_kinds() if self.by_weight else {}
            self._members[(side, kind)] = [
                (family.family, family.mods[0].mod)
                for family in self._pool()
                if family.side is side
                and family.family not in self._distinct
                and (kinds[family.family] if self.by_weight else ALIKE) == kind
            ]
        return self._members[(side, kind)]

    def _type_kinds(self) -> dict[str, str]:
        """The kind of each family of the pool that no action tells apart by name: one per family type, numbered in sorted order."""
        if self._types is None:
            types = {
                family.family: (
                    family.side.value,
                    tuple(sorted((self.profile(entry.mod), entry.weight) for entry in family.mods)),
                )
                for family in self._pool()
                if family.family not in self._distinct
            }
            number = {kind: index for index, kind in enumerate(sorted(set(types.values())))}
            self._types = {name: f"{TYPE_PREFIX}{number[kind]}" for name, kind in types.items()}
        return self._types

    def _mod_of(self, key: str, side: Side) -> Mod:
        """A mod of the family `key` on `side` that an ordinary slot can hold, found in the data."""
        if self._by_family is None:
            grouped: dict[str, list[Mod]] = {}
            for mod in self.data.mods.values():
                grouped.setdefault(family_key(mod), []).append(mod)
            self._by_family = grouped
        domain = self.data.base_items[self.base_id].domain
        for mod in self._by_family.get(key, ()):
            if mod.generation_type == side.value and mod.domain in ({domain} | EXPLICIT_EXTRA_DOMAINS) - {"crafted"}:
                return mod
        raise ValueError(f"no {side.value} mod of the family {key} fits a base like {self.base_id}")
