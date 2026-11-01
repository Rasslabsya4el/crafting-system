"""Which families the enabled actions can tell apart, and a concrete mod to stand for a slot.

A slot of a compressed state keeps no family unless an enabled action needs it. What an action needs
is its own declaration, `Action.reads(data)` (see `actions.Reads`): an action that reads nothing of
the junk erases it (a Chaos Orb, a Harvest reforge, an essence, a resonator) and needs no slot; one
that reads the junk needs its count, and the families it names (a bench craft: the families of its
mod, because it is refused when one is on the item), or every family when it names none. An action that
adds mods and keeps the junk (`Reads.adding`) needs the pool weight of the junk families, so they are
told apart by family type: side, and the weights and goal contribution of their mods. An action that
declares nothing reads everything, so with one of those every family is told apart.

With `metamods` (the state may hold a lock, an Attack or a Caster metamod) the junk is always kept and
told apart by family type, and the kind of a mod also carries the tags an Attack or Caster metamod looks
at (`"@attack"`, `"@attack+caster"`): an Annulment removes only the mods without a protected tag, so two
slots of one family type that differ in them are not alike. The "~n" of a kind stands for the family type
and never carries the tags itself (they belong to a mod); a family type is told from another one by the
tags of its mods too, so that a family whose mods differ in them is never mistaken for another family.

An action that rerolls the values of the mods an item holds (`Reads.rerolls_values`, a Divine Orb) makes the
result depend on which mod each slot stands for, as far as a roll requirement of the goal looks at its values.
Every ordinary family with a mod whose roll changes what it gives the goal (a rollable mod, `_rolls.py`) is then
told apart by MOD: all its mods have the kind `"$" + mod id`. The prefix is not "=" (that names a pool of families
in `_coarse.py`), "~" (a family type), "@" (the tags of a mod) or "#" (a family without a name).
"""

from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable

from crafting_system.actions import BLOCKED_TAG, Action, build_pool
from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Rarity, Side
from crafting_system.items.model import EXPLICIT_EXTRA_DOMAINS

ALIKE = ""  # the kind of a family that every enabled action treats like any other of its side
TYPE_PREFIX = "~"  # a kind that stands for a family type (pool weight), not for one family
MOD_PREFIX = "$"  # a kind that stands for one mod (a family with a rollable mod, when an action rerolls values): "$<mod id>"
TAG_MARK = "@"  # a kind with the protected tags of its mod: "<kind>@attack", "<kind>@attack+caster"
PROTECTED_TAGS = frozenset(BLOCKED_TAG.values())  # the tags an Attack or Caster metamod keeps out of a draw and an Annulment


def family_key(mod: Mod) -> str:
    """The families of a mod as one string; a mod without a family stands alone."""
    return "|".join(mod.families) or f"#{mod.id}"


def base_kind(kind: str) -> str:
    """`kind` without the tags of its mod: "~3@attack" -> "~3"."""
    return kind.partition(TAG_MARK)[0]


def kind_tags(kind: str) -> frozenset[str]:
    """The protected tags a kind carries ("~3@attack+caster" -> {"attack", "caster"}); none for a kind without them."""
    tail = kind.partition(TAG_MARK)[2]
    return frozenset(tail.split("+")) if tail else frozenset()


def protected_tags(mod: Mod) -> frozenset[str]:
    """The tags of `mod` that an Attack or Caster metamod looks at."""
    return PROTECTED_TAGS & set(mod.implicit_tags)


def held_families(mod: Mod) -> set[str]:
    """The families a mod on an item occupies, one by one (a mod can have several)."""
    return set(mod.families) or {f"#{mod.id}"}


class TypeNumbers:
    """The number of every family type ("~n"), shared by the kinds of all influence sets of one abstraction.

    A family type is `(side, sorted (profile, weight) of its mods)`. The first types asked for are
    numbered in sorted order (the same on every run); a type met later, in another influence set, gets the
    next numbers, so one "~n" always stands for one family type and two pools that read alike share a signature.
    """

    def __init__(self) -> None:
        self._numbers: dict[tuple, int] = {}
        self._sides: dict[str, Side] = {}

    def kinds_of(self, types: Iterable[tuple]) -> dict[tuple, str]:
        """The kind of each family type of `types`, numbering the new ones in sorted order."""
        wanted = set(types)
        for key in sorted(key for key in wanted if key not in self._numbers):
            number = self._numbers[key] = len(self._numbers)
            self._sides[f"{TYPE_PREFIX}{number}"] = Side(key[0])
        return {key: f"{TYPE_PREFIX}{self._numbers[key]}" for key in wanted}

    def side_of(self, kind: str) -> Side:
        return self._sides[kind]


class Kinds:
    """The kind of every ordinary mod, and the representative mods that stand for slots.

    `actions` are the enabled actions. With none that reads the junk, nothing is kept for it. With one
    that adds mods and keeps the junk (`Reads.pool_weight`), a family that no action tells apart by
    name has the kind of its family type: its side and the sorted (`profile(mod)`, weight) of its mods
    in the pool of an empty rare item (with the item's `influences`), `profile` being what a mod gives the goal.
    """

    def __init__(
        self,
        data: GameData,
        base_id: str,
        item_level: int,
        actions: Iterable[Action],
        profile: Callable[[Mod], Hashable] = lambda mod: (),
        *,
        metamods: bool = False,
        influences: frozenset = frozenset(),
        numbers: TypeNumbers | None = None,
        rollable: Callable[[], Iterable[Mod]] = lambda: (),
    ):
        self.data = data
        self.profile = profile
        self.base_id = base_id
        self.item_level = item_level
        self.metamods = metamods
        self.influences = influences
        self._numbers = numbers if numbers is not None else TypeNumbers()
        self.actions = tuple(actions)
        self.tracked = metamods or any(self.reads_junk(action) for action in self.actions)
        self._distinct: set[str] = set()
        self._everything = False
        self.by_weight = metamods
        self.fractures = False  # an enabled action may fracture a mod the item holds
        self.rerolls = False  # an enabled action rerolls the values of the mods the item holds
        self._rollable = rollable
        for action in self.actions:
            reads = action.reads(data)
            self.fractures = self.fractures or reads.fractures
            self.rerolls = self.rerolls or reads.rerolls_values
            if not reads.junk:
                continue
            self.by_weight = self.by_weight or reads.pool_weight
            if reads.families is None:
                self._everything = True
            else:
                self._distinct.update(reads.families)
        self._listed: set[str] | None = None
        self._by_mod: set[str] | None = None
        self._by_family: dict[str, list[Mod]] | None = None
        self._types: dict[str, str] | None = None
        self._members: dict[tuple[Side, str], list[tuple[str, tuple[Mod, ...]]]] = {}
        self._pooled = None

    def reads_junk(self, action: Action) -> bool:
        """Whether `action` can see the mods that a Chaos Orb would erase (their number or their families)."""
        return action.reads(self.data).junk

    def of(self, mod: Mod) -> str:
        """The kind of an ordinary (not crafted) mod: its family key, its family type's kind, or `ALIKE`.

        With `metamods` it also carries the protected tags of the mod (see the module docstring).
        """
        key = family_key(mod)
        if key in self._families_by_mod():
            kind = MOD_PREFIX + mod.id
        elif self._everything or key in self._distinct or key not in self._listed_families():
            kind = key
        elif self.by_weight:
            types = self._type_kinds()
            kind = types.get((key, mod.generation_type))
            if kind is None:  # a mod on a side where its family has no weight: the family's own type (the one side it has)
                kind = next((found for (name, _), found in types.items() if name == key), key)
        else:
            kind = ALIKE
        if self.metamods:
            tags = protected_tags(mod)
            if tags:
                kind += TAG_MARK + "+".join(sorted(tags))
        return kind

    def number_types(self) -> None:
        """Number the family types of this pool now (when mods are told apart by weight), before another influence set does."""
        if self.by_weight:
            self._type_kinds()

    def side_of(self, kind: str) -> Side:
        """The side of the family type a kind stands for ("~n", with or without tags); `ValueError` for another kind."""
        base = base_kind(kind)
        if not base.startswith(TYPE_PREFIX):
            raise ValueError(f"{kind!r} is not a family type")
        self._type_kinds()
        return self._numbers.side_of(base)

    def shared_families(self, kind: str) -> set[str]:
        """The families a family-type kind ("~n", tags ignored) stands for, or none when it stands for just one."""
        found = self._members_of(self.side_of(kind), base_kind(kind))
        return {family for family, _ in found} if len(found) > 1 else set()

    def representative(self, side: Side, kind: str, taken: set[str]) -> Mod:
        """A mod to put on a concrete item for a slot of `side` and `kind`, of a family not in `taken`.

        The families of the chosen mod are added to `taken` (single families, as `held_families`).
        With `metamods`, the mod has exactly the protected tags the kind carries.
        Raises `ValueError` when the item has no room for one more of that kind.
        """
        base, tags = base_kind(kind), kind_tags(kind)
        if base.startswith(MOD_PREFIX):
            mod = self.data.mods[base[len(MOD_PREFIX) :]]
            if mod.generation_type != side.value:
                raise ValueError(f"the mod {mod.id} is not a {side.value} mod")
            if held_families(mod) & taken:
                raise ValueError(f"two slots of the family of {mod.id}: one item cannot hold both")
            taken |= held_families(mod)
            return mod
        if base != ALIKE and not base.startswith(TYPE_PREFIX):
            mod = self._mod_of(base, side, tags)
            if held_families(mod) & taken:
                raise ValueError(f"two slots of the family {base}: one item cannot hold both")
            taken |= held_families(mod)
            return mod
        for key, mods in self._members_of(side, base):
            if key in taken:
                continue
            for mod in mods:
                if not self.metamods or protected_tags(mod) == tags:
                    taken.add(key)
                    return mod
        raise ValueError(f"the state has more {side.value} slots of an ordinary family of that type than the pool has families")

    def _families_by_mod(self) -> set[str]:
        """The families told apart by mod: those with a rollable mod, when an enabled action rerolls values; none otherwise."""
        if self._by_mod is None:
            self._by_mod = {family_key(mod) for mod in self._rollable()} if self.rerolls else set()
        return self._by_mod

    def _listed_families(self) -> set[str]:
        if self._listed is None:
            self._listed = {family.family for family in self._pool()}
        return self._listed

    def _pool(self):
        if self._pooled is None:
            empty = Item.build(
                self.data, base_id=self.base_id, item_level=self.item_level, rarity=Rarity.RARE, influences=self.influences
            )
            self._pooled = build_pool(self.data, empty)
        return self._pooled

    def _members_of(self, side: Side, kind: str) -> list[tuple[str, tuple[Mod, ...]]]:
        """The families (key and its mods) of the pool on `side` with this kind, in pool order."""
        if (side, kind) not in self._members:
            kinds = self._type_kinds() if self.by_weight else {}
            self._members[(side, kind)] = [
                (family.family, tuple(entry.mod for entry in family.mods))
                for family in self._pool()
                if family.side is side
                and family.family not in self._distinct
                and family.family not in self._families_by_mod()
                and (kinds[family.family, family.side.value] if self.by_weight else ALIKE) == kind
            ]
        return self._members[(side, kind)]

    def _type_kinds(self) -> dict[tuple[str, str], str]:
        """The kind of each family of the pool that no action tells apart by name, by `(family, side)`: one per family type, numbered in sorted order.

        A family with mods on both sides has a kind for each side. Its type holds the mods of the other
        side too, because holding the one takes the other out of the pool: a family of one side never
        shares a type with it.
        """
        if self._types is None:
            pool = self._pool()
            shapes = {
                (family.family, family.side.value): tuple(sorted(self._shape(entry) for entry in family.mods))
                for family in pool
            }
            sides_of: dict[str, list[str]] = defaultdict(list)
            for name, side in shapes:
                sides_of[name].append(side)
            types = {}
            for family in pool:
                if family.family in self._distinct or family.family in self._families_by_mod():
                    continue
                side = family.side.value
                other = tuple(sorted((o, shapes[family.family, o]) for o in sides_of[family.family] if o != side))
                types[family.family, side] = (side, shapes[family.family, side], other)
            kinds = self._numbers.kinds_of(types.values())
            self._types = {name: kinds[kind] for name, kind in types.items()}
        return self._types

    def _shape(self, entry) -> tuple:
        """What a mod of a family adds to its family type: what it gives the goal and its weight, and with `metamods` its protected tags.

        The tags are in the type (not only in the kind of a mod), so two families that hold the same mods
        apart from their tags never share a type: the representative of a slot is then any family of its type.
        """
        shape = (self.profile(entry.mod), entry.weight)
        return (*shape, tuple(sorted(protected_tags(entry.mod)))) if self.metamods else shape

    def _mod_of(self, key: str, side: Side, tags: frozenset[str] = frozenset()) -> Mod:
        """A mod of the family `key` on `side` that an ordinary slot can hold, found in the data (with `metamods`, with exactly `tags`)."""
        if self._by_family is None:
            grouped: dict[str, list[Mod]] = {}
            for mod in self.data.mods.values():
                grouped.setdefault(family_key(mod), []).append(mod)
            self._by_family = grouped
        domain = self.data.base_items[self.base_id].domain
        for mod in self._by_family.get(key, ()):
            if mod.generation_type == side.value and mod.domain in ({domain} | EXPLICIT_EXTRA_DOMAINS) - {"crafted"}:
                if not self.metamods or protected_tags(mod) == tags:
                    return mod
        raise ValueError(f"no {side.value} mod of the family {key} fits a base like {self.base_id}")
