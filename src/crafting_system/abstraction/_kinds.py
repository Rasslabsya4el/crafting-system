"""Which families the enabled actions can tell apart, and a concrete mod to stand for a slot.

A slot of a compressed state keeps no family unless an enabled action needs it. The actions that
erase the junk (`ChaosOrb`, `HarvestReforge`, `ApplyEssence`) read nothing of it; `RemoveCraftedMods`
reads only the count; a `BenchCraft` also reads the families, because it is refused when its mod
shares a family with a mod on the item, so the families of its crafted mod are told apart. Any other
action is not known to treat families alike, so with one of those every family is told apart.
"""

from collections.abc import Iterable

from crafting_system.actions import ApplyEssence, BenchCraft, ChaosOrb, HarvestReforge, RemoveCraftedMods, build_pool
from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Rarity, Side
from crafting_system.items.model import EXPLICIT_EXTRA_DOMAINS

ERASING = (ChaosOrb, HarvestReforge, ApplyEssence)
ALIKE = ""  # the kind of a family that every enabled action treats like any other of its side


def family_key(mod: Mod) -> str:
    """The families of a mod as one string; a mod without a family stands alone."""
    return "|".join(mod.families) or f"#{mod.id}"


def reads_junk(action: object) -> bool:
    """Whether `action` can see the mods that a Chaos Orb would erase (their number or their families)."""
    return not isinstance(action, ERASING)


class Kinds:
    """The kind of every ordinary mod, and the representative mods that stand for slots.

    `actions` are the enabled actions. With none that reads the junk, nothing is kept for it.
    """

    def __init__(self, data: GameData, base_id: str, item_level: int, actions: Iterable[object]):
        self.data = data
        self.base_id = base_id
        self.item_level = item_level
        self.actions = tuple(actions)
        self.tracked = any(reads_junk(action) for action in self.actions)
        self._distinct: set[str] = set()
        self._everything = False
        for action in self.actions:
            if isinstance(action, BenchCraft):
                self._distinct.update(data.mods[action.mod_id].families)
            elif reads_junk(action) and not isinstance(action, RemoveCraftedMods):
                self._everything = True
        self._listed: set[str] | None = None
        self._alike: dict[Side, list[tuple[str, Mod]]] = {}
        self._by_family: dict[str, list[Mod]] | None = None

    def of(self, mod: Mod) -> str:
        """The kind of an ordinary (not crafted) mod: `ALIKE` or its family key."""
        key = family_key(mod)
        if self._everything or key in self._distinct or key not in self._listed_families():
            return key
        return ALIKE

    def representative(self, side: Side, kind: str, taken: set[str]) -> Mod:
        """A mod to put on a concrete item for a slot of `side` and `kind`, of a family not in `taken`.

        The family key of the chosen mod is added to `taken`. Raises `ValueError` when the item has no
        room for one more of that kind.
        """
        if kind != ALIKE:
            if kind in taken:
                raise ValueError(f"two slots of the family {kind}: one item cannot hold both")
            taken.add(kind)
            return self._mod_of(kind, side)
        for key, mod in self._alike_of(side):
            if key not in taken:
                taken.add(key)
                return mod
        raise ValueError(f"the state has more {side.value} slots of an ordinary family than the pool has families")

    def _listed_families(self) -> set[str]:
        if self._listed is None:
            self._listed = {family.family for family in self._pool()}
        return self._listed

    def _pool(self):
        empty = Item.build(self.data, base_id=self.base_id, item_level=self.item_level, rarity=Rarity.RARE)
        return build_pool(self.data, empty)

    def _alike_of(self, side: Side) -> list[tuple[str, Mod]]:
        if side not in self._alike:
            self._alike[side] = [
                (family.family, family.mods[0].mod)
                for family in self._pool()
                if family.side is side and family.family not in self._distinct
            ]
        return self._alike[side]

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
